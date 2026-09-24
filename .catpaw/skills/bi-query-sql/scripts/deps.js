'use strict';
/**
 * deps.js — 脚本外部依赖统一配置
 *
 * 集中声明所有外部依赖，升级版本或替换包时只需修改这里。
 *
 * packages.<key> 字段说明：
 *   name        npm 包名（require 时使用）
 *   version     安装版本约束（如 'latest'、'2'、'0.2.9'）
 *   binName     可选，CLI 工具的 bin 名称（有 bin 的包才填）
 *   minVersion  可选，版本满足性检查的最低要求（CLI 工具按需填写）
 *
 * 工具函数：
 *   installSpec(pkg)  返回 npm install 规格字符串，例如 "node-fetch@2"
 *   cliOpts(key)      返回 ensureGlobalCli 所需的参数对象
 */

/** 返回包的 npm install 规格字符串，例如 "@mtfe/sso-web-oidc-cli@latest" */
function installSpec(pkg) {
  return pkg.name + '@' + pkg.version;
}

const packages = {
  // ── CLI 工具 ────────────────────────────────────────────────────────────────
  dsx: {
    name:       '@datafe/dsx-cli',
    version:    'latest',
    binName:    'dsx',
    minVersion: '0.2.9',
  },
  sql: {
    name:       '@datafe/sql-cli',
    version:    'latest',
    binName:    'sql',
    minVersion: '0.1.4',
  },

  // ── mt-mcp-client.js 运行时库（按需全局安装）────────────────────────────────
  /** MCP 协议客户端 */
  mcpSdk: {
    name:    '@modelcontextprotocol/sdk',
    version: 'latest',
  },
  /** SSO 认证（CatPaw Desk 浏览器 SSO 路径）*/
  ssoWebOidc: {
    name:    '@mtfe/sso-web-oidc-cli',
    version: 'latest',
  },
  /** MOA 本地换票（CatClaw 沙箱 + CatPaw Desk MOA 路径）*/
  mtssoAuth: {
    name:    '@mtfe/mtsso-auth-official',
    version: 'latest',
  },
  /** HTTP fetch（Node 18+ 内置，低版本需要；v2 为 CJS，避免 ESM 兼容问题）*/
  nodeFetch: {
    name:    'node-fetch',
    version: '2',
  },
};

/**
 * 为 platform-compat.ensureGlobalCli 生成参数对象。
 * 该函数接收 { binName, packageName, minVersion, registry, ... }，
 * 其中 packageName 对应 packages[key].name。
 */
function cliOpts(key) {
  const pkg = packages[key];
  return {
    binName:     pkg.binName,
    packageName: pkg.name,
    minVersion:  pkg.minVersion,
  };
}

/** 内网 npm registry */
const registry = 'http://r.npm.sankuai.com';

module.exports = { packages, registry, installSpec, cliOpts };
