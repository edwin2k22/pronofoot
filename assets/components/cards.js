// assets/components/cards.js
import { pct, ouLineRow } from '../core/utils.js';

export function cardsBlock(m,p){
  const c=p.cards; if(!c) return "";
  const ln=c.lines||{};
  const rows=["2.5","3.5","4.5"].filter(k=>ln[k]).map(k=>ouLineRow(`${k} cartons`,ln[k])).join("");
  const ref=p.referee;
  const refLine = (ref && ref.name)
    ? `<div class="stat"><span>🧑‍⚖️ Arbitre</span><span><b>${ref.name}</b> <span style="color:var(--muted)">(${ref.nation || 'N/D'})</span></span></div>`
      + (ref.severity?`<div class="stat"><span>⚖️ Style d'arbitrage</span><span><b>${ref.severity}</b> cartons/match <span style="color:var(--muted);font-size:10px">(${ref.severitySrc})</span></span></div>`:"")
    : `<div class="stat"><span>🧑‍⚖️ Arbitre</span><span style="color:var(--muted)">N/D — non désigné publiquement</span></div>`;
  const red = c.redProb!=null
    ? `<div class="stat"><span>🟥 Au moins 1 rouge</span><span>${pct(c.redProb)} <span style="color:var(--muted);font-size:10px">(approx. structurelle)</span></span></div>`
    : "";
  const rp=p.riskPlayers||{};
  const realList=[...((rp.home&&rp.home.real)||[]).map(x=>({...x,team:m.home})),
                 ...((rp.away&&rp.away.real)||[]).map(x=>({...x,team:m.away}))];
  const realHtml = realList.length
    ? `<div class="risk-real">${realList.map(x=>`<div class="risk-r"><span class="risk-card">${x.card}</span> <b>${x.name}</b> <span class="risk-pos">${x.pos||""} · ${x.team}</span></div>`).join("")}</div>`
    : `<div class="risk-nd">Aucun joueur déjà averti (équipes pas encore en lice ou match propre). <b>N/D</b> tant qu'aucun match joué.</div>`;
  const profiles=((rp.home&&rp.home.profiles)||[]);
  const profHtml = profiles.length
    ? `<div class="risk-prof"><div class="risk-prof-head">🧠 Profils tactiques exposés <span>éclairage générique, pas un joueur nommé</span></div>
        ${profiles.map(x=>`<div class="risk-p">• <b>${x.role}</b> — ${x.why}</div>`).join("")}</div>`
    : "";
  return `<div class="module mod-cards"><h3>🟨 Cartons <span class="mod-hint">${c.src?`📊 ${c.src} · `:""}un match physique ne donne pas toujours beaucoup de cartons</span></h3>
    <div class="mod-top">
      <div class="mod-big"><b>${c.exp_cards}</b><small>total projeté</small></div>
      <div class="mod-split">
        <div class="stat"><span>${m.home}</span><span><b>${c.home}</b></span></div>
        <div class="stat"><span>${m.away}</span><span><b>${c.away}</b></span></div>
      </div>
    </div>
    <div class="ou-wrap">
      <div class="ou-legend"><span><i class="dot u"></i>Under</span><span>50%</span><span><i class="dot o"></i>Over</span></div>
      ${rows}
    </div>
    ${refLine}${red}
    ${(c.foulsHome!=null||c.foulsAway!=null)?`<div class="stat"><span>Fautes moy.</span><span>${c.foulsHome??"N/D"} — ${c.foulsAway??"N/D"}</span></div>`:`<div class="stat"><span>Fautes moy. / équipe</span><span style="color:var(--muted)">N/D (non agrégé gratuitement)</span></div>`}
    <div class="risk-wrap"><div class="risk-head">⚠️ Joueurs à risque</div>${realHtml}${profHtml}</div>
    </div>`;
}
