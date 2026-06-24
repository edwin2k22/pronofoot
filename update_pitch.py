with open('c:/Users/zakro/ZCodeProject/assets/dashboard.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Replace .pitch-grass
old_grass = '''.pitch-grass{background:linear-gradient(180deg,#143d28,#0e2c1d);border:1px solid #1e5236;
    border-radius:12px;padding:12px 6px;display:flex;flex-direction:column;justify-content:space-between;
    gap:10px;min-height:230px;background-image:repeating-linear-gradient(180deg,transparent,transparent 28px,rgba(255,255,255,.03) 28px,rgba(255,255,255,.03) 56px)}'''

new_grass = '''.pitch-grass {
  background: #2a6a3b;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-radius: 4px;
  padding: 12px 6px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  min-height: 280px;
  position: relative;
  overflow: hidden;
}
.pitch-grass::before {
  content: ""; position: absolute; top: 50%; left: 0; width: 100%; height: 2px; background: rgba(255, 255, 255, 0.3); z-index: 0;
}
.pitch-grass::after {
  content: ""; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 60px; height: 60px; border: 2px solid rgba(255, 255, 255, 0.3); border-radius: 50%; z-index: 0;
}
.pitch-box-top, .pitch-box-bottom {
  position: absolute; width: 60%; height: 18%; border: 2px solid rgba(255, 255, 255, 0.3); left: 50%; transform: translateX(-50%); z-index: 0;
}
.pitch-box-top { top: 0; border-top: none; }
.pitch-box-bottom { bottom: 0; border-bottom: none; }
.pl-row { z-index: 1; position: relative; }
'''
css = css.replace(old_grass, new_grass)

# Replace .form-dot
old_dot = '.form-dot{width:16px;height:16px;border-radius:50%;box-shadow:0 0 0 2px rgba(0,0,0,.3)}'
new_dot = '.form-dot{width:20px;height:20px;border-radius:50%;box-shadow:0 3px 6px rgba(0,0,0,.5); border: 2px solid #fff;}'
css = css.replace(old_dot, new_dot)

# Ensure pitches grid gap is larger
css = css.replace('.pitches{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}', '.pitches{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:10px}')

with open('c:/Users/zakro/ZCodeProject/assets/dashboard.css', 'w', encoding='utf-8') as f:
    f.write(css)
print("CSS updated")
