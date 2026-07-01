import re, json

html = open('index.html', encoding='utf-8').read()
payload = re.search(r'<script id="matchesData" type="application/json">(.*?)</script>', html, re.S).group(1)
d = json.loads(payload)
for m in d:
    if m['home'] == 'Brazil' and m['away'] == 'Japan' and m.get('analysis'):
        print(list(m['analysis'].get('events', {}).keys()))
