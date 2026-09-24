#!/usr/bin/env python3
"""Generate a reproducible evidence packet for keeta-brand-anomaly.

The script keeps the fixed kdata path in code, preserves runnable commands in
the output, and reports each query as a skill-script node through skill_tracker.
Telemetry is best-effort and must never block evidence generation.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
DATASET_SUPPLY_OVERVIEW = "62059636"

try:
    from skill_tracker import get_or_create_task_id, report_script
except Exception:  # noqa: BLE001 - telemetry is optional by design.
    get_or_create_task_id = None  # type: ignore[assignment]
    report_script = None  # type: ignore[assignment]


def parse_range(value: str) -> tuple[str, str]:
    text = value.strip()
    if "~" in text:
        start, end = text.split("~", 1)
    else:
        start = end = text
    if not (start.isdigit() and end.isdigit() and len(start) == 8 and len(end) == 8):
        raise argparse.ArgumentTypeError("date range must be YYYYMMDD or YYYYMMDD~YYYYMMDD")
    return start, end


def date_range_text(value: tuple[str, str]) -> str:
    return f"{value[0]}~{value[1]}"


def command_text(command: list[str]) -> str:
    return " ".join(command)


def parse_json_stdout(stdout: str) -> Any:
    if not stdout:
        return None
    start = stdout.find("{")
    if start < 0:
        start = stdout.find("[")
    if start < 0:
        raise ValueError("no JSON object or array found in stdout")
    return json.loads(stdout[start:])


def extract_rows(data: Any) -> list[Any]:
    if isinstance(data, dict):
        for key in ("rows", "data", "result"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = extract_rows(value)
                if nested:
                    return nested
    return []


def extract_total(data: Any, rows: list[Any]) -> int:
    if isinstance(data, dict):
        for key in ("total", "total_num", "totalNum"):
            value = data.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.replace(",", "").isdigit():
                return int(value.replace(",", ""))
    return len(rows)


def extract_query_id(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("query_id", "queryId", "task_id", "taskId"):
            value = data.get(key)
            if value:
                return str(value)
    return ""


def classify_error(text: str) -> str:
    lower = text.lower()
    if "timeout" in lower or "timed out" in lower:
        return "timeout"
    if "permission" in lower or "403" in lower or "401" in lower or "auth" in lower:
        return "auth_failed"
    if "no data" in lower or "empty" in lower or "无数据" in lower:
        return "empty_data"
    if "not found" in lower or "invalid" in lower or "参数" in lower:
        return "invalid_args"
    if "connection" in lower or "network" in lower or "tls" in lower:
        return "tool_unavailable"
    return "unknown"


def safe_report(stage: str, params: dict[str, Any], output: dict[str, Any], cost_ms: int, success: bool, error: str = "") -> None:
    if report_script is None:
        return
    try:
        if os.environ.get("SKILL_TRACKER_DRY_RUN") == "1":
            with contextlib.redirect_stdout(sys.stderr):
                report_script(
                    params={"script": "brand_anomaly_evidence", "stage": stage, **params},
                    output=output,
                    cost_ms=cost_ms,
                    success=success,
                    error_msg=error,
                )
        else:
            report_script(
                params={"script": "brand_anomaly_evidence", "stage": stage, **params},
                output=output,
                cost_ms=cost_ms,
                success=success,
                error_msg=error,
            )
    except Exception:
        return


def build_standard_query(
    *,
    kdata: str,
    task_id: str,
    task_name: str,
    measures: list[str],
    date_range: tuple[str, str],
    region: str,
    group_by: str = "",
    filters: list[str] | None = None,
    page_size: int = 10000,
    biz_type: str = "",
) -> list[str]:
    command = [
        kdata,
        "--json",
        "--task-id",
        task_id,
        "--task-name",
        task_name,
        "standard",
        "query",
        "--dataset",
        DATASET_SUPPLY_OVERVIEW,
        "--measures",
        ",".join(measures),
        "--date",
        date_range_text(date_range),
        "--region",
        region,
    ]
    if biz_type:
        command.extend(["--biz-type", biz_type])
    for item in filters or []:
        if item:
            command.extend(["--filter", item])
    if group_by:
        command.extend(["--group-by", group_by])
    if page_size:
        command.extend(["--page-size", str(page_size)])
    return command


def run_kdata_query(name: str, command: list[str], timeout: int, dry_run: bool) -> dict[str, Any]:
    start = time.time()
    record: dict[str, Any] = {
        "name": name,
        "command": command_text(command),
        "ok": True,
        "returncode": 0,
        "duration_sec": 0.0,
        "query_id": "",
        "rows": 0,
        "total_num": 0,
        "error": None,
        "data": None,
    }
    if dry_run:
        record["dry_run"] = True
        record["duration_sec"] = 0.0
        safe_report(
            name,
            params=params_from_command(command),
            output={"event": "dry_run", "status": "ok", "rows": 0, "total_num": 0},
            cost_ms=0,
            success=True,
        )
        return record

    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        elapsed_ms = int((time.time() - start) * 1000)
        record["returncode"] = proc.returncode
        record["duration_sec"] = round(elapsed_ms / 1000, 3)
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "")[-2000:]
            record["ok"] = False
            record["error"] = message
            safe_report(
                name,
                params=params_from_command(command),
                output={"event": name, "status": "fail", "returncode": proc.returncode, "error_type": classify_error(message)},
                cost_ms=elapsed_ms,
                success=False,
                error=message,
            )
            return record

        data = parse_json_stdout(proc.stdout)
        rows = extract_rows(data)
        total = extract_total(data, rows)
        record.update({
            "data": data,
            "query_id": extract_query_id(data),
            "rows": len(rows),
            "total_num": total,
        })
        safe_report(
            name,
            params=params_from_command(command),
            output={
                "event": name,
                "status": "ok",
                "query_id": record["query_id"],
                "rows": len(rows),
                "total_num": total,
                "elapsed_sec": record["duration_sec"],
            },
            cost_ms=elapsed_ms,
            success=True,
        )
        return record
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.time() - start) * 1000)
        message = f"timeout after {timeout}s: {exc}"
        record.update({"ok": False, "returncode": -1, "duration_sec": round(elapsed_ms / 1000, 3), "error": message})
        safe_report(
            name,
            params=params_from_command(command),
            output={"event": name, "status": "fail", "error_type": "timeout"},
            cost_ms=elapsed_ms,
            success=False,
            error=message,
        )
        return record
    except Exception as exc:  # noqa: BLE001 - evidence packet should capture failure.
        elapsed_ms = int((time.time() - start) * 1000)
        message = str(exc)
        record.update({"ok": False, "returncode": -1, "duration_sec": round(elapsed_ms / 1000, 3), "error": message})
        safe_report(
            name,
            params=params_from_command(command),
            output={"event": name, "status": "fail", "error_type": classify_error(message)},
            cost_ms=elapsed_ms,
            success=False,
            error=message,
        )
        return record


def params_from_command(command: list[str]) -> dict[str, Any]:
    params: dict[str, Any] = {"command": "kdata"}
    for flag, key in [
        ("--task-name", "task_name"),
        ("--date", "date_range"),
        ("--region", "region"),
        ("--dataset", "dataset"),
        ("--measures", "measure"),
        ("--group-by", "group_by"),
        ("--biz-type", "biz_type"),
    ]:
        if flag in command:
            index = command.index(flag)
            if index + 1 < len(command):
                params[key] = command[index + 1]
    filters = [command[i + 1] for i, item in enumerate(command[:-1]) if item == "--filter"]
    for item in filters:
        if item.startswith("brand_id="):
            params["brand_id"] = item.split("=", 1)[1]
        elif "=" in item:
            params["dim_code"], params["org_id"] = item.split("=", 1)
    return params


def summarize_packet(records: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[str]]:
    errors: list[dict[str, Any]] = []
    data_gaps: list[str] = []
    for record in records:
        if not record.get("ok"):
            errors.append({
                "name": record["name"],
                "error_type": classify_error(str(record.get("error") or "")),
                "error": record.get("error"),
            })
        elif not record.get("dry_run") and record.get("rows", 0) == 0:
            data_gaps.append(f"{record['name']} returned 0 rows")
    if errors and len(errors) == len(records):
        status = "fail"
    elif errors or data_gaps:
        status = "partial"
    else:
        status = "ok"
    return status, errors, data_gaps


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    current_range = parse_range(args.date_range)
    prev_range = parse_range(args.prev_date_range)
    task_id = args.task_id
    if not task_id and get_or_create_task_id is not None:
        task_id = get_or_create_task_id()
    if not task_id:
        task_id = "manual-task-id-required"

    common_filters = list(args.filter or [])
    if args.brand_id:
        brand_filter = f"brand_id={args.brand_id}"
        if brand_filter not in common_filters:
            common_filters.append(brand_filter)

    query_specs: list[tuple[str, list[str]]] = []
    query_specs.append((
        "brand_overview_curr",
        build_standard_query(
            kdata=args.kdata,
            task_id=task_id,
            task_name=f"brand_overview_curr:{args.region}:{date_range_text(current_range)}",
            measures=["fin_ord_num"],
            date_range=current_range,
            region=args.region,
            group_by="brand_id,brand_name",
            filters=args.filter,
            page_size=args.page_size,
            biz_type=args.biz_type,
        ),
    ))
    query_specs.append((
        "brand_overview_prev",
        build_standard_query(
            kdata=args.kdata,
            task_id=task_id,
            task_name=f"brand_overview_prev:{args.region}:{date_range_text(prev_range)}",
            measures=["fin_ord_num"],
            date_range=prev_range,
            region=args.region,
            group_by="brand_id,brand_name",
            filters=args.filter,
            page_size=args.page_size,
            biz_type=args.biz_type,
        ),
    ))
    query_specs.append((
        "region_total_curr",
        build_standard_query(
            kdata=args.kdata,
            task_id=task_id,
            task_name=f"region_total_curr:{args.region}:{date_range_text(current_range)}",
            measures=["fin_ord_num"],
            date_range=current_range,
            region=args.region,
            filters=args.filter,
            page_size=0,
            biz_type=args.biz_type,
        ),
    ))
    query_specs.append((
        "region_total_prev",
        build_standard_query(
            kdata=args.kdata,
            task_id=task_id,
            task_name=f"region_total_prev:{args.region}:{date_range_text(prev_range)}",
            measures=["fin_ord_num"],
            date_range=prev_range,
            region=args.region,
            filters=args.filter,
            page_size=0,
            biz_type=args.biz_type,
        ),
    ))

    if args.brand_id:
        measures = [
            "fin_ord_num",
            "shop_avg_shop_actual_online_days",
            "shop_avg_shop_actual_open_days",
            "davg_shop_avg_open_dura",
            "shop_oavg_readied_duration",
            "paid_order_cancel_rate_merchant_reason",
            "davg_fulldisc_open_shop_coverage",
            "davg_discount_spu_shop_coverage",
            "davg_reduceshipfee_shop_coverage",
            "davg_shop_avg_ad_position_shop_entry_exposure_uv",
            "davg_shop_entry_exposure_visit_ratio",
            "actual_shop_charge_amt_ratio",
        ]
        query_specs.append((
            "brand_detail_curr",
            build_standard_query(
                kdata=args.kdata,
                task_id=task_id,
                task_name=f"brand_detail_curr:{args.region}:{date_range_text(current_range)}",
                measures=measures,
                date_range=current_range,
                region=args.region,
                group_by="brand_id,brand_name",
                filters=common_filters,
                page_size=10,
                biz_type=args.biz_type,
            ),
        ))
        query_specs.append((
            "brand_detail_prev",
            build_standard_query(
                kdata=args.kdata,
                task_id=task_id,
                task_name=f"brand_detail_prev:{args.region}:{date_range_text(prev_range)}",
                measures=measures,
                date_range=prev_range,
                region=args.region,
                group_by="brand_id,brand_name",
                filters=common_filters,
                page_size=10,
                biz_type=args.biz_type,
            ),
        ))

    records = [run_kdata_query(name, command, args.timeout, args.dry_run) for name, command in query_specs]
    status, errors, data_gaps = summarize_packet(records)
    sections = {
        "overview": {
            "current": records[0].get("data"),
            "previous": records[1].get("data"),
            "region_total_current": records[2].get("data"),
            "region_total_previous": records[3].get("data"),
        },
        "brand_detail": {
            "current": records[4].get("data") if len(records) > 4 else None,
            "previous": records[5].get("data") if len(records) > 5 else None,
        },
    }
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "request": {
            "scene": "brand_anomaly",
            "region": args.region,
            "date_range": date_range_text(current_range),
            "prev_date_range": date_range_text(prev_range),
            "brand_id": args.brand_id,
            "brand_name": args.brand_name,
            "biz_type": args.biz_type,
            "filters": args.filter or [],
            "task_input_hash_only": bool(args.task_input),
        },
        "query_records": [
            {key: value for key, value in record.items() if key != "data"}
            for record in records
        ],
        "sections": sections,
        "summary": {
            "queries": len(records),
            "succeeded": sum(1 for record in records if record.get("ok")),
            "failed": sum(1 for record in records if not record.get("ok")),
            "dry_run": args.dry_run,
        },
        "errors": errors,
        "data_gaps": data_gaps,
    }


def write_packet(packet: dict[str, Any], output: str, fmt: str) -> None:
    text = json.dumps(packet, ensure_ascii=False, indent=2, default=str)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    if fmt == "json" or not output:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate keeta-brand-anomaly evidence packet")
    parser.add_argument("--region", default="SA", help="Region code, e.g. SA/HK/AE/QA/KW/BR/BH")
    parser.add_argument("--date-range", default="20260601~20260607", help="Current date range: YYYYMMDD or YYYYMMDD~YYYYMMDD")
    parser.add_argument("--prev-date-range", default="20260525~20260531", help="Comparison date range")
    parser.add_argument("--brand-id", default="", help="Optional brand_id for brand detail query")
    parser.add_argument("--brand-name", default="", help="Optional brand name for request metadata")
    parser.add_argument("--biz-type", default="", help="Front-line permission bizType")
    parser.add_argument("--filter", action="append", default=[], help="Extra kdata filter, repeatable")
    parser.add_argument("--page-size", type=int, default=10000, help="Overview grouped query page size")
    parser.add_argument("--task-id", default="", help="Existing task id from skill_tracker.py start")
    parser.add_argument("--task-input", default="", help="Original user input; retained as request metadata only")
    parser.add_argument("--timeout", type=int, default=300, help="Per-query timeout seconds")
    parser.add_argument("--kdata", default=os.environ.get("KDATA_BIN", "kdata"), help="kdata executable")
    parser.add_argument("--format", choices=["json"], default="json")
    parser.add_argument("--output", default="", help="Write evidence packet to this path")
    parser.add_argument("--dry-run", action="store_true", help="Build commands without executing kdata")
    parser.add_argument("--self-test", action="store_true", help="Run a deterministic dry-run sample")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        args.region = "SA"
        args.date_range = "20260601~20260607"
        args.prev_date_range = "20260525~20260531"
        args.brand_id = "12345"
        args.brand_name = "KFC"
        args.dry_run = True
        os.environ.setdefault("SKILL_TRACKER_DRY_RUN", "1")
    packet = build_packet(args)
    write_packet(packet, args.output, args.format)
    return 0 if packet["status"] in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
