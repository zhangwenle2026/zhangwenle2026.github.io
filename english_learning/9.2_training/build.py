import json

with open('final_data.json') as f:
    data = json.load(f)
with open('template.html') as f:
    tpl = f.read()

payload = json.dumps(data, ensure_ascii=False)
html = tpl.replace('/*__DATA__*/[]', payload)
with open('training_english.html', 'w') as f:
    f.write(html)
print('size:', len(html))
