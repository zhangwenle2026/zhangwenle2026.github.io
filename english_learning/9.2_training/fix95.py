import json

with open('final_data.json') as f:
    data = json.load(f)
with open('sent_chunk_2_out.json') as f:
    ch = json.load(f)

fix = {item['id']: item['cn'] for item in ch}
for b in data:
    if b['id'] in fix:
        n = len(b['sentences'])
        cn = fix[b['id']]
        if len(cn) != n:
            # pad or trim to align
            if len(cn) < n:
                cn = cn + [''] * (n - len(cn))
            else:
                cn = cn[:n]
        b['cnSentence'] = cn

aligned = sum(1 for b in data if len(b.get('cnSentence',[]))==len(b['sentences']))
print('aligned:', aligned, '/', len(data))
with open('final_data.json','w') as f:
    json.dump(data, f, ensure_ascii=False)
