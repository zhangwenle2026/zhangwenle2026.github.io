#!/usr/bin/env python3
"""kdata - Keeta 统一数据查询 CLI

用法：
  kdata standard datasets
  kdata standard measures --dataset 60049761 [--search 订单]
  kdata standard dims --dataset 60049761
  kdata standard dim-values op_city_id [--search Riyadh]  # dim_code 须先用 dims 确认
  kdata standard query --dataset 60049761 --measures fin_ord_num --date 20260615 --region HK [--pops wow]
  kdata standard apply --dataset 60049761 --measures fin_ord_num,gmv

  kdata table search mart_sailor_global
  kdata table info mart_sailor_global.topic_ord_info_d

  kdata hive run "SELECT * FROM mart_sailor_global.topic_ord_info_d LIMIT 10"
  kdata hive submit "SELECT ..." [--queue default]
  kdata hive status <query_id>
  kdata hive result <query_id>
  kdata hive spaces
  kdata hive queues

  kdata dataset list
  kdata dataset info 300046295 [300046740]

  kdata template list [--shared] [--managed]
  kdata template show 300046740 [300046295]

"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shlex
import sys
import tempfile
import time

# ── 模块路径 ─────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.realpath(__file__))
# 确保脚本所在目录本身在 sys.path
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)
for _sub in ["core", "capability1_standard", "capability2_hive",
             "capability5_meta"]:
    _p = os.path.join(_DIR, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── 统一路径解析（从 __file__ 自推导，不依赖硬编码前缀）────────────────────
from core.bootstrap import check_deps as _check_deps
from core.bootstrap import cmd_init, ensure_cli_installed as _ensure_cli_installed
from capability1_standard import mtcli_standard_client as standard_cli
from capability2_hive.hive_client import BI_BASE as _HIVE_BI_BASE


# ══════════════════════════════════════════════════════════════════════════════
# [TRACKING] CLI 日志上报 — 通过 core/task.py + mtcli kdata log log-report
# ══════════════════════════════════════════════════════════════════════════════

# 从 core 包导入 task 模块（用包路径避免与 capability5_meta/auth.py 冲突）
try:
    from core.task import (
        get_active_task as _get_active_task,
        touch_task as _touch_task,
        report_cli_command as _report_cli_command,
        cmd_task_start as _cmd_task_start,
        cmd_task_input as _cmd_task_input,
        cmd_task_end as _cmd_task_end,
        cmd_task_status as _cmd_task_status,
        cmd_feedback as _cmd_feedback,
        _get_mis as _task_get_mis,
    )
    _CORE_IMPORTED = True
except ImportError as _e:
    import sys as _sys
    print(f"[kdata][WARN] core 模块导入失败，日志上报已禁用: {_e}", file=_sys.stderr)
    _CORE_IMPORTED = False

    def _report_cli_command(*_args, **kwargs):
        cli_command = str(kwargs.get("cli_command", ""))[:80]
        success = kwargs.get("success")
        status = "SUCCESS" if success is True else "FAIL" if success is False else "UNKNOWN"
        print(f"[kdata][WARN] 跳过日志上报（core 未导入）: cmd={cli_command!r} status={status}", file=_sys.stderr)

    def _cmd_task_start(args):
        import uuid as _uuid
        user_input = getattr(args, "input", "") or ""
        if not user_input:
            print("❌ 请通过 --input 提供用户原始问题", file=_sys.stderr)
            sys.exit(1)
        task_id = str(_uuid.uuid4())
        print(f"task_id={task_id}")
        print("[task][WARN] core 未导入，仅生成 ID，未上报日志", file=_sys.stderr)

    def _cmd_task_input(args):
        user_input = getattr(args, "input", "") or ""
        if not user_input:
            print("❌ 请通过 --input 提供用户输入", file=_sys.stderr)
            sys.exit(1)
        print("[task][WARN] core 未导入，跳过 input 上报", file=_sys.stderr)

    def _cmd_task_end(_args):
        print("[task][WARN] core 未导入，跳过 end", file=_sys.stderr)

    def _cmd_task_status(_args):
        print("(core 未导入，无法查询)")

    def _cmd_feedback(_args):
        print("[feedback][WARN] core 未导入，跳过反馈上报", file=_sys.stderr)


def _get_current_mis() -> str:
    """获取当前用户 MIS（via core.mis / mtcli kdata log get-mis）。"""
    if _CORE_IMPORTED:
        return _task_get_mis()
    for key in ("KDATA_MIS", "OPENCLAW_MIS", "MEITUAN_MIS"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


def _normalise_argv(argv: list[str]) -> tuple[list[str], bool]:
    """Move global flags accepted anywhere to the root parser position."""
    json_enabled = False
    cleaned = []
    for item in argv:
        if item == "--json":
            json_enabled = True
            continue
        cleaned.append(item)
    if json_enabled:
        cleaned.insert(0, "--json")
    return cleaned, json_enabled


def _build_cli_command(args, argv: list[str] | None = None) -> str:
    """Build the command recorded in cliCommand from the original argv."""
    raw_argv = list(argv if argv is not None else getattr(args, "_raw_argv", []) or sys.argv[1:])
    if not raw_argv:
        raw_argv = [getattr(args, "group", "")]
    parts = ["kdata"] + raw_argv
    return " ".join(shlex.quote(str(p)) for p in parts if str(p))


def _unset_proxy():
    """默认 unset HTTP 代理，避免内网调用被代理拦截"""
    for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)


# ══════════════════════════════════════════════════════════════════════════════
# table 子命令
# ══════════════════════════════════════════════════════════════════════════════

def _cmd_table_search(args):
    from capability5_meta.table import search_tables
    results = search_tables(args.keyword, page_size=args.size, include_columns=False)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"共找到 {len(results)} 张表：")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['name']}  [{r['dsn']}]  {r['comment']}")
            if r.get('owner'):
                print(f"     负责人: {r['owner']}")


def _cmd_table_info(args):
    from capability5_meta.table import get_table_info
    info = get_table_info(args.table)
    if not info:
        print(f"未找到表: {args.table}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"表名: {info['name']}")
        print(f"DSN:  {info['dsn']}")
        print(f"描述: {info['comment']}")
        print(f"负责人: {info['owner']}")
        cols = info.get('columns', [])
        print(f"\n字段 ({len(cols)} 个):")
        for c in cols:
            tags = (' [分区]' if c['is_partition'] else '') + (' ★' if c['is_important'] else '')
            print(f"  {c['name']} ({c['type']}){tags}")
            if c['comment']:
                print(f"    └ {c['comment']}")


# ══════════════════════════════════════════════════════════════════════════════
# hive 子命令（代理给 keeta_bi_skill 的 cmd_* 函数）
# ══════════════════════════════════════════════════════════════════════════════

def _auto_sql_to_file(sql_or_file: str) -> str:
    """
    自动将 SQL 文本转为临时文件路径。
    
    逻辑：
      1. 如果 sql_or_file 是已存在的文件路径，直接返回
      2. 否则将其视为 SQL 文本，创建临时文件并返回路径
    
    这个函数确保 CLI 总是以文件形式提交 SQL，避免命令行长度限制。
    """
    candidate = os.path.expanduser(sql_or_file.strip())
    if os.path.isfile(candidate):
        return candidate
    
    # 创建临时文件，使用 .sql 扩展名以便调试时易于识别
    tmp_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.sql', delete=False, encoding='utf-8'
    )
    try:
        tmp_file.write(sql_or_file)
        tmp_file.flush()
        return tmp_file.name
    finally:
        tmp_file.close()


_HIVE_DEFAULTS = dict(
    base_url=_HIVE_BI_BASE,
    project="0",
    engine="onesql",
    ds_name="dw_hive",
    stat_ds="DW_ONESQL_DB_CONNECT_URL",
    resource_name="新查询",
    resource_owner="",
    entrance=None,
    filter_relation_type="AND",
    filter_type="EQ",
    json_output=False,
)


def _hive_ns(**kwargs) -> argparse.Namespace:
    ns = argparse.Namespace(**_HIVE_DEFAULTS)
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def _hive_runner(command_name: str, kwargs_builder):
    def _runner(args):
        module = importlib.import_module("keeta_bi_skill")
        ns = _hive_ns(**kwargs_builder(args))
        sys.exit(getattr(module, command_name)(ns))
    _runner.__name__ = f"_hive_{command_name}"
    return _runner


def _hive_submit_kwargs(args):
    return {
        "sql_or_file": _auto_sql_to_file(args.sql),
        "queue": args.queue or "default",
        "project": args.project,
        "json_output": args.json,
    }


def _hive_run_kwargs(args):
    kwargs = _hive_submit_kwargs(args)
    kwargs.update(
        limit=args.limit,
        poll_interval=5,
        timeout=300,
    )
    return kwargs


# ── capability5_meta 命令函数 ─────────────────────────────────────────────────

def _meta_runner(module_name: str):
    def _runner(args):
        module = importlib.import_module(f"capability5_meta.{module_name}")
        module.run(args)
    _runner.__name__ = f"_meta_{module_name}"
    return _runner

def _cmd_meta_auth(args):
    _p = os.path.join(_DIR, "capability5_meta")
    if _p not in sys.path: sys.path.insert(0, _p)
    from capability5_meta.auth_check import run
    run(
        fix=getattr(args, "fix", False),
        check_only=getattr(args, "check", False),
        targets=getattr(args, "targets", None) or None,
        as_json=getattr(args, "json", False),
    )


def _moshu_module():
    return importlib.import_module("moshu.mtcli_resources")


def _cmd_dataset_list(args):
    args.page_num = getattr(args, "page_num", 1)
    args.page_size = getattr(args, "page_size", 50)
    args.query = getattr(args, "query", "")
    return _moshu_module().cmd_dataset_list(args)


def _cmd_dataset_info(args):
    return _moshu_module().cmd_dataset_info(args)


def _cmd_template_list(args):
    args.query = getattr(args, "query", "")
    args.project_id = getattr(args, "project_id", getattr(args, "project", ""))
    return _moshu_module().cmd_template_list(args)


def _cmd_template_show(args):
    moshu = _moshu_module()
    for template_id in args.ids:
        detail = moshu.get_template_detail(template_id, ver_no=getattr(args, "ver_no", "1"))
        if args.json:
            print(json.dumps(detail, ensure_ascii=False, indent=2))
        else:
            print(moshu.format_template_detail(detail))
            print()

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kdata",
        description="Keeta 统一数据查询 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--with-proxy", action="store_true", help="保留 HTTP 代理环境变量（默认自动 unset）")
    parser.add_argument("--locale", default="zh", help="语言枚举: zh / en / pt-BR，默认 zh（所有接口 header 必传）")
    parser.add_argument("--task-id", default="", help="任务 ID（UUID），用于日志关联；不传则自动从 session state 读取")
    parser.add_argument("--task-name", default="", help="任务描述（用户原始输入），用于日志记录；不传则自动从 session state 读取")

    sub = parser.add_subparsers(dest="group", required=True)

    # ── standard ──────────────────────────────────────────────────────────────
    p_std = sub.add_parser("standard", help="起源标准数据集查询")
    std_sub = p_std.add_subparsers(dest="cmd", required=True)

    p_ds2 = std_sub.add_parser("datasets", help="列出所有数据集")
    p_ds2.add_argument("--region", default=None, help="兼容旧参数；当前数据集列表不需要 region，传入会被忽略")
    p_ds2.add_argument("--full", action="store_true", help="JSON 模式输出完整 measureCodeList/dimCodeList")
    p_ds2.set_defaults(func=standard_cli.cmd_datasets)

    p_m = std_sub.add_parser("measures", help="列出数据集指标")
    p_m.add_argument("--dataset", "-d", required=True, help="数据集 ID")
    p_m.add_argument("--search", "-s", help="关键词过滤")
    p_m.add_argument("--region", default=None, help="兼容旧参数；当前指标列表不需要 region，传入会被忽略")
    p_m.set_defaults(func=standard_cli.cmd_measures)

    p_dim = std_sub.add_parser("dims", help="列出数据集维度")
    p_dim.add_argument("--dataset", "-d", required=True)
    p_dim.add_argument("--search", "-s", help="关键词过滤")
    p_dim.add_argument("--region", default=None, help="兼容旧参数；当前维度列表不需要 region，传入会被忽略")
    p_dim.set_defaults(func=standard_cli.cmd_dims)

    p_dv = std_sub.add_parser("dim-values", help="查询维度的可选值；dim_code 须先用 dims 命令确认")
    p_dv.add_argument("dim_code", help="维度 code（须先用 dims 确认），如 global_region_code、city_id")
    p_dv.add_argument("--search", "-s", help="关键词过滤（按 label 或 value）")
    p_dv.add_argument("--region", default=None, help="兼容旧参数；当前维值列表不需要 region，传入会被忽略")
    p_dv.set_defaults(func=standard_cli.cmd_dim_values)

    p_q = std_sub.add_parser("query", help="查询数据")
    p_q.add_argument("--dataset", "-d", required=True, help="数据集 ID")
    p_q.add_argument("--measures", "-m", required=True, nargs="+", help="指标 code，支持逗号分隔")
    p_q.add_argument("--date", required=True, help="日期或范围，必须为 yyyyMMdd 或 yyyyMMdd~yyyyMMdd，如 20260615 或 20260314~20260320")
    p_q.add_argument("--filter", "-f", action="append", help="维度过滤，格式 code=value，可多次")
    p_q.add_argument("--group-by", "-g", help="分组维度，逗号分隔，如 dt,region_code")
    p_q.add_argument("--order-by", help="排序，如 dt=ASC")
    p_q.add_argument("--pops", help="环比同比，逗号分隔，如 wow,dod")
    p_q.add_argument("--proportion", nargs="+", help="计算占比的指标 code（可多次或逗号分隔），在结果中插入 {measure}_proportion 列")
    p_q.add_argument("--gini", nargs="+", help="计算波动贡献基尼系数的指标 code（可多次或逗号分隔），自动带上 --fluctuation，需配合 --group-by 使用")
    p_q.add_argument("--gini-mode", default="normalized", choices=["standard", "normalized", "both"], help="基尼系数模式：normalized（默认，输出 {measure}_{pop}_normalized_gini）/ standard（输出 {measure}_{pop}_gini）/ both")
    p_q.add_argument("--fluctuation", nargs="+", help="计算波动贡献的指标 code，需配合 --pops 使用，插入 {measure}_{pop}_fluctuation_value 列")
    p_q.add_argument("--fluctuation-mode", default="auto", choices=["auto", "additive", "deduplicative", "ratio"], help="波动贡献计算模式：auto（默认，从指标元数据自动判断）/ additive / deduplicative / ratio")
    p_q.add_argument("--fluctuation-components", action="append", metavar="RATIO=NUM/DEN", help="比值型指标的分子/分母，格式 visit_order_rate=fin_ord_num/visit_user_num，可多次指定")
    p_q.add_argument("--region", help="地区 code，必须指定（HK/SA/AE/QA/KW/BR/BH）")
    p_q.add_argument("--page-size", type=int, default=1000)
    p_q.set_defaults(func=standard_cli.cmd_query)

    p_apply = std_sub.add_parser("apply", help="生成指标权限申请链接")
    p_apply.add_argument("--dataset", "-d", required=True, help="数据集 ID")
    p_apply.add_argument("--measures", "-m", required=True, nargs="+",
                         help="指标 code，支持空格分隔或逗号分隔，如 fin_ord_num gmv 或 fin_ord_num,gmv")
    p_apply.set_defaults(func=standard_cli.cmd_apply)

    # ── table ─────────────────────────────────────────────────────────────────
    p_tbl = sub.add_parser("table", help="Hive 表搜索")
    tbl_sub = p_tbl.add_subparsers(dest="cmd", required=True)

    p_ts = tbl_sub.add_parser("search", help="搜表")
    p_ts.add_argument("keyword", help="搜索关键词或表名")
    p_ts.add_argument("--size", type=int, default=10, help="返回条数，默认 10")
    p_ts.set_defaults(func=_cmd_table_search)

    p_ti = tbl_sub.add_parser("info", help="查表字段/结构")
    p_ti.add_argument("table", help="表名，格式 schema.table")
    p_ti.set_defaults(func=_cmd_table_info)

    # ── hive ──────────────────────────────────────────────────────────────────
    p_hive = sub.add_parser("hive", help="Hive SQL 执行（通过魔数引擎）")
    hive_sub = p_hive.add_subparsers(dest="cmd", required=True)

    hive_sub.add_parser("spaces", help="列出可用工作空间").set_defaults(
        func=_hive_runner("cmd_spaces", lambda args: {"json_output": args.json})
    )
    hive_sub.add_parser("queues", help="列出可用队列").set_defaults(
        func=_hive_runner("cmd_queues", lambda args: {"json_output": args.json})
    )

    p_hr = hive_sub.add_parser("run", help="提交 SQL 并等待结果")
    p_hr.add_argument("sql", help="SQL 语句")
    p_hr.add_argument("--queue", help="队列名称，默认 default")
    p_hr.add_argument("--limit", type=int, default=1000, help="返回行数上限")
    p_hr.add_argument("--project", "-p", default="0", help="项目 ID 或名称（0=个人空间）")
    p_hr.set_defaults(func=_hive_runner("cmd_run", _hive_run_kwargs))

    p_hs = hive_sub.add_parser("submit", help="异步提交 SQL，返回 query_id")
    p_hs.add_argument("sql", help="SQL 语句")
    p_hs.add_argument("--queue", help="队列名称，默认 default")
    p_hs.add_argument("--project", "-p", default="0", help="项目 ID 或名称（0=个人空间）")
    p_hs.set_defaults(func=_hive_runner("cmd_submit", _hive_submit_kwargs))

    p_hst = hive_sub.add_parser("status", help="查询执行状态")
    p_hst.add_argument("query_id", help="query_id")
    p_hst.set_defaults(
        func=_hive_runner("cmd_status", lambda args: {"query_id": args.query_id, "json_output": args.json})
    )

    p_hres = hive_sub.add_parser("result", help="拉取执行结果")
    p_hres.add_argument("query_id", help="query_id")
    p_hres.add_argument("--limit", type=int, default=1000)
    p_hres.set_defaults(
        func=_hive_runner(
            "cmd_result",
            lambda args: {"query_id": args.query_id, "limit": args.limit, "json_output": args.json},
        )
    )

    # ── dataset（魔数个人数据集，内部走 mtcli kdata moshu）──────────────────────
    p_ds = sub.add_parser("dataset", help="魔数个人数据集元信息")
    ds_sub = p_ds.add_subparsers(dest="cmd", required=True)

    p = ds_sub.add_parser("list", help="列出所有数据集")
    p.add_argument("--query", default="", help="搜索关键词")
    p.add_argument("--page-num", type=int, default=1)
    p.add_argument("--page-size", type=int, default=50)
    p.set_defaults(func=_cmd_dataset_list)

    p = ds_sub.add_parser("info", help="查数据集详情（指标/维度/SQL）")
    p.add_argument("ids", nargs="+", help="数据集 subjectId，支持多个")
    p.set_defaults(func=_cmd_dataset_info)

    # ── template（魔数 SQL 模板，内部走 mtcli kdata moshu）─────────────────────
    p_tmpl = sub.add_parser("template", help="魔数 SQL 模板")
    tmpl_sub = p_tmpl.add_subparsers(dest="cmd", required=True)

    p = tmpl_sub.add_parser("list", help="列出所有 SQL 模板")
    p.add_argument("--query", "-q", default="", help="搜索关键词")
    p.add_argument("--managed", action="store_true", help="查询管理模板")
    p.add_argument("--shared", action="store_true", help="查询共享模板")
    p.add_argument("--project", dest="project_id", default="", metavar="ID", help="指定项目空间 ID")
    p.set_defaults(func=_cmd_template_list)

    p = tmpl_sub.add_parser("show", help="查看模板详情（含 SQL）")
    p.add_argument("ids", nargs="+", help="模板 ID，支持多个")
    p.add_argument("--ver-no", default="1", help="模板版本号，默认 1")
    p.set_defaults(func=_cmd_template_show)

    # ── meta（找表 / 指标血缘 / ETL / Hive血缘）─────────────────────
    p_meta = sub.add_parser("meta", help="元数据查询（找表/ETL/指标血缘/Hive血缘）")
    meta_sub = p_meta.add_subparsers(dest="cmd", required=True)

    # meta table bi
    p_meta_tbl = meta_sub.add_parser("table", help="找表（bi/rag/etl）")
    meta_tbl_sub = p_meta_tbl.add_subparsers(dest="table_cmd", required=True)

    p = meta_tbl_sub.add_parser("bi", help="BI+DataMap 关键词找表")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--page-size", type=int, default=40)
    p.add_argument("--schema", default="mart_sailor_global")
    p.add_argument("--no-filter", action="store_true")
    p.add_argument("--format", choices=["json", "text"], default="text")
    p.add_argument("--refresh-cookie", action="store_true")
    p.add_argument("--no-enrich", action="store_true")
    p.set_defaults(func=_meta_runner("table"))

    p = meta_tbl_sub.add_parser("rag", help="RAG 语义找表")
    p.add_argument("query")
    p.add_argument("--type", choices=["table", "business", "metric"], default="table")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--format", choices=["json", "text"], default="text")
    p.set_defaults(func=_meta_runner("rag"))

    p = meta_tbl_sub.add_parser("etl", help="查 XT ETL 代码")
    p.add_argument("task_name")
    p.add_argument("--from-source", choices=["local", "api", "auto"], default="api")
    p.add_argument("--code-only", action="store_true")
    p.add_argument("-o", "--output", default="")
    p.set_defaults(func=_meta_runner("etl"))

    # meta origin
    p = meta_sub.add_parser("origin", help="起源指标血缘")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("kpi_id", type=int, nargs="?")
    g.add_argument("--code", "-c")
    g.add_argument("--name", "-n")
    g.add_argument("--search", "-s")
    p.add_argument("--json", action="store_true")
    p.add_argument("--info", action="store_true")
    p.add_argument("--list-only", action="store_true")
    p.add_argument("--all-schemas", action="store_true")
    p.set_defaults(func=_meta_runner("origin"))

    # meta lineage
    p = meta_sub.add_parser("lineage", help="Hive 数据地图血缘")
    lg = p.add_mutually_exclusive_group()
    lg.add_argument("--table")
    lg.add_argument("--table-id", type=int, dest="table_id")
    p.add_argument("--upstream-only", action="store_true")
    p.add_argument("--downstream-only", action="store_true")
    p.add_argument("--columns", action="store_true")
    p.add_argument("--column")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_meta_runner("lineage"))

    # meta auth
    p = meta_sub.add_parser("auth", help="鉴权检查/修复")
    p.add_argument("--check", action="store_true")
    p.add_argument("--fix", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("targets", nargs="*", help="指定检查项：bi rag origin xt km（origin_token 为兼容别名）")
    p.set_defaults(func=_cmd_meta_auth)

    # init 子命令
    p_init = sub.add_parser("init", help="初始化 kdata 运行依赖")
    p_init.add_argument("--mis", default="", help=argparse.SUPPRESS)
    p_init.set_defaults(func=cmd_init)

    # ── task ─────────────────────────────────────────────────────────────────
    p_task = sub.add_parser("task", help="Task 生命周期管理（start/end/status）")
    task_sub = p_task.add_subparsers(dest="cmd", required=True)

    p_ts_start = task_sub.add_parser("start", help="开始新 task（记录用户输入）")
    p_ts_start.add_argument("--input", required=True, help="用户原始问题/输入")
    p_ts_start.add_argument("--mis", default="", help="执行人 MIS（不传则自动获取）")
    p_ts_start.set_defaults(func=_cmd_task_start)

    p_ts_input = task_sub.add_parser("input", help="记录同一 task 内的后续用户输入")
    p_ts_input.add_argument("--input", required=True, help="用户原始问题/输入")
    p_ts_input.add_argument("--mis", default="", help="执行人 MIS（不传则自动获取）")
    p_ts_input.set_defaults(func=_cmd_task_input)

    p_ts_end = task_sub.add_parser("end", help="结束 task（记录最终输出）")
    p_ts_end.add_argument("--output", default="", help="最终回答摘要")
    p_ts_end.add_argument("--mis", default="", help="执行人 MIS（不传则自动获取）")
    p_ts_end.set_defaults(func=_cmd_task_end)

    task_sub.add_parser("status", help="查看当前 task 状态").set_defaults(func=_cmd_task_status)

    # ── feedback ─────────────────────────────────────────────────────────────
    p_feedback = sub.add_parser("feedback", help="上报用户反馈（点赞/点踩）")
    p_feedback.add_argument("--rating", type=int, choices=[1, -1], required=True, help="反馈评分：1=有帮助，-1=无帮助")
    p_feedback.add_argument("--comment", default="", help="用户反馈内容")
    p_feedback.add_argument("--type", default="thumbs", help="反馈类型，默认 thumbs")
    p_feedback.add_argument("--mis", default="", help="执行人 MIS（不传则自动获取）")
    p_feedback.set_defaults(func=_cmd_feedback)

    return parser

# ══════════════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = _build_parser()
    _ensure_cli_installed()
    raw_argv = sys.argv[1:]
    parse_argv, json_requested = _normalise_argv(raw_argv)
    args = parser.parse_args(parse_argv)
    args._raw_argv = raw_argv

    # 透传 --json 和 --locale 到子命令（子 parser 没有这两个字段时补上）
    if not hasattr(args, "json"):
        args.json = False
    if json_requested:
        args.json = True
    if not hasattr(args, "locale"):
        args.locale = "zh"
    if not hasattr(args, "region"):
        args.region = None

    # 默认 unset 代理，除非明确指定 --with-proxy
    if not getattr(args, "with_proxy", False):
        _unset_proxy()

    # init/task 子命令不被查询依赖检查拦截。
    if getattr(args, "group", None) == "init":
        args.func(args)
        return

    # task/feedback 子命令自己管理生命周期，不走通用 tracking 流程
    if getattr(args, "group", None) in ("task", "feedback"):
        try:
            args.func(args)
        except SystemExit as e:
            sys.exit(e.code if isinstance(e.code, int) else 0)
        return

    _check_deps()

    # [TRACKING] 获取 MIS、构建命令描述
    # 补全 PATH 确保 npx 可以被找到（无论以何种方式调用 kdata）
    _extra = ":".join([
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/bin"),
        "/usr/local/bin",
    ])
    if _extra not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _extra + ":" + os.environ.get("PATH", "/usr/bin:/bin")
    _mis = _get_current_mis()
    if _mis == "unknown":
        print("[kdata] MIS 未知，日志以 unknown 上报。设置：export SANDBOX_MIS=<your_mis>", file=sys.stderr)
    _cli_cmd = _build_cli_command(args, raw_argv)

    # [TRACKING] task_id 优先级：--task-id 参数 > 环境变量 > task state 文件 > 自动生成
    _session_id = getattr(args, "task_id", "") or os.environ.get("KDATA_SESSION_ID", "") or os.environ.get("OPENCLAW_SESSION_ID", "")
    if not _session_id and _CORE_IMPORTED:
        _session_id, _ = _get_active_task()
    if not _session_id:
        import uuid as _uuid
        _session_id = str(_uuid.uuid4())
        # 降级警告：提示 Agent 必须先调 task start
        print(f"[kdata] ⚠️ 未检测到活跃 task！已自动生成临时 session {_session_id[:8]}，但日志将无法聚合。", file=sys.stderr)
        print(f"[kdata] ⚠️ 请在执行查询命令前先调用：kdata task start --input \"用户原始问题\"", file=sys.stderr)

    _task_desc = getattr(args, "task_name", "").strip() or os.environ.get("KDATA_TASK", "").strip()
    # 如果没有显式 task_desc，尝试从 task state 读取
    if not _task_desc and _CORE_IMPORTED:
        _, _task_desc = _get_active_task()

    # [TRACKING] hive run/submit 时，失败才在 input_summary 追加 SQL，成功不记录节省存储
    _hive_sql = ""
    if getattr(args, "group", None) == "hive" and getattr(args, "cmd", None) in ("run", "submit"):
        _raw_sql = getattr(args, "sql", "") or ""
        if _raw_sql:
            _hive_sql = _raw_sql.strip()[:800]

    def _task_desc_with_sql():
        """失败时调用，返回带 SQL 的 input_summary"""
        if _hive_sql:
            return f"{_task_desc}\n[SQL] {_hive_sql}" if _task_desc else f"[SQL] {_hive_sql}"
        return _task_desc
    # [TRACKING] 输出截断限制（按命令类型分级）
    def _get_output_limit() -> int:
        """根据命令类型返回 output_summary 截断字符数。"""
        _group = getattr(args, "group", "") or ""
        _cmd = getattr(args, "cmd", "") or ""
        if _group == "hive" and _cmd in ("run", "result"):
            return 3000       # hive 结果可能很大，取前 3000 字符
        if _group == "standard" and _cmd == "query":
            return 5000       # standard query 通常不大，但保留足够空间
        return 3000           # 其余命令默认 3000

    _t0 = time.time()

    # [TRACKING] 通过 stdout 捕获获取命令原始输出（用于准确性评测）
    import io as _io
    _stdout_capture = _io.StringIO()
    _original_stdout = sys.stdout
    # 使用 TeeWriter 同时写入 stdout 和 capture buffer
    class _TeeWriter:
        def __init__(self, original, capture):
            self._orig = original
            self._cap = capture
        def write(self, s):
            self._cap.write(s)
            return self._orig.write(s)
        def flush(self):
            return self._orig.flush()
        def fileno(self):
            return self._orig.fileno()
        def isatty(self):
            return self._orig.isatty() if hasattr(self._orig, 'isatty') else False
        def __getattr__(self, name):
            return getattr(self._orig, name)
    sys.stdout = _TeeWriter(_original_stdout, _stdout_capture)

    _exit_code = 0
    try:
        args.func(args)
    except SystemExit as e:
        sys.stdout = _original_stdout
        _exit_code = e.code if isinstance(e.code, int) else 0
        _status = "SUCCESS" if _exit_code == 0 else "FAIL"
        _cost = int((time.time() - _t0) * 1000)
        _captured = _stdout_capture.getvalue()
        if _exit_code == 0 and _captured:
            # 成功的 sys.exit(0)（如 hive 命令），记录输出
            _output_limit = _get_output_limit()
            _report_cli_command(
                cli_command=_cli_cmd,
                mis=_mis,
                params=_task_desc,
                output=_captured[:_output_limit],
                cost_ms=_cost,
                success=(_status == "SUCCESS"),
                session_id=_session_id,
            )
        else:
            _input = _task_desc_with_sql() if _exit_code else _task_desc
            _report_cli_command(
                cli_command=_cli_cmd,
                mis=_mis,
                params=_input,
                cost_ms=_cost,
                success=(_status == "SUCCESS"),
                error_msg=f"exit {_exit_code}" if _exit_code else "",
                session_id=_session_id,
            )
        sys.exit(_exit_code)
    except RuntimeError as e:
        sys.stdout = _original_stdout
        _cost = int((time.time() - _t0) * 1000)
        _report_cli_command(
            cli_command=_cli_cmd,
            mis=_mis,
            params=_task_desc_with_sql(),
            cost_ms=_cost,
            success=False,
            error_msg=str(e),
            session_id=_session_id,
        )
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stdout = _original_stdout
        sys.exit(0)
    except BrokenPipeError:
        # Downstream output consumers such as `head` or host-side truncators can
        # close stdout early. Treat that as normal output truncation, not as a
        # failed data query, and silence final interpreter flushes on stdout.
        sys.stdout = open(os.devnull, "w")
        _cost = int((time.time() - _t0) * 1000)
        _captured = _stdout_capture.getvalue()
        _output_limit = _get_output_limit()
        _report_cli_command(
            cli_command=_cli_cmd,
            mis=_mis,
            params=_task_desc,
            output=_captured[:_output_limit] if _captured else "",
            cost_ms=_cost,
            success=True,
            session_id=_session_id,
        )
        sys.exit(0)
    except Exception as e:
        sys.stdout = _original_stdout
        _cost = int((time.time() - _t0) * 1000)
        _report_cli_command(
            cli_command=_cli_cmd,
            mis=_mis,
            params=_task_desc_with_sql(),
            cost_ms=_cost,
            success=False,
            error_msg=f"uncaught {type(e).__name__}: {e}",
            session_id=_session_id,
        )
        import traceback
        traceback.print_exc()
        sys.exit(1)

    sys.stdout = _original_stdout
    _cost = int((time.time() - _t0) * 1000)
    # 成功时记录输出摘要（用于准确性评测）
    _captured = _stdout_capture.getvalue()
    _output_limit = _get_output_limit()
    _output_summary = _captured[:_output_limit] if _captured else ""
    _report_cli_command(
        cli_command=_cli_cmd,
        mis=_mis,
        params=_task_desc,
        output=_output_summary,
        cost_ms=_cost,
        success=True,
        session_id=_session_id,
    )
    # 更新 task 活跃时间
    if _CORE_IMPORTED:
        try:
            _touch_task()
        except Exception:
            pass


if __name__ == "__main__":
    main()
