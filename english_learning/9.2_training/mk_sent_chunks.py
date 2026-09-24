import json

with open('final_data.json') as f:
    data = json.load(f)

# Build per-chunk input: blocks with sentences + block-level cn
k = 3
size = (len(data) + k - 1) // k
for c in range(k):
    chunk = []
    for b in data[c*size:(c+1)*size]:
        chunk.append({'id': b['id'], 'ts': b.get('ts',''), 'sentences': b['sentences'], 'block_cn': b.get('cn','')})
    with open(f'sent_chunk_{c}.json', 'w') as f:
        json.dump(chunk, f, ensure_ascii=False, indent=1)
print('chunks written, sizes:', [ (len(data[c*size:(c+1)*size])) for c in range(k) ])
