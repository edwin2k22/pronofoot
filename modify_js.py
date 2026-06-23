import re

with open('c:/Users/zakro/ZCodeProject/assets/main.js', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace probBlock
old_prob_block = '''function probBlock(m,p){
  const cm=p.corners, cd=p.cards;
  return \\<div class="grid2">
    <div>
      <h3>Issue du match</h3>
      <div class="probbar"><div class="lbl"><span>Victoire <b>\</b></span><b>\</b></div><div class="track"><div class="b1" style="width:\%"></div></div></div>
      <div class="probbar"><div class="lbl"><span>Match nul</span><b>\</b></div><div class="track"><div class="bx" style="width:\%"></div></div></div>
      <div class="probbar"><div class="lbl"><span>Victoire <b>\</b></span><b>\</b></div><div class="track"><div class="b2" style="width:\%"></div></div></div>
    </div>
    <div>
      <h3>Marchés</h3>
      \
      \
    </div>
  </div>\\\\\\\\\\\;
}'''

new_prob_block = '''function probBlock(m,p){
  const cm=p.corners, cd=p.cards;
  const wrap = (html, delay) => html ? <div class="anim-block anim-\">\</div> : '';
  return \\<div class="grid2 anim-block anim-1">
    <div>
      <h3>Issue du match</h3>
      <div class="probbar anim-block anim-2"><div class="lbl"><span>Victoire <b>\</b></span><b>\</b></div><div class="track"><div class="b1" style="width:\%"></div></div></div>
      <div class="probbar anim-block anim-3"><div class="lbl"><span>Match nul</span><b>\</b></div><div class="track"><div class="bx" style="width:\%"></div></div></div>
      <div class="probbar anim-block anim-4"><div class="lbl"><span>Victoire <b>\</b></span><b>\</b></div><div class="track"><div class="b2" style="width:\%"></div></div></div>
    </div>
    <div class="anim-block anim-5">
      <h3>Marchés</h3>
      \
      \
    </div>
  </div>\\\\\\\\\\\;
}'''

code = code.replace(old_prob_block, new_prob_block)

# Replace vs-box to have animations
code = code.replace('<div class="vs-box">', '<div class="vs-box anim-block anim-3">')

# Replace verdict in finished
code = code.replace('<div class="verdict done">', '<div class="verdict done anim-block anim-4">')

# Replace verdict in upcoming
code = code.replace('<div class="verdict">', '<div class="verdict anim-block anim-5">')

# Add animation to scoreline
code = code.replace('<div class="scoreline">', '<div class="scoreline anim-block anim-1">')

with open('c:/Users/zakro/ZCodeProject/assets/main.js', 'w', encoding='utf-8') as f:
    f.write(code)

print("JS modifie avec succes.")
