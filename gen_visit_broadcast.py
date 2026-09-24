#!/usr/bin/env python3
"""
实时拜访数据播报 — 生成图片并发送到 BDM 群
每天巴西时间 12:00、14:00、16:00、18:00 推送当天实时累计数据

数据源：visit-record-query skill (step5)
目标群：BDM群 gid: 70411703622
机器人：AI Eric (appkey: 65a6eb395a)
"""

import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ============ CONFIG ============
REGION = "BR"
TEAM_ID = "16"
TARGET_GID = "70411703622"
BOT_APPKEY = "65a6eb395a"
SKILL_DIR = Path.home() / ".openclaw/skills/visit-record-query"
OUTPUT_DIR = Path("/tmp/files")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BRT = ZoneInfo("America/Sao_Paulo")


# ============ STEP 1: Fetch all visit records for today ============
def fetch_all_visits():
    """Fetch all today's visit records with pagination."""
    now_brt = datetime.now(BRT)
    today_str = now_brt.strftime("%Y%m%d")

    all_rows = []
    page = 1
    page_size = 50
    total = None

    while True:
        env = os.environ.copy()
        env.update({
            "REGION": REGION,
            "TEAM_ID": TEAM_ID,
            "START_DATE": today_str,
            "END_DATE": today_str,
            "PAGE_NUM": str(page),
            "PAGE_SIZE": str(page_size),
        })

        result = subprocess.run(
            ["bash", str(SKILL_DIR / "apis/step5_query_visit_records.sh")],
            env=env, capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            print(f"[ERROR] step5 failed on page {page}: {result.stderr}", file=sys.stderr)
            break

        with open("/tmp/visit_result.json") as f:
            data = json.load(f)

        if data.get("code") != 0:
            print(f"[ERROR] API returned code={data.get('code')}: {data.get('msg')}", file=sys.stderr)
            break

        rows = data.get("data", {}).get("row", [])
        if total is None:
            total = data.get("data", {}).get("total", 0)

        all_rows.extend(rows)

        if len(all_rows) >= total or not rows:
            break

        page += 1

    print(f"[INFO] Fetched {len(all_rows)} / {total} visit records for {today_str}")
    return all_rows, now_brt


# ============ STEP 2: Aggregate data (Metropolitan Region, 3 cities only) ============
# Only: Western SP Metropolitan, Southern SP Metropolitan, Santos City
# Exclude: Northeast SP Metropolitan
INCLUDED_CITIES = ["Western", "Southern", "Santos"]

def _city_included(city_name):
    """Check if a city/sub-region is in our 3-city scope."""
    for keyword in INCLUDED_CITIES:
        if keyword.lower() in city_name.lower():
            return True
    return False

def aggregate_visits(rows):
    """Aggregate visit data — Metropolitan Region, 3 cities only (excl. Northeast)."""
    emp_stats = defaultdict(lambda: {
        "total": 0,
        "offline": 0,
        "online": 0,
        "org": "",
        "city": "",
    })

    city_stats = defaultdict(lambda: {"total": 0, "employees": set()})
    skipped = 0

    for r in rows:
        cell = r.get("cell", {})
        org = cell.get("ORG_LINK", {}).get("content", "")
        parts = org.split("-")
        region = parts[1].strip() if len(parts) > 1 else ""

        # Only keep Metropolitan Region
        if "Metropolitan" not in region:
            skipped += 1
            continue

        # City = level 3 in ORG_LINK
        city = parts[2].strip() if len(parts) > 2 else "Other"

        # Exclude Northeast
        if not _city_included(city):
            skipped += 1
            continue

        name = cell.get("VISIT_EMPLOY_NAME", {}).get("content", "Unknown")
        vtype = cell.get("VISIT_TYPE", {}).get("content", "")

        emp_stats[name]["total"] += 1
        emp_stats[name]["org"] = org
        emp_stats[name]["city"] = city

        # Offline vs Online
        if vtype in ("上門拜訪", "實體拜訪", "上门物料拜访"):
            emp_stats[name]["offline"] += 1
        else:
            emp_stats[name]["online"] += 1

        city_stats[city]["total"] += 1
        city_stats[city]["employees"].add(name)

    if skipped:
        print(f"[INFO] Filtered: kept 3 cities (excl. Northeast), skipped {skipped} records")

    return emp_stats, city_stats


# ============ STEP 3: Generate image (compact, mobile-friendly) ============
def generate_image(emp_stats, city_stats, now_brt, total_visits):
    """Generate a compact broadcast image card optimized for mobile group chat."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.font_manager import FontProperties
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "matplotlib", "-q"], check=True)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.font_manager import FontProperties

    # Font setup
    font_path = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
    if Path(font_path).exists():
        fp = FontProperties(fname=font_path, size=10)
        fp_title = FontProperties(fname=font_path, size=14, weight="bold")
        fp_small = FontProperties(fname=font_path, size=9)
        fp_header = FontProperties(fname=font_path, size=10, weight="bold")
    else:
        fp = FontProperties(size=10)
        fp_title = FontProperties(size=14, weight="bold")
        fp_small = FontProperties(size=9)
        fp_header = FontProperties(size=10, weight="bold")

    # Sort employees by total visits (desc), show all (Metropolitan is smaller)
    sorted_emps = sorted(emp_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    top_n = len(sorted_emps)  # Show all Metropolitan BDs
    display_emps = sorted_emps[:top_n]
    remaining = 0

    # Layout calculations
    row_h = 0.40
    n_cities = len(city_stats)
    header_h = 1.8
    city_section_h = 0.5 + n_cities * 0.32
    table_h = 0.6 + (top_n + 1) * row_h
    footer_h = 0.6
    fig_height = header_h + city_section_h + table_h + footer_h
    fig_width = 8

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.set_xlim(0, fig_width)
    ax.set_ylim(0, fig_height)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # === HEADER ===
    time_str = now_brt.strftime("%H:%M")
    date_str = now_brt.strftime("%Y-%m-%d")

    # Title bar
    rect = mpatches.FancyBboxPatch((0.15, fig_height - header_h), fig_width - 0.3, header_h - 0.1,
                                   boxstyle="round,pad=0.08",
                                   facecolor="#1565c0", edgecolor="none")
    ax.add_patch(rect)

    ax.text(fig_width / 2, fig_height - 0.5, "Real-time Visit Broadcast",
            fontproperties=fp_title, ha="center", va="center", color="white")
    ax.text(fig_width / 2, fig_height - 1.0,
            f"Metropolitan Region | {date_str} {time_str} BRT",
            fontproperties=fp, ha="center", va="center", color="#bbdefb")
    ax.text(fig_width / 2, fig_height - 1.45,
            f"Total: {total_visits} visits | {len(emp_stats)} BDs active",
            fontproperties=fp, ha="center", va="center", color="#e3f2fd")

    # === CITY SUMMARY ===
    y = fig_height - header_h - 0.3
    ax.text(0.4, y, "By City / Sub-region", fontproperties=fp_header, va="center", color="#37474f")
    ax.plot([0.3, fig_width - 0.3], [y - 0.12, y - 0.12], color="#e0e0e0", linewidth=0.8)

    y -= 0.38
    sorted_cities = sorted(city_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    for city_name, stats in sorted_cities:
        short_name = city_name[:28]
        ax.text(0.5, y, short_name, fontproperties=fp_small, va="center", color="#424242")
        ax.text(5.8, y, f"{stats['total']}", fontproperties=fp, va="center", color="#1b5e20", fontweight="bold")
        ax.text(6.5, y, f"({len(stats['employees'])} BDs)", fontproperties=fp_small, va="center", color="#757575")
        y -= 0.32

    # === BDs TABLE ===
    y -= 0.25
    ax.text(0.4, y, f"BDM Ranking ({top_n} BDs)", fontproperties=fp_header, va="center", color="#37474f")
    ax.plot([0.3, fig_width - 0.3], [y - 0.12, y - 0.12], color="#e0e0e0", linewidth=0.8)

    # Table header
    y -= 0.38
    x_cols = [0.4, 1.0, 5.2, 6.3, 7.3]
    col_headers = ["#", "Name", "Total", "Offline", "Online"]
    for x, h in zip(x_cols, col_headers):
        ax.text(x, y, h, fontproperties=fp_header, va="center", color="#546e7a")

    # Rows
    for idx, (name, stats) in enumerate(display_emps):
        y -= row_h

        # Zebra striping
        if idx % 2 == 0:
            rect = mpatches.FancyBboxPatch((0.3, y - 0.14), fig_width - 0.6, row_h - 0.04,
                                           boxstyle="round,pad=0.01",
                                           facecolor="#f5f5f5", edgecolor="none")
            ax.add_patch(rect)

        # Rank
        rank_str = str(idx + 1)
        rank_color = ["#f44336", "#ff6d00", "#ff9800"][idx] if idx < 3 else "#757575"
        ax.text(x_cols[0], y, rank_str, fontproperties=fp_small, va="center",
                color=rank_color, fontweight="bold")

        # Name
        display_name = name if len(name) <= 24 else name[:22] + ".."
        ax.text(x_cols[1], y, display_name, fontproperties=fp_small, va="center", color="#212121")

        # Numbers
        ax.text(x_cols[2], y, str(stats["total"]), fontproperties=fp,
                va="center", color="#1b5e20", fontweight="bold")
        ax.text(x_cols[3], y, str(stats["offline"]), fontproperties=fp_small,
                va="center", color="#e65100")
        ax.text(x_cols[4], y, str(stats["online"]), fontproperties=fp_small,
                va="center", color="#0277bd")

    # Footer
    if remaining > 0:
        y -= row_h
        ax.text(fig_width / 2, y, f"... and {remaining} more BDs",
                fontproperties=fp_small, ha="center", va="center", color="#9e9e9e")

    y -= 0.35
    ax.text(fig_width / 2, max(0.15, y),
            "Offline = In-person | Online = Phone/IM/Video",
            fontproperties=fp_small, ha="center", va="center", color="#bdbdbd")

    plt.tight_layout(pad=0.2)

    output_path = OUTPUT_DIR / "visit_broadcast.png"
    plt.savefig(str(output_path), dpi=180, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close()

    print(f"[INFO] Image saved: {output_path}")
    return str(output_path)


# ============ STEP 4: Upload image ============
def upload_image(image_path):
    """Upload image via s3-file-clawx-uploader."""
    upload_script = Path.home() / ".openclaw/skills/s3-file-clawx-uploader/scripts/upload.py"
    if not upload_script.exists():
        print(f"[WARN] Upload script not found, using local path")
        return image_path

    result = subprocess.run(
        [sys.executable, str(upload_script), image_path, "--json"],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        print(f"[ERROR] Upload failed: {result.stderr}", file=sys.stderr)
        return None

    # Try to parse the full output as JSON
    full_output = result.stdout.strip()
    try:
        data = json.loads(full_output)
        url = data.get("url") or data.get("fileUrl")
        if url:
            print(f"[INFO] Uploaded: {url}")
            return url
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: find URL in output
    import re
    for line in full_output.split("\n"):
        m = re.search(r'https?://[^\s"\']+', line)
        if m:
            print(f"[INFO] Uploaded (parsed): {m.group(0)}")
            return m.group(0)

    print(f"[ERROR] Could not parse upload result: {full_output}", file=sys.stderr)
    return None


# ============ STEP 5: Send to group ============
def send_to_group(image_url):
    """Send image to BDM group via cap001 module."""
    cap_script = Path.home() / ".openclaw/workspace/cap001_dx_group_msg.py"
    if not cap_script.exists():
        print(f"[WARN] cap001 script not found")
        return False

    import importlib.util
    spec = importlib.util.spec_from_file_location("cap001", str(cap_script))
    cap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cap)

    try:
        result = cap.send_group_image(image_url, group_id=TARGET_GID, robot="ai_eric")
        print(f"[INFO] Sent to group {TARGET_GID}: {json.dumps(result)}")
        return True
    except Exception as e:
        print(f"[ERROR] Send via cap001 failed: {e}", file=sys.stderr)
        return False


# ============ MAIN ============
def main():
    print("=" * 50)
    print("  Real-time Visit Broadcast")
    print("=" * 50)

    # 1. Fetch data
    rows, now_brt = fetch_all_visits()
    if not rows:
        print("[INFO] No visits yet today. Skipping broadcast.")
        print("OUTPUT_URL=NONE")
        return

    # 2. Aggregate (Metropolitan only)
    emp_stats, city_stats = aggregate_visits(rows)
    total_visits = sum(s["total"] for s in emp_stats.values())

    if not emp_stats:
        print("[INFO] No Metropolitan Region visits yet. Skipping.")
        print("OUTPUT_URL=NONE")
        return

    print(f"[INFO] Metropolitan: {total_visits} visits by {len(emp_stats)} BDs across {len(city_stats)} cities")

    # 3. Generate image
    image_path = generate_image(emp_stats, city_stats, now_brt, total_visits)

    # 4. Upload
    image_url = upload_image(image_path)
    if not image_url:
        print("[ERROR] Failed to get image URL")
        print("OUTPUT_URL=FAILED")
        sys.exit(1)

    # 5. Try sending to group (cap001)
    sent = send_to_group(image_url)

    # Output URL for cron/agent to use
    print(f"\nOUTPUT_URL={image_url}")
    if sent:
        print("[SUCCESS] Broadcast sent to BDM group!")
    else:
        print("[INFO] Image ready. Agent should use message tool to send.")


if __name__ == "__main__":
    main()
