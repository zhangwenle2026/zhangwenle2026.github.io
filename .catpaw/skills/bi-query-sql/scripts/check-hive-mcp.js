#!/usr/bin/env node
/**
 * check-hive-mcp.js — 检查 hive MCP Server 可用性
 *
 * 用法：node <skill_dir>/scripts/check-hive-mcp.js [server-alias]
 *   server-alias  可选，默认 "hive"；海外传 "fra_hive"
 *
 * 退出码：
 *   0  — 可用（hive server tools 正常）
 *   1  — 不可用（token 过期 / 超时 / 其他异常）
 *
 * stdout 只输出一行简洁状态，不打印完整 tool 列表，节省 token。
 * 兼容 macOS / Linux / Windows。
 *
 * 使用 mt-mcp-client.js 直接连接 MCP Server，不再依赖 mcporter + mcp-proxy。
 */

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');
const step = require('./lx-step');

const SCRIPT_DIR = __dirname;
const MT_MCP_CLIENT = path.join(SCRIPT_DIR, 'mcp-client-shim.js');

// MCP Server 别名，支持命令行参数覆盖（默认国内 alias，由调用方显式传入；未传则兜底 'hive'）
const HIVE_MCP_SERVER_ALIAS = process.argv[2] || 'hive';

step('mcp.start', 'MCP 可用性检测开始', { alias: HIVE_MCP_SERVER_ALIAS });

// ── 执行 mcp-client-shim list hive ───────────────────────────────────────────

const result = spawnSync(process.execPath, [MT_MCP_CLIENT, 'list', HIVE_MCP_SERVER_ALIAS], {
  encoding: 'utf8',
  timeout: 90_000,
});

const stdout = (result.stdout || '').trim();
const stderr = (result.stderr || '').trim();
const combined = stdout + '\n' + stderr;

// ── 判断是否可用 ──────────────────────────────────────────────────────────────
// 可用标志：输出中包含 "N tools"（N >= 1）
const toolsMatch = combined.match(/(\d+)\s+tools/);
const toolCount = toolsMatch ? parseInt(toolsMatch[1], 10) : 0;

// 不可用关键词（匹配时注意：只匹配明确的错误模式，避免误匹配工具名/描述中的正常词汇）
// 注意：不要用裸 /failed/i，会误匹配工具名如 get_failed_queries / talos_get_query_engine_log
const UNAVAILABLE_PATTERNS = [
  /tools\s+unavailable/i,
  /token\s+error/i,
  /timed?\s*out/i,
  /not\s+found/i,
  /unknown\s+mcp\s+server/i,
  /error:/i,
  /\bauth.*failed\b/i,       // auth failed / authentication failed
  /\blogin.*failed\b/i,      // login failed
  /\bconnect.*failed\b/i,    // connect failed
  /\bfetch.*failed\b/i,      // fetch failed
];

const hasUnavailableSignal = UNAVAILABLE_PATTERNS.some(p => p.test(combined));

if (toolCount > 0 && !hasUnavailableSignal) {
  process.stdout.write(`${HIVE_MCP_SERVER_ALIAS} MCP 可用（${toolCount} tools）\n`, () => {
    step('mcp.done', 'MCP 可用性检测结果', {
      alias: HIVE_MCP_SERVER_ALIAS,
      status: 'available',
      tool_count: toolCount,
    }).finally(() => process.exit(0));
  });
} else {
  // 提取关键错误信息（取第一行非空内容，最多 120 字符）
  const firstLine = combined
    .split('\n')
    .map(l => l.trim())
    .find(l => l.length > 0) || '未知错误';
  const hint = firstLine.length > 120 ? firstLine.slice(0, 120) + '…' : firstLine;
  process.stdout.write(`${HIVE_MCP_SERVER_ALIAS} MCP 不可用：${hint}\n`, () => {
    step('mcp.done', 'MCP 可用性检测结果', {
      alias: HIVE_MCP_SERVER_ALIAS,
      status: 'unavailable',
      reason: hint,
    }).finally(() => process.exit(1));
  });
}
