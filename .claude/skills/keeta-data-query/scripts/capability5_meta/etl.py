#!/usr/bin/env python3
"""
Keeta XT ETL Reader - Unified Tool for Fetching XT Task Configurations and ETL Code

This tool provides a unified interface to:
1. Fetch task configurations and ETL code from local files
2. Query XT task information through mtcli
3. Parse and extract table structure (DDL) information
4. Intelligently switch between local and online sources
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_CORE_DIR = Path(__file__).resolve().parents[1] / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run


# ============================================================================
# Configuration & Constants
# ============================================================================

SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent

WORKSPACE_ROOT = Path(os.environ.get("OPENCLAW_WORKSPACE_ROOT", os.getcwd())).resolve()
OPENCLAW_HOME = Path(
    os.environ.get("OPENCLAW_HOME", str(WORKSPACE_ROOT / ".openclaw"))
).expanduser()
STATE_ROOT = Path(
    os.environ.get("MEITUAN_XT_STATE_DIR", str(OPENCLAW_HOME / "state" / "meituan-xt"))
).expanduser()
DEFAULT_XT_BASE_URL = "xt.keetapp.com"

# SQL Section Markers
SECTION_MARKERS = [
    "##Description##",
    "##TaskInfo##",
    "##Extract##",
    "##Preload##",
    "##Load##",
    "##TargetDDL##",
]


logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(message)s",
)
logger = logging.getLogger("keeta_xt_etl_reader")


# ============================================================================
# Exceptions
# ============================================================================

class ReaderError(RuntimeError):
    """Raised when ETL reader operations fail."""


# ============================================================================
# File I/O Helper Functions
# ============================================================================

def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """写入 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_json(payload: object) -> None:
    """打印 JSON 到标准输出"""
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# ============================================================================
# Configuration Management
# ============================================================================

def _read_from_env_file(env_file: Path, key: str) -> str | None:
    """从 .env 文件读取值"""
    if not env_file.exists():
        return None

    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            found_key, value = line.split("=", 1)
            if found_key.strip() != key:
                continue
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            return value or None
    except Exception as exc:
        logger.debug("Read .env failed: %s", exc)
    return None


def _find_repo_root(start_path: Path | None = None) -> Path:
    """查找仓库根目录"""
    current = (start_path or WORKSPACE_ROOT).resolve()
    if (current / "XT").is_dir():
        return current

    for parent in [current] + list(current.parents):
        if (parent / "XT").is_dir():
            return parent

    try:
        git_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
        if git_root:
            return Path(git_root)
    except Exception:
        pass

    return current


def _find_env_path() -> Path:
    """查找 .env 文件路径"""
    current = Path.cwd().resolve()
    for candidate in [current] + list(current.parents):
        env_path = candidate / ".env"
        if env_path.exists():
            return env_path

    repo_root = _find_repo_root(current)
    return repo_root / ".env"


def _get_config_value(key: str, default: str | None = None) -> str | None:
    """从 .env 或环境变量读取配置值"""
    env_path = _find_env_path()
    env_file_value = _read_from_env_file(env_path, key)
    if env_file_value:
        return env_file_value
    env_value = os.environ.get(key)
    if env_value:
        return env_value
    return default


# ============================================================================
# XT mtcli Client
# ============================================================================


class XTClient:
    """XT mtcli 客户端。"""

    def __init__(self, base_url: str, access_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token or ""
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Keeta-ETL-Reader/1.0",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if self.access_token:
            self.headers["access-token"] = self.access_token

    def _token_headers(self) -> dict[str, str] | None:
        return {"access-token": self.access_token} if self.access_token else None

    @staticmethod
    def _needs_token_retry(result: dict[str, Any]) -> bool:
        msg = str(result.get("msg") or result.get("message") or "").lower()
        return str(result.get("code")) == "401" and "access-token" in msg

    def _run_task_command(self, command: str, task_name: str, timeout: int = 30) -> dict[str, Any]:
        result = _mtcli_run(
            ["kdata", "meta", command],
            params={"task_name": task_name},
            headers=self._token_headers(),
            timeout=timeout,
        )
        if not self.access_token and self._needs_token_retry(result):
            token = _resolve_access_token()
            if token:
                self.access_token = token
                self.headers["access-token"] = token
                result = _mtcli_run(
                    ["kdata", "meta", command],
                    params={"task_name": task_name},
                    headers=self._token_headers(),
                    timeout=timeout,
                )
        return result

    def get_task_code(self, task_name: str, version_id: int = 0) -> dict[str, Any]:
        """通过 mtcli 获取任务代码。"""
        del version_id
        result = self._run_task_command("xt-task-code", task_name, timeout=30)
        if isinstance(result, dict) and result.get("code") not in (0, 200, None):
            msg = result.get("msg") or result.get("message") or "未知错误"
            raise ReaderError(f"获取任务代码失败(code={result.get('code')}): {msg}")
        return result

    def get_task_config(self, task_name: str) -> dict[str, Any]:
        """通过 mtcli 获取任务配置。"""
        result = self._run_task_command("xt-task-info", task_name, timeout=30)
        if result.get("code") in (0, 200, None):
            return result
        raise ReaderError(f"获取任务配置失败: {result.get('msg') or result.get('message') or '未知错误'}")


# ============================================================================
# SQL Parsing Functions (from keeta-data-assistant)
# ============================================================================

def extract_section(content: str, marker: str) -> str:
    """提取指定 section 的内容"""
    lines = content.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == marker:
            start = i + 1
            break
    if start < 0:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].strip() in SECTION_MARKERS:
            end = j
            break
    return "\n".join(lines[start:end]).strip("\n")


def split_sections(content: str) -> dict[str, str]:
    """按 SECTION_MARKERS 将内容拆成 marker -> body 的映射"""
    return {m: extract_section(content, m) for m in SECTION_MARKERS}


def parse_taskinfo(taskinfo_body: str) -> dict[str, str]:
    """解析 TaskInfo section 正文"""
    def _re1(text: str, pattern: str) -> str:
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1) if m else ""
    
    t = taskinfo_body or ""
    return {
        "creator": _re1(t, r"creator\s*=\s*['\"]([^'\"]+)['\"]"),
        "source_db": _re1(t, r"source\s*=\s*\{[^}]*'db'\s*:\s*META\[['\"]([^'\"]+)['\"]\]"),
        "target_db": _re1(t, r"target\s*=\s*\{[^}]*'db'\s*:\s*META\[['\"]([^'\"]+)['\"]\]"),
        "target_table": _re1(t, r"target\s*=\s*\{[^}]*'table'\s*:\s*['\"]([^'\"]+)['\"]"),
    }


def _strip_wrapped_identifier(value: str) -> str:
    """移除包装的标识符"""
    text = value.strip()
    if not text:
        return text
    if text[0] in ("`", '"') and text[-1] == text[0]:
        return text[1:-1].strip()
    return text


def _split_top_level_csv(text: str) -> list[str]:
    """拆分顶级 CSV"""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_sq = False
    in_dq = False
    in_bt = False
    esc = False

    for ch in text:
        if esc:
            buf.append(ch)
            esc = False
            continue
        if ch == "\\":
            buf.append(ch)
            esc = True
            continue
        if not in_dq and not in_bt and ch == "'":
            in_sq = not in_sq
            buf.append(ch)
            continue
        if not in_sq and not in_bt and ch == '"':
            in_dq = not in_dq
            buf.append(ch)
            continue
        if not in_sq and not in_dq and ch == "`":
            in_bt = not in_bt
            buf.append(ch)
            continue
        if in_sq or in_dq or in_bt:
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _extract_create_table_stmt(ddl_sql: str) -> str:
    """提取 CREATE TABLE 语句"""
    text = (ddl_sql or "").strip()
    if not text:
        return ""
    m = re.search(r"(?is)\bcreate\s+(?:external\s+)?table\b", text)
    if not m:
        return ""
    return text[m.start() :].strip()


def _find_matching_rparen_index(create_stmt: str) -> int:
    """找到与第一个左括号匹配的右括号位置"""
    lpar = create_stmt.find("(")
    if lpar < 0:
        return -1
    depth = 0
    in_sq = False
    in_dq = False
    in_bt = False
    esc = False
    for idx in range(lpar, len(create_stmt)):
        ch = create_stmt[idx]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if not in_dq and not in_bt and ch == "'":
            in_sq = not in_sq
            continue
        if not in_sq and not in_bt and ch == '"':
            in_dq = not in_dq
            continue
        if not in_sq and not in_dq and ch == "`":
            in_bt = not in_bt
            continue
        if in_sq or in_dq or in_bt:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _extract_parenthesized_columns_block(create_stmt: str) -> str:
    """提取 CREATE TABLE (...) 中的字段定义部分"""
    if not create_stmt:
        return ""
    lpar = create_stmt.find("(")
    if lpar < 0:
        return ""
    rpar = _find_matching_rparen_index(create_stmt)
    if rpar < 0:
        return ""
    return create_stmt[lpar + 1 : rpar].strip()


def _parse_column_line(line: str) -> dict[str, str] | None:
    """解析单行列定义"""
    line = line.strip()
    if not line:
        return None
    # 跳过 PARTITIONED BY 等
    if re.match(r"(?i)^\s*(partitioned|stored|location|tblproperties)", line):
        return None
    
    # 提取列名
    m = re.match(r"^([`\"\w]+)", line)
    if not m:
        return None
    raw_name = _strip_wrapped_identifier(m.group(1))
    rest = line[m.end() :].strip()
    if not raw_name or not rest:
        return None
    
    comment = ""
    cm = re.search(r"(?is)\bcomment\s+'((?:\\'|[^'])*)'", rest)
    if cm:
        comment = cm.group(1).replace("\\'", "'").strip()
        col_type = rest[: cm.start()].strip()
    else:
        col_type = rest.strip()
    
    return {
        "name": raw_name,
        "type": col_type,
        "comment": comment,
    }


def _parse_columns(create_stmt: str) -> list[dict[str, str]]:
    """解析所有列定义"""
    block = _extract_parenthesized_columns_block(create_stmt)
    if not block:
        return []
    out: list[dict[str, str]] = []
    for part in _split_top_level_csv(block):
        col = _parse_column_line(part)
        if col:
            out.append(col)
    return out


def extract_table_profile_from_raw_code(
    raw_code: str,
    *,
    task_name: str = "",
    fallback_owner: str = "",
) -> dict[str, Any]:
    """从 XT 任务代码中提取表结构信息"""
    sections = split_sections(raw_code or "")
    desc = (sections.get("##Description##") or "").strip()
    taskinfo = parse_taskinfo(sections.get("##TaskInfo##") or "")
    creator = (taskinfo.get("creator") or fallback_owner or "").strip()
    ddl_sql = (sections.get("##TargetDDL##") or "").strip()

    # 优先从 taskinfo 的 target_table 和 target_db 字段中提取表名
    target_db = str(taskinfo.get("target_db", "")).strip()
    target_table = str(taskinfo.get("target_table", "")).strip()
    
    # 去除 DSN 格式中的 h 前缀（如 hmart_sailor_global -> mart_sailor_global）
    if target_db.startswith("h") and len(target_db) > 1:
        target_db = target_db[1:]
    
    # 拼接完整表名 (db.table)
    if target_db and target_table:
        table_name = f"{target_db}.{target_table}"
    elif target_table:
        table_name = target_table
    else:
        table_name = ""
    
    # 如果 taskinfo 中没有，尝试从 DDL 中提取
    create_stmt = _extract_create_table_stmt(ddl_sql)
    table_desc = ""
    if not table_name and create_stmt:
        table_name_match = re.search(
            r"(?is)\bcreate\s+(?:external\s+)?table\s+(?:if\s+not\s+exists\s+)?([`\"\w.]+)",
            create_stmt,
        )
        if table_name_match:
            table_name = _strip_wrapped_identifier(table_name_match.group(1))

    # 提取表描述
    if create_stmt:
        tail = create_stmt[_find_matching_rparen_index(create_stmt) + 1 :]
        table_desc_match = re.search(r"(?is)\bcomment\s+'((?:\\'|[^'])*)'", tail)
        if table_desc_match:
            table_desc = table_desc_match.group(1).replace("\\'", "'").strip()

    columns = _parse_columns(create_stmt or ddl_sql)
    if not table_desc:
        table_desc = desc.splitlines()[0].strip() if desc else ""

    return {
        "task_name": task_name,
        "table_name": table_name,
        "table_description": table_desc,
        "table_owner": creator,
        "task_owner": creator,
        "description": desc,
        "creator": creator,
        "target_ddl": ddl_sql,
        "columns": columns,
    }


def render_table_profile_text(profile: dict[str, Any]) -> str:
    """将表结构信息渲染为文本格式"""
    lines: list[str] = []
    lines.append(f"Table Name: {profile.get('table_name', '')}")
    lines.append(f"Table Description: {profile.get('table_description', '')}")
    lines.append(f"Table Owner: {profile.get('table_owner', '')}")
    lines.append(f"Task Name: {profile.get('task_name', '')}")
    lines.append("")
    lines.append("Columns:")
    cols = profile.get("columns") or []
    if not isinstance(cols, list) or not cols:
        lines.append("(empty)")
        return "\n".join(lines) + "\n"

    for col in cols:
        name = str(col.get("name", "")).strip()
        comment = str(col.get("comment", "")).strip()
        col_type = str(col.get("type", "")).strip()
        if comment and col_type:
            lines.append(f"{name}  {col_type}  {comment}")
        elif col_type:
            lines.append(f"{name}  {col_type}")
        elif comment:
            lines.append(f"{name}  {comment}")
        else:
            lines.append(name)
    return "\n".join(lines) + "\n"


# ============================================================================
# ETL Reader Class
# ============================================================================

class ETLReader:
    """统一的 ETL 读取器"""

    def __init__(self, workspace_root: Path | None = None, repo_root: Path | None = None):
        self.workspace_root = (workspace_root or WORKSPACE_ROOT).resolve()
        self.repo_root = (repo_root or _find_repo_root(self.workspace_root)).resolve()

    def _infer_layer(self, task_name: str) -> str:
        """推断任务层级"""
        normalized = task_name.strip().lower()
        for layer in ("fact", "dim", "aggr", "topic", "app"):
            if f".{layer}_" in normalized or normalized.startswith(layer + "_"):
                return layer
        return "app"

    def _get_task_file_path(self, task_name: str) -> Path:
        """获取本地任务文件路径"""
        layer = self._infer_layer(task_name)
        return self.repo_root / "XT" / layer / f"{task_name}.sql"

    def _read_local_task(self, task_name: str) -> dict[str, Any] | None:
        """从本地文件读取任务"""
        file_path = self._get_task_file_path(task_name)
        if not file_path.exists():
            return None
        
        try:
            raw_code = file_path.read_text(encoding="utf-8")
            sections = split_sections(raw_code)
            desc = (sections.get("##Description##") or "").strip()
            taskinfo = parse_taskinfo(sections.get("##TaskInfo##") or "")
            
            return {
                "source": "local",
                "file_path": str(file_path),
                "description": desc,
                "creator": taskinfo.get("creator", ""),
                "target_db": taskinfo.get("target_db", ""),
                "target_table": taskinfo.get("target_table", ""),
                "source_db": taskinfo.get("source_db", ""),
                "raw_code": raw_code,
            }
        except Exception as exc:
            logger.warning("读取本地任务文件失败 %s: %s", file_path, exc)
            return None

    def _fetch_from_api(self, task_name: str, access_token: str | None = None) -> dict[str, Any] | None:
        """从 XT API 获取任务"""
        try:
            client = XTClient(
                base_url=_resolve_xt_base_url(),
                access_token=access_token,
            )
            config_result = client.get_task_config(task_name)
            config_data = config_result.get("data") or {}
            # 不传 version_id，直接用 task_name 调用即可拿到最新代码
            # 注意：传 version_id 反而会报"该任务版本不存在"
            code_result = client.get_task_code(task_name)
            
            data = code_result.get("data") or {}
            raw_code = data.get("raw_code", "")
            
            sections = split_sections(raw_code)
            taskinfo = parse_taskinfo(sections.get("##TaskInfo##") or "")
            desc = (sections.get("##Description##") or "").strip()
            
            return {
                "source": "api",
                "description": desc,
                "creator": taskinfo.get("creator", ""),
                "target_db": taskinfo.get("target_db", ""),
                "target_table": taskinfo.get("target_table", ""),
                "source_db": taskinfo.get("source_db", ""),
                "raw_code": raw_code,
                "api_response": {
                    "code": code_result,
                    "config": config_result,
                },
            }
        except Exception as exc:
            logger.debug("从 XT API 获取任务失败: %s", exc)
            return None

    def fetch_etl_info(
        self,
        task_name: str,
        from_source: str = "auto",
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """获取 ETL 信息"""
        # 规范化任务名
        task_name = task_name.strip()
        
        result: dict[str, Any] = {
            "success": False,
            "task_name": task_name,
            "source": None,
            "error_message": None,
        }
        
        # 尝试本地查询
        if from_source in ("local", "auto"):
            local_result = self._read_local_task(task_name)
            if local_result:
                result["success"] = True
                result["source"] = "local"
                result.update(local_result)
                
                # 提取表结构
                raw_code = local_result.get("raw_code", "")
                table_profile = extract_table_profile_from_raw_code(
                    raw_code,
                    task_name=task_name,
                    fallback_owner=local_result.get("creator", ""),
                )
                result["table_profile"] = table_profile
                
                # 重命名 raw_code 为 etl_code
                result["etl_code"] = result.pop("raw_code")
                
                # 构建任务配置
                result["task_config"] = {
                    "description": local_result.get("description"),
                    "creator": local_result.get("creator"),
                    "target_table": local_result.get("target_table"),
                    "target_db": local_result.get("target_db"),
                    "source_db": local_result.get("source_db"),
                }
                
                return result
            
            if from_source == "local":
                result["error_message"] = f"本地文件不存在: {self._get_task_file_path(task_name)}"
                return result
        
        # 尝试 API 查询
        if from_source in ("api", "auto"):
            api_result = self._fetch_from_api(task_name, access_token)
            if api_result:
                result["success"] = True
                result["source"] = "api"
                result.update(api_result)
                
                # 提取表结构
                raw_code = api_result.get("raw_code", "")
                table_profile = extract_table_profile_from_raw_code(
                    raw_code,
                    task_name=task_name,
                    fallback_owner=api_result.get("creator", ""),
                )
                result["table_profile"] = table_profile
                
                # 重命名 raw_code 为 etl_code
                result["etl_code"] = result.pop("raw_code")
                
                # 构建任务配置
                result["task_config"] = {
                    "description": api_result.get("description"),
                    "creator": api_result.get("creator"),
                    "target_table": api_result.get("target_table"),
                    "target_db": api_result.get("target_db"),
                    "source_db": api_result.get("source_db"),
                }
                
                return result
            
            if from_source == "api":
                result["error_message"] = "从 XT API 获取任务失败"
                return result
        
        # 两者都失败
        result["error_message"] = (
            f"无法获取任务信息: 本地文件不存在，且 XT API 不可用"
        )
        return result


# ============================================================================
# Token Resolution Functions
# ============================================================================

def _resolve_xt_base_url() -> str:
    """解析 XT 基础 URL"""
    return str(_get_config_value("XT_BASE_URL", DEFAULT_XT_BASE_URL))


def _get_xt_token_via_mtsso() -> str:
    """通过 auth 模块换票，获取 xt.keetapp.com access-token。"""
    scripts_dir = Path(__file__).resolve().parents[1]
    scripts_str = str(scripts_dir)
    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)
    from capability5_meta.auth import get_xt_token as _auth_get_xt_token

    return _auth_get_xt_token()


def _resolve_access_token(explicit_token: str | None = None) -> str:
    """解析 XT token。默认先交给 mtcli SSO，仅在服务要求 header 时调用。"""
    if explicit_token:
        return explicit_token
    return _get_xt_token_via_mtsso()


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_fetch(args: argparse.Namespace) -> int:
    """获取 ETL 信息"""
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    reader = ETLReader(workspace_root=WORKSPACE_ROOT, repo_root=repo_root)
    
    result = reader.fetch_etl_info(
        task_name=args.task_name,
        from_source=args.from_source,
        access_token=args.access_token,
    )
    
    if args.format == "text":
        if result.get("success"):
            print(f"Task Name: {result.get('task_name')}")
            print(f"Source: {result.get('source')}")
            print(f"Description: {result.get('task_config', {}).get('description', '')}")
            print(f"Creator: {result.get('task_config', {}).get('creator', '')}")
            print(f"Target Table: {result.get('task_config', {}).get('target_table', '')}")
            print("")
            print("Table Profile:")
            table_profile = result.get("table_profile", {})
            print(f"  Table Name: {table_profile.get('table_name', '')}")
            print(f"  Table Owner: {table_profile.get('table_owner', '')}")
            print("")
            print("Columns:")
            for col in table_profile.get("columns", []):
                print(f"  {col.get('name')}  {col.get('type')}  {col.get('comment', '')}")
        else:
            print(f"Error: {result.get('error_message')}", file=sys.stderr)
    else:
        _print_json(result)
    
    if args.output_path:
        _write_json(Path(args.output_path), result)
    
    return 0 if result.get("success") else 1


def cmd_parse_ddl(args: argparse.Namespace) -> int:
    """解析表结构信息"""
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    reader = ETLReader(workspace_root=WORKSPACE_ROOT, repo_root=repo_root)
    
    result = reader.fetch_etl_info(
        task_name=args.task_name,
        from_source=args.from_source,
        access_token=args.access_token,
    )
    
    if not result.get("success"):
        print(f"Error: {result.get('error_message')}", file=sys.stderr)
        return 1
    
    table_profile = result.get("table_profile", {})
    
    if args.format == "text":
        print(render_table_profile_text(table_profile), end="")
    else:
        _print_json(table_profile)
    
    if args.output_path:
        _write_json(Path(args.output_path), table_profile)
    
    return 0


# ============================================================================
# CLI Parser
# ============================================================================

def _build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器"""
    parser = argparse.ArgumentParser(
        description="Keeta XT ETL Reader - 统一的 XT 任务配置和代码查询工具"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # fetch 命令
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="获取 XT 任务配置和 ETL 代码",
    )
    fetch_parser.add_argument(
        "--task-name",
        required=True,
        help="XT 任务名称（格式：hmart_sailor_global.<layer>_<table_name>）",
    )
    fetch_parser.add_argument(
        "--from-source",
        choices=["local", "api", "auto"],
        default="auto",
        help="查询源（默认: auto - 本地优先）",
    )
    fetch_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="输出格式",
    )
    fetch_parser.add_argument(
        "-o", "--output",
        dest="output_path",
        default="",
        help="输出文件路径",
    )
    fetch_parser.add_argument(
        "--repo-root",
        default="",
        help="仓库根路径（默认: 自动检测）",
    )
    fetch_parser.add_argument(
        "--access-token",
        default="",
        help="XT API token（可选；默认由 mtcli SSO 登录态处理）",
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # parse-ddl 命令
    parse_parser = subparsers.add_parser(
        "parse-ddl",
        help="解析 XT 任务的表结构信息（DDL）",
    )
    parse_parser.add_argument(
        "--task-name",
        required=True,
        help="XT 任务名称",
    )
    parse_parser.add_argument(
        "--from-source",
        choices=["local", "api", "auto"],
        default="auto",
        help="查询源（默认: auto）",
    )
    parse_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="输出格式",
    )
    parse_parser.add_argument(
        "-o", "--output",
        dest="output_path",
        default="",
        help="输出文件路径",
    )
    parse_parser.add_argument(
        "--repo-root",
        default="",
        help="仓库根路径",
    )
    parse_parser.add_argument(
        "--access-token",
        default="",
        help="XT API token（可选；默认由 mtcli SSO 登录态处理）",
    )
    parse_parser.set_defaults(func=cmd_parse_ddl)

    return parser


# ============================================================================
# Main Entry Point
# ============================================================================

def main() -> int:
    """主入口"""
    parser = _build_parser()
    args = parser.parse_args()
    
    try:
        return args.func(args)
    except ReaderError as exc:
        print(f"[keeta_xt_etl_reader] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[keeta_xt_etl_reader] Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


# ── 规范接口 ─────────────────────────────────────────────────────
def run(args):
    """供 cli.py 通过 dispatch 调用的统一入口"""
    import subprocess as _sp, json as _json, sys as _sys, os as _os

    SKILL_DIR = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    cmd = [
        _sys.executable,
        _os.path.abspath(__file__),
        "fetch",
        "--task-name", args.task_name,
        "--from-source", getattr(args, "from_source", "api"),
        "--format", "json",
    ]
    output_path = getattr(args, "output", "")
    if output_path:
        cmd += ["-o", output_path]

    env = {**_os.environ, "PYTHONPATH": SKILL_DIR}
    result = _sp.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print(result.stderr, file=_sys.stderr)
        raise SystemExit(result.returncode)

    if getattr(args, "code_only", False):
        try:
            d = _json.loads(result.stdout)
            raw = (d.get("api_response") or {}).get("code", {}).get("data", {}).get("raw_code", "")
            print(raw or d.get("description") or "NO ETL CODE")
            return
        except Exception:
            pass
    print(result.stdout)
