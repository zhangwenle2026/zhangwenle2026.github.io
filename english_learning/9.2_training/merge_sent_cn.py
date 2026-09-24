import json

with open('final_data.json') as f:
    data = json.load(f)

# merge sentence-level cn
sent_cn = {}
for c in range(3):
    with open(f'sent_chunk_{c}_out.json') as f:
        for item in json.load(f):
            sent_cn[item['id']] = item['cn']

updated = 0
for b in data:
    if b['id'] in sent_cn and len(sent_cn[b['id']]) == len(b['sentences']):
        b['cnSentence'] = sent_cn[b['id']]
        updated += 1
    # else keep existing fallback (single-sentence blocks already have cnSentence)

print('updated blocks:', updated, '/', len(data))

with open('final_data.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False)
