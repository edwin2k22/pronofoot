// assets/components/playerProps.js
import { pct, bioHtml } from '../core/utils.js';

export function ppTeam(teamName, pp){
  if(!pp) return `<div class="risk-nd">Effectif indisponible — <b>N/D</b>.</div>`;
  const bar=(p)=>`<span class="pp-bar"><span class="pp-fill" style="width:${Math.round(p*100)}%"></span></span>`;
  const scorers=(pp.scorers||[]).map((s,i)=>`<div class="pp-row">
      <span class="pp-rk">${i+1}</span>
      <span class="pp-nm">${s.name}<span class="pp-pos">${s.poste||""}</span>${s.bio?'<span class="pp-bio-tag">bio ✓</span>':''}</span>
      ${bar(s.p)}<b class="pp-pct">${pct(s.p)}</b>
      <div class="pp-why">${s.why||""}</div>
      ${bioHtml(s.bio)}
    </div>`).join("");
  const cr=pp.creator;
  const creator = cr?`<div class="pp-line"><span class="pp-k">🎨 Créateur principal</span>
    <span><b>${cr.name}</b> <span class="pp-pos">${cr.poste||""}</span> · ${pct(cr.p)} <span class="pp-why-inline">${cr.why||""}</span></span></div>`:"";
  const assisters=(pp.assisters||[]).slice(0,3).map(a=>`<div class="pp-line"><span class="pp-k">🅰️ Passeur</span>
    <span><b>${a.name}</b> <span class="pp-pos">${a.poste||""}</span> · ${pct(a.p)}</span></div>`).join("");
  const gk=pp.keeper;
  const keeper = gk?`<div class="pp-line"><span class="pp-k">🧤 Gardien sollicité</span>
    <span><b>${gk.name}</b>${gk.expSotFaced!=null?` · ~${gk.expSotFaced} tirs cadrés à gérer`:" · N/D"}
    <span class="pp-why-inline">${gk.why||""}</span></span></div>${gk.bio?bioHtml(gk.bio):""}`:"";
  const bench=(pp.benchImpact||[]);
  const benchHtml = bench.length
    ? bench.map(b=>`<div class="pp-line"><span class="pp-k">🔄 Impact banc</span>
        <span><b>${b.name}</b> <span class="pp-pos">${b.poste||""}</span> · <span class="pp-why-inline">${b.why||""}</span></span></div>`).join("")
    : `<div class="pp-line"><span class="pp-k">🔄 Impact banc</span><span style="color:var(--muted)">N/D tant qu'aucun remplaçant n'a été décisif</span></div>`;
  return `<div class="pp-team"><div class="pp-team-h">${teamName}</div>
    <div class="pp-sub">⚽ Buteurs probables</div>${scorers||'<div class="risk-nd">N/D</div>'}
    ${creator}${assisters}${keeper}${benchHtml}</div>`;
}

export function scorersVsBlock(m){
  const a=m.analysis, p=m.prediction; if(!a||!p) return "";
  const ev=a.events||{}; const goals=(ev.goals||[]).filter(g=>g.player && g.player!=="N/D");
  const pp=p.playerProps; if(!pp) return "";
  const norm=s=>(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
  const last=s=>{const n=norm(s).split(" ");return n[n.length-1]||"";};
  const realScorers=goals.map(g=>g.player);
  const realAssists=goals.filter(g=>g.assist).map(g=>({name:g.assist, team:g.team, minute:g.minute, scorer:g.player}));
  const realLast=new Set(realScorers.map(last));
  const realAssistLast=new Set(realAssists.map(a=>last(a.name)));
  const picks=[];
  const assistPicks=[];
  for(const side of ["home","away"]){
    const t=pp[side]||{}; const sc=t.scorers||[]; const ast=t.assisters||[];
    (Array.isArray(sc)?sc:[]).slice(0,3).forEach(x=>picks.push({team:m[side],name:x.name,prob:x.p}));
    (Array.isArray(ast)?ast:[]).slice(0,3).forEach(x=>assistPicks.push({team:m[side],name:x.name,prob:x.p}));
  }
  const goalRows=goals.map(g=>{
    const pred=picks.some(x=>last(x.name)===last(g.player));
    const ast = g.assist ? `<br><small style="color:var(--muted)">Passe decisive : <b>${g.assist}</b></small>` : `<br><small style="color:var(--muted)">Passe decisive : N/D</small>`;
    const note = g.note ? ` <small style="color:var(--muted)">- ${g.note}</small>` : "";
    return `<div class="stat"><span>${g.minute}' <b>${g.player}</b>${note} <small style="color:var(--muted)">(${g.team})</small>${ast}</span>
      <span>${pred?'<span class="vs-chip win">✅ prédit</span>':'<span class="vs-chip lose">—</span>'}</span></div>`;
  }).join("");
  const assistRows=realAssists.map(a=>{
    const pred=assistPicks.some(x=>last(x.name)===last(a.name));
    return `<div class="stat"><span>${a.minute}' <b>${a.name}</b> <small style="color:var(--muted)">pour ${a.scorer} (${a.team})</small></span>
      <span>${pred?'<span class="vs-chip win">✅ prédit</span>':'<span class="vs-chip lose">—</span>'}</span></div>`;
  }).join("");
  const pickRows=picks.map(x=>{
    const nm=x.name; const hit=realLast.has(last(nm));
    const prob=x.prob!=null?` <small>${Math.round(x.prob*100)}%</small>`:"";
    return `<div class="stat"><span>${nm} <small style="color:var(--muted)">(${x.team})</small>${prob}</span>
      <span>${hit?'<span class="vs-chip win">✅ a marqué</span>':'<span class="vs-chip lose">❌</span>'}</span></div>`;
  }).join("");
  const assistPickRows=assistPicks.map(x=>{
    const nm=x.name; const hit=realAssistLast.has(last(nm));
    const prob=x.prob!=null?` <small>${Math.round(x.prob*100)}%</small>`:"";
    return `<div class="stat"><span>${nm} <small style="color:var(--muted)">(${x.team})</small>${prob}</span>
      <span>${hit?'<span class="vs-chip win">✅ passe déc.</span>':'<span class="vs-chip lose">❌</span>'}</span></div>`;
  }).join("");
  return `<div class="module mod-players"><h3>🎯 Buteurs & passeurs : prono vs réel</h3>
    <div class="grid2">
      <div>
        <h4 style="margin:4px 0;font-size:13px">⚽ Buts réels du match</h4>${goalRows||'<div class="note">Aucun but.</div>'}
        <h4 style="margin:10px 0 4px;font-size:13px">Passes décisives réelles</h4>${assistRows||'<div class="note">Aucune passe décisive officielle/N.D.</div>'}
      </div>
      <div>
        <h4 style="margin:4px 0;font-size:13px">🔮 Buteurs pronostiqués (top 3/équipe)</h4>${pickRows||'<div class="note">N/D</div>'}
        <h4 style="margin:10px 0 4px;font-size:13px">Passeurs pronostiqués (top 3/équipe)</h4>${assistPickRows||'<div class="note">N/D</div>'}
      </div>
    </div>
    <div class="note" style="margin-top:6px">Le modèle donne des <b>probabilités</b>, pas des certitudes : un buteur non prédit reste un résultat normal.</div>
  </div>`;
}

export function playerPropsBlock(m,p){
  const pp=p.playerProps; if(!pp) return "";
  if (!pp.home && !pp.away && (!pp.scorers || pp.scorers.length === 0)) return "";
  return `<div class="module mod-players"><h3>👤 Pronos joueurs <span class="mod-hint">probabilités, pas des certitudes</span></h3>
    <div class="pp-note">Probabilités <b>modèle</b> : effectif réel (poste) + production réelle des matchs joués.
    Se précisent à mesure que les équipes jouent. Aucun chiffre inventé.</div>
    <div class="pp-grid">${ppTeam(m.home,pp.home)}${ppTeam(m.away,pp.away)}</div>
  </div>`;
}
