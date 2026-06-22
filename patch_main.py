import re

with open("C:/Users/zakro/ZCodeProject/assets/main.js", "r", encoding="utf-8") as f:
    content = f.read()

replacements = [
    (r'try \{ FAV_TEAMS = JSON\.parse\(localStorage\.getItem\("prono_favs"\)\) \|\| \[\]; \} catch\(e\)\{\}',
     r'try { setFavTeams(JSON.parse(localStorage.getItem("prono_favs")) || []); } catch(e){}'),
    (r'FAV_TEAMS = FAV_TEAMS\.filter\(t=>t!==team\);',
     r'setFavTeams(FAV_TEAMS.filter(t=>t!==team));'),
    (r'FAV_TEAMS = \[\.\.\.FAV_TEAMS, team\];',
     r'setFavTeams([...FAV_TEAMS, team]);'),
    (r'MATCHES = data;', r'setMatches(data);'),
    (r'TOPPICKS = JSON\.parse\(tpEl\.textContent\) \|\| null;', r'setTopPicks(JSON.parse(tpEl.textContent) || null);'),
    (r'LIVEFEED = JSON\.parse\(fEl\.textContent\) \|\| \[\];', r'setLiveFeed(JSON.parse(fEl.textContent) || []);'),
    (r'PNL = JSON\.parse\(pEl\.textContent\) \|\| null;', r'setPnl(JSON.parse(pEl.textContent) || null);'),
    (r'STANDINGS = JSON\.parse\(stEl\.textContent\) \|\| \[\];', r'setStandings(JSON.parse(stEl.textContent) || []);'),
    (r'H2H = JSON\.parse\(hEl\.textContent\) \|\| \{\};', r'setH2h(JSON.parse(hEl.textContent) || {});'),
    (r'SELECTED = null;', r'setSelected(null);'),
    (r'TAB=tab\.dataset\.t;', r'setTab(tab.dataset.t);'),
    (r'GROUP="Tous";', r'setGroup("Tous");'),
    (r'SELECTED=m\.home\+"\|"\+m\.away;', r'setSelected(m.home+"|"+m.away);'),
    (r'SELECTED = h\+"\|"\+a;', r'setSelected(h+"|"+a);'),
    (r'GROUP=this\.value;', r'setGroup(this.value);')
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open("C:/Users/zakro/ZCodeProject/assets/main.js", "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced state assignments in main.js successfully.")
