#!/usr/bin/env python3
"""
cxr_fetch.py — CXR 访购率诊断并发取数脚本

并发查询 CXR 分析所需的全部路径数据，输出 JSON 结果。
底层复用 keeta-data-query skill 的 KeetaClient，无需额外鉴权。

用法：
  python3 cxr_fetch.py --region QA --date 20260419 --compare 20260412
  python3 cxr_fetch.py --region SA --date 20260405~20260411 --compare 20260329~20260404
  python3 cxr_fetch.py --region HK --date 20260419 --compare 20260418  # DoD
  python3 cxr_fetch.py --region QA --date 20260419 --compare 20260412 --mode user  # 用户口径

输出：
  JSON 到 stdout，包含所有路径数据（本期 + 对比期）
  使用 --out <file> 保存到文件

错误处理：
  单路径查询失败不中断整体，结果中该路径数据为 null + error 字段
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# ── 把 keeta-data-query 的 scripts 目录加入 path ─────────────────────────────
_SKILL_DIR = Path(__file__).resolve().parent.parent.parent  # ~/.openclaw/skills/
_KDATA_SCRIPTS = _SKILL_DIR / "keeta-data-query" / "scripts"
if str(_KDATA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KDATA_SCRIPTS))

try:
    from core.keeta_client import KeetaClient
except ImportError as e:
    KeetaClient = None  # type: ignore[assignment]
    _KEETA_CLIENT_IMPORT_ERROR = e
else:
    _KEETA_CLIENT_IMPORT_ERROR = None

# ── 埋点模块（同目录，降级保护）─────────────────────────────────────────────
try:
    from skill_tracker import report_script
except ImportError:
    def report_script(*args, **kwargs): pass  # 埋点不可用时静默跳过


def _get_keeta_client_cls():
    """Lazy-load KeetaClient so --help/--dry-run do not require runtime deps."""
    if KeetaClient is None:
        print(f"[cxr_fetch] 无法导入 KeetaClient: {_KEETA_CLIENT_IMPORT_ERROR}", file=sys.stderr)
        print(f"[cxr_fetch] 请确认 keeta-data-query skill 已安装，路径: {_KDATA_SCRIPTS}", file=sys.stderr)
        raise SystemExit(1)
    return KeetaClient


def _format_for_log(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _report_script_node(
    node: str,
    params: dict,
    output: Any,
    cost_ms: int,
    success: bool = True,
    error_msg: str = "",
) -> None:
    payload = {"node": node, **params}
    report_script(
        "",
        _format_for_log(payload),
        _format_for_log(output),
        cost_ms,
        success,
        error_msg,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 查询任务定义
# ══════════════════════════════════════════════════════════════════════════════

def _build_tasks(region: str, date_cur: str, date_cmp: str, mode: str = "device") -> list[dict]:
    """
    返回所有并发查询任务列表。
    每个任务：{name, dataset, measures, group_by, order_by, page_size, dates: [cur, cmp]}
    mode: "device"（设备访购率，默认）| "user"（用户访购率）
    """
    tasks = []

    # ── Path F：大盘核心指标 ─────────────────────────────────────────────
    if mode == "user":
        tasks.append({
            "name": "base",
            "path": "base",
            "dataset": "60051108",
            "measures": [
                "davg_visit2ord_rate",         # 用户访购率
                "davg_visit_usr_num",          # 日均访问用户数
                "davg_fin_user_num",           # 日均交易用户数
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        })
        # 供需指标仍从 60051984 取
        tasks.append({
            "name": "base_supply",
            "path": "base",
            "dataset": "60051984",
            "measures": [
                "davg_open_shop_num",              # 营业商家数
                "davg_shop_avg_open_dura",         # 店均营业时长
                "davg_reduced_range_merchants_rate",  # 爆单缩减范围商家率
                "to_c_eta_avg_min",            # C端展示ETA均值（分钟）
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        })
    else:
        tasks.append({
            "name": "base",
            "path": "base",
            "dataset": "60051984",
            "measures": [
                "davg_visit_txn_ratio",       # CXR 访购率
                "davg_dau",                    # DAU
                "davg_fin_ord_uv",             # 交易设备数
                "davg_open_shop_num",              # 营业商家数
                "davg_shop_avg_open_dura",         # 店均营业时长
                "davg_reduced_range_merchants_rate",  # 爆单缩减范围商家率
                "to_c_eta_avg_min",            # C端展示ETA均值（分钟）
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        })

    tasks += [
        # ── Path 2：补贴价格 ─────────────────────────────────────────────────
        {
            "name": "subsidy",
            "path": "path2",
            "dataset": "60048561",
            "measures": [
                "actual_disc_ratio",             # 整体补贴率
                "actual_mt_charge_amt_ratio",    # 美补率
                "actual_c_mt_charge_amt_ratio",  # C补率（用户感知最强）
                "actual_shop_charge_amt_ratio",  # 商补率
                "actual_pay_no_tip_gmv",         # 实付交易额（总量，供贡献度基准）
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # ── Path 3：流量结构 ──────────────────────────────────────────────────
        {
            "name": "traffic_structure",
            "path": "path3",
            "dataset": "60051108" if mode == "user" else "60051984",
            "measures": [
                "davg_visit2ord_rate",   # 用户访购率
                "davg_visit_usr_num",    # 访问用户数
            ] if mode == "user" else [
                "davg_visit_txn_ratio",  # 分层 CXR
                "davg_dau",              # 分层 DAU
            ],
            "group_by": ["upto_yesterday_user_layers_name"] if mode == "user" else ["user_finord_type_name"],
            "order_by": None,
            "page_size": 20,
        },
        # ── Path 4：模块 CXR（资源位分发） ───────────────────────────────────
        {
            "name": "module_cxr",
            "path": "path4",
            "dataset": "62059514",
            "measures": [
                "davg_cxr_uv",             # 模块 CXR
                "davg_module_exposure_uv", # 模块曝光 UV
                "davg_module_click_uv",    # 模块点击 UV
                "davg_ctr_uv",             # 模块 CTR
            ],
            "group_by": ["first_ad_position_name"],
            "order_by": {"davg_module_exposure_uv": "DESC"},
            "page_size": 30,
        },
        # ── Path 5：用户路径漏斗 ─────────────────────────────────────────────
        {
            "name": "funnel",
            "path": "path5",
            "dataset": "60051108" if mode == "user" else "60051984",
            "measures": [
                "davg_visit_shop_cvr",                  # DAU→进店（user_id）
                "davg_visit_shop_submit_page_cvr",      # 进店→提单页（user_id）
                "davg_submit_page_submit_cvr",          # 提单页→提单（user_id）
                "davg_submit_pay_cvr",                  # 提单→支付（user_id）
                "davg_pay_fin_cvr",                     # 支付→完单（user_id）
            ] if mode == "user" else [
                "davg_device_visit_shop_cvr",           # DAU→进店
                "davg_visit_shop_submit_page_uuid_cvr", # 进店→提单页
                "davg_submit_page_submit_uuid_cvr",     # 提单页→提单
                "davg_device_submit_pay_cvr",           # 提单→支付
                "davg_pay_fin_union_cvr",               # 支付→完单
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # ── Path 1 补充：搜索质量 ─────────────────────────────────────────────
        # 注意：置休率/超区率/无精准结果率/搜索CTR 已在 search_funnel task 中取全量
        # 此处只取 search_funnel 未覆盖的指标
        {
            "name": "search",
            "path": "path1_search",
            "dataset": "60052643",
            "measures": [
                "search_no_result_rate_new",   # 搜索无结果率（供给因果链首环，Path 1 必查）
                "daily_search_no_result_rate", # 日均搜索无结果率
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # ── Path 1A：需求质量（渠道拆分）─ 逐天降级 ─────────────────────────
        # 62055197 周区间+group_by 超时，逐天查再 SUM 聚合（可累加）
        {
            "name": "demand_channel",
            "path": "path1a",
            "dataset": "62055197",
            "measures": [
                "visit_usr_num",   # 访问用户数
                "fin_usr_num",     # 交易用户数
            ] if mode == "user" else [
                "app_uv",       # DAU
                "fin_ord_uv",   # 交易设备数
            ],
            "group_by": ["primary_access_channel_code", "secondary_visit_channel_code"],
            "order_by": {"visit_usr_num": "DESC"} if mode == "user" else {"app_uv": "DESC"},
            "page_size": 200,
            "day_by_day": True,
        },
        # ── Path 2 补充：补贴结构-营销类型 ───────────────────────────────────
        {
            "name": "subsidy_sales_type",
            "path": "path2_structure",
            "dataset": "60048561",
            "measures": [
                "actual_disc_ratio",
                "actual_mt_charge_amt_ratio",
                "actual_c_mt_charge_amt_ratio",
                "actual_shop_charge_amt_ratio",
                "actual_pay_no_tip_gmv",         # 实付交易额（贡献度分母）
            ],
            "group_by": ["sales_type_name"],
            "order_by": None,
            "page_size": 30,
        },
        # ── Path 2 补充：补贴结构-生命周期 ───────────────────────────────────
        {
            "name": "subsidy_lifecycle",
            "path": "path2_structure",
            "dataset": "60048561",
            "measures": [
                "actual_disc_ratio",
                "actual_mt_charge_amt_ratio",
                "actual_c_mt_charge_amt_ratio",
                "actual_shop_charge_amt_ratio",
                "actual_pay_no_tip_gmv",         # 实付交易额（贡献度分母）
            ],
            "group_by": ["lifecycle_global_name"],
            "order_by": None,
            "page_size": 30,
        },
        # ── Path 2 补充：补贴结构-价格带 ─────────────────────────────────────
        {
            "name": "subsidy_price_range",
            "path": "path2_structure",
            "dataset": "60048561",
            "measures": [
                "actual_disc_ratio",
                "actual_mt_charge_amt_ratio",
                "actual_c_mt_charge_amt_ratio",
                "actual_shop_charge_amt_ratio",
                "actual_pay_no_tip_gmv",         # 实付交易额（贡献度分母）
            ],
            "group_by": ["actual_price_range_name"],
            "order_by": None,
            "page_size": 30,
        },
        # ── Path 2 价格信号：实付配送费 / AOV（Fix D）─────────────────
        {
            "name": "price_signal",
            "path": "path2_price",
            "dataset": "60051108",
            "measures": [
                "actua_delivery_fee_per_order",   # 实付单均配送费（拼写就是 actua）
                "oavg_fin_actual_amt",            # 实付单均价/AOV
                "oavg_orig_dlvr_fee",             # 原价单均配送费
                "oavg_charge_fee",                # 单均补贴金额
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # ── Path 3 补充：设备类型维度 ────────────────────────────────────────
        {
            "name": "traffic_device",
            "path": "path3_device",
            "dataset": "60051108" if mode == "user" else "60051984",
            "measures": [
                "davg_visit2ord_rate",
                "davg_visit_usr_num",
            ] if mode == "user" else [
                "davg_visit_txn_ratio",
                "davg_dau",
            ],
            "group_by": ["os"],
            "order_by": None,
            "page_size": 20,
        },
        # ── Path 3 补充：语言维度 ────────────────────────────────────────────
        # device 用 device_language_code(60051984)；user 用 user_app_language_code(60051108)
    ]
    if mode == "user":
        tasks.append({
            "name": "traffic_language",
            "path": "path3_language",
            "dataset": "60051108",
            "measures": [
                "davg_visit2ord_rate",
                "davg_visit_usr_num",
            ],
            "group_by": ["user_app_language_code"],
            "order_by": {"davg_visit_usr_num": "DESC"},
            "page_size": 20,
        })
    else:
        tasks.append({
            "name": "traffic_language",
            "path": "path3_language",
            "dataset": "60051984",
            "measures": [
                "davg_visit_txn_ratio",
                "davg_dau",
            ],
            "group_by": ["device_language_code"],
            "order_by": {"davg_dau": "DESC"},
            "page_size": 20,
        })

    # ── Path 3 补充：区域等级维度（仅 BR）────────────────────────────────
    # tier_name 仅在 60051108 存在，设备口径也统一用 60051108 取此维度
    if region == "BR":
        tasks.append({
            "name": "traffic_tier",
            "path": "path3_tier",
            "dataset": "60051108",
            "measures": [
                "davg_visit2ord_rate",
                "davg_visit_usr_num",
            ],
            "group_by": ["tier_name"],
            "order_by": {"davg_visit_usr_num": "DESC"},
            "page_size": 20,
        })

    # ── Path 3 补充：业务城市维度（仅 AE/SA）─────────────────────────────
    if region in ("AE", "SA"):
        tasks.append({
            "name": "traffic_city",
            "path": "path3_city",
            "dataset": "60051108" if mode == "user" else "60051984",
            "measures": [
                "davg_visit2ord_rate",
                "davg_visit_usr_num",
            ] if mode == "user" else [
                "davg_visit_txn_ratio",
                "davg_dau",
            ],
            "group_by": ["op_city_name"],
            "order_by": {"davg_visit_usr_num": "DESC"} if mode == "user" else {"davg_dau": "DESC"},
            "page_size": 20,
        })

    tasks += [
        # ── Path 4.2 搜索四层漏斗 ────────────────────────────────────────
        {
            "name": "search_funnel",
            "path": "path4_search_funnel",
            "dataset": "60052643",
            "measures": [
                "search_no_result_rate_new",           # 无结果率
                "search_no_precise_result_rate",       # 无精准结果率
                "search_precision_shop_not_ava_rate",  # 置休率
                "search_precision_out_of_range_rate",  # 超区率
                "davg_search_result_click_to_exposure_ratio",  # 搜索结果页CTR
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # ── Path 4.3 金刚分品类 ── 暂时禁用（首轮） ──────────────────────
        # 62059514 按 second_ad_position_name 查周区间超时（单维度也不稳定）；
        # davg_* 指标逐天 SUM 聚合无意义（日均值不可累加）。
        # 放到 follow-up 下钻阶段，用单日查询实现。
    ]

    # ── Path 3 补充：生命周期维度（仅 user 模式）────────────────────────
    if mode == "user":
        tasks.append({
            "name": "traffic_lifecycle",
            "path": "path3_lifecycle",
            "dataset": "60051108",
            "measures": [
                "davg_visit2ord_rate",
                "davg_visit_usr_num",
            ],
            "group_by": ["lifecycle_global_name"],
            "order_by": None,
            "page_size": 20,
        })

    return tasks


# ══════════════════════════════════════════════════════════════════════════════
# 下钻查询任务定义
# ══════════════════════════════════════════════════════════════════════════════

def _build_drilldown_tasks(region: str, drilldown_mode: str) -> list[dict]:
    """
    返回下钻查询任务列表，按 drilldown_mode 过滤。
    drilldown_mode: 'store_to_order' | 'order_to_submit' | 'all'
    task dict 格式与 _build_tasks 完全一致。
    """
    store_to_order_tasks = [
        # 1. 进店→提单页 按商家类型
        {
            "name": "drilldown_s2o_merchant_type",
            "path": "drilldown_s2o",
            "dataset": "60051108",
            "measures": [
                "davg_visit_shop_submit_page_uuid_cvr",
                "davg_enter_merchant_union_id",  # 日均进店UV（流量量级参考）
            ],
            "group_by": ["shop_type_name"],
            "order_by": {"davg_enter_merchant_union_id": "DESC"},
            "page_size": 50,
        },
        # 2. 进店→提单页 按商家品类
        {
            "name": "drilldown_s2o_merchant_category",
            "path": "drilldown_s2o",
            "dataset": "60051108",
            "measures": [
                "davg_visit_shop_submit_page_uuid_cvr",
                "davg_enter_merchant_union_id",  # 日均进店UV（流量量级参考）
            ],
            "group_by": ["second_shop_category_name"],
            "order_by": {"davg_enter_merchant_union_id": "DESC"},
            "page_size": 50,
        },
        # 3. 进店→提单页 按用户分层
        {
            "name": "drilldown_s2o_user_segment",
            "path": "drilldown_s2o",
            "dataset": "60051108",
            "measures": [
                "davg_visit_shop_submit_page_uuid_cvr",
                "davg_enter_merchant_union_id",  # 日均进店UV（流量量级参考）
            ],
            "group_by": ["uuid_layers_3_name"],
            "order_by": {"davg_enter_merchant_union_id": "DESC"},
            "page_size": 50,
        },
        # 4. 进店→加购→提单页 漏斗拆分（无分组）
        {
            "name": "drilldown_s2o_add_to_cart",
            "path": "drilldown_s2o",
            "dataset": "60051108",
            "measures": [
                "davg_shop_entry_add_to_cart_cvr",         # 进店→店内加购转化率（Uuid）
                "davg_add_to_cart_submit_page_cvr",        # 店内加购→提单页转化率（Uuid）
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # 5. 店内优惠专区曝光指标（无分组）
        {
            "name": "drilldown_s2o_promo_pv",
            "path": "drilldown_s2o",
            "dataset": "60051108",
            "measures": [
                "davg_discount_spu_shop_coverage",                              # 折扣菜活动生效营业商家覆盖率
                "davg_in_store_free_delivery_deals_zone_impression_pv_rate",    # 免运优惠专区曝光PV占比
                "davg_in_store_coupon_deals_zone_impression_pv_rate",           # 券优惠专区曝光PV占比
                "davg_in_store_discount_dishes_deals_zone_impression_pv_rate",  # 折扣菜优惠专区曝光PV占比
                "davg_in_store_free_delivery_deals_zone_merchant_exposure_rate",# 免运优惠专区曝光商家占比
                "davg_in_store_coupon_deals_zone_merchant_expose_rate",         # 券优惠专区曝光商家占比
                "davg_in_store_discount_dishes_deals_zone_merchant_expose_rate",# 折扣菜优惠专区曝光商家占比
                "davg_in_store_store_campaign_deals_zone_impression_pv_rate",   # 门店活动优惠专区曝光PV占比
                "davg_in_store_store_campaign_deals_zone_merchant_expose_rate", # 门店活动优惠专区曝光商家占比
                "davg_in_store_promotion_zone_expose_pv",                       # 店内优惠专区曝光PV总量（前置判断用）
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # 6. 商家入口进店UV + 支付UV（按 page_name + resource_name，逐天查询）
        {
            "name": "drilldown_s2o_entrance",
            "path": "drilldown_s2o_entrance",
            "dataset": "60048404",
            "measures": [
                "davg_shop_entry_visit_uv",    # 日均商家入口进店UV
                "davg_shop_entry_payment_uv",  # 日均商家入口支付UV
            ],
            "group_by": ["ad_position_page_name", "ad_position_name"],
            "order_by": {"davg_shop_entry_visit_uv": "DESC"},
            "page_size": 100,
            "day_by_day": True,
        },
    ]

    order_to_submit_tasks = [
        # 7. 提单页→提单 按商家类型
        {
            "name": "drilldown_o2s_merchant_type",
            "path": "drilldown_o2s",
            "dataset": "60051108",
            "measures": [
                "davg_submit_page_submit_uuid_cvr",
                "davg_enter_merchant_union_id",  # 日均进店UV（流量量级参考）
            ],
            "group_by": ["shop_type_name"],
            "order_by": {"davg_enter_merchant_union_id": "DESC"},
            "page_size": 50,
        },
        # 8. 提单页→提单 按商家品类
        {
            "name": "drilldown_o2s_merchant_category",
            "path": "drilldown_o2s",
            "dataset": "60051108",
            "measures": [
                "davg_submit_page_submit_uuid_cvr",
                "davg_enter_merchant_union_id",  # 日均进店UV（流量量级参考）
            ],
            "group_by": ["second_shop_category_name"],
            "order_by": {"davg_enter_merchant_union_id": "DESC"},
            "page_size": 50,
        },
        # 9. 提单页→提单 按用户分层
        {
            "name": "drilldown_o2s_user_segment",
            "path": "drilldown_o2s",
            "dataset": "60051108",
            "measures": [
                "davg_submit_page_submit_uuid_cvr",
                "davg_enter_merchant_union_id",  # 日均进店UV（流量量级参考）
            ],
            "group_by": ["uuid_layers_3_name"],
            "order_by": {"davg_enter_merchant_union_id": "DESC"},
            "page_size": 50,
        },
        # 10. 提单页质量指标（无分组）
        {
            "name": "drilldown_o2s_submit_page_quality",
            "path": "drilldown_o2s",
            "dataset": "60051108",
            "measures": [
                "davg_sub_available_coupon_pv_ratio",                   # 提单页可用券占比
                "davg_sub_unavailable_coupon_pv_ratio",                 # 提单页无券占比
                "davg_sub_has_coupon_unavailable_pv_ratio",             # 提单页有券但不可用占比
                "davg_discount_amount_per_single_ord_sub_page_expose",  # 日均单次提单页曝光优惠金额
                "davg_in_store_free_delivery_deals_zone_impression_pv_rate", # 免运优惠专区曝光PV占比（复用）
                "davg_prop_of_ord_sub_page_expose_free_shipping_ord",          # 提单页订单免运曝光PV占比
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # 11. 支付→完单：取消率
        {
            "name": "drilldown_o2s_cancel_rate",
            "path": "drilldown_o2s",
            "dataset": "60051108",
            "measures": [
                "post_payment_order_cancellation_rate",  # 支付后取消率
            ],
            "group_by": None,
            "order_by": None,
            "page_size": 10,
        },
        # 12. 支付→完单：取消原因拆分
        {
            "name": "drilldown_o2s_cancel_reason",
            "path": "drilldown_o2s",
            "dataset": "60051108",
            "measures": [
                "pay_cancel_ord_num",  # 支付后取消单量
            ],
            "group_by": ["order_cancellation_reason"],
            "order_by": {"pay_cancel_ord_num": "DESC"},
            "page_size": 20,
        },
    ]

    if drilldown_mode == "store_to_order":
        return store_to_order_tasks
    elif drilldown_mode == "order_to_submit":
        return order_to_submit_tasks
    elif drilldown_mode == "all":
        return store_to_order_tasks + order_to_submit_tasks
    else:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# ── 数据集 ID → 中文名称（运行时查 API）──────────────────────────────────────
_dataset_name_cache: dict[str, str] = {}


def _get_dataset_name(dataset_id: str) -> str:
    """通过起源 API 获取数据集中文名称，失败时返回 ID 本身。"""
    ds_id = str(dataset_id)
    if ds_id in _dataset_name_cache:
        return _dataset_name_cache[ds_id]
    try:
        from moshu.mtcli_resources import get_dataset_info
        infos = get_dataset_info([int(ds_id)])
        if infos:
            name = infos[0].get("name") or infos[0].get("subjectName") or ds_id
            _dataset_name_cache[ds_id] = name
            return name
    except Exception as e:
        print(f"[cxr_fetch] 查询数据集名称失败({ds_id}): {e}", file=sys.stderr)
    _dataset_name_cache[ds_id] = ds_id
    return ds_id


# 单任务执行（同步，供线程池调用）
# ══════════════════════════════════════════════════════════════════════════════

def _run_one(client: KeetaClient, task: dict, date: str, label: str, region: str,
             max_retries: int = 1) -> dict:
    """执行单个查询，返回 {name, label, date, columns, rows, error}。超时自动重试。"""
    last_error = None
    t0 = time.time()
    for attempt in range(1 + max_retries):
        try:
            result = client.query(
                dataset_id=task["dataset"],
                measures=task["measures"],
                date_range=date,
                region=region,
                group_by=task["group_by"],
                order_by=task["order_by"],
                page_size=task.get("page_size", 1000),
            )
            elapsed = round(time.time() - t0, 2)
            # tracking: scripts/cxr_fetch.py::_run_one::skill-script
            _report_script_node(
                "scripts/cxr_fetch.py::_run_one::skill-script",
                {
                    "task": task["name"],
                    "dataset": task["dataset"],
                    "date": date,
                    "label": label,
                    "region": region,
                    "attempt": attempt,
                },
                result,
                int(elapsed * 1000),
                True,
                "",
            )
            return {
                "name": task["name"],
                "path": task["path"],
                "label": label,
                "date": date,
                "dataset": task["dataset"],
                "columns": result.get("columns", []),
                "rows": result.get("rows", []),
                "total": result.get("total", 0),
                "elapsed_s": elapsed,
                "error": None,
            }
        except Exception as e:
            last_error = e
            if attempt < max_retries and "超时" in str(e):
                time.sleep(1)  # brief pause before retry
                continue
            break
    elapsed = round(time.time() - t0, 2)
    # tracking: scripts/cxr_fetch.py::_run_one::skill-script
    _report_script_node(
        "scripts/cxr_fetch.py::_run_one::skill-script",
        {
            "task": task["name"],
            "dataset": task["dataset"],
            "date": date,
            "label": label,
            "region": region,
        },
        {},
        int(elapsed * 1000),
        False,
        str(last_error),
    )
    # 检测数据集权限错误
    _perm_keywords = ("no permission", "NO_PERMISSION", "no_permission", "无权限", "权限不足")
    _err_str = str(last_error).lower() if last_error else ""
    if any(kw.lower() in _err_str for kw in _perm_keywords):
        _dataset_id = task.get("dataset", "")
        _dataset_name = _get_dataset_name(_dataset_id)
        return {
            "name": task["name"],
            "path": task["path"],
            "label": label,
            "date": date,
            "dataset": _dataset_id,
            "dataset_name": _dataset_name,
            "columns": [],
            "rows": [],
            "total": 0,
            "elapsed_s": elapsed,
            "error": str(last_error),
            "error_type": "no_permission",
            "permission_msg": f"数据集\"{_dataset_name}\"无权限，请在 https://auth.keetapp.com/apply 资源选择“魔数2.0(MTBI)-数据集”，搜索\"{_dataset_name}\"",
        }
    return {
        "name": task["name"],
        "path": task["path"],
        "label": label,
        "date": date,
        "dataset": task["dataset"],
        "columns": [],
        "rows": [],
        "total": 0,
        "elapsed_s": elapsed,
        "error": str(last_error),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Path 0 附加：逐天 CXR 序列 + 异常日检测（缺口2）
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_daily_cxr(client: "KeetaClient", region: str,
                     date_cur: str, date_cmp: str,
                     mode: str = "device") -> dict:
    """
    逐天 CXR 序列 + 异常日检测（Path 0 附加，周期>=3天时执行）。
    用 group_by=["dt"] 一次性取回每天的访购率（率值，不可 SUM）。
    mode: "device" 用 davg_visit_txn_ratio(60051984)；"user" 用 davg_visit2ord_rate(60051108)。
    """
    _cxr_dataset = "60051108" if mode == "user" else "60051984"
    _cxr_measure = "davg_visit2ord_rate" if mode == "user" else "davg_visit_txn_ratio"
    import statistics

    def _expand(date_range: str) -> list:
        from datetime import datetime, timedelta
        a, b = date_range.split("~")
        s = datetime.strptime(a, "%Y%m%d"); e = datetime.strptime(b, "%Y%m%d")
        out = []; d = s
        while d <= e:
            out.append(d.strftime("%Y%m%d")); d += timedelta(days=1)
        return out

    cur_days = _expand(date_cur)
    cmp_days = _expand(date_cmp)

    if len(cur_days) < 3:
        return {
            "executed": False,
            "reason": f"分析周期 {len(cur_days)} 天 < 3，跳过异常日检测",
        }

    def _query_daily(date_range: str, label: str) -> dict:
        t_query = time.time()
        try:
            res = client.query(
                dataset_id=_cxr_dataset,
                measures=[_cxr_measure],
                date_range=date_range,
                region=region,
                group_by=["dt"],
                order_by={"dt": "ASC"},
                page_size=100,
            )
        except Exception as e:
            # tracking: scripts/cxr_fetch.py::_fetch_daily_cxr._query_daily::skill-script
            _report_script_node(
                "scripts/cxr_fetch.py::_fetch_daily_cxr._query_daily::skill-script",
                {
                    "task": "daily_cxr",
                    "dataset": _cxr_dataset,
                    "measure": _cxr_measure,
                    "date": date_range,
                    "label": label,
                    "region": region,
                },
                {},
                int((time.time() - t_query) * 1000),
                False,
                str(e),
            )
            return {"error": str(e), "series": {}}
        # tracking: scripts/cxr_fetch.py::_fetch_daily_cxr._query_daily::skill-script
        _report_script_node(
            "scripts/cxr_fetch.py::_fetch_daily_cxr._query_daily::skill-script",
            {
                "task": "daily_cxr",
                "dataset": _cxr_dataset,
                "measure": _cxr_measure,
                "date": date_range,
                "label": label,
                "region": region,
            },
            res,
            int((time.time() - t_query) * 1000),
            True,
            "",
        )
        series = {}
        for row in res.get("rows", []):
            raw_dt = str(row.get("dt", ""))
            norm = raw_dt.replace("-", "").replace("/", "")[:8]
            cxr = _safe_float(row.get(_cxr_measure))
            if cxr > 1:
                cxr /= 100.0
            if norm:
                series[norm] = cxr
        return {"error": None, "series": series}

    cur = _query_daily(date_cur, "cur")
    cmp = _query_daily(date_cmp, "cmp")

    if cur.get("error") or not cur.get("series"):
        return {
            "executed": True,
            "verdict": "error",
            "error": cur.get("error") or "本期逐天序列为空",
            "daily_series_cur": cur.get("series", {}),
            "daily_series_cmp": cmp.get("series", {}),
        }

    cur_series = cur["series"]
    cmp_series = cmp.get("series", {})

    vals = list(cur_series.values())
    day_mean = statistics.mean(vals)
    day_std = statistics.pstdev(vals) if len(vals) > 1 else 0.0

    anomaly_days = []
    for dt, cxr in sorted(cur_series.items()):
        dev_pp = (cxr - day_mean)
        hit_pp = abs(dev_pp) >= 0.02
        hit_sigma = (day_std > 0 and abs(dev_pp) >= 2 * day_std)
        if hit_pp or hit_sigma:
            anomaly_days.append({
                "dt": dt,
                "cxr": round(cxr, 6),
                "deviation_pp": round(dev_pp * 100, 4),
                "sigma": round(dev_pp / day_std, 2) if day_std > 0 else None,
                "trigger": "≥2pp" if hit_pp else "≥2σ",
            })

    cmp_vals = list(cmp_series.values())
    cmp_mean = statistics.mean(cmp_vals) if cmp_vals else None
    raw_change_pp = round((day_mean - cmp_mean) * 100, 4) if cmp_mean is not None else None

    recomputed = None
    if anomaly_days:
        anom_dt_set = {a["dt"] for a in anomaly_days}
        cur_kept = {d: v for d, v in cur_series.items() if d not in anom_dt_set}
        idx_to_remove = [cur_days.index(d) for d in anom_dt_set if d in cur_days]
        cmp_remove_dts = {cmp_days[i] for i in idx_to_remove if i < len(cmp_days)}
        cmp_kept = {d: v for d, v in cmp_series.items() if d not in cmp_remove_dts}

        cur_kept_mean = statistics.mean(list(cur_kept.values())) if cur_kept else None
        cmp_kept_mean = statistics.mean(list(cmp_kept.values())) if cmp_kept else None
        if cur_kept_mean is not None and cmp_kept_mean is not None:
            change_after = round((cur_kept_mean - cmp_kept_mean) * 100, 4)
            recomputed = {
                "cur_mean_after": round(cur_kept_mean, 6),
                "cmp_mean_after": round(cmp_kept_mean, 6),
                "change_pp_after": change_after,
                "dominated_by_anomaly_day": abs(change_after) < 1.0,
            }

    if not anomaly_days:
        verdict = "no_anomaly_day"
    elif recomputed and recomputed["dominated_by_anomaly_day"]:
        verdict = "anomaly_day_dominated"
    else:
        verdict = "anomaly_day_present"

    return {
        "executed": True,
        "verdict": verdict,
        "period_days": len(cur_days),
        "cur_day_mean": round(day_mean, 6),
        "cur_day_std": round(day_std, 6),
        "raw_change_pp": raw_change_pp,
        "anomaly_days": anomaly_days,
        "recomputed": recomputed,
        "daily_series_cur": {k: round(v, 6) for k, v in sorted(cur_series.items())},
        "daily_series_cmp": {k: round(v, 6) for k, v in sorted(cmp_series.items())},
    }


# ══════════════════════════════════════════════════════════════════════════════
# Path 0 前置：基期健康度校验（缺口1，并发版）
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_baseline_health(client: "KeetaClient", region: str,
                           date_cur: str, date_cmp: str,
                           lookback_weeks: int = 10,
                           mode: str = "device") -> dict:
    """
    基期健康度校验（SKILL.md §3.0 最高优先前置闸门）。
    回溯近 ~10 周周度访购率，判断对比期/本期是否离群。
    并发执行（ThreadPoolExecutor max_workers=4），不复用主结果并发池。
    mode: "device" 用 davg_visit_txn_ratio(60051984)；"user" 用 davg_visit2ord_rate(60051108)。
    """
    _cxr_dataset = "60051108" if mode == "user" else "60051984"
    _cxr_measure = "davg_visit2ord_rate" if mode == "user" else "davg_visit_txn_ratio"
    import statistics
    from datetime import datetime, timedelta

    def _win_len(rng: str) -> int:
        a, b = rng.split("~")
        return (datetime.strptime(b, "%Y%m%d") - datetime.strptime(a, "%Y%m%d")).days + 1

    cmp_a, cmp_b = date_cmp.split("~")
    win = _win_len(date_cmp)

    windows = []
    end = datetime.strptime(cmp_b, "%Y%m%d")
    start = datetime.strptime(cmp_a, "%Y%m%d")
    for _ in range(lookback_weeks):
        windows.append((start.strftime("%Y%m%d"), end.strftime("%Y%m%d")))
        end = start - timedelta(days=1)
        start = end - timedelta(days=win - 1)
    windows = list(reversed(windows))  # 时间升序

    def _week_cxr(a: str, b: str):
        t_query = time.time()
        date_range = f"{a}~{b}"
        try:
            res = client.query(
                dataset_id=_cxr_dataset,
                measures=[_cxr_measure],
                date_range=date_range, region=region,
                group_by=None, order_by=None, page_size=10,
            )
            # tracking: scripts/cxr_fetch.py::_fetch_baseline_health._week_cxr::skill-script
            _report_script_node(
                "scripts/cxr_fetch.py::_fetch_baseline_health._week_cxr::skill-script",
                {
                    "task": "baseline_health",
                    "dataset": _cxr_dataset,
                    "measure": _cxr_measure,
                    "date": date_range,
                    "region": region,
                },
                res,
                int((time.time() - t_query) * 1000),
                True,
                "",
            )
            rows = res.get("rows", [])
            if not rows:
                return None
            v = _safe_float(rows[0].get(_cxr_measure))
            if v > 1:
                v /= 100.0
            return v if v > 0 else None
        except Exception as e:
            # tracking: scripts/cxr_fetch.py::_fetch_baseline_health._week_cxr::skill-script
            _report_script_node(
                "scripts/cxr_fetch.py::_fetch_baseline_health._week_cxr::skill-script",
                {
                    "task": "baseline_health",
                    "dataset": _cxr_dataset,
                    "measure": _cxr_measure,
                    "date": date_range,
                    "region": region,
                },
                {},
                int((time.time() - t_query) * 1000),
                False,
                str(e),
            )
            return None

    # 并发跑 lookback_weeks 个历史周 + 本期窗口
    cur_a, cur_b = date_cur.split("~")
    series_cxr = [None] * len(windows)
    cur_cxr = None
    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_map = {}
        for i, (a, b) in enumerate(windows):
            fut_map[pool.submit(_week_cxr, a, b)] = i
        fut_cur = pool.submit(_week_cxr, cur_a, cur_b)
        for fut in as_completed(list(fut_map.keys()) + [fut_cur]):
            if fut is fut_cur:
                cur_cxr = fut.result()
            else:
                series_cxr[fut_map[fut]] = fut.result()

    series = []  # 时间升序回填
    for (a, b), c in zip(windows, series_cxr):
        series.append({"range": f"{a}~{b}", "cxr": round(c, 6) if c is not None else None})

    hist = [s for s in series if s["cxr"] is not None and s["range"] != date_cmp]
    cmp_point = next((s["cxr"] for s in series if s["range"] == date_cmp), None)

    if len(hist) < 4 or cmp_point is None:
        return {
            "verdict": "error", "pass": None,
            "suggested_baseline": None, "cyclicality_note": None,
            "error": f"有效历史周样本不足（{len(hist)} 周）或对比期取数失败",
            "weekly_series": series, "cur_cxr": cur_cxr,
        }

    hist_vals = [s["cxr"] for s in hist]
    mean = statistics.mean(hist_vals)
    std = statistics.pstdev(hist_vals) if len(hist_vals) > 1 else 0.0

    def _z(x):
        return (x - mean) / std if std > 0 else 0.0

    z_cmp = _z(cmp_point)
    z_cur = _z(cur_cxr) if cur_cxr is not None else None

    suggested_baseline = None
    if abs(z_cmp) >= 2:
        verdict = "baseline_anomaly"; passed = False
        cand = sorted(hist, key=lambda s: abs(s["cxr"] - mean))
        suggested_baseline = cand[0]["range"] if cand else None
    elif z_cur is not None and abs(z_cur) >= 2:
        verdict = "current_anomaly"; passed = False
    else:
        verdict = "baseline_ok"; passed = True

    notes = []
    d0, d1 = cmp_a[-2:], cmp_b[-2:]
    if int(d0) <= 5 or int(d1) >= 25:
        notes.append("对比期落在月初/月末，注意 payweek/发薪周期影响（启发式，需结合 §3.2 确认）")
    if std > 0 and (max(hist_vals) - min(hist_vals)) >= 0.02:
        notes.append(f"近{len(hist)}周 CXR 极差 {round((max(hist_vals)-min(hist_vals))*100,2)}pp，序列含周期/趋势成分")
    cyclicality_note = "；".join(notes) if notes else None

    return {
        "verdict": verdict,
        "pass": passed,
        "suggested_baseline": suggested_baseline,
        "cyclicality_note": cyclicality_note,
        "hist_mean_cxr": round(mean, 6),
        "hist_std_cxr": round(std, 6),
        "cmp_cxr": round(cmp_point, 6),
        "cmp_zscore": round(z_cmp, 2),
        "cur_cxr": round(cur_cxr, 6) if cur_cxr is not None else None,
        "cur_zscore": round(z_cur, 2) if z_cur is not None else None,
        "weekly_series": series,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 并发主入口
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_external_context(region: str, date_cur: str, date_cmp: str) -> dict:
    """
    查询外部环境信息（天气 + 节假日），Path 0 必查项。
    Best-effort：查询失败不阻塞主流程，返回 error 字段。
    """
    import subprocess

    weather_script = str(_SKILL_DIR / "keeta-external-context" / "scripts" / "weather.py")
    holidays_script = str(_SKILL_DIR / "keeta-external-context" / "scripts" / "holidays.py")

    result = {"weather_cur": None, "weather_cmp": None, "holidays": None}

    # 检测 skill 是否安装
    if not Path(weather_script).exists() and not Path(holidays_script).exists():
        print("[cxr_fetch] ℹ️ 外部环境查询跳过: 未安装 keeta-external-context skill", file=sys.stderr)
        result["_skill_missing"] = True
        return result

    # 天气-本期（逐天查）
    def _query_weather(date_range: str) -> list[dict]:
        """查单日或连续日天气，返回 list of day records"""
        days = []
        # 解析日期范围
        if "~" in date_range:
            start, end = date_range.split("~")
        else:
            start = end = date_range
        from datetime import datetime, timedelta
        dt = datetime.strptime(start, "%Y%m%d")
        dt_end = datetime.strptime(end, "%Y%m%d")
        while dt <= dt_end:
            d = dt.strftime("%Y%m%d")
            t_query = time.time()
            try:
                res = subprocess.run(
                    [sys.executable, weather_script, region, d, "--allow-fallback"],
                    capture_output=True, text=True, timeout=15
                )
                # tracking: scripts/cxr_fetch.py::_fetch_external_context._query_weather::skill-script
                _report_script_node(
                    "scripts/cxr_fetch.py::_fetch_external_context._query_weather::skill-script",
                    {
                        "task": "external_weather",
                        "script": weather_script,
                        "date": d,
                        "region": region,
                    },
                    {"returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr},
                    int((time.time() - t_query) * 1000),
                    res.returncode == 0,
                    "" if res.returncode == 0 else (res.stderr or res.stdout or "weather script failed"),
                )
                if res.returncode == 0:
                    import json as _json
                    data = _json.loads(res.stdout)
                    for row in data.get("data", []):
                        days.append(row)
            except Exception as e:
                # tracking: scripts/cxr_fetch.py::_fetch_external_context._query_weather::skill-script
                _report_script_node(
                    "scripts/cxr_fetch.py::_fetch_external_context._query_weather::skill-script",
                    {
                        "task": "external_weather",
                        "script": weather_script,
                        "date": d,
                        "region": region,
                    },
                    {},
                    int((time.time() - t_query) * 1000),
                    False,
                    str(e),
                )
                pass
            dt += timedelta(days=1)
        return days

    # 天气-本期
    try:
        result["weather_cur"] = _query_weather(date_cur)
        print(f"[cxr_fetch] 外部环境-天气(本期): {len(result['weather_cur'])} days", file=sys.stderr)
    except Exception as e:
        result["weather_cur"] = {"error": str(e)}

    # 天气-对比期
    try:
        result["weather_cmp"] = _query_weather(date_cmp)
        print(f"[cxr_fetch] 外部环境-天气(对比期): {len(result['weather_cmp'])} days", file=sys.stderr)
    except Exception as e:
        result["weather_cmp"] = {"error": str(e)}

    # 节假日
    t_query = time.time()
    try:
        from datetime import datetime as _dt
        start_iso = _dt.strptime(date_cur.split("~")[0], "%Y%m%d").strftime("%Y-%m-%d")
        end_iso = _dt.strptime(date_cur.split("~")[-1], "%Y%m%d").strftime("%Y-%m-%d")
        res = subprocess.run(
            [sys.executable, holidays_script, "range",
             "--start", start_iso, "--end", end_iso,
             "--regions", region, "--allow-fallback"],
            capture_output=True, text=True, timeout=45
        )
        # tracking: scripts/cxr_fetch.py::_fetch_external_context.holidays::skill-script
        _report_script_node(
            "scripts/cxr_fetch.py::_fetch_external_context.holidays::skill-script",
            {
                "task": "external_holidays",
                "script": holidays_script,
                "date": f"{start_iso}~{end_iso}",
                "region": region,
            },
            {"returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr},
            int((time.time() - t_query) * 1000),
            res.returncode == 0,
            "" if res.returncode == 0 else (res.stderr or res.stdout or "holidays script failed"),
        )
        if res.returncode == 0:
            import json as _json
            result["holidays"] = _json.loads(res.stdout)
        else:
            result["holidays"] = {"error": res.stderr[:200] if res.stderr else "exit code != 0"}
        print(f"[cxr_fetch] 外部环境-节假日: {'ok' if isinstance(result['holidays'], dict) and 'error' not in result['holidays'] else 'failed'}", file=sys.stderr)
    except Exception as e:
        # tracking: scripts/cxr_fetch.py::_fetch_external_context.holidays::skill-script
        _report_script_node(
            "scripts/cxr_fetch.py::_fetch_external_context.holidays::skill-script",
            {
                "task": "external_holidays",
                "script": holidays_script,
                "date": date_cur,
                "region": region,
            },
            {},
            int((time.time() - t_query) * 1000),
            False,
            str(e),
        )
        result["holidays"] = {"error": str(e)}

    return result


def _resolve_project_ids(bi_client: "BiClient" | None = None) -> list[str]:
    """
    动态获取用户可用的项目组 ID 列表。
    旧方案硬编码 project_id="109495"，新方案通过 BiClient.get_spaces() 动态获取。
    """
    DEFAULT_PROJECT_GROUP = "sailor-product-data"

    if bi_client is None:
        try:
            from core.bi_client import BiClient
            bi_client = BiClient()
        except Exception:
            return [DEFAULT_PROJECT_GROUP]

    try:
        spaces = bi_client.get_spaces()
        data = spaces.get("data", [])
        if not isinstance(data, list) or not data:
            return [DEFAULT_PROJECT_GROUP]
        project_ids = []
        _priority_id = None
        for group in data:
            children = group.get("children", [])
            if children:
                for child in children:
                    pid = str(child.get("id", child.get("projectId", "")))
                    name = str(child.get("name", child.get("projectName", "")))
                    if pid and pid.isdigit():
                        project_ids.append(pid)
                        if DEFAULT_PROJECT_GROUP.lower() in name.lower():
                            _priority_id = pid
        if not project_ids:
            return [DEFAULT_PROJECT_GROUP]
        if _priority_id and _priority_id in project_ids:
            project_ids.remove(_priority_id)
            project_ids.insert(0, _priority_id)
        return project_ids
    except Exception as e:
        print(f"[cxr_fetch] _resolve_project_ids 失败: {e}", file=sys.stderr)
        return [DEFAULT_PROJECT_GROUP]


def _fetch_keemart_split(region: str, date_cur: str, date_cmp: str,
                         mode: str = "device") -> dict | None:
    """
    SA 地区专属：拆分 Keeta 外卖 vs Keemart 电商的流量和访购率。
    仅 region.upper() == "SA" 时执行，其他地区返回 None。
    """
    if region.upper() != "SA":
        return None

    QUEUE = "root.fra02.hadoop-sailor.query"

    if mode == "user":
        table = "mart_sailor_global.aggr_flow_usr_visit_biz_type_d"
        uv_col = "user_id"
        uv_measure = "davg_visit_usr_num"
        txn_measure = "davg_visit2ord_rate"
    else:
        table = "mart_sailor_global.aggr_flow_union_visit_biz_type_d"
        uv_col = "union_id"
        uv_measure = "davg_dau"
        txn_measure = "davg_visit_txn_ratio"

    def _parse_dates(date_range: str) -> tuple[str, str]:
        parts = date_range.split("~")
        return (parts[0], parts[1] if len(parts) > 1 else parts[0])

    cur_start, cur_end = _parse_dates(date_cur)
    cmp_start, cmp_end = _parse_dates(date_cmp)

    sql_template = """
SELECT 
    biz_type,
    COUNT(DISTINCT {uv_col}) / COUNT(DISTINCT dt) AS {uv_measure},
    COUNT(DISTINCT CASE WHEN is_kt_ordered = 1 THEN {uv_col} END) / COUNT(DISTINCT dt) AS txn_{uv_col}_cnt,
    COUNT(DISTINCT CASE WHEN is_kt_ordered = 1 THEN {uv_col} END) / COUNT(DISTINCT CASE WHEN {uv_col} IS NOT NULL THEN {uv_col} END) AS {txn_measure}
FROM {table}
WHERE dt BETWEEN '__START__' AND '__END__'
  AND {uv_col} IS NOT NULL
GROUP BY biz_type
ORDER BY {uv_measure} DESC
"""

    sql_cur = sql_template.format(
        uv_col=uv_col, uv_measure=uv_measure, txn_measure=txn_measure, table=table
    ).replace('__START__', cur_start).replace('__END__', cur_end)
    sql_cmp = sql_template.format(
        uv_col=uv_col, uv_measure=uv_measure, txn_measure=txn_measure, table=table
    ).replace('__START__', cmp_start).replace('__END__', cmp_end)

    km_channel_sql_template = """
SELECT 
    is_km_channel_user,
    COUNT(DISTINCT {uv_col}) / COUNT(DISTINCT dt) AS {uv_measure},
    COUNT(DISTINCT CASE WHEN is_kt_ordered = 1 THEN {uv_col} END) / COUNT(DISTINCT dt) AS txn_{uv_col}_cnt,
    COUNT(DISTINCT CASE WHEN is_kt_ordered = 1 THEN {uv_col} END) / COUNT(DISTINCT CASE WHEN {uv_col} IS NOT NULL THEN {uv_col} END) AS {txn_measure}
FROM {table}
WHERE dt BETWEEN '__START__' AND '__END__'
  AND {uv_col} IS NOT NULL
  AND biz_type = 'keemart'
GROUP BY is_km_channel_user
ORDER BY {uv_measure} DESC
"""

    km_channel_sql_cur = km_channel_sql_template.format(
        uv_col=uv_col, uv_measure=uv_measure, txn_measure=txn_measure, table=table
    ).replace('__START__', cur_start).replace('__END__', cur_end)
    km_channel_sql_cmp = km_channel_sql_template.format(
        uv_col=uv_col, uv_measure=uv_measure, txn_measure=txn_measure, table=table
    ).replace('__START__', cmp_start).replace('__END__', cmp_end)

    print(f"[cxr_fetch] _fetch_keemart_split: 执行 SA biz_type + km_channel 查询 (mode={mode})", file=sys.stderr)

    project_ids = _resolve_project_ids()

    try:
        from core.bi_client import BiClient
    except ImportError:
        print(f"[cxr_fetch] _fetch_keemart_split: 无法导入 BiClient，跳过", file=sys.stderr)
        return None

    bi_client = BiClient()

    def _try_run_sql(sql: str) -> dict | None:
        for pid in project_ids:
            try:
                bi_client.project_id = pid
                submit_result = bi_client.submit_sql(
                    sql=sql, spark_queue=QUEUE, ds_name="dw_hive",
                    stat_ds="DW_ONESQL_DB_CONNECT_URL", engine="onesql",
                )
                submit_data = submit_result.get("data") or {}
                query_id = submit_data.get("queryId") or submit_data.get("id")
                if not query_id:
                    msg = submit_result.get("message", "")
                    print(f"[cxr_fetch] _fetch_keemart_split: 提交失败 (pid={pid}): {msg}", file=sys.stderr)
                    continue

                import time as _time
                for _ in range(60):
                    _time.sleep(2)
                    status_result = bi_client.get_status(query_id)
                    status_data = status_result.get("data") or {}
                    status = str(status_data.get("status", ""))
                    if status in ("SUCCESS", "DONE", "3"):
                        _time.sleep(2)
                        result = bi_client.get_result(query_id, limit=500)
                        result_data = result.get("data") or {}
                        col_names = result_data.get("columns", []) or []
                        raw_rows = result_data.get("data", []) or []
                        for _retry in range(5):
                            if raw_rows:
                                break
                            _time.sleep(3)
                            result = bi_client.get_result(query_id, limit=500)
                            result_data = result.get("data") or {}
                            col_names = result_data.get("columns", []) or []
                            raw_rows = result_data.get("data", []) or []
                        if col_names and raw_rows and isinstance(raw_rows[0], list):
                            rows = [dict(zip(col_names, row)) for row in raw_rows]
                        elif isinstance(raw_rows, list) and raw_rows and isinstance(raw_rows[0], dict):
                            rows = raw_rows
                        else:
                            rows = []
                        return {"columns": col_names, "rows": rows}
                    elif status in ("4", "5", "6", "7", "FAILED", "ERROR"):
                        error_msg = status_data.get("message", "unknown")
                        if "permission" in str(error_msg).lower() or "NO_PERMISSION" in str(error_msg):
                            print(f"[cxr_fetch] _fetch_keemart_split: 项目组 {pid} 无权限，尝试下一个", file=sys.stderr)
                            break
                        print(f"[cxr_fetch] _fetch_keemart_split: SQL 执行失败 (pid={pid}): {error_msg}", file=sys.stderr)
                        continue
                else:
                    print(f"[cxr_fetch] _fetch_keemart_split: 查询超时 (pid={pid})", file=sys.stderr)
                    continue
            except Exception as e:
                err_str = str(e)
                if "permission" in err_str.lower() or "NO_PERMISSION" in err_str:
                    print(f"[cxr_fetch] _fetch_keemart_split: 项目组 {pid} 无权限，尝试下一个", file=sys.stderr)
                    continue
                print(f"[cxr_fetch] _fetch_keemart_split: 项目组 {pid} 执行异常: {e}", file=sys.stderr)
                continue

        table_name = table.split(".")[-1]
        hetu_url = f"https://data.keetapp.com/hetu/tableApply?applyType=external&providerType=person&refer=role&source=DW_ONESQL_DB_CONNECT_URL&database=mart_sailor_global&table={table_name}"
        print(f"[cxr_fetch] _fetch_keemart_split: 所有项目组均无权限，请申请: {hetu_url}", file=sys.stderr)
        return {"error": "no_permission", "hetu_apply_url": hetu_url, "table": table_name}

    cur_result = _try_run_sql(sql_cur)
    cmp_result = _try_run_sql(sql_cmp)
    km_cur_result = _try_run_sql(km_channel_sql_cur)
    km_cmp_result = _try_run_sql(km_channel_sql_cmp)

    if cur_result is None and cmp_result is None and km_cur_result is None and km_cmp_result is None:
        return None

    result = {
        "traffic_biz_type": {
            "cur": cur_result or {"columns": [], "rows": [], "error": "query_failed"},
            "cmp": cmp_result or {"columns": [], "rows": [], "error": "query_failed"},
            "path": "path3_biz_type",
            "dataset": "hive",
        }
    }

    if km_cur_result or km_cmp_result:
        result["traffic_km_channel"] = {
            "cur": km_cur_result or {"columns": [], "rows": [], "error": "query_failed"},
            "cmp": km_cmp_result or {"columns": [], "rows": [], "error": "query_failed"},
            "path": "path3_km_channel",
            "dataset": "hive",
        }

    return result


def fetch_all(
    region: str,
    date_cur: str,
    date_cmp: str,
    max_workers: int = 12,
    timeout: float = 120.0,
    drilldown_mode: str | None = None,
    mode: str = "device",
) -> dict[str, Any]:
    """
    并发查询所有路径，本期 + 对比期同时发出。

    返回结构：
    {
        "region": "QA",
        "date_cur": "20260419~20260419",
        "date_cmp": "20260412~20260412",
        "elapsed_total_s": 4.2,
        "results": {
            "base":             {"cur": {...}, "cmp": {...}},
            "subsidy":          {"cur": {...}, "cmp": {...}},
            "traffic_structure":{"cur": {...}, "cmp": {...}},
            "module_cxr":       {"cur": {...}, "cmp": {...}},
            "funnel":           {"cur": {...}, "cmp": {...}},
            "search":           {"cur": {...}, "cmp": {...}},
        }
    }
    """
    # 单日 → 补全为区间格式
    def _normalize_date(d: str) -> str:
        d = d.strip()
        if "~" not in d:
            return f"{d}~{d}"
        return d

    date_cur = _normalize_date(date_cur)
    date_cmp = _normalize_date(date_cmp)

    tasks = _build_tasks(region, date_cur, date_cmp, mode=mode)

    # 追加下钻任务（如有）
    if drilldown_mode:
        drilldown_tasks = _build_drilldown_tasks(region, drilldown_mode)
        if drilldown_tasks:
            print(f"[cxr_fetch] 下钻模式: {drilldown_mode}，追加 {len(drilldown_tasks)} 个下钻任务", file=sys.stderr)
            tasks = tasks + drilldown_tasks

    # 共享一个 KeetaClient 实例（鉴权只做一次）
    print(f"[cxr_fetch] 初始化鉴权 ...", file=sys.stderr)
    t_auth = time.time()
    client_cls = _get_keeta_client_cls()
    client = client_cls(region=region)
    print(f"[cxr_fetch] 鉴权完成 ({round(time.time()-t_auth,2)}s)", file=sys.stderr)

    # ── 辅助：日期区间 → 逐天列表 ────────────────────────────────────────
    def _expand_dates(date_range: str) -> list[str]:
        """'20260412~20260418' → ['20260412', '20260413', ..., '20260418']"""
        from datetime import datetime, timedelta
        parts = date_range.split("~")
        start = datetime.strptime(parts[0], "%Y%m%d")
        end = datetime.strptime(parts[1], "%Y%m%d")
        days = []
        d = start
        while d <= end:
            days.append(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
        return days

    # 构造所有并发任务：每个 task × 两个日期（cur + cmp）
    # day_by_day=True 的任务拆成逐天查询
    jobs = []          # (task, date_str, label, is_day_part)
    dbd_tasks = set()  # 需要逐天聚合的 task names
    for task in tasks:
        if task.get("day_by_day"):
            dbd_tasks.add(task["name"])
            for day in _expand_dates(date_cur):
                jobs.append((task, f"{day}~{day}", "cur", True))
            for day in _expand_dates(date_cmp):
                jobs.append((task, f"{day}~{day}", "cmp", True))
        else:
            jobs.append((task, date_cur, "cur", False))
            jobs.append((task, date_cmp, "cmp", False))

    print(f"[cxr_fetch] 并发执行 {len(jobs)} 个查询（{len(tasks)} 路径，含逐天展开）...", file=sys.stderr)
    t0 = time.time()

    results_flat: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_one, client, task, date, label, region): (task["name"], label, is_dp)
            for task, date, label, is_dp in jobs
        }
        for future in as_completed(futures, timeout=timeout):
            name, label, is_dp = futures[future]
            try:
                res = future.result()
                results_flat.append(res)
                status = "✓" if not res["error"] else f"✗ {res['error'][:60]}"
                if not is_dp:
                    print(f"[cxr_fetch]   {name}/{label}: {status} ({res['elapsed_s']}s)", file=sys.stderr)
            except Exception as e:
                results_flat.append({
                    "name": name, "path": name, "label": label,
                    "date": "", "dataset": "",
                    "columns": [], "rows": [], "total": 0,
                    "elapsed_s": 0, "error": f"future failed: {e}",
                })

    elapsed_total = round(time.time() - t0, 2)

    # ── 逐天结果聚合（对 day_by_day 任务，按 label+group_by 做 SUM 聚合）────
    def _aggregate_day_results(name: str, label: str, day_results: list[dict]) -> dict:
        """将多天结果聚合为一条汇总结果（SUM 聚合）"""
        ok_results = [r for r in day_results if not r.get("error")]
        if not ok_results:
            # 全部失败
            errors = "; ".join(set(r.get("error", "unknown") for r in day_results if r.get("error")))
            return {
                "date": date_cur if label == "cur" else date_cmp,
                "columns": [], "rows": [], "total": 0,
                "elapsed_s": sum(r.get("elapsed_s", 0) for r in day_results),
                "error": f"all {len(day_results)} day queries failed: {errors[:100]}",
            }
        columns = ok_results[0].get("columns", [])
        # 找出 group_by 列
        task_obj = next((t for t in tasks if t["name"] == name), None)
        group_cols = set(task_obj.get("group_by") or []) if task_obj else set()
        measure_cols = [c for c in columns if c not in group_cols]

        # 按 group_key 聚合 SUM
        agg: dict[tuple, dict] = {}
        failed_days = len(day_results) - len(ok_results)
        for r in ok_results:
            for row in r.get("rows", []):
                gk = tuple(row.get(g, "") for g in sorted(group_cols)) if group_cols else ("__all__",)
                if gk not in agg:
                    agg[gk] = {g: row.get(g, "") for g in group_cols}
                    for mc in measure_cols:
                        agg[gk][mc] = 0.0
                    agg[gk]["__days__"] = 0
                for mc in measure_cols:
                    try:
                        val = row.get(mc, 0) or 0
                        if isinstance(val, str):
                            val = val.replace(",", "")  # "1,493,824" → "1493824"
                        agg[gk][mc] += float(val)
                    except (ValueError, TypeError):
                        pass
                agg[gk]["__days__"] += 1

        # 去掉 __days__ 辅助字段
        rows = []
        for gk, vals in agg.items():
            days_count = vals.pop("__days__", 1)
            rows.append(vals)

        total_elapsed = round(sum(r.get("elapsed_s", 0) for r in day_results), 2)
        print(f"[cxr_fetch]   {name}/{label}: ✓ aggregated {len(ok_results)} days"
              f"{f' ({failed_days} failed)' if failed_days else ''}"
              f" → {len(rows)} rows ({total_elapsed}s)", file=sys.stderr)

        return {
            "date": date_cur if label == "cur" else date_cmp,
            "columns": columns,
            "rows": rows,
            "total": len(rows),
            "elapsed_s": total_elapsed,
            "error": f"{failed_days} of {len(day_results)} days failed" if failed_days else None,
        }

    print(f"[cxr_fetch] 全部完成，总耗时 {elapsed_total}s", file=sys.stderr)

    # 整理成按 name 分组的结构
    grouped: dict[str, dict] = {}

    # 先处理非逐天的结果
    for res in results_flat:
        name = res["name"]
        label = res["label"]
        if name in dbd_tasks:
            continue  # 逐天任务后面聚合处理
        if name not in grouped:
            grouped[name] = {"cur": None, "cmp": None, "path": res["path"], "dataset": res["dataset"]}
        grouped[name][label] = {
            "date": res["date"],
            "columns": res["columns"],
            "rows": res["rows"],
            "total": res["total"],
            "elapsed_s": res["elapsed_s"],
            "error": res["error"],
        }

    # 再处理逐天聚合的结果
    for task_name in dbd_tasks:
        task_results = [r for r in results_flat if r["name"] == task_name]
        cur_days = [r for r in task_results if r["label"] == "cur"]
        cmp_days = [r for r in task_results if r["label"] == "cmp"]
        task_obj = next((t for t in tasks if t["name"] == task_name), None)
        grouped[task_name] = {
            "cur": _aggregate_day_results(task_name, "cur", cur_days) if cur_days else None,
            "cmp": _aggregate_day_results(task_name, "cmp", cmp_days) if cmp_days else None,
            "path": task_obj["path"] if task_obj else task_name,
            "dataset": task_obj["dataset"] if task_obj else "",
        }

    # ── 贡献度计算 ─────────────────────────────────────────────────────────
    print(f"[cxr_fetch] 计算贡献度 ...", file=sys.stderr)
    try:
        contributions = compute_contributions(grouped, mode=mode)
    except Exception as e:
        contributions = None
        print(f"[cxr_fetch] 贡献度计算整体失败: {e}", file=sys.stderr)

    # 记录贡献度计算状态到 data_status
    contrib_status = {}
    if contributions:
        for key in ["funnel"]:
            contrib_status[f"contribution_{key}"] = "ok" if contributions.get(key) else "missing_data"
        if contributions.get("stp"):
            for sub_key, sub_val in contributions["stp"].items():
                contrib_status[f"contribution_stp_{sub_key}"] = "ok" if sub_val else "missing_data"
        else:
            contrib_status["contribution_stp"] = "missing_data"
        contrib_status["contribution_module_structure"] = (
            "ok" if contributions.get("module_structure") else "missing_data"
        )
        # 补贴贡献度
        if contributions.get("subsidy_structure"):
            for sub_key, sub_val in contributions["subsidy_structure"].items():
                contrib_status[f"contribution_subsidy_{sub_key}"] = "ok" if sub_val else "missing_data"
        else:
            contrib_status["contribution_subsidy"] = "missing_data"
    else:
        contrib_status["contributions"] = "computation_failed"
    print(f"[cxr_fetch] 贡献度计算完成: {contrib_status}", file=sys.stderr)

    # ── Gate checks（前置判断，agent 直接读 flag，不需要自行计算） ──────────
    gate_checks = {}

    # Gate 1: 优惠感知 — 日均店内优惠专区曝光PV vs 日均进店UV×4
    # 若曝光PV < 4×进店UV，说明优惠模块规模过小，跳过优惠专区分析
    try:
        promo_rows_cur = grouped.get("drilldown_s2o_promo_pv", {}).get("cur", {}).get("rows", [])
        promo_pv = _safe_float(promo_rows_cur[0].get("davg_in_store_promotion_zone_expose_pv", 0)) if promo_rows_cur else 0.0
        # 进店UV 从 drilldown_s2o_merchant_type 汇总（排除'-'异常行）
        mt_rows_cur = grouped.get("drilldown_s2o_merchant_type", {}).get("cur", {}).get("rows", [])
        enter_uv = sum(_safe_float(r.get("davg_enter_merchant_union_id", 0)) for r in mt_rows_cur if r.get("shop_type_name") != "-")
        threshold = enter_uv * 4
        _pass = promo_pv >= threshold
        gate_checks["promo_zone_gate"] = {
            "pass": _pass,
            "promo_pv": promo_pv,
            "enter_uv": enter_uv,
            "threshold_4x": threshold,
            "analysis_conclusion": (
                None if _pass
                else f"优惠感知：规模不达门槛（店内优惠专区曝光PV {promo_pv:,.0f} < 4×进店UV {threshold:,.0f}），跳过。"
            ),
        }
    except Exception as e:
        gate_checks["promo_zone_gate"] = {"pass": None, "error": str(e), "analysis_conclusion": None}

    # Gate 2: 提单页曝光优惠金额绝对值 — 若 < 0.5 本币，变化比例无参考价值，跳过该指标
    try:
        o2s_quality_cur = grouped.get("drilldown_o2s_submit_page_quality", {}).get("cur", {}).get("rows", [])
        disc_amt = _safe_float(o2s_quality_cur[0].get("davg_discount_amount_per_single_ord_sub_page_expose", 0)) if o2s_quality_cur else 0.0
        _pass2 = disc_amt >= 0.5
        gate_checks["submit_page_discount_amt_gate"] = {
            "pass": _pass2,
            "discount_amt": disc_amt,
            "analysis_conclusion": (
                None if _pass2
                else f"提单页曝光优惠金额（{disc_amt:.2f} 本币）绝对值过小，变化比例无参考价值，跳过该指标。"
            ),
        }
    except Exception as e:
        gate_checks["submit_page_discount_amt_gate"] = {"pass": None, "error": str(e), "analysis_conclusion": None}

    print(f"[cxr_fetch] Gate checks: promo_zone={gate_checks.get('promo_zone_gate',{}).get('pass')} | submit_disc_amt={gate_checks.get('submit_page_discount_amt_gate',{}).get('pass')}", file=sys.stderr)

    # ── Path 0 附加：逐天 CXR 异常日检测（周期>=3天自动执行） ──────────────
    print(f"[cxr_fetch] 逐天 CXR 异常日检测 ...", file=sys.stderr)
    try:
        anomaly_day_check = _fetch_daily_cxr(client, region, date_cur, date_cmp, mode=mode)
    except Exception as e:
        anomaly_day_check = {"executed": False, "verdict": "error", "error": str(e)}
        print(f"[cxr_fetch] 异常日检测失败: {e}", file=sys.stderr)
    print(f"[cxr_fetch] 异常日检测: verdict={anomaly_day_check.get('verdict')}", file=sys.stderr)

    # ── Path 0 前置：基期健康度校验（近~10周，并发） ──────────────
    print(f"[cxr_fetch] 基期健康度回溯（近~10周）...", file=sys.stderr)
    try:
        baseline_health = _fetch_baseline_health(client, region, date_cur, date_cmp, mode=mode)
    except Exception as e:
        baseline_health = {"verdict": "error", "pass": None,
                           "suggested_baseline": None, "cyclicality_note": None,
                           "error": str(e)}
        print(f"[cxr_fetch] 基期健康度校验失败: {e}", file=sys.stderr)
    print(f"[cxr_fetch] baseline_health: verdict={baseline_health.get('verdict')} "
          f"pass={baseline_health.get('pass')}", file=sys.stderr)

    # ── Path 0 外部环境查询（天气 + 节假日）──────────────────────────
    print("[cxr_fetch] 查询外部环境（天气/节假日）...", file=sys.stderr)
    external_context = _fetch_external_context(region, date_cur, date_cmp)

    # ── SA Keemart/Keeta 用户结构拆分 ──────────────────────────
    print(f"[cxr_fetch] SA biz_type 拆分查询 ...", file=sys.stderr)
    try:
        keemart_result = _fetch_keemart_split(region, date_cur, date_cmp, mode=mode)
        if keemart_result:
            grouped.update(keemart_result)
            print(f"[cxr_fetch] 含 biz_type 数据，重新计算贡献度 ...", file=sys.stderr)
            contributions = compute_contributions(grouped, mode=mode)
    except Exception as e:
        print(f"[cxr_fetch] SA biz_type 拆分查询失败（不影响主流程）: {e}", file=sys.stderr)

    return {
        "region": region,
        "mode": mode,
        "date_cur": date_cur,
        "date_cmp": date_cmp,
        "elapsed_total_s": elapsed_total,
        "results": grouped,
        "contributions": contributions,
        "contribution_status": contrib_status,
        "gate_checks": gate_checks,
        "anomaly_day_check": anomaly_day_check,
        "baseline_health": baseline_health,
        "external_context": external_context,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 格式化输出工具（供主 agent 读取后生成 Markdown 表格用）
# ══════════════════════════════════════════════════════════════════════════════

def _safe_float(val, default=0.0) -> float:
    """Safely convert a value to float, handling strings with commas, None, etc.
    If the string ends with '%', strip it and divide by 100 to return a true decimal.
    e.g. '0.62%' -> 0.0062, '12.02%' -> 0.1202
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.replace(",", "")
        is_pct = s.endswith("%")
        try:
            f = float(s.replace("%", ""))
            return f / 100.0 if is_pct else f
        except (ValueError, TypeError):
            return default
    return default


def _compute_funnel_contributions(results: dict) -> list[dict] | None:
    """
    计算漏斗贡献度（Path 5 数据）。
    公式：某环节贡献 ≈ Δ该环节转化率(pp) × Π(其余环节转化率_对比期)
    """
    funnel_data = results.get("funnel")
    if not funnel_data:
        return None
    cur_data = funnel_data.get("cur")
    cmp_data = funnel_data.get("cmp")
    if not cur_data or not cmp_data:
        return None
    cur_rows = cur_data.get("rows", [])
    cmp_rows = cmp_data.get("rows", [])
    if not cur_rows or not cmp_rows:
        return None

    cur_row = cur_rows[0]
    cmp_row = cmp_rows[0]

    # Ordered funnel steps: measure_key → display label
    # Detect mode by checking which measures are present in the data
    sample_row = cur_rows[0] if cur_rows else {}
    if "davg_visit_shop_cvr" in sample_row:
        # user mode
        funnel_steps = [
            ("davg_visit_shop_cvr",              "DAU→进店"),
            ("davg_visit_shop_submit_page_cvr",  "进店→提单页"),
            ("davg_submit_page_submit_cvr",      "提单页→提单"),
            ("davg_submit_pay_cvr",              "提单→支付"),
            ("davg_pay_fin_cvr",                 "支付→完单"),
        ]
    else:
        # device mode (default)
        funnel_steps = [
            ("davg_device_visit_shop_cvr",           "DAU→进店"),
            ("davg_visit_shop_submit_page_uuid_cvr", "进店→提单页"),
            ("davg_submit_page_submit_uuid_cvr",     "提单页→提单"),
            ("davg_device_submit_pay_cvr",           "提单→支付"),
            ("davg_pay_fin_union_cvr",               "支付→完单"),
        ]

    # Extract rates (as decimals, e.g. 0.55 for 55%)
    cur_rates = []
    cmp_rates = []
    for key, _ in funnel_steps:
        cur_val = _safe_float(cur_row.get(key))
        cmp_val = _safe_float(cmp_row.get(key))
        # If values look like percentages (>1), convert to decimal
        if cur_val > 1:
            cur_val /= 100.0
        if cmp_val > 1:
            cmp_val /= 100.0
        cur_rates.append(cur_val)
        cmp_rates.append(cmp_val)

    # For each step i, contribution ≈ Δ(rate_i) × Π(cmp_rate_j for j≠i)
    contributions = []
    for i, (key, label) in enumerate(funnel_steps):
        delta = cur_rates[i] - cmp_rates[i]  # change in this step's rate (decimal)
        # Product of all OTHER steps' compare-period rates
        product_others = 1.0
        for j in range(len(funnel_steps)):
            if j != i:
                product_others *= cmp_rates[j]
        contribution_pp = round(delta * product_others * 100, 4)  # convert to pp
        contributions.append({
            "step": label,
            "measure": key,
            "current_rate": round(cur_rates[i], 6),
            "compare_rate": round(cmp_rates[i], 6),
            "delta_pp": round(delta * 100, 4),
            "contribution_pp": contribution_pp,
        })

    return contributions


def _compute_stp_contributions(results: dict, task_name: str, group_col: str,
                                dau_measure: str, cxr_measure: str,
                                share_measure: str | None = None) -> dict | None:
    """
    计算 STP 结构/效率贡献度（通用函数，适用于 Path 3 / Path 3 补充 / Path 4）。

    公式：
      结构贡献 = Σ（Δ分层占比 × 分层CXR_对比期）
      效率贡献 = Σ（分层占比_本期 × Δ分层CXR）
      总变化 ≈ 结构贡献 + 效率贡献

    参数：
      task_name: results 中的 key，如 "traffic_structure", "traffic_device", "module_cxr"
      group_col: 分组列名，如 "user_finord_type_name", "os", "first_ad_position_name"
      dau_measure: 用于计算占比的量，如 "davg_dau", "davg_module_exposure_uv"
      cxr_measure: CXR 指标名，如 "davg_visit_txn_ratio", "davg_cxr_uv"
      share_measure: 若数据中已有占比字段则直接用，否则 None（从 dau_measure 计算）
    """
    task_data = results.get(task_name)
    if not task_data:
        return None
    cur_data = task_data.get("cur")
    cmp_data = task_data.get("cmp")
    if not cur_data or not cmp_data:
        return None
    cur_rows = cur_data.get("rows", [])
    cmp_rows = cmp_data.get("rows", [])
    if not cur_rows or not cmp_rows:
        return None

    # Build lookup maps: segment → row
    cur_map = {}
    for r in cur_rows:
        seg = r.get(group_col, "unknown")
        if seg:
            cur_map[seg] = r
    cmp_map = {}
    for r in cmp_rows:
        seg = r.get(group_col, "unknown")
        if seg:
            cmp_map[seg] = r

    all_segments = sorted(set(list(cur_map.keys()) + list(cmp_map.keys())))
    if not all_segments:
        return None

    # Compute DAU/volume totals for share calculation
    cur_total = sum(_safe_float(cur_map.get(s, {}).get(dau_measure)) for s in all_segments)
    cmp_total = sum(_safe_float(cmp_map.get(s, {}).get(dau_measure)) for s in all_segments)

    if cur_total == 0 and cmp_total == 0:
        return None

    detail = []
    total_structure_pp = 0.0
    total_efficiency_pp = 0.0

    for seg in all_segments:
        cur_row = cur_map.get(seg, {})
        cmp_row = cmp_map.get(seg, {})

        cur_dau = _safe_float(cur_row.get(dau_measure))
        cmp_dau = _safe_float(cmp_row.get(dau_measure))
        cur_cxr = _safe_float(cur_row.get(cxr_measure))
        cmp_cxr = _safe_float(cmp_row.get(cxr_measure))

        # CXR values: if > 1, assume percentage, convert to decimal
        if cur_cxr > 1:
            cur_cxr /= 100.0
        if cmp_cxr > 1:
            cmp_cxr /= 100.0

        # Compute shares
        cur_share = (cur_dau / cur_total) if cur_total > 0 else 0.0
        cmp_share = (cmp_dau / cmp_total) if cmp_total > 0 else 0.0

        # Structure contribution = Δshare × cxr_compare
        delta_share = cur_share - cmp_share
        structure_pp = delta_share * cmp_cxr * 100  # convert to pp

        # Efficiency contribution = share_current × Δcxr
        delta_cxr = cur_cxr - cmp_cxr
        efficiency_pp = cur_share * delta_cxr * 100  # convert to pp

        total_structure_pp += structure_pp
        total_efficiency_pp += efficiency_pp

        detail.append({
            "segment": seg,
            "dau_current": cur_dau,
            "dau_compare": cmp_dau,
            "dau_share_current": round(cur_share, 6),
            "dau_share_compare": round(cmp_share, 6),
            "cxr_current": round(cur_cxr, 6),
            "cxr_compare": round(cmp_cxr, 6),
            "structure_pp": round(structure_pp, 4),
            "efficiency_pp": round(efficiency_pp, 4),
        })

    # Verification: total_pp should ≈ overall CXR change
    total_pp = total_structure_pp + total_efficiency_pp

    # Compute actual overall CXR change for verification
    # weighted CXR = Σ(share × cxr)
    actual_cur_cxr = sum(d["dau_share_current"] * d["cxr_current"] for d in detail)
    actual_cmp_cxr = sum(d["dau_share_compare"] * d["cxr_compare"] for d in detail)
    actual_change_pp = (actual_cur_cxr - actual_cmp_cxr) * 100
    verification_error_pp = round(total_pp - actual_change_pp, 4)

    return {
        "structure_contribution_pp": round(total_structure_pp, 4),
        "efficiency_contribution_pp": round(total_efficiency_pp, 4),
        "total_pp": round(total_pp, 4),
        "verification_error_pp": verification_error_pp,
        "detail": sorted(detail, key=lambda x: abs(x["structure_pp"] + x["efficiency_pp"]), reverse=True),
    }


def compute_contributions(results: dict, mode: str = "device") -> dict:
    """
    在所有取数完成后，计算各维度的贡献度。

    返回结构：
    {
        "funnel": [...],                      # 漏斗贡献度（Path 5）
        "stp": {
            "by_user_type": {...},             # 按潜客/非潜客（Path 3）
            "by_device": {...},                # 按设备类型（Path 3 补充）
            "by_language": {...},              # 按语言（Path 3 补充）
        },
        "module_structure": {...},             # 模块结构贡献度（Path 4）
    }

    任何维度计算失败则对应字段为 None。
    """
    contributions = {}

    # ── 1. 漏斗贡献度（Path 5）──────────────────────────────────────
    try:
        contributions["funnel"] = _compute_funnel_contributions(results)
    except Exception as e:
        contributions["funnel"] = None
        print(f"[cxr_fetch] 漏斗贡献度计算失败: {e}", file=sys.stderr)

    # ── 2. STP 结构贡献度（Path 3 及补充）──────────────────────────
    stp = {}
    # 2a. 按用户分层
    try:
        if mode == "user":
            stp["by_user_type"] = _compute_stp_contributions(
                results, "traffic_structure", "upto_yesterday_user_layers_name",
                "davg_visit_usr_num", "davg_visit2ord_rate"
            )
        else:
            stp["by_user_type"] = _compute_stp_contributions(
                results, "traffic_structure", "user_finord_type_name",
                "davg_dau", "davg_visit_txn_ratio"
            )
    except Exception as e:
        stp["by_user_type"] = None
        print(f"[cxr_fetch] STP(user_type)贡献度计算失败: {e}", file=sys.stderr)

    # 2b. 按设备类型（iOS/Android）
    try:
        if mode == "user":
            stp["by_device"] = _compute_stp_contributions(
                results, "traffic_device", "os",
                "davg_visit_usr_num", "davg_visit2ord_rate"
            )
        else:
            stp["by_device"] = _compute_stp_contributions(
                results, "traffic_device", "os",
                "davg_dau", "davg_visit_txn_ratio"
            )
    except Exception as e:
        stp["by_device"] = None
        print(f"[cxr_fetch] STP(device)贡献度计算失败: {e}", file=sys.stderr)

    # 2c. 按语言
    try:
        if mode == "user":
            stp["by_language"] = _compute_stp_contributions(
                results, "traffic_language", "user_app_language_code",
                "davg_visit_usr_num", "davg_visit2ord_rate"
            )
        else:
            stp["by_language"] = _compute_stp_contributions(
                results, "traffic_language", "device_language_code",
                "davg_dau", "davg_visit_txn_ratio"
            )
    except Exception as e:
        stp["by_language"] = None
        print(f"[cxr_fetch] STP(language)贡献度计算失败: {e}", file=sys.stderr)

    # 2d. 按生命周期（仅 user 模式）
    if mode == "user":
        try:
            stp["by_lifecycle"] = _compute_stp_contributions(
                results, "traffic_lifecycle", "lifecycle_global_name",
                "davg_visit_usr_num", "davg_visit2ord_rate"
            )
        except Exception as e:
            stp["by_lifecycle"] = None
            print(f"[cxr_fetch] STP(lifecycle)贡献度计算失败: {e}", file=sys.stderr)

    contributions["stp"] = stp

    # 2e. 按 biz_type（Keemart/Keeta 拆分，仅 SA）
    try:
        biz_type_data = results.get("traffic_biz_type")
        if biz_type_data:
            if mode == "user":
                stp["by_biz_type"] = _compute_stp_contributions(
                    results, "traffic_biz_type", "biz_type",
                    "davg_visit_usr_num", "davg_visit2ord_rate"
                )
            else:
                stp["by_biz_type"] = _compute_stp_contributions(
                    results, "traffic_biz_type", "biz_type",
                    "davg_dau", "davg_visit_txn_ratio"
                )
        else:
            stp["by_biz_type"] = None
    except Exception as e:
        stp["by_biz_type"] = None
        print(f"[cxr_fetch] STP(biz_type)贡献度计算失败: {e}", file=sys.stderr)

    # 2f. 按 is_km_channel_user（keemart 内部外投渠道拆分，仅 SA）
    try:
        km_channel_data = results.get("traffic_km_channel")
        if km_channel_data:
            if mode == "user":
                stp["by_km_channel"] = _compute_stp_contributions(
                    results, "traffic_km_channel", "is_km_channel_user",
                    "davg_visit_usr_num", "davg_visit2ord_rate"
                )
            else:
                stp["by_km_channel"] = _compute_stp_contributions(
                    results, "traffic_km_channel", "is_km_channel_user",
                    "davg_dau", "davg_visit_txn_ratio"
                )
        else:
            stp["by_km_channel"] = None
    except Exception as e:
        stp["by_km_channel"] = None
        print(f"[cxr_fetch] STP(km_channel)贡献度计算失败: {e}", file=sys.stderr)

    # 2g-pre. 按区域等级（仅 BR）
    try:
        tier_data = results.get("traffic_tier")
        if tier_data:
            stp["by_tier"] = _compute_stp_contributions(
                results, "traffic_tier", "tier_name",
                "davg_visit_usr_num", "davg_visit2ord_rate"
            )
        else:
            stp["by_tier"] = None
    except Exception as e:
        stp["by_tier"] = None
        print(f"[cxr_fetch] STP(tier)贡献度计算失败: {e}", file=sys.stderr)

    # 2g-pre. 按业务城市（仅 AE/SA）
    try:
        city_data = results.get("traffic_city")
        if city_data:
            if mode == "user":
                stp["by_city"] = _compute_stp_contributions(
                    results, "traffic_city", "op_city_name",
                    "davg_visit_usr_num", "davg_visit2ord_rate"
                )
            else:
                stp["by_city"] = _compute_stp_contributions(
                    results, "traffic_city", "op_city_name",
                    "davg_dau", "davg_visit_txn_ratio"
                )
        else:
            stp["by_city"] = None
    except Exception as e:
        stp["by_city"] = None
        print(f"[cxr_fetch] STP(city)贡献度计算失败: {e}", file=sys.stderr)

    # ── 3. 模块结构贡献度（Path 4）─────────────────────────────────
    try:
        contributions["module_structure"] = _compute_stp_contributions(
            results, "module_cxr", "first_ad_position_name",
            "davg_module_exposure_uv", "davg_cxr_uv"
        )
    except Exception as e:
        contributions["module_structure"] = None
        print(f"[cxr_fetch] 模块结构贡献度计算失败: {e}", file=sys.stderr)

    # ── 4. 渠道贡献度（Path 1A）────────────────────────────────────
    # 分母：渠道 DAU；指标：渠道访购率（推算）
    # 注：62055197 与大盘口径不同，合计可能有偏差，消费时需注意
    try:
        dc = results.get("demand_channel")
        if dc:
            cur_rows = dc.get("cur", {}).get("rows", [])
            cmp_rows = dc.get("cmp", {}).get("rows", [])
            if cur_rows and cmp_rows:
                # 根据 mode 选择对应的 DAU 和交易指标
                _dau_field = "visit_usr_num" if mode == "user" else "app_uv"
                _txn_field = "fin_usr_num" if mode == "user" else "fin_ord_uv"

                def _inject_cxr(rows):
                    out = []
                    for row in rows:
                        r = dict(row)
                        uv = _safe_float(r.get(_dau_field))
                        txn = _safe_float(r.get(_txn_field))
                        r["_cxr_rate"] = (txn / uv * 100) if uv > 0 else 0.0
                        # 合成一级+二级渠道组合 key
                        p = r.get("primary_access_channel_code", "") or ""
                        s = r.get("secondary_visit_channel_code", "") or ""
                        r["_channel_key"] = f"{p}/{s}" if s else p
                        out.append(r)
                    return out

                dc_injected = {
                    "cur": {"rows": _inject_cxr(cur_rows)},
                    "cmp": {"rows": _inject_cxr(cmp_rows)},
                }
                contributions["demand_channel"] = _compute_stp_contributions(
                    {"demand_channel": dc_injected},
                    "demand_channel", "_channel_key",
                    _dau_field, "_cxr_rate"
                )
            else:
                contributions["demand_channel"] = None
        else:
            contributions["demand_channel"] = None
    except Exception as e:
        contributions["demand_channel"] = None
        print(f"[cxr_fetch] 渠道贡献度计算失败: {e}", file=sys.stderr)

    # ── 5. 补贴结构贡献度（Path 2）─────────────────────────────────
    # 分母：各分层实付交易额（actual_pay_no_tip_gmv）；指标：实付补贴率（actual_disc_ratio）
    subsidy_contrib = {}
    for task_name, group_col, label in [
        ("subsidy_sales_type", "sales_type_name", "by_sales_type"),
        ("subsidy_lifecycle", "lifecycle_global_name", "by_lifecycle"),
        ("subsidy_price_range", "actual_price_range_name", "by_price_range"),
    ]:
        try:
            _res = _compute_stp_contributions(
                results, task_name, group_col,
                "actual_pay_no_tip_gmv", "actual_disc_ratio"
            )
            # Fix C: 补贴分支传入的是补贴率(actual_disc_ratio)，通用函数把它存进了
            # cxr_current/cxr_compare 字段，语义上其实是补贴率。这里仅对补贴结构的
            # detail 重命名键名（数值不变），避免下游误标为 CXR。STP 漏斗调用不走此分支。
            if _res and _res.get("detail"):
                for _item in _res["detail"]:
                    if "cxr_current" in _item:
                        _item["subsidy_rate_current"] = _item.pop("cxr_current")
                    if "cxr_compare" in _item:
                        _item["subsidy_rate_compare"] = _item.pop("cxr_compare")
            subsidy_contrib[label] = _res
        except Exception as e:
            subsidy_contrib[label] = None
            print(f"[cxr_fetch] 补贴贡献度({label})计算失败: {e}", file=sys.stderr)
    contributions["subsidy_structure"] = subsidy_contrib if any(subsidy_contrib.values()) else None

    # ── 6. 下钻场景贡献度（--drilldown 模式）──────────────────────
    # 进店→提单页 入口CVR（store_to_order drilldown）
    try:
        s2o = results.get("drilldown_s2o_entry")
        if s2o:
            contributions["drilldown_entry_cvr"] = _compute_stp_contributions(
                results, "drilldown_s2o_entry",
                "ad_position_name",
                "davg_shop_entry_visit_uv",
                "davg_shop_entry_payment_cvr"
            )
        else:
            contributions["drilldown_entry_cvr"] = None
    except Exception as e:
        contributions["drilldown_entry_cvr"] = None
        print(f"[cxr_fetch] 下钻入口CVR贡献度计算失败: {e}", file=sys.stderr)

    # 商家类型下钻（shop_type）
    try:
        shop = results.get("drilldown_s2o_shop_type")
        if shop:
            contributions["drilldown_shop_type"] = _compute_stp_contributions(
                results, "drilldown_s2o_shop_type",
                "shop_type_name",
                "davg_shop_entry_visit_uv",
                "davg_shop_entry_payment_cvr"
            )
        else:
            contributions["drilldown_shop_type"] = None
    except Exception as e:
        contributions["drilldown_shop_type"] = None
        print(f"[cxr_fetch] 下钻商家类型贡献度计算失败: {e}", file=sys.stderr)

    # 用户分层下钻（uuid_layers）
    try:
        ulayer = results.get("drilldown_s2o_user_layer")
        if ulayer:
            contributions["drilldown_user_layer"] = _compute_stp_contributions(
                results, "drilldown_s2o_user_layer",
                "uuid_layers_3_name",
                "davg_shop_entry_visit_uv",
                "davg_shop_entry_payment_cvr"
            )
        else:
            contributions["drilldown_user_layer"] = None
    except Exception as e:
        contributions["drilldown_user_layer"] = None
        print(f"[cxr_fetch] 下钻用户分层贡献度计算失败: {e}", file=sys.stderr)

    return contributions


def format_comparison_table(path_data: dict, title: str = "") -> str:
    """将 cur/cmp 两组数据格式化为 Markdown 对比表格。"""
    cur = path_data.get("cur") or {}
    cmp = path_data.get("cmp") or {}

    if cur.get("error") and cmp.get("error"):
        return f"**{title}**: 查询失败\n- 本期: {cur['error']}\n- 对比期: {cmp['error']}\n"

    # 单行结果（无 group_by）
    cur_rows = cur.get("rows", [])
    cmp_rows = cmp.get("rows", [])

    if not cur_rows and not cmp_rows:
        return f"**{title}**: 无数据\n"

    columns = cur.get("columns") or cmp.get("columns") or []
    # 已知的维度列集合
    known_dim_set = {"user_finord_type_name", "first_ad_position_name",
                     "first_ad_position_id", "ad_position_page_name", "ad_position_name"}
    # 过滤掉分组维度以外的列，保留指标列
    metric_cols = [c for c in columns if c not in known_dim_set]
    dim_cols = [c for c in columns if c in known_dim_set and c not in ("first_ad_position_id",)]

    lines = [f"### {title}" if title else ""]

    # 检测是否为入口来源数据（含 ad_position_page_name + ad_position_name + 进店UV + 支付UV）
    is_entrance_data = ("ad_position_page_name" in columns and "ad_position_name" in columns
                        and "davg_shop_entry_visit_uv" in columns)

    if is_entrance_data:
        # 入口来源专用展示：页面×资源位 + 进店UV + 支付UV + CVR
        has_payment = "davg_shop_entry_payment_uv" in columns
        if has_payment:
            header = "| 页面 | 资源位 | 对比期进店UV | 对比期支付UV | 对比期CVR | 本期进店UV | 本期支付UV | 本期CVR | CVR变化 |"
            sep = "|---|---|---|---|---|---|---|---|---|"
        else:
            header = "| 页面 | 资源位 | 对比期进店UV | 本期进店UV | 变化 |"
            sep = "|---|---|---|---|---|"
        lines += [header, sep]

        # 构建 composite key → row 映射
        def _make_key(row):
            return (row.get("ad_position_page_name", ""), row.get("ad_position_name", ""))

        cur_map = {_make_key(r): r for r in cur_rows}
        cmp_map = {_make_key(r): r for r in cmp_rows}
        all_keys = list({**cur_map, **cmp_map}.keys())
        # 按本期进店UV降序
        try:
            all_keys.sort(key=lambda k: -float(cur_map.get(k, cmp_map.get(k, {})).get("davg_shop_entry_visit_uv", 0) or 0))
        except Exception:
            pass

        for key in all_keys[:30]:  # 展示top30
            cr = cur_map.get(key, {})
            cm = cmp_map.get(key, {})
            page_name, res_name = key

            cur_visit = float(cr.get("davg_shop_entry_visit_uv", 0) or 0)
            cmp_visit = float(cm.get("davg_shop_entry_visit_uv", 0) or 0)

            if has_payment:
                cur_pay = float(cr.get("davg_shop_entry_payment_uv", 0) or 0)
                cmp_pay = float(cm.get("davg_shop_entry_payment_uv", 0) or 0)
                cur_cvr = (cur_pay / cur_visit * 100) if cur_visit > 0 else 0
                cmp_cvr = (cmp_pay / cmp_visit * 100) if cmp_visit > 0 else 0
                cvr_change = cur_cvr - cmp_cvr
                lines.append(
                    f"| {page_name} | {res_name} "
                    f"| {cmp_visit:,.0f} | {cmp_pay:,.0f} | {cmp_cvr:.2f}% "
                    f"| {cur_visit:,.0f} | {cur_pay:,.0f} | {cur_cvr:.2f}% "
                    f"| {cvr_change:+.2f}pp |"
                )
            else:
                visit_change = cur_visit - cmp_visit
                lines.append(
                    f"| {page_name} | {res_name} "
                    f"| {cmp_visit:,.0f} | {cur_visit:,.0f} | {visit_change:+,.0f} |"
                )

    elif not dim_cols:
        # 无分组：生成纵向对比表
        header = "| 指标 | 对比期 | 本期 |"
        sep = "|---|---|---|"
        lines += [header, sep]
        cur_row = cur_rows[0] if cur_rows else {}
        cmp_row = cmp_rows[0] if cmp_rows else {}
        for col in metric_cols:
            cur_val = cur_row.get(col, "N/A")
            cmp_val = cmp_row.get(col, "N/A")
            lines.append(f"| {col} | {cmp_val} | {cur_val} |")
    else:
        # 有分组：生成横向表格（每行一个维度值）
        dim_col = dim_cols[0]
        header = f"| {dim_col} | 对比期 CXR | 对比期 DAU | 本期 CXR | 本期 DAU |"
        sep = "|---|---|---|---|---|"
        lines += [header, sep]
        # 以本期行为主
        cur_map = {r.get(dim_col, ""): r for r in cur_rows}
        cmp_map = {r.get(dim_col, ""): r for r in cmp_rows}
        all_dims = list({**cur_map, **cmp_map}.keys())
        # 按本期 DAU 降序
        try:
            all_dims.sort(key=lambda d: -float((cur_map.get(d) or cmp_map.get(d) or {}).get("davg_dau", 0) or 0))
        except Exception:
            pass
        for dim_val in all_dims[:20]:  # 最多展示20行
            cr = cur_map.get(dim_val, {})
            cm = cmp_map.get(dim_val, {})
            # 取第一个指标（CXR）和第二个（DAU）
            metric1 = metric_cols[0] if metric_cols else ""
            metric2 = metric_cols[1] if len(metric_cols) > 1 else ""
            lines.append(
                f"| {dim_val} "
                f"| {cm.get(metric1,'N/A')} | {cm.get(metric2,'N/A')} "
                f"| {cr.get(metric1,'N/A')} | {cr.get(metric2,'N/A')} |"
            )

    return "\n".join(lines) + "\n"


# ══════════════════════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════════════════════

def _slim_data(data: dict) -> dict:
    """精简 JSON：去掉元数据，减小文件体积，保留归因所需内容。"""
    slim = {}
    # 保留顶层关键字段
    for key in ["region", "mode", "date_cur", "date_cmp", "elapsed_total_s"]:
        if key in data:
            slim[key] = data[key]

    # 精简 results：只保留 rows，去掉 elapsed_s/error/total/columns/date
    if "results" in data:
        slim["results"] = {}
        for task_name, task_data in data["results"].items():
            slim_task = {}
            for period in ["cur", "cmp"]:
                if period in task_data:
                    p = task_data[period]
                    if p is None:
                        continue
                    slim_p = {}
                    if "rows" in p:
                        slim_p["rows"] = p["rows"]
                    if slim_p:
                        slim_task[period] = slim_p
            # 保留其他字段（如 group_by）
            for k, v in task_data.items():
                if k not in ("cur", "cmp"):
                    slim_task[k] = v
            slim["results"][task_name] = slim_task

    # 直接保留预计算结果（归因核心依赖）
    for key in ["contributions", "gate_checks", "baseline_health",
                "anomaly_day_check", "external_context"]:
        if key in data:
            slim[key] = data[key]

    return slim


# ── 广告影响评估集成 ───────────────────────────────────────────────────────

def _calc_cxr_wave_pp(data: dict) -> float | None:
    """从已取的 base 数据中提取大盘 CXR 波动值(pp)，用于广告主因判定。"""
    try:
        base = data["results"]["base"]
        cur_rows = base["cur"]["rows"]
        cmp_rows = base["cmp"]["rows"]
        # 设备口径 vs 用户口径
        cxr_field = None
        for field in ["davg_visit_txn_ratio", "davg_visit2ord_rate"]:
            if field in cur_rows[0]:
                cxr_field = field
                break
        if cxr_field is None:
            return None
        cxr_cur = float(cur_rows[0][cxr_field])
        cxr_cmp = float(cmp_rows[0][cxr_field])
        # 返回 pp（百分点）
        return (cxr_cur - cxr_cmp) * 100
    except (KeyError, IndexError, TypeError, ValueError):
        return None


# 广告影响评估仅支持的地区（已开广告）
_AD_IMPACT_REGIONS = {"HK", "SA", "QA"}


def _fetch_ad_impact(
    region: str,
    date_cur: str,
    date_cmp: str,
    cxr_wave_pp: float | None = None,
) -> dict | None:
    """
    调用 keeta-data-ad-analysis skill 的 ad_impact_fetch.py 获取广告影响评估结论。
    仅对 HK/SA/QA 执行广告查询，其他地区跳过。
    返回结果 dict 或 None（失败时降级不中断主流程）。
    """
    import subprocess

    if region.upper() not in _AD_IMPACT_REGIONS:
        print(f"[cxr_fetch] ℹ️ 广告影响评估跳过: {region} 未开广告", file=sys.stderr)
        return None

    ad_script = Path(__file__).resolve().parent.parent.parent / "keeta-data-ad-analysis" / "scripts" / "ad_impact_fetch.py"
    if not ad_script.exists():
        print(f"[cxr_fetch] ℹ️ 广告影响评估跳过: 未找到 {ad_script}", file=sys.stderr)
        return None

    cmd = [
        sys.executable, str(ad_script),
        "--region", region,
        "--date", date_cur,
        "--compare", date_cmp,
    ]
    if cxr_wave_pp is not None:
        cmd += ["--cxr-wave-pp", str(round(cxr_wave_pp, 4))]

    print(f"[cxr_fetch] 广告影响评估中 ...", file=sys.stderr)
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.time() - t0
        if result.returncode != 0:
            print(f"[cxr_fetch] ⚠️ 广告评估失败 (rc={result.returncode}, {elapsed:.1f}s): {result.stderr[:200]}", file=sys.stderr)
            return None
        # 解析 stdout JSON
        ad_data = json.loads(result.stdout)
        print(f"[cxr_fetch] ✅ 广告影响评估完成 ({elapsed:.1f}s)", file=sys.stderr)
        return ad_data
    except subprocess.TimeoutExpired:
        print(f"[cxr_fetch] ⚠️ 广告评估超时 (>120s)，跳过", file=sys.stderr)
        return None
    except (json.JSONDecodeError, Exception) as e:
        print(f"[cxr_fetch] ⚠️ 广告评估异常: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="CXR 访购率诊断并发取数",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 cxr_fetch.py --region QA --date 20260419 --compare 20260412
  python3 cxr_fetch.py --region SA --date 20260405~20260411 --compare 20260329~20260404
  python3 cxr_fetch.py --region HK --date 20260419 --compare 20260418 --out /tmp/result.json
  python3 cxr_fetch.py --region QA --date 20260419 --compare 20260412 --markdown
        """
    )
    parser.add_argument("--region", required=True, help="Region: SA/HK/QA/AE/KW/BH/BR")
    parser.add_argument("--date", required=True, help="本期日期，如 20260419 或 20260405~20260411")
    parser.add_argument("--compare", required=True, help="对比期日期，如 20260412 或 20260329~20260404")
    parser.add_argument("--out", help="输出 JSON 文件路径（不指定则输出到 stdout）")
    parser.add_argument("--mode", choices=["device", "user"], default="device",
                        help="分析口径：device（设备访购率，默认）| user（用户访购率）")
    parser.add_argument("--markdown", action="store_true", help="同时生成 Markdown 摘要表格")
    parser.add_argument("--dry-run", action="store_true", help="只输出待执行查询计划，不初始化鉴权或取数")
    parser.add_argument("--workers", type=int, default=12, help="并发线程数（默认 12）")
    parser.add_argument("--timeout", type=float, default=120.0, help="总超时秒数（默认 120）")
    parser.add_argument("--drilldown",
                        choices=["store_to_order", "order_to_submit", "all"],
                        default=None,
                        help="下钻取数模式：store_to_order（进店→提单页）/ order_to_submit（提单页→提单）/ all（全部）",
                        )
    parser.add_argument("--slim", action="store_true", help="精简 JSON：去掉元数据（elapsed_s/error/total/columns/date），减小文件体积")
    args = parser.parse_args()

    if args.dry_run:
        date_cur = args.date if "~" in args.date else f"{args.date}~{args.date}"
        date_cmp = args.compare if "~" in args.compare else f"{args.compare}~{args.compare}"
        tasks = _build_tasks(args.region.upper(), date_cur, date_cmp, mode=args.mode)
        if args.drilldown:
            tasks = tasks + _build_drilldown_tasks(args.region.upper(), args.drilldown)
        print(json.dumps({
            "status": "dry_run",
            "region": args.region.upper(),
            "mode": args.mode,
            "date_cur": date_cur,
            "date_cmp": date_cmp,
            "task_count": len(tasks),
            "tasks": tasks,
        }, ensure_ascii=False, indent=2))
        return

    data = fetch_all(
        region=args.region.upper(),
        date_cur=args.date,
        date_cmp=args.compare,
        max_workers=args.workers,
        timeout=args.timeout,
        drilldown_mode=args.drilldown,
        mode=args.mode,
    )

    # ── 广告影响评估（自动调用 keeta-data-ad-analysis skill）────────────────
    ad_impact_result = _fetch_ad_impact(
        region=args.region.upper(),
        date_cur=data["date_cur"],
        date_cmp=data["date_cmp"],
        cxr_wave_pp=_calc_cxr_wave_pp(data),
    )
    if ad_impact_result is not None:
        data["results"]["ad_impact"] = ad_impact_result

    # ── 检测缺失的依赖 skill ────────────────────────────────────────────
    missing_skills = []
    ext_ctx = data.get("external_context", {})
    if ext_ctx.get("_skill_missing"):
        missing_skills.append({
            "skill": "keeta-external-context",
            "impact": "外部环境分析（天气/节假日）不可用",
            "install_hint": "请在 Skill 广场搜索 'keeta-external-context' 安装",
        })
    if args.region.upper() in _AD_IMPACT_REGIONS and ad_impact_result is None:
        ad_script = Path(__file__).resolve().parent.parent.parent / "keeta-data-ad-analysis" / "scripts" / "ad_impact_fetch.py"
        if not ad_script.exists():
            missing_skills.append({
                "skill": "keeta-data-ad-analysis",
                "impact": "广告影响评估不可用",
                "install_hint": "请在 Skill 广场搜索 'keeta-data-ad-analysis' 安装",
            })
    if missing_skills:
        data["missing_skills"] = missing_skills

    # 输出 JSON — 始终写文件，stdout 只输出操作状态
    if args.slim:
        data = _slim_data(data)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    out_path = args.out or f"/tmp/cxr_{args.region}_{args.mode}.json"
    Path(out_path).write_text(json_str, encoding="utf-8")

    # stdout 精简状态（零原始数值，防止主 agent context 污染）
    ok_count = sum(1 for name in data.get("results", {}) if data["results"][name].get("cur") and not data["results"][name]["cur"].get("error"))
    total_count = len(data.get("results", {}))
    print(f"✅ 取数完成")
    print(f"   Region: {args.region} | Mode: {args.mode}")
    print(f"   本期: {data['date_cur']} | 对比期: {data['date_cmp']}")
    print(f"   路径: {ok_count}/{total_count} 成功 | 耗时: {data['elapsed_total_s']}s")
    if ad_impact_result is not None:
        ad_overall = ad_impact_result.get("overall", {})
        if ad_overall.get("skip"):
            print(f"   广告: 跳过 ({ad_overall.get('reason', 'Adload < 1%')})")
        else:
            print(f"   广告: ad_contribution={ad_overall.get('ad_contribution_pp')}pp | is_primary={ad_overall.get('is_primary_factor')}")
    else:
        print(f"   广告: 未获取（降级跳过）")
    print(f"   数据文件: {out_path}")
    if missing_skills:
        print(f"   ⚠️ 缺失依赖 skill:")
        for ms in missing_skills:
            print(f"      - {ms['skill']}: {ms['impact']}。{ms['install_hint']}")

    # 可选：输出 Markdown 摘要
    if args.markdown:
        md_lines = [
            f"# {args.region} CXR 取数摘要",
            f"本期：{data['date_cur']} ｜ 对比期：{data['date_cmp']}",
            f"总耗时：{data['elapsed_total_s']}s",
            "",
        ]
        labels = {
            "base": "大盘核心指标",
            "subsidy": "Path2 补贴价格",
            "traffic_structure": "Path3 流量结构",
            "module_cxr": "Path4 模块CXR",
            "funnel": "Path5 漏斗转化",
            "search": "Path1 搜索质量",
        }
        for name, title in labels.items():
            if name in data["results"]:
                md_lines.append(format_comparison_table(data["results"][name], title))

        # 下钻结果表格（如有）
        drilldown_labels = {
            "drilldown_s2o_merchant_type":      "下钻 进店→提单页 / 商家类型",
            "drilldown_s2o_merchant_category":  "下钻 进店→提单页 / 商家品类",
            "drilldown_s2o_user_segment":       "下钻 进店→提单页 / 用户分层",
            "drilldown_s2o_add_to_cart":        "下钻 进店→加购→提单页",
            "drilldown_s2o_promo_pv":           "下钻 店内优惠专区曝光",
            "drilldown_s2o_entrance":           "下钻 商家入口进店UV+支付UV+CVR（页面×资源位）",
            "drilldown_o2s_merchant_type":      "下钻 提单页→提单 / 商家类型",
            "drilldown_o2s_merchant_category":  "下钻 提单页→提单 / 商家品类",
            "drilldown_o2s_user_segment":       "下钻 提单页→提单 / 用户分层",
            "drilldown_o2s_submit_page_quality":"下钻 提单页质量指标",
        }
        has_drilldown = any(k in data["results"] for k in drilldown_labels)
        if has_drilldown:
            md_lines.append("\n## 下钻数据\n")
            for name, title in drilldown_labels.items():
                if name in data["results"]:
                    md_lines.append(format_comparison_table(data["results"][name], title))

        md_str = "\n".join(md_lines)
        md_path = out_path.replace(".json", ".md") if out_path.endswith(".json") else out_path + ".md"
        Path(md_path).write_text(md_str, encoding="utf-8")
        print(f"   Markdown: {md_path}")


if __name__ == "__main__":
    main()
