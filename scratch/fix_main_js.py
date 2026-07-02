import os

js_path = 'assets/main.js'
with open(js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix live_feed.json
content = content.replace(
    'fetch("collector/data/livefeed.json?_=" + Date.now())',
    'fetch("collector/data/live_feed.json?_=" + Date.now())'
)

# Fix renderLive
old_renderLive = '''      <div class="tn">${m.away}</div>
    </div>
    ${probBlock(m,p)}
    ${nlpMomentumBlock(m)}
    <div class="verdict anim-block anim-5">'''
new_renderLive = '''      <div class="tn">${m.away}</div>
    </div>
    ${exactScoresStrip(p)}
    ${scoreUncertaintyBlock(p)}
    ${probBlock(m,p)}
    ${nlpMomentumBlock(m)}
    <div class="verdict anim-block anim-5">'''

if old_renderLive in content:
    content = content.replace(old_renderLive, new_renderLive)

# Write back
with open(js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed main.js")
