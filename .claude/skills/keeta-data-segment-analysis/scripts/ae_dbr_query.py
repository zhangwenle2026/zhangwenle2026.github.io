#!/usr/bin/env python3
"""
AE DBR 用户生命周期监控查询脚本（独立运行版）

用法:
  python3 ae_dbr_query.py                         # T1 = 昨天
  python3 ae_dbr_query.py --date 20260519         # 指定 T1
  python3 ae_dbr_query.py --date 20260519 --sql funnel,global  # 仅执行指定 SQL
  python3 ae_dbr_query.py --reset-config          # 清除项目组缓存，重新选择

输出:
  .artifacts/segment_analysis/{T1}/sql_{name}.csv

配置缓存:
  .artifacts/dbr_config.json  —  记录每条 SQL 选定的项目组

依赖（同 bi_client.py）:
  pip3 install requests python-dotenv browser-cookie3 keyring cryptography

鉴权（由 bi_client.BiClient 自动处理，三层回退）:
  1. mtsso-moa-local-exchange（MOA 已登录时最稳定）
  2. browser_cookie3（从本地浏览器 profile 读取）
  3. CDP WebSocket（浏览器运行时）
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ── 路径：bi_client.py 与本脚本同目录 ─────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from bi_client import BiClient  # noqa: E402
from skill_tracker import report_script  # noqa: E402

# ── 常量 ──────────────────────────────────────────────────────────────────────

REGION = "AE"
ALL_SQL_NAMES = ["funnel", "visit_old", "trade", "csub", "global", "sab"]
CONFIG_FILE = PROJECT_DIR / ".artifacts" / "dbr_config.json"


# ── 配置缓存 ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_config(config: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))


# ── 项目组管理 ────────────────────────────────────────────────────────────────

def list_projects(client: BiClient) -> list[tuple[str, str]]:
    """返回 [(name, id), ...] 的可用项目组列表。
    注意：spaces API 返回 个人空间 id=1，但 BiClient 个人空间用 id=0，此处统一映射为 '0'。
    """
    try:
        spaces = client.get_spaces()
        projects: list[tuple[str, str]] = []
        for group in spaces.get("data", []):
            children = group.get("children", [])
            items = children if children else [group]
            for p in items:
                pid = str(p.get("id", ""))
                name = str(p.get("name", ""))
                if not pid:
                    continue
                # 个人空间在 spaces API 里是 id=1，BiClient 用 "0" 表示个人空间
                if name == "个人空间":
                    pid = "0"
                projects.append((name, pid))
        return projects
    except Exception as e:
        print(f"⚠️  获取项目组列表失败：{e}", file=sys.stderr)
        return []


def prompt_select_project(projects: list[tuple[str, str]], prompt: str) -> tuple[str, str] | None:
    """打印项目组列表，提示用户选择，返回 (name, id)"""
    if not projects:
        return None
    print(f"\n{prompt}")
    for i, (name, pid) in enumerate(projects, 1):
        print(f"  {i}. {name}  (id={pid})")
    while True:
        try:
            raw = input(f"请输入序号 [1-{len(projects)}]，回车跳过: ").strip()
            if not raw:
                return None
            idx = int(raw) - 1
            if 0 <= idx < len(projects):
                return projects[idx]
        except (ValueError, EOFError):
            pass
        print("  输入无效，请重新输入")


def ensure_project_for_sql(
    sql_name: str,
    client: BiClient,
    projects: list[tuple[str, str]],
    config: dict,
) -> str | None:
    """
    返回该 SQL 应使用的 project_id（字符串）。
    优先级：config 缓存 > 用户交互选择 > None（使用 client 当前默认）
    """
    cached = config.get("sql_projects", {}).get(sql_name)
    if cached:
        name = config.get("project_names", {}).get(cached, cached)
        print(f"  [项目组] 使用缓存：{name}（id={cached}）")
        return cached

    # 没有缓存时，先用默认
    default_id = config.get("default_project")
    if default_id:
        name = config.get("project_names", {}).get(default_id, default_id)
        print(f"  [项目组] 使用默认：{name}（id={default_id}）")
        return default_id

    return None


def select_and_cache_default(client: BiClient, projects: list[tuple[str, str]], config: dict) -> str | None:
    """首次运行时询问用户选择默认项目组，写入缓存"""
    print("\n首次运行，未找到项目组配置。")
    result = prompt_select_project(projects, "请选择默认项目组（所有 SQL 的初始选择）：")
    if result:
        name, pid = result
        config["default_project"] = pid
        config.setdefault("project_names", {})[pid] = name
        save_config(config)
        print(f"  ✅ 已保存默认项目组：{name}（id={pid}）")
        return pid
    return None


class PermissionStop(Exception):
    """用户选择停止执行以申请权限时抛出"""


def extract_permission_info(result: dict) -> tuple[list[str], list[str]]:
    """从 submit_failed 的 detail 中提取（缺权限表名列表，申请链接列表）"""
    import re
    detail = result.get("detail") or {}
    if not isinstance(detail, dict):
        return [], []
    data = detail.get("data") or {}
    solve = (data.get("tableAuthResult") or {}).get("solvForTable") or []
    tables, urls = [], []
    for item in solve:
        db, tbl = item.get("db", ""), item.get("table", "")
        if db and tbl:
            tables.append(f"{db}.{tbl}")
        m = re.search(r'href="([^"]+)"', item.get("url", ""))
        if m:
            urls.append(m.group(1))
    return tables, urls


def handle_permission_error(
    sql_name: str,
    sql: str,
    client: BiClient,
    projects: list[tuple[str, str]],
    failed_id: str | None,
    config: dict,
    run_kwargs: dict,
    result: dict,
) -> dict:
    """
    权限不足时停止执行，展示缺权限表明细，询问用户：
      1. 选择其他项目组重试
      2. 停止执行并给出权限申请指引

    返回成功的 result（选项1成功时），否则抛出 PermissionStop。
    """
    tables, urls = extract_permission_info(result)

    print(f"\n  ❌ 权限不足，停止执行")
    print(f"  缺少以下表的访问权限：")
    for t in (tables or ["(未能解析表名，请查看详细错误)"]):
        print(f"    · {t}")

    other_projects = [(n, p) for n, p in projects if p != failed_id]

    print()
    print("  请选择处理方式：")
    if other_projects:
        print("    1. 切换项目组后重试")
    print("    2. 申请表权限（停止当前执行）")
    valid = (["1"] if other_projects else []) + ["2"]

    while True:
        try:
            choice = input(f"  请输入 [{'/'.join(valid)}]: ").strip()
        except EOFError:
            choice = "2"

        if choice == "1" and other_projects:
            sel = prompt_select_project(other_projects, "请选择要尝试的项目组：")
            if not sel:
                continue
            name, pid = sel
            print(f"  → 尝试 {name}（id={pid}）...")
            client.project_id = pid
            try:
                new_result = client.run_sql(sql=sql, **run_kwargs)
            except Exception as e:
                print(f"  → {name} 执行异常：{e}，请重新选择")
                continue
            if new_result.get("success"):
                print(f"  ✅ {name} 有权限")
                try:
                    raw = input(f"  是否将 '{sql_name}' 固定使用项目组 '{name}'？[y/N]: ").strip().lower()
                except EOFError:
                    raw = "y"
                if raw == "y":
                    config.setdefault("sql_projects", {})[sql_name] = pid
                    config.setdefault("project_names", {})[pid] = name
                    save_config(config)
                    print(f"  ✅ 已保存 {sql_name} → {name}")
                return new_result
            # 仍然权限不足，重新展示信息
            new_tables, new_urls = extract_permission_info(new_result)
            if new_tables or "权限" in str(new_result.get("detail", "")):
                print(f"  → {name} 仍权限不足，请重新选择")
                tables = new_tables or tables
                urls = new_urls or urls
            else:
                print(f"  → {name} 失败（{new_result.get('error')}），请重新选择")

        elif choice == "2":
            print()
            print("  请申请以下表的访问权限后重新运行：")
            for t in (tables or ["(请检查错误信息中的表名)"]):
                print(f"    · {t}")
            if urls:
                print()
                print("  权限申请链接：")
                for url in urls:
                    print(f"    {url}")
            else:
                print()
                print("  申请入口：http://data.sankuai.com/hetu/tableApply")
            raise PermissionStop(f"{sql_name}: {', '.join(tables)}")

        else:
            print(f"  输入无效，请输入 {'/'.join(valid)}")


# ── 日期计算 ──────────────────────────────────────────────────────────────────

def calc_dates(t1_str: str) -> tuple[str, str, str, str]:
    """返回 (T9, T8, T2, T1)"""
    t1 = date.fromisoformat(f"{t1_str[:4]}-{t1_str[4:6]}-{t1_str[6:]}")
    fmt = lambda d: d.strftime("%Y%m%d")
    return fmt(t1 - timedelta(days=8)), fmt(t1 - timedelta(days=7)), fmt(t1 - timedelta(days=1)), fmt(t1)


def yesterday() -> str:
    return (date.today() - timedelta(days=1)).strftime("%Y%m%d")


# ── SQL 定义 ──────────────────────────────────────────────────────────────────

def build_sqls(t9: str, t8: str, t2: str, t1: str, region: str = "AE") -> dict[str, str]:
    d = f"'{t9}','{t8}','{t2}','{t1}'"

    return {
        # SQL 1: 新客/潜客 Visit UV（O/S 用 first_channel_name）
        "funnel": f"""
WITH dedup AS (
  SELECT dt, user_id, user_layers_5_id, first_channel_name,
    ROW_NUMBER() OVER (PARTITION BY dt, user_id ORDER BY user_layers_5_id) AS rn
  FROM mart_sailor_global.topic_flow_user_txn_conversion_funnel_d
  WHERE dt IN ({d}) AND region='{region}'
)
SELECT dt,
  CASE user_layers_5_id WHEN 1 THEN 'new1st' WHEN 2 THEN 'newNon1st' END AS seg,
  CASE WHEN first_channel_name rlike '(?i)organic' THEN 1 ELSE 0 END AS is_org,
  COUNT(DISTINCT user_id) AS vuv
FROM dedup WHERE rn=1 AND user_layers_5_id IN (1,2)
GROUP BY dt,
  CASE user_layers_5_id WHEN 1 THEN 'new1st' WHEN 2 THEN 'newNon1st' END,
  CASE WHEN first_channel_name rlike '(?i)organic' THEN 1 ELSE 0 END
ORDER BY dt,
  CASE user_layers_5_id WHEN 1 THEN 'new1st' WHEN 2 THEN 'newNon1st' END,
  CASE WHEN first_channel_name rlike '(?i)organic' THEN 1 ELSE 0 END
""".strip(),

        # SQL 2: 老客 Visit UV（O/S 用 user_id % 10 = 0）
        "visit_old": f"""
WITH dedup AS (
  SELECT dt, user_id, user_layers_5_id,
    ROW_NUMBER() OVER (PARTITION BY dt, user_id ORDER BY user_layers_5_id) AS rn
  FROM mart_sailor_global.topic_flow_user_txn_conversion_funnel_d
  WHERE dt IN ({d}) AND region='{region}' AND user_layers_5_id NOT IN (1,2)
), seg_base AS (
  SELECT ul.dt, ul.user_id,
    CASE WHEN feat.l30d_fin_ord_cnt=0 OR feat.l30d_fin_ord_cnt IS NULL THEN 'lapsed'
         WHEN feat.accu_fin_ord_num BETWEEN 1 AND 4 THEN '1to4'
         WHEN feat.accu_fin_ord_num>=5 THEN '5plus'
         ELSE 'lapsed' END AS seg
  FROM dedup ul
  LEFT JOIN mart_sailor_global.topic_usr_feature_d feat
    ON CAST(ul.user_id AS BIGINT)=feat.user_id
    AND feat.dt=DATE_FORMAT(DATE_ADD(DATE_PARSE(ul.dt,'%Y%m%d'),-1),'%Y%m%d')
    AND feat.region='{region}'
  WHERE ul.rn=1
)
SELECT sb.dt, sb.seg,
  CASE WHEN CAST(sb.user_id AS BIGINT)%10=0 THEN 1 ELSE 0 END AS is_org,
  COUNT(DISTINCT sb.user_id) AS vuv
FROM seg_base sb
GROUP BY sb.dt, sb.seg,
  CASE WHEN CAST(sb.user_id AS BIGINT)%10=0 THEN 1 ELSE 0 END
ORDER BY sb.dt, sb.seg, is_org
""".strip(),

        # SQL 3: 各分层 Order UV/订单量/AOV/美补率（O/S 拆分）
        "trade": f"""
WITH us AS (
  SELECT ul.dt, ul.user_id,
    CASE WHEN ul.user_layers_5_id=1 THEN 'new1st'
         WHEN ul.user_layers_5_id=2 THEN 'newNon1st'
         WHEN feat.l30d_fin_ord_cnt=0 OR feat.l30d_fin_ord_cnt IS NULL THEN 'lapsed'
         WHEN feat.accu_fin_ord_num BETWEEN 1 AND 4 THEN '1to4'
         WHEN feat.accu_fin_ord_num>=5 THEN '5plus'
         ELSE 'lapsed' END AS seg
  FROM (
    SELECT dt, user_id, user_layers_5_id,
      ROW_NUMBER() OVER (PARTITION BY dt, user_id ORDER BY user_layers_5_id) AS rn
    FROM mart_sailor_global.topic_flow_user_txn_conversion_funnel_d
    WHERE dt IN ({d}) AND region='{region}'
  ) ul
  LEFT JOIN mart_sailor_global.topic_usr_feature_d feat
    ON CAST(ul.user_id AS BIGINT)=feat.user_id
    AND feat.dt=DATE_FORMAT(DATE_ADD(DATE_PARSE(ul.dt,'%Y%m%d'),-1),'%Y%m%d')
    AND feat.region='{region}'
  WHERE ul.rn=1
)
SELECT o.dt, us.seg,
  CASE WHEN CAST(o.user_id AS BIGINT)%10=0 THEN 'O' ELSE 'S' END AS os,
  COUNT(DISTINCT o.user_id) AS ouv,
  COUNT(DISTINCT o.order_view_id) AS ord_cnt,
  ROUND(SUM(o.fin_actual_amt_no_tip/100.0)/NULLIF(COUNT(DISTINCT o.order_view_id),0),2) AS aov,
  ROUND(SUM(o.mt_charge_fee/100.0)/NULLIF(SUM(o.fin_actual_amt_no_tip/100.0),0)*100,2) AS sub
FROM mart_sailor_global.topic_ord_order_promotion_info_d o
INNER JOIN us ON CAST(o.user_id AS BIGINT)=CAST(us.user_id AS BIGINT) AND o.dt=us.dt
WHERE o.dt IN ({d}) AND o.region='{region}' AND o.is_pickup=0
GROUP BY o.dt, us.seg,
  CASE WHEN CAST(o.user_id AS BIGINT)%10=0 THEN 'O' ELSE 'S' END
ORDER BY o.dt, us.seg,
  CASE WHEN CAST(o.user_id AS BIGINT)%10=0 THEN 'O' ELSE 'S' END
""".strip(),

        # SQL 4: C补率分子（按分层，PN 码为 AE region 专用）
        "csub": f"""
WITH us AS (
  SELECT ul.dt, ul.user_id,
    CASE WHEN ul.user_layers_5_id=1 THEN 'new1st'
         WHEN ul.user_layers_5_id=2 THEN 'newNon1st'
         WHEN feat.l30d_fin_ord_cnt=0 OR feat.l30d_fin_ord_cnt IS NULL THEN 'lapsed'
         WHEN feat.accu_fin_ord_num BETWEEN 1 AND 4 THEN '1to4'
         WHEN feat.accu_fin_ord_num>=5 THEN '5plus'
         ELSE 'lapsed' END AS seg
  FROM (
    SELECT dt, user_id, user_layers_5_id,
      ROW_NUMBER() OVER (PARTITION BY dt, user_id ORDER BY user_layers_5_id) AS rn
    FROM mart_sailor_global.topic_flow_user_txn_conversion_funnel_d
    WHERE dt IN ({d}) AND region='{region}'
  ) ul
  LEFT JOIN mart_sailor_global.topic_usr_feature_d feat
    ON CAST(ul.user_id AS BIGINT)=feat.user_id
    AND feat.dt=DATE_FORMAT(DATE_ADD(DATE_PARSE(ul.dt,'%Y%m%d'),-1),'%Y%m%d')
    AND feat.region='{region}'
  WHERE ul.rn=1
)
SELECT a.dt, us.seg, SUM(b.mt_charge_fee/100.0) AS c_sub
FROM mart_sailor_global.topic_ord_order_promotion_info_d a
INNER JOIN (
  SELECT dt, order_view_id, SUM(mt_charge_fee) AS mt_charge_fee
  FROM mart_sailor_global.fact_act_order_promotion_d
  WHERE dt IN ({d}) AND region='{region}'
    AND mt_charge_pn IN (
      'PN2576E9CS06242G','PN254G6A3S062439','PN2572094S06244C',
      'PN255B35GS06245B','PN2520A5DS062463'
    )
  GROUP BY dt, order_view_id
) b ON a.dt=b.dt AND a.order_view_id=b.order_view_id
INNER JOIN us ON CAST(a.user_id AS BIGINT)=CAST(us.user_id AS BIGINT) AND a.dt=us.dt
WHERE a.dt IN ({d}) AND a.region='{region}' AND a.is_pickup=0
GROUP BY a.dt, us.seg
ORDER BY a.dt, us.seg
""".strip(),

        # SQL 5: 全量 Order UV/订单量/AOV/美补率（C补率分母）
        "global": f"""
SELECT dt,
  COUNT(DISTINCT user_id) AS ouv,
  COUNT(DISTINCT order_view_id) AS ord,
  ROUND(SUM(fin_actual_amt_no_tip/100.0)/NULLIF(COUNT(DISTINCT order_view_id),0),2) AS aov,
  ROUND(SUM(mt_charge_fee/100.0)/NULLIF(SUM(fin_actual_amt_no_tip/100.0),0)*100,2) AS sub
FROM mart_sailor_global.topic_ord_order_promotion_info_d
WHERE dt IN ({d}) AND region='{region}' AND is_pickup=0
GROUP BY dt
ORDER BY dt
""".strip(),

        # SQL 6: SAB 漏斗（VUV/OUV，SAB 快照用 T1）
        "sab": f"""
WITH sab AS (
  SELECT DISTINCT user_id, sab_level_1
  FROM mart_sailor_algorithm.aggr_user_sab_level_manual_result_ae_d
  WHERE dt='{t1}' AND region='{region}'
), fn AS (
  SELECT dt, user_id, finish_user_id
  FROM mart_sailor_global.topic_flow_user_txn_conversion_funnel_d
  WHERE dt IN ({d}) AND region='{region}'
)
SELECT f.dt,
  COALESCE(s.sab_level_1,'Unknown') AS lvl,
  COUNT(DISTINCT f.user_id) AS vuv,
  COUNT(DISTINCT f.finish_user_id) AS ouv
FROM fn f
LEFT JOIN sab s ON CAST(f.user_id AS BIGINT)=s.user_id
GROUP BY f.dt, COALESCE(s.sab_level_1,'Unknown')
ORDER BY f.dt, COALESCE(s.sab_level_1,'Unknown')
""".strip(),
    }


# ── 结果保存 ──────────────────────────────────────────────────────────────────

def save_csv(result: dict, out_path: Path) -> int:
    columns = result.get("columns", [])
    rows = result.get("data", [])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            if isinstance(row, dict):
                writer.writerow([row.get(c, "") for c in columns])
            else:
                writer.writerow(row)
    return len(rows)


# ── 自检 ──────────────────────────────────────────────────────────────────────

def selfcheck_visit_old(csv_path: Path, t1: str) -> bool:
    if not csv_path.exists():
        return True
    s_5plus = o_5plus = 0
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("dt") == t1 and row.get("seg") == "5plus":
                vuv = int(row.get("vuv", 0) or 0)
                if row.get("is_org") == "0":
                    s_5plus = vuv
                elif row.get("is_org") == "1":
                    o_5plus = vuv
    total = s_5plus + o_5plus
    if total == 0:
        print("  [selfcheck] ⚠️  5plus 数据为空，跳过", file=sys.stderr)
        return True
    ratio = s_5plus / total
    if ratio < 0.80:
        print(
            f"  [selfcheck] ❌ 5+ Strategy {ratio:.1%}（S={s_5plus:,}, O={o_5plus:,}）\n"
            "              O/S 口径可能用错：老客应用 user_id%10=0",
            file=sys.stderr,
        )
        return False
    print(f"  [selfcheck] ✅ 5+ Strategy {ratio:.1%}（S={s_5plus:,}, O={o_5plus:,}）")
    return True


# ── C 补率 ────────────────────────────────────────────────────────────────────

def calc_c_sub_rates(csub_csv: Path, global_csv: Path) -> dict[str, str]:
    if not csub_csv.exists() or not global_csv.exists():
        return {}
    gmv: dict[str, float] = {}
    with open(global_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                gmv[row["dt"]] = float(row["aov"]) * int(row["ord"])
            except (ValueError, KeyError):
                pass
    # csub 按 seg 分组，先聚合到 dt 级
    c_sub_by_dt: dict[str, float] = {}
    with open(csub_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dt = row.get("dt", "")
            try:
                c_sub_by_dt[dt] = c_sub_by_dt.get(dt, 0.0) + float(row.get("c_sub", 0) or 0)
            except (ValueError, KeyError):
                pass
    rates: dict[str, str] = {}
    for dt, c_sub in c_sub_by_dt.items():
        total = gmv.get(dt, 0)
        rates[dt] = f"{c_sub / total * 100:.2f}%" if total > 0 else "—"
    return rates


# ── 报告生成 ──────────────────────────────────────────────────────────────────

def _fv(v: float | None, decimals: int = 2, is_pct: bool = False) -> str:
    """格式化数值：None → —，整数 count → 千分位整数，AOV 等小数保留 decimals 位，比率加 %"""
    if v is None:
        return "—"
    if is_pct:
        return f"{v:.{decimals}f}%"
    if v >= 1000 or (v == int(v) and decimals == 0):
        return f"{int(v):,}"
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:.{decimals}f}"


def _pct(new_v: float | None, old_v: float | None) -> str:
    """百分比变化：(new-old)/old，适用于绝对量"""
    if new_v is None or old_v is None or old_v == 0:
        return "—"
    return f"{(new_v - old_v) / old_v * 100:+.1f}%"


def _pp(new_v: float | None, old_v: float | None) -> str:
    """百分点变化：适用于补贴率等已是百分比的指标"""
    if new_v is None or old_v is None:
        return "—"
    return f"{new_v - old_v:+.2f}pp"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fv_num(s: str | None) -> float | None:
    try:
        return float(s) if s not in (None, "", "—") else None
    except ValueError:
        return None


def build_report(out_dir: Path, t9: str, t8: str, t2: str, t1: str) -> str:
    """
    读取所有 SQL 结果 CSV，计算 DoD（t1 vs t2）/ WoW（t1 vs t8）。
    格式：分层×渠道 为行，各指标为子行，4个日期 + DoD + WoW 为列。
    """
    dates = [t9, t8, t2, t1]

    def row(*cells: str) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    # ── 加载所有数据源 ────────────────────────────────────────────────────────
    global_rows = {r["dt"]: r for r in _read_csv(out_dir / "sql_global.csv")}

    # csub 按 seg 分组后加载，同时聚合到 dt 级用于大盘 C补率
    csub_seg: dict[tuple, float] = {}   # (seg, dt) -> c_sub
    csub_dt:  dict[str, float]   = {}   # dt -> total c_sub
    for r in _read_csv(out_dir / "sql_csub.csv"):
        c = _fv_num(r.get("c_sub")) or 0.0
        csub_seg[(r.get("seg", ""), r["dt"])] = c
        csub_dt[r["dt"]] = csub_dt.get(r["dt"], 0.0) + c

    # VUV: {(seg, channel): {dt: float}}  channel = "S"/"O"
    vuv: dict[tuple, dict[str, float | None]] = {}
    for r in _read_csv(out_dir / "sql_funnel.csv"):
        ch = "O" if r["is_org"] == "1" else "S"
        vuv.setdefault((r["seg"], ch), {})[r["dt"]] = _fv_num(r.get("vuv"))
    for r in _read_csv(out_dir / "sql_visit_old.csv"):
        ch = "O" if r["is_org"] == "1" else "S"
        vuv.setdefault((r["seg"], ch), {})[r["dt"]] = _fv_num(r.get("vuv"))

    # Trade: {(seg, channel, dt): {ouv, ord_cnt, aov, sub}}
    trade: dict[tuple, dict] = {}
    for r in _read_csv(out_dir / "sql_trade.csv"):
        trade[(r["seg"], r["os"], r["dt"])] = r

    # SAB: {(lvl, dt): {vuv, ouv}}
    sab: dict[tuple, dict] = {}
    sab_lvls: list[str] = []
    for r in _read_csv(out_dir / "sql_sab.csv"):
        k = (r["lvl"], r["dt"])
        sab[k] = r
        if r["lvl"] not in sab_lvls:
            sab_lvls.append(r["lvl"])

    ALL_SEGS = ["new1st", "newNon1st", "5plus", "1to4", "lapsed"]

    def c_rate(dt: str) -> float | None:
        g = global_rows.get(dt, {})
        aov, ord_ = _fv_num(g.get("aov")), _fv_num(g.get("ord"))
        total_c = csub_dt.get(dt, 0)
        if aov and ord_ and aov * ord_ > 0 and total_c > 0:
            return total_c / (aov * ord_) * 100
        return None

    def _sum2(a: float | None, b: float | None) -> float | None:
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    def _w_aov(seg: str, dt: str) -> float | None:
        s = trade.get((seg, "S", dt), {})
        o = trade.get((seg, "O", dt), {})
        as_, os_ = _fv_num(s.get("aov")), _fv_num(s.get("ord_cnt"))
        ao, oo  = _fv_num(o.get("aov")), _fv_num(o.get("ord_cnt"))
        if as_ and os_ and ao and oo:
            return (as_ * os_ + ao * oo) / (os_ + oo)
        return as_ or ao or None

    def _w_sub(seg: str, dt: str) -> float | None:
        s = trade.get((seg, "S", dt), {})
        o = trade.get((seg, "O", dt), {})
        ss, as_, os_ = _fv_num(s.get("sub")), _fv_num(s.get("aov")), _fv_num(s.get("ord_cnt"))
        so, ao, oo  = _fv_num(o.get("sub")), _fv_num(o.get("aov")), _fv_num(o.get("ord_cnt"))
        if ss and so and as_ and ao and os_ and oo:
            rs, ro = as_ * os_, ao * oo
            return (ss * rs + so * ro) / (rs + ro) if (rs + ro) > 0 else None
        return ss or so or None

    def _seg_gmv(seg: str, dt: str) -> float | None:
        s = trade.get((seg, "S", dt), {})
        o = trade.get((seg, "O", dt), {})
        as_, os_ = _fv_num(s.get("aov")), _fv_num(s.get("ord_cnt"))
        ao, oo   = _fv_num(o.get("aov")), _fv_num(o.get("ord_cnt"))
        gmv = ((as_ * os_) if as_ and os_ else 0.0) + ((ao * oo) if ao and oo else 0.0)
        return gmv if gmv > 0 else None

    def _c_rate_seg(seg: str, dt: str) -> float | None:
        c_sub = csub_seg.get((seg, dt))
        gmv = _seg_gmv(seg, dt)
        if c_sub is not None and gmv and gmv > 0:
            return c_sub / gmv * 100
        return None

    def _cvr(ouv: float | None, vuv_: float | None) -> float | None:
        if ouv is not None and vuv_ is not None and vuv_ > 0:
            return ouv / vuv_ * 100
        return None

    # ── 构建统一宽表 ──────────────────────────────────────────────────────────
    # 表头：分层 | 指标 | t9 | t8 | t2 | t1 | DoD | WoW
    NCOL = 8
    hdr = row("分层", "指标", t9, t8, t2, t1, "DoD", "WoW")
    sep_line = "| " + " | ".join(["---"] * NCOL) + " |"
    lines = [hdr, sep_line]

    def add_rows(seg_label: str, metrics: list[tuple], first_idx: int = 0) -> None:
        """
        metrics: [(label, vs, is_rate), ...]
        first_idx: 第几行显示 seg_label（0=第一行）
        """
        for i, (metric_label, vs, is_rate) in enumerate(metrics):
            sl = seg_label if i == first_idx else ""
            dod = _pp(vs[3], vs[2]) if is_rate else _pct(vs[3], vs[2])
            wow = _pp(vs[3], vs[1]) if is_rate else _pct(vs[3], vs[1])
            fmt = [_fv(v, is_pct=is_rate) for v in vs]
            lines.append(row(sl, metric_label, *fmt, dod, wow))

    # ── 大盘 ─────────────────────────────────────────────────────────────────
    if global_rows:
        def _g_vuv_ch(ch: str, dt: str) -> float | None:
            vals = [vuv.get((s, ch), {}).get(dt) for s in ALL_SEGS]
            vals = [v for v in vals if v is not None]
            return sum(vals) if vals else None

        def _g_ord_ch(ch: str, dt: str) -> float | None:
            vals = [_fv_num(trade.get((s, ch, dt), {}).get("ord_cnt")) for s in ALL_SEGS]
            vals = [v for v in vals if v is not None]
            return sum(vals) if vals else None

        g_vuv_s = [_g_vuv_ch("S", d) for d in dates]
        g_vuv_o = [_g_vuv_ch("O", d) for d in dates]
        g_vuv   = [_sum2(s, o) for s, o in zip(g_vuv_s, g_vuv_o)]
        g_ord_s = [_g_ord_ch("S", d) for d in dates]
        g_ord_o = [_g_ord_ch("O", d) for d in dates]

        g_metrics = [
            ("visit UV",   g_vuv,                                                             False),
            ("  · S",      g_vuv_s,                                                           False),
            ("  · O",      g_vuv_o,                                                           False),
            ("Order UV",   [_fv_num(global_rows.get(d, {}).get("ouv")) for d in dates],       False),
            ("订单量",      [_fv_num(global_rows.get(d, {}).get("ord")) for d in dates],       False),
            ("  · S",      g_ord_s,                                                           False),
            ("  · O",      g_ord_o,                                                           False),
            ("AOV (AED)",  [_fv_num(global_rows.get(d, {}).get("aov")) for d in dates],       False),
            ("美补率",      [_fv_num(global_rows.get(d, {}).get("sub")) for d in dates],       True),
            ("C补率",       [c_rate(d) for d in dates],                                        True),
        ]
        add_rows("大盘", g_metrics)

    # ── 生命周期各分层：合计 + O/S 子行 ──────────────────────────────────────
    SEG_DISPLAY = {
        "new1st":    "新客首单",
        "newNon1st": "新客非首单",
        "5plus":     "成熟用户(5+单)",
        "1to4":      "尝鲜用户(1-4单)",
        "lapsed":    "沉流用户",
    }
    SEG_ORDER = ["new1st", "newNon1st", "5plus", "1to4", "lapsed"]

    for seg in SEG_ORDER:
        seg_label = SEG_DISPLAY[seg]
        seg_rows: list[tuple] = []

        # Visit UV
        s_vuv = [vuv.get((seg, "S"), {}).get(d) for d in dates]
        o_vuv = [vuv.get((seg, "O"), {}).get(d) for d in dates]
        t_vuv = [_sum2(s, o) for s, o in zip(s_vuv, o_vuv)]
        seg_rows += [("Visit UV", t_vuv, False), ("  · S", s_vuv, False), ("  · O", o_vuv, False)]

        # Order UV
        s_ouv = [_fv_num(trade.get((seg, "S", d), {}).get("ouv")) for d in dates]
        o_ouv = [_fv_num(trade.get((seg, "O", d), {}).get("ouv")) for d in dates]
        t_ouv = [_sum2(s, o) for s, o in zip(s_ouv, o_ouv)]
        seg_rows += [("Order UV", t_ouv, False), ("  · S", s_ouv, False), ("  · O", o_ouv, False)]

        # 订单量
        s_ord = [_fv_num(trade.get((seg, "S", d), {}).get("ord_cnt")) for d in dates]
        o_ord = [_fv_num(trade.get((seg, "O", d), {}).get("ord_cnt")) for d in dates]
        t_ord = [_sum2(s, o) for s, o in zip(s_ord, o_ord)]
        seg_rows += [("订单量", t_ord, False), ("  · S", s_ord, False), ("  · O", o_ord, False)]

        # CVR = orderUV / visitUV
        t_cvr = [_cvr(t_ouv[i], t_vuv[i]) for i in range(4)]
        s_cvr = [_cvr(s_ouv[i], s_vuv[i]) for i in range(4)]
        o_cvr = [_cvr(o_ouv[i], o_vuv[i]) for i in range(4)]
        seg_rows += [("CVR", t_cvr, True), ("  · S", s_cvr, True), ("  · O", o_cvr, True)]

        # AOV
        s_aov = [_fv_num(trade.get((seg, "S", d), {}).get("aov")) for d in dates]
        o_aov = [_fv_num(trade.get((seg, "O", d), {}).get("aov")) for d in dates]
        t_aov = [_w_aov(seg, d) for d in dates]
        seg_rows += [("AOV (AED)", t_aov, False), ("  · S", s_aov, False), ("  · O", o_aov, False)]

        # 美补率
        s_sub = [_fv_num(trade.get((seg, "S", d), {}).get("sub")) for d in dates]
        o_sub = [_fv_num(trade.get((seg, "O", d), {}).get("sub")) for d in dates]
        t_sub = [_w_sub(seg, d) for d in dates]
        seg_rows += [("美补率", t_sub, True), ("  · S", s_sub, True), ("  · O", o_sub, True)]

        # C补率（分层级，无 O/S 拆分）
        seg_rows.append(("C补率", [_c_rate_seg(seg, d) for d in dates], True))

        add_rows(seg_label, seg_rows)

    # ── SAB 漏斗 ─────────────────────────────────────────────────────────────
    if sab:
        for lvl in sab_lvls:
            label = f"SAB-{lvl}"
            v_vuv = [_fv_num(sab.get((lvl, d), {}).get("vuv")) for d in dates]
            v_ouv = [_fv_num(sab.get((lvl, d), {}).get("ouv")) for d in dates]
            add_rows(label, [
                ("Visit UV",  v_vuv, False),
                ("Order UV",  v_ouv, False),
            ])

    # ── 输出 ─────────────────────────────────────────────────────────────────
    report = (
        f"# AE DBR 用户生命周期监控  region=AE\n\n"
        f"**查询日期**：{t9} / {t8} / {t2} / {t1}  "
        f"| **DoD** = {t1} vs {t2}  | **WoW** = {t1} vs {t8}\n\n"
        f"> O/S 口径：新客首单/非首单 = first_channel_name rlike organic；"
        f"成熟/尝鲜/沉流 = user_id%10=0｜SAB 快照日期：{t1}\n\n"
        + "\n".join(lines)
    )

    report_path = out_dir / f"report_{t1}.md"
    report_path.write_text(report, encoding="utf-8")
    return report


# ── 摘要打印 ──────────────────────────────────────────────────────────────────

def _print_summary(
    summary: list[dict],
    t1: str,
    out_dir: Path,
    dates_label: dict[str, str] | None = None,
) -> None:
    print(f"\n{'─' * 60}")
    print(f"执行摘要  region={REGION}  T1={t1}")
    print(f"{'─' * 60}")
    icons = {"ok": "✅", "permission": "🔒", "failed": "❌", "exception": "💥"}
    for r in summary:
        icon = icons.get(r["status"], "❓")
        note = f"  [{r['note']}]" if r["note"] and r["status"] != "ok" else ""
        print(f"  {icon} {r['name']:12s}  {r['rows']:>5} 行{note}")

    rates = calc_c_sub_rates(out_dir / "sql_csub.csv", out_dir / "sql_global.csv")
    if rates:
        print("\nC 补率（csub / global GMV）：")
        for dt in sorted(rates):
            label = (dates_label or {}).get(dt, dt)
            print(f"  {label}({dt}): {rates[dt]}")

    ok = sum(1 for r in summary if r["status"] == "ok")
    print(f"{'─' * 60}")
    print(f"共 {len(summary)} 条，成功 {ok} 条  输出：{out_dir}")
    if CONFIG_FILE.exists():
        print(f"配置缓存：{CONFIG_FILE}")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AE DBR 用户生命周期监控查询",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--date", default=None, help="T1 日期 YYYYMMDD（默认昨天）")
    parser.add_argument("--sql", default=None,
                        help=f"仅执行指定 SQL，逗号分隔，可选：{','.join(ALL_SQL_NAMES)}")
    parser.add_argument("--out-dir", default=None, help="输出目录（默认 .artifacts/segment_analysis/{T1}/）")
    parser.add_argument("--reset-config", action="store_true",
                        help="清除项目组缓存，重新选择")
    args = parser.parse_args()

    t1_input = args.date or yesterday()
    t9, t8, t2, t1 = calc_dates(t1_input)
    print(f"DBR 查询参数：region={REGION}  T9={t9}  T8={t8}  T2={t2}  T1={t1}")

    out_dir = Path(args.out_dir) if args.out_dir else PROJECT_DIR / ".artifacts" / "segment_analysis" / t1
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录：{out_dir}")

    sql_names = ALL_SQL_NAMES
    if args.sql:
        requested = [s.strip() for s in args.sql.split(",")]
        unknown = [s for s in requested if s not in ALL_SQL_NAMES]
        if unknown:
            print(f"⚠️  未知 SQL 名称（忽略）：{unknown}", file=sys.stderr)
        sql_names = [s for s in requested if s in ALL_SQL_NAMES]

    sqls = build_sqls(t9, t8, t2, t1, region=REGION)

    # ── 初始化 BiClient + 项目组配置 ─────────────────────────────────────────
    client = BiClient()
    config = {} if args.reset_config else load_config()
    projects = list_projects(client)

    if not projects:
        print("⚠️  无法获取项目组列表，将使用个人空间", file=sys.stderr)

    # 首次运行（无缓存）时询问默认项目组
    if projects and "default_project" not in config:
        select_and_cache_default(client, projects, config)

    print()

    # ── 执行 SQL ──────────────────────────────────────────────────────────────
    run_kwargs = dict(spark_queue=None, limit=10000, timeout=600.0)
    summary: list[dict] = []

    def report_query_node(
        sql_name: str,
        status: str,
        elapsed_sec: float,
        rows: int = 0,
        note: str = "",
        query_id: str | int = "",
    ) -> None:
        params = {
            "script": "ae_dbr_query.py",
            "region": REGION,
            "date": t1,
            "sql": sql_name,
        }
        output = {
            "status": status,
            "rows": rows,
        }
        if query_id:
            output["query_id"] = str(query_id)
        if note:
            output["note"] = note[:120]
        # tracking: scripts/ae_dbr_query.py::report_query_node::skill-script
        report_script(
            params=json.dumps(params, ensure_ascii=False),
            output=json.dumps(output, ensure_ascii=False),
            cost_ms=int(elapsed_sec * 1000),
            success=(status == "ok"),
            error_msg="" if status == "ok" else note[:200],
        )

    def report_gate_node(
        gate_name: str,
        success: bool,
        elapsed_sec: float,
        note: str = "",
    ) -> None:
        params = {
            "script": "ae_dbr_query.py",
            "region": REGION,
            "date": t1,
            "node": "gate_check",
            "gate": gate_name,
        }
        output = {
            "status": "ok" if success else "failed",
            "gate": gate_name,
        }
        if note:
            output["note"] = note[:200]
        # tracking: scripts/ae_dbr_query.py::report_gate_node::skill-script
        report_script(
            params=json.dumps(params, ensure_ascii=False),
            output=json.dumps(output, ensure_ascii=False),
            cost_ms=int(elapsed_sec * 1000),
            success=success,
            error_msg="" if success else note[:200],
        )

    def report_report_node(
        success: bool,
        elapsed_sec: float,
        report_path: Path,
        note: str = "",
    ) -> None:
        params = {
            "script": "ae_dbr_query.py",
            "region": REGION,
            "date": t1,
            "node": "build_report",
        }
        output = {
            "status": "ok" if success else "failed",
            "report_path": str(report_path),
        }
        if note:
            output["note"] = note[:200]
        # tracking: scripts/ae_dbr_query.py::report_report_node::skill-script
        report_script(
            params=json.dumps(params, ensure_ascii=False),
            output=json.dumps(output, ensure_ascii=False),
            cost_ms=int(elapsed_sec * 1000),
            success=success,
            error_msg="" if success else note[:200],
        )

    for name in sql_names:
        sql = sqls[name]
        out_path = out_dir / f"sql_{name}.csv"
        print(f"[{name}] 提交查询...")

        # 决定本次使用的 project_id
        proj_id = ensure_project_for_sql(name, client, projects, config)
        if proj_id:
            client.project_id = proj_id

        t_start = time.monotonic()
        try:
            result = client.run_sql(sql=sql, resource_name=f"dbr_{name}_{t1}", **run_kwargs)
        except Exception as e:
            elapsed = round(time.monotonic() - t_start, 1)
            print(f"[{name}] ❌ 异常（{elapsed}s）：{e}")
            summary.append({"name": name, "status": "exception", "rows": 0, "note": str(e)[:120]})
            report_query_node(name, "exception", elapsed, note=str(e))
            continue

        elapsed = round(time.monotonic() - t_start, 1)

        if not result.get("success"):
            detail = result.get("detail") or {}
            detail_msg = detail.get("message", "") if isinstance(detail, dict) else ""
            detail_code = detail.get("code", 0) if isinstance(detail, dict) else 0
            is_permission_err = (
                detail_code == 40016
                or "权限" in detail_msg
                or "不属于项目组" in detail_msg
                or (result.get("error") == "submit_failed" and
                    ("权限" in str(detail) or "不属于项目组" in str(detail)))
            )

            if is_permission_err:
                active_entry: dict = {"name": name, "status": "permission", "rows": 0, "note": detail_msg}
                summary.append(active_entry)
                try:
                    result = handle_permission_error(
                        name, sql, client, projects, proj_id, config, run_kwargs, result
                    )
                    elapsed = round(time.monotonic() - t_start, 1)
                    # 重试成功：直接更新 active_entry，不再走后面的 append
                    n = save_csv(result, out_path)
                    print(f"[{name}] ✅ {n} 行  ({elapsed}s)  → {out_path.name}")
                    active_entry.update({"status": "ok", "rows": n, "note": ""})
                    report_query_node(name, "ok", elapsed, rows=n, query_id=result.get("query_id", ""))
                    if name == "visit_old":
                        selfcheck_visit_old(out_path, t1)
                    continue
                except PermissionStop as e:
                    print(f"\n已停止执行（等待权限申请）")
                    report_query_node(name, "permission", elapsed, note=str(e))
                    _print_summary(summary, t1, out_dir,
                                   dates_label={t9: "T9", t8: "T8", t2: "T2", t1: "T1"})
                    sys.exit(0)
            else:
                err = result.get("error", "")
                msg = detail_msg or str(result.get("problem", ""))
                print(f"[{name}] ❌ 失败（{elapsed}s）：{err}  {msg}")
                summary.append({"name": name, "status": "failed", "rows": 0, "note": f"{err}: {msg}"[:120]})
                report_query_node(name, "failed", elapsed, note=f"{err}: {msg}")
                continue

        if not result.get("success"):
            # handle_permission_error 切换项目组后仍然失败（不应到达这里）
            summary[-1]["status"] = "failed"
            report_query_node(name, "failed", elapsed, note="query result is not successful")
            continue

        n = save_csv(result, out_path)
        print(f"[{name}] ✅ {n} 行  ({elapsed}s)  → {out_path.name}")
        summary.append({"name": name, "status": "ok", "rows": n, "note": ""})
        report_query_node(name, "ok", elapsed, rows=n, query_id=result.get("query_id", ""))

        if name == "visit_old":
            selfcheck_visit_old(out_path, t1)

    _print_summary(summary, t1, out_dir, dates_label={t9: "T9", t8: "T8", t2: "T2", t1: "T1"})

    # ── Gate Check（必须在 report 生成之前）────────────────────────────────────
    # 正确顺序：先 gate，全部通过后再生成 report。
    # 若先生成 report 再检查 gate，弱模型看到 report 输出后可能忽略后续非零退出码。
    #
    # 退出码约定：
    #   0 = 全部通过，report 已生成
    #   1 = Gate 失败（数据质量问题，禁止输出业务结论）
    #   2 = 部分 SQL 失败（查询未完成，禁止输出业务结论）
    # 每条失败都打印 [GATE FAIL] 标记行，方便模型定位原因。

    gate_start = time.monotonic()

    # G1：部分 SQL 失败，退出码 2
    failed_sqls = [r["name"] for r in summary if r["status"] != "ok"]
    if failed_sqls:
        gate_message = (
            f"[GATE FAIL] G1 SQL 完整性：{len(failed_sqls)} 条 SQL 未成功"
            f"（{', '.join(failed_sqls)}），禁止输出业务结论。"
        )
        print(gate_message, file=sys.stderr)
        report_gate_node("G1 SQL 完整性", False, time.monotonic() - gate_start, gate_message)
        sys.exit(2)

    # G2/G3/G4：数据质量检测，退出码 1
    gate_passed = _run_gate_checks(summary, out_dir, t1)
    if not gate_passed:
        report_gate_node(
            "G2/G3/G4 数据质量",
            False,
            time.monotonic() - gate_start,
            "G2/G3/G4 gate check failed; see stderr [GATE FAIL] lines",
        )
        sys.exit(1)
    report_gate_node("G2/G3/G4 数据质量", True, time.monotonic() - gate_start)

    # ── 全部 Gate 通过后，生成 DoD/WoW 分析报告 ──────────────────────────────
    ok_names = {r["name"] for r in summary if r["status"] == "ok"}
    if ok_names & {"global", "funnel", "visit_old"}:
        report_path = out_dir / f"report_{t1}.md"
        report_start = time.monotonic()
        try:
            report = build_report(out_dir, t9, t8, t2, t1)
        except Exception as e:
            report_report_node(False, time.monotonic() - report_start, report_path, str(e))
            raise
        report_report_node(True, time.monotonic() - report_start, report_path)
        print()
        print(report)
        print(f"\n📄 报告已保存：{report_path}")


def _run_gate_checks(summary: list[dict], out_dir: Path, t1: str) -> bool:
    """
    执行所有 Gate Check，返回 True（全部通过）或 False（至少一项失败）。
    失败时打印 [GATE FAIL] 标记行到 stderr，供模型定位原因。
    """
    passed = True

    # ── G2：空分区检测 ────────────────────────────────────────────────────────
    # 核心 CSV 中 T1 日期必须有数据行，否则可能查到空分区
    core_csvs = ["funnel", "global", "trade"]
    for name in core_csvs:
        csv_path = out_dir / f"sql_{name}.csv"
        if not csv_path.exists():
            continue  # SQL 未执行，由 G1 负责
        t1_rows = 0
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("dt") == t1:
                    t1_rows += 1
        if t1_rows == 0:
            print(
                f"[GATE FAIL] G2 空分区检测：{name} CSV 中 T1={t1} 无数据行，"
                f"可能查到空分区或日期参数错误。",
                file=sys.stderr,
            )
            passed = False

    # ── G3：O/S 自检 ──────────────────────────────────────────────────────────
    # 5+ Strategy VUV 占 5+ 总量应 ≥ 80%；若接近 0 说明老客 O/S 口径混用
    visit_old_csv = out_dir / "sql_visit_old.csv"
    if visit_old_csv.exists():
        ok = selfcheck_visit_old(visit_old_csv, t1)
        if not ok:
            print(
                f"[GATE FAIL] G3 O/S 自检失败：5+ Strategy VUV 占比 < 80%，"
                f"老客 O/S 口径可能混用了 first_channel_name，"
                f"应使用 user_id % 10 = 0 判断 Organic。",
                file=sys.stderr,
            )
            passed = False

    # ── G4：C 补率范围检测 ────────────────────────────────────────────────────
    # C 补率正常范围约 10%~15%；< 1% 或 > 20% 说明 csub SQL 口径有问题
    csub_csv  = out_dir / "sql_csub.csv"
    global_csv = out_dir / "sql_global.csv"
    if csub_csv.exists() and global_csv.exists():
        c_rates = calc_c_sub_rates(csub_csv, global_csv)
        for dt, rate_str in c_rates.items():
            if rate_str == "—":
                continue
            try:
                rate = float(rate_str.rstrip("%"))
            except ValueError:
                continue
            if rate < 1.0:
                print(
                    f"[GATE FAIL] G4 C补率过低：dt={dt} C补率={rate_str}（< 1%），"
                    f"请检查 SQL 4 csub 是否 INNER JOIN 主表并过滤 is_pickup=0。",
                    file=sys.stderr,
                )
                passed = False
            elif rate > 20.0:
                print(
                    f"[GATE FAIL] G4 C补率过高：dt={dt} C补率={rate_str}（> 20%），"
                    f"请检查 SQL 4 csub JOIN 条件，确认已先聚合到订单级再 JOIN。",
                    file=sys.stderr,
                )
                passed = False

    if passed:
        print("[GATE OK] G2/G3/G4 全部通过")

    return passed


if __name__ == "__main__":
    main()
