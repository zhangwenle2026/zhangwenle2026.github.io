#!/usr/bin/env python3
"""
keeta-data-html-publish: 将本地 HTML 文件发布到 html-hosting-hub.mynocode.host
通过 Supabase Edge Function 完成上传、元数据写入和权限管理。

子命令:
  publish  — 发布/更新 HTML 文件（默认，兼容旧用法）
  access   — 管理文件访问权限（list/add/remove/transfer）
"""

import argparse
import json
import os
import sys
import uuid as _uuid
import urllib.request
import urllib.error

FUNCTION_URL = os.environ.get(
    "PUBLISH_FUNCTION_URL",
    "https://dblgj1nam8vwyfgtgs.database.sankuai.com/functions/v1/publish-html",
)


# ── 发布功能 ─────────────────────────────────────────────────────

def _build_multipart(fields, file_field, file_path):
    boundary = _uuid.uuid4().hex
    body = b""
    for key, value in fields.items():
        if value is None:
            continue
        body += "--{}\r\n".format(boundary).encode()
        body += 'Content-Disposition: form-data; name="{}"\r\n\r\n'.format(key).encode()
        body += "{}\r\n".format(value).encode()

    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        content = f.read()
    body += "--{}\r\n".format(boundary).encode()
    body += 'Content-Disposition: form-data; name="{}"; filename="{}"\r\n'.format(
        file_field, filename
    ).encode()
    body += b"Content-Type: text/html\r\n\r\n"
    body += content
    body += b"\r\n"
    body += "--{}--\r\n".format(boundary).encode()
    return body, "multipart/form-data; boundary={}".format(boundary)


def publish(html_path, name=None, creator_mis=None, creator_name=None,
            is_private=True, update_uuid=None):
    fields = {}
    if name:
        fields["name"] = name
    if creator_mis:
        fields["creator_mis"] = creator_mis
    if creator_name:
        fields["creator_name"] = creator_name
    fields["is_private"] = "true" if is_private else "false"
    if update_uuid:
        fields["uuid"] = update_uuid

    body, content_type = _build_multipart(fields, "file", html_path)

    req = urllib.request.Request(
        FUNCTION_URL,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            msg = error_json.get("error", error_body)
        except json.JSONDecodeError:
            msg = error_body
        print("❌ 发布失败 ({}): {}".format(e.code, msg), file=sys.stderr)
        sys.exit(1)

    mode = result.get("mode", "create")
    mode_cn = "更新" if mode == "update" else "发布"

    print("✅ {}成功".format(mode_cn))
    print()
    print("🌐 访问地址: {}".format(result["url"]))
    print("📋 UUID: {}".format(result["uuid"]))
    print("📄 文件名: {}".format(result["filename"]))
    print("📦 大小: {} bytes".format(result["size"]))

    return result


# ── 权限管理功能 ──────────────────────────────────────────────────

def _json_request(payload):
    """发送 JSON 请求到 Edge Function，返回解析后的 dict。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        FUNCTION_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            msg = error_json.get("error", error_body)
        except json.JSONDecodeError:
            msg = error_body
        print("❌ 请求失败 ({}): {}".format(e.code, msg), file=sys.stderr)
        sys.exit(1)


def access_list(uuid, operator_mis):
    result = _json_request({
        "action": "list",
        "uuid": uuid,
        "operator_mis": operator_mis,
    })
    print("📋 文件权限信息 [{}]".format(uuid))
    print()
    print("👤 Owner:    {}".format(result.get("owner", "—")))
    print("🔒 Private:  {}".format(result.get("is_private", True)))
    managers = result.get("managers", [])
    viewers = result.get("viewers", [])
    print("🛡️  Managers: {}".format(", ".join(managers) if managers else "(无)"))
    print("👁️  Viewers:  {}".format(", ".join(viewers) if viewers else "(无)"))


def access_add(uuid, mis_list, role, operator_mis):
    result = _json_request({
        "action": "add",
        "uuid": uuid,
        "mis_list": mis_list,
        "role": role,
        "operator_mis": operator_mis,
    })
    print("✅ 已添加 {} 为 {}".format(", ".join(mis_list), role))
    print()
    print("当前 Managers: {}".format(", ".join(result.get("managers", [])) or "(无)"))
    print("当前 Viewers:  {}".format(", ".join(result.get("viewers", [])) or "(无)"))


def access_remove(uuid, mis_list, operator_mis):
    result = _json_request({
        "action": "remove",
        "uuid": uuid,
        "mis_list": mis_list,
        "operator_mis": operator_mis,
    })
    print("✅ 已移除 {} 的权限".format(", ".join(mis_list)))
    print()
    print("当前 Managers: {}".format(", ".join(result.get("managers", [])) or "(无)"))
    print("当前 Viewers:  {}".format(", ".join(result.get("viewers", [])) or "(无)"))


def access_transfer(uuid, new_owner, operator_mis):
    result = _json_request({
        "action": "transfer",
        "uuid": uuid,
        "new_owner": new_owner,
        "operator_mis": operator_mis,
    })
    print("✅ 所有权已转让")
    print()
    print("旧 Owner: {}".format(result.get("old_owner", "—")))
    print("新 Owner: {}".format(result.get("new_owner", "—")))


# ── CLI 入口 ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="keeta-data-html-publish: 发布 HTML + 权限管理",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── publish 子命令 ──
    p_publish = subparsers.add_parser("publish", help="发布或更新 HTML 文件")
    p_publish.add_argument("html_file", help="本地 HTML 文件路径")
    p_publish.add_argument("--name", help="发布后的文件名（不含 .html，默认取原文件名）")
    p_publish.add_argument("--mis", required=True, help="创建者 MIS 账号")
    p_publish.add_argument("--creator-name", required=True, help="创建者名称")
    p_publish.add_argument("--public", action="store_true", help="设为公开文件")
    p_publish.add_argument("--update", metavar="UUID", help="更新已有页面（传入已发布的 UUID）")

    # ── access 子命令 ──
    p_access = subparsers.add_parser("access", help="管理文件访问权限")
    access_sub = p_access.add_subparsers(dest="access_cmd")

    # access list
    p_list = access_sub.add_parser("list", help="查看文件权限列表")
    p_list.add_argument("--uuid", required=True, help="文件 UUID")
    p_list.add_argument("--operator", required=True, help="操作者 MIS")

    # access add
    p_add = access_sub.add_parser("add", help="添加访问/管理权限")
    p_add.add_argument("--uuid", required=True, help="文件 UUID")
    p_add.add_argument("--mis", required=True, help="要授权的 MIS（多个用逗号分隔）")
    p_add.add_argument("--role", choices=["viewer", "manager"], default="viewer", help="角色（默认 viewer）")
    p_add.add_argument("--operator", required=True, help="操作者 MIS（需为 owner 或 manager）")

    # access remove
    p_remove = access_sub.add_parser("remove", help="移除权限")
    p_remove.add_argument("--uuid", required=True, help="文件 UUID")
    p_remove.add_argument("--mis", required=True, help="要移除的 MIS（多个用逗号分隔）")
    p_remove.add_argument("--operator", required=True, help="操作者 MIS（需为 owner 或 manager）")

    # access transfer
    p_transfer = access_sub.add_parser("transfer", help="转让文件所有权")
    p_transfer.add_argument("--uuid", required=True, help="文件 UUID")
    p_transfer.add_argument("--to", required=True, help="新 owner 的 MIS")
    p_transfer.add_argument("--operator", required=True, help="操作者 MIS（需为当前 owner）")

    args = parser.parse_args()

    # ── 兼容旧用法：无子命令 → 当作 publish ──
    if args.command is None:
        # 检查是否像旧用法（第一个 positional arg 是文件路径）
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("publish", "access"):
            # 旧用法兼容：直接当 publish 处理
            old_parser = argparse.ArgumentParser()
            old_parser.add_argument("html_file")
            old_parser.add_argument("--name")
            old_parser.add_argument("--mis", required=True)
            old_parser.add_argument("--creator-name", required=True)
            old_parser.add_argument("--public", action="store_true")
            old_parser.add_argument("--update", metavar="UUID")
            old_args = old_parser.parse_args()
            if not os.path.exists(old_args.html_file):
                print("❌ 文件不存在: {}".format(old_args.html_file), file=sys.stderr)
                sys.exit(1)
            publish(
                html_path=old_args.html_file,
                name=old_args.name,
                creator_mis=old_args.mis,
                creator_name=old_args.creator_name,
                is_private=not old_args.public,
                update_uuid=old_args.update,
            )
            return
        parser.print_help()
        sys.exit(1)

    if args.command == "publish":
        if not os.path.exists(args.html_file):
            print("❌ 文件不存在: {}".format(args.html_file), file=sys.stderr)
            sys.exit(1)
        publish(
            html_path=args.html_file,
            name=args.name,
            creator_mis=args.mis,
            creator_name=args.creator_name,
            is_private=not args.public,
            update_uuid=args.update,
        )

    elif args.command == "access":
        if not args.access_cmd:
            p_access.print_help()
            sys.exit(1)

        if args.access_cmd == "list":
            access_list(args.uuid, args.operator)

        elif args.access_cmd == "add":
            mis_list = [m.strip() for m in args.mis.split(",") if m.strip()]
            access_add(args.uuid, mis_list, args.role, args.operator)

        elif args.access_cmd == "remove":
            mis_list = [m.strip() for m in args.mis.split(",") if m.strip()]
            access_remove(args.uuid, mis_list, args.operator)

        elif args.access_cmd == "transfer":
            access_transfer(args.uuid, getattr(args, "to"), args.operator)


if __name__ == "__main__":
    main()
