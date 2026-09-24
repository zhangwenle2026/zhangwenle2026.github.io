# operators — 客户端算子包
# 每个模块对应 server 侧一个 FunctionExecutor，复现其计算逻辑
from .proportion import calc_proportion
from .gini import calc_gini
from .fluctuation import (
    calc_fluctuation, calc_fluctuation_ratio, resolve_ratio_components,
    infer_pop_from_date, shift_date_range, merge_base_period, get_fluctuation_type,
)

__all__ = [
    "calc_proportion", "calc_gini", "calc_fluctuation", "calc_fluctuation_ratio",
    "resolve_ratio_components", "infer_pop_from_date",
    "shift_date_range", "merge_base_period", "get_fluctuation_type",
]
