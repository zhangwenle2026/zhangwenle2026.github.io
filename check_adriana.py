import json
D = json.load(open('order_penetration_data_0830_final.json'))
# adriana: 8-person team. brunacrelien left/absent (0 rows in Excel); remove from roster AND scoring.
# Others keep their scores. Recompute adriananaves summary with 8 BDs (excl. brunacrelien).
scores = {b['bd']: b['total'] for b in D['ws_bds'] + D['santos_bds']}
# remove brunacrelien from ws_bds entirely
D['ws_bds'] = [b for b in D['ws_bds'] if b['bd'] != 'brunacrelien']
old = D['bdm_summary']['adriananaves']
team = scores.get('wanessasilva',0)+scores.get('rodrigoalmeida',0)+scores.get('tiagodangelo',0)+scores.get('marciajesuino',0)+scores.get('josenascimento',0)+scores.get('elisangelasouza',0)+scores.get('ivanfelizardo',0)+scores.get('evaldosilva',0)+scores.get('murilosilva',0)
# 8-person team per user: which 8? Excel shows 9 BDs incl. marcia, brunacrelien gone.
# Original roster had 9 (+marcia=10). brunacrelien 0 rows & 0 score. If she left, the 8/1 rule says
# headcount by 8/1 active. User says 8: keep the 9 Excel BDs = wanessa,rodrigo,tiago,marcia,josenasci,elisa,ivan,evaldo,murilo = 9.
# User explicitly says 8 -> likely excluding murilosilva or ivanfelizardo? Can't guess; use Excel 9-> hmm.
# Safest: 8 = the 9 above minus evaldosilva/murilo who have tiny scores? NO - don't guess ranks.
# Use: brunacrelien out; if still 9, the avg with 8 requires dropping one more. We'll list candidates for user.
print('Excel adriana BDs: 9 (wanessa,rodrigo,tiago,marcia,josenascimento,elisangelasouza,ivanfelizardo,evaldosilva,murilosilva)')
print('User says 8 -> need to know which one is out')
print('With marcia, 9 people:', scores.get('wanessasilva',0), scores.get('rodrigoalmeida',0), scores.get('tiagodangelo',0), scores.get('marciajesuino',0), scores.get('josenascimento',0), scores.get('elisangelasouza',0), scores.get('ivanfelizardo',0), scores.get('evaldosilva',0), scores.get('murilosilva',0))
# prev data: 0827 json check adriana bd_count
P = json.load(open('order_penetration_data_0827_final.json'))
print('0827 adriana bd_count:', P['bdm_summary']['adriananaves'])
