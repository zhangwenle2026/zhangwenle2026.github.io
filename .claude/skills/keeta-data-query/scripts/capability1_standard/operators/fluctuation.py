"""
波动贡献算子 — 对应 server DimFluctuationFunctionExecutor

计算逻辑（三种模式）：

  ADDITIVE（可加型，默认）：
    contribution_i = (value_i - base_i) / (total_current - total_base)
    对应 FunctionMathUtil.caleDimFluctuationValue

  DEDUPLICATIVE（去重型）：
    all_changes = |∑(value_j - base_j)|   （先求和再取绝对值）
    contribution_i = (value_i - base_i) * sign(total_change) / all_changes
    对应 FunctionMathUtil.caleDeductiveDimFluctuationValue

  RATIO（比值型）：
    贡献度 = (趋势贡献 + 结构贡献) / total_ratio_change
      趋势贡献 = (ratio_i - ratio_base_i) × (den_base_i / den_sum_base)
      结构贡献 = (den_i/den_sum_current - den_base_i/den_sum_base) × (ratio_i - ratio_sum_base)
      total_ratio_change = num_sum_cur/den_sum_cur - num_sum_base/den_sum_base
    对应 FunctionMathUtil.caleRatioFluctuationValue
    需要提供分子/分母的 measure code（components 参数）。

数据依赖：
  - ADDITIVE/DEDUPLICATIVE：result 中须含 {measure}_{pop}_origin_value 列；
    需要一次无 group_by 的汇总查询作为 total_result。
  - RATIO：result 中须含 numerator、denominator 及其 _origin_value 列；
    total_result 同样需要上述四列。
  调用方通过 build_fluctuation_pops 扩展 pops 列表后传给 standard query。

列命名规则（与 server FunctionEnum.DIM_FLUCTUATION 一致）：
  {measureCode}_{pop}_fluctuation_value
"""

from __future__ import annotations
import re


def _to_float(v) -> float | None:
    if v is None or str(v).strip() in ("", "null", "NULL", "None"):
        return None
    s = str(v).strip().replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _sign(x: float) -> float:
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def _calc_additive(value: float | None, base: float | None,
                   total_current: float | None, total_base: float | None) -> float | None:
    """
    可加型波动贡献：contribution = (value - base) / (total_current - total_base)
    对应 FunctionMathUtil.caleDimFluctuationValue
    """
    if any(v is None for v in (value, base, total_current, total_base)):
        return None
    total_change = total_current - total_base
    if total_change == 0:
        return None
    return round((value - base) / total_change, 6)


def _calc_deduplicative(value: float | None, base: float | None,
                        total_current: float | None, total_base: float | None,
                        all_changes_abs_sum: float | None) -> float | None:
    """
    去重型波动贡献：contribution = (value - base) * sign(total_change) / all_changes_abs_sum
    对应 FunctionMathUtil.caleDeductiveDimFluctuationValue
    """
    if any(v is None for v in (value, base, total_current, total_base, all_changes_abs_sum)):
        return None
    total_change = total_current - total_base
    if total_change == 0 or all_changes_abs_sum == 0:
        return None
    return round((value - base) * _sign(total_change) / all_changes_abs_sum, 6)


def _calc_ratio(
    num_i: float | None, num_base_i: float | None,
    den_i: float | None, den_base_i: float | None,
    num_sum_cur: float | None, num_sum_base: float | None,
    den_sum_cur: float | None, den_sum_base: float | None,
) -> float | None:
    """
    比值型波动贡献 = (趋势贡献 + 结构贡献) / total_ratio_change
    对应 FunctionMathUtil.caleRatioFluctuationValue
    """
    if any(v is None for v in (num_i, num_base_i, den_i, den_base_i,
                                num_sum_cur, num_sum_base, den_sum_cur, den_sum_base)):
        return None
    if 0 in (den_i, den_base_i, den_sum_cur, den_sum_base):
        return None

    ratio_sum_cur = num_sum_cur / den_sum_cur
    ratio_sum_base = num_sum_base / den_sum_base
    total_ratio_change = ratio_sum_cur - ratio_sum_base
    if total_ratio_change == 0:
        return None

    ratio_i = num_i / den_i
    ratio_base_i = num_base_i / den_base_i

    weight_base = den_base_i / den_sum_base
    weight_cur = den_i / den_sum_cur

    trend = (ratio_i - ratio_base_i) * weight_base
    structure = (weight_cur - weight_base) * (ratio_i - ratio_sum_base)
    return round((trend + structure) / total_ratio_change, 6)


def calc_fluctuation_ratio(
    result: dict,
    total_result: dict,
    ratio_measures: list[str],
    pops: list[str],
    components: dict[str, tuple[str, str]],
) -> dict:
    """
    比值型波动贡献计算，在 result 中插入 {ratio_measure}_{pop}_fluctuation_value 列。

    参数：
        result        : 含分子/分母当期值及其 {pop}_origin_value 基期值的查询结果
        total_result  : 无 group_by 的汇总查询结果（同 measures/pops）
        ratio_measures: 比值型指标 code 列表
        pops          : 基期类型列表，如 ["dod"]
        components    : 分子分母映射，格式 {ratio_code: (numerator_code, denominator_code)}
                        例：{"visit_order_rate": ("fin_ord_num", "visit_user_num")}
    """
    total_row = total_result["rows"][0] if total_result.get("rows") else {}

    for ratio_measure in ratio_measures:
        if ratio_measure not in components:
            continue
        num_code, den_code = components[ratio_measure]

        for pop in pops:
            num_base_col = f"{num_code}_{pop}_origin_value"
            den_base_col = f"{den_code}_{pop}_origin_value"
            out_col = f"{ratio_measure}_{pop}_fluctuation_value"

            num_sum_cur = _to_float(total_row.get(num_code))
            num_sum_base = _to_float(total_row.get(num_base_col))
            den_sum_cur = _to_float(total_row.get(den_code))
            den_sum_base = _to_float(total_row.get(den_base_col))

            for row in result["rows"]:
                row[out_col] = _calc_ratio(
                    _to_float(row.get(num_code)),
                    _to_float(row.get(num_base_col)),
                    _to_float(row.get(den_code)),
                    _to_float(row.get(den_base_col)),
                    num_sum_cur, num_sum_base, den_sum_cur, den_sum_base,
                )

    # 列顺序：每个 ratio_measure 列后追加各 pop 的贡献度列
    new_columns = []
    for col in result["columns"]:
        new_columns.append(col)
        if col in ratio_measures:
            for pop in pops:
                new_columns.append(f"{col}_{pop}_fluctuation_value")
    result["columns"] = new_columns
    return result


def calc_fluctuation(
    result: dict,
    total_result: dict,
    fluctuation_measures: list[str],
    pops: list[str],
    mode: str = "additive",
    components: dict[str, tuple[str, str]] | None = None,
) -> dict:
    """
    计算波动贡献，在 result 中为每个 (measure, pop) 组合插入贡献度列。

    参数：
        result              : standard query 返回值，columns 中须含
                              {measure} 和 {measure}_{pop}_origin_value 两列
        total_result        : 无 group_by 的汇总查询结果（同 measures/pops）
        fluctuation_measures: 需要计算贡献度的指标 code 列表
        pops                : 基期类型列表，如 ["dod", "wow"]
        mode                : "additive"（默认）/ "deduplicative" / "ratio"
        components          : mode="ratio" 时必填，格式见 calc_fluctuation_ratio

    返回：
        修改后的 result（in-place 修改 rows/columns，同时返回以便链式调用）
    """
    if mode == "ratio":
        return calc_fluctuation_ratio(
            result, total_result, fluctuation_measures, pops, components or {}
        )

    rows = result["rows"]
    total_row = total_result["rows"][0] if total_result.get("rows") else {}

    for measure in fluctuation_measures:
        for pop in pops:
            base_col = f"{measure}_{pop}_origin_value"
            out_col = f"{measure}_{pop}_fluctuation_value"

            total_current = _to_float(total_row.get(measure))
            total_base = _to_float(total_row.get(base_col))

            # 去重型需要先算所有维度变化量之和
            all_changes_abs_sum = None
            if mode == "deduplicative":
                changes_sum = 0.0
                for row in rows:
                    v = _to_float(row.get(measure))
                    b = _to_float(row.get(base_col))
                    if v is not None and b is not None:
                        changes_sum += (v - b)
                all_changes_abs_sum = abs(changes_sum)

            for row in rows:
                value = _to_float(row.get(measure))
                base = _to_float(row.get(base_col))

                if mode == "deduplicative":
                    row[out_col] = _calc_deduplicative(
                        value, base, total_current, total_base, all_changes_abs_sum
                    )
                else:
                    row[out_col] = _calc_additive(value, base, total_current, total_base)

    # 重建列顺序：每个 measure 列后紧跟其各 pop 的贡献度列
    new_columns = []
    for col in result["columns"]:
        new_columns.append(col)
        if col in fluctuation_measures:
            for pop in pops:
                new_columns.append(f"{col}_{pop}_fluctuation_value")
    result["columns"] = new_columns
    return result


def get_fluctuation_type(measure: dict) -> str:
    """
    从 list_measures() 返回的指标元数据中判断波动计算类型，对齐 server MeasureTagEnum.getFluctuationCalculationType()。

    判断优先级（与 server 逻辑一致）：
      1. tags 字段含 RATIO/比值型        → "ratio"
      2. tags 字段含 DEDUPLICATIVE/去重型 → "deduplicative"
      3. formula 字段含两个 ${id} 模式   → "ratio"（兜底：formula 存在说明是比值型）
      4. 其他                            → "additive"

    参数：
        measure: client.list_measures() 返回的单条指标 dict

    返回：
        "additive" | "deduplicative" | "ratio"
    """
    # 检查 tags 字段（API 可能返回 list 或 comma-separated string）
    raw_tags = measure.get("tags") or measure.get("measureTag") or []
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    for tag in raw_tags:
        t = tag.upper()
        if t in ("RATIO", "比值型"):
            return "ratio"
        if t in ("DEDUPLICATIVE", "去重型"):
            return "deduplicative"

    # 兜底：formula 存在且含两个 ${id} 模式 → 比值型
    formula = measure.get("formula") or ""
    if len(re.findall(r'\$\{(\d+)\}', formula)) == 2:
        return "ratio"

    return "additive"


def resolve_ratio_components(
    measures_meta: list[dict],
    ratio_codes: list[str],
) -> dict[str, tuple[str, str]]:
    """
    从 list_measures 返回的元数据中自动解析比值型指标的分子/分母 code。

    服务端逻辑（MeasureTypeService.getRatioMeasureListComponents）：
      1. 读取 measure.formula，格式为 "${num_id} / ${den_id}"（ID 为整数）
      2. 用 ID 反查 measureIdMap 得到分子/分母的 code

    参数：
        measures_meta: client.list_measures() 的返回值（含 id/kpiId、code、formula 字段）
        ratio_codes:   需要解析的比值型指标 code 列表

    返回：
        {ratio_code: (numerator_code, denominator_code)}
        无法解析的指标不会出现在结果中
    """
    id_map: dict[int, dict] = {}
    code_map: dict[str, dict] = {}
    for m in measures_meta:
        mid = m.get("id") or m.get("kpiId")
        if mid is not None:
            id_map[int(mid)] = m
        code = m.get("code")
        if code:
            code_map[code] = m

    components: dict[str, tuple[str, str]] = {}
    for ratio_code in ratio_codes:
        measure = code_map.get(ratio_code)
        if not measure:
            continue
        formula = measure.get("formula") or ""
        parts = [int(x) for x in re.findall(r'\$\{(\d+)\}', formula)]
        if len(parts) != 2:
            continue
        num_m = id_map.get(parts[0])
        den_m = id_map.get(parts[1])
        if num_m and den_m and num_m.get("code") and den_m.get("code"):
            components[ratio_code] = (num_m["code"], den_m["code"])

    return components


def infer_pop_from_date(date_range: str) -> str:
    """
    从日期范围推断波动贡献的基期类型，对应 server DimFluctuationProcessor.getDimFluctuationPopByDateFilters。
      单日 / 日粒度 → dod
      跨 7 天      → wow
      跨月（≥28天）→ mom
      其他          → dod（保底）
    """
    if not date_range:
        return "dod"
    parts = date_range.split("~")
    if len(parts) != 2:
        return "dod"
    start, end = parts[0].strip(), parts[1].strip()
    if start == end:
        return "dod"
    try:
        from datetime import datetime
        d_start = datetime.strptime(start, "%Y%m%d")
        d_end = datetime.strptime(end, "%Y%m%d")
        diff = (d_end - d_start).days
        if diff >= 28:
            return "mom"
        if diff >= 6:
            return "wow"
    except ValueError:
        pass
    return "dod"


def shift_date_range(date_range: str, pop: str) -> str:
    """
    将日期范围按基期类型向前移动，得到基期的日期范围。
      dod → -1 天
      wow → -7 天
      mom → -30 天（近似，与 server 行为对齐）

    例：shift_date_range('20260528~20260528', 'dod') → '20260527~20260527'
    """
    from datetime import datetime, timedelta
    shifts = {"dod": 1, "wow": 7, "mom": 30}
    days = shifts.get(pop, 1)
    parts = date_range.split("~")
    if len(parts) != 2:
        return date_range
    fmt = "%Y%m%d"
    try:
        d_start = datetime.strptime(parts[0].strip(), fmt) - timedelta(days=days)
        d_end = datetime.strptime(parts[1].strip(), fmt) - timedelta(days=days)
        return f"{d_start.strftime(fmt)}~{d_end.strftime(fmt)}"
    except ValueError:
        return date_range


def merge_base_period(
    result: dict,
    base_result: dict,
    measures: list[str],
    pop: str,
    group_by: list[str] | None = None,
) -> dict:
    """
    将基期查询结果合并到 result 中，以 {measure}_{pop}_origin_value 列的形式写入每行。
    通过 group_by 维度列进行行级匹配；若 group_by 为空则按行顺序对齐。

    对应 server DimFluctuationProcessor 中追加 _origin_value 列的逻辑。
    """
    base_col_suffix = f"_{pop}_origin_value"

    if group_by:
        # 构建 (维度值组合) -> 基期行 的索引
        base_index: dict[tuple, dict] = {}
        for row in base_result.get("rows", []):
            key = tuple(str(row.get(g, "")) for g in group_by)
            base_index[key] = row

        for row in result.get("rows", []):
            key = tuple(str(row.get(g, "")) for g in group_by)
            base_row = base_index.get(key, {})
            for m in measures:
                row[f"{m}{base_col_suffix}"] = base_row.get(m)
    else:
        # 按顺序对齐
        base_rows = base_result.get("rows", [])
        for i, row in enumerate(result.get("rows", [])):
            base_row = base_rows[i] if i < len(base_rows) else {}
            for m in measures:
                row[f"{m}{base_col_suffix}"] = base_row.get(m)

    # 同步更新 columns（供 calc_fluctuation 读取，不展示给用户）
    if "columns" in result:
        existing = set(result["columns"])
        for m in measures:
            col = f"{m}{base_col_suffix}"
            if col not in existing:
                result["columns"].append(col)

    return result


def build_fluctuation_pops(pops: list[str]) -> list[str]:
    """
    将用户指定的 pops（如 ["dod", "wow"]）扩展为查询所需的完整 pops 列表，
    追加 {pop}_origin_value 变体以获取基期原始值。
    对应 server DimFluctuationProcessor 中 newPops 的构建逻辑。
    """
    extended = []
    for pop in pops:
        extended.append(pop)
        origin_col = f"{pop}_origin_value"
        if origin_col not in extended:
            extended.append(origin_col)
    return extended
