import openpyxl, warnings, re
from collections import Counter, defaultdict
warnings.filterwarnings('ignore')
wb = openpyxl.load_workbook('visit_record.xlsx', read_only=True)
ws = wb['0']
rows = list(ws.iter_rows(values_only=True))[1:]

def parse_date(t):
    m = re.match(r'2026年(\d+)月(\d+)日', str(t))
    return (int(m.group(1)), int(m.group(2))) if m else None

main = [r for r in rows if parse_date(r[3]) and (9,7) <= parse_date(r[3]) <= (9,12)]
print('window rows:', len(main))
extra = [r for r in rows if parse_date(r[3]) and parse_date(r[3]) <= (9,6)]
print('prior-week stragglers:', len(extra))

DAYS = 5
total = len(main)
onsite = sum(1 for r in main if r[7]=='上門拜訪')
phone = sum(1 for r in main if r[7]=='電話拜訪')
bds = set(r[4] for r in main if r[4])
print(f'total={total} onsite={onsite} phone={phone} offline_rate={onsite/total*100:.1f}% BDs={len(bds)}')
print(f'per BD per day ({DAYS}d): {total/len(bds)/DAYS:.1f}')

region_bd = defaultdict(set); region_n = Counter()
for r in main:
    parts = (r[0] or '').split('-')
    reg = parts[2] if len(parts)>2 else '?'
    region_n[reg] += 1
    if r[4]: region_bd[reg].add(r[4])
for k in ['Southern São Paulo Metropolitan','Western São Paulo Metropolitan','Santos City']:
    n = region_n[k]; nb = len(region_bd[k])
    print(f'{k}: visits={n} bds={nb} per_bd_day={n/nb/DAYS:.1f}')

daily = Counter()
for r in main: daily[parse_date(r[3])] += 1
for d in sorted(daily): print(d, daily[d])

m = Counter((r[8] or '').strip() for r in main)
print('matters:', dict(m))
stage = Counter((r[10] or '').strip() for r in main if (r[10] or '').strip())
print('new signing stage:', dict(stage))
onsite_exsat = sum(1 for r in main if r[7]=='上門拜訪' and parse_date(r[3])<(9,12))
tot_exsat = sum(1 for r in main if parse_date(r[3])<(9,12))
print(f'excl Sat: total={tot_exsat} onsite_rate={onsite_exsat/tot_exsat*100:.1f}%')
