"""
基尼系数算子

用于衡量某个指标波动贡献在当前 group-by 维度下的集中度：
  0 表示贡献分布完全均匀，越接近 1 表示波动贡献越集中。

列命名规则：
  standard   : {measureCode}_{pop}_gini
  normalized : {measureCode}_{pop}_normalized_gini
"""

from __future__ import annotations


def _to_float(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "null", "NULL", "None"):
        return None
    is_percent = s.endswith("%")
    if is_percent:
        s = s[:-1]
    s = s.replace(",", "")
    try:
        value = float(s)
    except (ValueError, TypeError):
        return None
    if is_percent:
        value = value / 100
    return value


def _calc_standard_gini(cleaned: list[float]) -> float | None:
    n = len(cleaned)
    if n == 0:
        return None
    total = sum(cleaned)
    if total == 0 or n == 1:
        return 0.0
    sorted_values = sorted(cleaned)
    weighted_sum = sum((idx + 1) * value for idx, value in enumerate(sorted_values))
    gini = (2 * weighted_sum) / (n * total) - (n + 1) / n
    return round(gini, 6)


def _calc_normalized_gini(cleaned: list[float]) -> float | None:
    standard = _calc_standard_gini(cleaned)
    if standard is None:
        return None
    n = len(cleaned)
    if n <= 1:
        return 0.0
    max_gini = (n - 1) / n
    if max_gini == 0:
        return 0.0
    normalized = standard / max_gini
    return round(min(max(normalized, 0.0), 1.0), 6)


def _calc_gini(values: list[float | None], mode: str) -> dict[str, float | None]:
    cleaned = [max(v, 0.0) for v in values if v is not None]
    standard = _calc_standard_gini(cleaned)
    normalized = _calc_normalized_gini(cleaned)
    if mode == "standard":
        return {"gini": standard}
    if mode == "normalized":
        return {"normalized_gini": normalized}
    if mode == "both":
        return {"gini": standard, "normalized_gini": normalized}
    raise ValueError(f"unsupported gini mode: {mode}")


def calc_gini(
    result: dict,
    gini_measures: list[str],
    pops: list[str],
    mode: str = "normalized",
) -> dict:
    """
    在 result 中为每个 gini_measures 指标插入波动贡献基尼系数列。

    基尼系数基于 {measure}_{pop}_fluctuation_value 的绝对值计算，衡量
    波动贡献是否集中在少数分组上。波动贡献列由 fluctuation 算子生成。
    """
    rows = result.get("rows") or []
    gini_values: dict[str, dict[str, float | None]] = {}
    for measure in gini_measures:
        for pop in pops:
            source_col = f"{measure}_{pop}_fluctuation_value"
            values = []
            for row in rows:
                value = _to_float(row.get(source_col))
                values.append(abs(value) if value is not None else None)
            gini_values[f"{measure}_{pop}"] = _calc_gini(values, mode)

    for row in rows:
        for measure in gini_measures:
            for pop in pops:
                values = gini_values.get(f"{measure}_{pop}", {})
                if "gini" in values:
                    row[f"{measure}_{pop}_gini"] = values["gini"]
                if "normalized_gini" in values:
                    row[f"{measure}_{pop}_normalized_gini"] = values["normalized_gini"]

    new_columns = []
    for col in result.get("columns") or []:
        new_columns.append(col)
        for measure in gini_measures:
            for pop in pops:
                fluctuation_col = f"{measure}_{pop}_fluctuation_value"
                if col == fluctuation_col:
                    if mode in ("standard", "both"):
                        new_columns.append(f"{measure}_{pop}_gini")
                    if mode in ("normalized", "both"):
                        new_columns.append(f"{measure}_{pop}_normalized_gini")
    result["columns"] = new_columns
    return result
