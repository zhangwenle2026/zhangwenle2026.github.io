#!/usr/bin/env node
/**
 * mcp-client-shim.js — mt-mcp-client.js 的 CatDesk 包装器
 *
 * 用法：node <skill_dir>/scripts/mcp-client-shim.js <args...>
 *   （接口与 mt-mcp-client.js 完全相同，透明替换）
 *
 * 【CatDesk 环境】
 *   mt-mcp-client.js 在 SSO 认证失效时会调用 @mtfe/sso-web-oidc-cli，
 *   后者内部通过 open(url) 打开浏览器完成 OAuth 回调。
 *   sso-web-oidc-cli 使用自己 bundled 的 open（node_modules/open/index.js），
 *   与全局安装的 open 是不同的 require.cache key，同进程 patch 无法可靠拦截。
 *
 *   本 shim 采用与 sql-shim.js / dsx-shim.js 一致的进程隔离方案：
 *     1. 解析 sso-web-oidc-cli bundled open 的绝对路径
 *     2. 生成 ESM preload（NODE_OPTIONS --import），patch 该路径的 require.cache entry
 *     3. 以子进程方式启动 mt-mcp-client.js，子进程启动时 preload 最先执行，
 *        open() 被替换为 catdesk browser-action（CatDesk 内置浏览器）
 *
 *   mt-mcp-client.js 本身不再需要做任何 open patch，职责单一：SSO 认证 + MCP 通信。
 *
 * 【非 CatDesk 环境】直接透传给 mt-mcp-client.js，不做任何修改。
 *
 * 【CatDesk 环境检测】
 *   委托给 platform-compat.isCatDesk()，详见该函数文档。
 */

'use strict';

const path = require('path');
const fs   = require('fs');
const os   = require('os');
const compat = require('./platform-compat');
const { registry: NPM_REGISTRY } = require('./deps');

const SCRIPT_DIR   = __dirname;
const MT_MCP_CLIENT = path.join(SCRIPT_DIR, 'mt-mcp-client.js');

const { isCatDesk } = compat;

// ── 解析 sso-web-oidc-cli 中 open 模块的实际路径 ─────────────────────────────
//
// server.js 内部执行 require("open")，Node 解析规则是从 server.js 所在目录开始
// 向上查找 node_modules/open。有两种情况：
//   1. sso-web-oidc-cli 自带嵌套 node_modules/open（open@8 CJS）
//   2. npm dedupe 把 open 提升到全局，sso-web-oidc-cli 内部没有 node_modules/open
//
// 必须用 require.resolve({paths:[server.js目录]}) 得到真实解析路径，才能正确 patch。
// 注意：open@10+ 是纯 ESM，package.json 中有 "type":"module"，需要特殊处理。

function resolveSsoCliOpenPath() {
  try {
    const ssoCliPkg = compat.resolveGlobalLibraryPath('@mtfe/sso-web-oidc-cli', '@mtfe/sso-web-oidc-cli@latest', NPM_REGISTRY);

    // server.js 所在目录（require("open") 从这里开始解析）
    const serverJsDir = path.join(ssoCliPkg, 'lib', 'utils');

    // 从 server.js 视角解析 open 的真实路径
    try {
      const { createRequire } = require('module');
      const serverRequire = createRequire(path.join(serverJsDir, '_placeholder_.js'));
      return serverRequire.resolve('open');
    } catch (_) {}

    // fallback：尝试嵌套路径
    const nested = path.join(ssoCliPkg, 'node_modules', 'open', 'index.js');
    if (fs.existsSync(nested)) return nested;

    return null;
  } catch (_) {
    return null;
  }
}

// 检测 open 模块是否为 ESM（open@10+ 的 package.json 有 "type":"module"）
function isOpenEsm(openModulePath) {
  try {
    const pkgPath = path.join(path.dirname(openModulePath), 'package.json');
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
    return pkg.type === 'module';
  } catch (_) {
    return false;
  }
}

// ── 主逻辑 ────────────────────────────────────────────────────────────────────

const userArgs  = process.argv.slice(2);
const childEnv  = { ...process.env };

if (isCatDesk()) {
  const openModulePath = resolveSsoCliOpenPath();

  if (openModulePath && fs.existsSync(openModulePath)) {
    const openIsEsm = isOpenEsm(openModulePath);
    // 生成 ESM preload，写临时文件，拿到 --import <url> 片段
    const { bin: catdeskBin } = compat.resolveCatdesk();
    const preloadPath = path.join(os.tmpdir(), `mcp-client-shim-open-patch-${process.pid}.mjs`);
    const importOption = compat.writePreloadAndGetNodeOption(
      openModulePath, catdeskBin, preloadPath, '[mcp-client-shim]', openIsEsm
    );
    const existing = (process.env.NODE_OPTIONS || '').trim();
    childEnv.NODE_OPTIONS = [importOption, existing].filter(Boolean).join(' ');
  }
}

// 以子进程方式启动 mt-mcp-client.js，透传所有参数
// 使用 process.execPath（node 二进制绝对路径）而非 "node" 字符串，
// 避免 Windows 上 node.exe 不在 PATH 时报 ENOENT
const { spawnSync } = require('child_process');
const result = spawnSync(process.execPath, [MT_MCP_CLIENT, ...userArgs], {
  env:   childEnv,
  stdio: 'inherit',
});

process.exit(result.status ?? 0);
