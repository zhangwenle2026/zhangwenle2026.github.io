/**
 * sql-shim.js — CatDesk 环境下的 sql-cli 包装器
 *
 * 用法：node <skill_dir>/scripts/sql-shim.js <args...>
 *
 * 【CatDesk 环境】
 *   sql login 的 fallback 路径会通过 @mtfe/sso-web-oidc-cli 调用 open(url) 打开浏览器。
 *   本 shim 在 CatDesk 环境下做四件事：
 *     1. 注入 AGENT_SSO_CLIENT_ID 环境变量（触发 loginViaMtsso 路径，优先走 MOA 换票）
 *     2. 把 scripts/ 注入到子进程 PATH 最前面（确保版本检查时的路径跳过逻辑正确）
 *     3. 通过 NODE_OPTIONS --import 注入 ESM preload，patch sql-cli 内置的 open 模块，
 *        将 open(url) 替换为 catdesk browser-action（CatDesk 内置浏览器）
 *     4. 在执行命令前自动检查登录状态（sql login --check），未登录则先执行 sql login
 *
 * 【版本检查】
 *   委托给 platform-compat.ensureGlobalCli：
 *   未安装或版本低于 MIN_SQL_VERSION 时自动 npm install -g，安装后重新验证；
 *   仍不满足则打印错误并以 exit code 1 退出。
 *
 * 【登录检查】
 *   执行任何命令前（login 命令本身除外），先运行 sql login 检查登录状态。
 *   已登录时 login 会直接输出成功信息并以 0 退出；未登录时会触发浏览器 SSO 流程。
 *   login 检查复用相同的 childEnv（含 NODE_OPTIONS preload patch），
 *   确保 CatDesk 环境下 open 被正确替换为 catdesk browser-action。
 *
 * 【非 CatDesk 环境】直接透传给真正的 sql，不做任何修改。
 *
 * 【CatDesk 环境检测】
 *   委托给 platform-compat.isCatDesk()，详见该函数文档。
 */

'use strict';

const path = require('path');
const fs = require('fs');
const os = require('os');
const compat = require('./platform-compat');
const { cliOpts, registry } = require('./deps');
const step = require('./lx-step');

const SCRIPT_DIR = __dirname;
const { IS_WIN, isCatDesk } = compat;
const SEP = IS_WIN ? ';' : ':';

// ── 主逻辑 ────────────────────────────────────────────────────────────────────

// 确保 sql 已安装且版本满足要求；未安装/版本过低时自动安装/升级
const { binPath: real, pkgDir: sqlCliPkg } = compat.ensureGlobalCli({
  ...cliOpts('sql'),
  registry,
  skipDirs:  [SCRIPT_DIR],   // 跳过 scripts/ 自身，避免递归调用到本 shim
  logPrefix: '[sql-shim]',
});

const childEnv = { ...process.env };

if (isCatDesk()) {
  // 1. 注入 AGENT_SSO_CLIENT_ID，触发 loginViaMtsso() 路径
  childEnv.AGENT_SSO_CLIENT_ID = process.env.AGENT_SSO_CLIENT_ID || 'catdesk';

  // 2. 把 scripts/ 注入到 PATH 最前面（确保 ensureGlobalCli 的路径跳过正确）
  childEnv.PATH = [
    SCRIPT_DIR,
    ...(process.env.PATH || '').split(SEP).filter(d => path.resolve(d) !== path.resolve(SCRIPT_DIR)),
  ].join(SEP);

  // 3. 通过 NODE_OPTIONS --import 注入 ESM preload，patch open 模块
  //    sql-cli 是 ESM 包，--require 对其无效，必须用 --import
  //    preload 是 ESM 文件，用 createRequire 操作 CJS require.cache
  if (sqlCliPkg) {
    const openModulePath = path.join(sqlCliPkg, 'node_modules', 'open', 'index.js');
    if (fs.existsSync(openModulePath)) {
      const { bin: catdeskBin } = compat.resolveCatdesk();
      const preloadPath = path.join(os.tmpdir(), `sql-shim-open-patch-${process.pid}.mjs`);
      // compat 统一生成 preload 内容并写文件，返回 --import <url> 片段
      const importOption = compat.writePreloadAndGetNodeOption(
        openModulePath, catdeskBin, preloadPath, '[sql-shim]'
      );
      const existingNodeOptions = (process.env.NODE_OPTIONS || '').trim();
      childEnv.NODE_OPTIONS = [importOption, existingNodeOptions].filter(Boolean).join(' ');
    }
  }
}

// ── 内置子命令：template vars / template resolve ──────────────────────────────
//
// 【template vars】
//   用法：node sql-shim.js template vars <templateId> <verNo> [--with-statement]
//   功能：获取模板 SQL 原文，解析其中需要用户提供值的变量，stdout 输出一行 JSON：
//     成功：{ "status":"ok", "vars": [...] }
//     失败：{ "status":"error", "step":"get|vars|login|args", "message":"..." }
//   选项：
//     --with-statement  同时在输出中附带原始 SQL statement（默认不返回）
//   注意：
//     - 登录检查使用 `sql login --status`（非阻塞，未登录时立即以非零退出，不打开浏览器）
//     - vars 只返回"需要赋值"的变量（系统自动变量 $$today 等已被过滤），每项仅保留 LLM 所需字段
//     - vars 请求失败时降级返回空数组并附带 varsError 字段（status 仍为 ok）
//
// 【template resolve】
//   用法：node sql-shim.js template resolve <templateId> <verNo> [--var k=v]... (--work-dir <path> | --out <file>)
//   功能：
//     1. 调用 `sql template get <id> <verNo> --save <tmpSql>` 获取模板 SQL 原文
//     2. 将 SQL 写成 { "statement": "..." } 的 JSON 文件，调用 `sql query vars --file` 解析变量
//        - 返回的是"需要赋值"的变量列表（系统自动变量如 $$today 已被过滤，不会出现）
//     3. 调用 `sql query resolve --file <json> [--var k=v]...` 渲染可执行 SQL
//     4. 将渲染后的 SQL 写入输出文件：
//        - --work-dir <path>：输出到 <path>/bi-query-sql/sql/<ts>_<rand>.sql（与普通 SQL 文件路径规范一致）
//        - --out <file>：直接指定输出路径（优先级高于 --work-dir）
//        - 两者均未传：退出并报错
//     5. stdout 输出一行 JSON：
//        成功：{ "status":"ok", "vars": [...], "outputPath": "..." }
//        失败：{ "status":"error", "step":"get|vars|resolve|write|login|args", "message":"..." }
//   注意：所有中间临时文件在退出前清理

const userArgs = process.argv.slice(2);
const firstArg = userArgs[0];
const secondArg = userArgs[1];

function stdoutWriteAndExit(data, exitCode, stepMeta) {
  process.stdout.write(data, () => {
    if (stepMeta) {
      step(stepMeta.id, stepMeta.name, stepMeta.customRecord).finally(() => process.exit(exitCode));
    } else {
      process.exit(exitCode);
    }
  });
}

// ── 公共工具：构建 childEnv + runSql（供 template vars / resolve 共用）──────
// 注意：real / sqlCliPkg / isCatDesk / SCRIPT_DIR / SEP 均已在上方声明

/**
 * 构建子进程环境变量（等同于下方主流程的 childEnv 构建逻辑）。
 * 抽为函数供内置子命令提前使用（主流程的 childEnv 在拦截块之后才被赋值）。
 */
function buildChildEnv() {
  const env = { ...process.env };
  if (isCatDesk()) {
    env.AGENT_SSO_CLIENT_ID = process.env.AGENT_SSO_CLIENT_ID || 'catdesk';
    env.PATH = [
      SCRIPT_DIR,
      ...(process.env.PATH || '').split(SEP).filter(d => path.resolve(d) !== path.resolve(SCRIPT_DIR)),
    ].join(SEP);
    if (sqlCliPkg) {
      const openModulePath = path.join(sqlCliPkg, 'node_modules', 'open', 'index.js');
      if (fs.existsSync(openModulePath)) {
        const { bin: catdeskBin } = compat.resolveCatdesk();
        const preloadPath = path.join(os.tmpdir(), `sql-shim-open-patch-${process.pid}.mjs`);
        const importOption = compat.writePreloadAndGetNodeOption(
          openModulePath, catdeskBin, preloadPath, '[sql-shim]'
        );
        const existingNodeOptions = (process.env.NODE_OPTIONS || '').trim();
        env.NODE_OPTIONS = [importOption, existingNodeOptions].filter(Boolean).join(' ');
      }
    }
  }
  return env;
}

/**
 * 解析 sql cli stdout，取最后一个完整 JSON 对象（兼容升级提示行）。
 */
function parseLastJson(raw) {
  if (!raw) return null;
  const segments = [];
  let depth = 0, start = -1;
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] === '{') { if (depth === 0) start = i; depth++; }
    else if (raw[i] === '}') { depth--; if (depth === 0 && start !== -1) { segments.push(raw.slice(start, i + 1)); start = -1; } }
  }
  for (let i = segments.length - 1; i >= 0; i--) {
    try { return JSON.parse(segments[i]); } catch (_) {}
  }
  return null;
}

// ── 内置子命令：template vars ─────────────────────────────────────────────────

if (firstArg === 'template' && secondArg === 'vars') {
  const varsArgs = userArgs.slice(2);
  const positional = varsArgs.filter(a => !a.startsWith('-'));
  const templateId = positional[0];
  const verNo      = positional[1];
  const withStatement = varsArgs.includes('--with-statement');

  if (!templateId || !verNo) {
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'args',
      message: 'Usage: node sql-shim.js template vars <templateId> <verNo> [--with-statement]',
    }) + '\n', 1);
    return;
  }

  const env = buildChildEnv();

  // 登录检查：使用 --status 非阻塞检测，未登录时立即以非零退出，不打开浏览器
  const loginResult = compat.spawnBin(real, ['login', '--status'], {
    env, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', timeout: 15_000,
  });
  if ((loginResult.status ?? 1) !== 0) {
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'login',
      message: '未登录，请先执行 sql login 完成认证后重试',
    }) + '\n', loginResult.status ?? 1);
    return;
  }

  // Step 1：template get --save <tmpSql>（pipe stdout/stderr 避免污染调用方的 stdout）
  const tmpSql = path.join(os.tmpdir(), `sql-shim-stmt-${templateId}-${Date.now()}.sql`);
  const getResult = compat.spawnBin(real, ['template', 'get', templateId, verNo, '--save', tmpSql], {
    env, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', timeout: 30_000,
  });
  if ((getResult.status ?? 1) !== 0 || !fs.existsSync(tmpSql)) {
    try { fs.unlinkSync(tmpSql); } catch (_) {}
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'get',
      message: `template get 失败（exit ${getResult.status}）：` + (getResult.stderr || '').trim(),
    }) + '\n', 1);
    return;
  }
  const statement = fs.readFileSync(tmpSql, 'utf8');
  try { fs.unlinkSync(tmpSql); } catch (_) {}

  // Step 2：query vars --file <json>
  const tmpVarsJson = path.join(os.tmpdir(), `sql-shim-vars-${templateId}-${Date.now()}.json`);
  fs.writeFileSync(tmpVarsJson, JSON.stringify({ statement }), 'utf8');
  const varsResult = compat.spawnBin(real, ['query', 'vars', '--file', tmpVarsJson, '-o', 'json'], {
    env, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', timeout: 30_000,
  });
  try { fs.unlinkSync(tmpVarsJson); } catch (_) {}

  let parsedVars = [];
  let varsError = null;
  if ((varsResult.status ?? 1) === 0) {
    const obj = parseLastJson((varsResult.stdout || '').trim());
    // 精简字段：只保留 LLM 决策所需的最小集合，去掉 clientId 等噪音
    parsedVars = ((obj && obj.data) || []).map(v => {
      const item = { name: v.name, inputType: v.inputType };
      if (v.dateFormat)    item.dateFormat    = v.dateFormat;
      if (v.defaultValue != null) item.defaultValue = v.defaultValue;
      return item;
    });
  } else {
    varsError = ((varsResult.stderr || '') + (varsResult.stdout || '')).trim() || 'query vars 失败';
  }

  stdoutWriteAndExit(JSON.stringify({
    status: 'ok',
    vars:   parsedVars,
    ...(varsError      ? { varsError }           : {}),
    ...(withStatement  ? { statement }            : {}),
  }) + '\n', 0, { id: 'sql_template.vars', name: '模板变量解析完成' });
  return;
}

// ── 内置子命令：template resolve ─────────────────────────────────────────────

if (firstArg === 'template' && secondArg === 'resolve') {
  // 解析 template resolve 专属参数
  const resolveArgs = userArgs.slice(2); // 去掉 'template' 'resolve'

  // 位置参数：templateId verNo
  const positional = resolveArgs.filter(a => !a.startsWith('-'));
  const templateId = positional[0];
  const verNo      = positional[1];

  if (!templateId || !verNo) {
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'args',
      message: 'Usage: node sql-shim.js template resolve <templateId> <verNo> [--var k=v]... [--out <file>]',
    }) + '\n', 1);
    return;
  }

  // 收集 --var k=v 参数（可多次）
  const vars = [];
  for (let i = 0; i < resolveArgs.length; i++) {
    if (resolveArgs[i] === '--var' && resolveArgs[i + 1]) {
      vars.push(resolveArgs[i + 1]);
      i++;
    }
  }

  // --work-dir 工作目录（LLM 推理后传入，输出路径为 <work_dir>/bi-query-sql/sql/<ts>_<rand>.sql）
  // --out 可直接指定输出路径（优先级高于 --work-dir）
  const outIdx = resolveArgs.indexOf('--out');
  const workDirIdx = resolveArgs.indexOf('--work-dir');
  const _workDirVal = workDirIdx !== -1 ? resolveArgs[workDirIdx + 1] : null;
  const workDir = (_workDirVal && !_workDirVal.startsWith('-')) ? _workDirVal : null;
  const _outVal = outIdx !== -1 ? resolveArgs[outIdx + 1] : null;
  const outputPath = (_outVal && !_outVal.startsWith('-'))
    ? _outVal
    : workDir
      ? path.join(workDir, 'bi-query-sql', 'sql', `${Date.now()}_${Math.floor(Math.random() * 10000)}.sql`)
      : null;

  if (!outputPath) {
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'args',
      message: '缺少输出路径：请通过 --work-dir <path> 或 --out <file> 指定',
    }) + '\n', 1);
    return;
  }

  // 临时文件列表，退出前清理
  const tmpFiles = [];
  function cleanup() {
    for (const f of tmpFiles) {
      try { fs.unlinkSync(f); } catch (_) {}
    }
  }

  const env = buildChildEnv();

  // 登录检查：使用 --status 非阻塞检测，未登录时立即以非零退出，不打开浏览器
  const loginResult = compat.spawnBin(real, ['login', '--status'], {
    env, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', timeout: 15_000,
  });
  if ((loginResult.status ?? 1) !== 0) {
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'login',
      message: '未登录，请先执行 sql login 完成认证后重试',
    }) + '\n', loginResult.status ?? 1);
    return;
  }

  // 辅助：调用真实 sql bin（全部 pipe，避免子命令的 stdout 污染调用方期望的单行 JSON 输出）
  function runSql(args) {
    return compat.spawnBin(real, args, {
      env,
      stdio:    ['ignore', 'pipe', 'pipe'],
      encoding: 'utf8',
      timeout:  30_000,
    });
  }

  // Step 1：template get --save <tmpSql>
  const tmpSql = path.join(os.tmpdir(), `sql-shim-stmt-${templateId}-${Date.now()}.sql`);
  tmpFiles.push(tmpSql);
  const getResult = runSql(['template', 'get', templateId, verNo, '--save', tmpSql]);
  if ((getResult.status ?? 1) !== 0 || !fs.existsSync(tmpSql)) {
    cleanup();
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'get',
      message: `template get 失败（exit ${getResult.status}）：` + (getResult.stderr || '').trim(),
    }) + '\n', 1);
    return;
  }
  const statement = fs.readFileSync(tmpSql, 'utf8');

  // Step 2：query vars --file <json>（vars 失败不阻断，resolve 时系统变量会被自动展开）
  const tmpVarsJson = path.join(os.tmpdir(), `sql-shim-vars-${templateId}-${Date.now()}.json`);
  tmpFiles.push(tmpVarsJson);
  fs.writeFileSync(tmpVarsJson, JSON.stringify({ statement }), 'utf8');
  const varsResult = runSql(['query', 'vars', '--file', tmpVarsJson, '-o', 'json']);
  let parsedVars = [];
  if ((varsResult.status ?? 1) === 0) {
    const obj = parseLastJson((varsResult.stdout || '').trim());
    // 精简字段：与 template vars 保持一致，只保留 LLM 决策所需的最小集合
    parsedVars = ((obj && obj.data) || []).map(v => {
      const item = { name: v.name, inputType: v.inputType };
      if (v.dateFormat)           item.dateFormat   = v.dateFormat;
      if (v.defaultValue != null) item.defaultValue = v.defaultValue;
      return item;
    });
  }

  // Step 3：query resolve --file <json> [--var k=v]...
  const tmpResolveJson = path.join(os.tmpdir(), `sql-shim-resolve-${templateId}-${Date.now()}.json`);
  tmpFiles.push(tmpResolveJson);
  fs.writeFileSync(tmpResolveJson, JSON.stringify({ statement }), 'utf8');
  const resolveCliArgs = ['query', 'resolve', '--file', tmpResolveJson];
  for (const v of vars) resolveCliArgs.push('--var', v);
  const resolveResult = runSql(resolveCliArgs);
  if ((resolveResult.status ?? 1) !== 0) {
    cleanup();
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'resolve',
      message: `query resolve 失败（exit ${resolveResult.status}）：` + ((resolveResult.stderr || '') + (resolveResult.stdout || '')).trim(),
    }) + '\n', 1);
    return;
  }

  // resolve 输出为纯文本 SQL（非 JSON）
  const resolvedSql = (resolveResult.stdout || '').trim();
  if (!resolvedSql) {
    cleanup();
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'resolve',
      message: 'query resolve 输出为空',
    }) + '\n', 1);
    return;
  }

  // Step 4：写出最终 SQL 文件
  try {
    fs.mkdirSync(path.dirname(path.resolve(outputPath)), { recursive: true });
    fs.writeFileSync(outputPath, resolvedSql, 'utf8');
  } catch (e) {
    cleanup();
    stdoutWriteAndExit(JSON.stringify({
      status: 'error', step: 'write',
      message: `写入输出文件失败：${e.message}`,
    }) + '\n', 1);
    return;
  }

  cleanup();
  stdoutWriteAndExit(JSON.stringify({
    status:     'ok',
    vars:       parsedVars,
    outputPath: path.resolve(outputPath),
  }) + '\n', 0, { id: 'sql_template.resolve', name: '模板 SQL 渲染完成' });
  return;
}

if (firstArg !== 'login') {
  // 执行 sql login 检查登录状态：
  //   - 已登录：直接输出成功信息并以 0 退出
  //   - 未登录：触发浏览器 SSO 流程（CatDesk 环境下 open 已被 preload patch 替换）
  // 必须使用 childEnv（含 NODE_OPTIONS preload），确保 CatDesk 环境下 open 正常工作
  const loginResult = compat.spawnBin(real, ['login'], { env: childEnv });
  if ((loginResult.status ?? 1) !== 0) {
    process.stderr.write('[sql-shim] 登录失败，请手动执行 sql login 后重试。\
');
    process.exit(loginResult.status ?? 1);
  }
}

// ── 启动 ──────────────────────────────────────────────────────────────────────
// 调用真实 bin（自动处理 Windows .cmd 的 EINVAL 问题）

const result = compat.spawnBin(real, userArgs, { env: childEnv });

// Windows 上 spawnSync + stdio:'inherit' 时 status 可能为 null（正常退出），视为 0
const exitCode = result.status ?? 0;
if (exitCode === 0) {
  if (firstArg === 'template' && secondArg === 'search') {
    step('sql_template.search', '模板搜索完成').finally(() => process.exit(exitCode));
    return;
  }
  if (firstArg === 'template' && secondArg === 'get') {
    step('sql_template.get', '模板详情获取完成').finally(() => process.exit(exitCode));
    return;
  }
}
process.exit(exitCode);
