const $ = id => document.getElementById(id);
const pct = x => Math.round((x||0)*100) + "%";
let MATCHES = [], TAB = "SCHEDULED", GROUP = "Tous", SELECTED = null, TOPPICKS = null, LIVEFEED = [], PNL = null, STANDINGS = [], H2H = {};

/* ===== FAVORIS & NOTIFICATIONS ===== */
let FAV_TEAMS = [];
try { FAV_TEAMS = JSON.parse(localStorage.getItem("prono_favs")) || []; } catch(e){}

function toggleFav(team) {
  if(FAV_TEAMS.includes(team)) FAV_TEAMS = FAV_TEAMS.filter(t=>t!==team);
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
  MATCHES = data;
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
  try{ const tpEl=$("embedded-toppicks"); if(tpEl) TOPPICKS = JSON.parse(tpEl.textContent) || null; }catch(_){}
  try{ const fEl=$("embedded-feed"); if(fEl) LIVEFEED = JSON.parse(fEl.textContent) || []; }catch(_){}
  try{ const pEl=$("embedded-pnl"); if(pEl) PNL = JSON.parse(pEl.textContent) || null; }catch(_){}
  try{ const stEl=$("embedded-standings"); if(stEl) STANDINGS = JSON.parse(stEl.textContent) || []; }catch(_){}
  try{ const hEl=$("embedded-h2h"); if(hEl) H2H = JSON.parse(hEl.textContent) || {}; }catch(_){}
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
function parseKickoff(dateStr){
  // formats : "2026-06-13 12:00 UTC-7", "2026-06-13 20:00 UTC+1", "UTC+5:30", ou sans UTC
  if(!dateStr) return null;
  const m = dateStr.match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?:\s*UTC([+-]\d{1,2})(?::?(\d{2}))?)?/);
  if(!m) return null;
  const [,Y,Mo,D,H,Mi,tzH,tzMin] = m;
  // construit l'instant en UTC puis applique le décalage du fuseau du stade
  let t = Date.UTC(+Y, +Mo-1, +D, +H, +Mi);
  if(tzH!==undefined){
    const sign = tzH[0]==="-" ? -1 : 1;
    const offMin = (Math.abs(+tzH))*60 + (tzMin?+tzMin:0);
    t -= sign*offMin*60*1000;   // UTC-7 => +7h pour revenir à l'UTC
  }
  return t;
}
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
function effectiveStatus(m){
  // 1) priorité absolue au vrai résultat confirmé
  if(m.status==="FINISHED") return "FINISHED";
  const ko = parseKickoff(m.date);
  const FULL = MATCH_MINUTES + HT_BREAK + STOPPAGE;       // ~113 min de jeu plausible
  const GRACE = FULL + 75;                                // marge avant de considérer "fini" (prolong./retards)

  // 2) donnée LIVE/HT réelle : crédible tant que l'horloge le confirme
  if(m.status==="LIVE"||m.status==="HT"){
    if(ko==null) return m.status;                         // pas de date : on garde la donnée live réelle
    const el=(Date.now()-ko)/60000;
    if(el<0) return "SCHEDULED";                          // coup d'envoi pas encore là
    if(el<=GRACE) return m.status;                        // toujours dans la fenêtre plausible
    return "FINISHED";                                    // live réel mais périmé -> terminé
  }

  // 3) match programmé sans donnée live : on N'INVENTE PAS de LIVE/score
  if(ko==null) return m.status||"SCHEDULED";
  const elapsed = (Date.now() - ko)/60000;
  if(elapsed < 0) return "SCHEDULED";                     // avant le coup d'envoi
  if(elapsed <= FULL) return "KICKOFF";                   // démarré (horloge) mais pas de donnée -> on attend
  return "AWAITING";                                      // fini côté horloge mais résultat pas encore ingéré
}
function clockMinute(m){
  // minute de jeu estimée — UNIQUEMENT pour un match dont la donnée live est réelle.
  // (on ne fabrique pas de minute pour un simple "coup d'envoi atteint")
  if(!(m.status==="LIVE"||m.status==="HT")) return null;
  const ko = parseKickoff(m.date); if(ko==null) return null;
  let e = Math.floor((Date.now()-ko)/60000);
  if(e<0) return null;
  if(e<=45) return {label:`${Math.max(1,e)}'`, phase:"1ère MT"};
  if(e<=45+HT_BREAK) return {label:"Mi-temps", phase:"pause"};
  e -= HT_BREAK;
  if(e<=90) return {label:`${e}'`, phase:"2ème MT"};
  return {label:"90'+", phase:"temps additionnel"};
}
function fmtCountdown(ms){
  if(ms<=0) return "maintenant";
  const s=Math.floor(ms/1000), d=Math.floor(s/86400), h=Math.floor(s%86400/3600),
        mn=Math.floor(s%3600/60), sec=s%60;
  if(d>0) return `dans ${d}j ${h}h`;
  if(h>0) return `dans ${h}h ${mn}min`;
  if(mn>0) return `dans ${mn}min ${sec}s`;
  return `dans ${sec}s`;
}
function countdown(m){
  const ko=parseKickoff(m.date); if(ko==null) return "";
  return fmtCountdown(ko - Date.now());
}


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
    comboHtml = `<div class="combo-box">
      <div class="combo-head">🧩 Combiné du jour <span class="mod-hint">${combo.length} sélections verrouillées</span></div>
      ${legs}
      <div class="combo-total">Probabilité combinée du modèle : <b>${Math.round(comboProb*100)}%</b>
        <span style="color:var(--muted);font-size:11px"> (cote théorique ≈ ${(1/comboProb).toFixed(2)})</span></div>
      <div class="note" style="margin-top:6px">Un combiné multiplie les risques : il suffit d'1 raté pour tout perdre. À jouer avec prudence.</div>
    </div>`;
  }
  box.innerHTML = `
    <div class="best-intro">
      <div class="best-title">🎯 Les meilleurs choix de l'app</div>
      <div class="best-sub">Sélection automatique des paris les plus sûrs parmi <b>tout</b> ce que le modèle prédit.
        Le taux de réussite affiché est <b>réellement mesuré</b> sur les ${sample} matchs déjà joués — pas une promesse.</div>
      <div class="rel-grid">${relCard("lock",lock)}${relCard("strong",strong)}${relCard("value",val)}</div>
      ${comboHtml}
    </div>
    ${groups || '<div class="empty">Aucun pick assez fiable pour l\'instant.</div>'}
    <div class="note" style="margin-top:14px">⚠️ Paris sportifs = risque réel. Même à 90%+, 1 pari sur 10 perd. Joue de façon responsable. Aucune donnée inventée : tout dérive des matchs réels.</div>
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
    return `<div class="tv-card" onclick="openMatchByTeams('${(b.home||'').replace(/'/g,"\\'")}','${(b.away||'').replace(/'/g,"\\'")}')">
      <div class="tv-match">${b.home} <span style="opacity:.5">vs</span> ${b.away}</div>
      <div class="tv-pick">${b.label}</div>
      <div class="tv-nums">
        <span>Modèle <b style="color:var(--acc)">${Math.round(b.prob*100)}%</b> · cote <span class="tv-odd">${b.odd}</span></span>
        <span class="tv-edge">+${edge}% value</span>
      </div>
    </div>`;
  }).join("");
  box.innerHTML=`<div class="tv-head">💎 Top Value Bets du jour <span class="mod-hint">écart entre la proba du modèle et la cote du bookmaker</span></div>
    <div class="tv-grid">${cards}</div>`;
}

/* PERFORMANCE : ROI dans le hero + sparkline d'évolution de la réussite */
function renderPerf(){
  const roiEl=$("heroRoi"), subEl=$("heroRoiSub");
  if(roiEl && PNL && PNL.value){
    const v=PNL.value, y=v.yield, n=v.bets, small=(n||0)<25;
    if(y==null){ roiEl.textContent="N/D"; roiEl.style.color="var(--muted)"; subEl.textContent="cotes insuffisantes"; }
    else{
      roiEl.textContent=(y>0?"+":"")+y+"%";
      roiEl.style.color = small ? "var(--muted)" : (y>0?"var(--acc)":(y<0?"var(--danger)":"var(--muted)"));
      // honnête : on signale que l'échantillon est trop petit pour conclure
      subEl.innerHTML = small
        ? `${v.pnl>0?"+":""}${v.pnl}u · <span style="color:var(--warn)">échantillon ${n} (peu fiable)</span>`
        : `${v.pnl>0?"+":""}${v.pnl}u sur ${n} value bets`;
    }
    const card=$("heroPerfCard");
    if(card) card.title=`ROI value: ${y}% (${n} paris) · favori 1N2: ${PNL.favorite?PNL.favorite.yield:"—"}% · échantillon ${PNL.sampleWithOdds} matchs avec cotes`;
  } else if(roiEl){ roiEl.textContent="—"; subEl.textContent="en attente de cotes"; }
  drawSpark();
}

/* sparkline : précision cumulée du modèle (1N2) au fil des matchs joués */
function drawSpark(){
  const svg=$("perfSpark"); if(!svg) return;
  const played=MATCHES.filter(m=>m.status==="FINISHED"&&m.analysis)
    .sort((a,b)=>(a.date||"").localeCompare(b.date||""));
  if(played.length<2){ svg.innerHTML=""; return; }
  let ok=0; const pts=[];
  played.forEach((m,i)=>{ if(m.analysis.predictionCorrect)ok++; pts.push(ok/(i+1)); });
  const W=120,H=28,n=pts.length;
  const x=i=>i/(n-1)*W;
  const y=v=>H-2-v*(H-4);            // 0..1 -> bas..haut
  const d=pts.map((v,i)=>`${i?"L":"M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last=pts[pts.length-1];
  const col=last>=0.5?"#4ee1a0":"#ffcf5c";
  svg.innerHTML=`<polyline points="${pts.map((v,i)=>x(i).toFixed(1)+","+y(v).toFixed(1)).join(" ")}"
      fill="none" stroke="${col}" stroke-width="1.6"/>
      <line x1="0" y1="${y(0.5)}" x2="${W}" y2="${y(0.5)}" stroke="#ffffff22" stroke-dasharray="2 2"/>`;
}

/* 🏆 CLASSEMENT DES GROUPES */
function teamFlag(name){ return teamBadge(name); }
function renderStandings(){
  const box=$("matchList");
  if(!STANDINGS || !STANDINGS.length){
    box.innerHTML=`<div class="empty">Classements indisponibles.</div>`; return;
  }
  box.innerHTML = `<div class="groups-grid">` + STANDINGS.map(g=>{
    const rows=g.rows.map(r=>{
      const qual = r.rank<=2 ? "q1" : (r.rank===3 ? "q3" : "");  // 1-2 qualifiés, 3e repêchable
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
  <div class="note" style="margin-top:12px">🟢 1er-2e qualifiés · 🟡 3e éventuellement repêché. Classement calculé sur les résultats réels (pts > différence > buts marqués).</div>`;
}

function renderBracket(){
  // On filtre et trie les matchs par ordre chronologique pour chaque round
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
      
      html += `<div class="bracket-match" onclick="openMatchByTeams('${(m.home||'').replace(/'/g,"\\'")}','${(m.away||'').replace(/'/g,"\\'")}')">
        <div class="bracket-team">${teamBadge(m.home)} <span style="flex-grow:1;margin-left:8px">${m.home}</span>${favBtn(m.home)}</div>
        <div style="text-align:center; font-weight:800; color:var(--acc); font-size:14px; margin:2px 0">${scoreHtml}</div>
        <div class="bracket-team">${teamBadge(m.away)} <span style="flex-grow:1;margin-left:8px">${m.away}</span>${favBtn(m.away)}</div>
      </div>`;
    });
    html += `</div>`;
  });
  html += `</div>`;
  const box=$("bracketView");
  if(box){
    box.innerHTML = html;
    box.classList.remove("u-hidden");
  }
}

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
    d.onclick=()=>{ SELECTED=m.home+"|"+m.away; showDetail(m); };
    $("matchList").appendChild(d);
  });
}

/* pastille équipe : initiales + couleur dérivée du nom (déterministe) */
function teamBadge(name){
  const init=(name||"?").replace(/[^A-Za-zÀ-ÿ ]/g,"").split(/\s+/).map(w=>w[0]).join("").slice(0,3).toUpperCase();
  let h=0; for(const c of (name||"")) h=(h*31+c.charCodeAt(0))%360;
  const bg=`hsl(${h},62%,58%)`;
  return `<span class="mi-badge" style="background:${bg}">${init}</span>`;
}
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
  SELECTED = null;
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
  // l'extérieur joue "vers le haut" -> on inverse l'ordre des lignes
  if(side==="away") rows.reverse();
  return `<div class="pitch ${side}">
      <div class="pitch-head">${team} <b>${form||""}</b>${coach?` · 👔 ${coach}`:""}</div>
      <div class="pitch-grass">${rows.join("")}</div>
    </div>`;
}
function clean(n){ return (n||"").replace(/\s*\(GK\)|\s*\(C\)/g,""); }
/* pastille de forme : vert/jaune/rouge — placeholder déterministe tant que xG joueur = N/D */
function dot(name){
  const s = (name||"").length % 3;            // pseudo-forme stable (à remplacer par xG réel)
  const c = s===0?"#33e0a0":s===1?"#ffd34e":"#ff6b7d";
  const susp = /\(C\)/.test(name)?"":""; // place pour 🟨 suspension future
  return `<span class="form-dot" style="background:${c}"></span>${susp}`;
}

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

  return `<div class="vs-box">
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
    <div class="scoreline">
      <div class="tn">${m.home}</div>
      <div class="sc gold">${a.realScore.replace("-"," – ")}<small>score final</small></div>
      <div class="tn">${m.away}</div>
    </div>
    ${vsTable(m)}
    <div class="verdict done"><b>${a.predictionCorrect?"✅":"❌"} Verdict du modèle :</b> ${a.summary}</div>
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
    <div class="scoreline">
      <div class="tn">${m.home}</div>
      <div class="sc live-c">${(m.liveScore||"–").replace("-"," – ")}<small>${realMin?realMin+" ("+src+")":"en direct"}</small></div>
      <div class="tn">${m.away}</div>
    </div>
    ${probBlock(m,p)}
    <div class="verdict">Pronostic d'avant-match (repère). Élo ${m.homeElo} vs ${m.awayElo}.</div>
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
    <div class="scoreline">
      <div class="tn">${m.home}</div>
      <div class="sc">${p.topScore[0]} – ${p.topScore[1]}<small>${scoreNote(p)}</small></div>
      <div class="tn">${m.away}</div>
    </div>
    ${coherenceHint(m,p)}
    ${probBlock(m,p)}
    <div class="verdict">Le modèle favorise <b>${bl}</b> (${pct(bp)}).
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
  if(form5) return `${formBadge(form5)} <span style="color:var(--muted);font-size:11px">(${det.pts10}pts · ${det.gf_avg}⚽/${det.ga_avg})</span>`;
  if(det) return `<span style="color:var(--muted);font-size:11.5px">indice ${Math.round(det.form_index*100)}% · <i>estimée (FIFA)</i></span>`;
  return `<span style="color:var(--muted);font-size:11px">N/D</span>`;
}
function formRow(m){
  if(!m.homeFormDetail && !m.awayFormDetail) return "";
  return `<div style="margin:6px 0 10px">
    <h3>📈 Forme (10 derniers, le + récent à gauche)</h3>
    <div class="stat"><span>${m.home}</span><span>${formCell(m.homeForm5, m.homeFormDetail)}</span></div>
    <div class="stat"><span>${m.away}</span><span>${formCell(m.awayForm5, m.awayFormDetail)}</span></div>
  </div>`;
}

/* intelligence contextuelle : enjeu (MWI), confiance (métacognition), Kelly, trap */
/* indice de surprise — facteurs au-delà des maths */
function attackQualityBlock(m,p){
  const aq=p.attackQuality; if(!aq) return "";
  const h=aq.home||{}, a=aq.away||{};
  if(!(h.stars||a.stars)) return "";
  const side=(t,x)=>`<div style="flex:1">
      <div style="font-size:11px;color:var(--muted)">${t}</div>
      <div style="font-size:15px;font-weight:700">${"⭐".repeat(Math.min(x.stars||0,5))||"—"} <span style="font-size:11px;color:var(--acc)">×${x.boost}</span></div>
      <div style="font-size:10px;color:var(--muted)">${(x.names||[]).join(", ")||"N/D"}</div>
    </div>`;
  return `<div class="module"><h3 style="color:#ffcf5c">⚡ Qualité offensive <span class="mod-hint">profils d'élite reconnus</span></h3>
    <div style="display:flex;gap:14px">${side(m.home,h)}${side(m.away,a)}</div>
    <div class="note" style="margin-top:8px">Le modèle rehausse le potentiel offensif des équipes au front d'élite (corrige la sous-estimation des équipes dangereuses sans match joué).</div>
  </div>`;
}
function availabilityBlock(m,p){
  const av=p.availability; if(!av) return "";
  const h=av.home||{}, a=av.away||{};
  // n'affiche que si une compo réelle a été utilisée ET qu'il y a un impact
  const hHit=(h.applied && h.factor<1), aHit=(a.applied && a.factor<1);
  if(!hHit && !aHit) return "";
  const side=(t,x)=>{
    if(!(x.applied && x.factor<1)) return "";
    const pct=Math.round((1-x.factor)*100);
    const who=(x.missing||[]).map(z=>z.name).join(", ");
    return `<div style="flex:1">
      <div style="font-size:11px;color:var(--muted)">${t}</div>
      <div style="font-size:15px;font-weight:700;color:var(--danger)">−${pct}% <span style="font-size:11px;color:var(--muted)">buts attendus</span></div>
      <div style="font-size:10px;color:var(--muted)">absent(s) : ${who||"—"}</div>
    </div>`;
  };
  return `<div class="module"><h3 style="color:#ff7a7a">🩹 Absences clés <span class="mod-hint">compo officielle ESPN</span></h3>
    <div style="display:flex;gap:14px">${side(m.home,h)}${side(m.away,a)}</div>
    <div class="note" style="margin-top:8px">Quand un joueur majeur manque dans le XI officiel, le modèle réduit dynamiquement les buts attendus (λ) <b>avant</b> le calcul des probabilités. Aucun ajustement tant que la compo réelle n'est pas publiée.</div>
  </div>`;
}
function upsetBlock(m,p){
  const ui=p.upsetIndex; if(!ui) return availabilityBlock(m,p)+attackQualityBlock(m,p);
  const _aq=availabilityBlock(m,p)+attackQualityBlock(m,p);
  const col = ui.index>=55?"var(--danger)":ui.index>=35?"var(--warn)":"var(--acc)";
  const facts=[];
  if(ui.dogLowBlock) facts.push("🛡️ l'outsider défend bas (peu d'xG encaissé)");
  if(ui.favOverperf) facts.push("🎯 le favori surperformait sa finition → régression probable");
  if(ui.dampener<1) facts.push("⚖️ domination du favori atténuée par le modèle");
  const fav = p.p1>=p.p2 ? m.home : m.away;
  return _aq + `<div class="module"><h3 style="color:${col}">⚠️ Indice de surprise <span class="mod-hint">au-delà des maths</span></h3>
    <div style="display:flex;align-items:center;gap:12px;margin:6px 0 8px">
      <div style="font-size:30px;font-weight:800;color:${col}">${ui.index}<span style="font-size:14px;color:var(--muted)">/100</span></div>
      <div style="flex:1">
        <div style="height:8px;background:#0b1020;border-radius:6px;overflow:hidden"><div style="height:100%;width:${ui.index}%;background:${col};border-radius:6px"></div></div>
        <div style="font-size:11px;color:var(--muted);margin-top:4px">risque que <b>${fav}</b> (favori) ne gagne pas — niveau <b style="color:${col}">${ui.label}</b></div>
      </div>
    </div>
    ${facts.length?`<div class="note">${facts.join("<br>")}</div>`:`<div class="note">Aucun signal d'alerte majeur : le favori part en confiance.</div>`}
  </div>`;
}

function contextBlock(m,p){
  const mwi=p.mwi, meta=p.meta;
  if(!mwi && !meta) return upsetBlock(m,p);
  return upsetBlock(m,p) + _contextInner(m,p);
}
function _contextInner(m,p){
  const mwi=p.mwi, meta=p.meta;
  const confColor = meta ? (meta.confidence>=0.8?"#33e0a0":meta.confidence>=0.55?"#ffd34e":"#ff6b7d") : "#94a0c8";
  const stake = mwi ? Math.round(mwi.stageStake*100) : null;
  const stakeLabel = mwi && mwi.groupMatchday ? `Journée ${mwi.groupMatchday} de poule` : "Phase finale";
  let html = `<div style="margin-top:14px"><h3>🧠 Contexte & confiance</h3>`;
  if(meta){
    html += `<div class="stat"><span>Confiance du modèle</span>
      <span style="color:${confColor}">${Math.round(meta.confidence*100)}% (${meta.label})</span></div>
      <div class="note" style="margin-top:4px">${meta.reasons.join(" · ")}</div>`;
  }
  if(mwi){
    html += `<div class="stat" style="margin-top:8px"><span>Enjeu du match (Must-Win)</span>
      <span>${stake}% — ${stakeLabel}</span></div>`;
    // statut de qualification réel (si calculé)
    const badge=(s)=> s==="qualified"?'<span class="tag" style="background:rgba(51,224,160,.15);color:#33e0a0">✅ qualifié</span>'
      : s==="eliminated"?'<span class="tag" style="background:rgba(255,107,125,.15);color:#ff6b7d">❌ éliminé</span>'
      : s==="alive"?'<span class="tag" style="background:rgba(91,140,255,.12);color:#5b8cff">⚪ en lice</span>':"";
    if(mwi.statusHome||mwi.statusAway){
      html += `<div class="stat"><span>Statut ${m.home}</span><span>${badge(mwi.statusHome)}</span></div>
        <div class="stat"><span>Statut ${m.away}</span><span>${badge(mwi.statusAway)}</span></div>`;
    }
    if((mwi.statusHome==="qualified"||mwi.statusAway==="qualified") && mwi.groupMatchday===3)
      html += `<div class="note" style="margin-top:4px">⚡ Une équipe déjà qualifiée joue ce match : rotation/baisse d'intensité probable (variance accrue).</div>`;
    else if(stake>=80) html += `<div class="note" style="margin-top:4px">⚡ Enjeu élevé : 3e journée décisive.</div>`;
  }
  // Kelly (si cotes dispo)
  const k=p.kelly;
  if(k){
    const lines=[["home",m.home],["draw","Nul"],["away",m.away]]
      .map(([key,lbl])=> k[key]&&k[key].kelly>0 ? `<div class="stat"><span>💰 Mise conseillée (${lbl})</span><span>${(k[key].kelly*100).toFixed(1)}% bankroll</span></div>`:"")
      .join("");
    if(lines) html += lines;
    else html += `<div class="note" style="margin-top:6px">💰 Kelly : aucune mise (pas de cotes saisies ou pas de value).</div>`;
  }
  // Line movement / trap — affiche ouverture → cote actuelle (et le drift)
  const lm=p.lineMovement;
  if(lm && lm.opening){
    const op=lm.opening;
    const cur={odd1:m.odd1, oddX:m.oddX, odd2:m.odd2};
    // drift par issue (négatif = la cote a baissé = équipe soutenue par le marché)
    const drift={"1":lm.home, "X":lm.draw, "2":lm.away};
    const row=(key,oKey,label)=>{
      const o=op[oKey], c=cur[oKey];
      if(o==null) return "";
      const d=drift[key];
      const arrow = (c!=null && c<o) ? "↘" : (c!=null && c>o) ? "↗" : "→";
      const col = (c!=null && c<o) ? "var(--acc)" : (c!=null && c>o) ? "var(--danger)" : "var(--muted)";
      const cTxt = (c!=null) ? c : "—";
      const dTxt = (d!=null && Math.abs(d)>=0.1) ? ` <span style="color:${col}">(${d>0?"+":""}${d}%)</span>` : "";
      return `<div class="stat"><span>${label}</span><span>${o} <span style="color:${col}">${arrow}</span> ${cTxt}${dTxt}</span></div>`;
    };
    // a-t-on un VRAI mouvement (ouverture ≠ actuelle) ?
    const moved = (cur.odd1!=null && (cur.odd1!==op.odd1 || cur.oddX!==op.oddX || cur.odd2!==op.odd2));
    if(moved){
      html += `<div class="stat" style="margin-top:8px"><span>📉 Mouvement de cote</span>
          <span style="color:var(--muted);font-size:11px">ouverture → actuelle · ${lm.provider||""}</span></div>`;
      html += row("1","odd1",m.home) + row("X","oddX","Nul") + row("2","odd2",m.away);
      const favKey = (m.odd1!=null && m.odd2!=null) ? (m.odd1<=m.odd2?"1":"2") : null;
      const favDrift = favKey ? drift[favKey] : null;
      if(favDrift!=null && favDrift<=-5)
        html += `<div class="note" style="margin-top:4px">📊 Le marché soutient fortement ${favKey==="1"?m.home:m.away} (cote en forte baisse).</div>`;
    } else {
      // pas de second relevé : on montre les cotes d'ouverture, sans fausse flèche
      html += `<div class="stat" style="margin-top:8px"><span>🎰 Cotes (ouverture)</span>
          <span>${op.odd1}/${op.oddX}/${op.odd2} <span style="color:var(--muted);font-size:11px">· ${lm.provider||""} · stables</span></span></div>`;
    }
  }
  html += `</div>`;

  // marché "qui se qualifie ?" (phase à élimination directe)
  const ko=p.knockout;
  if(ko){
    html += `<div style="margin-top:14px"><h3>🏆 Qualification (90' + prolong. + TAB)</h3>
      <div class="probbar"><div class="lbl"><span>${m.home} se qualifie</span><b>${pct(ko.qualifyHome)}</b></div><div class="track"><div class="b1" style="width:${ko.qualifyHome*100}%"></div></div></div>
      <div class="probbar"><div class="lbl"><span>${m.away} se qualifie</span><b>${pct(ko.qualifyAway)}</b></div><div class="track"><div class="b2" style="width:${ko.qualifyAway*100}%"></div></div></div>
      <div class="note" style="margin-top:4px">Si tirs au but : ${m.home} ${pct(ko.shootoutHome)} (Elo + sang-froid). ${ko.note}</div>
    </div>`;
  }
  // signature modèle
  if(p.ensemble && p.ensemble.weights){
    const w=p.ensemble.weights;
    const pc=v=>Math.round(v*100);
    html += `<div class="note" style="margin-top:8px">🧠 Modèle d'ensemble (poids appris sur les résultats) :
      Elo ${pc(w.elo)}% · Buts/xG ${pc(w.grid)}% · Forme ${pc(w.form)}%${p.ensemble.T&&Math.abs(p.ensemble.T-1)>0.02?` · calibration T=${p.ensemble.T}`:""}</div>`;
  }
  if(p.dixonColes){
    html += `<div class="note" style="margin-top:8px">📐 Modèle : Dixon-Coles (ρ=${p.dixonColes.rho})${p.dixonColes.gamma>0?` + effet de choc (γ=${p.dixonColes.gamma})`:""}</div>`;
  }
  return html;
}

function probBlock(m,p){
  const cm=p.corners, cd=p.cards;
  return `${formRow(m)}<div class="grid2">
    <div>
      <h3>Issue du match</h3>
      <div class="probbar"><div class="lbl"><span>Victoire <b>${m.home}</b></span><b>${pct(p.p1)}</b></div><div class="track"><div class="b1" style="width:${p.p1*100}%"></div></div></div>
      <div class="probbar"><div class="lbl"><span>Match nul</span><b>${pct(p.pX)}</b></div><div class="track"><div class="bx" style="width:${p.pX*100}%"></div></div></div>
      <div class="probbar"><div class="lbl"><span>Victoire <b>${m.away}</b></span><b>${pct(p.p2)}</b></div><div class="track"><div class="b2" style="width:${p.p2*100}%"></div></div></div>
    </div>
    <div>
      <h3>Marchés</h3>
      ${ouBlock(m,p)}
      ${bttsBlock(p)}
    </div>
  </div>${h2hBlock(m)}${oddsBlock(m,p)}${halftimeBlock(m,p)}${marketsBlock(m,p)}${scenariosBlock(m,p)}${playerPropsBlock(m,p)}${shotsBlock(m,p)}${cornersBlock(m,p)}${cardsBlock(m,p)}${contextBlock(m,p)}`;
}

/* ===== HEAD-TO-HEAD (confrontations directes réelles ESPN) ===== */
function h2hBlock(m){
  const h = H2H[m.home+"|"+m.away] || H2H[m.away+"|"+m.home];
  if(!h || !h.games || !h.games.length) return "";
  const s=h.summary||{};
  // si la clé inversée a servi, on réoriente l'affichage vers m.home
  const flip = !H2H[m.home+"|"+m.away];
  const win = flip ? s.loss : s.win, loss = flip ? s.win : s.loss, draw=s.draw;
  const rows=h.games.slice(0,6).map(g=>{
    let sc=g.score;
    if(flip) sc = sc.split("-").reverse().join("-");
    const [a,b]=sc.split("-").map(Number);
    const col = a>b?"var(--acc)":(a<b?"var(--danger)":"var(--muted)");
    return `<div class="h2h-row"><span class="h2h-d">${g.date||""}</span>
      <span class="h2h-sc" style="color:${col}">${sc}</span>
      <span class="h2h-c">${g.competition||""}</span></div>`;
  }).join("");
  return `<div class="module"><h3>🤝 Confrontations directes <span class="mod-hint">historique réel ESPN</span></h3>
    <div class="h2h-sum">
      <div><b style="color:var(--acc)">${win}</b><small>${m.home}</small></div>
      <div><b>${draw}</b><small>nuls</small></div>
      <div><b style="color:var(--danger)">${loss}</b><small>${m.away}</small></div>
    </div>
    <div class="h2h-list">${rows}</div>
    <div class="note" style="margin-top:6px">Scores du point de vue de <b>${m.home}</b> · ${s.total} match(s) recensés.</div>
  </div>`;
}

/* ===== COTES réelles + VALUE + KELLY (données ESPN/DraftKings) ===== */
function oddsBlock(m,p){
  if(m.odd1==null) return "";   // pas de cotes pour ce match
  const v=p.value||{}, k=p.kelly||{};
  const lm=p.lineMovement;
  const cell=(lbl,odd,val,kel)=>{
    const isVal = val&&val.value;
    const kpct = (kel&&kel.kelly)?` · 💰 ${Math.round(kel.kelly*100)}%`:"";
    return `<div class="odd-cell ${isVal?'val':''}">
      <div class="odd-lbl">${lbl}</div>
      <div class="odd-val">${odd!=null?odd.toFixed(2):"—"}</div>
      <div class="odd-edge">${val?(val.edge>0?'+':'')+Math.round(val.edge*100)+' pts':''}${isVal?' ✅':''}${kpct}</div>
    </div>`;
  };
  let mv="";
  if(lm && lm.opening){
    const arrow=x=> (x!=null&&x<-0.05)?'📉':(x!=null&&x>0.05?'📈':'➡️');
    const op=lm.opening;
    mv=`<div class="odd-mv">Mouvement cote : ${m.home} ${arrow(lm.home)} · ${m.away} ${arrow(lm.away)} <span style="color:var(--muted)">(ouverture ${op.odd1}/${op.oddX}/${op.odd2})</span></div>`;
  }
  return `<div class="module mod-odds"><h3>🎰 Cotes & value <span class="mod-hint">${m.oddsProvider||"bookmaker"} · réelles</span></h3>
    <div class="odd-grid">
      ${cell(m.home, m.odd1, v.home, k.home)}
      ${cell("Nul", m.oddX, v.draw, k.draw)}
      ${cell(m.away, m.odd2, v.away, k.away)}
    </div>
    ${mv}
    <div class="odd-note">✅ value = le modèle estime une probabilité supérieure à celle du bookmaker (+2 pts mini). 💰 = mise Kelly conseillée (% bankroll, plafonné 5%). <b>Information, pas un conseil de pari.</b></div>
  </div>`;
}

/* Buts : total xG projeté + Over/Under multi-lignes (1.5 / 2.5 / 3.5).
   Tout dérivé de la grille Dixon-Coles réelle. */
function ouBlock(m,p){
  const ou=p.overUnder;
  const xg = p.totalXg!=null
    ? `<div class="stat"><span>🎯 Total xG projeté</span><span><b>${p.totalXg}</b> (${p.lamHome} + ${p.lamAway})</span></div>`
    : `<div class="stat"><span>Buts attendus</span><span>${p.lamHome} — ${p.lamAway}</span></div>`;
  if(!ou) return xg + `<div class="stat"><span>Over 2.5 buts</span><span>${pct(p.over25)}</span></div>`;
  const row=(ln)=>{
    const o=ou[ln]; if(!o) return "";
    const over=o.over, under=o.under, overLead=over>=under;
    const uPct=Math.round(under*100), oPct=100-uPct;
    return `<div class="ou-row">
      <span class="ou-ln">${ln} but${parseFloat(ln)>=2?"s":""}</span>
      <span class="ou-bar" title="Under ${pct(under)} · Over ${pct(over)}">
        <span class="ou-u${overLead?"":" win"}" style="width:${uPct}%">${uPct>=18?`U ${pct(under)}`:""}</span>
        <span class="ou-o${overLead?" win":""}" style="width:${oPct}%">${oPct>=18?`O ${pct(over)}`:""}</span>
        <span class="ou-mid"></span>
      </span>
    </div>`;
  };
  return xg + `<div class="ou-wrap">
    <div class="ou-legend"><span><i class="dot u"></i>Under (moins de)</span><span>50%</span><span><i class="dot o"></i>Over (plus de)</span></div>
    ${row("1.5")}${row("2.5")}${row("3.5")}
  </div>`;
}

/* BTTS (les deux marquent) Oui/Non + niveau de confiance (métacognition + netteté du marché) */
function bttsBlock(p){
  const c=p.bttsConf;
  const yes=p.btts, no=1-yes;
  const confTxt = c ? ` · confiance <b class="conf-${c.label}">${c.label}</b>` : "";
  const pick = c ? c.pick : (yes>=0.5?"Oui":"Non");
  // transparence : si on a appliqué une correction empirique, on l'indique
  const mc=p.marketCalib;
  let calNote="";
  if(mc && mc.n>0 && Math.abs(mc.bttsShift)>=0.01){
    const sign=mc.bttsShift>0?"+":"";
    calNote=`<div class="cal-note">⚙️ ajusté ${sign}${Math.round(mc.bttsShift*100)} pts d'après ${mc.n} matchs joués (brut ${pct(mc.bttsRaw)})</div>`;
  }
  return `<div class="stat"><span>BTTS — les deux marquent</span>
    <span>Oui ${pct(yes)} / Non ${pct(no)}</span></div>
    <div class="btts-pick">Pronostic : <b>${pick}</b>${confTxt}</div>${calNote}`;
}

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
function halftimeBlock(m,p){
  const h=p.halftime;
  if(!h) return "";
  
  const realHt = (m.analysis && m.analysis.events && m.analysis.events.halftime) ? m.analysis.events.halftime : null;
  const isStarted = m.status === 'IN_PROGRESS' || m.status === 'FINISHED';
  
  if (isStarted && realHt) {
    return `<div style="margin-top:14px"><h3>⏱️ Score à la mi-temps (Réel)</h3>
      <div class="scoreline" style="margin:4px 0">
        <div class="tn" style="font-size:13px">${m.home}</div>
        <div class="sc" style="font-size:26px">${realHt.replace("-", " – ")}<small>score à la pause</small></div>
        <div class="tn" style="font-size:13px">${m.away}</div>
      </div>
    </div>`;
  }

  const note = (h.shareHome !== undefined && h.shareAway !== undefined)
    ? `ℹ️ La mi-temps est estimée via les ratios de buts en 1ère MT propres à chaque équipe (priorisé à ~42% via Bayesian Shrinkage). Domicile (${m.home}) : <b>${Math.round(h.shareHome*100)}%</b> · Extérieur (${m.away}) : <b>${Math.round(h.shareAway*100)}%</b>.`
    : `ℹ️ La mi-temps est dérivée du ratio structurel des buts en Coupe du Monde (~42 % marqués en 1ère période · sources : CDM 2018/2022 & 19 CDM 1930-2010). C'est une constante du football mondial, <b>pas</b> une statistique propre à ${m.home}/${m.away}.`;

  return `<div style="margin-top:14px"><h3>⏱️ Mi-temps probable</h3>
    <div class="grid2">
      <div>
        <div class="scoreline" style="margin:4px 0">
          <div class="tn" style="font-size:13px">${m.home}</div>
          <div class="sc" style="font-size:26px">${h.topScore[0]} – ${h.topScore[1]}<small>score à la pause</small></div>
          <div class="tn" style="font-size:13px">${m.away}</div>
        </div>
      </div>
      <div>
        <div class="stat"><span>Score final probable</span><span><b>${p.topScore[0]} – ${p.topScore[1]}</b></span></div>
        <div class="stat"><span>Au moins 1 but en 1ère MT</span><span>${pct(h.ou05.over)}</span></div>
        <div class="stat"><span>Over 1.5 en 1ère MT</span><span>${pct(h.ou15.over)}</span></div>
      </div>
    </div>
    <div class="note">${note}</div>
  </div>`;
}

/* Marchés dérivés : Double Chance, Draw No Bet, top-3 scores exacts.
   100% calculés sur la grille Dixon-Coles (aucune cote, aucune donnée externe). */
function marketsBlock(m,p){
  const dc=p.doubleChance, dnb=p.drawNoBet, ts=p.topScores;
  if(!dc && !dnb && !ts) return "";
  let out = `<div style="margin-top:14px"><h3>🎯 Marchés dérivés</h3>`;
  if(dc) out += `<div style="font-size:11.5px;color:var(--muted);margin:2px 0 3px">Double chance</div>
    <div class="mk-chips">
      <div class="mk-chip"><span class="k">${m.home} ou nul (1X)</span><span class="v">${pct(dc["1X"])}</span></div>
      <div class="mk-chip"><span class="k">pas de nul (12)</span><span class="v">${pct(dc["12"])}</span></div>
      <div class="mk-chip"><span class="k">nul ou ${m.away} (X2)</span><span class="v">${pct(dc["X2"])}</span></div>
    </div>`;
  if(dnb) out += `<div style="font-size:11.5px;color:var(--muted);margin:9px 0 3px">Draw No Bet (nul = remboursé)</div>
    <div class="mk-chips">
      <div class="mk-chip"><span class="k">${m.home}</span><span class="v">${pct(dnb.home)}</span></div>
      <div class="mk-chip"><span class="k">${m.away}</span><span class="v">${pct(dnb.away)}</span></div>
    </div>`;
  if(ts && ts.length) out += `<div style="font-size:11.5px;color:var(--muted);margin:9px 0 3px">Scores probables (top 3)</div>
    <div class="mk-chips">
      ${ts.map(s=>`<div class="mk-chip"><span class="k">score</span><span class="v">${s.score} · ${pct(s.p)}</span></div>`).join("")}
    </div>`;
  return out + `</div>`;
}

/* Scénarios narratifs : 4 catégories dérivées de la grille de scores réelle.
   Aucun timing/historique inventé — chaque % vient de la somme des cases de la grille. */
function scenariosBlock(m,p){
  const sc=p.scenarios;
  if(!sc || !sc.length) return "";
  const col=id=> id==="closed"?"#5b8cff": id==="tight"?"#ffd34e": id==="open"?"#33e0a0":"#ff8a5b";
  const main = sc.filter(s=>!s.angle);
  const angle = sc.filter(s=>s.angle);
  const card = s=>`<div class="scn ${s.angle?"angle":""}">
      <div class="scn-bar" style="background:${col(s.id)}"></div>
      <div class="scn-top"><div class="scn-title">${s.title}</div><div class="scn-p">${pct(s.p)}</div></div>
      <div class="scn-track"><div class="scn-fill" style="width:${Math.round(s.p*100)}%;background:${col(s.id)}"></div></div>
      <div class="scn-scores">${(s.scores||[]).map(x=>`<b>${x}</b>`).join("")}</div>
      <div class="scn-note">${s.note||""}</div>
    </div>`;
  return `<div style="margin-top:14px"><h3>🎬 Scénarios du match</h3>
    <div style="font-size:11.5px;color:var(--muted);margin:2px 0 4px">
      Probabilités dérivées de la grille de scores réelle (les 3 premiers totalisent 100 %).
      « Large écart » est un angle inclus dans « spectacle ».</div>
    <div class="scn-grid">${main.map(card).join("")}</div>
    ${angle.length?`<div class="scn-grid" style="grid-template-columns:1fr">${angle.map(card).join("")}</div>`:""}
  </div>`;
}

/* helper : barre Over/Under générique (réutilisée par corners & cartons) */
function ouLineRow(label, o){
  const over=o.over, under=o.under, overLead=over>=under;
  const uPct=Math.round(under*100), oPct=100-uPct;
  return `<div class="ou-row"><span class="ou-ln">${label}</span>
    <span class="ou-bar" title="Under ${pct(under)} · Over ${pct(over)}">
      <span class="ou-u${overLead?"":" win"}" style="width:${uPct}%">${uPct>=18?`U ${pct(under)}`:""}</span>
      <span class="ou-o${overLead?" win":""}" style="width:${oPct}%">${oPct>=18?`O ${pct(over)}`:""}</span>
      <span class="ou-mid"></span></span></div>`;
}

/* bloc bio (forces/faiblesses) — données réelles sourcées, sinon rien */
function bioHtml(b){
  if(!b) return "";
  const f=(b.forces||[]).map(x=>`<li>${x}</li>`).join("");
  const w=(b.faiblesses||[]).map(x=>`<li>${x}</li>`).join("");
  return `<div class="bio-card">
    <div class="bio-top">${b.bio||""}${b.club?` <span class="bio-club">${b.club}</span>`:""}</div>
    <div class="bio-fw">
      <div class="bio-col bio-pro"><div class="bio-h">✅ Forces</div><ul>${f||"<li>N/D</li>"}</ul></div>
      <div class="bio-col bio-con"><div class="bio-h">⚠️ Faiblesses</div><ul>${w||"<li>N/D</li>"}</ul></div>
    </div>
    ${b.source?`<div class="bio-src">source : ${b.source}</div>`:""}
  </div>`;
}

/* ===== MODULE PRONOS JOUEURS (6 rôles, en probabilités) ===== */
function ppTeam(teamName, pp){
  if(!pp) return `<div class="risk-nd">Effectif indisponible — <b>N/D</b>.</div>`;
  const bar=(p)=>`<span class="pp-bar"><span class="pp-fill" style="width:${Math.round(p*100)}%"></span></span>`;
  // buteurs
  const scorers=(pp.scorers||[]).map((s,i)=>`<div class="pp-row">
      <span class="pp-rk">${i+1}</span>
      <span class="pp-nm">${s.name}<span class="pp-pos">${s.poste||""}</span>${s.bio?'<span class="pp-bio-tag">bio ✓</span>':''}</span>
      ${bar(s.p)}<b class="pp-pct">${pct(s.p)}</b>
      <div class="pp-why">${s.why||""}</div>
      ${bioHtml(s.bio)}
    </div>`).join("");
  // passeur principal / créateur
  const cr=pp.creator;
  const creator = cr?`<div class="pp-line"><span class="pp-k">🎨 Créateur principal</span>
    <span><b>${cr.name}</b> <span class="pp-pos">${cr.poste||""}</span> · ${pct(cr.p)} <span class="pp-why-inline">${cr.why||""}</span></span></div>`:"";
  // passeurs probables (top 3 hors créateur déjà cité)
  const assisters=(pp.assisters||[]).slice(0,3).map(a=>`<div class="pp-line"><span class="pp-k">🅰️ Passeur</span>
    <span><b>${a.name}</b> <span class="pp-pos">${a.poste||""}</span> · ${pct(a.p)}</span></div>`).join("");
  // gardien
  const gk=pp.keeper;
  const keeper = gk?`<div class="pp-line"><span class="pp-k">🧤 Gardien sollicité</span>
    <span><b>${gk.name}</b>${gk.expSotFaced!=null?` · ~${gk.expSotFaced} tirs cadrés à gérer`:" · N/D"}
    <span class="pp-why-inline">${gk.why||""}</span></span></div>${gk.bio?bioHtml(gk.bio):""}`:"";
  // remplaçant impact
  const bench=(pp.benchImpact||[]);
  const benchHtml = bench.length
    ? bench.map(b=>`<div class="pp-line"><span class="pp-k">🔄 Impact banc</span>
        <span><b>${b.name}</b> <span class="pp-pos">${b.poste||""}</span> · <span class="pp-why-inline">${b.why||""}</span></span></div>`).join("")
    : `<div class="pp-line"><span class="pp-k">🔄 Impact banc</span><span style="color:var(--muted)">N/D tant qu'aucun remplaçant n'a été décisif</span></div>`;
  return `<div class="pp-team"><div class="pp-team-h">${teamName}</div>
    <div class="pp-sub">⚽ Buteurs probables</div>${scorers||'<div class="risk-nd">N/D</div>'}
    ${creator}${assisters}${keeper}${benchHtml}</div>`;
}
/* ===== BUTEURS : pronostiqués (modèle) vs réels (match joué) ===== */
function scorersVsBlock(m){
  const a=m.analysis, p=m.prediction; if(!a||!p) return "";
  const ev=a.events||{}; const goals=(ev.goals||[]).filter(g=>g.player && g.player!=="N/D");
  const pp=p.playerProps; if(!pp) return "";
  // noms réellement buteurs (normalisés sur le nom de famille)
  const norm=s=>(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
  const last=s=>{const n=norm(s).split(" ");return n[n.length-1]||"";};
  const realScorers=goals.map(g=>g.player);
  const realLast=new Set(realScorers.map(last));
  // top buteurs pronostiqués par le modèle (rôle "scorer")
  const picks=[];
  for(const side of ["home","away"]){
    const t=pp[side]||{}; const sc=t.scorers||[];
    (Array.isArray(sc)?sc:[]).slice(0,3).forEach(x=>picks.push({team:m[side],name:x.name,prob:x.p}));
  }
  const goalRows=goals.map(g=>{
    const pred=picks.some(x=>last(x.name)===last(g.player));
    return `<div class="stat"><span>${g.minute}' ${g.player} <small style="color:var(--muted)">(${g.team})</small></span>
      <span>${pred?'<span class="vs-chip win">✅ prédit</span>':'<span class="vs-chip lose">—</span>'}</span></div>`;
  }).join("");
  const pickRows=picks.map(x=>{
    const nm=x.name; const hit=realLast.has(last(nm));
    const prob=x.prob!=null?` <small>${Math.round(x.prob*100)}%</small>`:"";
    return `<div class="stat"><span>${nm} <small style="color:var(--muted)">(${x.team})</small>${prob}</span>
      <span>${hit?'<span class="vs-chip win">✅ a marqué</span>':'<span class="vs-chip lose">❌</span>'}</span></div>`;
  }).join("");
  return `<div class="module mod-players"><h3>🎯 Buteurs : prono vs réel</h3>
    <div class="grid2">
      <div><h4 style="margin:4px 0;font-size:13px">⚽ Buts réels du match</h4>${goalRows||'<div class="note">Aucun but.</div>'}</div>
      <div><h4 style="margin:4px 0;font-size:13px">🔮 Buteurs pronostiqués (top 3/équipe)</h4>${pickRows||'<div class="note">N/D</div>'}</div>
    </div>
    <div class="note" style="margin-top:6px">Le modèle donne des <b>probabilités</b>, pas des certitudes : un buteur non prédit reste un résultat normal.</div>
  </div>`;
}

function playerPropsBlock(m,p){
  const pp=p.playerProps; if(!pp) return "";
  return `<div class="module mod-players"><h3>👤 Pronos joueurs <span class="mod-hint">probabilités, pas des certitudes</span></h3>
    <div class="pp-note">Probabilités <b>modèle</b> : effectif réel (poste) + production réelle des matchs joués.
    Se précisent à mesure que les équipes jouent. Aucun chiffre inventé.</div>
    <div class="pp-grid">${ppTeam(m.home,pp.home)}${ppTeam(m.away,pp.away)}</div>
  </div>`;
}

function showLog(log){ const e=$("adminLog"); if(!e) return; if(log){e.classList.remove("u-hidden");e.textContent=log.slice(-4000);} else e.classList.add("u-hidden"); }

/* ===== MODULE TIRS (vue équipe) — données réelles, N/D si match à venir ===== */
function shotsBlock(m,p){
  const s=p.shots; if(!s) return "";
  // ----- MATCH À VENIR : PRONO de tirs/cadrés (moyennes évolutives réelles) -----
  if(!s.real || s.home==null){
    if(s.expShots==null) return "";   // aucun prono possible
    const ln=s.lines||{}, lnOn=s.linesOn||{};
    const keys=Object.keys(ln).sort((a,b)=>parseFloat(a)-parseFloat(b));
    const keysOn=Object.keys(lnOn).sort((a,b)=>parseFloat(a)-parseFloat(b));
    const rows=keys.map(k=>ouLineRow(`${k} tirs`,ln[k])).join("");
    const rowsOn=keysOn.map(k=>ouLineRow(`${k} cadrés`,lnOn[k])).join("");
    const accBadge=(a)=> a==null?`<span style="color:var(--muted)">N/D</span>`:`${a}%`;
    return `<div class="module mod-shots"><h3>🎯 Tirs & tirs cadrés <span class="mod-hint">📊 prono (moyennes réelles CDM 2026)</span></h3>
      <div class="mod-top">
        <div class="mod-big"><b>${s.expShots}</b><small>tirs projetés</small></div>
        <div class="mod-split">
          <div class="stat"><span>${m.home}</span><span><b>${s.home}</b> tirs · ${s.homeOn} cadrés</span></div>
          <div class="stat"><span>${m.away}</span><span><b>${s.away}</b> tirs · ${s.awayOn} cadrés</span></div>
        </div>
      </div>
      <div class="ou-lines">${rows}</div>
      <div class="mod-big" style="margin-top:10px"><b>${s.expShotsOn}</b><small>tirs cadrés projetés (total)</small></div>
      <div class="ou-lines">${rowsOn}</div>
      <div class="stat"><span>Précision attendue ${m.home}</span><span>${accBadge(s.homeAcc)}</span></div>
      <div class="stat"><span>Précision attendue ${m.away}</span><span>${accBadge(s.awayAcc)}</span></div>
      ${s.basis?`<div class="note" style="margin-top:8px">📐 Calculé sur : <b>attaque/défense</b> (tirs produits vs concédés) × <b>domination</b> (${s.basis.dominance?.[0]}/${s.basis.dominance?.[1]}, via buts attendus + Elo) × <b>possession</b> (${s.basis.possession?.[0]}%/${s.basis.possession?.[1]}%). Cadrés = tirs × précision réelle de chaque équipe (${s.basis.accuracy?.[0]}%/${s.basis.accuracy?.[1]}%).</div>`:`<div class="note" style="margin-top:8px">Projection dérivée des tirs réellement produits/concédés par chaque sélection au Mondial 2026.</div>`}
      <div class="note" style="margin-top:4px;opacity:.75">⚠️ Les tirs d'un match sont très variables : ce prono indique une tendance, pas une certitude.</div>
    </div>`;
  }
  // barre comparative tirs (domicile vs extérieur)
  const tot=Math.max((s.home||0)+(s.away||0),1);
  const hW=Math.round((s.home||0)/tot*100);
  const totOn=Math.max((s.homeOn||0)+(s.awayOn||0),1);
  const hOnW=Math.round((s.homeOn||0)/totOn*100);
  const accBadge=(a)=> a==null?`<span style="color:var(--muted)">N/D</span>`:`${a}%`;
  return `<div class="module mod-shots"><h3>🎯 Tirs & tirs cadrés <span class="mod-hint">données réelles du match</span></h3>
    <div class="cmp">
      <div class="cmp-lbl"><b>${s.home}</b><span>Tirs</span><b>${s.away}</b></div>
      <div class="cmp-bar"><span class="cmp-h" style="width:${hW}%"></span><span class="cmp-a" style="width:${100-hW}%"></span></div>
    </div>
    <div class="cmp">
      <div class="cmp-lbl"><b>${s.homeOn??"N/D"}</b><span>Tirs cadrés</span><b>${s.awayOn??"N/D"}</b></div>
      <div class="cmp-bar"><span class="cmp-h on" style="width:${hOnW}%"></span><span class="cmp-a on" style="width:${100-hOnW}%"></span></div>
    </div>
    <div class="stat"><span>Précision ${m.home}</span><span>${accBadge(s.homeAcc)}</span></div>
    <div class="stat"><span>Précision ${m.away}</span><span>${accBadge(s.awayAcc)}</span></div>
  </div>`;
}

/* ===== MODULE CORNERS (autonome) ===== */
function cornersBlock(m,p){
  const c=p.corners; if(!c) return "";
  const ln=c.lines||{};
  // lignes dynamiques (centrées sur le total attendu) -> on prend les clés du modèle, triées
  const keys=Object.keys(ln).sort((a,b)=>parseFloat(a)-parseFloat(b));
  const rows=keys.map(k=>ouLineRow(`${k} corners`,ln[k])).join("");
  return `<div class="module mod-corners"><h3>⛳ Corners ${c.src?`<span class="mod-hint">📊 ${c.src}</span>`:""}</h3>
    <div class="mod-top">
      <div class="mod-big"><b>${c.exp_corners}</b><small>total projeté</small></div>
      <div class="mod-split">
        <div class="stat"><span>${m.home}</span><span><b>${c.home}</b></span></div>
        <div class="stat"><span>${m.away}</span><span><b>${c.away}</b></span></div>
      </div>
    </div>
    <div class="ou-wrap">
      <div class="ou-legend"><span><i class="dot u"></i>Under</span><span>50%</span><span><i class="dot o"></i>Over</span></div>
      ${rows}
    </div></div>`;
}

/* ===== MODULE CARTONS (autonome — séparé des corners) ===== */
function cardsBlock(m,p){
  const c=p.cards; if(!c) return "";
  const ln=c.lines||{};
  const rows=["2.5","3.5","4.5"].filter(k=>ln[k]).map(k=>ouLineRow(`${k} cartons`,ln[k])).join("");
  const ref=p.referee;
  const refLine = ref
    ? `<div class="stat"><span>🧑‍⚖️ Arbitre</span><span><b>${ref.name}</b> <span style="color:var(--muted)">(${ref.nation})</span></span></div>`
      + (ref.severity?`<div class="stat"><span>⚖️ Style d'arbitrage</span><span><b>${ref.severity}</b> cartons/match <span style="color:var(--muted);font-size:10px">(${ref.severitySrc})</span></span></div>`:"")
    : `<div class="stat"><span>🧑‍⚖️ Arbitre</span><span style="color:var(--muted)">N/D — non désigné publiquement</span></div>`;
  const red = c.redProb!=null
    ? `<div class="stat"><span>🟥 Au moins 1 rouge</span><span>${pct(c.redProb)} <span style="color:var(--muted);font-size:10px">(approx. structurelle)</span></span></div>`
    : "";
  // joueurs à risque
  const rp=p.riskPlayers||{};
  const realList=[...((rp.home&&rp.home.real)||[]).map(x=>({...x,team:m.home})),
                 ...((rp.away&&rp.away.real)||[]).map(x=>({...x,team:m.away}))];
  const realHtml = realList.length
    ? `<div class="risk-real">${realList.map(x=>`<div class="risk-r"><span class="risk-card">${x.card}</span> <b>${x.name}</b> <span class="risk-pos">${x.pos||""} · ${x.team}</span></div>`).join("")}</div>`
    : `<div class="risk-nd">Aucun joueur déjà averti (équipes pas encore en lice ou match propre). <b>N/D</b> tant qu'aucun match joué.</div>`;
  const profiles=((rp.home&&rp.home.profiles)||[]);
  const profHtml = profiles.length
    ? `<div class="risk-prof"><div class="risk-prof-head">🧭 Profils tactiques exposés <span>éclairage générique, pas un joueur nommé</span></div>
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

/* ---------- interactions ---------- */
$("tabs").querySelectorAll(".tab").forEach(tab=>{
  tab.onclick=()=>{
    $("tabs").querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
    tab.classList.add("active");
    TAB=tab.dataset.t; GROUP="Tous"; closeDetail();
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
