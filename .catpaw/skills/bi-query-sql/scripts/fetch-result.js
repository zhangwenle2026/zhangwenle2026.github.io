#!/usr/bin/env node
/**
 * fetch-result.js — 轮询 Talos 查询状态 + 拉取结果 + 落盘 CSV（路径 B）或返回全量数据（路径 A）
 *
 * 用法：
 *   node fetch-result.js <qid> --server <alias> [options]
 *
 * 参数：
 *   qid           Talos 查询 ID（位置参数，必填）
 *
 * 选项：
 *   --server <alias>        MCP server alias（必填，国内传 hive，海外传 fra_hive）
 *   --work-dir <path>       工作区根目录，CSV 落盘到 <work-dir>/bi-query-sql/；未传则默认 process.cwd()
 *   --batch-size <n>        初始分批大小，默认 500
 *   --timeout <s>           最大等待秒数，默认 300
 *   --small-threshold <n>   ≤ 此行数走路径 A（全量返回），默认 100
 *
 * stdout 输出一行 JSON（供 LLM 解析）：
 *   成功路径 A：{ "status":"ok","path":"A","total":N,"columns":[...],"rows":[[...],...],"elapsed":N }
 *   成功路径 B：{ "status":"ok","path":"B","total":N,"columns":[...],"outputPath":"...","sizeKB":N,"preview":[[...],...],"elapsed":N }
 *   失败：      { "status":"error","reason":"FAILED|KILLED|TIMEOUT|...","message":"..." }
 *
 * 实现说明：
 *   本脚本通过 mcp-client-shim.js 调用 mt-mcp-client.js 的 query-info / query-result 子命令（shim 负责环境适配与鉴权）。
 *   query-result 数据量可能很大，通过 spawnSync + stdio 文件重定向写临时文件后再由 Node 读取解析，
 *   避免 maxBuffer 截断问题。
 *   query-info 数据量小，直接用 spawnSync 捕获 stdout 即可。
 *   两处 JSON 解析均有容错逻辑，兼容 shim 输出前带有 warning/ANSI 颜色码的情况。
 */

"use strict";

const { spawnSync } = require("child_process");
const fs   = require("fs");
const path = require("path");
const step = require("./lx-step");

// mcp-client-shim 路径（CatDesk 环境下自动注入 open preload，透明替代 mt-mcp-client.js）
const MCPORTER_JS = path.join(__dirname, "mcp-client-shim.js");

// ─── 参数解析 ────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const qid        = args[0];

if (!qid) {
  process.stderr.write("Usage: node fetch-result.js <qid> --server <alias> [--batch-size N] [--timeout N] [--small-threshold N] [--work-dir <path>]\n");
  process.exit(1);
}

function getOpt(name, def) {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] ? Number(args[i + 1]) : def;
}

const SERVER_ALIAS = (() => {
  const i = args.indexOf("--server");
  if (i === -1 || !args[i + 1]) {
    process.stderr.write("fetch-result: 缺少 --server\n");
    process.exit(1);
  }
  return args[i + 1];
})();

// 传给 mt-mcp-client 的 alias 参数
function serverArgs() {
  return ["--server", SERVER_ALIAS];
}

const INIT_BATCH_SIZE = getOpt("--batch-size", 500);
const TIMEOUT_SEC     = getOpt("--timeout", 300);
const SMALL_THRESHOLD = getOpt("--small-threshold", 100);
const WORK_DIR = (() => {
  const i = args.indexOf("--work-dir");
  if (i !== -1 && args[i+1]) return args[i+1];
  const cwd = process.cwd();
  process.stderr.write(`[fetch-result] --work-dir 未指定，CSV 将落盘到 ${cwd}/bi-query-sql/\n`);
  return cwd;
})();
const BI_DIR = path.join(WORK_DIR, "bi-query-sql");
const outputPath = path.join(BI_DIR, `query_result_${qid.slice(0, 8)}.csv`);
const MIN_BATCH_SIZE  = 1;

const startTime = Date.now();

step("query_execution.fetch_result.start", "查询结果拉取开始", {
  qid: qid.slice(0, 8),
  alias: SERVER_ALIAS,
});

// ─── stdoutWriteAndExit ──────────────────────────────────────────────────────
// 与 mt-mcp-client.js 同款：将 exit 放入 write 回调，确保 pipe 模式下数据不截断。
function stdoutWriteAndExit(data, exitCode, stepMeta) {
  process.stdout.write(data, () => {
    if (stepMeta) {
      step(stepMeta.id, stepMeta.name, stepMeta.customRecord).finally(() => process.exit(exitCode));
    } else {
      process.exit(exitCode);
    }
  });
}

// ─── mt-mcp-client 调用 ──────────────────────────────────────────────────────

/** 解析 mcp-client-shim stdout，取最后一个完整 JSON 对象（兼容登录消息 + 结果两行的情况） */
function parseShimOutput(raw) {
  if (!raw) throw new Error("No JSON in output: (empty)");
  try { return JSON.parse(raw.trim()); } catch (_) {}
  // 多对象：取最后一个顶层 JSON 对象
  const segments = [];
  let depth = 0, start = -1;
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] === "{") { if (depth === 0) start = i; depth++; }
    else if (raw[i] === "}") { depth--; if (depth === 0 && start !== -1) { segments.push(raw.slice(start, i + 1)); start = -1; } }
  }
  for (let i = segments.length - 1; i >= 0; i--) {
    try { return JSON.parse(segments[i]); } catch (_) {}
  }
  throw new Error("No JSON in output: " + raw.slice(0, 200));
}

/**
 * 调用 query-info 子命令（get_query_info / overseas_get_query_info）。
 * 数据量小，可以直接捕获 stdout。
 */
function callQueryInfo(qid) {
  const result = spawnSync(
    process.execPath,
    [MCPORTER_JS, "query-info", "--qid", qid, ...serverArgs()],
    { encoding: "utf8", timeout: 30000, maxBuffer: 8 * 1024 * 1024 }
  );
  if (result.error) throw result.error;
  return parseShimOutput(result.stdout || "");
}

/**
 * 调用 query-result 子命令（get_query_result / overseas_get_query_result）。
 * 数据量大，通过 spawnSync + stdio 文件重定向写临时文件，再由 Node 读取解析，
 * 避免 maxBuffer 截断问题。
 */
function callQueryResult(qid, offset, length) {
  const tmpDir = path.join(BI_DIR, ".tmp");
  fs.mkdirSync(tmpDir, { recursive: true });
  const tmpFile = path.join(tmpDir, `mcp_${Date.now()}_${Math.random().toString(36).slice(2)}.json`);
  try {
    const fd = fs.openSync(tmpFile, "w");
    const result = spawnSync(
      process.execPath,
      [MCPORTER_JS, "query-result",
        "--qid", qid,
        "--offset", String(offset),
        "--length", String(length),
        ...serverArgs()],
      { timeout: 60000, stdio: ["ignore", fd, "ignore"] }
    );
    fs.closeSync(fd);
    if (result.error) throw result.error;
    return parseShimOutput(fs.readFileSync(tmpFile, "utf8"));
  } finally {
    try { fs.unlinkSync(tmpFile); } catch (_) {}
  }
}

// ─── 轮询状态 ────────────────────────────────────────────────────────────────

function pollIntervalMs(elapsed) {
  if (elapsed < 10)  return 1000;
  if (elapsed < 30)  return 3000;
  if (elapsed < 60)  return 5000;
  if (elapsed < 300) return 10000;
  return 20000;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function pollUntilDone() {
  while (true) {
    const elapsed = (Date.now() - startTime) / 1000;
    if (elapsed > TIMEOUT_SEC) {
      return { status: "error", reason: "TIMEOUT", message: `Query did not finish within ${TIMEOUT_SEC}s` };
    }

    const res = callQueryInfo(qid);
    if (res.code !== 1) {
      return { status: "error", reason: "API_ERROR", message: res.message || JSON.stringify(res) };
    }

    const d     = res.data;
    const state = (d.status || "").trim();

    if (state === "FINISHED") {
      const total   = d.total ?? 0;
      const columns = (d.resultTableColumns || d.columns || []).map(c => c.name);
      return { status: "ok", total, columns };
    }
    if (state === "FAILED") {
      return { status: "error", reason: "FAILED", message: d.failReason || "Query FAILED" };
    }
    if (state === "KILLED") {
      return { status: "error", reason: "KILLED", message: "Query was KILLED" };
    }

    process.stderr.write(`[poll] status=${state} elapsed=${elapsed.toFixed(0)}s\n`);
    await sleep(pollIntervalMs(elapsed));
  }
}

// ─── 获取一批结果行 ───────────────────────────────────────────────────────────

function fetchBatch(offset, length) {
  const res = callQueryResult(qid, offset, length);

  if (res.code === -1) {
    const msg = String(res.message || "");
    if (msg.includes("超过1MB限制")) {
      const e = new Error("超过1MB限制");
      e.limitHit = true;
      throw e;
    }
    // C4+ 安全屋拦截统一由 mt-mcp-client.js 检测并替换提示文本，
    // 识别统一提示文本，保持 reason=SAFE_ROOM_BLOCKED 供上层错误处理路由
    if (msg.includes("C4+高敏数据")) {
      const e = new Error(msg);
      e.safeRoomBlocked = true;
      throw e;
    }
    throw new Error(msg || "get_query_result failed");
  }
  if (res.code !== 1) {
    throw new Error(res.message || "get_query_result unknown error");
  }

  // data.data 是序列化 JSON 字符串，需要二次 parse
  let inner = res?.data?.data ?? "{}";
  if (typeof inner === "string") inner = JSON.parse(inner);
  return inner?.data?.data ?? [];
}

// ─── CSV 工具 ─────────────────────────────────────────────────────────────────

function csvCell(val) {
  const s = val === null || val === undefined ? "" : String(val);
  if (s.includes(",") || s.includes('"') || s.includes("\n") || s.includes("\r")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}
function csvRow(cells) { return cells.map(csvCell).join(","); }

// ─── 路径 A：小结果集，全量返回（不落盘）────────────────────────────────────

async function fetchSmall(total, columns) {
  let rows;
  try {
    rows = fetchBatch(0, total);
  } catch (e) {
    if (e.limitHit) return null; // 降级到路径 B
    if (e.safeRoomBlocked) return { status: "error", reason: "SAFE_ROOM_BLOCKED", message: e.message };
    return { status: "error", reason: "FETCH_ERROR", message: e.message };
  }
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  return { status: "ok", path: "A", total, columns, rows, elapsed: Number(elapsed) };
}

// ─── 路径 B：大结果集，分批落盘 ──────────────────────────────────────────────

async function fetchLarge(total, columns, initBatch) {
  const outDir = path.dirname(path.resolve(outputPath));
  fs.mkdirSync(outDir, { recursive: true });

  const out = fs.createWriteStream(outputPath, { encoding: "utf8" });
  out.write("\uFEFF" + csvRow(columns) + "\n"); // UTF-8 BOM

  let batchSize = initBatch;
  let offset    = 0;
  let written   = 0;
  const preview = [];

  while (offset < total) {
    let rows;
    const remaining = total - offset;

    while (true) {
      const thisLength = Math.min(batchSize, remaining); // 每次重算，确保 batchSize 缩减后立即生效
      try {
        rows = fetchBatch(offset, thisLength);
        // 成功：尝试小幅恢复 batchSize（避免因一次碰限后永久低速拉取）
        if (batchSize < initBatch) {
          batchSize = Math.min(initBatch, batchSize * 2);
        }
        break;
      } catch (e) {
        if (e.limitHit) {
          const next = Math.max(MIN_BATCH_SIZE, Math.floor(batchSize / 2));
          if (next === batchSize) {
            // batchSize 已降至 1 仍触发限制 → 该行的某个字段值本身超过 1MB，无法拉取
            return { status: "error", reason: "BATCH_TOO_LARGE", message: `Single row at offset ${offset} contains a field exceeding 1MB, cannot fetch` };
          }
          process.stderr.write(`[batch] 1MB limit, reducing: ${batchSize} → ${next}\n`);
          batchSize = next;
          continue;
        }
        if (e.safeRoomBlocked) return { status: "error", reason: "SAFE_ROOM_BLOCKED", message: e.message };
        return { status: "error", reason: "FETCH_ERROR", message: e.message };
      }
    }

    if (rows.length === 0) break;

    for (const row of rows) {
      out.write(csvRow(row) + "\n");
      if (preview.length < 10) preview.push(row);
    }

    written += rows.length;
    offset  += rows.length;

    if (written % 1000 === 0 || offset >= total) {
      process.stderr.write(`[fetch] ${written}/${total} rows written\n`);
    }
  }

  await new Promise(r => out.end(r));

  const sizeKB  = (fs.statSync(outputPath).size / 1024).toFixed(1);
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  return {
    status: "ok",
    path: "B",
    total: written,
    columns,
    outputPath: path.resolve(outputPath),
    sizeKB: Number(sizeKB),
    preview,
    elapsed: Number(elapsed)
  };
}

// ─── 主入口 ──────────────────────────────────────────────────────────────────

async function main() {
  const poll = await pollUntilDone();
  if (poll.status !== "ok") {
    stdoutWriteAndExit(JSON.stringify(poll) + "\n", 1);
    return;
  }

  const resultBase = { qid: qid.slice(0, 8), total: poll.total };

  const { total, columns } = poll;

  // total=0：查询成功但无结果行，直接返回空路径 A，不调用 get_query_result
  if (total === 0) {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    stdoutWriteAndExit(JSON.stringify({
      status: "ok", path: "A", total: 0, columns, rows: [], elapsed: Number(elapsed)
    }) + "\n", 0, {
      id: "query_execution.fetch_result.done",
      name: "查询结果拉取完成",
      customRecord: { ...resultBase, path: "A", status: "success" },
    });
    return;
  }

  let result;
  if (total <= SMALL_THRESHOLD) {
    result = await fetchSmall(total, columns);
    if (result === null) {
      result = await fetchLarge(total, columns, Math.min(total, 50));
    }
  } else {
    const initBatch = columns.length > 30 ? 200 : INIT_BATCH_SIZE;
    result = await fetchLarge(total, columns, initBatch);
  }

  const stepMeta = {
    id: "query_execution.fetch_result.done",
    name: "查询结果拉取完成",
    customRecord: {
      ...resultBase,
      path: result.path,
      status: result.status === "ok" ? "success" : "error",
      reason: result.status === "ok" ? undefined : result.reason,
    },
  };
  stdoutWriteAndExit(JSON.stringify(result) + "\n", result.status === "ok" ? 0 : 1, stepMeta);
}

main().catch(e => {
  stdoutWriteAndExit(JSON.stringify({ status: "error", reason: "UNEXPECTED", message: e.message }) + "\n", 1);
});
