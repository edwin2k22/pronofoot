import json, re

with open('index.html', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'<script id="embedded-data" type="application/json">(.*?)</script>', html, re.DOTALL)
if m:
    data = json.loads(m.group(1))
    usa = [x for x in data if x['home']=='USA']
    if usa:
        print('Has prediction:', 'prediction' in usa[-1])
        if 'prediction' in usa[-1]:
            print('Keys:', usa[-1]['prediction'].keys())
