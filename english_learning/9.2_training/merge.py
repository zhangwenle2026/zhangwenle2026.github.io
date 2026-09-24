import re

with open('clean.txt') as f:
    lines = [l.strip() for l in f if l.strip()]

texts = []
i = 0
while i < len(lines):
    if re.match(r'^\d{2}:\d{2}:\d{2}$', lines[i]):
        if i + 1 < len(lines):
            texts.append(lines[i+1])
            i += 2
        else:
            i += 1
    else:
        texts.append(lines[i])
        i += 1

# First: keep the timestamp of the first text line in each block
stamped = []  # (ts, text)
i = 0
last_ts = None
while i < len(lines):
    if re.match(r'^\d{2}:\d{2}:\d{2}$', lines[i]):
        last_ts = lines[i]
        i += 1
    else:
        stamped.append((last_ts, lines[i]))
        i += 1

def is_garbage(t):
    # near-empty or non-English filler
    letters = re.sub(r'[^A-Za-z]', '', t)
    return len(letters) < 2

merged = []
cur = ""
cur_ts = None
for ts, t in stamped:
    if is_garbage(t):
        continue
    if not cur:
        cur = t
        cur_ts = ts
    else:
        cur = cur + " " + t
    # end block at sentence-ending punctuation when reasonably sized
    if len(cur) >= 60 and re.search(r'[.?!…]["\')]*\s*$', cur):
        merged.append((cur_ts, cur.strip()))
        cur = ""
if cur:
    merged.append((cur_ts, cur.strip()))

with open('blocks.txt', 'w') as f:
    for ts, b in merged:
        f.write((ts or "") + "\t" + b + "\n")
print(len(stamped), "raw;", len(merged), "blocks")
