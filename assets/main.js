import { MATCHES, TAB, GROUP, SELECTED, TOPPICKS, LIVEFEED, PNL, STANDINGS, H2H, FAV_TEAMS, setMatches, setTab, setGroup, setSelected, setTopPicks, setLiveFeed, setPnl, setStandings, setH2h, setFavTeams } from './core/state.js';
import { $, pct, parseKickoff, effectiveStatus, clockMinute, fmtCountdown, countdown, teamBadge, clean, dot, ouLineRow, bioHtml } from './core/utils.js';
import { h2hBlock } from './components/h2h.js';
import { oddsBlock } from './components/odds.js';
import { attackQualityBlock, availabilityBlock, upsetBlock, contextBlock } from './components/context.js';
import { marketsBlock, ouBlock, bttsBlock } from './components/markets.js';
import { scenariosBlock } from './components/scenarios.js';
import { shotsBlock } from './components/shots.js';
import { cornersBlock } from './components/corners.js';
import { cardsBlock } from './components/cards.js';
import { renderStandings, renderBracket } from './components/standings.js';
import { ppTeam, scorersVsBlock, playerPropsBlock } from './components/playerProps.js';
import { halftimeBlock } from './components/halftime.js';
import { renderPerf, drawSpark } from './components/performance.js';

// Attach needed functions to window so inline HTML onclick handlers still work
window.openMatchByTeams = openMatchByTeams;
window.favBtn = favBtn;
window.toggleFav = toggleFav;
window.openSidebar = openSidebar;
window.closeSidebar = closeSidebar;
window.adminAction = adminAction;





/* ===== FAVORIS & NOTIFICATIONS ===== */

try { setFavTeams(JSON.parse(localStorage.getItem("prono_favs")) || []); } catch(e){}

function toggleFav(team) {
  if(FAV_TEAMS.includes(team)) setFavTeams(FAV_TEAMS.filter(t=>t!==team));
  else FAV_TEAMS.push(team);
  localStorage.setItem("prono_favs", JSON.stringify(FAV_TEAMS));
  render();
  updateFavoritesPanel();
  if(Notification.permission === "default") {
    Notification.requestPermission();
  }
}

function favBtn(team) {
  const isFav = FAV_TEAMS.includes(team);
  return `<button class="fav-btn ${isFav?'active':''}" onclick="event.stopPropagation(); toggleFav('${(team||'').replace(/'/g,"\\'")}')" title="Favori">⭐</button>`;
}

function updateFavoritesPanel() {
  const panel = $("favoritesList");
  if(!panel) return;
  if(FAV_TEAMS.length === 0) {
    panel.innerHTML = `<div style="padding:16px;color:var(--muted)">Aucun favori. Cliquez sur l'étoile à côté d'une équipe pour l'ajouter.</div>`;
    return;
  }
  panel.innerHTML = FAV_TEAMS.map(t => `<div style="padding:8px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;">
    <span>${t}</span>
    <button class="icon-btn" style="color:var(--danger)" onclick="toggleFav('${t}')">✕</button>
  </div>`).join("");
}

const favTog = $("favoritesToggle");
if(favTog) {
  favTog.onclick = () => {
    const p = $("favoritesPanel");
    if(p) {
      p.classList.toggle("open");
      if(p.classList.contains("open")) updateFavoritesPanel();
    }
  };
}

function checkNotifications(newData) {
  if(Notification.permission !== "granted") return;
  if(!MATCHES || !MATCHES.length) return;
  
  newData.forEach(newM => {
    if(!FAV_TEAMS.includes(newM.home) && !FAV_TEAMS.includes(newM.away)) return;
    
    const oldM = MATCHES.find(m => m.home === newM.home && m.away === newM.away);
    if(!oldM) return;
    
    const newSt = effectiveStatus(newM);
    const oldSt = effectiveStatus(oldM);
    
    // Status change to LIVE
    if(oldSt !== "LIVE" && oldSt !== "HT" && (newSt === "LIVE" || newSt === "HT")) {
      new Notification(`⚽ Coup d'envoi !`, { body: `${newM.home} vs ${newM.away} a commencé.` });
    }
    
    // Status change to FINISHED
    if(oldSt !== "FINISHED" && newSt === "FINISHED" && newM.analysis) {
      new Notification(`🏁 Match terminé`, { body: `${newM.home} ${newM.analysis.realScore} ${newM.away}` });
    }
    
    // Score change during LIVE
    if((newSt === "LIVE" || newSt === "HT") && newM.liveScore && newM.liveScore !== oldM.liveScore) {
      new Notification(`⚽ But !`, { body: `${newM.home} ${newM.liveScore} ${newM.away}` });
    }
  });
}


/* ---------- chargement ---------- */
function applyData(data, srcLabel){
  if(!Array.isArray(data)||!data.length) return false;
  setMatches(data);
  window.__PRONOFOOT_MATCHES = MATCHES;
  $("srcPill").innerHTML = `<b>${data.length}</b> matchs · ${srcLabel}`;
  const nLive = data.filter(m=>{const s=effectiveStatus(m);return s==="LIVE"||s==="HT";}).length;
  const nFin = data.filter(m=>effectiveStatus(m)==="FINISHED").length;
  const liveCount = $("liveCount");
  if(liveCount) liveCount.textContent = "Dashboard intelligent · données réelles ESPN/Opta · modèle Elo + Poisson";
  updateCounts(); buildGroupFilter(); render();
  return true;
}

function showBuild(){
  const b=document.body.getAttribute("data-build");
  const el=$("buildPill"); if(el && b) el.textContent="🕒 maj "+b;
}

async function load(){
  showBuild();
  // 1) données embarquées (marche toujours, même hors-ligne / dans l'aperçu)
  let embedded = [];
  try{ embedded = JSON.parse($("embedded-data").textContent) || []; }catch(_){}
  try{ const tpEl=$("embedded-toppicks"); if(tpEl) setTopPicks(JSON.parse(tpEl.textContent) || null); }catch(_){}
  try{ const fEl=$("embedded-feed"); if(fEl) setLiveFeed(JSON.parse(fEl.textContent) || []); }catch(_){}
  try{ const pEl=$("embedded-pnl"); if(pEl) setPnl(JSON.parse(pEl.textContent) || null); }catch(_){}
  try{ const stEl=$("embedded-standings"); if(stEl) setStandings(JSON.parse(stEl.textContent) || []); }catch(_){}
  try{ const hEl=$("embedded-h2h"); if(hEl) setH2h(JSON.parse(hEl.textContent) || {}); }catch(_){}
  if(embedded.length) applyData(embedded, "intégré");
  renderLiveFeed();
  renderTopValue();
  renderPerf();

  // 2) tentative live (si un serveur sert le fichier) -> remplace les données
  try{
    const res = await fetch("collector/data/predictions.json?_=" + Date.now(), {cache:"no-store"});
    if(res.ok){
      const data = await res.json();
      checkNotifications(data);
      const sources = [...new Set(data.flatMap(m=>m.sources||[]))].slice(0,3).join(", ");
      applyData(data, sources || "live");
      // si on regardait un match, on rouvre sa version à jour
      if(SELECTED){ const m=MATCHES.find(x=>x.home+"|"+x.away===SELECTED); if(m) showDetail(m); }
    }
  }catch(_){ /* hors-ligne : on garde les données embarquées */ }

  if(!MATCHES.length){
    $("srcPill").textContent = "aucune donnée";
    $("matchList").innerHTML = `<div class="empty">⚠️ Aucune donnée.<br>
      Lance <code>python3 -m collector.refresh && python3 -m collector.embed</code>.</div>`;
  }
}

function updateCounts(){
  // "En cours" inclut KICKOFF (coup d'envoi atteint, en attente de données live)
  const nLive=MATCHES.filter(m=>{const s=effectiveStatus(m);return s==="LIVE"||s==="HT"||s==="KICKOFF";}).length;
  // "À venir" inclut AWAITING (résultat pas encore intégré)
  const nSched=MATCHES.filter(m=>{const s=effectiveStatus(m);return s==="SCHEDULED"||s==="AWAITING";}).length;
  const fins=MATCHES.filter(m=>effectiveStatus(m)==="FINISHED");
  const nFin=fins.length;
  $("cntLive").textContent=nLive; $("cntSched").textContent=nSched; $("cntFin").textContent=nFin;
  const cb=$("cntBest"); if(cb) cb.textContent=(TOPPICKS&&TOPPICKS.picks)?TOPPICKS.picks.length:0;
  // hero cards
  const set=(id,v)=>{const e=$(id);if(e)e.textContent=v;};
  set("heroLive",nLive); set("heroSched",nSched); set("heroFin",nFin);
  const nKick=MATCHES.filter(m=>effectiveStatus(m)==="KICKOFF").length;
  $("heroLiveSub").textContent = nLive? (nKick?"coup d'envoi atteint — données en cours":"suivi en direct") : "aucun match en cours";
  // précision globale du modèle (1N2 sur matchs joués)
  let ok=0,tot=0;
  fins.forEach(m=>{if(m.analysis){tot++; if(m.analysis.predictionCorrect)ok++;}});
  $("heroAcc").textContent = tot?`1N2 réussi : ${ok}/${tot} (${Math.round(ok/tot*100)}%)`:"précision modèle —";
  // prochain match
  const up=MATCHES.filter(m=>effectiveStatus(m)==="SCHEDULED"&&parseKickoff(m.date)!=null)
                  .sort((a,b)=>parseKickoff(a.date)-parseKickoff(b.date))[0];
  $("heroNext").textContent = up?`prochain : ${up.home}–${up.away}`:"calendrier à venir";
}

function buildGroupFilter(){
  const inTab = MATCHES.filter(m=>matchInTab(m));
  const groups = ["Tous", ...new Set(inTab.map(m=>m.league))];
  $("groupFilter").innerHTML = groups.map(g=>`<option value="${g}"${g===GROUP?" selected":""}>${g==="Tous"?"🔎 Toutes les phases":g}</option>`).join("");
}

function matchInTab(m){
  const st = effectiveStatus(m);
  // KICKOFF (coup d'envoi atteint, en attente de données) = onglet "En cours"
  if(TAB==="LIVE") return st==="LIVE"||st==="HT"||st==="KICKOFF";
  // AWAITING (résultat pas encore ingéré) reste avec les matchs "À venir"
  if(TAB==="SCHEDULED") return st==="SCHEDULED"||st==="AWAITING";
  return st===TAB;
}

/* ===== HORLOGE INTELLIGENTE =====================================================
   Calcule le statut RÉEL d'un match à partir de l'heure du coup d'envoi.
   - Respecte les données : un match marqué FINISHED (vrai résultat) reste FINISHED.
   - Sinon, dérive du temps : avant le coup d'envoi -> SCHEDULED (compte à rebours),
     pendant ~[0; 115] min -> LIVE (minute de jeu estimée), après -> FINISHED (horloge).
   - N'INVENTE JAMAIS de score : la minute est une estimation d'horloge, clairement
     marquée ⏱️ ; le score affiché reste celui des vraies données (ou « score à venir »).
   ============================================================================= */
const MATCH_MINUTES = 90, HT_BREAK = 15, STOPPAGE = 8; // durée plausible d'un match

/* effectiveStatus : statut RÉEL d'un match, en RESPECTANT TOUJOURS les données.
   États possibles :
     FINISHED  → vrai résultat confirmé (donnée) OU live périmé devenu fini.
     LIVE / HT → seulement si la DONNÉE le dit ET que l'horloge reste plausible.
     KICKOFF   → l'heure du coup d'envoi est atteinte mais AUCUNE donnée live encore
                 (le match a démarré côté horloge, on attend les vraies infos).
     AWAITING  → coup d'envoi dépassé depuis longtemps, mais résultat pas encore
                 ingéré (on n'invente NI score NI "terminé").
     SCHEDULED → avant le coup d'envoi (compte à rebours).
   L'horloge ne FABRIQUE jamais un LIVE ou un FINISHED « vide ». */






/* ---------- liste ---------- */
/* ===== 🎯 MEILLEURS CHOIX (sélection auto haute confiance) ===== */
const TIER_META = {
  lock:   {icon:"🔒", name:"Verrouillé", col:"#33e0a0", desc:"haute confiance"},
  strong: {icon:"💪", name:"Fort",       col:"#5b8cff", desc:"solide"},
  value:  {icon:"📈", name:"Intéressant",col:"#ffd34e", desc:"à surveiller"},
};
const MARKET_NAME = {DC:"Double chance",DNB:"Sans match nul",OU:"Buts O/U",BTTS:"Les 2 marquent",
  ["1N2"]:"Résultat",TIRS:"Tirs",CORNERS:"Corners",CARTONS:"Cartons"};

function renderBestPicks(){
  const box = $("matchList");
  if(!TOPPICKS || !TOPPICKS.picks || !TOPPICKS.picks.length){
    box.innerHTML = `<div class="empty">Aucun pick à venir pour l'instant. Reviens quand des matchs sont programmés !</div>`;
    return;
  }
  const rel = TOPPICKS.reliability || {};
  const tiers = rel.byTier || {};
  const lock = tiers.lock||{}, strong=tiers.strong||{}, val=tiers.value||{};
  const sample = rel.sampleMatches || 0;
  // bandeau fiabilité réelle mesurée
  const relCard = (t,r)=>{
    const meta=TIER_META[t];
    return `<div class="rel-card" style="border-color:${meta.col}44">
      <div style="font-size:11px;color:var(--muted)">${meta.icon} ${meta.name}</div>
      <div style="font-size:22px;font-weight:800;color:${meta.col}">${r.pct!=null?r.pct+"%":"—"}</div>
      <div style="font-size:10px;color:var(--muted)">${r.won||0}/${r.total||0} réussis (mesuré)</div>
    </div>`;
  };
  // groupes par niveau
  const order=["lock","strong","value"];
  let groups="";
  for(const t of order){
    const picks=TOPPICKS.picks.filter(p=>p.tier===t);
    if(!picks.length) continue;
    const meta=TIER_META[t];
    groups += `<h3 style="margin:18px 0 8px;color:${meta.col}">${meta.icon} ${meta.name} <span class="mod-hint">${meta.desc} · fiabilité mesurée ${(tiers[t]||{}).pct??"—"}%</span></h3>`;
    groups += picks.map(p=>{
      const conf=Math.round(p.prob*100);
      return `<div class="pick-row" onclick="openMatchByTeams('${(p.home||'').replace(/'/g,"\\'")}','${(p.away||'').replace(/'/g,"\\'")}')">
        <div class="pick-conf" style="color:${meta.col}">${conf}%</div>
        <div class="pick-body">
          <div class="pick-label">${p.label}</div>
          <div class="pick-match">${p.home} <span style="opacity:.5">vs</span> ${p.away} <span class="pick-mk">${MARKET_NAME[p.market]||p.market}</span></div>
          ${p.why?`<div class="pick-why">${p.why}</div>`:""}
        </div>
        <div class="pick-arrow">›</div>
      </div>`;
    }).join("");
  }
  // ----- combiné (accumulateur) : 1 pick verrouillé par match, max 4 -----
  const lockPicks = TOPPICKS.picks.filter(p=>p.tier==="lock");
  const seenMatch = new Set();
  const combo = [];
  for(const p of lockPicks){
    const k=p.home+"|"+p.away;
    if(seenMatch.has(k)) continue;
    seenMatch.add(k); combo.push(p);
    if(combo.length>=4) break;
  }
  let comboHtml="";
  if(combo.length>=2){
    const comboProb = combo.reduce((a,p)=>a*p.prob,1);
    const legs = combo.map(p=>`<div class="combo-leg"><span>${p.home} v ${p.away}</span><b>${p.label}</b><span style="color:#33e0a0">${Math.round(p.prob*100)}%</span></div>`).join("");
    comboHtml = `<div class="combo-box" style="margin-top:0; height:100%;">
      <div class="combo-head">🧩 Combiné du jour <span class="mod-hint">${combo.length} sélections verrouillées</span></div>
      ${legs}
      <div class="combo-total">Probabilité combinée du modèle : <b>${Math.round(comboProb*100)}%</b>
        <span style="color:var(--muted);font-size:11px"> (cote théorique ≈ ${(1/comboProb).toFixed(2)})</span></div>
      <div class="note" style="margin-top:6px">Un combiné multiplie les risques : il suffit d'1 raté pour tout perdre. À jouer avec prudence.</div>
    </div>`;
  }

  // groups par niveau (reconstruit avec grille interne)
  let groupsHtml = "";
  for(const t of order){
    const picks=TOPPICKS.picks.filter(p=>p.tier===t);
    if(!picks.length) continue;
    const meta=TIER_META[t];
    groupsHtml += `<h3 style="margin:24px 0 12px;color:${meta.col};grid-column:1/-1;">${meta.icon} ${meta.name} <span class="mod-hint">${meta.desc} · fiabilité mesurée ${(tiers[t]||{}).pct??"—"}%</span></h3>`;
    groupsHtml += `<div style="grid-column:1/-1; display:grid; grid-template-columns:repeat(auto-fill, minmax(330px, 1fr)); gap:12px;">`;
    groupsHtml += picks.map(p=>{
      const conf=Math.round(p.prob*100);
      return `<div class="pick-row" style="margin-bottom:0;" onclick="openMatchByTeams('${(p.home||'').replace(/'/g,"\\'")}','${(p.away||'').replace(/'/g,"\\'")}')">
        <div class="pick-conf" style="color:${meta.col}">${conf}%</div>
        <div class="pick-body">
          <div class="pick-label">${p.label}</div>
          <div class="pick-match">${p.home} <span style="opacity:.5">vs</span> ${p.away} <span class="pick-mk">${MARKET_NAME[p.market]||p.market}</span></div>
          ${p.why?`<div class="pick-why">${p.why}</div>`:""}
        </div>
        <div class="pick-arrow">›</div>
      </div>`;
    }).join("");
    groupsHtml += `</div>`;
  }

  box.innerHTML = `
    <div style="grid-column: 1 / -1;">
      <div class="best-intro" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(400px, 1fr)); gap:24px; align-items:stretch;">
        <div>
          <div class="best-title">🎯 Les meilleurs choix de l'app</div>
          <div class="best-sub">Sélection automatique des paris les plus sûrs parmi <b>tout</b> ce que le modèle prédit.
            Le taux de réussite affiché est <b>réellement mesuré</b> sur les ${sample} matchs déjà joués — pas une promesse.</div>
          <div class="rel-grid">${relCard("lock",lock)}${relCard("strong",strong)}${relCard("value",val)}</div>
        </div>
        <div>
          ${comboHtml}
        </div>
      </div>
      ${groupsHtml || '<div class="empty" style="margin-top:24px;">Aucun pick assez fiable pour l\'instant.</div>'}
      <div class="note" style="margin-top:24px;">⚠️ Paris sportifs = risque réel. Même à 90%+, 1 pari sur 10 perd. Joue de façon responsable. Aucune donnée inventée : tout dérive des matchs réels.</div>
    </div>
  `;
}

function openMatchByTeams(h,a){
  const m = MATCHES.find(x=>x.home===h && x.away===a);
  if(m) showDetail(m);
}

/* journal temps réel : montre que la machine réagit aux nouvelles infos */
function renderLiveFeed(){
  const box=$("liveFeed"); if(!box) return;
  if(!LIVEFEED || !LIVEFEED.length){ box.classList.add("u-hidden"); return; }
  box.classList.remove("u-hidden");
  const rows=LIVEFEED.slice(0,8).map(e=>
    `<div class="lf-row"><span class="lf-t">${e.t||""}</span>${e.text||""}</div>`).join("");
  box.innerHTML=`<h4><span class="lf-dot"></span> ⚡ Mises à jour en direct <span class="mod-hint">la machine recalcule à chaque nouvelle info</span></h4>${rows}`;
}

/* TOP 3 VALUE BETS du jour (écart proba modèle vs cote bookmaker) */
function renderTopValue(){
  const box=$("topValue"); if(!box) return;
  const tv=(PNL && PNL.topValue) || [];
  if(!tv.length){ box.classList.add("u-hidden"); return; }
  box.classList.remove("u-hidden");
  const cards=tv.map(b=>{
    const edge=Math.round(b.edge*100);
    let trend = "";
    if (b.lineMovement && b.lineMovement !== 0) {
       const isDrop = b.lineMovement < 0;
       const col = isDrop ? "var(--acc)" : "var(--danger)";
       const arr = isDrop ? "↘" : "↗";
       trend = `<span style="color:${col}; font-size:11px; margin-left:6px;" title="Évolution de la cote depuis l'ouverture">
                  ${arr} ${Math.abs(b.lineMovement).toFixed(2)}
                </span>`;
    }
    return `<div class="tv-card" onclick="openMatchByTeams('${(b.home||'').replace(/'/g,"\\'")}','${(b.away||'').replace(/'/g,"\\'")}')">
      <div class="tv-match">${b.home} <span style="opacity:.5">vs</span> ${b.away}</div>
      <div class="tv-pick">${b.label}</div>
      <div class="tv-nums">
        <span>Modèle <b style="color:var(--acc)">${Math.round(b.prob*100)}%</b> · cote <span class="tv-odd">${b.odd}</span>${trend}</span>
        <span class="tv-edge">+${edge}% value</span>
      </div>
    </div>`;
  }).join("");
  box.innerHTML=`<div class="tv-head">💎 Top Value Bets du jour <span class="mod-hint">écart entre la proba du modèle et la cote du bookmaker</span></div>
    <div class="tv-grid">${cards}</div>`;
}

/* PERFORMANCE : ROI dans le hero + sparkline d'évolution de la réussite */


/* sparkline : précision cumulée du modèle (1N2) au fil des matchs joués */


/* 🏆 CLASSEMENT DES GROUPES */





function render(){
  if(TAB==="BEST"){ renderBestPicks(); return; }
  if(TAB==="GROUPS"){ renderStandings(); return; }
  if(TAB==="BRACKET"){
    const ml = $("matchList"); if(ml) ml.classList.add("u-hidden");
    const hero = document.querySelector(".hero"); if(hero) hero.classList.add("u-hidden");
    renderBracket(); 
    return; 
  } else {
    const box=$("bracketView"); if(box) box.classList.add("u-hidden");
    const ml = $("matchList"); if(ml) ml.classList.remove("u-hidden");
    const hero = document.querySelector(".hero"); if(hero) hero.classList.remove("u-hidden");
  }
  const q = $("search").value.toLowerCase();
  let list = MATCHES.filter(matchInTab);
  if(GROUP!=="Tous") list = list.filter(m=>m.league===GROUP);
  if(q) list = list.filter(m=>(m.home+" "+m.away).toLowerCase().includes(q));

  if(!list.length){
    const msg = TAB==="LIVE"
      ? "🔴 Aucun match en cours actuellement. Reviens à l'heure d'un coup d'envoi !"
      : TAB==="FINISHED"
      ? "Aucun match terminé pour l'instant."
      : "Aucun match à venir dans cette catégorie.";
    // note : les matchs au coup d'envoi apparaissent dans « En cours », ceux dont le
    // résultat n'est pas encore intégré restent dans « À venir » jusqu'au rafraîchissement.
    $("matchList").innerHTML = `<div class="empty">${msg}</div>`;
    return;
  }
  $("matchList").innerHTML = "";
  list.forEach(m=>{
    const st = effectiveStatus(m);
    const isLive=st==="LIVE"||st==="HT";          // donnée live RÉELLE
    const isDone=st==="FINISHED";
    const isKick=st==="KICKOFF";                  // coup d'envoi atteint, en attente de données
    const isAwait=st==="AWAITING";               // résultat pas encore intégré
    const p=m.prediction||{};
    const when = m.date ? m.date.slice(0,16) : "";
    // bandeau + accent couleur selon le statut
    let badge="", accent="var(--acc)";
    if(isLive){
      const cm=clockMinute(m);
      // priorité à la VRAIE minute ESPN (m.liveClock) sinon estimation horloge
      const realMin = m.liveClock || (cm?cm.label:"");
      const min = realMin ? ` ⏱️${realMin}` : "";
      badge=`<span class="tag live">🔴 LIVE${min}</span>`; accent="var(--live)";
    } else if(isKick){
      badge=`<span class="tag live">🟢 Coup d'envoi</span>`; accent="var(--live)";
    } else if(isDone){
      badge=`<span class="tag done">🏁 Terminé</span>`; accent="var(--gold)";
    } else if(isAwait){
      badge=`<span class="tag soon">⌛ Résultat à venir</span>`; accent="var(--gold)";
    } else {
      badge=`<span class="tag soon">⏳ ${countdown(m)}</span>`; accent="var(--acc)";
    }
    // score affiché : réel/live UNIQUEMENT si la donnée existe ; sinon prono.
    // On ne fabrique JAMAIS un score : KICKOFF/AWAITING montrent le prono d'avant-match.
    let scoreHtml;
    if(isDone && m.realScore) scoreHtml=`<div class="mi-score">${m.realScore.replace("-"," – ")}</div><div class="mi-when">score final</div>`;
    else if(isLive && m.liveScore) scoreHtml=`<div class="mi-score">${m.liveScore.replace("-"," – ")}</div><div class="mi-when">en direct</div>`;
    else if(isKick) scoreHtml=`<div class="mi-vsmid">VS</div><div class="mi-when">en attente du direct</div>`;
    else if(isAwait) scoreHtml=`<div class="mi-vsmid">VS</div><div class="mi-when">résultat en attente</div>`;
    else if(p.topScore) scoreHtml=`<div class="mi-vsmid">VS</div><div class="mi-when">prév. ${p.topScore[0]}-${p.topScore[1]}</div>`;
    else scoreHtml=`<div class="mi-vsmid">VS</div>`;
    // barre proba 1N2
    let probBar="";
    if(p.p1!=null) probBar=`<div class="mi-probbar">
      <i class="mi-p1" style="width:${p.p1*100}%"></i><i class="mi-px" style="width:${p.pX*100}%"></i><i class="mi-p2" style="width:${p.p2*100}%"></i></div>`;
    // méta : tags (value, scénario, bilan terminé)
    let tags="";
    if(isDone && m.analysis){
      tags = m.analysis.predictionCorrect?'<span class="tag ok">✅ prono réussi</span>':'<span class="tag ko">❌ prono manqué</span>';
      tags += vsSummaryInline(m);
    } else {
      const hasVal=["home","draw","away","over","under"].some(k=>(p.value||{})[k]&&p.value[k].value);
      if(hasVal) tags+=`<span class="tag val">💎 value détectée</span>`;
      const ui=p.upsetIndex;
      if(ui && ui.index>=45){
        const col = ui.index>=55?"var(--danger)":"var(--warn)";
        tags+=`<span class="tag" style="background:rgba(255,179,71,.14);border:1px solid ${col};color:${col}">⚠️ surprise ${ui.index}/100</span>`;
      }
      const sc=(p.scenarios||[]).filter(s=>!s.angle);
      const lead=sc.length?sc.reduce((a,b)=>b.p>a.p?b:a):null;
      if(lead) tags+=`<span class="tag" style="background:var(--glass);border:1px solid var(--line);color:var(--muted)">🎬 ${lead.title} ${pct(lead.p)}</span>`;
    }
    const cta=isDone?"Analyse →":(isLive||isKick?"Suivre →":(isAwait?"Voir prono →":"Pronostic →"));
    const d=document.createElement("div");
    d.className="matchitem";
    d.innerHTML=`<div class="mi-accent" style="background:${accent}"></div>
      <div class="mi-body">
        <div class="mi-lg"><span>📍 ${m.league}</span><span>${when}</span>${badge}</div>
        <div class="mi-vs">
          <div class="mi-team">${teamBadge(m.home)}<span class="mi-tname">${m.home}</span>${favBtn(m.home)}</div>
          <div class="mi-center">${scoreHtml}</div>
          <div class="mi-team away">${favBtn(m.away)}${teamBadge(m.away)}<span class="mi-tname">${m.away}</span></div>
        </div>
        ${probBar}
        <div class="mi-meta"><div class="mi-tags">${tags}</div><div class="mi-go">${cta}</div></div>
      </div>`;
    d.onclick=()=>{ setSelected(m.home+"|"+m.away); showDetail(m); };
    $("matchList").appendChild(d);
  });
}

/* pastille équipe : initiales + couleur dérivée du nom (déterministe) */

/* résumé X/4 inline pour les cartes terminées */
function vsSummaryInline(m){
  const a=m.analysis,p=m.prediction; if(!a||!p) return "";
  const overPred=p.over25>=0.5,bttsPred=p.btts>=0.5;
  const hits=[a.predictionCorrect,a.exactScore,overPred===a.over25Real,bttsPred===a.bttsReal].filter(Boolean).length;
  return `<span class="tag" style="background:var(--glass);border:1px solid var(--line);color:var(--muted)">${hits}/4 marchés</span>`;
}

/* ---------- détail ---------- */
function showDetail(m){
  const d=$("detail");
  const st = effectiveStatus(m);
  if(st==="FINISHED" && m.analysis) d.innerHTML = renderFinished(m);
  else if(st==="LIVE"||st==="HT") d.innerHTML = renderLive(m);
  else if(st==="KICKOFF") d.innerHTML = renderUpcoming(m, "kickoff");
  else if(st==="AWAITING") d.innerHTML = renderUpcoming(m, "awaiting");
  else d.innerHTML = renderUpcoming(m);
  
  $("offcanvas").classList.add("open");
  $("ocBackdrop").classList.add("open");
  $("offcanvas").scrollTop = 0;
  document.body.style.overflow = "hidden";
  
  // Fetch live timeline for ESPN commentary
  if(st==="FINISHED" || st==="LIVE" || st==="HT" || st==="KICKOFF") {
    fetch(`/api/timeline?home=${encodeURIComponent(m.home)}&away=${encodeURIComponent(m.away)}`)
      .then(r => r.json())
      .then(data => {
         const container = document.getElementById("live-timeline-container");
         if(!container) return;
         if(!data || !data.commentary || data.commentary.length === 0) return;
         
         const comments = data.commentary.map(c => 
           `<div class="tl-row" style="margin-top:4px">
              <div class="tl-min" style="color:var(--muted)">${c.time?.displayValue || ''}</div>
              <div class="tl-ev" style="width:100%">
                <div style="font-size:12px;color:var(--muted);background:var(--glass);padding:6px;border-radius:4px;border-left:2px solid var(--line);">
                  🎙️ ${c.text}
                </div>
              </div>
            </div>`
         ).join("");
         
         // On ajoute ou remplace la section "Déroulé du match" existante
         // S'il y a déjà des events statiques (buts, cartons), on les affiche AVANT les commentaires
         let staticEvents = "";
         if(m.analysis && m.analysis.events) {
           staticEvents = timeline(m, m.analysis);
         }
         
         container.innerHTML = staticEvents + comments;
      })
      .catch(e => console.log("Timeline fetch error", e));
  }
}
function closeDetail(){
  $("offcanvas").classList.remove("open");
  $("ocBackdrop").classList.remove("open");
  document.body.style.overflow = "";
  setSelected(null);
}
window.showDetail = showDetail;

function srcTags(m){ return `<div class="src">${(m.sources||[]).map(s=>`<span>${s}</span>`).join("")}</div>`; }

/* match TERMINÉ : score + analyse + stats complètes + prono d'avant */
/* déroulé du match : buteurs, cartons, MOTM, commentary */
function timeline(m, a){
  const e = a.events;
  if(!e) return "";
  const icon = c => c==="Red"?"🟥":"🟨";
  let items = [];
  (e.goals||[]).forEach(g=> items.push({min:g.minute, side:g.team===m.home?"h":"a",
    html:`⚽ <b>${g.player}</b> ${g.assist?`<span style="color:var(--muted)">(passe ${g.assist})</span>`:""} <span style="color:var(--muted)">${g.team}</span>`}));
  (e.cards||[]).forEach(c=> items.push({min:c.minute, side:c.team===m.home?"h":"a",
    html:`${icon(c.type)} ${c.player} <span style="color:var(--muted)">${c.team}${c.note?" · "+c.note:""}</span>`}));
  (e.commentary||[]).forEach(c=> items.push({min:c.minute, side:"c",
    html:`<div style="font-size:12px;color:var(--muted);background:var(--glass);padding:6px;border-radius:4px;border-left:2px solid var(--line);">🎙️ ${c.text}</div>`}));
  
  items.sort((x,y)=>x.min-y.min);
  if(items.length === 0 && !e.motm && !e.note) return "";
  
  const rows = items.map(it=>{
    if(it.side === "c") {
        return `<div class="tl-row" style="margin-top:4px"><div class="tl-min">${it.min}'</div><div class="tl-ev" style="width:100%">${it.html}</div></div>`;
    }
    return `<div class="tl-row tl-${it.side}"><div class="tl-min">${it.min}'</div><div class="tl-ev">${it.html}</div></div>`;
  }).join("");
  
  const motm = e.motm?`<div class="tl-motm">⭐ Homme du match : <b>${e.motm}</b></div>`:"";
  const note = e.note?`<div class="note" style="margin-top:8px">${e.note}</div>`:"";
  return `<div style="margin-top:14px"><h3>⏱️ Déroulé du match</h3><div style="max-height: 350px; overflow-y: auto; padding-right: 8px;">${rows}</div>${motm}${note}</div>`;
}

/* ANGLE 3 — mini-terrain CSS : compo cartographiée + pastilles de forme */
function pitchFor(team, form, coach, xi, side){
  // répartit le XI par lignes selon la formation (ex "4-3-3")
  const lines = (form||"4-3-3").split("-").map(n=>parseInt(n)||0).filter(Boolean);
  const names = (xi||[]).slice();
  const gk = names.shift(); // 1er = gardien
  let rows = [`<div class="pl-row"><span class="pl">${dot(gk)}<i>${clean(gk)}</i></span></div>`];
  let idx = 0;
  lines.forEach(n=>{
    const cells = [];
    for(let i=0;i<n && idx<names.length;i++,idx++){
      cells.push(`<span class="pl">${dot(names[idx])}<i>${clean(names[idx])}</i></span>`);
    }
    rows.push(`<div class="pl-row">${cells.join("")}</div>`);
  });
  
  // on inverse toujours pour que le gardien soit en bas (les deux équipes attaquent vers le haut)
  rows.reverse();
  
  return `<div class="pitch ${side}">
      <div class="pitch-head" style="text-align:center; padding-bottom:6px;">${team} <b style="color:var(--acc2);">${form||""}</b>${coach?`<br><span style="font-weight:normal;font-size:11px;opacity:0.8;">👔 ${coach}</span>`:""}</div>
      <div class="pitch-grass">
        <div class="pitch-box-top"></div>
        <div class="pitch-box-bottom"></div>
        ${rows.join("")}
      </div>
    </div>`;
}

/* pastille de forme : vert/jaune/rouge — placeholder déterministe tant que xG joueur = N/D */


/* compositions : mini-terrain + impact tactique sur le modèle */
function lineupsBlock(m, a){
  const e = a.events; if(!e || !e.lineups) return "";
  const L = e.lineups;
  const li = (m.prediction&&m.prediction.lineupImpact)||{};
  const impact = li.tacticalMod!=null ? `<div class="note" style="margin-top:8px">
      ⚙️ <b>Impact sur le modèle :</b> duel ${L.home_formation} vs ${L.away_formation} →
      modificateur tactique ×${li.tacticalMod}.
      ${li.rotationDeltaHome>0.02?`Rotation ${m.home} −${Math.round(li.rotationDeltaHome*100)}% offensif.`:""}
      ${li.benchBonusOver25>0?` Banc → +${Math.round(li.benchBonusOver25*100)}% Over 2.5.`:""}
    </div>`:"";
  const bench = (label, list) => (list&&list.length) ? `<div class="bench">
      <span class="bench-lbl">🪑 ${label} :</span> ${list.map(p=>`<span class="bench-p">${dot(p)}${clean(p)}</span>`).join("")}
    </div>` : "";
  return `<details style="margin-top:12px" open><summary>👥 Compositions (système & impact)</summary>
    <div class="pitches">
      ${pitchFor(m.home, L.home_formation, L.home_coach, L.home_xi, "home")}
      ${pitchFor(m.away, L.away_formation, L.away_coach, L.away_xi, "away")}
    </div>
    <div class="legend-form">🟢 en forme · 🟡 moyen · 🔴 méforme <span style="opacity:.6">(forme = xG récent dès que dispo)</span></div>
    ${bench(m.home, L.home_bench)}
    ${bench(m.away, L.away_bench)}
    ${impact}
  </details>`;
}

/* ===== COMPARAISON PRONO vs RÉSULTAT (onglet Terminés) =====
   Confronte, marché par marché, ce que le modèle avait prévu AVANT le match
   et ce qui s'est réellement passé. ✅ = vu juste, ❌ = manqué. 100% données réelles. */
function vsTable(m){
  const a=m.analysis, p=m.prediction; if(!a||!p) return "";
  const lbl={"1":m.home,"X":"Nul","2":m.away};
  const row=(market, prono, reel, ok)=>`<div class="vs-row">
    <span class="vs-mk">${market}</span>
    <span class="vs-prono">${prono}</span>
    <span class="vs-arrow">→</span>
    <span class="vs-reel">${reel}</span>
    <span class="vs-ok ${ok===null?'na':(ok?'win':'lose')}">${ok===null?"—":(ok?"✅":"❌")}</span>
  </div>`;
  const rows=[]; let hits=0, total=0;
  const add=(market,prono,reel,ok)=>{ rows.push(row(market,prono,reel,ok)); if(ok!==null){total++; if(ok)hits++;} };

  // total de buts réel
  const tg=a.totalGoals;
  const [gh,ga]=a.realScore.split("-").map(Number);

  // 1) Résultat 1N2
  const pprob={"1":p.p1,"X":p.pX,"2":p.p2}[a.predictedOutcome];
  add("Résultat 1N2", `${lbl[a.predictedOutcome]} (${pct(pprob)})`, lbl[a.outcome], a.predictionCorrect);

  // 2) Double chance (le modèle "joue" la double chance la plus probable)
  if(p.doubleChance){
    const dc=p.doubleChance;
    const cand=[["1X",dc["1X"],["1","X"]],["12",dc["12"],["1","2"]],["X2",dc["X2"],["X","2"]]]
      .sort((x,y)=>y[1]-x[1])[0];
    const dcLbl={"1X":`${m.home} ou nul`,"12":"pas de nul","X2":`nul ou ${m.away}`}[cand[0]];
    const dcOk=cand[2].includes(a.outcome);
    add("Double chance", `${dcLbl} (${pct(cand[1])})`, lbl[a.outcome], dcOk);
  }

  // 3) Draw No Bet (nul = annulé)
  if(p.drawNoBet){
    const dnb=p.drawNoBet, pick=dnb.home>=dnb.away?"1":"2";
    const dnbOk = a.outcome==="X" ? null : (pick===a.outcome);
    add("Draw No Bet", `${lbl[pick]} (${pct(Math.max(dnb.home,dnb.away))})`,
        a.outcome==="X"?"nul → remboursé":lbl[a.outcome], dnbOk);
  }

  // 4) Score exact
  add("Score exact", `${p.topScore[0]}-${p.topScore[1]}`, a.realScore, a.exactScore);

  // 5) Over/Under multi-lignes (1.5 / 2.5 / 3.5)
  if(p.overUnder){
    [["1.5",1],["2.5",2],["3.5",3]].forEach(([ln,thr])=>{
      const o=p.overUnder[ln]; if(!o) return;
      const overPred=o.over>=0.5, overReal=tg>parseFloat(ln);
      add(`Over ${ln} buts`,
        `${overPred?"Over":"Under"} (${pct(overPred?o.over:o.under)})`,
        `${overReal?"Over":"Under"} (${tg})`, overPred===overReal);
    });
  } else {
    const overPred=p.over25>=0.5;
    add("Over 2.5 buts", `${overPred?"Over":"Under"} (${pct(overPred?p.over25:1-p.over25)})`,
        `${a.over25Real?"Over":"Under"} (${tg})`, overPred===a.over25Real);
  }

  // 6) BTTS
  const bttsPred=p.btts>=0.5;
  add("Les 2 marquent", `${bttsPred?"Oui":"Non"} (${pct(bttsPred?p.btts:1-p.btts)})`,
      a.bttsReal?"Oui":"Non", bttsPred===a.bttsReal);

  // 7) Cartons (ligne du modèle vs total réel)
  if(p.cards && a.homeCards!=null && a.awayCards!=null){
    const realCards=(a.homeCards||0)+(a.awayCards||0);
    const cl=p.cards.line, cOverPred=p.cards.over>=0.5, cOverReal=realCards>cl;
    add(`Cartons O/U ${cl}`,
      `${cOverPred?"Over":"Under"} (${pct(cOverPred?p.cards.over:p.cards.under)})`,
      `${cOverReal?"Over":"Under"} (${realCards})`, cOverPred===cOverReal);
  }

  // 8) Corners (modèle calibré empiriquement vs total réel du match)
  if(p.corners && a.homeCorners!=null && a.awayCorners!=null){
    const realCorn=(a.homeCorners||0)+(a.awayCorners||0);
    const col=p.corners.line, coOverPred=p.corners.over>=0.5, coOverReal=realCorn>col;
    add(`Corners O/U ${col}`,
      `${coOverPred?"Over":"Under"} (${pct(coOverPred?p.corners.over:p.corners.under)})`,
      `${coOverReal?"Over":"Under"} (${realCorn})`, coOverPred===coOverReal);
  }

  // 9) Score mi-temps (indicatif : on n'a pas toujours le score MT réel -> N/A)
  if(p.halftime){
    const realHt = (a && a.events && a.events.halftime) ? a.events.halftime : "non disponible";
    const predStr = `${p.halftime.topScore[0]}-${p.halftime.topScore[1]}`;
    let isCorrect = null;
    if (realHt !== "non disponible") {
      isCorrect = (realHt === predStr);
    }
    add("Score mi-temps", predStr, realHt, isCorrect);
  }

  return `<div class="vs-box anim-block anim-3">
    <div class="vs-head">⚖️ Prédictions du modèle <span>vs</span> Résultat réel
      <span class="vs-score">${hits}/${total} marchés réussis</span></div>
    <div class="vs-cols"><span>marché</span><span>prévu (proba)</span><span></span><span>réel</span><span></span></div>
    ${rows.join("")}
    <div class="vs-foot">Prédictions figées <b>avant le coup d'envoi</b>. ✅ vu juste · ❌ manqué · — non comparable.</div>
  </div>`;
}

/* mini-résumé pour la carte de liste (onglet Terminés) */
function vsSummary(m){
  const a=m.analysis, p=m.prediction; if(!a||!p) return "";
  const overPred=p.over25>=0.5, bttsPred=p.btts>=0.5;
  const hits=[a.predictionCorrect,a.exactScore,overPred===a.over25Real,bttsPred===a.bttsReal].filter(Boolean).length;
  const chip=(ok,txt)=>`<span class="vs-chip ${ok?'win':'lose'}">${ok?"✅":"❌"} ${txt}</span>`;
  return `<div class="vs-mini">${chip(a.predictionCorrect,"1N2")}${chip(a.exactScore,"score")}`
    + `${chip(overPred===a.over25Real,"O/U")}${chip(bttsPred===a.bttsReal,"BTTS")}`
    + `<span class="vs-mini-tot">${hits}/4</span></div>`;
}

function renderFinished(m){
  const a=m.analysis, p=m.prediction;
  const st=(label,h,v)=>`<div class="stat"><span>${label}</span><span>${h??"N/D"} — ${v??"N/D"}</span></div>`;
  return `<div class="card">
    <div class="banner done">🏁 Match TERMINÉ — résultat & analyse (pas un pronostic).</div>
    <div class="scoreline anim-block anim-1">
      <div class="tn">${m.home}</div>
      <div class="sc gold">${a.realScore.replace("-"," – ")}<small>score final</small></div>
      <div class="tn">${m.away}</div>
    </div>
    ${vsTable(m)}
    <div class="verdict done anim-block anim-4"><b>${a.predictionCorrect?"✅":"❌"} Verdict du modèle :</b> ${a.summary}</div>
    ${formRow(m)}
    <div id="live-timeline-container">${timeline(m, a)}</div>
    ${lineupsBlock(m, a)}
    <div class="grid2" style="margin-top:16px">
      <div>
        <h3>📊 Statistiques du match</h3>
        ${st("Buts", a.realScore.split("-")[0], a.realScore.split("-")[1])}
        ${st("xG réel", a.homeXgReal, a.awayXgReal)}
        ${st("Tirs", a.homeShots, a.awayShots)}
        ${(a.homeShotsOn!=null||a.awayShotsOn!=null)?st("Tirs cadrés", a.homeShotsOn, a.awayShotsOn):""}
        ${st("Corners", a.homeCorners, a.awayCorners)}
        ${st("Cartons", a.homeCards, a.awayCards)}
        <div class="stat"><span>Total buts</span><span>${a.totalGoals} (${a.over25Real?"Over":"Under"} 2.5)</span></div>
        <div class="stat"><span>Les deux marquent</span><span>${a.bttsReal?"Oui":"Non"}</span></div>
      </div>
      <div>
        <h3>🔮 Ce que le modèle avait prévu</h3>
        <div class="probbar"><div class="lbl"><span>Victoire ${m.home}</span><b>${pct(p.p1)}</b></div><div class="track"><div class="b1" style="width:${p.p1*100}%"></div></div></div>
        <div class="probbar"><div class="lbl"><span>Match nul</span><b>${pct(p.pX)}</b></div><div class="track"><div class="bx" style="width:${p.pX*100}%"></div></div></div>
        <div class="probbar"><div class="lbl"><span>Victoire ${m.away}</span><b>${pct(p.p2)}</b></div><div class="track"><div class="b2" style="width:${p.p2*100}%"></div></div></div>
        <div class="stat" style="margin-top:8px"><span>Score le plus probable</span><span>${p.topScore[0]}-${p.topScore[1]} ${a.exactScore?"✅ exact":""}</span></div>
        <div class="note">Prono d'avant-match conservé pour comparaison. Issue réelle :
          <b>${a.winner||"match nul"}</b>.</div>
      </div>
    </div>
    ${teamStatsBlock(m)}
    ${scorersVsBlock(m)}
    ${srcTags(m)}
  </div>`;
}

/* ===== STATS D'ÉQUIPE COMPLÈTES (match terminé) — données réelles ESPN/Opta ===== */
function teamStatsBlock(m){
  const ts=(m.analysis||{}).teamStats; if(!ts) return "";
  // barre comparative domicile vs extérieur pour chaque métrique
  const bar=(label,h,a,fmt)=>{
    if(h==null && a==null) return "";
    const hv=h||0, av=a||0, tot=Math.max(hv+av,0.0001);
    const hPct=Math.round(hv/tot*100);
    const f=fmt||(x=>x);
    return `<div class="ts-row">
      <span class="ts-h">${f(h)}</span>
      <span class="ts-lbl">${label}</span>
      <span class="ts-a">${f(a)}</span>
      <span class="ts-bar"><span class="ts-fill-h" style="width:${hPct}%"></span><span class="ts-fill-a" style="width:${100-hPct}%"></span></span>
    </div>`;
  };
  const p=x=>x==null?"—":(x<=1?Math.round(x*100)+"%":x);   // pass_pct en %
  const rows=[
    bar("Possession", ts.home_possession, ts.away_possession, x=>x==null?"—":x+"%"),
    bar("Passes", ts.home_passes, ts.away_passes),
    bar("Passes réussies", ts.home_passes_ok, ts.away_passes_ok),
    bar("% passes", ts.home_pass_pct, ts.away_pass_pct, p),
    bar("Centres (réussis)", ts.home_crosses, ts.away_crosses),
    bar("Longs ballons", ts.home_long_balls, ts.away_long_balls),
    bar("Tacles (gagnés)", ts.home_tackles, ts.away_tackles),
    bar("Interceptions", ts.home_interceptions, ts.away_interceptions),
    bar("Dégagements", ts.home_clearances, ts.away_clearances),
    bar("Tirs bloqués", ts.home_blocked_shots, ts.away_blocked_shots),
    bar("Fautes", ts.home_fouls, ts.away_fouls),
    bar("Hors-jeu", ts.home_offsides, ts.away_offsides),
    bar("Arrêts gardien", ts.home_saves, ts.away_saves),
  ].filter(Boolean).join("");
  return `<div class="module mod-teamstats"><h3>📊 Statistiques d'équipe complètes <span class="mod-hint">données réelles ESPN/Opta</span></h3>
    <div class="ts-head"><span>${m.home}</span><span></span><span>${m.away}</span></div>
    ${rows}</div>`;
}

/* match EN COURS : score live + prono d'avant en repère */
function renderLive(m){
  const p=m.prediction;
  const cm = clockMinute(m);   // minute estimée (repli)
  const realMin = m.liveClock || (cm?cm.label:"");          // vraie minute ESPN en priorité
  const src = m.liveClock ? "ESPN en direct" : (cm?"horloge":"en direct");
  const clk = realMin?` · ⏱️ <b>${realMin}</b> <span style="opacity:.8">(${src})</span>`:"";
  return `<div class="card">
    <div class="banner live">🔴 Match EN COURS ${m.liveScore?("— score actuel <b>"+m.liveScore+"</b>"):""}${clk} — suivi en direct.</div>
    <div class="scoreline anim-block anim-1">
      <div class="tn">${m.home}</div>
      <div class="sc live-c">${(m.liveScore||"–").replace("-"," – ")}<small>${realMin?realMin+" ("+src+")":"en direct"}</small></div>
      <div class="tn">${m.away}</div>
    </div>
    ${probBlock(m,p)}
    <div class="verdict anim-block anim-5">Pronostic d'avant-match (repère). Élo ${m.homeElo} vs ${m.awayElo}.</div>
    <div id="live-timeline-container"></div>
    ${srcTags(m)}
  </div>`;
}

/* match À VENIR : pronostic complet.
   mode : undefined = à venir | "kickoff" = coup d'envoi atteint | "awaiting" = résultat en attente */
function renderUpcoming(m, mode){
  const p=m.prediction;
  const conf = m.confidence!=null ? `${Math.round(m.confidence*100)}% (${m.confidence>=.8?"élevée":m.confidence>=.4?"moyenne":"faible — prior"})` : "—";
  let best="p1",bp=p.p1,bl=m.home;
  if(p.pX>bp){best="pX";bp=p.pX;bl="le nul";}
  if(p.p2>bp){bp=p.p2;bl=m.away;}
  let banner;
  if(mode==="kickoff")
    banner = `<div class="banner live">🟢 COUP D'ENVOI atteint — le suivi en direct n'est pas encore disponible. Le score réel apparaîtra au prochain rafraîchissement. Ci-dessous : le pronostic d'avant-match.</div>`;
  else if(mode==="awaiting")
    banner = `<div class="banner done">⌛ Match probablement TERMINÉ (selon l'horloge) — le résultat réel n'est pas encore intégré. Il apparaîtra au prochain rafraîchissement. Ci-dessous : le pronostic d'avant-match.</div>`;
  else
    banner = `<div class="banner soon">⏳ Match À VENIR — coup d'envoi ${countdown(m)} ${m.date?("("+m.date.slice(0,16)+")"):""}. Pronostic du modèle :</div>`;
  return `<div class="card">
    ${banner}
    <div class="scoreline anim-block anim-1">
      <div class="tn">${m.home}</div>
      <div class="sc">${p.topScore[0]} – ${p.topScore[1]}<small>${scoreNote(p)}</small></div>
      <div class="tn">${m.away}</div>
    </div>
    ${coherenceHint(m,p)}
    ${probBlock(m,p)}
    <div class="verdict anim-block anim-5">Le modèle favorise <b>${bl}</b> (${pct(bp)}).
      Tendance ${p.over25>0.5?"<b>Over 2.5</b>":"<b>Under 2.5</b>"} (${pct(p.over25)}),
      BTTS ${p.btts>0.5?"probable":"peu probable"} (${pct(p.btts)}).</div>
    ${srcTags(m)}
  </div>`;
}

/* bloc commun : barres 1N2 + marchés */
/* forme W/D/L en pastilles colorées (le plus récent à gauche) */
function formBadge(str){
  if(!str) return `<span style="color:var(--muted);font-size:11px">forme N/D</span>`;
  const col=r=> r==="W"?"#33e0a0": r==="D"?"#ffd34e":"#ff6b7d";
  return str.split("").map(r=>`<span style="display:inline-block;width:18px;height:18px;line-height:18px;
    text-align:center;border-radius:5px;font-size:10px;font-weight:700;color:#0b1020;
    background:${col(r)};margin-right:3px">${r}</span>`).join("");
}
function formCell(form5, det){
  if(form5) return `${formBadge(form5)} <span style="color:var(--muted);font-size:11px">(${det.pts5}pts · ${det.gf_avg}⚽/${det.ga_avg})</span>`;
  if(det) return `<span style="color:var(--muted);font-size:11.5px">indice ${Math.round(det.form_index*100)}% · <i>estimée (FIFA)</i></span>`;
  return `<span style="color:var(--muted);font-size:11px">N/D</span>`;
}
function formRow(m){
  if(!m.homeFormDetail && !m.awayFormDetail) return "";
  return `<div style="margin:6px 0 10px">
    <h3>📈 Forme (5 derniers, le + récent à gauche)</h3>
    <div class="stat"><span>${m.home}</span><span>${formCell(m.homeForm5, m.homeFormDetail)}</span></div>
    <div class="stat"><span>${m.away}</span><span>${formCell(m.awayForm5, m.awayFormDetail)}</span></div>
  </div>`;
}

/* intelligence contextuelle : enjeu (MWI), confiance (métacognition), Kelly, trap */
/* indice de surprise — facteurs au-delà des maths */







function probBlock(m,p){
  const accordion = (title, content, delay, icon, open=false) => {
    if (!content || content.trim() === '') return '';
    return `<details class="anim-block anim-${delay}" ${open ? 'open' : ''}><summary>${icon} ${title}</summary><div style="padding-top:10px">${content}</div></details>`;
  };
  
  const marketsHtml = [marketsBlock(m,p), shotsBlock(m,p), cornersBlock(m,p), cardsBlock(m,p)].filter(Boolean).join('');
  const scenHalftime = [halftimeBlock(m,p), scenariosBlock(m,p)].filter(Boolean).join('');
  const contextHtml = [h2hBlock(m), contextBlock(m,p), oddsBlock(m,p)].filter(Boolean).join('');
  const propsHtml = playerPropsBlock(m,p) || '';
  
  return `${formRow(m)}
    <div class="anim-block anim-1" style="display:flex;flex-direction:column;gap:16px;margin-bottom:16px;">
      <div>
        <h3 style="margin-bottom:12px;color:#cfe0ff">Issue du match</h3>
        <div class="probbar anim-block anim-2"><div class="lbl"><span>Victoire <b>${m.home}</b></span><b>${pct(p.p1)}</b></div><div class="track"><div class="b1" style="width:${p.p1*100}%"></div></div></div>
        <div class="probbar anim-block anim-3"><div class="lbl"><span>Match nul</span><b>${pct(p.pX)}</b></div><div class="track"><div class="bx" style="width:${p.pX*100}%"></div></div></div>
        <div class="probbar anim-block anim-4"><div class="lbl"><span>Victoire <b>${m.away}</b></span><b>${pct(p.p2)}</b></div><div class="track"><div class="b2" style="width:${p.p2*100}%"></div></div></div>
      </div>
      <div class="anim-block anim-5">
        <h3 style="margin-bottom:8px;color:#cfe0ff">Buts & BTTS</h3>
        ${ouBlock(m,p)}
        ${bttsBlock(p)}
      </div>
    </div>
    ${accordion('Détails des Marchés (Corners, Cartons, Tirs)', marketsHtml, 6, '📋')}
    ${accordion('Scénarios & Mi-Temps', scenHalftime, 7, '🎯')}
    ${accordion('Pronostics Joueurs', propsHtml, 8, '👤')}
    ${accordion('Contexte & Historique', contextHtml, 9, '📊')}
  `;
}

/* ===== HEAD-TO-HEAD (confrontations directes réelles ESPN) ===== */


/* ===== COTES réelles + VALUE + KELLY (données ESPN/DraftKings) ===== */


/* Buts : total xG projeté + Over/Under multi-lignes (1.5 / 2.5 / 3.5).
   Tout dérivé de la grille Dixon-Coles réelle. */


/* BTTS (les deux marquent) Oui/Non + niveau de confiance (métacognition + netteté du marché) */


/* libellé du score : sa vraie probabilité (souvent ~12-15%, pas une certitude !) */
function scoreNote(p){
  const ts=(p.topScores&&p.topScores[0]);
  if(ts) return `score le + probable (${pct(ts.p)})`;
  return "score le plus probable";
}

/* note de cohérence : explique le « favori mais score nul » et signale les conflits.
   Répond à la critique : un favori à 40% peut avoir un nul comme score modal. */
function coherenceHint(m,p){
  const hints=[];
  // 1) favori clair vs score modal = nul
  const fav = p.p1>=p.p2 ? {n:m.home,prob:p.p1} : {n:m.away,prob:p.p2};
  const modalIsDraw = p.topScore[0]===p.topScore[1];
  if(modalIsDraw && fav.prob>Math.max(p.pX,0)){
    hints.push(`<b>${fav.n}</b> est favori (${pct(fav.prob)}) mais le score <b>unique</b> le plus probable est un nul : normal, la victoire du favori se répartit sur de nombreux scores (2-1, 2-0, 3-1…), alors que le nul se concentre. Le marché 1N2 reste le repère, pas le score exact.`);
  }
  // 2) cohérence BTTS vs score modal (le bug que tu as repéré)
  const modalBTTS = p.topScore[0]>0 && p.topScore[1]>0;
  if(modalBTTS && p.btts<0.5){
    hints.push(`⚠️ Le score modal (${p.topScore[0]}-${p.topScore[1]}) implique que les deux marquent, alors que BTTS &lt; 50% : zone d'incertitude, à lire comme « indécis » plutôt que « non ».`);
  }
  if(!hints.length) return "";
  return `<div class="coh-note">💡 ${hints.join("<br>")}</div>`;
}

/* Score à la mi-temps probable (ratio structurel CDM ~42%, sourcé & étiqueté) */


/* Marchés dérivés : Double Chance, Draw No Bet, top-3 scores exacts.
   100% calculés sur la grille Dixon-Coles (aucune cote, aucune donnée externe). */


/* Scénarios narratifs : 4 catégories dérivées de la grille de scores réelle.
   Aucun timing/historique inventé — chaque % vient de la somme des cases de la grille. */


/* helper : barre Over/Under générique (réutilisée par corners & cartons) */


/* bloc bio (forces/faiblesses) — données réelles sourcées, sinon rien */


/* ===== MODULE PRONOS JOUEURS (6 rôles, en probabilités) ===== */

/* ===== BUTEURS : pronostiqués (modèle) vs réels (match joué) ===== */




function showLog(log){ const e=$("adminLog"); if(!e) return; if(log){e.classList.remove("u-hidden");e.textContent=log.slice(-4000);} else e.classList.add("u-hidden"); }

/* ===== MODULE TIRS (vue équipe) — données réelles, N/D si match à venir ===== */


/* ===== MODULE CORNERS (autonome) ===== */


/* ===== MODULE CARTONS (autonome — séparé des corners) ===== */


/* ---------- interactions ---------- */
$("tabs").querySelectorAll(".tab").forEach(tab=>{
  tab.onclick=()=>{
    $("tabs").querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
    tab.classList.add("active");
    setTab(tab.dataset.t); setGroup("Tous"); closeDetail();
    // le filtre par groupe n'a pas de sens dans "Meilleurs choix" / "Groupes"
    const gf=$("groupFilter"); if(gf) gf.style.display = (TAB==="BEST"||TAB==="GROUPS")?"none":"";
    buildGroupFilter(); render();
    closeSidebar();   // referme la sidebar sur mobile après sélection
  };
});
$("groupFilter").onchange=()=>{ GROUP=$("groupFilter").value; render(); };
$("search").oninput=render;

/* ===== Offcanvas (panneau d'analyse) : fermeture ===== */
$("ocClose").onclick=closeDetail;
$("ocBackdrop").onclick=closeDetail;
document.addEventListener("keydown",e=>{ if(e.key==="Escape") closeDetail(); });

/* ===== Sidebar mobile : ouverture/fermeture ===== */
function openSidebar(){ $("sidebar").classList.add("open"); $("sbBackdrop").classList.add("open"); }
function closeSidebar(){ $("sidebar").classList.remove("open"); $("sbBackdrop").classList.remove("open"); }
const _sbT=$("sbToggle"); if(_sbT) _sbT.onclick=openSidebar;
const _sbB=$("sbBackdrop"); if(_sbB) _sbB.onclick=closeSidebar;

/* HORLOGE : tick chaque seconde -> compte à rebours, minute live, bascule auto des onglets.
   Re-rend la liste seulement si un statut effectif a changé (évite de casser le scroll). */
let _clockSig = "";
(function clockTick(){
  setInterval(()=>{
    if(!MATCHES.length) return;
    // signature des statuts effectifs : si elle change, un match a basculé d'onglet
    const sig = MATCHES.map(effectiveStatus).join("");
    updateCounts();
    // horloge globale + prochain coup d'envoi
    const hc=$("hClock"); if(hc) hc.textContent = new Date().toLocaleTimeString("fr-FR");
    const nk=$("nextKO");
    if(nk){
      const upcoming = MATCHES.filter(m=>effectiveStatus(m)==="SCHEDULED" && parseKickoff(m.date)!=null)
                              .sort((a,b)=>parseKickoff(a.date)-parseKickoff(b.date))[0];
      const liveNow = MATCHES.filter(m=>{const s=effectiveStatus(m);return s==="LIVE"||s==="HT"||s==="KICKOFF";});
      if(liveNow.length) nk.innerHTML = `<b style="color:#ff8a96">${liveNow.length} en cours</b>`;
      else if(upcoming) nk.textContent = `coup d'envoi ${countdown(upcoming)}`;
      else nk.textContent = "";
    }
    if(sig!==_clockSig){ _clockSig = sig; buildGroupFilter(); render(); }
    else if(TAB==="SCHEDULED" || TAB==="LIVE"){
      // rafraîchit les badges (compte à rebours / minute live) sans casser le scroll
      render();
    }
  }, 1000);
})();

/* auto-reload intelligent : 20s s'il y a du live (horloge), 5 min sinon */
(function smartReload(){
  // recharge plus vite quand un match est en cours OU vient de démarrer / attend son résultat
  const hasLive = MATCHES.some(m=>{const s=effectiveStatus(m);return s==="LIVE"||s==="HT"||s==="KICKOFF"||s==="AWAITING";});
  setTimeout(async ()=>{
    await load();
    if(SELECTED){
      const m=MATCHES.find(x=>x.home+"|"+x.away===SELECTED);
      if(m) showDetail(m);
    }
    smartReload();
  }, hasLive?20000:300000);
})();

/* ===== PANNEAU D'ACTIONS (boutons) ===== */
let SERVER_OK = false;
async function checkServer(){
  try{ const r=await fetch("api/status",{cache:"no-store"});
    if(r.ok){ SERVER_OK=true; return await r.json(); } }catch(_){}
  SERVER_OK=false; return null;
}
function fillAdminMatches(){
  const sel=$("adminMatch"); if(!sel) return;
  // matchs pertinents : à venir / en cours / déjà commencés
  const opts = MATCHES.map(m=>`<option value="${m.home}|${m.away}">${m.home} – ${m.away} (${(m.date||"").slice(5,16)})</option>`).join("");
  sel.innerHTML = opts;
}
function setAdminStatus(txt){ const e=$("adminStatus"); if(e) e.textContent=txt; }


async function adminAction(act){
  if(!SERVER_OK){
    // mode hors-serveur : on ne peut pas exécuter Python -> on guide l'utilisateur
    // Windows : python | Linux/Mac : python3
    const py = navigator.platform.startsWith("Win") ? "python" : "python3";
    const cmds={refresh:`${py} -m collector.refresh`,
      predict:`${py} -m collector.pipeline predict && ${py} -m collector.embed`,
      sync:`${py} -m collector.live --sync && ${py} -m collector.refresh`};
    const c=cmds[act]||`${py} -m collector.refresh`;
    setAdminStatus("⚠️ Serveur non détecté — lance l'app via le serveur de contrôle.");
    $("adminHint").innerHTML = `Pour activer les boutons, lance : <code>${py} -m collector.server</code> puis ouvre <code>http://localhost:8077/index.html</code>.<br>Ou exécute directement : <code>${c}</code>`;
    return;
  }
  const btns=document.querySelectorAll(".abtn"); btns.forEach(b=>b.disabled=true);
  setAdminStatus("⏳ Exécution en cours… (peut prendre quelques secondes)");
  let body={};
  let route="api/"+act;
  if(act==="setscore"){
    const v=$("adminMatch").value.split("|");
    body={home:v[0],away:v[1],hg:+$("adminHg").value||0,ag:+$("adminAg").value||0,state:$("adminState").value};
  }
  try{
    const r=await fetch(route,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const j=await r.json();
    setAdminStatus(j.ok?"✅ Terminé. Données réactualisées.":"❌ Erreur (voir le log).");
    showLog(j.log);
    await load();           // recharge les nouvelles données dans l'app
    fillAdminMatches();
  }catch(e){ setAdminStatus("❌ Échec : "+e); }
  finally{ btns.forEach(b=>b.disabled=false); }
}

$("toggleAdmin").onclick=async ()=>{
  const p=$("adminPanel");
  const show = p.classList.contains("u-hidden");
  if(show) p.classList.remove("u-hidden"); else p.classList.add("u-hidden");
  if(show){
    fillAdminMatches();
    const st=await checkServer();
    if(st) setAdminStatus(`🎛️ Serveur connecté · ${st.finished} terminés / ${st.live} en cours / ${st.scheduled} à venir`);
    else { setAdminStatus("⚠️ Serveur non détecté (boutons en mode lecture seule).");
      const py2 = navigator.platform.startsWith("Win") ? "python" : "python3";
      $("adminHint").innerHTML = `Lance <code>${py2} -m collector.server</code> puis ouvre <code>http://localhost:8077/index.html</code> pour activer les boutons.`; }
  }
};
document.querySelectorAll(".abtn").forEach(b=> b.onclick=()=>adminAction(b.dataset.act));

load();
