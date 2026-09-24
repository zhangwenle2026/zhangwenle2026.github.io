#!/usr/bin/env node
/**
 * mt-mcp-client.js — 美团内部 MCP 客户端
 *
 * 支持两种运行环境：
 *
 * 【CatPaw Desk（本地）模式】
 *   直接实现 SSO 认证 + MCP HTTP 客户端：
 *   1. SSO 认证（完全对齐 mcp-proxy 的 SSOAuthHelper 逻辑）
 *      - proxy token 落盘（~/.mt_sso_config/product/<md5>_tokens.json）
 *      - MCP Server token 通过 tokenExchange 获取（内存，每次重新获取）
 *      - 浏览器打开改为 catdesk browser-action（内置浏览器）
 *   2. MCP HTTP 客户端（StreamableHTTP → SSE fallback）
 *
 * 【CatClaw 沙箱模式】（检测到 SANDBOX_ID / KUBERNETES_SERVICE_HOST 时自动启用）
 *   CatClaw 中 OAuth 回调无法工作，走无感换票路径：
 *   1. 优先调用 @mtfe/mtsso-auth-official 的 mtsso-moa-local-exchange 命令自动换票；
 *      token 缓存在 os.tmpdir()/mt-mcp-sso-<hash>.json，按 JWT exp 字段自动刷新；
 *      若连接时遭遇 401/403，自动清除缓存重新换票并重试一次。
 *   2. 若 mtsso 不可用（旧版沙箱），降级读取 mcporter.json 中已注册的 URL + header。
 *
 * 【依赖管理】所有第三方包均通过 npm install -g 自动安装到全局，不依赖任何外部工具
 *   的内部 node_modules 或 npx 缓存：
 *   - @modelcontextprotocol/sdk  — MCP 协议客户端
 *   - @mtfe/sso-web-oidc-cli     — SSO 认证（CatPaw Desk 模式）
 *   - @mtfe/mtsso-auth-official  — MOA 本地换票（CatClaw 沙箱模式）
 *   - open                       — 打开浏览器（被 catdesk browser-action patch 替代）
 *   - node-fetch                 — HTTP fetch（Node 18+ 内置，仅低版本需要）
 *
 * 【CLI 接口】list / call 命令行接口，兼容 mcporter 调用格式
 *
 * 用法（mcporter 兼容格式）：
 *   node mt-mcp-client.js list hive
 *   node mt-mcp-client.js call 'hive.submit_query(statement: "SELECT 1", submitScene: "MCP_SKILL")'
 *
 * 用法（直接 URL 格式）：
 *   node mt-mcp-client.js list http://mcphub-server.sankuai.com/mcphub-api/b9ab5ad54bd141
 *   node mt-mcp-client.js call http://mcphub-server.sankuai.com/mcphub-api/b9ab5ad54bd141 'submit_query(statement: "SELECT 1")'
 *
 * 环境变量：
 *   CATDESK_BIN   — catdesk 可执行文件路径（默认 ~/.catpaw/bin/catdesk）
 *   MT_MCP_DEBUG  — 设为 1 开启调试日志
 */

'use strict';

const path = require('path');
const os = require('os');
const fs = require('fs');
const crypto = require('crypto');
const { execFileSync, spawnSync } = require('child_process');
const compat = require('./platform-compat');

// ── Server 别名映射（从 mcporter.json 读取，或使用默认值）──────────────────

const DEFAULT_SERVER_ALIASES = {
  hive: 'http://mcphub-server.sankuai.com/mcphub-api/b9ab5ad54bd141',
  fra_hive: 'http://mcphub-server.sankuai.com/mcphub-c/a3733dbbf6344f',
};

function loadServerAliases() {
  const candidates = [
    path.join(os.homedir(), '.mcporter', 'mcporter.json'),
    path.join(os.homedir(), 'config', 'mcporter.json'),
    path.join(process.cwd(), 'config', 'mcporter.json'),
  ];
  for (const f of candidates) {
    try {
      const cfg = JSON.parse(fs.readFileSync(f, 'utf-8'));
      const servers = cfg?.mcpServers || {};
      const aliases = {};
      for (const [name, conf] of Object.entries(servers)) {
        // 从 npx @mtfe/mcp-proxy@latest <url> 的 args 中提取 URL
        const args = conf?.args || [];
        const url = args.find(a => a.startsWith('http://') || a.startsWith('https://'));
        if (url) aliases[name] = url;
      }
      if (Object.keys(aliases).length > 0) {
        // 合并而非替换，确保 DEFAULT_SERVER_ALIASES 里的条目（如 fra_hive）不丢失
        const merged = { ...DEFAULT_SERVER_ALIASES, ...aliases };
        log('loaded server aliases from', f, JSON.stringify(merged));
        return merged;
      }
    } catch (_) {}
  }
  return DEFAULT_SERVER_ALIASES;
}

// ── 常量（完全对齐 mcp-proxy）────────────────────────────────────────────────

const MCP_PROXY_CLIENT_ID = 'f29616e499'; // product 环境
const MCP_GATEWAY_ORIGIN = 'https://mcphub.sankuai.com';
const LOCAL_CALLBACK_PORTS = [7152, 8152, 9152, 10152];

const DEBUG = process.env.MT_MCP_DEBUG === '1';
const log = (...args) => { if (DEBUG) process.stderr.write('[mt-mcp] ' + args.join(' ') + '\n'); };
const info = (...args) => process.stderr.write('[mt-mcp] ' + args.join(' ') + '\n');

// ── CatClaw 沙箱环境检测 ──────────────────────────────────────────────────────

function isCatClaw() {
  return !!(
    process.env.SANDBOX_ID ||
    process.env.KUBERNETES_SERVICE_HOST ||
    (process.env.HOSTNAME || '').startsWith('sandbox-')
  );
}

// ── 依赖管理（委托给 platform-compat 的公共实现）────────────────────────────
const { ensureGlobalPackage, requireGlobalPackagePath } = Object.assign(
  function () {},
  compat,
  {
    ensureGlobalPackage: compat.ensureGlobalPackage || function (name, spec) { /* already installed globally */ },
    requireGlobalPackagePath: compat.requireGlobalPackagePath || function (name) {
      const globalRoot = require('child_process').execSync('npm root -g', { encoding: 'utf8' }).trim();
      return require('path').join(globalRoot, name);
    },
  }
);

// ── CatClaw 模式：通过官方 mtsso CLI 获取 token（含本地缓存）────────────────
//
// 使用 @mtfe/mtsso-auth-official 的 npx mtsso-moa-local-exchange 命令换票。
// token 缓存写入 os.tmpdir()/mt-mcp-sso-<hash>.json，解析 JWT exp 字段，提前 60s 视为过期。
// 如果 mtsso 失败（环境不支持 MOA），自动降级到 mcporter.json 读取。

// os.tmpdir() 跨平台返回正确的系统临时目录：
//   macOS/Linux → /tmp 或 $TMPDIR
//   Windows     → C:\Users\xxx\AppData\Local\Temp
const MTSSO_TOKEN_CACHE_DIR = os.tmpdir();

// ── 通用工具函数 ──────────────────────────────────────────────────────────────

function getHash(text) {
  return crypto.createHash('md5').update(text).digest('hex');
}

// ─────────────────────────────────────────────────────────────────────────────

function getMtssoTokenCachePath(audienceClientId) {
  const key = getHash('mtsso-' + (audienceClientId || 'default'));
  return path.join(MTSSO_TOKEN_CACHE_DIR, `mt-mcp-sso-${key}.json`);
}

function readMtssoTokenCache(audienceClientId) {
  try {
    const raw = JSON.parse(fs.readFileSync(getMtssoTokenCachePath(audienceClientId), 'utf-8'));
    const token = raw?.access_token;
    if (!token) return null;
    // 解析 JWT payload 中的 exp（无需验签，只看过期时间）
    const parts = token.split('.');
    if (parts.length === 3) {
      const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf-8'));
      const exp = payload?.exp;
      if (exp && Date.now() / 1000 < exp - 60) {
        log('mtsso: cache hit, exp in', Math.floor(exp - Date.now() / 1000), 's');
        return token;
      }
      log('mtsso: cache expired (exp was', exp, ')');
    }
    return null;
  } catch (_) {
    return null;
  }
}

function writeMtssoTokenCache(audienceClientId, accessToken) {
  try {
    fs.writeFileSync(
      getMtssoTokenCachePath(audienceClientId),
      JSON.stringify({ access_token: accessToken, cached_at: Date.now() }),
      'utf-8'
    );
  } catch (e) {
    log('mtsso: failed to write token cache:', e.message);
  }
}

// ensureMtssoInstalled 已被统一的 ensureGlobalPackage 取代，
// 保留此函数名作为语义别名，方便阅读。
function ensureMtssoInstalled() {
  ensureGlobalPackage('@mtfe/mtsso-auth-official', '@mtfe/mtsso-auth-official@latest');
}

async function getTokenViaMtsso(audienceClientId) {
  // 1. 确保依赖已安装
  ensureMtssoInstalled();

  // 2. 读缓存
  const cached = readMtssoTokenCache(audienceClientId);
  if (cached) return cached;

  // 3. 调用官方 CLI
  log('mtsso: calling mtsso-moa-local-exchange, audience:', audienceClientId || '(none)');
  // --registry 是 npx 自身参数（下载包时指定源），需放在包名之前
  const npxArgs = ['mtsso-moa-local-exchange'];
  if (audienceClientId) npxArgs.push('--audience', audienceClientId);

  const r = spawnSync(compat.getNpxCmd(), npxArgs, {
    encoding: 'utf-8',
    timeout: 30_000,
    env: { ...process.env },
  });
  if (r.error) {
    throw new Error('mtsso-moa-local-exchange 启动失败：' + r.error.message);
  }

  if (r.status !== 0) {
    const errMsg = (r.stderr || r.stdout || '').trim();
    // some versions exit non-zero but still print valid JSON token on stdout
    const so = (r.stdout || '').trim();
    let recovered = false;
    if (so) {
      try { const p = JSON.parse(so); if (p.access_token) { writeMtssoTokenCache(audienceClientId, p.access_token); return p.access_token; } } catch (_) {}
    }
    throw new Error('mtsso-moa-local-exchange 失败（exit ' + r.status + '）：' + errMsg);
  }

  let parsed;
  try {
    parsed = JSON.parse(r.stdout.trim());
  } catch (e) {
    throw new Error('mtsso-moa-local-exchange 输出解析失败：' + r.stdout.trim());
  }

  const token = parsed?.access_token;
  if (!token) {
    throw new Error('mtsso-moa-local-exchange 未返回 access_token：' + JSON.stringify(parsed));
  }

  // 3. 写缓存
  writeMtssoTokenCache(audienceClientId, token);
  log('mtsso: token obtained and cached, prefix:', token.substring(0, 10));
  return token;
}

// ── 加载 @modelcontextprotocol/sdk（统一入口，两种模式共用）────────────────
//
// 通过 ensureGlobalPackage 保证 SDK 已全局安装，返回 SDK 包目录。
function getMcpSdkBase() {
  return requireGlobalPackagePath('@modelcontextprotocol/sdk', '@modelcontextprotocol/sdk@latest');
}

// ── 通用 MCP 连接函数（CatClaw 和 CatPaw Desk 两种模式共用）─────────────────

async function connectMCPWithHeaders(serverUrl, headers) {
  const sdkBase = getMcpSdkBase();
  log('using SDK from', sdkBase);

  const { Client } = require(path.join(sdkBase, 'dist', 'cjs', 'client', 'index.js'));
  const client = new Client({ name: 'mt-mcp-client', version: '1.0.0' }, { capabilities: {} });
  const url = new URL(serverUrl);

  const streamableHttpPath = path.join(sdkBase, 'dist', 'cjs', 'client', 'streamableHttp.js');
  const ssePath = path.join(sdkBase, 'dist', 'cjs', 'client', 'sse.js');

  if (fs.existsSync(streamableHttpPath)) {
    try {
      const { StreamableHTTPClientTransport } = require(streamableHttpPath);
      const transport = new StreamableHTTPClientTransport(url, { requestInit: { headers } });
      await client.connect(transport);
      log('connected via StreamableHTTP');
      return client;
    } catch (e) {
      log('StreamableHTTP failed:', e.message);
      const msg = e.message || '';
      const shouldFallback = msg.includes('405') || msg.includes('Method Not Allowed')
        || msg.includes('404') || msg.includes('Not Found')
        || msg.includes('Unexpected content type')
        || msg.includes('text/html');
      if (!shouldFallback) throw e;
      log('falling back to SSE transport');
    }
  }

  if (fs.existsSync(ssePath)) {
    const { SSEClientTransport } = require(ssePath);
    const transport = new SSEClientTransport(url, { requestInit: { headers } });
    await client.connect(transport);
    log('connected via SSE');
    return client;
  }

  throw new Error('MCP SDK 中找不到可用的 transport（streamableHttp / sse）');
}

// CatClaw 模式直连入口（保持语义清晰）
async function connectMCPDirect(serverUrl, headers) {
  return connectMCPWithHeaders(serverUrl, headers);
}

// ── catdesk browser-action（替换 open npm 包）────────────────────────────────

const _catdesk = compat.resolveCatdesk();

function openWithCatdesk(url) {
  log('openWithCatdesk:', url);
  compat.openWithCatdesk(url, _catdesk, { log: info });
}

// ── Token 存储（完全对齐 mcp-proxy 的 SSOTokenStorage）──────────────────────

function encodeText(clientId, text) {
  if (!clientId || !text) return '';
  const key = getHash(clientId);
  const iv = crypto.randomBytes(16);
  const keyData = crypto.createHash('sha256').update(key).digest();
  const cipher = crypto.createCipheriv('aes-256-cbc', keyData, iv);
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  return Buffer.from(iv.toString('hex') + ':' + encrypted).toString('base64');
}

function decodeText(clientId, text) {
  if (!clientId || !text) return '';
  try {
    const key = getHash(clientId);
    const combined = Buffer.from(text, 'base64').toString('utf8');
    const [ivHex, encrypted] = combined.split(':');
    const iv = Buffer.from(ivHex, 'hex');
    const keyData = crypto.createHash('sha256').update(key).digest();
    const decipher = crypto.createDecipheriv('aes-256-cbc', keyData, iv);
    let decrypted = decipher.update(encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  } catch (e) {
    log('decodeText error:', e.message);
    return '';
  }
}

function getTokenDir() {
  return path.join(os.homedir(), '.mt_sso_config', 'product');
}

function getTokenFilePath(clientId) {
  const dir = getTokenDir();
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `${getHash(clientId)}_tokens.json`);
}

function readTokenSync(clientId) {
  try {
    const raw = JSON.parse(fs.readFileSync(getTokenFilePath(clientId), 'utf-8'));
    return {
      ...raw,
      access_token: decodeText(clientId, raw.access_token),
      refresh_token: decodeText(clientId, raw.refresh_token),
    };
  } catch (_) {
    return {};
  }
}

function writeTokenSync(clientId, tokens) {
  const raw = {
    ...tokens,
    access_token: encodeText(clientId, tokens.access_token || ''),
    refresh_token: encodeText(clientId, tokens.refresh_token || ''),
    created_at: Date.now(),
  };
  fs.writeFileSync(getTokenFilePath(clientId), JSON.stringify(raw, null, 2), 'utf-8');
}

// findMcpProxyDir / getNpxCacheCandidates 已移除。
// 所有依赖现在通过 ensureGlobalPackage / requireGlobalPackagePath 统一管理。

// ── Monkey-patch open 模块 ────────────────────────────────────────────────────
//
// @mtfe/sso-web-oidc-cli/lib/utils/server.js 在被 require 时执行：
//   var open_1 = __importDefault(require("open"))
// 之后调用 (0, open_1.default)(loginUrl)
//
// 策略：
//   1. 确保 open 已全局安装（ensureGlobalPackage）
//   2. 在 server.js 被 require 之前，替换 open 模块的 module.exports
//      → 这样 __importDefault(require("open")) 拿到的就是 patched 函数
//   3. 如果 server.js 已经被 require（require.cache 中存在），
//      清除 cache 后重新加载（此时 open 已被 patch）

function patchOpenModule(ssoCliBase) {
  // 确保 open 包已全局安装并定位路径
  const openBase = requireGlobalPackagePath('open', 'open@latest');
  // open v9+ 是纯 ESM，open v8 是 CJS。优先找 CJS 入口。
  const openModulePath = (() => {
    for (const candidate of [
      path.join(openBase, 'index.js'),        // open v8 (CJS)
      path.join(openBase, 'index.cjs'),       // 某些 fork
    ]) {
      if (fs.existsSync(candidate)) return candidate;
    }
    return null;
  })();

  if (!openModulePath) {
    // open v9+ 纯 ESM，CJS require 不可用。
    // sso-web-oidc-cli 内部的 open 是它自己 package.json 里锁定的版本，
    // 我们通过 patch require.cache 的方式已无法 intercept ESM。
    // 降级策略：用 patch require 拦截 sso-web-oidc-cli 自带的 open。
    log('patchOpenModule: open CJS not found, patching via sso-web-oidc-cli bundled open');
    patchOpenModuleViaSsoCli(ssoCliBase);
    return;
  }

  const patchedFn = function patchedOpen(url) {
    log('patched open() called:', url);
    openWithCatdesk(String(url));
    return Promise.resolve({ pid: -1, unref: () => {}, kill: () => {} });
  };

  // Step 1: 先 require 确保进入 cache，然后替换 exports
  const origOpen = require(openModulePath);
  Object.assign(patchedFn, origOpen); // 保留 .apps / .openApp 等属性
  try {
    const openMod = require.cache[require.resolve(openModulePath)];
    if (openMod) {
      openMod.exports = patchedFn;
      log('open module.exports patched at', openModulePath);
    }
  } catch (e) {
    log('open module cache patch failed (non-fatal):', e.message);
  }

  // Step 2: 如果 server.js 已经被 require，清除 cache 重新加载
  patchOpenModuleViaSsoCli(ssoCliBase);

  log('open module patched successfully');
}

// patch sso-web-oidc-cli 内部 server.js，确保它 require open 时拿到 patched 版本
function patchOpenModuleViaSsoCli(ssoCliBase) {
  const serverJsPath = path.join(ssoCliBase, 'lib', 'utils', 'server.js');
  try {
    const resolvedServerJs = require.resolve(serverJsPath);
    const serverMod = require.cache[resolvedServerJs];
    if (serverMod) {
      log('server.js already in cache, clearing and reloading...');
      delete require.cache[resolvedServerJs];
      require(serverJsPath);
      log('server.js reloaded with patched open');
    }
  } catch (e) {
    log('server.js cache patch failed (non-fatal):', e.message);
  }
}

// ── 确保 proxy token 有效，返回 SSOCliClient 实例 ────────────────────────────

async function ensureProxyClient() {
  // 确保 @mtfe/sso-web-oidc-cli 已全局安装
  const ssoCliBase = requireGlobalPackagePath('@mtfe/sso-web-oidc-cli', '@mtfe/sso-web-oidc-cli@latest');
  const ssoCliPath = path.join(ssoCliBase, 'lib', 'index.js');
  // 先 patch open，再 require（确保 server.js 加载时拿到 patched open）
  patchOpenModule(ssoCliBase);
  const { SSOCliClient } = require(ssoCliPath);

  const tokenStorage = {
    async get() { return readTokenSync(MCP_PROXY_CLIENT_ID); },
    async set(t) { writeTokenSync(MCP_PROXY_CLIENT_ID, t); },
  };

  const client = new SSOCliClient({
    clientId: MCP_PROXY_CLIENT_ID,
    accessEnv: 'product',
    tokenStorage,
    localPortList: Array.from(LOCAL_CALLBACK_PORTS),
    logOutputer: { log: (...a) => log(...a) },
    tag: 'mt-mcp-client',
  });

  // 检查现有 token
  const existing = readTokenSync(MCP_PROXY_CLIENT_ID);
  if (existing?.access_token) {
    log('checking existing proxy token...');
    try {
      const r = await client.whoami();
      if (r?.code === 0) {
        log('proxy token valid');
        return client;
      }
      log('proxy token invalid, code:', r?.code);
    } catch (e) {
      log('whoami error:', e.message);
    }
  }

  // token 不存在或已过期，重新登录
  info('SSO proxy token 不存在或已过期，开始登录...');
  patchOpenModule(ssoCliBase);
  await client.login();
  return client;
}

// ── 获取 MCP Server clientId（对齐 mcp-proxy 的 fetchRemoteClientId）─────────

async function fetchRemoteClientId(serverUrl) {
  try {
    const res = await nodeFetch(`${MCP_GATEWAY_ORIGIN}/public/openapi/mcpserver/details/by-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: [serverUrl] }),
    });
    if (!res.ok) { log('fetchRemoteClientId HTTP', res.status); return ''; }
    const data = await res.json();
    log('fetchRemoteClientId response:', JSON.stringify(data).substring(0, 200));
    if (data?.code === 200 && data?.result?.items?.length > 0) {
      return data.result.items[0].clientId || '';
    }
  } catch (e) {
    log('fetchRemoteClientId error:', e.message);
  }
  return '';
}

// ── 获取 MCP Server access token（对齐 SSOAuthHelper.waitForMCPServerAuthorized）

async function getMCPServerToken(proxyClient, mcpServerClientId) {
  if (!mcpServerClientId) {
    // 没有独立 clientId，直接用 proxy token
    log('no mcpServerClientId, using proxy token directly');
    return readTokenSync(MCP_PROXY_CLIENT_ID).access_token || '';
  }

  // 尝试 tokenExchange（对齐 mcp-proxy 的 waitForMCPServerAuthorized）
  log('attempting tokenExchange for clientId:', mcpServerClientId);
  try {
    const result = await proxyClient.tokenExchange(mcpServerClientId);
    if (result?.code === 0 && result?.data?.access_token) {
      log('tokenExchange success, token prefix:', result.data.access_token.substring(0, 10));
      return result.data.access_token;
    }
    log('tokenExchange failed:', JSON.stringify(result));
  } catch (e) {
    log('tokenExchange error:', e.message);
  }

  // fallback: 直接用 proxy token
  log('tokenExchange failed, falling back to proxy token');
  return readTokenSync(MCP_PROXY_CLIENT_ID).access_token || '';
}

// ── 简单 fetch 封装（Node 18+ 内置，低版本自动安装 node-fetch）──────────────

async function nodeFetch(url, opts) {
  if (typeof globalThis.fetch === 'function') {
    return globalThis.fetch(url, opts);
  }
  // Node < 18：确保 node-fetch 已全局安装后 require
  // node-fetch v3+ 是纯 ESM，v2 是 CJS；全局安装时优先用 v2 保证 require 可用
  const nfBase = requireGlobalPackagePath('node-fetch', 'node-fetch@2');
  const nf = require(nfBase);
  const fetchFn = nf.default || nf;
  return fetchFn(url, opts);
}

// ── MCP HTTP 客户端（CatPaw Desk 模式入口）───────────────────────────────────

async function connectMCP(serverUrl, accessToken) {
  const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
  return connectMCPWithHeaders(serverUrl, headers);
}

// ── 解析调用表达式 ────────────────────────────────────────────────────────────
//
// 支持两种格式：
//   mcporter 兼容：hive.submit_query(statement: "SELECT 1", submitScene: "MCP_SKILL")
//   直接格式：     submit_query(statement: "SELECT 1")

function parseCallExpression(expr) {
  const match = expr.match(/^(?:(\w+)\.)?(\w+)\s*\((.*)\)$/s);
  if (!match) throw new Error('无效的调用语法，期望：[alias.]toolName(arg: val, ...)');

  const serverAlias = match[1] || null;
  const toolName = match[2];
  const argsStr = (match[3] || '').trim();
  const args = {};

  if (argsStr) {
    let remaining = argsStr;
    while (remaining.length > 0) {
      remaining = remaining.replace(/^[\s,]+/, '');
      if (!remaining) break;

      const keyMatch = remaining.match(/^(\w+)\s*:\s*/);
      if (!keyMatch) break;
      const key = keyMatch[1];
      remaining = remaining.slice(keyMatch[0].length);

      let value;
      if (remaining.startsWith('"') || remaining.startsWith("'")) {
        const quote = remaining[0];
        let i = 1, str = '';
        while (i < remaining.length) {
          if (remaining[i] === '\\' && i + 1 < remaining.length) {
            const esc = remaining[i + 1];
            str += esc === 'n' ? '\n' : esc === 't' ? '\t' : esc;
            i += 2;
          } else if (remaining[i] === quote) { i++; break; }
          else { str += remaining[i]; i++; }
        }
        value = str;
        remaining = remaining.slice(i);
      } else if (remaining.startsWith('{') || remaining.startsWith('[')) {
        const open = remaining[0], close = open === '{' ? '}' : ']';
        let depth = 0, i = 0;
        for (; i < remaining.length; i++) {
          if (remaining[i] === open) depth++;
          else if (remaining[i] === close && --depth === 0) { i++; break; }
        }
        const jsonStr = remaining.slice(0, i);
        try { value = JSON.parse(jsonStr); } catch { value = jsonStr; }
        remaining = remaining.slice(i);
      } else {
        const valMatch = remaining.match(/^([^,]+)/);
        if (!valMatch) break;
        const raw = valMatch[1].trim();
        remaining = remaining.slice(valMatch[0].length);
        if (raw === 'true') value = true;
        else if (raw === 'false') value = false;
        else if (raw === 'null') value = null;
        else if (!isNaN(Number(raw)) && raw !== '') value = Number(raw);
        else value = raw;
      }
      args[key] = value;
    }
  }

  return { serverAlias, toolName, args };
}

// ── 解析 server URL（支持别名和直接 URL）────────────────────────────────────

function resolveServerUrl(serverOrAlias, aliases) {
  if (!serverOrAlias) throw new Error('缺少 server URL 或别名');
  if (serverOrAlias.startsWith('http://') || serverOrAlias.startsWith('https://')) {
    return serverOrAlias;
  }
  const url = aliases[serverOrAlias.toLowerCase()];
  if (!url) throw new Error(`未知的 server 别名：${serverOrAlias}，已知别名：${Object.keys(aliases).join(', ')}`);
  return url;
}

// ── 主逻辑 ───────────────────────────────────────────────────────────────────

async function main() {
  const argv = process.argv.slice(2);
  const command = argv[0];

  if (!command || command === '--help' || command === '-h') {
    process.stderr.write(
      '用法：\n' +
      '  node mt-mcp-client.js list <serverUrl|alias>\n' +
      '  node mt-mcp-client.js call <serverUrl|alias> \'toolName(arg: val)\'\n' +
      '  node mt-mcp-client.js call \'alias.toolName(arg: val)\'  # mcporter 兼容\n'
    );
    process.exit(0);
  }

  // 加载 server 别名
  const aliases = loadServerAliases();

  let serverUrl;
  let callExpr;

  if (command === 'list') {
    serverUrl = resolveServerUrl(argv[1], aliases);
  } else if (command === 'call') {
    if (argv[1] && !argv[2]) {
      // mcporter 兼容格式：'hive.toolName(...)'
      callExpr = argv[1];
      const { serverAlias } = parseCallExpression(callExpr);
      if (!serverAlias) throw new Error('单参数 call 需要 alias 前缀，如：hive.toolName(...)');
      serverUrl = resolveServerUrl(serverAlias, aliases);
    } else if (argv[1] && argv[2]) {
      // 直接格式：<serverUrl> 'toolName(...)'
      serverUrl = resolveServerUrl(argv[1], aliases);
      callExpr = argv[2];
    } else {
      process.stderr.write('call 命令缺少参数\n');
      process.exit(1);
    }
  } else {
    process.stderr.write(`未知命令：${command}\n`);
    process.exit(1);
  }

  // ── 认证 + 连接（根据运行环境选择不同路径）──────────────────────────────────

  let client;

  if (isCatClaw()) {
    // ── CatClaw 沙箱模式：通过官方 mtsso CLI 无感取票后直连 ──────────────────
    // 优先使用 npx mtsso-moa-local-exchange（MOA 本地换票，无需浏览器/手动注册）。
    // 若 mtsso 不可用（旧沙箱版本），自动降级到读取 mcporter.json（兼容旧流程）。
    log('running in CatClaw sandbox mode');

    // Step 1：查询 MCP Server clientId（用作 mtsso --audience 参数）
    const mcpServerClientId = await fetchRemoteClientId(serverUrl);
    log('catclaw: mcpServerClientId:', mcpServerClientId || '(none)');

    let resolvedUrl = serverUrl;
    let authHeaders = {};

    // Step 2：尝试 mtsso 官方换票
    let mtssoToken = null;
    try {
      mtssoToken = await getTokenViaMtsso(mcpServerClientId);
    } catch (mtssoErr) {
      log('catclaw: mtsso failed:', mtssoErr.message);
      info('CatClaw 模式：mtsso 换票失败，降级到 mcporter.json 配置...');
    }

    if (mtssoToken) {
      // mtsso 成功：直接用 serverUrl + Bearer token
      authHeaders = { Authorization: `Bearer ${mtssoToken}` };
      info('CatClaw 模式：mtsso 换票成功，连接 ' + resolvedUrl);
    } else {
      // 降级：从 mcporter.json 读取已注册的 URL + header（旧版沙箱兼容路径）
      // mcporter config add 写入格式：{ mcpServers: { hive: { url, headers, allowHttp } } }
      const aliasMap = loadServerAliases();
      const serverAliasForCatclaw = Object.entries(aliasMap).find(([, v]) => v === serverUrl)?.[0]
        || Object.keys(aliasMap).find(k => serverUrl === k)
        || 'hive';

      const mcporterJsonCandidates = [
        path.join(os.homedir(), '.mcporter', 'mcporter.json'),
        path.join(os.homedir(), 'config', 'mcporter.json'),
      ];
      let mcporterCfg = null;
      for (const f of mcporterJsonCandidates) {
        try {
          const cfg = JSON.parse(fs.readFileSync(f, 'utf-8'));
          const server = cfg?.mcpServers?.[serverAliasForCatclaw];
          if (!server) continue;
          const httpUrl = server.url || server.baseUrl;
          if (httpUrl) {
            mcporterCfg = { url: httpUrl, headers: server.headers || {} };
            log('catclaw: fallback loaded mcporter config from', f);
            break;
          }
          // stdio 模式降级：从 args 里提取 URL
          const argUrl = (server.args || []).find(a => a.startsWith('http://') || a.startsWith('https://'));
          if (argUrl) {
            mcporterCfg = { url: argUrl, headers: {} };
            log('catclaw: fallback stdio-mode url from', f);
            break;
          }
        } catch (_) {}
      }

      if (!mcporterCfg) {
        throw new Error(
          `CatClaw 模式：mtsso 换票失败，且在 mcporter.json 中找不到 "${serverAliasForCatclaw}" 的配置。\n` +
          '请确认沙箱 MOA 已绑定用户身份，或手动运行：\n' +
          '  bash /app/skills/friday-catclaw-mcp/scripts/mcp-setup.sh "' + serverUrl + '"'
        );
      }
      resolvedUrl = mcporterCfg.url || serverUrl;
      authHeaders = mcporterCfg.headers;
      info('CatClaw 模式：使用 mcporter.json 降级配置连接 ' + resolvedUrl);
    }

    // 连接时若遇到 401/403（token 未到期但服务端已失效），自动清缓存重新换票重试一次
    try {
      client = await connectMCPDirect(resolvedUrl, authHeaders);
    } catch (connErr) {
      const msg = connErr.message || '';
      const isAuthError = msg.includes('401') || msg.includes('403')
        || msg.includes('Unauthorized') || msg.includes('Forbidden');
      if (!isAuthError || !mtssoToken) throw connErr;

      log('catclaw: got auth error, clearing token cache and retrying...');
      info('CatClaw 模式：token 已失效，正在重新换票...');

      // 清除缓存，强制重新调用 mtsso CLI
      try { fs.unlinkSync(getMtssoTokenCachePath(mcpServerClientId)); } catch (_) {}

      const freshToken = await getTokenViaMtsso(mcpServerClientId);
      client = await connectMCPDirect(resolvedUrl, { Authorization: `Bearer ${freshToken}` });
      log('catclaw: retry succeeded with fresh token');
    }

  } else {
    // ── CatPaw Desk 本地模式：走 SSO 认证 ───────────────────────────────────
    // Step 1: 确保 proxy token 有效
    const proxyClient = await ensureProxyClient();

    // Step 2: 获取 MCP Server clientId
    const mcpServerClientId = await fetchRemoteClientId(serverUrl);
    log('mcpServerClientId:', mcpServerClientId || '(none)');

    // Step 3: 获取 MCP Server access token
    const accessToken = await getMCPServerToken(proxyClient, mcpServerClientId);
    log('accessToken prefix:', accessToken?.substring(0, 10) || '(empty)');

    client = await connectMCP(serverUrl, accessToken);
  }

  try {
    if (command === 'list') {
      const result = await client.listTools();
      const tools = result?.tools || [];

      let output = serverUrl.split('/').pop() + '\n\n';
      for (const tool of tools) {
        if (tool.description) {
          output += `  /**\n   * ${tool.description.replace(/\n/g, '\n   * ')}\n   */\n`;
        }
        const props = tool.inputSchema?.properties || {};
        const required = tool.inputSchema?.required || [];
        const paramStr = Object.entries(props).map(([k, v]) => {
          const opt = required.includes(k) ? '' : '?';
          return `${k}${opt}: ${v.type || 'any'}`;
        }).join(', ');
        output += `  function ${tool.name}(${paramStr});\n\n`;
      }
      if (tools.length > 0) {
        output += `  Examples:\n    node mt-mcp-client.js call '${tools[0].name}(arg: "value")'\n\n`;
      }
      output += `  ${tools.length} tools`;
      process.stdout.write(output + '\n');

    } else if (command === 'call') {
      const { toolName, args: toolArgs } = parseCallExpression(callExpr);
      log('calling tool:', toolName, JSON.stringify(toolArgs));

      const result = await client.callTool({ name: toolName, arguments: toolArgs });
      const content = result?.content;
      if (Array.isArray(content) && content.length > 0 && content[0].type === 'text') {
        process.stdout.write(content[0].text + '\n');
      } else {
        process.stdout.write(JSON.stringify(result, null, 2) + '\n');
      }
    }
  } finally {
    await client.close().catch(() => {});
  }

  process.exit(0);
}

main().catch((e) => {
  process.stderr.write('[mt-mcp-client] 错误：' + e.message + '\n');
  if (DEBUG) process.stderr.write(e.stack + '\n');
  process.exit(1);
});
