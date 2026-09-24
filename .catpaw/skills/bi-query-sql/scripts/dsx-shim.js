#!/usr/bin/env node
/**
 * dsx-shim.js — CatDesk 环境下的 dsx-cli 包装器
 *
 * 用法：node <skill_dir>/scripts/dsx-shim.js <args...>
 *
 * 【CatDesk 环境】
 *   dsx login 的 fallback 路径会通过 @mtfe/sso-web-oidc-cli 调用 open(url) 打开浏览器。
 *   本 shim 在 CatDesk 环境下做三件事：
 *     1. 把 scripts/ 注入到子进程 PATH 最前面（确保版本检查时的路径跳过逻辑正确）
 *     2. 通过 NODE_OPTIONS --import 注入 ESM preload，patch dsx-cli 内置的 open 模块，
 *        将 open(url) 替换为 catdesk browser-action（CatDesk 内置浏览器）
 *     3. 在执行命令前自动检查登录状态（dsx login --check），未登录则先执行 dsx login
 *
 *   dsx-cli 是 ESM 包（"type":"module"），因此 --require 无效，必须用 --import。
 *   open 模块位于 @datafe/dsx-cli/node_modules/@mtfe/sso-web-oidc-cli/node_modules/open，
 *   是 CJS 模块（module.exports），通过 createRequire 在 preload 里完成 patch。
 *
 * 【版本检查】
 *   委托给 platform-compat.ensureGlobalCli：
 *   未安装或版本低于 MIN_DSX_VERSION 时自动 npm install -g，安装后重新验证；
 *   仍不满足则打印错误并以 exit code 1 退出。
 *
 * 【登录检查】
 *   执行任何命令前（login 命令本身除外），先运行 dsx login 检查登录状态。
 *   已登录时 login 会直接输出成功信息并以 0 退出；未登录时会触发浏览器 SSO 流程。
 *   login 检查复用相同的 childEnv（含 NODE_OPTIONS preload patch），
 *   确保 CatDesk 环境下 open 被正确替换为 catdesk browser-action。
 *
 * 【非 CatDesk 环境】直接透传给真正的 dsx，不做任何修改。
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

// 确保 dsx 已安装且版本满足要求；未安装/版本过低时自动安装/升级
const { binPath: real, pkgDir: dsxCliPkg } = compat.ensureGlobalCli({
  ...cliOpts('dsx'),
  registry,
  skipDirs: [SCRIPT_DIR], // 跳过 scripts/ 自身，避免递归调用到本 shim
  logPrefix: '[dsx-shim]',
});

const childEnv = { ...process.env };

if (isCatDesk()) {
  // 1. 把 scripts/ 注入到 PATH 最前面（确保 ensureGlobalCli 的路径跳过正确）
  childEnv.PATH = [
    SCRIPT_DIR,
    ...(process.env.PATH || '').split(SEP).filter(d => path.resolve(d) !== path.resolve(SCRIPT_DIR)),
  ].join(SEP);

  // 2. 通过 NODE_OPTIONS --import 注入 ESM preload，patch open 模块
  //    dsx-cli 是 ESM 包（"type":"module"），--require 对其无效，必须用 --import
  //    open 模块位于 sso-web-oidc-cli 的嵌套 node_modules 下，是 CJS 模块
  if (dsxCliPkg) {
    // sso-web-oidc-cli 使用自己嵌套的 open（@8.4.2），不是 dsx-cli 根目录下的 open
    const openModulePath = path.join(
      dsxCliPkg,
      'node_modules', '@mtfe', 'sso-web-oidc-cli',
      'node_modules', 'open', 'index.js'
    );
    if (fs.existsSync(openModulePath)) {
      const { bin: catdeskBin } = compat.resolveCatdesk();
      const preloadPath = path.join(os.tmpdir(), `dsx-shim-open-patch-${process.pid}.mjs`);
      // compat 统一生成 preload 内容并写文件，返回 --import <url> 片段
      const importOption = compat.writePreloadAndGetNodeOption(
        openModulePath, catdeskBin, preloadPath, '[dsx-shim]'
      );
      const existingNodeOptions = (process.env.NODE_OPTIONS || '').trim();
      childEnv.NODE_OPTIONS = [importOption, existingNodeOptions].filter(Boolean).join(' ');
    }
  }
}

// ── 登录检查 ──────────────────────────────────────────────────────────────────
// 在执行命令前，先检查登录状态；若未登录则先执行 dsx login
// login 命令本身跳过此检查，避免递归/重复

const userArgs = process.argv.slice(2);
const firstArg = userArgs[0];
const secondArg = userArgs[1];

if (firstArg !== 'login') {
  // 执行 dsx login 检查登录状态：
  //   - 已登录：直接输出成功信息并以 0 退出
  //   - 未登录：触发浏览器 SSO 流程（CatDesk 环境下 open 已被 preload patch 替换）
  // 必须使用 childEnv（含 NODE_OPTIONS preload），确保 CatDesk 环境下 open 正常工作
  const loginResult = compat.spawnBin(real, ['login'], { env: childEnv });
  if ((loginResult.status ?? 1) !== 0) {
    process.stderr.write('[dsx-shim] 登录失败，请手动执行 dsx login 后重试。\n');
    process.exit(loginResult.status ?? 1);
  }
}

// ── 启动 ──────────────────────────────────────────────────────────────────────
// 调用真实 bin（自动处理 Windows .cmd 的 EINVAL 问题）

const result = compat.spawnBin(real, userArgs, { env: childEnv });
const exitCode = result.status ?? 0;

// Windows 上 spawnSync + stdio:'inherit' 时 status 可能为 null（正常退出），视为 0
if (exitCode === 0) {
  if (firstArg === 'table' && secondArg === 'search') {
    step('table.search', '表结构搜索完成').finally(() => process.exit(exitCode));
    return;
  }
  if (firstArg === 'table' && secondArg === 'inspect') {
    step('table.inspect', '表结构详情获取完成').finally(() => process.exit(exitCode));
    return;
  }
  if (firstArg === 'project' && secondArg === 'list') {
    step('tenant_projects.list', '项目组权限查询完成').finally(() => process.exit(exitCode));
    return;
  }
}
process.exit(exitCode);
