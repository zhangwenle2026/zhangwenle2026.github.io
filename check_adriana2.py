import json
D = json.load(open('order_penetration_data_0830_final.json'))
scores = {b['bd']: b['total'] for b in D['ws_bds'] + D['santos_bds']}
# 0827 roster for adriana = 8: wanessasilva, rodrigoalmeida, tiagodangelo, josenascimento, elisangelasouza, ivanfelizardo, evaldosilva, murilosilva
# marciajesuino moved in (user ruling), so now 9 names. User says team is 8.
# Check who has 0 score / absent: brunacrelien (0) is not in adriana's excel rows at all -> she left.
# So "8人团队" = the 8 from 0827 (marcia counted within those? no, marcia was alisaeed's in 0827).
# Interpretation: adriana team = 8 BDs incl. marcia, excl. one of the 0827 members.
# murilosilva: 2 excel rows, score 3; evaldosilva 1 row score 3. Can't guess.
# Print candidates and compute both options for user confirmation preview.
members_0827 = ['wanessasilva','rodrigoalmeida','tiagodangelo','josenascimento','elisangelasouza','ivanfelizardo','evaldosilva','murilosilva']
for out in ['evaldosilva','murilosilva','ivanfelizardo']:
    team = [m for m in members_0827 if m != out] + ['marciajesuino']
    ts = sum(scores.get(m, 0) for m in team)
    print(f'若{out}不在团队: 8人={team} total={ts} avg={ts/8:.2f}')
team_all9 = members_0827 + ['marciajesuino']
ts = sum(scores.get(m, 0) for m in team_all9)
print(f'全部9人: total={ts} avg={ts/9:.2f}')
