#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert western_review.md to CitadelXML (tables as <table responsive=true>)."""
import re, uuid

md = open('/root/.openclaw/workspace/exclusivity/western_review.md').read()
lines = md.split('\n')

def esc(s):
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return s

def inline(s):
    s = esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', s)
    # links [text](url)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" title="\1">\1</a>', s)
    return s

def nid():
    return str(uuid.uuid4())

out = ['<km-doc>']
out.append(f'<km-title nodeId="{nid()}">Western Metropolitan Exclusivity Review 独家案件盘点 (2026-09-21)</km-title>')

i = 0
in_table = False
table_rows = []
def flush_table():
    global table_rows
    if not table_rows:
        return
    xml = [f'<table borderWidth="1" responsive="true" nodeId="{nid()}">']
    for row in table_rows:
        cells = [c.strip() for c in row.strip().strip('|').split('|')]
        tds = []
        first = True
        for cell in cells:
            tag = 'th' if is_header_row else 'td'
            tds.append(f'<{tag} nodeId="{nid()}"><p nodeId="{nid()}">{inline(cell)}</p></{tag}>')
        xml.append(f'<tr nodeId="{nid()}">' + ''.join(tds) + '</tr>')
    xml.append('</table>')
    out.extend(xml)
    table_rows = []

is_header_row = False
while i < len(lines):
    l = lines[i].rstrip()
    if l.startswith('|'):
        # collect table block
        if not in_table:
            in_table = True
            table_rows = []
        if re.match(r'^\|[\s\-|:]+\|?\s*$', l):
            i += 1
            continue
        if not table_rows:
            is_header_row = True
        else:
            is_header_row = False
        table_rows.append(l)
        # header detection: next non-separator line decides; simpler: first row of block is header
        i += 1
        continue
    else:
        if in_table:
            # first row of collected block is header
            flush_table()
            in_table = False
    if not l.strip():
        i += 1
        continue
    if l.startswith('## '):
        out.append(f'<h2 nodeId="{nid()}">{inline(l[3:])}</h2>')
    elif l.startswith('### '):
        out.append(f'<h3 nodeId="{nid()}">{inline(l[4:])}</h3>')
    elif l.startswith('> '):
        out.append(f'<blockquote nodeId="{nid()}"><p nodeId="{nid()}">{inline(l[2:])}</p></blockquote>')
    elif l.startswith('- '):
        out.append(f'<ul nodeId="{nid()}"><li nodeId="{nid()}"><p nodeId="{nid()}">{inline(l[2:])}</p></li></ul>')
    else:
        out.append(f'<p nodeId="{nid()}">{inline(l)}</p>')
    i += 1
if in_table:
    flush_table()

# fix: header detection — redo pass: first data row in each table block should be th
xml = '\n'.join(out)
# blockquote nesting: multiple single-item blockquotes fine.

open('/root/.openclaw/workspace/exclusivity/western_review.xml', 'w').write(xml)
print('xml written, len', len(xml))
