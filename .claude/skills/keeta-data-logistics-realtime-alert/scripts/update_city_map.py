#!/usr/bin/env python3
"""
更新城市名映射缓存文件 data/city_name_map.json
数据来源: mart_sailor_global.dim_city_snap_d

用法:
    python3 update_city_map.py              # 用最新分区更新
    python3 update_city_map.py --dt 20260614  # 指定分区日期
"""
import json
import os
import subprocess
import sys
import argparse
from datetime import datetime, timedelta

import shutil

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(SKILL_DIR, "data", "city_name_map.json")
SPACE_ID = "109495"
QUEUE = "root.fra02.hadoop-sailor.query"
REGIONS = ("AE", "SA", "HK", "QA", "KW", "BH", "BR")


def _resolve_hive_cmd():
    """动态查找 kdata/keeta_bi_skill.py 路径，避免硬编码。"""
    # 优先查找 kdata 软链接
    kdata_bin = shutil.which("kdata", path=os.path.expanduser("~/bin") + ":" + os.environ.get("PATH", ""))
    if kdata_bin:
        return [kdata_bin]
    # 回退: 查找 keeta_bi_skill.py
    candidates = [
        os.path.expanduser("~/.openclaw/skills/keeta-data-query/scripts/capability2_hive/keeta_bi_skill.py"),
        os.path.expanduser("~/.openclaw/skills/keeta-data-query/scripts/kdata.py"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return [sys.executable, p]
    # 最后尝试直接 python3 + 默认路径
    return [sys.executable, candidates[0]]


def get_latest_dt():
    """获取最近可用分区日期（T-1）"""
    return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


def query_city_map(dt: str) -> dict:
    sql = f"""
SELECT DISTINCT operation_city_name_zh, operation_city_name_en, operation_city_name_local, region
FROM mart_sailor_global.dim_city_snap_d
WHERE dt = '{dt}'
  AND operation_city_name_zh IS NOT NULL
  AND operation_city_name_en IS NOT NULL
  AND region IN ({', '.join(repr(r) for r in REGIONS)})
ORDER BY region, operation_city_name_zh
"""
    sql_file = "/tmp/_update_city_map_query.sql"
    with open(sql_file, "w") as f:
        f.write(sql)

    hive_cmd = _resolve_hive_cmd()
    result = subprocess.run(
        hive_cmd + ["run", sql_file,
         "-p", SPACE_ID, "-q", QUEUE, "--json"],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"[ERROR] 查询失败:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # 找到 JSON 输出（跳过非 JSON 的 stderr 混入）
    data = None
    for line in result.stdout.splitlines():
        if line.strip().startswith("{"):
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if data is None:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"[ERROR] 无法解析 Hive 输出为 JSON: {e}", file=sys.stderr)
            print(f"  stdout (first 500 chars): {result.stdout[:500]}", file=sys.stderr)
            sys.exit(1)

    rows = data["data"]
    cols = data["columns"]
    zh2en, en2zh = {}, {}
    en_aliases = {}  # 英文名对应的所有中文别名列表
    conflicts = []   # 记录多对一映射冲突
    for row in rows:
        r = dict(zip(cols, row))
        zh, en = r["operation_city_name_zh"], r["operation_city_name_en"]
        if zh and en:
            zh2en[zh] = en
            if en not in en_aliases:
                en_aliases[en] = []
            if zh not in en_aliases[en]:
                en_aliases[en].append(zh)
            if en in en2zh and en2zh[en] != zh:
                conflicts.append(f"  {en}: {en2zh[en]} vs {zh}")
            else:
                en2zh[en] = zh
    if conflicts:
        print(f"[WARN] 发现 {len(conflicts)} 个英文名多对一映射冲突（保留先出现的中文名）:", file=sys.stderr)
        for c in conflicts:
            print(c, file=sys.stderr)
    # 只保留有多个别名的条目
    en_aliases = {k: v for k, v in en_aliases.items() if len(v) > 1}
    return zh2en, en2zh, en_aliases


def main():
    parser = argparse.ArgumentParser(description="更新城市名映射缓存")
    parser.add_argument("--dt", default=None, help="分区日期 yyyymmdd，默认 T-1")
    args = parser.parse_args()

    dt = args.dt or get_latest_dt()
    print(f"[city_map] 查询分区 dt={dt} ...")

    zh2en, en2zh, en_aliases = query_city_map(dt)
    print(f"[city_map] 共 {len(zh2en)} 个城市")
    if en_aliases:
        print(f"[city_map] 发现 {len(en_aliases)} 个英文名有多个中文别名")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    result = {
        "zh_to_en": zh2en,
        "en_to_zh": en2zh,
        "en_aliases": en_aliases,  # 英文名对应的多个中文别名（仅有冲突时存在）
        "source": "mart_sailor_global.dim_city_snap_d",
        "dt": dt,
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[city_map] ✅ 已写入 {OUTPUT_PATH}")
    print("\n城市列表：")
    for zh, en in sorted(zh2en.items()):
        print(f"  {zh} → {en}")


if __name__ == "__main__":
    main()
