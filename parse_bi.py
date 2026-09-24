import json
from collections import defaultdict

with open("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json") as f:
    d = json.load(f)

print("=== NEW SIGNS (Last 10 days) ===")
ns = d.get("Last 10 days - New Signs", {}).get("data", {}).get("data", [])
daily = defaultdict(lambda: {"Top-Tier": 0, "Mid-Tier": 0, "Must-have": 0})
for row in ns:
    date, tier, count = row[0], row[1], int(row[2])
    daily[date][tier] = count

week_total = {"Top-Tier": 0, "Mid-Tier": 0, "Must-have": 0}
for date in sorted(daily.keys()):
    t = daily[date]
    total = sum(t.values())
    print(f"  {date}: Top={t['Top-Tier']} Mid={t['Mid-Tier']} MH={t['Must-have']} Total={total}")
    # Sum for our week (6/28 - 7/4)
    if "20260628" <= date <= "20260704":
        for k in week_total:
            week_total[k] += t[k]

print(f"\n  WEEK TOTAL (6/28-7/4): Top={week_total['Top-Tier']} Mid={week_total['Mid-Tier']} MH={week_total['Must-have']} Grand={sum(week_total.values())}")

print("\n=== ORDERS (Last 10 days) ===")
orders = d.get("Last 10 Days - Order Performance", {}).get("data", {}).get("data", [])
order_daily = defaultdict(lambda: {"Top-Tier": 0, "Mid-Tier": 0, "Must-have": 0})
for row in orders:
    date, tier, count = row[0], row[1], int(row[2])
    order_daily[date][tier] = count
for date in sorted(order_daily.keys()):
    t = order_daily[date]
    total = sum(t.values())
    print(f"  {date}: Top={t['Top-Tier']:,} Mid={t['Mid-Tier']:,} MH={t['Must-have']:,} Total={total:,}")

print("\n=== PROMOTION COVERAGE (Last 10 days) ===")
promo = d.get("Last 10 days - Promotion", {}).get("data", {}).get("data", [])
print("  date | col1(20%cov?) | col2(40%cov?) | col3(total?)")
for row in promo:
    date = row[0]
    vals = [float(x) for x in row[1:]]
    print(f"  {date}: {vals[0]*100:.1f}% | {vals[1]*100:.1f}% | {vals[2]*100:.1f}%")

print("\n=== USER EXPERIENCE / CANCEL RATE (Last 10 days) ===")
ux = d.get("Last 10 days - User Experience", {}).get("data", {}).get("data", [])
print("  date | col1 | col2 | col3")
for row in ux:
    date = row[0]
    vals = [float(x) for x in row[1:]]
    print(f"  {date}: {vals[0]*100:.2f}% | {vals[1]*100:.2f}% | {vals[2]*100:.2f}%")
