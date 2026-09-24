import openpyxl, re, json
from collections import Counter, defaultdict
wb = openpyxl.load_workbook('visit_record_20260906.xlsx', read_only=True)
ws = wb['0']
rows = list(ws.iter_rows(values_only=True))
data = rows[1:]

def parse_date(t):
    m = re.match(r'(\d+)年(\d+)月(\d+)日', str(t) if t else '')
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

# core period: 8/31-9/4 (5 weekdays); 8/30 and 9/5 are edge
core = [r for r in data if parse_date(r[3]) and parse_date(r[3]) >= (2026,8,31) and parse_date(r[3]) <= (2026,9,4)]
print("CORE (8/31-9/4):", len(core))

# offline rate
vt = Counter(str(r[7]) for r in core)
offline = vt.get('上門拜訪', 0)
print("上門拜訪:", offline, "/", len(core), "=", round(100*offline/len(core),1), "%")

# new-sign related visits: 一級拜訪事項 contains 新簽 or 新簽階段 non-empty
ns = [r for r in core if '新簽' in str(r[8]) or (str(r[10]).strip() and str(r[10]).strip() not in ('nan','None'))]
print("new-sign related visits:", len(ns), f"({100*len(ns)/len(core):.1f}%)")

# 一級拜訪事項 breakdown
print("\n一級拜訪事項:")
for k, v in Counter(str(r[8]).replace('\n','/') for r in core).most_common(10):
    print(f"  {k}: {v}")

# BD activity
bd = Counter(str(r[5]) for r in core)
print("\nactive BDs:", len(bd))
per_day = {k: round(v/5, 1) for k, v in bd.items()}
top10 = sorted(per_day.items(), key=lambda x: -x[1])[:10]
bot10 = sorted(per_day.items(), key=lambda x: x[1])[:10]
print("Top10 per-day:", top10)
print("Bottom10 per-day:", bot10)

# region
def region(org):
    org = str(org)
    if 'West Special' in org: return 'West Special (Santos)'
    if 'Western' in org: return 'Western'
    if 'Southern' in org: return 'Southern'
    if 'Eastern' in org: return 'Eastern'
    return 'OTHER'
reg = Counter(region(r[0]) for r in core)
print("\nregions:", dict(reg))

# region per BD per day: need BD->region mapping (by majority)
bd_region = defaultdict(Counter)
for r in core:
    bd_region[str(r[5])][region(r[0])] += 1
bd2reg = {b: c.most_common(1)[0][0] for b, c in bd_region.items() if c.most_common(1)[0][0] != 'OTHER'}
reg_bd = defaultdict(list)
for b, rg in bd2reg.items():
    reg_bd[rg].append(b)
print("\nBDs per region:", {k: len(v) for k, v in reg_bd.items()})
reg_stats = {}
for rg, bds in reg_bd.items():
    total = sum(bd[b] for b in bds)
    reg_stats[rg] = {"visits": total, "bds": len(bds), "per_bd_day": round(total/len(bds)/5, 1)}
print(json.dumps(reg_stats, indent=1))

# daily volume
dm = Counter(f"{parse_date(r[3])[1]}/{parse_date(r[3])[2]}" for r in core)
print("\ndaily:", dict(sorted(dm.items())))

# save per-BD
out = {b: {"visits": v, "per_day": round(v/5,1), "region": bd2reg.get(b,'OTHER')} for b, v in bd.items()}
json.dump(out, open('bd_visit_stats.json','w'), indent=1)
print("saved bd_visit_stats.json")
