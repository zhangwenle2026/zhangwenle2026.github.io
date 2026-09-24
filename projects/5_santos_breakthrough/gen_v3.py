import json

plans = json.load(open('/tmp/merchant_plans_v2.json'))

def money(v):
    s = ('%.1f' % v).rstrip('0').rstrip('.')
    return s.replace('.', ',')

for p in plans:
    for c in p['combos']:
        items = c['items']
        anchor = items[0]['name']
        rest_names = [it['name'] for it in items[1:]]
        rest_pt = ' + '.join(rest_names[:2])
        rest_cn = '+'.join(rest_names[:2])
        # PT logic
        c['logicPt'] = (
            f"Ancorado no best-seller {anchor[:30]} ({'líder de busca' if 'Âncora' in items[0]['role'] else 'item principal'}), "
            f"combinado com {rest_pt}. Soma dos itens avulsos ≈ R$ {money(c['items_sum'])}; "
            f"preço do combo R$ {money(c['bundle_price'])}. "
            f"Desconto da loja 40% (R$ {money(c['merchant_cost'])}) + subsídio da plataforma ≈ R$ {money(c['platform_subsidy'])} "
            f"→ preço final R$ {money(c['final'])}."
        )
        # saving display bilingual
        c['savingCn'] = f"立省 R$ {money(round(c['bundle_price'] - c['final'], 0))}"
        # tier label bilingual
        if 'Individual' in c['name_pt'] or c['tier'] == 'R$29,9':
            c['tierPt'] = 'Individual · 单人'
            c['tierCn'] = '单人引流'
        elif 'Família' in c['name_pt'] or float(c['final']) > 60:
            c['tierPt'] = 'Família · 家庭'
            c['tierCn'] = '家庭聚会'
        else:
            c['tierPt'] = 'Casal · 双人'
            c['tierCn'] = '双人主力'

out = []
for p in plans:
    out.append({
        'id': p['shop_id'],
        'name': p['shop_name'],
        'nameCn': '',
        'bdm': p['bdm'],
        'skus': p['total_skus'],
        'popular': p['popular_count'],
        'combos': [{
            'tier': c['tier'],
            'tierPt': c['tierPt'],
            'tierCn': c['tierCn'],
            'name': c['name_pt'],
            'nameCn': c['name_cn'],
            'items': c['items'],
            'bundle': c['bundle_price'],
            'sum': c['items_sum'],
            'final': c['final'],
            'mCost': c['merchant_cost'],
            'pSub': c['platform_subsidy'],
            'saving': c['saving_display'],
            'savingCn': c['savingCn'],
            'logic': c['logic'],
            'logicPt': c['logicPt'],
        } for c in p['combos']],
        'menu': p['menu'],
    })

js = 'export const merchantPlans = ' + json.dumps(out, ensure_ascii=False, indent=1) + ';\n'
open('/tmp/sushi_combo_app/src/merchantData.js', 'w').write(js)
print('written', len(js), 'bytes')
print(out[0]['combos'][0]['logicPt'])
