import sys, json

# Sample every Nth block to build a subagent task
with open('blocks.txt') as f:
    blocks = [l.rstrip('\n') for l in f if l.strip()]

n = len(blocks)
out = []
for idx, b in enumerate(blocks):
    ts, _, text = b.partition('\t')
    out.append({'id': idx, 'ts': ts, 'text': text})

# split into 3 chunks for parallel subagents
k = 3
size = (n + k - 1) // k
for c in range(k):
    chunk = out[c*size:(c+1)*size]
    if not chunk:
        continue
    with open(f'chunk_{c}.json', 'w') as f:
        json.dump(chunk, f, ensure_ascii=False, indent=1)
print(n, 'total blocks;', k, 'chunks')
for c in range(k):
    try:
        with open(f'chunk_{c}.json') as f:
            print(c, len(json.load(f)))
    except FileNotFoundError:
        pass
