import json
D = json.load(open('order_penetration_data_0830_final.json'))
for b in D['ws_bds']:
    if b['bd'] == 'marciajesuino':
        b['bdm'] = 'adriananaves'
scores = {b['bd']: b['total'] for b in D['ws_bds'] + D['santos_bds']}
roster = {
 'adriananaves': ['brunacrelien','elisangelasouza','evaldosilva','ivanfelizardo','josenascimento','murilosilva','rodrigoalmeida','tiagodangelo','wanessasilva','marciajesuino'],
 'fernandooliveira': ['brunapadilha','carlosmotta','cristianedasilva','erikboilesen','felipesanches','pedrosaccone','wainnergonzales','wellingtonsantos'],
 'eduardoalbuquerque': ['allanmaalouli','felipesilva','fernandoquintiliano','joycepurificacao','otaviomazzega','thaisvasconcelos'],
 'alisaeed': ['camilabatista','davidcaramaschi','eduardosantos','ricardoaraujo','rodrigocorreia'],
 'tadeumoraes': ['leandroresende','lucasreis','matheuscoelho','paulosantos','paulosilva','ricardoalmeida'],
 'biancaceotto': ['caiolorencato','karinacolomina','luizmoreira','nayannedias','nicolemenezes','nilmaxfranca','rodrigopoli'],
 'cesararraes': ['guilhermesantos','jadycarvalho','johnataguimaraes','kevinberti','renansilva','williamhenrique'],
 'thiagoscavazini': ['barbaraoliveira','claudiareis','felipecruz','heloisamagnani','marialisboa','milenasantana'],
 'igorfeitosa': ['alexlima','igorsouza','marcelofeitosa','tamirislopes','tatianarodrigues'],
 'lucasferreira': ['clebersoares','lucasnada','tatianeribeiro','valeriachacon'],
 'sabrinafernandes': ['brunosalmaso','ericabarbosa','felipebarbosa','giovanabareno'],
 'renataleite': ['jessicarossi','joaocastro','luizmarques','nathaliabernardino'],
}
for bdm, bds in roster.items():
    team = sum(scores.get(bd, 0) for bd in bds)
    avg = team / len(bds)
    old = D['bdm_summary'][bdm]
    D['bdm_summary'][bdm] = {'city': old['city'], 'bd_count': len(bds), 'team_score': team, 'avg': round(avg, 2), 'qualified': avg >= 15}
json.dump(D, open('order_penetration_data_0830_final.json','w'), indent=2, default=str, ensure_ascii=False)
for bdm, v in sorted(D['bdm_summary'].items(), key=lambda x: -x[1]['avg']):
    print(f"{bdm:22} {v['bd_count']}BDs avg={v['avg']:6} {'OK' if v['qualified'] else ''}")
