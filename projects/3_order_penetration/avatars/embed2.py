import base64

with open('/root/.openclaw/workspace/projects/3_order_penetration/awards_2026.html','r') as f:
    html = f.read()

with open('/root/.openclaw/workspace/projects/3_order_penetration/avatars/luizmarques.jpg','rb') as f:
    b64 = base64.b64encode(f.read()).decode()

html = html.replace('"avatars/luizmarques.jpg"', f'"data:image/jpeg;base64,{b64}"')

with open('/root/.openclaw/workspace/projects/3_order_penetration/awards_2026.html','w') as f:
    f.write(html)

with open('/root/.openclaw/workspace/projects/3_order_penetration/awards_2026.html','r') as f:
    h = f.read()
print('data URIs:', h.count('data:image/jpeg;base64,'))
print('remaining avatar paths:', h.count('avatars/'))
print('file size:', len(h))
