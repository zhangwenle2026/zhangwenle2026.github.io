#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Southern Metropolitan Exclusivity Review — 23 merchants (CM: danielalbuquerque).
Built to the same standard as the Western page (build_html.py), from excl_fresh2.json
(SMB Dashboard exclusivity-tracking scrape, updated 23/09/2026).
Note: no per-case Status do Contrato detail was scraped for Southern — risk uses
etapa + KP field (Aceita/Recusada) as primary signal, upfront amounts as severity."""
import json, re
from collections import Counter

cases = json.load(open('/mnt/openclaw/.openclaw/workspace/exclusivity/cases_southern.json'))

def money(v):
    m = re.search(r'R\$\s*([\d\.]+)', str(v or ''))
    try: return float(m.group(1).replace('.', '')) if m else 0.0
    except: return 0.0
def num(v):
    m = re.search(r'(\d+)', str(v or ''))
    return int(m.group(1)) if m else 0
def keeta_aov(c):
    m = re.search(r'R\$\s*([\d\.]+)', str(c.get('aov_keeta')))
    return m.group(1) if m else ''
def keeta_orders(c):
    m = re.search(r'([\d\.]+)/d', str(c.get('aov_keeta')))
    return m.group(1) if m else ''
def comp_orders(c):
    m = re.search(r'(\d+)', str(c.get('comp_orders') or ''))
    return m.group(1) if m else ''
def comp_aov(c):
    m = re.search(r'R\$\s*([\d\.]+)', str(c.get('comp_aov')))
    return m.group(1) if m else ''
def fmt_money(v):
    if not v: return '—'
    if v >= 1000000: return f"R$ {v/1000000:.2f}M".replace('.00', '')
    return f"R$ {int(round(v/1000))}K"

# classification for Southern (no per-case attitude scrape):
# - etapa KP aceitou -> RESOLVED (we won)
# - etapa Encerrado + KP Recusada -> we refused to counter / lost -> LOST
# - etapa Encerrado (no KP info) + big upfront -> LOST (case closed, comp money won)
# - etapa Encerrado small upfront -> LOST
# - etapa Relatório aprovado / Proposta concluída + upfront -> active fight: HIGH if big
# - etapa Reportado + upfront >= 300K or comp orders >= 300 -> HIGH, else MEDIUM
# - etapa Reportado no intel -> PENDING
for c in cases:
    up = money(c.get('upfront')); co = num(c.get('comp_orders')); et = str(c.get('etapa'))
    kp = str(c.get('kp'))
    if 'aceitou' in et:
        c['cls'] = 'RESOLVED'
    elif 'Encerrado' in et:
        c['cls'] = 'LOST'
    elif 'aprovado' in et or 'Proposta' in et:
        c['cls'] = 'HIGH' if (up >= 300000 or co >= 300) else 'MEDIUM'
    else:  # Reportado
        if up >= 300000 or co >= 5000 or (up >= 100000 and co >= 300):
            c['cls'] = 'HIGH'
        elif up > 0 or co > 0:
            c['cls'] = 'MEDIUM'
        else:
            c['cls'] = 'PENDING'

STAGE = {'Reportado': 'Reported 已上报', 'KP aceitou': 'KP Approved KP已通过', '🔒 Encerrado': 'Closed 已关闭',
         'Relatório BDM e CM aprovado': 'BDM/CM Approved BDM/CM已批', 'Contrato assinado': 'Signed 已签约',
         'Proposta concluída': 'Proposal Done 提案完成'}
RISK = {'LOST': ('Lost 已失守', 'lost'), 'HIGH': ('High 高风险', 'high'), 'MEDIUM': ('Medium 中风险', 'medium'),
        'RESOLVED': ('Resolved 已解除', 'resolved'), 'PENDING': ('Pending 待跟进', 'pending')}
PLAT = {'Yellow': 'Yellow(99)', 'Red': 'Red(iFood)', 'RedYellow': 'Red+Yellow', 'YellowRed': 'Red+Yellow', '': '—'}

def questions_for(c):
    cls = c['cls']; up = money(c.get('upfront')); co_n = num(c.get('comp_orders'))
    nm = c['nome'].strip()
    first = nm.split()[0].strip(',').strip('!') if nm else ''
    up_s = fmt_money(up) if up else ''
    qs = []
    if cls == 'LOST':
        qs = [f"Why did we lose {first}? 为什么丢了{first}？",
              f"How long is the contract? 合同签了多久？",
              f"What can bring {first} back? 什么条件能拉回{first}？"]
    elif cls == 'RESOLVED':
        qs = [f"When do we sign? 什么时候签约？",
              f"What can still go wrong? 还有什么变数？"]
        if up >= 500000:
            qs.append(f"Our {up_s} — one-time or monthly? 我们的{up_s}是一次性还是按月？")
        else:
            qs.append(f"What finally convinced {first}? 最后是什么打动了{first}？")
    elif cls == 'HIGH':
        if co_n:
            qs = [f"The {up_s} — one-time or monthly? {up_s}是一次性还是按月？",
                  f"Does {first} really do {co_n}/day? Check the app. {first}真有日单{co_n}？查App。",
                  f"What is our counter-offer? 我们的还价是什么？"]
        else:
            qs = [f"The {up_s} — one-time or monthly? {up_s}是一次性还是按月？",
                  f"How many orders/day really? Ask, don't guess. 真实日单多少？要问不要猜。",
                  f"What is our counter-offer? 我们的还价是什么？"]
    elif cls == 'MEDIUM':
        qs = [f"When did you last visit {first}? 上次拜访{first}是什么时候？",
              f"How many orders/day on the platform? 平台日单多少？"]
        k = num(keeta_orders(c))
        if k > 0:
            qs.append(f"{first} does {k}/d on Keeta — double it and they sign? Keeta日单{k}，翻一倍签吗？")
        else:
            qs.append(f"What does {first} need to sign? {first}要什么条件才肯签？")
    else:
        qs = [f"When did we first contact {first}? 第一次接触{first}是什么时候？",
              f"Real orders — don't guess. 真实日单，不要猜。",
              f"Is {first} worth fighting for? {first}值得争吗？"]
    return qs[:3]

rows = []
ORDER = {'LOST': 0, 'HIGH': 1, 'MEDIUM': 2, 'RESOLVED': 3, 'PENDING': 4}
STAGE_CN = {'Reportado': '已上报', 'KP aceitou': 'KP已通过', '🔒 Encerrado': '已关闭',
            'Relatório BDM e CM aprovado': 'BDM/CM已批', 'Contrato assinado': '已签约', 'Proposta concluída': '提案完成'}
for c in sorted(cases, key=lambda c: (ORDER[c['cls']], -money(c.get('upfront')))):
    up = money(c.get('upfront'))
    k_o = keeta_orders(c)
    name, rk = RISK[c['cls']]
    et = str(c.get('etapa'))
    cls = c['cls']
    plat = str(c.get('plataforma'))
    upd = str(c.get('updated', ''))[:5]
    co_n = num(c.get('comp_orders'))
    ca = comp_aov(c)
    kp = str(c.get('kp'))
    st = STAGE_CN.get(et.split('（')[0].strip(), et)
    k_str = f"Keeta日单{k_o}" if k_o else 'Keeta零单'
    if cls == 'LOST':
        if 'Recusada' in kp:
            fact_cn = f"我方拒绝跟价（{plat}报价{fmt_money(up)}），案件已关闭；{k_str}。判断：主动放弃的金额战——确认是否为策略性放弃，合同到期日是唯一翻盘窗口。"
        else:
            fact_cn = f"{plat}以{fmt_money(up)}预付锁定，案件已关闭；{k_str}。判断：失守，金额战未跟上；合同到期日是唯一翻盘窗口。"
    elif cls == 'RESOLVED':
        fact_cn = f"KP已通过我方{fmt_money(up)}方案，已胜出未签约；{k_str}。判断：方案赢了，最大风险是拖延变卦——锁定签约日期是唯一要务。"
    elif cls == 'HIGH':
        dep = f"商家{plat}日单{co_n}/d、Keeta {k_o or 0}/d，单量依赖竞对" if co_n else f"竞对日单未核实，Keeta {k_o or 0}/d"
        counter = "BDM/CM已批、我方反制方案已上报KP" if ('aprovado' in et or 'Proposta' in et) else "我方反制方案未定"
        fact_cn = f"{plat}报价{fmt_money(up)}（{upd}更新）；{dep}。判断：大额资金战，{counter}，需CM级介入定价。"
    elif cls == 'MEDIUM':
        amt = f"{plat}已给预付{fmt_money(up)}" if up else f"{plat}已接触"
        ords = f"竞对日单{co_n}/d" if co_n else "竞对日单未知"
        fact_cn = f"{amt}，{ords}；{k_str}；{st}。判断：金额在我方可对抗范围，先核实真实单量和商家态度，再谈钱。"
    else:
        fact_cn = f"仅{st}（{upd}更新）：无预付金额、无竞对日单、KP未录。判断：情报黑洞——BD未深挖或商家拒绝透露；需上门当面核实。"

    # KP attitude derived from etapa/kp field
    if 'aceitou' in et:
        att = "Rejected comp, chose us 拒绝竞对·选我方"
    elif 'Encerrado' in et:
        att = "Case closed 案件已关闭"
    elif 'aprovado' in et or 'Proposta' in et:
        att = "Under negotiation 谈判进行中"
    else:
        att = "Not reported 未报状态"
    if 'Encerrado' in et: sit = f"Lost to {plat or 'comp'} 已失守"
    elif 'aceitou' in et: sit = "Won — sign soon 已胜出待签约"
    elif 'aprovado' in et: sit = "BDM/CM approved, KP next 已批进KP"
    elif 'Proposta' in et: sit = "Proposal done 提案完成"
    elif up or num(c.get('comp_orders')): sit = "Under attack 被进攻中"
    else: sit = "Intel missing 情报缺失"
    qs = questions_for(c)
    rows.append({
        'name': c['nome'].strip(),
        'id': c.get('merchant_id', ''),
        'plat': PLAT.get(c.get('plataforma'), str(c.get('plataforma') or '—')),
        'bd': c.get('bd', ''),
        'bdm': str(c.get('bdm', '')) if str(c.get('bdm')) != 'NULL' else '未分配 Unassigned',
        'risk': name, 'rk': rk,
        'stage': STAGE.get(et, et),
        'kp': kp if kp not in ('—', '') else 'Not filled 未录',
        'upfront': up, 'upfront_s': fmt_money(up),
        'co': comp_orders(c), 'ca': comp_aov(c),
        'kgmv': keeta_aov(c), 'k_o': k_o,
        'sit': sit, 'qs': qs, 'upd': upd,
        'facts': fact_cn,
        'att': att,
    })

data = json.dumps(rows, ensure_ascii=False)
cnt = Counter(r['rk'] for r in rows)
total_up = sum(r['upfront'] for r in rows)
lost_up = sum(r['upfront'] for r in rows if r['rk'] == 'lost')
cons_up = sum(r['upfront'] for r in rows if r['rk'] in ('high', 'medium'))

html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Southern Exclusivity Review 南部独家盘点 (2026-09-24)</title>
<style>
:root { --bg:#f6f7f9; --card:#fff; --line:#e5e7eb; --txt:#1f2937; --mut:#6b7280; --acc:#0f766e; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--txt); padding:16px; }
.wrap { max-width:1400px; margin:0 auto; }
h1 { font-size:20px; margin-bottom:2px; }
.sub { color:var(--mut); font-size:12.5px; margin-bottom:12px; }
.cards { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px 14px; min-width:130px; }
.card .n { font-size:20px; font-weight:700; }
.card .l { font-size:11.5px; color:var(--mut); }
.lost .n{color:#374151} .high .n{color:#dc2626} .medium .n{color:#d97706} .resolved .n{color:#059669} .pending .n{color:#6b7280}
.toolbar { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; align-items:center; }
.search { flex:1; min-width:220px; position:relative; }
.search input { width:100%; padding:9px 12px 9px 34px; border:1px solid var(--line); border-radius:8px; font-size:14px; background:var(--card); }
.search::before { content:"🔍"; position:absolute; left:10px; top:8px; font-size:13px; opacity:.6; }
select { padding:8px 10px; border:1px solid var(--line); border-radius:8px; font-size:13px; background:var(--card); color:var(--txt); max-width:220px; }
.count { font-size:12.5px; color:var(--mut); }
table { width:100%; border-collapse:collapse; background:var(--card); border-radius:10px; overflow:hidden; font-size:12.5px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
thead th { position:sticky; top:0; background:#f3f4f6; padding:9px 8px; text-align:left; font-weight:600; border-bottom:2px solid var(--line); cursor:pointer; user-select:none; white-space:nowrap; z-index:2; }
thead th:hover { background:#ebedf0; }
thead th .arr { font-size:9px; margin-left:3px; color:var(--acc); }
tbody td { padding:8px; border-bottom:1px solid var(--line); vertical-align:top; }
tbody tr:hover { background:#fafafa; }
.rk { display:inline-block; padding:2px 8px; border-radius:99px; font-size:11px; font-weight:600; white-space:nowrap; }
.rk.lost{background:#e5e7eb;color:#374151} .rk.high{background:#fee2e2;color:#b91c1c} .rk.medium{background:#fef3c7;color:#b45309} .rk.resolved{background:#d1fae5;color:#047857} .rk.pending{background:#f3f4f6;color:#6b7280}
.mname { font-weight:600; }
.facts { max-width:340px; line-height:1.5; }
.att { display:inline-block; padding:2px 8px; border-radius:99px; font-size:11px; font-weight:600; white-space:nowrap; }
.att.rejected{background:#d1fae5;color:#047857} .att.signed{background:#e5e7eb;color:#374151} .att.considering{background:#fee2e2;color:#b91c1c} .att.under{background:#dbeafe;color:#1d4ed8} .att.not{background:#f3f4f6;color:#6b7280}
.qs { margin:0; padding-left:14px; }
.qs li { margin-bottom:3px; line-height:1.45; }
.up { font-weight:600; white-space:nowrap; }
.mono { font-family:ui-monospace,monospace; font-size:11.5px; }
.foot { margin-top:10px; color:var(--mut); font-size:11.5px; }
@media (max-width:760px){ body{padding:8px} table{font-size:11.5px} thead th,tbody td{padding:6px 5px} }
</style>
</head>
<body>
<div class="wrap">
<h1>Southern Exclusivity Review 南部独家案件盘点</h1>
<div class="sub">Southern São Paulo Metropolitan (CM: danielalbuquerque) · 24 merchants 商家 · Data updated 数据更新: 2026-09-23 · Click column headers to sort 点击表头排序</div>
<div class="cards">
 <div class="card lost"><div class="n">__LOST__</div><div class="l">Lost 已失守</div></div>
 <div class="card high"><div class="n">__HIGH__</div><div class="l">High Risk 高风险</div></div>
 <div class="card medium"><div class="n">__MED__</div><div class="l">Medium 中风险</div></div>
 <div class="card resolved"><div class="n">__RES__</div><div class="l">Resolved 已解除</div></div>
 <div class="card pending"><div class="n">__PEN__</div><div class="l">Pending 待跟进</div></div>
 <div class="card"><div class="n">R$ __TOTAL__</div><div class="l">Known Upfront 已知预付</div></div>
</div>
<div class="toolbar">
 <div class="search"><input id="q" type="text" placeholder="Search merchant name, ID, BD, BDM... 搜索商家名、ID、BD、BDM..."></div>
 <select id="fRisk"><option value="">Risk 风险: All 全部</option><option value="lost">Lost 已失守</option><option value="high">High 高风险</option><option value="medium">Medium 中风险</option><option value="resolved">Resolved 已解除</option><option value="pending">Pending 待跟进</option></select>
 <select id="fBdm"><option value="">BDM: All 全部</option></select>
 <select id="fPlat"><option value="">Platform 平台: All 全部</option><option>Yellow(99)</option><option>Red(iFood)</option></select>
 <select id="fAtt"><option value="">KP Attitude 态度: All 全部</option><option value="rejected">Rejected comp 拒绝竞对</option><option value="closed">Case closed 案件已关闭</option><option value="under">Under negotiation 谈判中</option><option value="not">Not reported 未报</option></select>
 <span class="count" id="cnt"></span>
</div>
<div style="overflow-x:auto">
<table id="tbl">
<thead><tr>
 <th data-k="idx" data-t="n">#</th>
 <th data-k="rk" data-t="s">Risk 风险</th>
 <th data-k="name" data-t="s">Merchant 商家</th>
 <th data-k="id" data-t="s">ID</th>
 <th data-k="plat" data-t="s">Plataforma</th>
 <th data-k="bd" data-t="s">BD</th>
 <th data-k="bdm" data-t="s">BDM</th>
 <th data-k="facts" data-t="s">Facts 事实说明</th>
 <th data-k="att" data-t="s">KP Attitude on Comp KP对竞对态度</th>
 <th data-k="stage" data-t="s">Stage 阶段</th>
 <th data-k="kp" data-t="s">KP</th>
 <th data-k="upfront" data-t="u">Upfront 预付</th>
 <th data-k="co" data-t="n">Comp Orders 竞对日单</th>
 <th data-k="ca" data-t="n">Comp AOV 竞对客单</th>
 <th data-k="k_o" data-t="n">Keeta Orders Keeta日单</th>
 <th data-k="sit" data-t="s">Status 状态</th>
 <th data-k="qs" data-t="s">Questions 追问</th>
</tr></thead>
<tbody></tbody>
</table>
</div>
<div class="foot">Risk by case stage & KP status 风险按案件阶段与KP状态: Closed/Lost=已失守 · KP Accepted (our counter)=Resolved 已解除 · Reportado with big money/ongoing proposal=High/Medium · Questions personalized 追问按商家定制 · Source: SMB Dashboard Exclusividade Tracking · Southern 23 cases, upfront R$ __LOSTUP__ lost / R$ __CONSUP__ in fight</div>
</div>
<script>
const DATA = __DATA__;
const tbody = document.querySelector('#tbl tbody');
const RISKC = {lost:'Lost 已失守',high:'High 高风险',medium:'Medium 中风险',resolved:'Resolved 已解除',pending:'Pending 待跟进'};
let sortK = 'idx', sortAsc = true;
const bdms = [...new Set(DATA.map(r=>r.bdm))].sort();
const fs = document.getElementById('fBdm');
bdms.forEach(b=>{const o=document.createElement('option');o.textContent=b;fs.appendChild(o);});
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function val(r,k){
  if(k==='idx') return r._i;
  if(k==='qs') return r.qs.join(' ');
  const v = r[k];
  if(k==='upfront') return r.upfront;
  if(k==='co'||k==='ca'||k==='k_o') return parseFloat(v)||0;
  return v;
}
function attKey(r){
  const a = r.att.split(' ')[0].toLowerCase();
  return {'rejected':'rejected','case':'closed','under':'under','not':'not'}[a]||'not';
}
function render(){
  const q = document.getElementById('q').value.trim().toLowerCase();
  const fr = document.getElementById('fRisk').value;
  const fb = document.getElementById('fBdm').value;
  const fp = document.getElementById('fPlat').value;
  const fa = document.getElementById('fAtt').value;
  let rows = DATA.filter(r=>{
    if(fr && r.rk!==fr) return false;
    if(fb && r.bdm!==fb) return false;
    if(fp && r.plat!==fp) return false;
    if(fa && attKey(r)!==fa) return false;
    if(q){
      const hay = (r.name+' '+r.id+' '+r.bd+' '+r.bdm).toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });
  rows.sort((a,b)=>{
    const t = sortK==='idx'||['co','ca','k_o','upfront'].includes(sortK) ? 'n':'s';
    let va=val(a,sortK), vb=val(b,sortK);
    if(t==='n'){ va=+va||0; vb=+vb||0; return sortAsc?va-vb:vb-va; }
    va=String(va); vb=String(vb);
    return sortAsc? va.localeCompare(vb) : vb.localeCompare(va);
  });
  document.getElementById('cnt').textContent = rows.length + ' / ' + DATA.length + ' merchants 商家';
  tbody.innerHTML = rows.map(r=>`<tr>
   <td>${r._i}</td>
   <td><span class="rk ${r.rk}">${RISKC[r.rk]}</span></td>
   <td class="mname">${esc(r.name)}</td>
   <td class="mono">${esc(r.id)}</td>
   <td>${esc(r.plat)}</td>
   <td>${esc(r.bd)}</td>
   <td>${esc(r.bdm)}</td>
   <td class="facts">${esc(r.facts)}</td>
   <td><span class="att ${attKey(r)==='rejected'?'rejected':(attKey(r)==='closed'?'signed':(attKey(r)==='under'?'under':'not'))}">${esc(r.att)}</span></td>
   <td>${esc(r.stage)}</td>
   <td>${esc(r.kp)}</td>
   <td class="up">${r.upfront_s}</td>
   <td>${esc(r.co||'—')}</td>
   <td>${r.ca?('R$'+r.ca):'—'}</td>
   <td>${r.k_o?esc(r.k_o):'0'}</td>
   <td>${esc(r.sit)}</td>
   <td><ul class="qs">${r.qs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></td>
  </tr>`).join('');
}
document.querySelectorAll('thead th').forEach(th=>{
  th.addEventListener('click',()=>{
    const k = th.dataset.k;
    if(sortK===k) sortAsc=!sortAsc; else { sortK=k; sortAsc=true; }
    document.querySelectorAll('thead th .arr').forEach(a=>a.remove());
    const s=document.createElement('span');s.className='arr';s.textContent=sortAsc?'▲':'▼';th.appendChild(s);
    render();
  });
});
['q','fRisk','fBdm','fPlat','fAtt'].forEach(id=>{
  document.getElementById(id).addEventListener('input',render);
  document.getElementById(id).addEventListener('change',render);
});
DATA.forEach((r,i)=>r._i=i+1);
render();
</script>
</body>
</html>"""

html = html.replace('__LOST__', str(cnt['lost'])).replace('__HIGH__', str(cnt['high']))
html = html.replace('__MED__', str(cnt['medium'])).replace('__RES__', str(cnt['resolved']))
html = html.replace('__PEN__', str(cnt['pending']))
html = html.replace('__TOTAL__', f"{total_up/1000000:.2f}M")
html = html.replace('__LOSTUP__', f"{lost_up/1000000:.2f}M")
html = html.replace('__CONSUP__', f"{cons_up/1000000:.2f}M")
html = html.replace('__DATA__', data)
open('/mnt/openclaw/.openclaw/workspace/exclusivity/southern_review.html', 'w').write(html)
print('html written:', len(html), 'chars,', len(rows), 'rows')
print('class counts:', dict(cnt))
print('upfront: total %.2fM lost %.2fM in-fight %.2fM' % (total_up/1e6, lost_up/1e6, cons_up/1e6))
