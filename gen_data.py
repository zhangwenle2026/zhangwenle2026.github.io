import pandas as pd
df = pd.read_excel('bdm_july20.xlsx', header=None)
field_names = df.iloc[1].tolist()
data_rows = df.iloc[2:]

float_fields = {
    'total_coefficient', 'newsign_coefficient', 'july_operation_rate', 'june_operation_rate',
    'op_base_score', 'op_deduction', 'op_bonus', 'op_final_score', 'op_coefficient',
    'ci_result_level', 'dd_result_level', 'dd_sa_weighted_score', 'total_order_achievement_rate',
    'keymerch_order_achievement_rate', 'keymerch_order_coefficient', 'order_coefficient',
    'campaign_intel_coefficient', 'deep_discount_coefficient', 'weight_newsign', 'weight_operation',
    'weight_campaign_intel', 'weight_deep_discount', 'weight_orders', 'weight_management',
    'total_order_target', 'keymerch_order_target', 'ci_score_sum', 'newsign_raw_score'
}

str_fields = {'dt', 'role_level', 'mis_id', 'rm_mis', 'dd_region'}

people = []
for _, row in data_rows.iterrows():
    obj_parts = []
    for i, fn in enumerate(field_names):
        val = row.iloc[i]
        if pd.isna(val):
            continue
        if fn in str_fields:
            obj_parts.append(f'{fn}:"{val}"')
        elif isinstance(val, (int, float)):
            if fn not in float_fields and val == int(val):
                obj_parts.append(f'{fn}:{int(val)}')
            else:
                obj_parts.append(f'{fn}:{val}')
        else:
            obj_parts.append(f'{fn}:"{val}"')

    line = '  { ' + ', '.join(obj_parts) + ' },'
    line = line.replace('role_level:', 'role:').replace('mis_id:', 'name:')
    people.append(line)

print('\n'.join(people))
