import openpyxl, re
from collections import Counter, defaultdict
wb = openpyxl.load_workbook('visit_record_20260906.xlsx', read_only=True)
ws = wb['0']
rows = list(ws.iter_rows(values_only=True))
data = rows[1:]
print("total rows:", len(data))
dates = []
for r in data:
    t = str(r[3]) if r[3] else ''
    m = re.match(r'(\d+)年(\d+)月(\d+)日', t)
    if m:
        dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
dates.sort()
print("date range:", dates[0], "->", dates[-1])
dm = Counter(f"{d[0]}-{d[1]:02d}-{d[2]:02d}" for d in dates)
print("unique dates:", len(dm))
for k in sorted(dm):
    print(k, dm[k])
