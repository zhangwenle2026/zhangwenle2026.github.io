#!/usr/bin/env python3
"""
TechPortal Skill 执行结果上报脚本

用法:
  python3 send_report.py '<JSON数据>'
  python3 send_report.py --file report.json
"""

import io
import json
import os
import sys
import math
import time
import random
import subprocess
import ssl
import urllib.request

# ============ 常量配置 ============

REPORT_URL = "https://plx.meituan.com"
SDK_VER = "2.1.3"
CATEGORY = "data_sdk_techportal"
APPNM = "lx-skill"
NM = "PV"
CT = "web"
SDK_ENV = "online"
VAL_CID = "c_techportal_sk27amkp"
PHASE_START = 0
PHASE_END = 1

# union_id / lxcuid 持久化目录及文件
# 放在用户 home 下的 .lx-skill-reporter/ 子目录，跨平台通用（Windows/macOS/Linux）
# os.path.expanduser("~") 在各平台均返回正确的用户目录：
#   macOS/Linux: /Users/xxx 或 /home/xxx
#   Windows:     C:\Users\xxx
LX_IDS_DIR = os.path.join(os.path.expanduser("~"), ".lx-skill-reporter")
LX_IDS_FILE = os.path.join(LX_IDS_DIR, "lx_ids.json")

# ============ misId 自动提取 ============

def get_mis_id_from_git():
    """
    自动提取 misId，依次尝试：
    1. git config --global user.name
    2. git config --global user.email（取 @ 前的值）
    3. whoami
    均失败时返回空字符串。
    """
    try:
        name = subprocess.check_output(
            ["git", "config", "--global", "user.name"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="replace").strip()
        if name:
            return name
    except Exception:
        pass

    try:
        email = subprocess.check_output(
            ["git", "config", "--global", "user.email"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="replace").strip()
        if email:
            at_idx = email.find("@")
            return email[:at_idx] if at_idx > 0 else email
    except Exception:
        pass

    try:
        name = subprocess.check_output(
            ["whoami"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="replace").strip()
        if name:
            return name
    except Exception:
        pass

    return ""

# ============ lxcuid / union_id 持久化 ============

def load_lx_ids():
    """
    从 ~/.lx-skill-reporter/lx_ids.json 读取已持久化的 union_id / lxcuid。
    文件不存在或格式错误时返回 None。
    """
    try:
        if not os.path.exists(LX_IDS_FILE):
            return None
        with io.open(LX_IDS_FILE, "r", encoding="utf-8") as _f:
            data = json.loads(_f.read())
        if isinstance(data.get("union_id"), str) and data["union_id"] \
                and isinstance(data.get("lxcuid"), str) and data["lxcuid"]:
            return {"union_id": data["union_id"], "lxcuid": data["lxcuid"]}
    except Exception:
        pass
    return None


def save_lx_ids(union_id):
    """将 union_id / lxcuid 持久化到 ~/.lx-skill-reporter/lx_ids.json。"""
    try:
        if not os.path.exists(LX_IDS_DIR):
            os.makedirs(LX_IDS_DIR)
        with io.open(LX_IDS_FILE, "w", encoding="utf-8") as _f:
            _f.write(json.dumps({"union_id": union_id, "lxcuid": union_id}, indent=2))
    except Exception as e:
        print("[lx-reporter] 保存 lx_ids 失败：{}".format(e), file=sys.stderr)

# ============ ID 生成算法 ============

def _generate_t():
    """时间戳（毫秒）转 16 进制，附加同毫秒内自增计数。"""
    d = int(time.time() * 1000)
    i = 0
    while int(time.time() * 1000) == d and i < 200:
        i += 1
    return format(d, "x") + format(i, "x")


def _generate_r():
    """Math.random() 等效：随机浮点数转 16 进制（去掉小数点）。
    直接用 random.getrandbits 生成随机整数并转 16 进制，避免浮点数科学计数法导致格式异常。
    """
    return format(random.getrandbits(52), "x")


def _generate_ua():
    """
    固定字符串 'lx-skill-agent' 按 4 字节分组异或后转 16 进制。
    与灵犀 websdk UA 熵算法一致。
    """
    ua = "lx-skill-agent"
    buf = []
    ret = 0

    def xor(result, byte_array):
        tmp = 0
        for j, b in enumerate(byte_array):
            tmp |= (b << (j * 8))
        return result ^ tmp

    for ch in ua:
        buf.insert(0, ord(ch) & 0xFF)
        if len(buf) >= 4:
            ret = xor(ret, buf)
            buf = []
    if buf:
        ret = xor(ret, buf)

    return format(ret & 0xFFFFFFFF, "x")


def generate_lxcuid():
    """生成 union_id / lxcuid，格式：T-R-UA-se-T。"""
    t1 = _generate_t()
    r = _generate_r()
    ua = _generate_ua()
    se = "0"
    t2 = _generate_t()
    return "{}-{}-{}-{}-{}".format(t1, r, ua, se, t2)


def _rnd_seed():
    """3 位随机 16 进制串。"""
    seed = math.floor(1 + random.random() * 65535)
    return format(seed, "04x")[1:]  # 保证4位十六进制，截去首位得3位


def generate_msid():
    """生成 msid，格式：time-seed-seed-seed。"""
    t = format(int(time.time() * 1000), "x")
    return "-".join([t, _rnd_seed(), _rnd_seed(), _rnd_seed()])


def generate_req_id():
    """生成 req_id，格式：timestamp-r1-r2。"""
    ts = format(int(time.time() * 1000), "x")
    r1 = math.floor(random.random() * 65535)
    r2 = math.floor(random.random() * 65535)
    return "{}-{}-{}".format(ts, r1, r2)

# ============ 数据封装 ============

def generate_report_ids():
    """
    生成所有上报所需 ID。
    union_id / lxcuid 优先从 ~/.lx-skill-reporter/lx_ids.json 读取，不存在时生成并保存。
    msid / req_id 每次重新生成。
    seq 由调用方根据 phase 决定（PHASE_START=0 / PHASE_END=1）。
    """
    saved = load_lx_ids()
    if saved:
        union_id = saved["union_id"]
    else:
        union_id = generate_lxcuid()
        save_lx_ids(union_id)

    return {
        "union_id": union_id,
        "lxcuid": union_id,
        "msid": generate_msid(),
        "req_id": generate_req_id(),
        "tm": int(time.time() * 1000),
    }


def build_report_data(skill_data, ids):
    """
    封装上报数据。
    misId 优先使用传入值；未传时自动从 git 提取。
    phase=PHASE_START 时 total_step 固定为 0，seq 固定为 0。
    phase=PHASE_END 时上报完整字段，seq 固定为 1。
    """
    mis_id = skill_data.get("misId")
    if not mis_id:
        mis_id = get_mis_id_from_git()

    phase = skill_data.get("phase")
    # seq：start=0，end=1，无 phase 时降级为 0
    seq = PHASE_END if phase == PHASE_END else PHASE_START

    custom = {
        "phase": phase,
        "is_success": skill_data.get("is_success"),
        "misId": mis_id,
        "start_time": skill_data.get("start_time"),
        "end_time": skill_data.get("end_time"),
        "executed_step": skill_data.get("executed_step"),
        "failed_step_name": skill_data.get("failed_step_name", ""),
        "skill_id": skill_data.get("skill_id"),
        "skill_name": skill_data.get("skill_name"),
        "skill_version": skill_data.get("skill_version", ""),
        "summary": skill_data.get("summary", ""),
        "env": skill_data.get("env", ""),
    }
    # start 阶段 total_step 固定为 0，end 阶段取传入值
    if phase == PHASE_START:
        custom["total_step"] = 0
    else:
        custom["total_step"] = skill_data.get("total_step")

    event = {
        "nt": 5,
        "nm": NM,
        "isauto": 7,
        "tm": ids["tm"],
        "val_cid": VAL_CID,
        "req_id": ids["req_id"],
        "refer_req_id": ids["req_id"],
        "seq": seq,
        "val_lab": {"custom": custom},
    }

    return [{
        "union_id": ids["union_id"],
        "lxcuid": ids["lxcuid"],
        "sdk_ver": SDK_VER,
        "category": CATEGORY,
        "appnm": APPNM,
        "msid": ids["msid"],
        "ct": CT,
        "sdk_env": SDK_ENV,
        "_misid": mis_id,
        "evs": [event],
    }]

# ============ 网络请求 ============

def send_report(data, max_retries=3):
    """
    通过 urllib 发送 HTTPS POST 请求，最多重试 max_retries 次。
    全部失败后降级使用 curl 发送。
    返回 True 表示成功，False 表示失败。
    """
    body = json.dumps(data).encode("utf-8")
    ctx = ssl.create_default_context()

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                REPORT_URL,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, context=ctx, timeout=3) as resp:
                resp_body = resp.read().decode("utf-8")
                if 200 <= resp.status < 300:
                    print("[lx-reporter] 上报成功 status={} body={}".format(resp.status, resp_body), file=sys.stderr)
                    return True
        except Exception as e:
            print("[lx-reporter] 上报失败（第 {}/{} 次）：{}".format(attempt, max_retries, e), file=sys.stderr)
            if attempt == max_retries:
                print("[lx-reporter] 已达最大重试次数，降级使用 curl 上报", file=sys.stderr)
        if attempt < max_retries:
            time.sleep(1)

    return send_report_via_curl(data)


def send_report_via_curl(data):
    """
    urllib 重试耗尽后的降级方案：使用系统 curl 命令发送 HTTPS POST 请求。
    返回 True 表示成功，False 表示失败（静默忽略，不阻塞主流程）。
    """
    try:
        body_str = json.dumps(data)
        result = subprocess.run(
            [
                "curl",
                "-s",                          # 静默模式，不显示进度
                "-o", "/dev/null",             # 丢弃响应体
                "-w", "%{http_code}",          # 只输出 HTTP 状态码
                "-X", "POST",
                "-H", "Content-Type: application/json",
                "--data", body_str,
                "--max-time", "3",            # 超时 3 秒
                REPORT_URL,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        status_code = result.stdout.decode("utf-8", errors="replace").strip()
        stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
        if result.returncode == 0 and status_code.isdigit() and 200 <= int(status_code) < 300:
            print("[lx-reporter] curl 降级上报成功 status={}".format(status_code), file=sys.stderr)
            return True
        else:
            print(
                "[lx-reporter] curl 降级上报失败 returncode={} status={} stderr={}".format(
                    result.returncode, status_code, stderr_text
                ),
                file=sys.stderr,
            )
    except Exception as e:
        print("[lx-reporter] curl 降级上报异常：{}".format(e), file=sys.stderr)

    return False


def send_skill_report(skill_data):
    """
    完整上报流程：生成 ID → 封装数据 → 发送请求（urllib，失败后 curl 降级）。

    phase=PHASE_START（0）/ phase=PHASE_END（1）模式：
      - 若 skill_data 含 msid 字段，则用其覆盖自动生成的 msid，确保两次上报使用同一 msid 关联。
      - msid 应事先通过 --gen-msid 生成并以环境变量传入。

    无 phase 字段：兼容旧调用，按原逻辑处理。
    """
    ids = generate_report_ids()

    # 若调用方传入了 msid（start/end 两阶段均支持），用其覆盖自动生成的值
    if skill_data.get("msid"):
        ids = dict(ids)
        ids["msid"] = skill_data["msid"]

    data = build_report_data(skill_data, ids)
    return send_report(data)

# ============ 入口 ============

def main():
    args = sys.argv[1:]

    if not args:
        print("用法:", file=sys.stderr)
        print("  python3 send_report.py '<JSON数据>'", file=sys.stderr)
        print("  python3 send_report.py --file report.json", file=sys.stderr)
        print("  python3 send_report.py --gen-msid               # 生成 msid 输出到 stdout", file=sys.stderr)
        print("  python3 send_report.py --phase start '<JSON数据>'  # 开始上报，JSON 须含 msid 字段", file=sys.stderr)
        print("  python3 send_report.py --phase end '<JSON数据>'    # 结束上报，JSON 须含 msid 字段", file=sys.stderr)
        sys.exit(1)

    # --gen-msid：仅生成并输出 msid，不发送上报
    if args[0] == "--gen-msid":
        print(generate_msid())
        sys.exit(0)

    # 处理 --phase 参数：将其注入 skill_data
    phase_override = None
    if args[0] == "--phase":
        if len(args) < 3:
            print("--phase 需要提供 start|end 和 JSON 数据", file=sys.stderr)
            sys.exit(1)
        raw_phase = args[1]
        if raw_phase == "start":
            phase_override = PHASE_START
        elif raw_phase == "end":
            phase_override = PHASE_END
        else:
            print("--phase 参数无效：{}，应为 start 或 end".format(raw_phase), file=sys.stderr)
            sys.exit(1)
        args = args[2:]  # 剩余部分为 JSON 或 --file

    if not args:
        print("--phase 后需要提供 JSON 数据或 --file 参数", file=sys.stderr)
        sys.exit(1)

    skill_data = None

    if args[0] == "--file":
        if len(args) < 2 or not os.path.exists(args[1]):
            print("文件不存在: {}".format(args[1] if len(args) > 1 else "(未提供)"), file=sys.stderr)
            sys.exit(1)
        with io.open(args[1], "r", encoding="utf-8") as f:
            skill_data = json.load(f)
    else:
        try:
            skill_data = json.loads(args[0])
        except json.JSONDecodeError as e:
            print("JSON 解析失败: {}".format(e), file=sys.stderr)
            sys.exit(1)

    if phase_override is not None:
        skill_data["phase"] = phase_override

    success = send_skill_report(skill_data)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
