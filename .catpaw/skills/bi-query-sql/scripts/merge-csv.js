#!/usr/bin/env node
/**
 * merge-csv.js — 合并 Hive 分批查询结果并输出 CSV
 *
 * 用法：
 *   node merge-csv.js <work_dir> <output_path> <columns_json>
 *
 * 参数：
 *   work_dir      批次 JSON 文件所在目录（含 batch_*.json）
 *   output_path   输出 CSV 文件路径
 *   columns_json  列定义 JSON 数组，格式：'[{"name":"col1","type":"bigint"}, ...]'
 *
 * 示例：
 *   node merge-csv.js /path/to/hive_result_abc123 ./result.csv '[{"name":"id"},{"name":"name"}]'
 */

"use strict";

const fs = require("fs");
const path = require("path");

// ---------- 从 shell 输出中提取纯 JSON ----------
// 批次文件内容可能被 shell 日志包裹，头部有 YAML 元信息，尾部有退出码等日志。
// 策略：找到第一个 '{' 到最后一个 '}' 之间的内容作为 JSON。
function extractJson(raw) {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("Cannot find JSON object in file content");
  }
  return raw.slice(start, end + 1);
}

// ---------- CSV 转义（RFC 4180）----------
function csvCell(val) {
  const s = val === null || val === undefined ? "" : String(val);
  if (s.includes(",") || s.includes('"') || s.includes("\n") || s.includes("\r")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function csvRow(cells) {
  return cells.map(csvCell).join(",");
}

// ---------- 主逻辑 ----------
function main() {
  const [, , workDir, outputPath, columnsJson] = process.argv;
  if (!workDir || !outputPath || !columnsJson) {
    console.error("Usage: node merge-csv.js <work_dir> <output_path> <columns_json>");
    process.exit(1);
  }

  // 解析列名
  const columns = JSON.parse(columnsJson).map((c) => c.name);

  // 按文件名排序读取所有批次文件
  const batchFiles = fs
    .readdirSync(workDir)
    .filter((f) => f.startsWith("batch_") && f.endsWith(".json"))
    .sort()
    .map((f) => path.join(workDir, f));

  if (batchFiles.length === 0) {
    console.error("ERROR: No batch files found in", workDir);
    process.exit(1);
  }

  // 确保输出目录存在
  const outDir = path.dirname(path.resolve(outputPath));
  fs.mkdirSync(outDir, { recursive: true });

  // 写 CSV（UTF-8 BOM，兼容 Excel）
  const BOM = "\uFEFF";
  const out = fs.createWriteStream(outputPath, { encoding: "utf8" });
  out.write(BOM + csvRow(columns) + "\n");

  let totalRows = 0;

  for (const bf of batchFiles) {
    const rawContent = fs.readFileSync(bf, "utf8");

    let raw;
    try {
      raw = JSON.parse(rawContent);
    } catch (_) {
      // 含 shell 日志包裹，提取纯 JSON 后再解析
      try {
        raw = JSON.parse(extractJson(rawContent));
      } catch (e) {
        console.error(`ERROR: Failed to parse ${path.basename(bf)}: ${e.message}`);
        process.exit(1);
      }
    }

    // data.data 可能是嵌套 JSON 字符串，也可能已经是对象
    let inner = raw?.data?.data ?? "{}";
    if (typeof inner === "string") inner = JSON.parse(inner);

    const rows = inner?.data?.data ?? [];
    for (const row of rows) {
      out.write(csvRow(row) + "\n");
    }
    totalRows += rows.length;
    console.log(`${path.basename(bf)}: ${rows.length} rows`);
  }

  console.log(`Total: ${totalRows} rows`);

  // 等 stream flush 完再 stat
  out.end(() => {
    const sizeKB = (fs.statSync(outputPath).size / 1024).toFixed(1);
    console.log(`Saved to: ${outputPath} (${sizeKB} KB)`);
  });
}

main();
