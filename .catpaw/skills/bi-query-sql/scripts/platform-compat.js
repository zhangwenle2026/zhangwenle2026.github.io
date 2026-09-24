#!/usr/bin/env node
/**
 * platform-compat.js — 跨平台兼容公共层（Windows / macOS / Linux + CatDesk CLI）
 *
 * 封装所有平台差异，对外暴露统一 API，供以下脚本复用：
 *   - mt-mcp-client.js       → resolveCatdesk / openWithCatdesk / getNpmCmd / getNpxCmd /
 *                               ensureGlobalLibrary / resolveGlobalLibraryPath
 *   - mcp-client-shim.js     → resolveCatdesk / writePreloadAndGetNodeOption /
 *                               resolveGlobalLibraryPath
 *   - sql-shim.js            → resolveCatdesk / writePreloadAndGetNodeOption /
 *                               ensureGlobalCli
 *   - dsx-shim.js            → resolveCatdesk / writePreloadAndGetNodeOption /
 *                               ensureGlobalCli
 *
 * 设计原则：
 *   - 纯 CJS（'use strict'），零外部依赖，Node.js >= 18 兼容
 *   - 不产生任何副作用，所有函数按需调用
 *   - 每个函数职责单一，可独立测试
 *
 * 环境检测 API（统一入口，勿在各脚本中重复实现）：
 *   isCatDesk()  — 是否在 CatDesk（Electron GUI）环境
 *   isCatClaw()  — 是否在 CatClaw（Kubernetes 沙箱）环境
 *   IS_WIN / IS_MAC / IS_LINUX — 操作系统平台常量
 */

'use strict';

const { execFileSync, spawnSync } = require('child_process');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');
const os = require('os');

/** 内网 npm registry 默认地址（以防调用方未传入时使用） */
const DEFAULT_NPM_REGISTRY = 'http://r.npm.sankuai.com';

// ── 平台常量 ──────────────────────────────────────────────────────────────────

const IS_WIN   = process.platform === 'win32';
const IS_MAC   = process.platform === 'darwin';
const IS_LINUX = process.platform === 'linux';

// ── 运行环境检测 ──────────────────────────────────────────────────────────────

/**
 * 判断当前是否运行在 CatDesk（Electron GUI）环境中。
 *
 * 判断依据：CATPAW_CONFIG_CONTENT 中的 "source" 字段值为 "CatPawDesk"。
 *
 * ⚠️  不能用 !!CATPAW_CLIENT_TYPE 判断：
 *      CatPawCLI 环境下该变量也非空（值为 "CatPawCLI"），会导致误判。
 *
 * 兼容策略（按优先级）：
 *   1. CATPAW_CONFIG_CONTENT 存在 → 解析 JSON 检查 source 字段
 *   2. CATPAW_CONFIG_CONTENT 不存在（旧版本）→ fallback 到 CATPAW_CLIENT_TYPE === 'CatDesk'
 *
 * @returns {boolean}
 */
function isCatDesk() {
  const cfg = process.env.CATPAW_CONFIG_CONTENT || '';
  if (cfg) {
    try {
      return JSON.parse(cfg).source === 'CatPawDesk';
    } catch (_) {
      // JSON 解析失败，fallback 到正则匹配
      return /"source"\s*:\s*"CatPawDesk"/.test(cfg);
    }
  }
  // 兼容旧版本：CATPAW_CONFIG_CONTENT 不存在时用 CATPAW_CLIENT_TYPE
  return process.env.CATPAW_CLIENT_TYPE === 'CatDesk';
}

/**
 * 判断当前是否运行在 CatClaw（Kubernetes 沙箱）环境中。
 *
 * 判断依据：CATCLAW_ENV 非空（如 "prod"）或 CATCLAW_PROFILE 非空（如 "personal"）。
 *
 * @returns {boolean}
 */
function isCatClaw() {
  return !!(process.env.CATCLAW_ENV || process.env.CATCLAW_PROFILE);
}

// ── catdesk 可执行文件解析 ────────────────────────────────────────────────────

/**
 * 解析 catdesk 可执行文件路径。
 *
 * Windows 上 ~/.catpaw/bin/catdesk 实为 catdesk.cmd，
 * execFileSync 不能直接执行 .cmd，需要通过 cmd.exe /c 中转。
 * 本函数返回 { bin, isCmd } 供调用方按需选择调用方式。
 *
 * 优先级：环境变量 CATDESK_BIN > catdesk.cmd（Windows）> catdesk
 *
 * @returns {{ bin: string, isCmd: boolean }}
 */
function resolveCatdesk() {
  if (process.env.CATDESK_BIN) {
    const bin = process.env.CATDESK_BIN;
    return { bin, isCmd: IS_WIN && bin.toLowerCase().endsWith('.cmd') };
  }
  const base = path.join(os.homedir(), '.catpaw', 'bin', 'catdesk');
  if (IS_WIN) {
    const cmdPath = base + '.cmd';
    if (fs.existsSync(cmdPath)) return { bin: cmdPath, isCmd: true };
  }
  return { bin: base, isCmd: false };
}

// ── catdesk browser-action ────────────────────────────────────────────────────

/**
 * 通过 catdesk browser-action 在 CatDesk 内置浏览器中打开 URL。
 *
 * Windows 上若目标是 .cmd 文件，自动通过 cmd.exe /c 中转调用。
 * 调用失败时静默降级（打印提示，不抛出异常）。
 *
 * @param {string} url          要打开的 URL
 * @param {{ bin: string, isCmd: boolean }} [catdesk]  可选，默认调用 resolveCatdesk()
 * @param {{ log?: (msg: string) => void, timeout?: number }} [opts]
 * @returns {boolean} 是否调用成功
 */
function openWithCatdesk(url, catdesk, opts) {
  catdesk = catdesk || resolveCatdesk();
  const log = (opts && opts.log) || (() => {});
  const timeout = (opts && opts.timeout) || 10_000;

  const actionArg = JSON.stringify({ action: 'navigate', url: String(url) });
  const args = ['browser-action', actionArg];

  try {
    if (IS_WIN && catdesk.isCmd) {
      // Windows 上 execFileSync 不能直接执行 .cmd 批处理文件，必须借助 cmd.exe /c
      execFileSync('cmd.exe', ['/c', catdesk.bin, ...args], {
        stdio: ['ignore', 'ignore', 'pipe'],
        timeout,
      });
    } else {
      execFileSync(catdesk.bin, args, {
        stdio: ['ignore', 'ignore', 'pipe'],
        timeout,
      });
    }
    log('已在 CatDesk 内置浏览器中打开 SSO 登录页面');
    return true;
  } catch (e) {
    log('catdesk browser-action 失败，请手动访问：' + url);
    log('错误：' + e.message);
    return false;
  }
}

// ── npm / npx 工具名 ──────────────────────────────────────────────────────────

/**
 * 返回当前平台的 npm 可执行文件名。
 * Windows 上需使用 npm.cmd，否则 execFileSync / spawnSync 会报 ENOENT。
 *
 * @returns {string}  'npm.cmd' | 'npm'
 */
function getNpmCmd() {
  return IS_WIN ? 'npm.cmd' : 'npm';
}

/**
 * 返回当前平台的 npx 可执行文件名。
 *
 * @returns {string}  'npx.cmd' | 'npx'
 */
function getNpxCmd() {
  return IS_WIN ? 'npx.cmd' : 'npx';
}

// ── semver 工具（支持 major.minor.patch[-prerelease]，零外部依赖）──────────────

/**
 * 将版本字符串解析为 { nums: [major, minor, patch], pre: string } 对象。
 *
 * 规则（遵循 semver 规范）：
 *   - 从字符串中提取第一个 major.minor.patch 数字段
 *   - patch 后紧跟 '-' 开头的内容视为 pre-release 标识（如 'beta-2'、'rc.1'）
 *   - 有 pre-release 的版本在数值段相等时小于正式版（如 0.0.9-beta-2 < 0.0.9）
 *
 * 示例：
 *   '0.1.1'        → { nums: [0,1,1], pre: '' }
 *   '0.0.9-beta-2' → { nums: [0,0,9], pre: 'beta-2' }
 *   '1.2.3-rc.1'   → { nums: [1,2,3], pre: 'rc.1' }
 *
 * @param {string} v
 * @returns {{ nums: [number, number, number], pre: string } | null}
 */
function parseVer(v) {
  const m = String(v || '').match(/(\d+)\.(\d+)\.(\d+)(-[^\s+]+)?/);
  if (!m) return null;
  return {
    nums: [+m[1], +m[2], +m[3]],
    pre: m[4] ? m[4].slice(1) : '',   // 去掉前导 '-'
  };
}

/**
 * 返回 v >= min 时为 true，任一参数解析失败返回 false。
 *
 * 比较规则：
 *   1. 先按 [major, minor, patch] 数值比较
 *   2. 数值段相等时，有 pre-release 的版本 < 无 pre-release 的版本（遵循 semver）
 *      例：0.0.9-beta-2 < 0.0.9，0.1.1-rc.1 < 0.1.1
 *   3. 两者均有 pre-release 时按字典序比较（0.0.9-beta < 0.0.9-rc）
 *
 * @param {string} v
 * @param {string} min
 * @returns {boolean}
 */
function versionGte(v, min) {
  const a = parseVer(v), b = parseVer(min);
  if (!a || !b) return false;
  for (let i = 0; i < 3; i++) {
    if (a.nums[i] !== b.nums[i]) return a.nums[i] > b.nums[i];
  }
  // 数值段相等，比较 pre-release
  if (a.pre === b.pre) return true;        // 完全相等
  if (a.pre && !b.pre) return false;       // a 是 pre-release，b 是正式版：a < b
  if (!a.pre && b.pre) return true;        // a 是正式版，b 是 pre-release：a > b
  return a.pre >= b.pre;                   // 两者都有 pre-release，字典序比较
}

// ── 全局包依赖管理 ────────────────────────────────────────────────────────────

// 将包名转换为合法文件名（替换 / @ 为 -）
function pkgToSlug(pkg) {
  return pkg.replace(/@/g, '').replace(/\//g, '-').replace(/[^a-zA-Z0-9._-]/g, '-');
}

/**
 * 调用 npm root -g 获取全局 node_modules 根目录。
 *
 * Windows 上 npm.cmd 是批处理文件，spawnSync 直接调用在部分环境下会 ENOENT，
 * 需要通过 cmd.exe /c 中转（与 openWithCatdesk 的处理方式一致）。
 *
 * @returns {string}
 */
function getNpmGlobalRoot() {
  let result;
  if (IS_WIN) {
    // Windows 上 npm.cmd 是批处理，必须通过 cmd.exe /c 执行
    result = spawnSync('cmd.exe', ['/c', getNpmCmd(), 'root', '-g'], {
      encoding: 'utf-8',
      timeout: 10_000,
    });
  } else {
    result = spawnSync(getNpmCmd(), ['root', '-g'], {
      encoding: 'utf-8',
      timeout: 10_000,
    });
  }
  if (result.error) throw new Error('npm root -g 执行失败：' + result.error.message);
  const globalRoot = (result.stdout || '').trim();
  if (!globalRoot) throw new Error('npm root -g 返回空结果');
  return globalRoot;
}

/**
 * 确保指定纯库包（无 CLI bin）已全局安装，未安装则自动执行 npm install -g。
 *
 * 缓存策略（两层）：
 *   1. flagFile（os.tmpdir()/mt-mcp-pkg-installed-<slug>）存在且包目录存在 → 完全跳过子进程
 *   2. 包目录存在但 flagFile 缺失 → 补写 flagFile，跳过安装
 *   3. 以上均不满足 → 执行 npm root -g + npm install -g
 *
 * @param {string} packageName    require 时的包名（如 "@modelcontextprotocol/sdk"）
 * @param {string} [installName]  安装时的包名（含版本，如 "@modelcontextprotocol/sdk@latest"），
 *                                省略时自动追加 @latest
 * @param {string} [registry]     npm registry，默认 http://r.npm.sankuai.com
 * @returns {string} 全局 node_modules 根目录（npm root -g 输出）
 */
function ensureGlobalLibrary(packageName, installName, registry) {
  registry = registry || DEFAULT_NPM_REGISTRY;
  const flagFile = path.join(os.tmpdir(), 'mt-mcp-pkg-installed-' + pkgToSlug(packageName));
  const rootCacheFile = path.join(os.tmpdir(), 'mt-mcp-npm-global-root');

  // ── 快速路径：flagFile + 缓存的 globalRoot 均存在，完全不调用子进程 ────────
  if (fs.existsSync(flagFile)) {
    let cachedRoot = '';
    try { cachedRoot = fs.readFileSync(rootCacheFile, 'utf-8').trim(); } catch (_) {}
    if (cachedRoot) {
      const pkgDir = path.join(cachedRoot, packageName);
      if (fs.existsSync(pkgDir)) return cachedRoot;
      // 缓存的 globalRoot 已失效（npm 路径变化），降级走完整路径
    }
  }

  // ── 查询全局 npm root ─────────────────────────────────────────────────────
  const globalRoot = getNpmGlobalRoot();
  // 持久化 globalRoot 缓存
  try { fs.writeFileSync(rootCacheFile, globalRoot); } catch (_) {}

  const pkgDir = path.join(globalRoot, packageName);

  // 标记文件存在且包目录也存在，直接返回
  if (fs.existsSync(flagFile) && fs.existsSync(pkgDir)) {
    return globalRoot;
  }

  // 已安装但标记文件被清理
  if (fs.existsSync(pkgDir)) {
    try { fs.writeFileSync(flagFile, String(Date.now())); } catch (_) {}
    return globalRoot;
  }

  // 尚未安装，执行 npm install -g
  const target = installName || (packageName + '@latest');
  process.stderr.write('[platform-compat] 正在自动安装 ' + target + ' ...\n');
  let install;
  if (IS_WIN) {
    // Windows 上 npm.cmd 批处理必须通过 cmd.exe /c 执行
    install = spawnSync(
      'cmd.exe',
      ['/c', getNpmCmd(), 'install', '-g', target, '--registry', registry],
      { encoding: 'utf-8', timeout: 120_000 }
    );
  } else {
    install = spawnSync(
      getNpmCmd(),
      ['install', '-g', target, '--registry', registry],
      { encoding: 'utf-8', timeout: 120_000 }
    );
  }
  if (install.error) throw new Error('npm install 执行失败：' + install.error.message);
  if (install.status !== 0) {
    const errMsg = (install.stderr || install.stdout || '').trim();
    throw new Error(target + ' 自动安装失败：' + errMsg);
  }

  try { fs.writeFileSync(flagFile, String(Date.now())); } catch (_) {}
  return globalRoot;
}

/**
 * 解析全局安装库包的目录绝对路径，未安装时自动安装。
 *
 * @param {string} packageName   包名（如 "@modelcontextprotocol/sdk"）
 * @param {string} [installName] 安装时的包名（含版本标签）
 * @param {string} [registry]    npm registry，默认 http://r.npm.sankuai.com
 * @returns {string}             包目录绝对路径（globalRoot/packageName）
 */
function resolveGlobalLibraryPath(packageName, installName, registry) {
  const globalRoot = ensureGlobalLibrary(packageName, installName, registry);
  return path.join(globalRoot, packageName);
}

/**
 * 确保有 CLI 入口的全局工具包已安装且满足最低版本要求。
 * 未安装或版本过低时，自动执行 npm install -g 一次，安装后重新验证。
 * 验证仍失败则打印错误并以 exit code 1 退出。
 *
 * 版本号来源：bin 所在包的 package.json（无额外子进程开销）。
 *
 * 使用场景：dsx-shim.js 对 @datafe/dsx-cli 的版本门控，
 *           未来其他有最低版本需求的 CLI 包可复用此方法。
 *
 * @param {object} opts
 * @param {string}   opts.binName       CLI 可执行文件名，如 'dsx'
 * @param {string}   opts.packageName   npm 包名，如 '@datafe/dsx-cli'
 * @param {string}   opts.minVersion    最低版本要求，如 '0.2.9'
 * @param {string}   [opts.registry]    npm registry，默认 http://r.npm.sankuai.com
 * @param {string[]} [opts.skipDirs]    在 PATH 中跳过的目录（避免递归），绝对路径数组
 * @param {string}   [opts.logPrefix]   日志前缀，默认 '[platform-compat]'
 *
 * @returns {{ binPath: string, pkgDir: string, version: string }}
 *          安装/验证成功后返回 bin 路径、包目录和实际版本
 */
function ensureGlobalCli(opts) {
  const {
    binName,
    packageName,
    minVersion,
    registry = DEFAULT_NPM_REGISTRY,
    skipDirs = [],
    logPrefix = '[platform-compat]',
  } = opts;

  const SEP = IS_WIN ? ';' : ':';
  const exts = IS_WIN ? ['.cmd', '.exe', ''] : [''];
  const skipResolved = skipDirs.map(d => path.resolve(d));

  // ── 在 PATH 中查找 bin（跳过 skipDirs）────────────────────────────────────
  function findBin() {
    const dirs = (process.env.PATH || '').split(SEP);
    for (const dir of dirs) {
      if (skipResolved.includes(path.resolve(dir))) continue;
      for (const ext of exts) {
        const bin = path.join(dir, binName + ext);
        try { fs.accessSync(bin, fs.constants.X_OK); return bin; } catch (_) {}
      }
    }
    return null;
  }

  // ── 从 bin 向上找包目录（含 package.json 且 name === packageName）─────────
  // 同时检查每一层的 node_modules/<scope>/<name> 子目录，
  // 处理 bin 与 node_modules 同级（如独立 Node 发行版的全局 bin 目录）的情况。
  function findPkgDir(binPath) {
    try {
      let dir = path.dirname(fs.realpathSync(binPath));
      for (let i = 0; i < 8; i++) {
        // 1. 当前目录本身是否就是包目录
        const pkgFile = path.join(dir, 'package.json');
        if (fs.existsSync(pkgFile)) {
          try {
            if (JSON.parse(fs.readFileSync(pkgFile, 'utf-8')).name === packageName) return dir;
          } catch (_) {}
        }
        // 2. 当前目录下的 node_modules/<packageName> 是否是包目录
        //    （bin 和 node_modules 在同级目录，如独立 Node 发行版）
        const nmPkgDir = path.join(dir, 'node_modules', packageName);
        const nmPkgFile = path.join(nmPkgDir, 'package.json');
        if (fs.existsSync(nmPkgFile)) {
          try {
            if (JSON.parse(fs.readFileSync(nmPkgFile, 'utf-8')).name === packageName) return nmPkgDir;
          } catch (_) {}
        }
        const parent = path.dirname(dir);
        if (parent === dir) break;
        dir = parent;
      }
    } catch (_) {}
    return null;
  }

  // ── 从包目录读版本号 ────────────────────────────────────────────────────────
  function readVersion(pkgDir) {
    try {
      return JSON.parse(fs.readFileSync(path.join(pkgDir, 'package.json'), 'utf-8')).version || '';
    } catch (_) { return ''; }
  }

  // ── 执行安装/升级 ───────────────────────────────────────────────────────────
  function runInstall(reason) {
    process.stderr.write(`${logPrefix} ${reason}，正在自动安装/升级 ${packageName}...\n`);
    let ret;
    if (IS_WIN) {
      ret = spawnSync('cmd.exe', ['/c', getNpmCmd(), 'install', '-g', packageName,
        '--registry', registry], { stdio: 'inherit', shell: false, timeout: 120_000 });
    } else {
      ret = spawnSync(getNpmCmd(), ['install', '-g', packageName,
        '--registry', registry], { stdio: 'inherit', shell: false, timeout: 120_000 });
    }
    if ((ret.status !== 0) || ret.error) {
      process.stderr.write(
        `${logPrefix} ERROR: 自动安装失败，请手动执行：\n` +
        `  npm install -g ${packageName} --registry=${registry}\n`
      );
      process.exit(1);
    }
    // 安装后重新定位
    const newBin = findBin();
    if (!newBin) {
      process.stderr.write(
        `${logPrefix} ERROR: 安装后仍找不到 ${binName}，` +
        `请检查 npm 全局 bin 目录是否在 PATH 中。\n`
      );
      process.exit(1);
    }
    const newPkgDir = findPkgDir(newBin);
    const newVer = newPkgDir ? readVersion(newPkgDir) : '';
    if (!newVer || !versionGte(newVer, minVersion)) {
      process.stderr.write(
        `${logPrefix} ERROR: 安装后版本仍不满足要求` +
        `（${newVer || '未知'}，要求 >= ${minVersion}）\n` +
        `  npm install -g ${packageName} --registry=${registry}\n`
      );
      process.exit(1);
    }
    process.stderr.write(`${logPrefix} 安装成功（${newVer}），继续执行。\n`);
    return { binPath: newBin, pkgDir: newPkgDir, version: newVer };
  }

  // ── 主流程 ─────────────────────────────────────────────────────────────────
  const binPath = findBin();
  if (!binPath) {
    return runInstall(`${binName} 未安装`);
  }
  const pkgDir = findPkgDir(binPath);
  const ver = pkgDir ? readVersion(pkgDir) : '';
  if (ver && !versionGte(ver, minVersion)) {
    return runInstall(`${binName} 版本过低（当前 ${ver}，要求 >= ${minVersion}）`);
  }
  return { binPath, pkgDir, version: ver };
}

// ── ESM preload 生成（供 sql-shim / dsx-shim 使用）──────────────────────────

/**
 * 生成 ESM preload 脚本内容（.mjs），用于 patch `open` 模块，
 * 将 open(url) 替换为 catdesk browser-action（失败时降级到系统浏览器）。
 *
 * 生成的脚本在运行时（dsx-cli / sql-cli / mt-mcp-client 的子进程里）执行，
 * 通过 NODE_OPTIONS --import 注入。
 *
 * 支持两种 open 版本：
 *   - open@8 及以下（CJS）：通过 require.cache 覆盖，直接替换 exports
 *   - open@10+（纯 ESM）：require.cache 无法拦截，改为向 require.cache 注入一个
 *     CJS 兼容的包装函数，同时用顶层 import 获取原始 ESM open 作为 fallback
 *
 * @param {string}  openModulePath   open 模块的绝对路径（index.js）
 * @param {string}  catdeskBin       catdesk 可执行文件的绝对路径
 * @param {string}  [prefix]         日志前缀，如 '[sql-shim]' / '[dsx-shim]'
 * @param {boolean} [openIsEsm]      open 是否为纯 ESM（open@10+），默认 false
 * @returns {string}                 preload .mjs 文件内容
 */
function buildOpenPatchContent(openModulePath, catdeskBin, prefix, openIsEsm) {
  prefix = prefix || '[shim]';
  openIsEsm = !!openIsEsm;
  // 注意：这段字符串会被写入 .mjs 文件后在子进程里执行
  // catdeskBin 已由父进程解析好（含 .cmd 后缀），此处直接嵌入

  // open@10+（ESM）时：顶层 import 取得原始 open 函数作为 fallback
  const esmImportBlock = openIsEsm
    ? `import origOpenModule from ${JSON.stringify(openModulePath)};\nconst _origOpenFn = origOpenModule.default || origOpenModule;\n`
    : '';

  return `
import { createRequire } from 'module';
import { execFileSync } from 'child_process';
${esmImportBlock}
const require = createRequire(import.meta.url);
const openModulePath = ${JSON.stringify(openModulePath)};
const catdeskBin = ${JSON.stringify(catdeskBin)};
const prefix = ${JSON.stringify(prefix)};
const openIsEsm = ${JSON.stringify(openIsEsm)};

function openWithCatdesk(url) {
  const isWin = process.platform === 'win32';
  const isCmd = isWin && catdeskBin.toLowerCase().endsWith('.cmd');
  const actionArg = JSON.stringify({ action: 'navigate', url: String(url) });
  const args = ['browser-action', actionArg];
  try {
    if (isWin && isCmd) {
      execFileSync('cmd.exe', ['/c', catdeskBin, ...args], {
        stdio: ['ignore', 'ignore', 'pipe'],
        timeout: 10000,
      });
    } else {
      execFileSync(catdeskBin, args, {
        stdio: ['ignore', 'ignore', 'pipe'],
        timeout: 10000,
      });
    }
    process.stderr.write(prefix + ' 已在 CatDesk 内置浏览器中打开 SSO 登录页面\\n');
    return true;
  } catch (e) {
    // catdesk browser-action 失败（GUI 未运行 / CLI 环境），降级到系统浏览器
    process.stderr.write(prefix + ' catdesk browser-action 失败，降级到系统浏览器：' + e.message.split('\\n')[0] + '\\n');
    return false;
  }
}

// 构建 patchedFn：先尝试 catdesk browser-action，失败则 fallback 到原始 open
function makePatchedOpen(origOpenFn) {
  return function patchedOpen(url) {
    const ok = openWithCatdesk(String(url));
    if (!ok) {
      // catdesk 不可用，fallback 到系统 open
      return origOpenFn(String(url));
    }
    return Promise.resolve({ pid: -1, unref: () => {}, kill: () => {} });
  };
}

if (openIsEsm) {
  // ── open@10+（纯 ESM）────────────────────────────────────────────────────────
  // server.js 里 require("open") 会因为目标是 ESM 而报错：
  //   "require() of ES Module ... not supported"
  // 解决方案：向 require.cache 中注入一个 CJS 兼容的假模块，
  // 让 require("open") 能正常返回我们的 patchedFn（不会触发 ESM 报错）。
  // 原始 open 通过顶层 import 已经加载好了（_origOpenFn），直接作为 fallback。
  try {
    const patchedFn = makePatchedOpen(_origOpenFn);
    const patchedExports = Object.assign(patchedFn, { __esModule: true, default: patchedFn });

    // 构造一个假的 Module 对象注入到 require.cache
    const Module = require('module');
    const fakeModule = new Module(openModulePath);
    fakeModule.exports = patchedExports;
    fakeModule.loaded = true;
    fakeModule.filename = openModulePath;
    require.cache[openModulePath] = fakeModule;

    if (process.env.MT_MCP_DEBUG === '1') {
      process.stderr.write(prefix + ' open patch 已就绪（ESM compat）：SSO 登录将优先通过 CatDesk 内置浏览器，失败时降级到系统浏览器\\n');
    }
  } catch (e) {
    if (process.env.MT_MCP_DEBUG === '1') {
      process.stderr.write(prefix + ' open patch 失败（ESM，' + e.message + '），将使用系统默认浏览器\\n');
    }
  }
} else {
  // ── open@8 及以下（CJS）──────────────────────────────────────────────────────
  try {
    const origOpen = require(openModulePath);
    // 保存原始 open 函数引用，供 catdesk browser-action 失败时 fallback 使用
    // origOpen 本身是函数（open@8 CJS exports），origOpen.default 在 __importDefault 包装后才存在
    const origOpenFn = (typeof origOpen === 'function') ? origOpen : (origOpen.default || origOpen);
    const patchedFn = makePatchedOpen(origOpenFn);
    Object.assign(patchedFn, origOpen);

    // server.js 通过 TypeScript 编译后的 __importDefault 引用 open：
    //   var open_1 = __importDefault(require("open"))
    //   (0, open_1.default)(loginUrl)
    //
    // __importDefault 逻辑：
    //   (mod && mod.__esModule) ? mod : { "default": mod }
    //
    // open@8 是 CJS（无 __esModule），所以 __importDefault 把整个 exports（函数本身）
    // 包装成 { default: <原始函数> }，open_1.default 指向原始函数。
    //
    // 修复方式：让替换后的 exports 携带 __esModule:true + default:patchedFn，
    // 这样 __importDefault 走 "已是 ESM" 分支直接透传，open_1 = exports，
    // open_1.default = patchedFn，patch 生效。
    const patchedExports = Object.assign(patchedFn, {
      __esModule: true,
      default: patchedFn,
    });

    // 先 require 一次确保模块进入 cache，再覆盖 exports
    require(openModulePath);
    const mod = require.cache[require.resolve(openModulePath)];
    if (mod) {
      mod.exports = patchedExports;
      if (process.env.MT_MCP_DEBUG === '1') {
        process.stderr.write(prefix + ' open patch 已就绪：SSO 登录将优先通过 CatDesk 内置浏览器，失败时降级到系统浏览器\\n');
      }
    } else {
      if (process.env.MT_MCP_DEBUG === '1') {
        process.stderr.write(prefix + ' open patch 跳过：open 模块不在 require.cache 中，将使用系统默认浏览器\\n');
      }
    }
  } catch (e) {
    // patch 失败不影响主流程，sso-web-oidc-cli 会继续用原始 open
    if (process.env.MT_MCP_DEBUG === '1') {
      process.stderr.write(prefix + ' open patch 失败（' + e.message + '），将使用系统默认浏览器\\n');
    }
  }
}
`.trimStart();
}

/**
 * 将 preload 脚本写入临时文件，返回可追加到 NODE_OPTIONS 的字符串片段。
 *
 * Windows 上 file:// URL 需要三条斜杠（file:///C:/...），
 * 使用 pathToFileURL 确保平台正确。
 *
 * @param {string}  openModulePath   open 模块的绝对路径
 * @param {string}  catdeskBin       catdesk 可执行文件绝对路径
 * @param {string}  tmpFilePath      preload .mjs 的临时文件绝对路径
 * @param {string}  [prefix]         日志前缀
 * @param {boolean} [openIsEsm]      open 是否为纯 ESM（open@10+），默认 false
 * @returns {string}                 NODE_OPTIONS 片段，如 `--import "file:///C:/..."`
 */
function writePreloadAndGetNodeOption(openModulePath, catdeskBin, tmpFilePath, prefix, openIsEsm) {
  const content = buildOpenPatchContent(openModulePath, catdeskBin, prefix, openIsEsm);
  fs.writeFileSync(tmpFilePath, content, 'utf-8');
  // pathToFileURL 在 Windows 上自动生成 file:///C:/... 格式
  const fileUrl = pathToFileURL(tmpFilePath).href;
  return `--import ${JSON.stringify(fileUrl)}`;
}

// ── 跨平台 bin 启动 ───────────────────────────────────────────────────────────

/**
 * 跨平台启动一个可执行文件（同步）。
 *
 * 解决 Windows 特有问题：`.cmd` 批处理文件不是 PE 可执行文件，
 * 直接 `spawnSync(bin, args, { shell: false })` 会报 `EINVAL`。
 * Windows 上若 bin 以 `.cmd` 结尾，自动改为 `cmd.exe /c <bin> <args>`。
 *
 * @param {string}   bin     可执行文件绝对路径（如 ensureGlobalPackageVersion 返回的 binPath）
 * @param {string[]} args    命令行参数
 * @param {object}   [opts]  spawnSync 选项（stdio / env / timeout 等），默认 stdio:'inherit'
 * @returns {import('child_process').SpawnSyncReturns<Buffer>}
 */
function spawnBin(bin, args, opts) {
  opts = Object.assign({ stdio: 'inherit', shell: false }, opts);
  if (IS_WIN && bin.toLowerCase().endsWith('.cmd')) {
    return spawnSync('cmd.exe', ['/c', bin, ...args], opts);
  }
  return spawnSync(bin, args, opts);
}

// ── 导出 ──────────────────────────────────────────────────────────────────────

module.exports = {
  IS_WIN,
  IS_MAC,
  IS_LINUX,
  isCatDesk,
  isCatClaw,
  resolveCatdesk,
  openWithCatdesk,
  getNpmCmd,
  getNpxCmd,
  parseVer,
  versionGte,
  ensureGlobalLibrary,
  resolveGlobalLibraryPath,
  ensureGlobalCli,
  buildOpenPatchContent,
  writePreloadAndGetNodeOption,
  spawnBin,
};