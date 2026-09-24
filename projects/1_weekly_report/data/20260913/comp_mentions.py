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

KWS = ['99','Yellow','red','IFood','ifood','Rappi','Loggi']
hits = []
for r in main:
    desc = ' '.join(str(x) for x in [r[9], r[13]] if x)
    found = [k for k in KWS if k in desc]
    if found:
        hits.append(dict(
            merchant=r[1], mid=r[2], region=(r[0] or '').split('-')[2] if len((r[0] or '').split('-'))>2 else '?',
            bd=r[4], matter=r[8], desc=str(r[13] or '')[:600].replace('\n',' | '), kw=','.join(found)))
print('total competitor-mention visits this week:', len(hits))
by_kw = Counter(h['kw'].split(',')[0] for h in hits)
print('by keyword:', by_kw.most_common())

# risk signals
RISK = ['独家','exclusiv','签','sign','upfront','加码','proposal','oferta','Offer','offer','contract','合同','rendeu','mudou','saiu','trocar','migrar','switch','sair']
risky = [h for h in hits if any(s.lower() in h['desc'].lower() for s in ['exclusiv','upfront','独家','trocou','mudou para','saiu da','encerrar','fechar conta','cancelar keeta','proposta'])]
print('\n=== HIGH-RISK SIGNAL MENTIONS ===', len(risky))
for h in risky:
    print(f"\n[{h['merchant']} | {h['mid']} | {h['region']} | BD:{h['bd']} | kw:{h['kw']}]")
    print('  ', h['desc'][:400])
