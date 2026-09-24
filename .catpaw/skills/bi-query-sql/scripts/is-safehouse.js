#!/usr/bin/env node
/**
 * is-safehouse.js — 检测当前会话是否已开启安全屋模式
 *
 * 用法:
 *   node is-safehouse.js
 *
 * 判断依据：环境变量 IS_SAFE_ROOM_AGENT
 *   - 值为 "true"（字符串）→ 安全屋 ON
 *   - 其他值或未设置      → 安全屋 OFF
 *
 * stdout 输出一行 JSON，LLM 直接读取 action 字段执行，无需推理：
 *
 *   {"action":"PROCEED"}
 *     → 安全屋 ON，直接继续，无需任何提示
 *
 *   {"action":"ASK_CONFIRM","question":"⚠️ 数据安全提示\n若数据包含高密数据（C4+数据），请确认已开启安全屋模式后，继续分析。","options":[{"id":"continue","label":"非高密数据，不开启安全屋，继续分析"},{"id":"stop","label":"高密数据（C4+数据），手动开启新会话打开安全屋，重新分析"}]}
 *     → 安全屋 OFF，LLM 必须立即用 AskQuestion 工具展示 question + options，
 *       用户选 continue → 继续，选 stop → 停止并提示重新开启安全屋
 *
 * 退出码统一为 0（stdout JSON 即为唯一信号，不再用退出码区分状态）
 */

"use strict";

const step = require("./lx-step");

step("safehouse.start", "安全屋检测开始");

const ASK_CONFIRM_PAYLOAD = {
  action: "ASK_CONFIRM",
  question:
    "⚠️ 数据安全提示\n若数据包含高密数据（C4+数据），请确认已开启安全屋模式后，继续分析。",
  options: [
    { id: "continue", label: "非高密数据，不开启安全屋，继续分析" },
    {
      id: "stop",
      label: "高密数据（C4+数据），手动开启新会话打开安全屋，重新分析",
    },
  ],
};

const payload = process.env.IS_SAFE_ROOM_AGENT === "true"
  ? { action: "PROCEED" }
  : ASK_CONFIRM_PAYLOAD;

process.stdout.write(JSON.stringify(payload) + "\n", () => {
  step("safehouse.done", "安全屋检测结果", { action: payload.action }).finally(() => {
    process.exit(0);
  });
});
