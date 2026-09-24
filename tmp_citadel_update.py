import sys, re

# Read current XML from stdin
xml = sys.stdin.read()

# New row for 2026-09-19
new_row = '''<tr nodeId="row-20260919">
<td colwidth="[150]" nodeId="cell-20260919-date">
<p nodeId="p-20260919-date">2026-09-19（BRT 18:00）</p>
</td>
<td colwidth="[400]" nodeId="cell-20260919-task">
<p nodeId="p-20260919-task">每日例行存档：wangwang-hq 打 v5.9.167 tag（归档 daily_bill_2026-09-19.png·HQ自动更新持续运行）/ 有今日记忆文件（2026-09-19·周报BRT 9.14-9.18定版·contentId 2788894160 / 独家跟踪S4竞对板块深化 / BDM Excel KRI全量更新 / BML板块重写）/ DBR日报连续失败（dbr_fetch.py 脚本缺失·111天+）/ DD/BD深折扣日报失败（脚本缺失）/ BP看板正常（MOA自动登录）/ CAPABILITIES.md 无新增 / 学城看板更新</p>
</td>
<td colwidth="[100]" nodeId="cell-20260919-status">
<p nodeId="p-20260919-status">✅ 完成</p>
</td>
<td colwidth="[68]" nodeId="cell-20260919-empty1">
<p nodeId="p-20260919-empty1" />
</td>
<td colwidth="[68]" nodeId="cell-20260919-empty2">
<p nodeId="p-20260919-empty2" />
</td>
<td colwidth="[68]" nodeId="cell-20260919-empty3">
<p nodeId="p-20260919-empty3" />
</td>
</tr>'''

# Insert new row before the final </table></km-doc>
# Find the last </table> before </km-doc>
updated = xml.replace('</table>\n</km-doc>', new_row + '\n</table>\n</km-doc>')

if updated == xml:
    print("ERROR: Could not find insertion point", file=sys.stderr)
    sys.exit(1)

print(updated)
