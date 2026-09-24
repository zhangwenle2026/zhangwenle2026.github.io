import openpyxl, re, json
from collections import Counter, defaultdict
wb = openpyxl.load_workbook('visit_record_20260906.xlsx', read_only=True)
ws = wb['0']
rows = list(ws.iter_rows(values_only=True))
hdr = list(rows[0])
data = rows[1:]

def parse_date(t):
    m = re.match(r'(\d+)年(\d+)月(\d+)日', str(t) if t else '')
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

# visit type
print("拜訪類型:", Counter(str(r[7]) for r in data))
# offline rate: 上門拜訪 vs others
# 新簽階段
print("新簽階段:", Counter(str(r[10]) for r in data if str(r[10]).strip()))
# BD mis
bd = Counter(str(r[5]) for r in data)
print("\nunique BDs:", len(bd))
for k, v in bd.most_common():
    print(f"  {k}: {v}")
# region from org
def region(org):
    org = str(org)
    if 'West Special' in org or 'Santos' in org: return 'Santos/WestSpecial'
    if 'Western' in org: return 'Western'
    if 'Southern' in org: return 'Southern'
    if 'Eastern' in org: return 'Eastern'
    return 'OTHER:' + org[:60]
reg = Counter(region(r[0]) for r in data)
print("\nregions:")
for k, v in reg.most_common():
    print(f"  {k}: {v}")
