import json, re
d=json.load(open('/mnt/openclaw/.openclaw/workspace/bi_all_charts_yesterday.json'))
ml=d['Merchant List']['data']
s=json.dumps(ml.get('filters',{}))
print('dates:', sorted(set(re.findall(r'2026\d{4}', s))))
