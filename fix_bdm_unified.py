import re

with open('order_penetration_dashboard_v4.html') as f:
    html = f.read()

# 1. Remove BDM tabs bar
old_tabs = '''<div class="tabs">
<button class="tab active" onclick="switchBdmTab('bdm-ws')">Western + Southern \u8054\u5408\u8d5b\u533a</button>
<button class="tab" onclick="switchBdmTab('bdm-santos')">Santos \u8d5b\u533a</button>
</div>'''
assert old_tabs in html, "BDM tabs not found"
html = html.replace(old_tabs, '')

# 2. Extract WS and Santos BDM table rows
m_ws = re.search(r'<div id="tab-bdm-ws" class="tab-content active"><div class="table-wrap">(.*?)</div></div>', html, re.DOTALL)
ws_content = m_ws.group(1)
m_santos = re.search(r'<div id="tab-bdm-santos" class="tab-content"><div class="table-wrap">(.*?)</div></div>', html, re.DOTALL)
santos_content = m_santos.group(1)

ws_rows = re.findall(r'<tr[^>]*>.*?</tr>', ws_content, re.DOTALL)
santos_rows = re.findall(r'<tr[^>]*>.*?</tr>', santos_content, re.DOTALL)

def extract_text(s):
    return re.sub(r'<[^>]+>', '', s).strip()

def parse_row(row):
    tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
    if len(tds) != 7:
        return None
    return {
        'bdm': extract_text(tds[1]),
        'city': extract_text(tds[2]),
        'bd_count': extract_text(tds[3]),
        'score': extract_text(tds[4]),
        'avg': float(extract_text(tds[5])),
        'status_html': tds[6],
    }

all_bdms = []
for row in ws_rows + santos_rows:
    d = parse_row(row)
    if d:
        all_bdms.append(d)

print(f"Total BDMs parsed: {len(all_bdms)}")
for b in all_bdms:
    print(f"  {b['bdm']} ({b['city']}): score={b['score']}, avg={b['avg']}")

# Sort by avg desc
all_bdms.sort(key=lambda x: -x['avg'])

# Build unified table
def build_row(rank, b):
    medal = ''
    row_class = ''
    if rank == 1:
        medal = '\U0001f947 '
        row_class = 'gold'
    elif rank == 2:
        medal = '\U0001f948 '
        row_class = 'silver'
    elif rank == 3:
        medal = '\U0001f949 '
        row_class = 'bronze'
    return f'<tr class="{row_class}"><td>{medal}{rank}</td><td>{b["bdm"]}</td><td>{b["city"]}</td><td>{b["bd_count"]}</td><td><b>{b["score"]}</b></td><td class="score-total"><b>{b["avg"]}</b></td><td>{b["status_html"]}</td></tr>'

bdm_header = '<thead><tr><th>Rank \u6392\u540d</th><th>BDM</th><th>City \u57ce\u5e02</th><th>BD Count BD\u6570</th><th>Team Score \u56e2\u961f\u603b\u5206</th><th>Avg \u4eba\u5747</th><th>Status \u8fbe\u6807</th></tr></thead>'

rows_html = '\n'.join(build_row(i+1, b) for i, b in enumerate(all_bdms))

unified_block = f'''<div class="table-wrap">
<table>{bdm_header}<tbody>
{rows_html}
</tbody></table></div>'''

# Replace the two tab-content divs with the unified block
old_block_pattern = re.compile(
    r'<div id="tab-bdm-ws" class="tab-content active"><div class="table-wrap">.*?</div></div>\s*'
    r'<div id="tab-bdm-santos" class="tab-content"><div class="table-wrap">.*?</div></div>',
    re.DOTALL
)
html2, n = old_block_pattern.subn(unified_block, html)
assert n == 1, f"Expected 1 replacement, got {n}"

# 3. Remove switchBdmTab JS function (no longer needed)
js_pattern = re.compile(r'function switchBdmTab\(tab\) \{.*?\n\}\n', re.DOTALL)
html2, n2 = js_pattern.subn('', html2)
print(f"JS function removed: {n2}")

# 4. Update MODULE 4 section title subtitle to clarify unified ranking
old_title = 'MODULE 4: BDM Team Rankings BDM\u56e2\u961f\u6392\u540d Ranking BDM'
new_title = 'MODULE 4: BDM Team Rankings BDM\u56e2\u961f\u6392\u540d Ranking BDM \u2014 12 BDMs Unified \u7edf\u4e00\u6392\u540d'
assert old_title in html2
html2 = html2.replace(old_title, new_title)

with open('order_penetration_dashboard_v4.html', 'w') as f:
    f.write(html2)

print("\nUnified BDM table written.")
print(f"HTML size: {len(html2)} bytes")

# Verify: print the BDM section
m = re.search(r'MODULE 4.*?(?=MODULE 5)', html2, re.DOTALL)
print(m.group(0)[:2000])
