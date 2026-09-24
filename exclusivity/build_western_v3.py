#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Western Exclusivity Review v3 — 43 merchants from fresh scrape (19-20/09 update).
Facts column: BD-reported FACTS ONLY (upfront, comp orders, comp AOV, Keeta GMV/d, KP result, stage, updated).
Separate from 竞争情况 (interpretation) and 追问 (questions)."""
import json, re
from collections import Counter

cases = json.load(open('/root/.openclaw/workspace/exclusivity/cases_fresh.json'))
# KP attitude on competitor from case detail (Status do Contrato):
# Assinado = merchant SIGNED with competitor -> LOST
# Recebido = competitor offer received, merchant considering -> risk (HIGH/MEDIUM by money)
# (KP aceitou etapa already = RESOLVED, we won)
ATT = {}
for n, d in json.load(open('/tmp/excl_attitude3.json')).items():
    vals = [p.split(':')[1].strip() for p in d.get('reports', []) if p.startswith('Status do Contrato')]
    ATT[n.strip().strip('|').strip()] = 'Assinado' if 'Assinado' in vals else (vals[0] if vals else 'NONE')

def _money0(v):
    import re as _re
    m = _re.search(r'R\$\s*([\d\.]+)', str(v or ''))
    return float(m.group(1).replace('.', '')) if m else 0.0

for c in cases:
    nm = c['nome'].strip().strip('|').strip()
    c['attitude'] = ATT.get(nm, 'NONE')
    et = c['etapa']; up = _money0(c.get('upfront'))
    import re as _re2
    mco = _re2.search(r'(\d+)', str(c.get('comp_orders') or ''))
    co = int(mco.group(1)) if mco else 0
    if 'aceitou' in et:
        c['cls'] = 'RESOLVED'
    elif c['attitude'] == 'Assinado':
        c['cls'] = 'LOST'
    elif c['attitude'] == 'Recebido':
        if up >= 300000 or co >= 5000 or (up >= 100000 and co >= 300):
            c['cls'] = 'HIGH'
        else:
            c['cls'] = 'MEDIUM'
    else:
        c['cls'] = 'PENDING'

W = cases

def money(v):
    m = re.search(r'R\$\s*([\d\.]+)', str(v or ''))
    try: return float(m.group(1).replace('.', '')) if m else 0
    except: return 0
def num(v):
    m = re.search(r'(\d+)', str(v or ''))
    return int(m.group(1)) if m else 0
def keeta_aov(c):
    m = re.search(r'R\$\s*([\d\.]+)', str(c.get('aov_keeta')))
    return m.group(1) if m else '—'
def keeta_orders(c):
    m = re.search(r'([\d\.]+)/d', str(c.get('aov_keeta')))
    return m.group(1) if m else '—'
def comp_orders(c):
    v = str(c.get('comp_orders') or '')
    m = re.search(r'(\d+)', v)
    return m.group(1) if m else '—'
def comp_aov(c):
    m = re.search(r'R\$\s*([\d\.]+)', str(c.get('comp_aov')))
    return m.group(1) if m else '—'
def upfront(c):
    return money(c.get('upfront'))
def fmt_money(v):
    if not v: return '—'
    if v >= 1000000: return f"R$ {v/1000000:.2f}M".replace('.00', '')
    return f"R$ {int(round(v/1000))}K"

# sort: LOST first? No — HIGH first (meeting priority), then MEDIUM, RESOLVED, PENDING, LOST last? 
# Keep prior order: LOST, HIGH, MEDIUM, RESOLVED, PENDING
ORDER = {'LOST': 0, 'HIGH': 1, 'MEDIUM': 2, 'RESOLVED': 3, 'PENDING': 4}
W = sorted(W, key=lambda c: (ORDER[c['cls']], -upfront(c)))

META = {
    'LOST': ('已失守 Lost', '⚫'),
    'HIGH': ('高风险 High', '🔴'),
    'MEDIUM': ('中风险 Medium', '🟡'),
    'RESOLVED': ('已解除 Resolved', '🟢'),
    'PENDING': ('待跟进 Pending', '⚪'),
}
cnt = Counter(c['cls'] for c in W)
total_up = sum(upfront(c) for c in W)

# ---------- personalized questions ----------
def qstr(en, cn):
    return f"{en}（{cn}）"

def questions_for(c):
    cls = c['cls']; up = upfront(c); co_n = num(c.get('comp_orders')); k_o = keeta_orders(c)
    nm = c['nome'].strip().strip('|').strip()
    first = nm.split()[0].strip(',').strip('!') if nm else ''
    up_s = fmt_money(up) if up else ''
    qs = []
    if cls == 'LOST':
        qs = [
            qstr(f"Why did we lose {first}?", f"为什么丢了{first}？"),
            qstr(f"How long is the {c.get('plataforma')} contract?", f"{c.get('plataforma')}合同签了多久？"),
            qstr(f"What can bring {first} back?", f"什么条件能拉回{first}？"),
        ]
    elif cls == 'RESOLVED':
        qs = [
            qstr(f"When do we sign with {first}?", f"{first}什么时候签约？"),
            qstr(f"What can still go wrong before signing?", f"签约前还有什么变数？"),
        ]
        if up >= 500000:
            qs.append(qstr(f"The {up_s} we pay — one-time or monthly?", f"我们出的{up_s}是一次性还是按月？"))
        else:
            qs.append(qstr(f"What finally convinced {first}?", f"最后是什么打动了{first}？"))
    elif cls == 'HIGH':
        base = [
            qstr(f"The {up_s} from {c.get('plataforma')} — one-time or monthly?", f"{c.get('plataforma')}的{up_s}是一次性还是按月？"),
            qstr(f"Does {first} really do {co_n} orders/day? Did you check the app?", f"{first}真有日单{co_n}？你查过App吗？"),
            qstr(f"What is our counter-offer for {first}?", f"我们对{first}的还价是什么？"),
        ] if co_n else [
            qstr(f"The {up_s} from {c.get('plataforma')} — one-time or monthly?", f"{c.get('plataforma')}的{up_s}是一次性还是按月？"),
            qstr(f"How many orders/day does {first} really have? Ask, don't guess.", f"{first}真实日单多少？要问，不要猜。"),
            qstr(f"What is our counter-offer for {first}?", f"我们对{first}的还价是什么？"),
        ]
        qs = base
    elif cls == 'MEDIUM':
        qs = [
            qstr(f"When did you last visit {first}?", f"你上次拜访{first}是什么时候？"),
            qstr(f"How many orders/day does {first} have on {c.get('plataforma')}?", f"{first}在{c.get('plataforma')}日单多少？"),
        ]
        if num(keeta_orders(c)) > 0:
            k = num(keeta_orders(c))
            qs.append(qstr(f"{first} does {k}/d on Keeta — double it and they sign?", f"{first}在Keeta日单{k}——翻一倍他愿意签吗？"))
        else:
            qs.append(qstr(f"What does {first} need to sign with us?", f"{first}要什么条件才肯签？"))
    else:  # PENDING
        qs = [
            qstr(f"When did we first contact {first}?", f"我们第一次接触{first}是什么时候？"),
            qstr(f"How many orders/day on {c.get('plataforma')}? Don't guess — check.", f"在{c.get('plataforma')}日单多少？不要猜，查一下。"),
            qstr(f"Is {first} worth fighting for?", f"{first}值得争吗？"),
        ]
    return qs[:3]

# ---------- build markdown ----------
L = []
L.append("Western Metropolitan Exclusivity Review 独家案件盘点 (2026-09-21)")
L.append("")
L.append(f"> 数据来源：[SMB Dashboard - Acompanhamento de Exclusividade](https://mirror-success-next.mynocode.host/#/exclusivity-tracking) · 更新至 2026-09-19/20 · Western São Paulo Metropolitan {len(W)} 案")
L.append("")
L.append("## Part 1 — Risk Overview 第一部分：风险总览")
L.append("")
L.append("**风险口径 Risk Basis:** 按商家真实状态 Status do Contrato——**已签约竞对 Signed with comp = 已失守**；**收到报价考虑中 Considering = 高/中风险**（按金额分档）；**KP通过我方反制 Rejected comp offer = 已解除**。*Risk is classified by merchant\'s real status: Signed with competitor = Lost; Considering = High/Medium by amount; our counter accepted = Resolved.*")
L.append("")
lost_up = sum(upfront(c) for c in W if c['cls'] == 'LOST')
cons_up = sum(upfront(c) for c in W if c['cls'] in ('HIGH', 'MEDIUM'))
L.append(f"- **西部 {len(W)} 案**：⚫ 已失守 {cnt['LOST']}（已签约竞对 Signed） · 🔴 高风险 {cnt['HIGH']} + 🟡 中风险 {cnt['MEDIUM']}（考虑中 Considering） · 🟢 已解除 {cnt['RESOLVED']}（拒绝竞对选我方） · ⚪ 待跟进 {cnt['PENDING']}")
L.append(f"- **已失守 {cnt['LOST']} 家已与竞对签约，涉及已知预付 R$ {lost_up/1000000:.2f}M**——商家已签竞对但案件还挂在'已上报'，合同到期日是唯一翻盘窗口，需逐一确认合同期限。")
L.append(f"- **考虑中 {cnt['HIGH']+cnt['MEDIUM']} 家手握竞对报价未签，涉及 R$ {cons_up/1000000:.2f}M**——这是还能争的盘子，其中高风险 {cnt['HIGH']} 家需要CM级反制定价。")
L.append(f"- **🟢 已解除 {cnt['RESOLVED']} 家**（KP通过我方方案）：尽快锁定签约时间，防止变数。")
bdm_cnt = Counter(c['bdm'] for c in W)
bdm_up = {}
for c in W:
    bdm_up[c['bdm']] = bdm_up.get(c['bdm'], 0) + upfront(c)
top = sorted(bdm_cnt.items(), key=lambda x: -bdm_up.get(x[0], 0))[:5]
L.append("- **BDM案件分布**：" + " · ".join(f"{b} {n}案/R${bdm_up.get(b,0)/1000:.0f}K" for b, n in top))
L.append("")
L.append("**会议优先级 Meeting Priority:** 高风险3家定反制方案 → 考虑中逐个确认态度和金额 → 已解除4家锁签约日期 → 已失守25家确认合同期限、建翻盘跟踪。")
L.append("")

# ---------- Part 2 ----------
L.append("## Part 2 — Merchant Review List 第二部分：商家盘点表")
L.append("")
L.append("每家一行；**Facts列为BD报送的原始事实**（预付/竞对日单/竞对AOV/Keeta日单/KP结果/阶段/更新时间），竞争情况为解读，追问为每家定制（≤3个）。*One row per merchant; **Facts = raw facts reported by BD** (upfront, competitor orders/AOV, Keeta daily, KP result, stage, last update); Situation = interpretation; questions personalized (max 3).*")
L.append("")
L.append("| # | 风险 | 商家 Merchant | ID | Plataforma | BD | BDM | Facts 事实说明（BD反馈+判断） | KP对竞对态度 KP Attitude | 竞对预付 | 竞对日单/d | 竞对AOV | Keeta GMV 30d | Keeta单/d | 我的追问 Questions |")
L.append("| " + " | ".join(["---"] * 15) + " |")
STAGE_CN = {'Reportado': '已上报', 'KP aceitou': 'KP已通过', '🔒 Encerrado': '已关闭', 'Relatório BDM e CM aprovado': 'BDM/CM已批', 'Contrato assinado': '已签约', 'Proposta concluída': '提案完成'}
for i, c in enumerate(W):
    cls = c['cls']; name, emoji = META[cls]
    nm = c['nome'].strip().strip('|').strip()
    up = upfront(c); co = comp_orders(c); co_n = num(c.get('comp_orders')); ca = comp_aov(c)
    k_o = keeta_orders(c)
    # Facts: BD-reported facts + case judgment (narrative, CN + short EN)
    plat = str(c.get('plataforma'))
    upd = str(c.get('updated', ''))[:5]
    k_str = f"Keeta日单{k_o}" if k_o != '—' else 'Keeta零单'
    kp = str(c.get('kp'))
    st = STAGE_CN.get(str(c.get('etapa')).split('（')[0].strip(), str(c.get('etapa')))
    if cls == 'LOST':
        fact_cn = f"{plat}以{fmt_money(up)}预付锁定，我方流程已关闭；{k_str}。判断：失守，金额战未跟上；合同到期日是唯一翻盘窗口。"
        fact_en = f"Lost to {plat} at {fmt_money(up)}; contract end date is our only window."
    elif cls == 'RESOLVED':
        fact_cn = f"KP已通过我方{fmt_money(up)}方案（{kp}），已胜出未签约；{k_str}。判断：方案赢了，最大风险是拖延变卦——锁定签约日期是唯一要务。"
        fact_en = f"We won at {fmt_money(up)} (KP approved); lock the signing date now."
    elif cls == 'HIGH':
        dep = f"商家{plat}日单{co_n}/d、Keeta {k_o}/d，单量依赖竞对" if co_n else f"竞对日单未核实，Keeta {k_o}/d"
        counter = "BDM/CM已批、我方反制方案已上报KP" if 'aprovado' in et else "我方反制方案未定"
        fact_cn = f"{plat}报价{fmt_money(up)}（{upd}更新）；{dep}。判断：大额资金战，{counter}，需CM级介入定价。"
        fact_en = f"{plat} offered {fmt_money(up)}; big money fight — CM-level counter needed."
    elif cls == 'MEDIUM':
        amt = f"{plat}已给预付{fmt_money(up)}" if up else f"{plat}已接触"
        ords = f"竞对日单{co_n}/d" if co_n else "竞对日单未知"
        fact_cn = f"{amt}，{ords}；{k_str}；{st}。判断：金额在我方可对抗范围，先核实真实单量和商家态度，再谈钱。"
        fact_en = f"Winnable amount — verify real orders and attitude first."
    else:  # PENDING
        fact_cn = f"仅{st}（{upd}更新）：无预付金额、无竞对日单、KP未录。判断：情报黑洞——BD未深挖或商家拒绝透露；需上门当面核实。"
        fact_en = f"No intel on money or orders — BD must visit and dig."
    fact_cell = fact_cn + f" *{fact_en}*"

    # situation (short interpretation)
    et = str(c.get('etapa'))
    if 'Encerrado' in et: sit = f"已失守；{c.get('plataforma')}锁定"
    elif 'aceitou' in et: sit = "我方KP已通过，待签约"
    elif 'aprovado' in et: sit = f"BDM/CM已批，进入KP提案"
    elif up or co_n: sit = f"{c.get('plataforma')}进攻中"
    else: sit = f"{c.get('plataforma')}已接触，情报缺失"
    if num(k_o) == 0 and 'Encerrado' not in et: sit += "；Keeta零单"
    qs = questions_for(c)
    qcell = " ".join(f"**{chr(0x2460+j)}** {q}" for j, q in enumerate(qs))
    plats = {'Yellow': 'Yellow(99)', 'Red': 'Red(iFood)', 'RedYellow': 'Red+Yellow', 'YellowRed': 'Red+Yellow', '—': '—'}
    pl = plats.get(str(c.get('plataforma')), str(c.get('plataforma')))
    gmv = str(c.get('aov_keeta', ''))
    gm = re.search(r'R\$\s*([\d\.]+)', gmv)
    gm_s = 'R$' + gm.group(1) if gm else '—'
    # KP attitude on competitor (real, from Status do Contrato)
    attitude = c.get('attitude', 'NONE')
    if 'aceitou' in et:
        att = "🟢 拒绝竞对·选我方 Rejected comp, chose us"
    elif attitude == 'Assinado':
        att = "⚫ 已签约竞对 Signed with comp"
    elif attitude == 'Recebido':
        att = "🔴 竞对报价考虑中 Considering offer"
    else:
        att = "⚪ 未报状态 Not reported"
    L.append(f"| {i+1} | {emoji} {name.split('（')[0]} | {nm} | {c.get('merchant_id','—')} | {pl} | {c.get('bd','—')} | {c.get('bdm','—')} | {fact_cell} | {att} | {fmt_money(up)} | {co} | {('R$'+ca) if ca != '—' else '—'} | {gm_s} | {k_o} | {qcell} |")
L.append("")

# ---------- Part 3 ----------
L.append("## Part 3 — Standard Questions (10) 第三部分：标准追问十句式")
L.append("")
L.append("会议通用句式，英文简单实用，可直接照读；谐音辅助发音。*Universal question patterns — short and practical; phonetics to help pronunciation.*")
L.append("")
L.append("| # | 英文 English | 中文 Chinese | 谐音 Phonetic |")
L.append("| --- | --- | --- | --- |")
L.append("| 1 | Can you show me the proof? Screenshot or message? | 能给我证据吗？截图或聊天记录？ | 坎·尤·肖·米·迪·普鲁夫？斯克林肖特·奥·梅西奇？ |")
L.append("| 2 | Is this offer one-time or monthly? | 这个报价是一次性还是按月？ | 伊斯·迪斯·奥弗·万·泰姆·奥·曼斯利？ |")
L.append("| 3 | What is the merchant's attitude now? | 商家现在的态度怎么样？ | 瓦特·伊斯·迪·莫钱特斯·阿提丘德·纳乌？ |")
L.append("| 4 | How many orders per day on Yellow? | Yellow上日均多少单？ | 豪·梅尼·奥德斯·佩·戴·昂·耶洛？ |")
L.append("| 5 | When did Yellow first contact them? | Yellow第一次接触是什么时候？ | 温·迪德·耶洛·弗斯特·康塔克特·泽姆？ |")
L.append("| 6 | What is our counter-offer? | 我们的还价方案是什么？ | 瓦特·伊斯·奥亚·康特-奥弗？ |")
L.append("| 7 | What support do you need from me — budget, campaign, or CM visit? | 你需要我什么支持——预算、活动、还是CM上门？ | 瓦特·萨波特·杜·尤·尼德·弗罗姆·米？ |")
L.append("| 8 | When can we sign the contract? | 我们什么时候能签合同？ | 温·坎·威·萨因·迪·康特拉特？ |")
L.append("| 9 | Why did we lose this merchant? | 这家我们为什么丢了？ | 瓦伊·迪德·威·卢斯·迪斯·莫钱特？ |")
L.append("| 10 | What is your next step, and when? | 你的下一步是什么？什么时候做？ | 瓦特·伊斯·尤尔·奈克斯特·斯特普？ |")
L.append("")
L.append("**用法提示 Usage Tips:** 问完第1句拿到证据后，接着问第3句（态度）判断立场，再用第6/7句（反制+支持）收口；高金额案件必问第2句（一次性 vs 按月）；失守案件用第9句复盘。*After getting proof (Q1), check attitude (Q3), then close with counter-offer and support (Q6/Q7); always ask Q2 for big amounts; use Q9 to review lost cases.*")
L.append("")

open('/root/.openclaw/workspace/exclusivity/western_review.md', 'w').write("\n".join(L))
print('v3 written. rows:', len(W), 'chars:', len("\n".join(L)))
print('class counts:', dict(cnt))
