#!/usr/bin/env python3
# 修复KRI表格内嵌图片：md表格cell里的 ![...]() 在xml转换中被inline()破坏。
# 方案：先生成xml，再把 <p>…&lt;img … 的情况处理。
# 更简单：在md_to_xml2基础上，表格cell单独渲染，允许cell里出现<img>。
import re, uuid, html

SRC = '/mnt/openclaw/.openclaw/workspace/projects/1_weekly_report/data/20260913/report_0907_0913.md'
OUT = '/tmp/report_final.xml'

def nid():
    return str(uuid.uuid4())

def inline(t):
    t = t.strip()
    # extract images first
    imgs = []
    def stash(m):
        imgs.append(m.group(0))
        return f'\x00IMG{len(imgs)-1}\x00'
    t = re.sub(r'!\[[^\]]*\]\(https?://[^)]+\)', stash, t)
    t = html.escape(t, quote=False)
    t = t.replace('\x00', '\x01')  # html.escape doesn't touch control chars but be safe
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: '<a href="%s" nodeId="%s">%s</a>' % (m.group(2), nid(), m.group(1)), t)
    t = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', t)
    t = t.replace('R$', 'R＄')
    # restore images
    def unstash(m):
        raw = imgs[int(m.group(1))]
        mm = re.match(r'!\[([^\]]*)\]\((https?://[^)]+)\)', raw)
        return f'<img src="{mm.group(2)}" name="{mm.group(1) or "chart"}" width="360" nodeId="{nid()}" />'
    t = re.sub(r'\x01IMG(\d+)\x01', unstash, t)
    return t

def para(t):
    return f'<p nodeId="{nid()}">{inline(t)}</p>'

lines = open(SRC).read().split('\n')

blocks = []
i = 0
while i < len(lines):
    s = lines[i].strip()
    if s.startswith('|') and i+1 < len(lines) and re.match(r'^\|[\s:|-]+\|?\s*$', lines[i+1].strip()):
        rows = []
        while i < len(lines) and lines[i].strip().startswith('|'):
            cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
            rows.append(cells)
            i += 1
        rows = rows[:1] + rows[2:]
        blocks.append(('table', rows))
        continue
    if not s:
        blocks.append(('blank', None))
        i += 1
        continue
    blocks.append(('line', s))
    i += 1

out = ['<km-doc>', '<km-title nodeId="%s">SP Metropolitan Weekly Review 圣保罗都市圈周报 (BRT 9.7-9.13)</km-title>' % nid()]
list_open = False
def close_list():
    global list_open
    if list_open:
        out.append('</ul>')
        list_open = False

bi = 0
while bi < len(blocks):
    typ, content = blocks[bi]
    if typ == 'blank':
        close_list(); bi += 1; continue
    if typ == 'table':
        close_list()
        rows = content
        out.append(f'<table borderWidth="1" responsive="true" nodeId="{nid()}">')
        for r_i, r in enumerate(rows):
            out.append(f'  <tr nodeId="{nid()}">')
            tag = 'th' if r_i == 0 else 'td'
            for c in r:
                inner = para(c) if c.strip() else '<p />'
                out.append(f'    <{tag} nodeId="{nid()}">{inner}</{tag}>')
            out.append('  </tr>')
        out.append('</table>')
        bi += 1
        continue
    s = content
    m = re.match(r'^(#{1,6})\s+(.*)', s)
    if m:
        close_list()
        lvl = min(4, max(2, len(m.group(1))))
        out.append(f'<h{lvl} nodeId="{nid()}">{inline(m.group(2))}</h{lvl}>')
        bi += 1; continue
    if s.startswith('> '):
        close_list()
        buf = []
        while bi < len(blocks) and blocks[bi][0] == 'line' and blocks[bi][1].startswith('>'):
            buf.append(blocks[bi][1].lstrip('>').strip())
            bi += 1
        out.append(f'<blockquote nodeId="{nid()}"><p>{inline(" ".join(buf))}</p></blockquote>')
        continue
    if s.startswith('- '):
        if not list_open:
            out.append(f'<ul nodeId="{nid()}">')
            list_open = True
        item = s[2:]
        while bi+1 < len(blocks) and blocks[bi+1][0] == 'line' and blocks[bi+1][1].startswith('  ') and not blocks[bi+1][1].strip().startswith('-'):
            bi += 1
            item += ' ' + blocks[bi][1].strip()
        out.append(f'<li nodeId="{nid()}">{inline(item)}</li>')
        bi += 1; continue
    if re.match(r'^\d+\.\s', s):
        close_list()
        out.append(f'<ol nodeId="{nid()}">')
        while bi < len(blocks) and blocks[bi][0] == 'line' and re.match(r'^\d+\.\s', blocks[bi][1]):
            out.append(f'<li nodeId="{nid()}">{inline(re.sub(r"^\d+\.\s", "", blocks[bi][1]))}</li>')
            bi += 1
        out.append('</ol>')
        continue
    m = re.match(r'^!\[([^\]]*)\]\((https?://[^)]+)\)', s)
    if m:
        close_list()
        out.append(f'<p nodeId="{nid()}"><img src="{m.group(2)}" name="{m.group(1) or "chart"}" width="600" nodeId="{nid()}" /></p>')
        rest = s[m.end():].strip()
        if rest:
            out.append(para(rest))
        bi += 1; continue
    buf = [s]
    bi += 1
    while bi < len(blocks):
        t2, c2 = blocks[bi]
        if t2 != 'line': break
        if (not c2 or c2.startswith('#') or c2.startswith('>') or c2.startswith('- ')
            or c2.startswith('!') or re.match(r'^\d+\.\s', c2)):
            break
        buf.append(c2)
        bi += 1
    close_list()
    out.append(para(' '.join(buf)))

close_list()
out.append('</km-doc>')
xml = '\n'.join(out)
open(OUT, 'w').write(xml)
print('OK', len(xml), 'chars | tables:', xml.count('<table'), '| imgs:', xml.count('<img'), '| h2:', xml.count('<h2'), '| h3:', xml.count('<h3'))
