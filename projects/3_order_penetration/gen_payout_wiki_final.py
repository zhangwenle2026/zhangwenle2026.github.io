#!/usr/bin/env python3
# 生成规范的 CitadelXML (km-doc根节点, km-title第一子节点, 无thead/tbody)

rows_bd_ws = [
    (1, "Wanessa Silva", "Southern", "Adriana Naves", "60", "🥇 Gold Champion 金牌冠军", "R$ 2,000"),
    (2, "Cristiane da Silva", "Southern", "Fernando Oliveira", "44", "🥈 Silver Elite 银牌精英", "R$ 1,500"),
    (3, "Luiz Moreira", "Western", "Bianca Ceotto", "40", "🥈 Silver Elite 银牌精英", "R$ 1,500"),
    (4, "Tamiris Lopes", "Western", "Igor Feitosa", "35", "🥉 Bronze Star 铜牌之星", "R$ 1,000"),
    (5, "Igor Souza", "Western", "Igor Feitosa", "30", "🥉 Bronze Star 铜牌之星", "R$ 1,000"),
    (6, "Pedro Saccone", "Southern", "Fernando Oliveira", "29", "🥉 Bronze Star 铜牌之星", "R$ 1,000"),
    (7, "Rodrigo Poli", "Western", "Bianca Ceotto", "26", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (8, "Guilherme Santos", "Western", "Cesar Arraes", "25", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (9, "Rodrigo Correia", "Southern", "Ali Saeed", "24", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (10, "Bruna Padilha", "Southern", "Fernando Oliveira", "23", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (11, "Ricardo Almeida", "Southern", "Tadeu Moraes", "21", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (11, "Marcelo Feitosa", "Western", "Igor Feitosa", "21", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (13, "Rodrigo Almeida", "Southern", "Adriana Naves", "18", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (14, "Jady Carvalho", "Western", "Cesar Arraes", "16", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (14, "Felipe Cruz", "Western", "Thiago Scavazini", "16", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (14, "Karina Colomina", "Western", "Bianca Ceotto", "16", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
    (14, "Tiago Dangelo", "Southern", "Adriana Naves", "16", "🏅 Outstanding Performer 优秀表现奖", "R$ 500"),
]
rows_bd_santos = [
    ("1", "Jessica Rossi", "Renata Leite", "17", "🥇 Gold Champion 金牌冠军（并列第一 Co-Champion）", "R$ 2,000"),
    ("1", "Luiz Marques", "Renata Leite", "17", "🥇 Gold Champion 金牌冠军（并列第一 Co-Champion）", "R$ 2,000"),
    ("3", "Erica Barbosa", "Sabrina Fernandes", "16", "🥉 Bronze Star 铜牌之星", "R$ 1,000"),
]
rows_bdm = [
    ("1", "Igor Feitosa", "Western", "5", "99", "19.8", "🥇 Best Team Leader 最佳团队领袖", "R$ 2,500"),
    ("2", "Adriana Naves", "Southern", "8", "139", "17.38", "🥈 Outstanding Team Leader 优秀团队领袖", "R$ 2,000"),
]

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def table(headers, rows, bold_last_row=False):
    trs = ['<tr>' + ''.join(f"<th><p>{esc(h)}</p></th>" for h in headers) + "</tr>"]
    for i, r in enumerate(rows):
        is_bold = bold_last_row and i == len(rows) - 1
        tds = "".join(f"<td><p><b>{esc(v)}</b></p></td>" if is_bold else f"<td><p>{esc(v)}</p></td>" for v in r)
        trs.append(f"<tr>{tds}</tr>")
    return "<table>" + "".join(trs) + "</table>"

t_summary = table(
    ["Category 类别", "Winners 获奖人数", "Actual Payout 实际发放", "Budget 预算", "Budget Use 使用率"],
    [
        ("BD — Western & Southern（17人）", "17", "R$ 13,500", "R$ 12,500", "108%"),
        ("BD — Santos（3人，双金牌）", "3", "R$ 5,000", "R$ 4,500", "111%"),
        ("BD Subtotal BD小计", "20", "R$ 18,500", "R$ 17,000", "109%"),
        ("BDM（2人）", "2", "R$ 4,500", "R$ 6,000", "75%"),
        ("GRAND TOTAL 总计", "22", "R$ 23,000", "R$ 23,000", "100%"),
    ],
    bold_last_row=True,
)

t_structure = table(
    ["赛道 Track", "Ranking", "Award 奖项", "Prize 奖金", "Winners 人数", "Subtotal 小计"],
    [
        ("WS BD", "Top 1", "Gold Champion 金牌冠军", "R$ 2,000", "1", "R$ 2,000"),
        ("WS BD", "Top 2-3", "Silver Elite 银牌精英", "R$ 1,500", "2", "R$ 3,000"),
        ("WS BD", "Top 4-6", "Bronze Star 铜牌之星", "R$ 1,000", "3", "R$ 3,000"),
        ("WS BD", "Top 7-15", "Outstanding Performer 优秀表现奖", "R$ 500", "11", "R$ 5,500"),
        ("Santos BD", "Top 1（并列双金 Co-Champions）", "Gold Champion 金牌冠军", "R$ 2,000", "2", "R$ 4,000"),
        ("Santos BD", "Top 3", "Bronze Star 铜牌之星", "R$ 1,000", "1", "R$ 1,000"),
        ("BDM", "Top 1", "Best Team Leader 最佳团队领袖", "R$ 2,500", "1", "R$ 2,500"),
        ("BDM", "Top 2", "Outstanding Team Leader 优秀团队领袖", "R$ 2,000", "1", "R$ 2,000"),
        ("TOTAL 合计", "—", "—", "—", "22", "R$ 23,000"),
    ],
    bold_last_row=True,
)

t_bd_ws = table(["Rank", "BD", "City", "BDM", "Score 得分", "Award 奖项", "Prize 奖金"], rows_bd_ws)
t_bd_santos = table(["Rank", "BD", "BDM", "Score 得分", "Award 奖项", "Prize 奖金"], rows_bd_santos)
t_bdm = table(["Rank", "BDM", "City", "BDs 达标人数", "Team Score 团队总分", "Avg 人均分", "Award 奖项", "Prize 奖金"], rows_bdm)

parts = []
parts.append('<km-title nodeId="e78809a2-cf0f-4e2c-b549-0c85724ccaa6">SP Metro Incentive Race Award Payout Summary 圣保罗都市圈激励赛奖金发放明细</km-title>')

parts.append("<h1>SP Metro Order Penetration Incentive Race — Award Payout Summary 圣保罗都市圈订单渗透激励赛奖金发放明细</h1>")
parts.append("<p>Campaign Period 激励赛周期: Jul 27 – Aug 31, 2026 ｜ Data Cutoff 数据截止: Aug 31, 2026 (BRT) ｜ Payout Request 发放申请: Sep 15, 2026</p>")

parts.append("<h2>1. Payout Summary 发放总览</h2>")
parts.append(t_summary)
parts.append("<p>说明 Notes:</p>")
parts.append("<p>① 原定预算 Original budget: R$ 23,000（WS BD R$ 12,500 + Santos BD R$ 4,500 + BDM R$ 6,000），实际发放 Actual payout: R$ 23,000，总预算刚好用满（100%）。</p>")
parts.append("<p>② WS赛区 Top 7-15 档（R$ 500）因多组并列分数，实际获奖 11 人（原定 9 个名额），该赛区发放 R$ 13,500，超出分区预算 R$ 1,000。</p>")
parts.append("<p>③ Santos赛区 Jessica Rossi 与 Luiz Marques 同为 17 分并列第一（Tiebreaker 未能分离），经裁定两人均授予金牌冠军 R$ 2,000（双金牌 Co-Champions），Erica Barbosa 16 分为铜牌之星 R$ 1,000。该赛区实际发放 R$ 5,000，超出原分区预算 R$ 500。</p>")
parts.append("<p>④ BDM赛道仅 2 人达标（人均 ≥15 分）：Igor Feitosa（人均 19.8）与 Adriana Naves（人均 17.38），Top 3 奖金档位未用满，实际发放 R$ 4,500 / 预算 R$ 6,000，冗余 R$ 1,500 吸收了 BD 赛道的并列溢出。</p>")
parts.append("<p>⑤ BD 达标线为 ≥15 分。全区域 71 名 BD 中 20 人达标（28.2%）。所有并列排名均按「并列同奖」原则处理。</p>")

parts.append("<h2>2. Award Structure &amp; Payout 奖项结构与发放</h2>")
parts.append(t_structure)

parts.append("<h2>3. BD Payout Detail — Western &amp; Southern (17 winners) BD发放明细</h2>")
parts.append(t_bd_ws)
parts.append("<p>小计 Subtotal: R$ 13,500（金牌 R$ 2,000 + 银牌 2×R$ 1,500 + 铜牌 3×R$ 1,000 + 优秀表现奖 11×R$ 500）</p>")

parts.append("<h2>4. BD Payout Detail — Santos (3 winners) BD发放明细 — 桑托斯</h2>")
parts.append(t_bd_santos)
parts.append("<p>小计 Subtotal: R$ 5,000（并列双金 2×R$ 2,000 + 铜牌 R$ 1,000）</p>")

parts.append("<h2>5. BDM Payout Detail (2 winners) BDM发放明细</h2>")
parts.append(t_bdm)
parts.append("<p>小计 Subtotal: R$ 4,500（最佳团队领袖 R$ 2,500 + 优秀团队领袖 R$ 2,000）</p>")

parts.append("<h2>6. Related Links 相关链接</h2>")
parts.append("<ul>")
parts.append("<li>Final Announcement 最终颁奖公告: https://html-hosting-hub.mynocode.host/#/preview/fb7b5e25-0560-4e12-8e65-6d713352c5dc</li>")
parts.append("<li>Incentive Scheme 激励方案: https://km.sankuai.com/collabpage/2776855669</li>")
parts.append("<li>Final Rankings 最终排名Wiki: https://km.sankuai.com/collabpage/2781368014</li>")
parts.append("<li>Incentive Data Dashboard 数据看板: https://html-hosting-hub.mynocode.host/#/preview/c998d382-7874-4273-8867-1cfe183eed41</li>")
parts.append("<li>Document Owner 文档负责人: SP Metro BD Team / 张文乐 (zhangwenle)</li>")
parts.append("</ul>")

xml = "<km-doc>\n" + "\n".join(parts) + "\n</km-doc>\n"
with open("/tmp/payout_wiki_v2.xml", "w", encoding="utf-8") as f:
    f.write(xml)
print("Written:", len(xml), "chars")
