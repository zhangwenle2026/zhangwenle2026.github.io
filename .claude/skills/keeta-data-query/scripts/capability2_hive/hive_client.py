#!/usr/bin/env python3
"""Hive client backed by `mtcli kdata meta bi-hive-*` commands."""

from __future__ import annotations

import os
from pathlib import Path
import time
import urllib.parse
from typing import Any

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run


BI_BASE = "https://bi.keetapp.com"

STATUS_RUNNING = 3
STATUS_SUCCESS = 5
STATUS_DONE = 8

_HETU_APPLY_BASE = "https://data.keetapp.com/hetu/tableApply"


def _normalize_project_name(value: str) -> str:
    lowered = value.strip().lower()
    return "".join(ch for ch in lowered if ch.isalnum())


def _resolve_sql_text(sql_or_file: str) -> str:
    candidate = Path(sql_or_file.strip()).expanduser()
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return sql_or_file


def _extract_apply_links(submit_result: dict) -> list[dict]:
    """从 submit_failed 的响应中提取无权限表，拼出个人空间申请链接。"""
    table_auth = (submit_result.get("data") or {}).get("tableAuthResult") or {}
    if table_auth.get("errorType") != "NO_PERMISSION":
        return []
    solv = table_auth.get("solvForTable") or []
    links = []
    for item in solv:
        db = item.get("db", "")
        table = item.get("table", "")
        source = item.get("key", "DW_ONESQL_DB_CONNECT_URL")
        if not db or not table:
            continue
        url = (
            f"{_HETU_APPLY_BASE}?applyType=external&providerType=person"
            f"&refer=role&source={source}&database={db}&table={table}"
        )
        links.append({"db": db, "table": table, "url": url})
    return links


class BiClient:
    """Hive client backed exclusively by `mtcli kdata meta bi-hive-*` commands."""

    def __init__(
        self,
        project_id: str | int = "0",
        base_url: str = BI_BASE,
    ) -> None:
        for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
            os.environ.pop(key, None)
        self.project_id = str(project_id)
        self.base_url = base_url.rstrip("/")

    def _mtcli_headers(self, project_id: str | None = None) -> dict[str, str]:
        project = str(project_id) if project_id is not None else self.project_id
        return {"projectId": project}

    def _run_mtcli(
        self,
        command: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        project_id: str | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        if os.getenv("KDATA_DISABLE_MTCLI_META", "").strip() == "1":
            raise RuntimeError("mtcli meta disabled by KDATA_DISABLE_MTCLI_META")
        return _mtcli_run(
            ["kdata", "meta", command],
            body=body,
            params=params,
            headers=self._mtcli_headers(project_id),
            timeout=timeout,
        )

    def get_spaces(self) -> dict[str, Any]:
        return self._run_mtcli("bi-hive-spaces", project_id="0")

    def get_queues(self) -> dict[str, Any]:
        return self._run_mtcli("bi-hive-queues")

    def get_datasources(self) -> dict[str, Any]:
        raise RuntimeError(
            "Hive datasources 旧 HTTP 链路已移除；当前 mtcli kdata meta 尚未暴露 bi-hive-datasources 命令。"
        )

    def get_status(self, query_id: int | str) -> dict[str, Any]:
        return self._run_mtcli(
            "bi-hive-status",
            params={"queryId": str(query_id)},
        )

    def get_result(self, query_id: int | str, limit: int = 200) -> dict[str, Any]:
        return self._run_mtcli(
            "bi-hive-result",
            params={"queryId": str(query_id), "limit": str(limit), "plaintext": "1"},
        )

    def analyze_sql(
        self,
        sql: str,
        engine: str = "onesql",
        ds_name: str = "dw_hive",
        stat_ds: str = "DW_ONESQL_DB_CONNECT_URL",
        var_map: dict[str, Any] | None = None,
        diagnose_source: str = "MTBI",
        get_inputs: bool = True,
        get_outputs: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "engine": engine,
            "dsName": ds_name,
            "statDs": stat_ds,
            "statement": sql,
            "varMap": var_map or {},
            "diagnoseSource": diagnose_source,
            "getInputs": get_inputs,
            "getOutputs": get_outputs,
        }
        return self._run_mtcli("bi-hive-analyze", body=payload, timeout=60)

    def submit_sql(
        self,
        sql: str,
        spark_queue: str | None,
        engine: str = "onesql",
        ds_name: str = "dw_hive",
        stat_ds: str = "DW_ONESQL_DB_CONNECT_URL",
        resource_id: int = 0,
        resource_name: str = "新查询",
        resource_ver: int = 1,
        resource_owner: str = "",
        entrance: list[str] | None = None,
        filter_relation_type: str = "AND",
        filter_type: str = "EQ",
        filter_children: list[Any] | None = None,
    ) -> dict[str, Any]:
        resource_url = (
            f"{self.base_url}/v2/sql/edit?projectId={self.project_id}"
            if self.project_id and self.project_id != "0"
            else f"{self.base_url}/v2/sql/edit"
        )
        if entrance is None:
            parsed = urllib.parse.urlparse(self.base_url)
            entrance = [parsed.netloc] if parsed.netloc else ["bi.keetapp.com"]
        if filter_children is None:
            filter_children = []

        payload = {
            "context": {
                "resourceId": resource_id,
                "resourceName": resource_name,
                "resourceVer": resource_ver,
                "resourceUrl": resource_url,
                "resourceOwner": resource_owner,
                "mdbiSparkQueue": spark_queue or "",
                "entrance": entrance,
            },
            "model": {
                "datasourceInfo": {
                    "sqlModelInfo": {
                        "sqlContent": sql,
                        "dsn": ds_name,
                        "hostGroup": ds_name,
                        "keyForAuth": stat_ds,
                        "engineType": engine,
                    }
                }
            },
            "access": {
                "filter": {
                    "relationType": filter_relation_type,
                    "filterType": filter_type,
                    "children": filter_children,
                },
            },
        }
        return self._run_mtcli("bi-hive-submit", body=payload, timeout=60)

    def resolve_project_id(self, project_ref: str | int) -> str:
        ref = str(project_ref).strip()
        if not ref:
            return "0"
        if ref.isdigit():
            return ref

        spaces = self.get_spaces()
        if spaces.get("error"):
            raise RuntimeError(f"读取工作空间失败: {spaces['error']}")
        if spaces.get("code", 0) != 0:
            raise RuntimeError(f"读取工作空间失败: {spaces.get('message', spaces)}")

        data = spaces.get("data", [])
        if not isinstance(data, list):
            raise RuntimeError(f"工作空间返回格式异常: {type(data)}")

        normalized_target = _normalize_project_name(ref)
        candidates: list[tuple[str, str]] = []

        for group in data:
            children = group.get("children", [])
            if children:
                for proj in children:
                    name = str(proj.get("name", "")).strip()
                    project_id = str(proj.get("id", "")).strip()
                    if not project_id:
                        continue
                    candidates.append((name, project_id))
                    if (
                        ref.lower() == name.lower()
                        or normalized_target == _normalize_project_name(name)
                    ):
                        return project_id
            else:
                name = str(group.get("name", "")).strip()
                project_id = str(group.get("id", "")).strip()
                if not project_id:
                    continue
                candidates.append((name, project_id))
                if (
                    ref.lower() == name.lower()
                    or normalized_target == _normalize_project_name(name)
                ):
                    return project_id

        sample = ", ".join(f"{name}({project_id})" for name, project_id in candidates[:10])
        raise RuntimeError(f"未找到工作空间: {ref}。可用示例: {sample}")

    @staticmethod
    def _is_sql_like(text: str) -> bool:
        """判断输入是否像 SQL 语句，避免把自然语言提交给 BI 语法检查接口。"""
        import re

        stripped = text.strip()
        return bool(
            re.search(
                r"^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|SHOW|DESCRIBE|EXPLAIN|USE|SET)\b",
                stripped,
                re.IGNORECASE,
            )
        )

    def run_sql(
        self,
        sql: str,
        spark_queue: str | None,
        engine: str = "onesql",
        ds_name: str = "dw_hive",
        stat_ds: str = "DW_ONESQL_DB_CONNECT_URL",
        resource_name: str = "新查询",
        resource_owner: str = "",
        entrance: list[str] | None = None,
        filter_relation_type: str = "AND",
        filter_type: str = "EQ",
        limit: int = 200,
        poll_interval: float = 3.0,
        timeout: float = 180.0,
    ) -> dict[str, Any]:
        if not self._is_sql_like(sql):
            return {
                "success": False,
                "error": "not_sql_input",
                "message": (
                    "输入内容不是有效的 SQL 语句。"
                    "请先将自然语言问题转换为 Hive SQL，再提交执行。\n"
                    f"收到的输入（前100字符）：{sql[:100]!r}"
                ),
            }

        import re as _re

        first_kw = _re.match(
            r"\s*(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE)\b",
            sql.strip(),
            _re.IGNORECASE,
        )
        if first_kw:
            return {
                "success": False,
                "error": "ddl_dml_blocked",
                "message": (
                    f"不支持 {first_kw.group(1).upper()} 操作。"
                    "本平台仅允许 SELECT 查询和 CREATE TABLE ... AS SELECT (CTAS)。\n"
                    "如需修改数据，请通过其他途径（如 XT 平台）操作。"
                ),
            }

        meta_kw = _re.match(r"\s*(SHOW|DESCRIBE|DESC|USE|SET)\b", sql.strip(), _re.IGNORECASE)
        if meta_kw:
            kw_upper = meta_kw.group(1).upper()
            return {
                "success": False,
                "error": "meta_sql_blocked",
                "message": (
                    f"不支持 {kw_upper} 语句。"
                    "请改用 kdata 元数据命令：\n"
                    "  - 查表结构：`kdata table info <schema.table>`\n"
                    "  - 搜索表：`kdata table search <关键词>` 或 `kdata meta table bi <关键词>`\n"
                    "  - 查看 Schema 下的表：`kdata meta table bi <关键词> --schema <schema名>`"
                ),
            }

        analyze_result = self.analyze_sql(sql, engine=engine, ds_name=ds_name, stat_ds=stat_ds)
        if "error" in analyze_result and "code" not in analyze_result:
            net_err = analyze_result.get("error", "unknown")
            net_msg = f"SQL 预检请求失败: {net_err}"
            if net_err == "auth_redirect":
                net_msg = "SQL 预检失败: 登录态已过期，请通过 mtsso/CIBA 重新授权后重试"
            elif net_err == "non_json_response":
                net_msg = f"SQL 预检失败: 服务端返回异常 (HTTP {analyze_result.get('status_code', '?')})"
            return {"success": False, "error": "analyze_failed", "message": net_msg, "detail": analyze_result}

        analyze_data = analyze_result.get("data") or {}
        if analyze_result.get("code") != 0 or not analyze_data.get("isPass"):
            diagnose = analyze_data.get("sqlDiagnoseInfo") or analyze_data.get("sqlErrorInfo") or {}
            msg = (
                diagnose.get("message")
                or diagnose.get("msg")
                or analyze_result.get("message")
                or "SQL 语法检查未通过，请确认 SQL 语句正确"
            )
            if msg == "SQL 语法检查未通过，请确认 SQL 语句正确" and analyze_data:
                extra = analyze_data.get("errorMsg") or analyze_data.get("error") or ""
                if extra:
                    msg = f"{msg} ({extra})"
            return {"success": False, "error": "analyze_failed", "message": msg, "detail": analyze_result}

        submit_result = self.submit_sql(
            sql=sql,
            spark_queue=spark_queue,
            engine=engine,
            ds_name=ds_name,
            stat_ds=stat_ds,
            resource_name=resource_name,
            resource_owner=resource_owner,
            entrance=entrance,
            filter_relation_type=filter_relation_type,
            filter_type=filter_type,
        )
        if submit_result.get("code") != 0:
            submit_data = submit_result.get("data") or {}
            auth = submit_data.get("tableAuthResult") or {}
            msg = (
                (auth.get("errorMessage") or "").split("\n")[0].strip()
                or auth.get("errorType", "")
                or submit_result.get("message", "")
                or f"code={submit_result.get('code')}"
            )
            is_auth = not auth.get("hasTableAuth", True) or "AUTH" in auth.get("errorType", "")
            error_type = "submit_no_permission" if is_auth else "submit_failed"
            return {
                "success": False,
                "error": error_type,
                "message": msg,
                "detail": submit_result,
                "apply_links": _extract_apply_links(submit_result),
            }

        query_id = (submit_result.get("data") or {}).get("queryId")
        if not query_id:
            return {"success": False, "error": "no_query_id", "detail": submit_result}

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status_result = self.get_status(query_id)
            status_data = status_result.get("data") or {}
            status = status_data.get("status")

            if status in (STATUS_SUCCESS, STATUS_DONE):
                break
            if status != STATUS_RUNNING:
                return {
                    "success": False,
                    "error": "query_failed",
                    "status": status,
                    "problem": status_data.get("problem", ""),
                    "query_id": query_id,
                    "detail": status_result,
                }

            time.sleep(max(0.2, poll_interval))
        else:
            return {"success": False, "error": "timeout", "query_id": query_id}

        result_data = self.get_result(query_id, limit=limit)
        if result_data.get("code") != 0:
            return {"success": False, "error": "data_failed", "detail": result_data, "query_id": query_id}

        data = result_data.get("data") or {}
        return {
            "success": True,
            "query_id": query_id,
            "columns": data.get("columns", []),
            "data": data.get("data", []),
            "total_num": data.get("totalNum", 0),
        }
