// assets/components/standings.js
import { STANDINGS, MATCHES } from '../core/state.js';
import { $, teamBadge, parseKickoff } from '../core/utils.js';

export function renderStandings(){
  const box=$("matchList");
  if(!STANDINGS || !STANDINGS.length){
    box.innerHTML=`<div class="empty">Classements indisponibles.</div>`; return;
  }
  box.innerHTML = `<div class="groups-grid">` + STANDINGS.map(g=>{
    const rows=g.rows.map(r=>{
      const qual = r.rank<=2 ? "q1" : (r.rank===3 ? "q3" : "");
      return `<tr class="${qual}">
        <td class="gt-rk">${r.rank}</td>
        <td class="gt-tm">${teamBadge(r.team)}<span>${r.team}</span></td>
        <td>${r.played}</td><td class="gt-hide">${r.win}</td><td class="gt-hide">${r.draw}</td><td class="gt-hide">${r.loss}</td>
        <td class="gt-hide">${r.gf}:${r.ga}</td><td>${r.gd>0?"+":""}${r.gd}</td>
        <td class="gt-pts">${r.pts}</td></tr>`;
    }).join("");
    return `<div class="group-card">
      <div class="group-title">${g.group.replace("Group","Groupe")}</div>
      <table class="grp-table">
        <thead><tr><th></th><th>Équipe</th><th>J</th><th class="gt-hide">G</th><th class="gt-hide">N</th><th class="gt-hide">P</th><th class="gt-hide">Buts</th><th>Diff</th><th>Pts</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  }).join("") + `</div>
  <div class="note" style="margin-top:12px">🟩 1er-2e qualifiés · 🟨 3e éventuellement repêché. Classement calculé sur les résultats réels (pts > différence > buts marqués).</div>`;
}

export function renderBracket(){
  const sortedMatches = [...MATCHES].sort((a,b)=>parseKickoff(a.date)-parseKickoff(b.date));
  const rounds = [
    { id: "LAST_16", label: "Huitièmes de finale" },
    { id: "QUARTER_FINAL", label: "Quarts de finale" },
    { id: "SEMI_FINAL", label: "Demi-finales" },
    { id: "FINAL", label: "Finale" }
  ];
  
  let html = `<div class="bracket-container">`;
  rounds.forEach(r => {
    const matches = sortedMatches.filter(m => String(m.league).includes(r.id));
    if(!matches.length) return;
    html += `<div class="bracket-round"><h4 style="text-align:center;color:var(--muted)">${r.label}</h4>`;
    matches.forEach(m => {
      let scoreHtml = "vs";
      if(m.status === "FINISHED" && (m.analysis||{}).realScore) scoreHtml = m.analysis.realScore;
      else if((m.status === "LIVE"||m.status === "HT") && m.liveScore) scoreHtml = m.liveScore;
      
      html += `<div class="bracket-match" onclick="window.openMatchByTeams('${(m.home||'').replace(/'/g,"\\'")}','${(m.away||'').replace(/'/g,"\\'")}')">
        <div class="bracket-team">${teamBadge(m.home)} <span style="flex-grow:1;margin-left:8px">${m.home}</span>${window.favBtn?window.favBtn(m.home):''}</div>
        <div style="text-align:center; font-weight:800; color:var(--acc); font-size:14px; margin:2px 0">${scoreHtml}</div>
        <div class="bracket-team">${teamBadge(m.away)} <span style="flex-grow:1;margin-left:8px">${m.away}</span>${window.favBtn?window.favBtn(m.away):''}</div>
      </div>`;
    });
    html += `</div>`;
  });
  html += `</div>`;
  $("matchList").innerHTML = html;
}
