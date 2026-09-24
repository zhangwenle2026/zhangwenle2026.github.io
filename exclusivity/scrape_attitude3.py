#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scrape v3: name-based row lookup (list re-sorts live). For each western merchant,
scan all 3 pages, find row by name, click, read Status do Contrato, back."""
import json, subprocess, time, base64

def ab(js, timeout=45):
    b64 = base64.b64encode(js.encode()).decode()
    r = subprocess.run(['agent-browser', 'eval', '-b', b64], capture_output=True, text=True, timeout=timeout)
    out = r.stdout.strip()
    if out.startswith('"') and out.endswith('"'):
        try: out = json.loads(out)
        except: out = out[1:-1]
    return out

rows = json.load(open('/tmp/excl_fresh2.json'))
W = [r for r in rows if r[11] == 'marciojaroslavsky']
names = [r[0].replace(' ~ ', ' ').strip() for r in W]
print('western:', len(names))

next_page = "(function(){const b=Array.from(document.querySelectorAll('button')).filter(x=>/próxima/i.test(x.innerText)); b[0].click(); return 1})()"
back_page = "(function(){const b=Array.from(document.querySelectorAll('button')).filter(x=>/anterior|prev/i.test(x.innerText)); if(b[0])b[0].click(); return 1})()"
voltar = "(function(){const b=Array.from(document.querySelectorAll('button')).filter(x=>/voltar/i.test(x.innerText)); if(b[0])b[0].click(); return 1})()"

# ensure on list page 1
ab(voltar); time.sleep(1.5)
ab(back_page); time.sleep(1); ab(back_page); time.sleep(1.5)

CLICK_JS = """(function(){
  const target = %s;
  const rows = Array.from(document.querySelectorAll('table tbody tr'));
  for (const r of rows) {
    const nm = r.cells[0].innerText.trim().replace(/\\n/g,' ');
    if (nm === target) { r.click(); return 'FOUND'; }
  }
  return 'NOT_ON_PAGE';
})()"""

results = {}
det_js = """(function(){const t=(document.querySelector('h1')||{}).innerText||'?'; const ps=Array.from(document.querySelectorAll('p')).map(p=>p.innerText).filter(x=>/Status do Contrato|Tipo de contrato/i.test(x)); return JSON.stringify({t:t, reports:ps})})()"""

for idx, name in enumerate(names):
    got = False
    for attempt in range(3):
        # try all 3 pages from current position
        for p in range(3):
            cur = ab("(document.body.innerText.match(/Página (\\d+) de 3/)||['','?'])[1]")
            res = ab(CLICK_JS % json.dumps(name))
            if res == 'FOUND':
                time.sleep(2)
                det = ab(det_js)
                try:
                    d = json.loads(det)
                except:
                    d = {'t': det, 'reports': []}
                results[name] = d
                print(idx, name[:26], '->', d['t'][:26], d['reports'])
                ab(voltar); time.sleep(1.5)
                got = True
                break
            else:
                # move to next page
                pg = ab("(document.body.innerText.match(/Página (\\d+) de 3/)||['','?'])[1]")
                if pg == '3':
                    ab(back_page); time.sleep(1); ab(back_page); time.sleep(1.8)
                else:
                    ab(next_page); time.sleep(1.8)
        if got: break
        time.sleep(2)
    if not got:
        results[name] = {'t': 'FAILED', 'reports': []}
        print(idx, name[:26], '-> FAILED')

# restore page 1
ab(back_page); time.sleep(1); ab(back_page)

json.dump(results, open('/tmp/excl_attitude3.json', 'w'), ensure_ascii=False, indent=1)
ok = sum(1 for v in results.values() if v['t'] != 'FAILED' and v['t'] != '?')
print('saved', len(results), 'ok:', ok)
