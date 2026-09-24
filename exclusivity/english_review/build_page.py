#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build English review prep page for tomorrow's Metropolitan City Review — Exclusive Cases.
Mobile-friendly, audio player per sentence: play/pause, seekable progress bar,
loop, slow (0.75x), normal, fast (1.25x)."""

AUDIO_BASE = "./audio"

questions = [
    ("q01", "What is the status of this case?", "这个案子现在什么状态？",
     "status 状态；case 案件。开场最常用，让 BDM 先给全貌。"),
    ("q02", "Why did we lose this merchant?", "我们为什么丢了这家商家？",
     "lose → lost 输/丢。复盘必问，逼对方给原因。"),
    ("q03", "How much was the upfront money?", "预付款是多少钱？",
     "upfront money 预付款。独家战核心筹码，必须张口就问。"),
    ("q04", "How many stores are included in this deal?", "这个合同包含几家店？",
     "deal 交易/合同。大额预付常覆盖多店多品牌。"),
    ("q05", "What is the KP's attitude toward us?", "KP 对我们什么态度？",
     "KP = Key Person 商家关键决策人；attitude 态度。"),
    ("q06", "Is he willing to sign, or still considering?", "他愿意签，还是还在考虑？",
     "willing to sign 愿意签；considering 考虑中。二选一逼出明确结论。"),
    ("q07", "What is our counter-offer?", "我们的还价方案是什么？",
     "counter-offer 还价/反提案。你要 resources 时的关键句。"),
    ("q08", "How many orders does he do per day on each platform?", "他在每个平台每天多少单？",
     "orders per day 日单量。判断商家真实价值的第一指标。"),
    ("q09", "When did you last visit this merchant?", "你上次拜访这家商家是什么时候？",
     "last visit 上次拜访。没有拜访就没有情报。"),
    ("q10", "Did he receive a formal contract or just a verbal offer?", "他收到的是正式合同还是口头报价？",
     "formal contract 正式合同；verbal offer 口头报价。区分真假威胁。"),
    ("q11", "When does the contract expire?", "合同什么时候到期？",
     "expire 到期。失守商家唯一的翻盘窗口。"),
    ("q12", "What is the risk level of this case — high, medium, or low?", "这个案子的风险等级：高、中、还是低？",
     "risk level 风险等级。会末收口，要求定性。"),
    ("q13", "When did the merchant receive the offer, and when did he sign it?", "商家什么时候收到的offer？什么时候签的？",
     "receive the offer 收到offer | sign 签约。两个时间点分开问，锁定时间线。"),
    ("q14", "What are the details of the offer?", "offer的具体内容是什么？",
     "details 细节/条款。金额、期限、覆盖范围都要问出来。"),
    ("q15", "How is the merchant performing on the competitor's platform?", "商家在竞对平台的单量表现怎么样？",
     "performing 表现 | on the competitor's platform 在竞对平台。判断竞对offer的真实效果。"),
    ("q16", "What is the merchant's attitude toward the offer?", "商家对这个offer是什么态度？",
     "attitude toward 对……的态度。接受、拒绝还是犹豫，决定下一步动作。"),
    ("q17", "If the KP is still considering, do we need a Keeta counter-offer?", "KP还在考虑中的话，我们需不需要出一个Keeta报价？",
     "still considering 还在考虑 | counter-offer 反报价。逼出明确的资源决策。"),
]

dialogues = [
    ("d01", "开场：逐案过",
     "Let's go through the cases one by one. Can you start with the first one?",
     "咱们一个一个案子过。你从第一个开始吧。",
     "Sure. This merchant is still considering our offer. He hasn't signed yet.",
     "好的。这个商家还在考虑我们的方案，还没签约。",
     "go through...one by one 逐个过 | considering 考虑中 | hasn't signed yet 还没签"),
    ("d02", "追问：金额",
     "What is the upfront money from the competitor?",
     "竞对的预付款是多少？",
     "The competitor offered two hundred K upfront, for three brands.",
     "竞对给了 20 万雷预付，覆盖三个品牌。",
     "two hundred K = R$200K | for three brands 覆盖三个品牌 | offer 报价(动词)"),
    ("d03", "追问：失守原因",
     "Why did we lose this case?",
     "这个案子我们为什么输了？",
     "We lost it because we didn't match the offer. Their money was too high for us to follow.",
     "输了是因为我们没跟价。他们的钱太高，我们跟不起。",
     "match the offer 跟价/对等报价 | too high for us to follow 高到跟不起 | follow 跟进"),
    ("d04", "追问：单量",
     "How many orders does he do per day?",
     "他一天多少单？",
     "Around one hundred and sixty orders per day on Keeta, and about eighty on the competitor.",
     "Keeta 大概日单 160，竞对大概 80。",
     "around / about 大约 | one hundred and sixty 160 | on the competitor 在竞对平台"),
    ("d05", "追问：合同真伪",
     "Did he receive a formal contract or just a verbal offer?",
     "他收到正式合同了还是只有口头报价？",
     "Just a verbal offer — he never received the paper contract.",
     "只是口头报价——他从没收到纸质合同。",
     "paper contract 纸质合同 | never received 从未收到 | just 只是"),
    ("d06", "追问：拜访与意愿",
     "When did you last visit this merchant?",
     "你上次什么时候拜访的这家商家？",
     "I visited him last Friday. He is willing to sign if we come with a higher amount.",
     "上周五拜访的。如果我们给更高的金额，他愿意签。",
     "come with a higher amount 给出更高金额 | willing to sign 愿意签"),
    ("d07", "追问：KP态度",
     "What is the KP's attitude?",
     "KP 什么态度？",
     "He is happy with us, but he heard his friends who signed with the competitor had bad experiences.",
     "他跟我们合作满意，但听说朋友签了竞对之后体验很差。",
     "happy with us 对我们满意 | heard 听说 | bad experiences 糟糕体验"),
    ("d08", "定性：风险",
     "Is this case high risk?",
     "这个案子是高风险吗？",
     "Yes, it's still high risk, because the competitor can come back with more money at any time.",
     "是，还是高风险，因为竞对随时可能加钱回来。",
     "come back with more money 加钱回来 | at any time 随时"),
    ("d09", "追问：合同期限",
     "When does the exclusivity contract expire?",
     "独家合同什么时候到期？",
     "It's a three-year contract, signed about six months ago.",
     "三年合同，大概六个月前签的。",
     "three-year contract 三年合同 | signed...ago ……前签的"),
    ("d10", "追问：我方方案",
     "What is our counter-offer?",
     "我们的还价方案是什么？",
     "We are preparing a package with upfront money plus guaranteed GMV.",
     "我们在准备一个方案：预付款加保底 GMV。",
     "package 方案组合 | plus 加上 | guaranteed GMV 保底交易额"),
    ("d11", "管理动作：补信息",
     "Can you complete the missing information before Wednesday?",
     "周三之前能把缺的信息补齐吗？",
     "Yes, I will fill in all the information in the dashboard by tomorrow morning.",
     "可以，我明早之前把看板里的信息全部补齐。",
     "complete the missing information 补齐缺失信息 | fill in 填写 | by tomorrow morning 明早之前"),
    ("d12", "收口：更新",
     "Do you have any update on this merchant?",
     "这家商家有新进展吗？",
     "Not yet. The BD will visit the store this week and collect more information.",
     "还没有。BD 这周会上门拜访，收集更多信息。",
     "not yet 还没有 | visit the store 上门 | collect information 收集信息"),
]

sentences = [
    ("s01", "We need to complete the information for each case, one by one.",
     "我们需要把每个案子的信息逐个补齐。", "complete 补齐 | one by one 逐个"),
    ("s02", "The merchant is still operating with us normally.",
     "商家目前还在我们平台正常经营。", "operate 经营 | normally 正常地"),
    ("s03", "He dropped seventy percent of his order volume in one week.",
     "他一周内单量掉了 70%。", "drop 下降 | order volume 单量 | in one week 一周内"),
    ("s04", "This is a huge player in our district.",
     "这是我们片区的大商家。", "huge player 大玩家/大商家 | district 片区"),
    ("s05", "The BD never really visited the merchant. He was always communicating through WhatsApp.",
     "BD 从没真正拜访过商家，一直靠 WhatsApp 沟通。", "never really 从未真正 | communicate through 通过……沟通"),
    ("s06", "The agent who signed the contract promised a lot of things and never showed up.",
     "签合同的业务员承诺了很多，但人再没出现过。", "promised 承诺 | never showed up 再没露面"),
    ("s07", "It was a lack of service to the merchant, that's why we lost him.",
     "是服务缺位，所以我们丢了他。", "lack of service 服务缺位 | that's why 这就是为什么"),
    ("s08", "He is willing to sign, but he refused our offer for now.",
     "他愿意签，但目前拒绝了我们这版报价。", "for now 目前 | refused 拒绝了"),
    ("s09", "We should keep the relationship and look for new opportunities in the future.",
     "我们应保持关系，未来找新机会。", "keep the relationship 保持关系 | look for 寻找"),
    ("s10", "The competitor offered guaranteed GMV and a big upfront payment.",
     "竞对给了保底 GMV 加一大笔预付款。", "guaranteed GMV 保底交易额 | upfront payment 预付款"),
]

def audio_tag(src, sid):
    return (
        f'<div class="player" data-src="{AUDIO_BASE}/{src}.mp3">'
        f'<button class="btn play" title="Play/Pause">▶</button>'
        f'<div class="bar"><div class="fill"></div></div>'
        f'<span class="time">0:00</span>'
        f'<button class="btn loop" title="Loop">🔁</button>'
        f'<div class="speeds">'
        f'<button class="btn sp" data-rate="0.75">0.75×</button>'
        f'<button class="btn sp on" data-rate="1">1×</button>'
        f'<button class="btn sp" data-rate="1.25">1.25×</button>'
        f'</div></div>'
    )

q_html = ""
for sid, en, zh, note in questions:
    q_html += f'''<div class="item">
<h3>{en}</h3>
<p class="zh">{zh}</p>
<p class="note">{note}</p>
{audio_tag(sid, sid)}
</div>'''

d_html = ""
for sid, title, a_en, a_zh, b_en, b_zh, vocab in dialogues:
    d_html += f'''<div class="item dialog">
<h3>{sid.upper()} · {title}</h3>
<div class="line a"><div class="who">Q（会议主持/Yoyo问）</div>
<p class="en">{a_en}</p><p class="zh">{a_zh}</p>
{audio_tag(sid+"_a", sid)}</div>
<div class="line b"><div class="who">A（你回答）</div>
<p class="en">{b_en}</p><p class="zh">{b_zh}</p>
{audio_tag(sid+"_b", sid)}</div>
<p class="note">💡 {vocab}</p>
</div>'''

s_html = ""
for sid, en, zh, vocab in sentences:
    s_html += f'''<div class="item">
<h3>{en}</h3>
<p class="zh">{zh}</p>
<p class="note">💡 {vocab}</p>
{audio_tag(sid, sid)}
</div>'''

html = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Meeting English Prep · Exclusive Cases Review 独家案件复盘会英语预习</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--line:#e2e6ea;--txt:#1c2733;--mut:#67748a;--acc:#0e6ba8;--acc2:#0a4d80;}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--txt);padding:12px 10px 40px}
.wrap{max-width:760px;margin:0 auto}
h1{font-size:19px;text-align:center;margin-bottom:4px}
.sub{color:var(--mut);font-size:12px;text-align:center;margin-bottom:14px}
.tabs{display:flex;gap:6px;margin-bottom:12px;position:sticky;top:0;z-index:10;background:var(--bg);padding:6px 0;border-bottom:1px solid var(--line)}
.tab{flex:1;text-align:center;padding:10px 4px;border-radius:10px;background:var(--card);border:1px solid var(--line);font-size:13px;font-weight:600;cursor:pointer}
.tab.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.tab small{display:block;font-weight:400;font-size:10px;opacity:.8}
.pane{display:none}.pane.on{display:block}
.item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:10px}
.item h3{font-size:15.5px;line-height:1.45;margin-bottom:4px}
.zh{color:var(--mut);font-size:13px;margin-bottom:6px}
.note{background:#f0f6fc;border-left:3px solid var(--acc);padding:6px 9px;font-size:12px;color:#3d5568;border-radius:0 6px 6px 0;margin-bottom:8px}
.dialog .line{padding:10px;border-radius:10px;margin-bottom:8px}
.line.a{background:#eef5fb}
.line.b{background:#eefaf1}
.who{font-size:10.5px;font-weight:700;color:var(--mut);margin-bottom:3px;letter-spacing:.4px}
.line .en{font-size:14.5px;font-weight:500;margin-bottom:2px}
.player{display:flex;align-items:center;gap:7px;flex-wrap:wrap;background:#fff;border:1px solid var(--line);border-radius:99px;padding:5px 8px;margin-top:6px}
.btn{border:1px solid var(--line);background:#fff;border-radius:99px;padding:5px 10px;font-size:12px;cursor:pointer;color:var(--txt)}
.btn:active{transform:scale(.96)}
.play{width:34px;height:34px;border-radius:50%;background:var(--acc);color:#fff;border:none;font-size:13px;flex-shrink:0;display:flex;align-items:center;justify-content:center}
.play.playing{background:#c0392b}
.bar{flex:1;min-width:90px;height:8px;background:#dfe5eb;border-radius:99px;cursor:pointer;position:relative;overflow:hidden}
.fill{height:100%;width:0;background:var(--acc);border-radius:99px;pointer-events:none}
.time{font-size:10.5px;color:var(--mut);font-variant-numeric:tabular-nums;white-space:nowrap}
.loop{font-size:13px;padding:4px 8px}
.loop.on{background:#fff3cd;border-color:#d4b106;color:#8a6d00}
.speeds{display:flex;gap:4px}
.sp{padding:4px 7px;font-size:11px}
.sp.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.tip{background:#fffbe6;border:1px solid #f0dd99;border-radius:10px;padding:10px;font-size:12.5px;color:#6b5d1f;margin-bottom:12px;line-height:1.6}
</style>
</head>
<body>
<div class="wrap">
<h1>Meeting English Prep 独家案件复盘会英语预习</h1>
<div class="sub">Metropolitan City Review — Exclusive Cases · 会议英语加油站 · 点▶播放，拖进度条选时间，🔁循环，0.75×慢速跟读</div>

<div class="tabs">
<div class="tab on" data-p="p1">17 Must-Ask<small>提问集锦</small></div>
<div class="tab" data-p="p2">Dialogues<small>会议对话</small></div>
<div class="tab" data-p="p3">Key Lines<small>高频句型</small></div>
</div>

<div class="pane on" id="p1">
<div class="tip">📌 明天会议主持方（Lucas/Yoyo）逐案 review 时的<strong>高频问题句型</strong>。先听熟问题，听懂了才不慌；再把追问打出来变成你的武器。</div>
__QUESTIONS__
</div>

<div class="pane" id="p2">
<div class="tip">📌 按<strong>真实会议流程</strong>编排：Q 是主持方/CM 会问你的，A 是你要答的。每句独立播放，慢速跟读 A 部分，明天开口不卡壳。</div>
__DIALOGUES__
</div>

<div class="pane" id="p3">
<div class="tip">📌 从 09-22 会议纪要中提炼的<strong>高频表达</strong>——复盘失守原因、单量下跌、服务缺位、竞对筹码，直接可以整句用。</div>
__SENTENCES__
</div>
</div>

<script>
document.querySelectorAll('.tab').forEach(t=>{
  t.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on'));
    t.classList.add('on');
    document.getElementById(t.dataset.p).classList.add('on');
    window.scrollTo({top:0});
  });
});

document.querySelectorAll('.player').forEach(p=>{
  const audio = new Audio(p.dataset.src);
  audio.preload = 'none';
  const playBtn = p.querySelector('.play');
  const bar = p.querySelector('.bar');
  const fill = p.querySelector('.fill');
  const timeEl = p.querySelector('.time');
  const loopBtn = p.querySelector('.loop');
  const spBtns = p.querySelectorAll('.sp');
  let seeking = false;

  function fmt(s){ if(!isFinite(s)) return '0:00'; const m=Math.floor(s/60), sec=Math.floor(s%60); return m+':'+String(sec).padStart(2,'0'); }

  playBtn.addEventListener('click',()=>{
    if(audio.paused){
      document.querySelectorAll('audio').forEach(a=>{if(a!==audio){a.pause();}});
      audio.play();
    } else audio.pause();
  });

  audio.addEventListener('play',()=>{playBtn.textContent='⏸';playBtn.classList.add('playing');audio.loop = loopBtn.classList.contains('on');});
  audio.addEventListener('pause',()=>{playBtn.textContent='▶';playBtn.classList.remove('playing');});
  audio.addEventListener('ended',()=>{playBtn.textContent='▶';playBtn.classList.remove('playing');fill.style.width='0%';});
  audio.addEventListener('loadedmetadata',()=>{timeEl.textContent='0:00 / '+fmt(audio.duration);});
  audio.addEventListener('timeupdate',()=>{
    if(!seeking && audio.duration){ fill.style.width=(audio.currentTime/audio.duration*100)+'%'; timeEl.textContent=fmt(audio.currentTime)+' / '+fmt(audio.duration); }
  });

  function pos(e){
    const r = bar.getBoundingClientRect();
    const x = (e.touches?e.touches[0].clientX:e.clientX) - r.left;
    return Math.min(Math.max(x/r.width,0),1);
  }
  function startSeek(e){ seeking=true; move(e); e.preventDefault && e.preventDefault(); }
  function move(e){ const r=pos(e); fill.style.width=(r*100)+'%'; audio.currentTime = r*(audio.duration||0); timeEl.textContent=fmt(r*(audio.duration||0))+' / '+fmt(audio.duration||0); }
  function endSeek(){ seeking=false; }
  bar.addEventListener('mousedown',startSeek);
  window.addEventListener('mousemove',e=>{if(seeking)move(e);});
  window.addEventListener('mouseup',endSeek);
  bar.addEventListener('touchstart',startSeek,{passive:false});
  bar.addEventListener('touchmove',e=>{move(e);e.preventDefault();},{passive:false});
  bar.addEventListener('touchend',endSeek);

  loopBtn.addEventListener('click',()=>{
    loopBtn.classList.toggle('on');
    audio.loop = loopBtn.classList.contains('on');
  });

  spBtns.forEach(b=>{
    b.addEventListener('click',()=>{
      spBtns.forEach(x=>x.classList.remove('on'));
      b.classList.add('on');
      audio.playbackRate = parseFloat(b.dataset.rate);
    });
  });
});
</script>
</body>
</html>"""

html = html.replace('__QUESTIONS__', q_html).replace('__DIALOGUES__', d_html).replace('__SENTENCES__', s_html)
out = "/mnt/openclaw/.openclaw/workspace/exclusivity/english_review/english_review_prep.html"
open(out, 'w').write(html)
print('written', out, len(html), 'chars')
