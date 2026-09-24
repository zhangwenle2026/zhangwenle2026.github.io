import re, json, uuid

xml = open('rank_wiki_0825_before.xml').read()
D = json.load(open('order_penetration_data_0825_final.json'))

def nid():
    return str(uuid.uuid4())

def td(content, tag='td', bold=False):
    inner = f'<strong>{content}</strong>' if bold else content
    return f'<{tag} colwidth="[68]" nodeId="{nid()}">\n<p nodeId="{nid()}">{inner}</p>\n</{tag}>'

def tr(cells):
    return f'<tr nodeId="{nid()}">\n' + '\n'.join(cells) + '\n</tr>'

CITY_LABEL = {'Southern': 'Southern / 南部 / Sul', 'Western': 'Western / 西部 / Oeste', 'Santos': 'Santos / 桑托斯 / Santos'}

WS_HEADER = ['Rank / 排名 / Posição', 'BD', 'BDM', 'City / 城市 / Cidade', '🔴NS', '🟡NO', '🟢NOP', 'HV+2', 'Total / 总分 / Pontuação Total', 'Status / 状态 / Status']

def bd_row(b, rank_disp, with_city=True, bold_total=True):
    cells = [td(rank_disp)]
    cells.append(td(b['bd']))
    cells.append(td(b['bdm']))
    if with_city:
        cells.append(td(CITY_LABEL[b['city']]))
    cells.append(td(str(b['not_signed'])))
    cells.append(td(str(b['not_online'])))
    cells.append(td(str(b['not_operating'])))
    cells.append(td(f"+{b['hv_count']}" if b['hv_count'] else '-'))
    if b['total'] >= 15:
        cells.append(td(str(b['total']), bold=bold_total))
        cells.append(td('✅ 达标'))
    else:
        cells.append(td(str(b['total']), bold=bold_total))
        cells.append(td(f"还差 {15 - b['total']} 分"))
    return tr(cells)

def rank_rows(bds, with_city=True):
    out = []
    rank = 0; prev = None; pos = 0
    for b in bds:
        pos += 1
        if b['total'] != prev:
            rank = pos; prev = b['total']
        if b['total'] == 0:
            rd = ' -'
        else:
            m = '🥇 ' if rank == 1 else ('🥈 ' if rank == 2 else ('🥉 ' if rank == 3 else ''))
            rd = f'{m}{rank}' if m else str(rank)
        out.append(bd_row(b, rd, with_city))
    return out

# ===== Build WS table (63 rows) =====
ws_rows = [tr([td(h, tag='th') for h in WS_HEADER])]
ws_rows += rank_rows(D['ws_bds'], with_city=True)
ws_table = f'<table nodeId="a0591c40-271b-42d3-bced-45aae57db40e">\n' + '\n'.join(ws_rows) + '\n</table>'

# ===== Santos table (8 rows) =====
santos_header = ['Rank / 排名 / Posição', 'BD', 'BDM', '🔴NS', '🟡NO', '🟢NOP', 'HV+2', 'Total / 总分 / Pontuação Total', 'Status / 状态 / Status']
s_rows = [tr([td(h, tag='th') for h in santos_header])]
s_rows += rank_rows(D['santos_bds'], with_city=False)
santos_table = f'<table nodeId="f084a98d-b471-47ce-a986-aa1b455be014">\n' + '\n'.join(s_rows) + '\n</table>'

# ===== BDM table (12 rows) =====
bdm_header = ['Rank / 排名 / Posição', 'BDM', 'City / 城市 / Cidade', 'BD Count / BD人数 / Nº de BDs', 'Team Score / 团队总分 / Pontuação da Equipe', 'Avg / 人均 / Média', 'Status / 状态 / Status']
b_rows = [tr([td(h, tag='th') for h in bdm_header])]
sorted_bdm = sorted(D['bdm_summary'].items(), key=lambda x: -x[1]['avg'])
rank = 0; prev = None; pos = 0
for bdm, v in sorted_bdm:
    pos += 1
    if v['avg'] != prev:
        rank = pos; prev = v['avg']
    m = '🥇 ' if rank == 1 else ('🥈 ' if rank == 2 else ('🥉 ' if rank == 3 else ''))
    rd = f'{m}{rank}' if m else str(rank)
    avg_str = ('%g' % v['avg'])
    status = '✅ 达标' if v['qualified'] else f"还差 {round(15 - v['avg'], 2):g}"
    qualified_bold = v['qualified']
    b_rows.append(tr([
        td(rd), td(bdm), td(CITY_LABEL[v['city']]), td(str(v['bd_count'])),
        td(str(v['team_score']), bold=qualified_bold), td(avg_str, bold=qualified_bold), td(status),
    ]))
bdm_table = f'<table nodeId="8c44d276-8dbd-4d81-9978-247e3f27e23a">\n' + '\n'.join(b_rows) + '\n</table>'

# ===== Text blocks =====
ws_q = [b for b in D['ws_bds'] if b['total'] >= 15]
ws_q_str = ', '.join(f"{b['bd']} ({b['total']})" for b in ws_q)
ws_note = f'<p nodeId="3bf351f0-4960-4de5-b01b-fe4cfeb07758"><em>Full 63-BD rankings shown. / 完整63人排名如上。 / Ranking completo de 63 BDs acima.</em></p>\n'
ws_note += f'<p nodeId="c00235d3-6a15-4454-b9a7-d38eb88b0ccd">✅ <strong>Qualified BDs / 达标BD / BDs Qualificados: {len(ws_q)}</strong> — {ws_q_str}</p>'

s_q = [b for b in D['santos_bds'] if b['total'] >= 15]
s_q_str = ', '.join(f"{b['bd']} ({b['total']})" for b in s_q)
s_note = f'<p nodeId="9f9acb0f-2be8-4e70-bcfd-99cd32c13e05">✅ <strong>Qualified BD / 达标BD / BD Qualificado: {len(s_q)}</strong> — {s_q_str}</p>'

top_bdm = sorted_bdm[0]
bdm_note = f'<p nodeId="0e326a0d-a089-4bf6-bcfb-007669ab336c">✅ <strong>Qualified BDMs / 达标BDM / BDMs Qualificados: 0</strong> — No BDM has reached the 15 avg threshold yet. Closest: {sorted_bdm[0][0]} (avg {sorted_bdm[0][1]["avg"]}), {sorted_bdm[1][0]} (avg {sorted_bdm[1][1]["avg"]}). / 达标BDM 0人：暂无BDM达到人均15分。最接近：{sorted_bdm[0][0]} (avg {sorted_bdm[0][1]["avg"]}), {sorted_bdm[1][0]} (avg {sorted_bdm[1][1]["avg"]})。</p>'

R = D['regional_summary']
top_bd = D['ws_bds'][0]
summary_items = [
    f"Total Score / 总分 / Pontuação Total: {R['total_score']} (BD-Level / BD级别 / Nível BD: {R['bd_level_score']})",
    f"Qualified BDs / 达标BD / BDs Qualificados: {len(ws_q)+len(s_q)}/71 ({round((len(ws_q)+len(s_q))/71*100,1)}%)",
    "Qualified BDMs / 达标BDM / BDMs Qualificados: 0/12",
    f"Top BD / 最佳BD / Melhor BD: {top_bd['bd']} ({top_bd['total']} pts)",
    f"Top BDM / 最佳BDM / Melhor BDM: {top_bdm[0]} (avg {top_bdm[1]['avg']})",
]
summary_block = '<ul nodeId="07bcddc2-720d-4d7d-ba01-af5872e39917">\n'
li_nids = ['5831ce19-877e-4eaf-a0f7-911565cccc06', 'd8d36c48-2bca-4bfd-9fa9-21c79f3ab37c', 'c81b77cf-90f2-4821-b403-a6644db859c1', '0dedfbe2-ee63-4153-80b7-51ce3f78a4e7', 'd9af30d4-85df-4cba-807a-31af7e369822']
for nid_, item in zip(li_nids, summary_items):
    summary_block += f'<li nodeId="{nid_}">{item}</li>\n'
summary_block += '</ul>'

new_title = 'SP Metro Incentive Race Rankings — Aug 25 / 圣保罗都市圈激励赛排名 — 8月25日 / Classificação da Corrida de Incentivo — 25 de Agosto'
new_date_p = '<p nodeId="d2e4a5fe-31c4-4195-b3d1-b72c64d649b4"><strong>Data as of / 数据截至 / Dados截至:</strong> August 25, 2026 (BRT)</p>'

# ===== Splice =====
tables = []
for m in re.finditer(r'<table nodeId="([^"]+)">', xml):
    s = m.start()
    e = xml.index('</table>', s) + len('</table>')
    tables.append((m.group(1), s, e))
t_ws = next(t for t in tables if t[0] == 'a0591c40-271b-42d3-bced-45aae57db40e')
t_santos = next(t for t in tables if t[0] == 'f084a98d-b471-47ce-a986-aa1b455be014')
t_bdm = next(t for t in tables if t[0] == '8c44d276-8dbd-4d81-9978-247e3f27e23a')

ws_note_start = t_ws[2]
ws_table_end_first = xml.index('</table>', t_ws[1]) + len('</table>')  # end of original WS table
santos_h2_start = xml.index('<h2 nodeId="911f1579-0250-436b-86ad-48fa35fbc5b6">')
out = xml[:t_ws[1]] + '\n' + ws_table + '\n' + ws_note + xml[santos_h2_start:]

# Recompute positions after first splice (only ONE table each now)
tables = []
for m in re.finditer(r'<table nodeId="([^"]+)">', out):
    s = m.start()
    e = out.index('</table>', s) + len('</table>')
    tables.append((m.group(1), s, e))
t_santos = next(t for t in tables if t[0] == 'f084a98d-b471-47ce-a986-aa1b455be014')
t_bdm = next(t for t in tables if t[0] == '8c44d276-8dbd-4d81-9978-247e3f27e23a')

# Replace Santos table + note (from end of Santos table to BDM h2)
bdm_h2_start = out.index('<h2 nodeId="4ae3293e-0cd8-419e-a013-16e5e3ca7d68">')
santos_table_end = t_santos[2]
out = out[:t_santos[1]] + '\n' + santos_table + '\n' + s_note + out[bdm_h2_start:]

# Recompute
tables = []
for m in re.finditer(r'<table nodeId="([^"]+)">', out):
    s = m.start()
    e = out.index('</table>', s) + len('</table>')
    tables.append((m.group(1), s, e))
t_bdm = next(t for t in tables if t[0] == '8c44d276-8dbd-4d81-9978-247e3f27e23a')

# Replace BDM table + bdm note + summary block: replace from end of BDM table to Links h2
links_h2_start = out.index('<h2 nodeId="0c32cc8f-5ead-440e-9f9c-26347d146ed8">')
orig_summary_h2 = '<h2 nodeId="5ac187a1-6a0b-4533-9840-1e712fc2d187">1.5 Summary <em>小结</em> <em>Resumo</em></h2>'
bdm_table_end = t_bdm[2]
out = out[:t_bdm[1]] + '\n' + bdm_table + '\n' + bdm_note + '\n' + orig_summary_h2 + '\n' + summary_block + out[links_h2_start:]

# Title & date
out = re.sub(r'<km-title nodeId="[^"]+">[^<]*</km-title>', f'<km-title nodeId="81364d1f-067e-4f55-ad90-dd604102dd1f">{new_title}</km-title>', out, count=1)
out = out.replace('<p nodeId="d2e4a5fe-31c4-4195-b3d1-b72c64d649b4"><strong>Data as of / 数据截至 / Dados截至:</strong> August 23, 2026 (BRT)</p>', new_date_p)

open('rank_wiki_0825.xml', 'w').write(out)
print('written, len:', len(out))
# sanity checks
assert out.count('<table') == out.count('</table>'), f"table mismatch {out.count('<table')} {out.count('</table>')}"
assert out.count('<tr') == out.count('</tr>'), f"tr mismatch {out.count('<tr')} {out.count('</tr>')}"
assert 'August 25, 2026' in out and 'Aug 25' in out
assert 'wanessasilva' in out
print('WS rows:', len(D['ws_bds']), '| Santos rows:', len(D['santos_bds']), '| BDM rows:', len(sorted_bdm))
print('tables:', out.count('<table'), '| trs:', out.count('<tr'))
