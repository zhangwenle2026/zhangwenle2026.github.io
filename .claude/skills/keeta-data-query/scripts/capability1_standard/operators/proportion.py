"""
占比算子 — 对应 server ProportionFunctionExecutor

计算逻辑：
  proportion_i = value_i / total_value
  total_value 来自调用方传入的汇总行（无 group_by 的查询结果第一行），
  对应 server 针对 DEDUPLICATIVE/RATIO 指标发起的 split 请求。

列命名规则（与 server FunctionEnum.PROPORTION 一致）：
  {measureCode}_proportion
"""

from __future__ import annotations


def _to_float(v) -> float | None:
    if v is None or str(v).strip() in ("", "null", "NULL", "None"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def calc_proportion(result: dict, total_row: dict, proportion_measures: list[str]) -> dict:
    """
    在 result 中为每个 proportion_measures 指标插入占比列。

    参数：
        result            : standard query 返回值（含 columns / rows / total）
        total_row         : 无 group_by 汇总查询的第一行，用作分母
        proportion_measures: 需要计算占比的指标 code 列表

    返回：
        修改后的 result（in-place 修改 rows/columns，同时返回以便链式调用）

    列规则：
        每个 measure 列之后紧跟 {measure}_proportion 列，值为 0~1 小数
    """
    for row in result["rows"]:
        for m in proportion_measures:
            val = _to_float(row.get(m))
            total = _to_float(total_row.get(m))
            if val is not None and total:
                row[f"{m}_proportion"] = round(val / total, 6)
            else:
                row[f"{m}_proportion"] = None

    new_columns = []
    for col in result["columns"]:
        new_columns.append(col)
        if col in proportion_measures:
            new_columns.append(f"{col}_proportion")
    result["columns"] = new_columns
    return result
