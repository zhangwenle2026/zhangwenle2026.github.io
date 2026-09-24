"use strict";

const { executeLxReport, ReportTypeEnum } = require("./lx.js");

module.exports = function step(stepId, stepName, customRecord = {}) {
  const payload = {
    command: ReportTypeEnum.STEP,
    stepId,
    customRecord: {
      step_name: stepName,
      ...customRecord,
    },
  };

  return executeLxReport(payload).catch((error) => {
    process.stderr.write(`[lx-step] ${stepId} 上报失败: ${error.message}\n`);
  });
};
