#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert meeting_log_new2.citadelmd (7-col table rows, soft-break paragraphs) to km-doc XML for updateDocumentByXml."""
import re, uuid

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

lines = open('/tmp/meeting_log_new2.citadelmd').read().split('\n')
xml = ['<km-doc>',
       '<km-title nodeId="6378da35-99b3-4162-84d9-c1573ed3fb9c">📋 Meeting Log · 会议日账本</km-title>',
       '<h2 nodeId="4b2699c7-3be2-46c5-a921-ee716c10f795">📅 会议记录 · Meeting Records</h2>']

# parse table rows
i = 0
n = len(lines)
def parse_paragraph_texts(start):
    """Return (texts list of lines until closing ':::')"""
    texts = []
    j = start
    while j < n and lines[j] != ':::':
        texts.append(lines[j].rstrip())
        j += 1
    return texts, j

# find table start
while i < n and not lines[i].startswith(':::table{'):
    i += 1
assert i < n, 'table not found'
table_nid = re.search(r'nodeId="([^"]+)"', lines[i]).group(1)
xml.append(f'<table responsive="false" nodeId="{table_nid}">')
i += 1
while i < n:
    l = lines[i]
    if l.startswith(':::table_row{'):
        row_nid = re.search(r'nodeId="([^"]+)"', l).group(1)
        i += 1
        cells = []
        while i < n and lines[i].startswith(':::table_') and not lines[i].startswith(':::table_row'):
            header = lines[i].startswith(':::table_header')
            m = re.search(r'nodeId="([^"]+)"', l if False else lines[i])
            cell_nid = m.group(1) if m else str(uuid.uuid4())
            i += 1
            paras = []
            while i < n and lines[i].startswith(':::paragraph'):
                pm = re.search(r'nodeId="([^"]+)"', lines[i])
                p_nid = pm.group(1) if pm else str(uuid.uuid4())
                texts, i = parse_paragraph_texts(i + 1)
                # soft-break paragraphs: lines ending with two spaces were breaks; we already rstripped.
                # Use <br/> between consecutive text lines in same paragraph
                paras.append((p_nid, texts))
                i += 1  # skip ':::'
            cells.append((header, cell_nid, paras))
            # skip cell close ':::'
            if i < n and lines[i] == ':::':
                i += 1
        xml.append(f'<tr nodeId="{row_nid}">')
        for header, cell_nid, paras in cells:
            tag = 'th' if header else 'td'
            xml.append(f'<{tag} nodeId="{cell_nid}">')
            for p_nid, texts in paras:
                body = '<br/>'.join(esc(t) for t in texts if t.strip() or len(texts) == 1)
                # keep empty as empty
                if not any(t.strip() for t in texts):
                    body = ''
                xml.append(f'<p nodeId="{p_nid}">{body}</p>')
            xml.append(f'</{tag}>')
        xml.append('</tr>')
    elif l.strip() == ':::':
        i += 1
    elif l.startswith(':::'):
        i += 1
    else:
        i += 1
xml.append('</table>')
xml.append('</km-doc>')
open('/tmp/meeting_log_restore.xml', 'w').write('\n'.join(xml))
print('rows:', xml.count('<tr '))
