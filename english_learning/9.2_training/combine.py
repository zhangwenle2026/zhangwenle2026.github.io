import json, re

# Combine translated chunks, then split each block into sentences for xieyin wave.
def split_sentences(text):
    # split after . ? ! … followed by space; keep fragments as-is
    parts = re.split(r'(?<=[.?!…])\s+', text.strip())
    return [p for p in parts if p.strip()]

out = []
for c in range(3):
    with open(f'chunk_{c}_out.json') as f:
        out.extend(json.load(f))

out.sort(key=lambda x: x['id'])

items = []
sid = 0
for b in out:
    sents = split_sentences(b['text'])
    for s in sents:
        items.append({'sid': sid, 'block': b['id'], 'sent': s})
        sid += 1

with open('sentences.json', 'w') as f:
    json.dump(items, f, ensure_ascii=False, indent=1)

with open('translated.json', 'w') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print('blocks:', len(out), 'sentences:', len(items))
