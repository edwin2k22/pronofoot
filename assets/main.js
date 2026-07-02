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
import { keyEventsBlock } from './components/keyEvents.js';
import { halftimeBlock } from './components/halftime.js';
import { renderPerf, drawSpark } from './components/performance.js';

// Attach needed functions to window so inline HTML onclick handlers still work
window.openMatchByTeams = openMatchByTeams;
window.favBtn = favBtn;
window.toggleFav = toggleFav;
window.openSidebar = openSidebar;
window.closeSidebar = closeSidebar;
window.adminAction = adminAction;

let COMBO_HISTORY = null;
function setComboHistory(d) { COMBO_HISTORY = d; }

const IS_LOCAL_SURFACE = ["localhost", "127.0.0.1", ""].includes(location.hostname) || location.protocol === "file:";
const IS_PUBLIC_SURFACE = !IS_LOCAL_SURFACE;

const DASHBOARD_VIEW = {
  sort: localStorage.getItem("pf-sort") || "time",
  valueOnly: localStorage.getItem("pf-filter-value") === "1",
  highConfidence: localStorage.getItem("pf-filter-confidence") === "1",
  withOdds: localStorage.getItem("pf-filter-odds") === "1",
};

const STRATEGY_STORE = "pf-strategy-saved";
const STRATEGY_CURRENT = "pf-strategy-current";
const SCANNER_STORE = "pf-scanner-saved";
const SCANNER_CURRENT = "pf-scanner-current";

const DEFAULT_STRATEGY = {
  name: "Value stricte",
  market: "value",
  minProb: 0.58,
  minEdge: 0.15,
  minOdd: 1.4,
  maxOdd: 8,
  minConf: 0,
  requireOdds: true,
};

const DEFAULT_SCANNER = {
  name: "Prematch value",
  status: "prematch",
  market: "value",
  minProb: 0.58,
  minEdge: 0.15,
  minOdd: 1.4,
  maxOdd: 8,
  maxHours: 72,
  onlyLineups: false,
  onlyReferee: false,
  requireOdds: true,
};

const MARKET_LABELS = {
  value: "Meilleure value",
  fav1n2: "Favori 1N2",
  home: "Victoire domicile",
  draw: "Match nul",
  away: "Victoire extérieur",
  over25: "Over 2.5",
  under25: "Under 2.5",
  overBook: "Over ligne book",
  underBook: "Under ligne book",
  bttsYes: "BTTS Oui",
  bttsNo: "BTTS Non",
};

function sourceCoverage(data){
  const matches = Array.isArray(data) ? data : [];
  const tags = new Set(matches.flatMap(m=>m.sources||[]));
  const count = fn => matches.filter(fn).length;
  return {
    matches: matches.length,
    tags,
    odds: count(m=>m.odd1 || m.oddOver || m.oddBTTS_Yes),
    refs: count(m=>(predictionOf(m).referee||{}).name),
    officialXi: count(m=>!!predictionOf(m).officialLineups),
    projectedXi: count(m=>!!predictionOf(m).projectedLineups),
    espn: count(m=>(m.sources||[]).some(s=>String(s).startsWith("ESPN"))),
  };
}

function renderFreeSourceStrip(data){
  const el = $("freeSourceStrip");
  if(!el) return;
  const c = sourceCoverage(data);
  const fragile = c.projectedXi ? `${c.projectedXi} XI projetes` : "XI projetes en attente";
  if(IS_PUBLIC_SURFACE){
    el.innerHTML = `
      <div class="source-strip-main">
        <div>
          <div class="source-strip-title">Donnees mises a jour</div>
          <div class="source-strip-sub">Scores, cotes, arbitres et compositions quand elles sont disponibles. Mode lecture seule.</div>
        </div>
        <span class="source-pill-ok">public</span>
      </div>
      <div class="source-strip-grid">
        <span><b>${c.matches}</b> matchs</span>
        <span><b>${c.odds}</b> avec cotes</span>
        <span><b>${c.refs}</b> arbitres</span>
        <span><b>${c.officialXi}</b> XI officiels</span>
        <span><b>${fragile}</b></span>
      </div>`;
    return;
  }
  el.innerHTML = `
    <div class="source-strip-main">
      <div>
        <div class="source-strip-title">Mode 100% gratuit</div>
        <div class="source-strip-sub">openfootball + ESPN public + cache local + modele Elo/Poisson. Aucune cle API payante obligatoire.</div>
      </div>
      <span class="source-pill-ok">free-only</span>
    </div>
    <div class="source-strip-grid">
      <span><b>${c.matches}</b> matchs</span>
      <span><b>${c.odds}</b> avec cotes</span>
      <span><b>${c.refs}</b> arbitres</span>
      <span><b>${c.officialXi}</b> XI officiels</span>
      <span><b>${fragile}</b></span>
      <span><b>${c.espn}</b> enrichis ESPN</span>
    </div>`;
}

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
  if(liveCount) liveCount.textContent = "Mode 100% gratuit - ESPN public/openfootball - modele Elo + Poisson";
  ensureModernDashboard();
  renderFreeSourceStrip(data);
  updateCounts(); buildGroupFilter(); renderDecisionRadar(); render();
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
  try{ const cbEl=$("embedded-combo"); if(cbEl) setComboHistory(JSON.parse(cbEl.textContent) || null); }catch(_){}
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

function predictionOf(m){
  return (m && m.prediction) || {};
}

function outcomeProfile(m){
  const p = predictionOf(m);
  const items = [
    {key:"home", label:m.home, prob:+p.p1 || 0, odd:m.odd1},
    {key:"draw", label:"Nul", prob:+p.pX || 0, odd:m.oddX},
    {key:"away", label:m.away, prob:+p.p2 || 0, odd:m.odd2},
  ];
  return items.reduce((best, item)=>item.prob > best.prob ? item : best, items[0]);
}

function modelConfidence(m){
  const declared = Number(m && m.confidence);
  if(Number.isFinite(declared) && declared > 0) return declared;
  return outcomeProfile(m).prob || 0;
}

function valueCandidates(m){
  const p = predictionOf(m);
  const v = p.value || {};
  return [
    {key:"home", label:m.home, data:v.home},
    {key:"draw", label:"Nul", data:v.draw},
    {key:"away", label:m.away, data:v.away},
  ].filter(x=>x.data && x.data.is_value && !marketGuard(m, {market:"1N2"}));
}

function bestValue(m){
  const values = valueCandidates(m);
  if(!values.length) return null;
  return values.sort((a,b)=>(b.data.edge || 0) - (a.data.edge || 0))[0];
}

function hasOdds(m){
  return !!(m && (m.odd1 || m.oddX || m.odd2 || m.oddOver || m.oddUnder));
}

function upsetInfo(m){
  const p = predictionOf(m);
  return p.upsetIndex || m.upsetIndex || null;
}

function totalGoalLean(m){
  const p = predictionOf(m);
  return Number.isFinite(+p.totalXg) ? +p.totalXg : ((+p.lamHome || 0) + (+p.lamAway || 0));
}

function sortRankDate(m){
  const t = parseKickoff(m.date);
  return t == null ? Number.MAX_SAFE_INTEGER : t;
}

function sortDisplayMatches(list){
  const direction = TAB === "FINISHED" ? -1 : 1;
  return [...list].sort((a,b)=>direction * (sortRankDate(a)-sortRankDate(b)));
}

function esc(v){
  return String(v ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function readStore(key, fallback){
  try{ return JSON.parse(localStorage.getItem(key)) ?? fallback; }catch(_){ return fallback; }
}

function writeStore(key, value){
  localStorage.setItem(key, JSON.stringify(value));
}

function nval(id, fallback=0){
  const el=$(id);
  const n=Number(el && el.value);
  return Number.isFinite(n) ? n : fallback;
}

function checked(id){
  const el=$(id);
  return !!(el && el.checked);
}

function marketOptions(selected){
  return Object.entries(MARKET_LABELS).map(([v,l])=>
    `<option value="${v}"${v===selected?" selected":""}>${l}</option>`).join("");
}

function oneXtwoCandidates(m){
  const p=predictionOf(m);
  return [
    {market:"1N2", selection:"1", label:`Victoire ${m.home}`, prob:+p.p1 || 0, odd:m.odd1},
    {market:"1N2", selection:"X", label:"Match nul", prob:+p.pX || 0, odd:m.oddX},
    {market:"1N2", selection:"2", label:`Victoire ${m.away}`, prob:+p.p2 || 0, odd:m.odd2},
  ].map(withEdge);
}

function withEdge(c){
  const odd=Number(c.odd);
  const prob=Number(c.prob);
  return {...c, prob, odd:Number.isFinite(odd) && odd>1 ? odd : null,
    edge:Number.isFinite(odd) && odd>1 ? prob - (1/odd) : null};
}

function ouCandidate(m, side, fixedLine){
  const p=predictionOf(m);
  const bookLine = Number(m.oddOU_line);
  const line = Number.isFinite(fixedLine) ? fixedLine : (Number.isFinite(bookLine) ? bookLine : 2.5);
  const key = String(line);
  const row = (p.overUnder || {})[key];
  let over = row ? +row.over : (line===2.5 ? +p.over25 : null);
  if(!Number.isFinite(over)) return null;
  const prob = side==="over" ? over : 1-over;
  const odd = Number.isFinite(bookLine) && Math.abs(bookLine-line)<0.01
    ? (side==="over" ? m.oddOver : m.oddUnder)
    : null;
  return withEdge({market:"OU", selection:side, line, label:`${side==="over"?"Plus":"Moins"} de ${line} buts`, prob, odd});
}

function bttsCandidate(m, side){
  const p=predictionOf(m);
  const b=Number(p.btts);
  if(!Number.isFinite(b)) return null;
  return withEdge({
    market:"BTTS",
    selection:side,
    label:`Les deux marquent : ${side==="yes"?"Oui":"Non"}`,
    prob:side==="yes" ? b : 1-b,
    odd:side==="yes" ? m.oddBTTS_Yes : m.oddBTTS_No,
  });
}

function allBetCandidates(m){
  return [
    ...oneXtwoCandidates(m),
    ouCandidate(m, "over", 2.5),
    ouCandidate(m, "under", 2.5),
    ouCandidate(m, "over", null),
    ouCandidate(m, "under", null),
    bttsCandidate(m, "yes"),
    bttsCandidate(m, "no"),
  ].filter(Boolean);
}

function marketGuard(m, c){
  const intel = (predictionOf(m).marketIntelligence || {});
  const checks = intel.checks || [];
  const aliases = {
    DNB: ["DNB", "1N2"],
    "1N2": ["1N2"],
    OU: ["OU"],
    BTTS: ["BTTS"],
    CORNERS: ["CORNERS"],
    CARTONS: ["CARTONS"],
  };
  const markets = aliases[c?.market] || [c?.market];
  return checks.find(x=>markets.includes(x.market) && x.verdict==="avoid") || null;
}

function pickCandidate(m, market){
  const fixed = {
    home: () => oneXtwoCandidates(m)[0],
    draw: () => oneXtwoCandidates(m)[1],
    away: () => oneXtwoCandidates(m)[2],
    over25: () => ouCandidate(m, "over", 2.5),
    under25: () => ouCandidate(m, "under", 2.5),
    overBook: () => ouCandidate(m, "over", null),
    underBook: () => ouCandidate(m, "under", null),
    bttsYes: () => bttsCandidate(m, "yes"),
    bttsNo: () => bttsCandidate(m, "no"),
  };
  if(market==="fav1n2") return oneXtwoCandidates(m).sort((a,b)=>b.prob-a.prob)[0];
  if(market==="value") return allBetCandidates(m)
    .filter(c=>c.odd && Number.isFinite(c.edge) && !marketGuard(m, c))
    .sort((a,b)=>(b.edge-a.edge) || (b.prob-a.prob))[0] || null;
  return fixed[market] ? fixed[market]() : null;
}

function candidateWon(m, c){
  const a=m.analysis;
  if(!a || !c) return null;
  if(c.market==="1N2") return c.selection === a.outcome;
  if(c.market==="OU"){
    const total=Number(a.totalGoals);
    if(!Number.isFinite(total)) return null;
    return c.selection==="over" ? total > c.line : total < c.line;
  }
  if(c.market==="BTTS") return (c.selection==="yes") === !!a.bttsReal;
  return null;
}

function passesBetFilters(m, c, cfg){
  if(!c) return false;
  if(marketGuard(m, c)) return false;
  if(c.prob < Number(cfg.minProb || 0)) return false;
  if(Number(cfg.minConf || 0) > 0 && modelConfidence(m) < Number(cfg.minConf)) return false;
  if(cfg.requireOdds && !c.odd) return false;
  if(c.odd){
    if(c.odd < Number(cfg.minOdd || 1)) return false;
    if(Number(cfg.maxOdd || 0) > 0 && c.odd > Number(cfg.maxOdd)) return false;
  } else if(Number(cfg.minOdd || 0) > 1 || Number(cfg.maxOdd || 0) > 0) return false;
  if(Number(cfg.minEdge || 0) > 0 && (!Number.isFinite(c.edge) || c.edge < Number(cfg.minEdge))) return false;
  return true;
}

function resultScore(m){
  return (m.analysis && m.analysis.realScore) || m.realScore || "";
}

function currentStrategyConfig(){
  return {
    name: ($("strategyName")?.value || DEFAULT_STRATEGY.name).trim() || DEFAULT_STRATEGY.name,
    market: $("strategyMarket")?.value || DEFAULT_STRATEGY.market,
    minProb: nval("strategyMinProb", DEFAULT_STRATEGY.minProb),
    minEdge: nval("strategyMinEdge", DEFAULT_STRATEGY.minEdge),
    minOdd: nval("strategyMinOdd", DEFAULT_STRATEGY.minOdd),
    maxOdd: nval("strategyMaxOdd", DEFAULT_STRATEGY.maxOdd),
    minConf: nval("strategyMinConf", DEFAULT_STRATEGY.minConf),
    requireOdds: checked("strategyRequireOdds"),
  };
}

function currentScannerConfig(){
  return {
    name: ($("scannerName")?.value || DEFAULT_SCANNER.name).trim() || DEFAULT_SCANNER.name,
    status: $("scannerStatus")?.value || DEFAULT_SCANNER.status,
    market: $("scannerMarket")?.value || DEFAULT_SCANNER.market,
    minProb: nval("scannerMinProb", DEFAULT_SCANNER.minProb),
    minEdge: nval("scannerMinEdge", DEFAULT_SCANNER.minEdge),
    minOdd: nval("scannerMinOdd", DEFAULT_SCANNER.minOdd),
    maxOdd: nval("scannerMaxOdd", DEFAULT_SCANNER.maxOdd),
    maxHours: nval("scannerMaxHours", DEFAULT_SCANNER.maxHours),
    onlyLineups: checked("scannerLineups"),
    onlyReferee: checked("scannerReferee"),
    requireOdds: true,
    minConf: 0,
  };
}

function backtestStrategy(cfg){
  const rows=[];
  MATCHES.filter(m=>effectiveStatus(m)==="FINISHED" && m.analysis).forEach(m=>{
    const cand=pickCandidate(m, cfg.market);
    if(!passesBetFilters(m, cand, cfg)) return;
    const won=candidateWon(m, cand);
    if(won==null) return;
    const profit=cand.odd ? (won ? cand.odd-1 : -1) : null;
    rows.push({m, cand, won, profit});
  });
  rows.sort((a,b)=>sortRankDate(a.m)-sortRankDate(b.m));
  const bets=rows.length;
  const wins=rows.filter(r=>r.won).length;
  const oddsRows=rows.filter(r=>r.profit!=null);
  const pnl=oddsRows.reduce((s,r)=>s+r.profit,0);
  const staked=oddsRows.length;
  let equity=0, peak=0, maxDd=0;
  oddsRows.forEach(r=>{
    equity += r.profit;
    peak = Math.max(peak, equity);
    maxDd = Math.min(maxDd, equity - peak);
  });
  return {
    rows, bets, wins,
    winRate:bets ? wins/bets : 0,
    pnl, staked,
    yield:staked ? pnl/staked : 0,
    avgOdd:oddsRows.length ? oddsRows.reduce((s,r)=>s+r.cand.odd,0)/oddsRows.length : null,
    avgProb:bets ? rows.reduce((s,r)=>s+r.cand.prob,0)/bets : null,
    maxDd,
  };
}

function scannerMatches(cfg){
  const now=Date.now();
  return MATCHES.map(m=>({m, st:effectiveStatus(m), ko:parseKickoff(m.date)}))
    .filter(x=>{
      const live = x.st==="LIVE" || x.st==="HT" || x.st==="KICKOFF";
      const prematch = x.st==="SCHEDULED";
      if(cfg.status==="live" && !live) return false;
      if(cfg.status==="prematch" && !prematch) return false;
      if(cfg.status==="both" && !(live || prematch)) return false;
      if(cfg.maxHours && x.ko && x.ko-now > cfg.maxHours*3600000) return false;
      if(cfg.maxHours && x.ko && x.ko < now-3*3600000 && !live) return false;
      const p=predictionOf(x.m);
      if(cfg.onlyLineups && !(p.officialLineups || p.projectedLineups)) return false;
      if(cfg.onlyReferee && !(p.referee && p.referee.name)) return false;
      return true;
    })
    .map(x=>({m:x.m, st:x.st, cand:pickCandidate(x.m, cfg.market)}))
    .filter(x=>passesBetFilters(x.m, x.cand, cfg))
    .sort((a,b)=>(b.cand.edge ?? -9)-(a.cand.edge ?? -9) || sortRankDate(a.m)-sortRankDate(b.m));
}

function applySmartFilters(list){
  let out = [...list];
  if(DASHBOARD_VIEW.valueOnly) out = out.filter(m=>!!bestValue(m));
  if(DASHBOARD_VIEW.highConfidence) out = out.filter(m=>modelConfidence(m) >= .72 || outcomeProfile(m).prob >= .62);
  if(DASHBOARD_VIEW.withOdds) out = out.filter(hasOdds);

  const by = DASHBOARD_VIEW.sort;
  out.sort((a,b)=>{
    if(by === "confidence") return modelConfidence(b) - modelConfidence(a);
    if(by === "value") return ((bestValue(b)||{}).data?.edge || -9) - ((bestValue(a)||{}).data?.edge || -9);
    if(by === "upset") return ((upsetInfo(b)||{}).index || -1) - ((upsetInfo(a)||{}).index || -1);
    if(by === "goals") return totalGoalLean(b) - totalGoalLean(a);
    return sortRankDate(a) - sortRankDate(b);
  });
  return out;
}

function ensureModernDashboard(){
  if(!$("decisionRadar")){
    const hero = document.querySelector(".hero");
    if(hero){
      hero.insertAdjacentHTML("afterend", `<section class="decision-radar" id="decisionRadar" aria-label="Radar decisionnel"></section>`);
    }
  }
  if(!$("freeSourceStrip")){
    const radar = $("decisionRadar");
    if(radar){
      radar.insertAdjacentHTML("afterend", `<section class="source-strip" id="freeSourceStrip" aria-label="Sources gratuites"></section>`);
    }
  }
  if(!$("smartControls")){
    const anchor = $("liveFeed") || $("matchList");
    if(anchor){
      anchor.insertAdjacentHTML("beforebegin", `
        <section class="command-strip" id="smartControls" aria-label="Controle des matchs">
          <div class="command-field">
            <label for="matchSort">Tri</label>
            <select id="matchSort" aria-label="Trier les matchs">
              <option value="time">Horaire</option>
              <option value="confidence">Confiance</option>
              <option value="value">Value</option>
              <option value="upset">Risque surprise</option>
              <option value="goals">Buts attendus</option>
            </select>
          </div>
          <button type="button" class="chip-toggle" data-filter="valueOnly">Value</button>
          <button type="button" class="chip-toggle" data-filter="highConfidence">Confiance</button>
          <button type="button" class="chip-toggle" data-filter="withOdds">Cotes</button>
          <div class="smart-count" id="smartCount"></div>
        </section>`);
    }
  }

  const sort = $("matchSort");
  if(sort && !sort.dataset.wired){
    sort.dataset.wired = "1";
    sort.value = DASHBOARD_VIEW.sort;
    sort.addEventListener("change", ()=>{
      DASHBOARD_VIEW.sort = sort.value;
      localStorage.setItem("pf-sort", DASHBOARD_VIEW.sort);
      render();
    });
  }

  document.querySelectorAll(".chip-toggle[data-filter]").forEach(btn=>{
    if(btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.addEventListener("click", ()=>{
      const key = btn.dataset.filter;
      DASHBOARD_VIEW[key] = !DASHBOARD_VIEW[key];
      const storageKey = key === "valueOnly" ? "pf-filter-value" : key === "highConfidence" ? "pf-filter-confidence" : "pf-filter-odds";
      localStorage.setItem(storageKey, DASHBOARD_VIEW[key] ? "1" : "0");
      render();
    });
  });
  updateSmartControls();
}

function updateSmartControls(shown, total){
  const panel = $("smartControls");
  if(panel){
    const hidden = TAB==="BEST" || TAB==="GROUPS" || TAB==="BRACKET" || TAB==="SCANNER" || TAB==="STRATEGY";
    panel.classList.toggle("u-hidden", hidden);
  }
  const radar = $("decisionRadar");
  if(radar) radar.classList.toggle("u-hidden", TAB==="BRACKET" || TAB==="SCANNER" || TAB==="STRATEGY");
  const sort = $("matchSort");
  if(sort) sort.value = DASHBOARD_VIEW.sort;
  document.querySelectorAll(".chip-toggle[data-filter]").forEach(btn=>{
    btn.classList.toggle("active", !!DASHBOARD_VIEW[btn.dataset.filter]);
  });
  const count = $("smartCount");
  if(count && Number.isFinite(shown) && Number.isFinite(total)){
    count.textContent = shown === total ? `${shown} matchs` : `${shown}/${total} matchs`;
  }
}

function renderDecisionRadar(){
  const box = $("decisionRadar");
  if(!box || !MATCHES.length) return;
  const active = MATCHES.filter(m=>effectiveStatus(m)!=="FINISHED");
  const pool = active.length ? active : MATCHES;
  const upcoming = pool.filter(m=>parseKickoff(m.date)!=null).sort((a,b)=>sortRankDate(a)-sortRankDate(b));
  const next = upcoming[0] || pool[0];
  const lock = [...pool].sort((a,b)=>modelConfidence(b)-modelConfidence(a))[0];
  const value = [...pool].filter(bestValue).sort((a,b)=>((bestValue(b)||{}).data.edge || 0)-((bestValue(a)||{}).data.edge || 0))[0];
  const upset = [...pool].filter(upsetInfo).sort((a,b)=>((upsetInfo(b)||{}).index || 0)-((upsetInfo(a)||{}).index || 0))[0];
  const goals = [...pool].sort((a,b)=>totalGoalLean(b)-totalGoalLean(a))[0];

  const card = (kind, title, m, metric, hint)=>{
    if(!m) return "";
    const key = `${(m.home || "").replace(/"/g,"&quot;")}|${(m.away || "").replace(/"/g,"&quot;")}`;
    return `<button type="button" class="radar-card ${kind}" data-open-match="${key}">
      <span class="radar-k">${title}</span>
      <b>${m.home} - ${m.away}</b>
      <span class="radar-m">${metric}</span>
      <small>${hint}</small>
    </button>`;
  };
  const emptyCard = (kind, title, metric, hint)=>`<div class="radar-card ${kind} disabled">
      <span class="radar-k">${title}</span>
      <b>${metric}</b>
      <span class="radar-m">--</span>
      <small>${hint}</small>
    </div>`;

  const valuePick = value ? bestValue(value) : null;
  const nextLabel = next && parseKickoff(next.date)!=null ? countdown(next) : "calendrier";
  const lockPick = lock ? outcomeProfile(lock) : null;
  const upsetMeta = upset ? upsetInfo(upset) : null;
  box.innerHTML = `
    <div class="radar-head">
      <div>
        <span>PronoFoot intelligence</span>
        <h2>Radar decisionnel</h2>
      </div>
      <div class="radar-meta">${MATCHES.length} matchs · ${active.length} a surveiller</div>
    </div>
    <div class="radar-grid">
      ${card("time", "Prochain", next, nextLabel, next?.date ? next.date.slice(0,16) : "")}
      ${card("lock", "Plus fiable", lock, lockPick ? `${lockPick.label} · ${pct(lockPick.prob)}` : "modele", `${Math.round(modelConfidence(lock || {})*100)}% confiance`)}
      ${value ? card("value", "Value", value, valuePick ? `${valuePick.label} · +${Math.round((valuePick.data.edge || 0)*100)}%` : "aucune value", valuePick?.data?.odd ? `cote ${valuePick.data.odd}` : "marche neutre") : emptyCard("value", "Value", "Aucune value active", "marche surveille")}
      ${card("risk", "Surprise", upset, upsetMeta ? `${upsetMeta.index}/100` : "faible", upsetMeta?.label || "indice modele")}
      ${card("goals", "Buts", goals, `${totalGoalLean(goals).toFixed(2)} xG`, predictionOf(goals).over25!=null ? `Over 2.5 ${pct(predictionOf(goals).over25)}` : "projection")}
    </div>`;

  box.querySelectorAll("[data-open-match]").forEach(btn=>{
    btn.addEventListener("click", ()=>{
      const [home, away] = btn.dataset.openMatch.split("|");
      openMatchByTeams(home, away);
    });
  });
}

function matchInsightStrip(m){
  const p = predictionOf(m);
  if(!p.p1 && !p.pX && !p.p2) return "";
  const pick = outcomeProfile(m);
  const val = bestValue(m);
  const risk = upsetInfo(m);
  const conf = Math.round(modelConfidence(m) * 100);
  const bits = [
    `<span>Pick <b>${pick.label} ${pct(pick.prob)}</b></span>`,
    `<span>Confiance <b>${conf}%</b></span>`,
  ];
  if(val) bits.push(`<span>Edge <b>+${Math.round((val.data.edge || 0)*100)}%</b></span>`);
  if(risk && risk.index != null) bits.push(`<span>Surprise <b>${risk.index}/100</b></span>`);
  if(p.over25 != null) bits.push(`<span>Over <b>${pct(p.over25)}</b></span>`);
  return `<div class="mi-insights">${bits.join("")}</div>`;
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
  let combo = [];
  let comboStats = null;
  let comboStatus = null;
  
  if (COMBO_HISTORY && COMBO_HISTORY.history) {
    comboStats = COMBO_HISTORY.stats;
    const todayStr = new Date().toISOString().split('T')[0];
    const todayCombo = COMBO_HISTORY.history[todayStr];
    if (todayCombo && todayCombo.legs.length > 0) {
      combo = todayCombo.legs;
      comboStatus = todayCombo.status;
    }
  }
  
  if (combo.length === 0) {
    const lockPicks = TOPPICKS.picks.filter(p=>p.tier==="lock");
    const seenMatch = new Set();
    for(const p of lockPicks){
      const k=p.home+"|"+p.away;
      if(seenMatch.has(k)) continue;
      seenMatch.add(k); combo.push(p);
      if(combo.length>=4) break;
    }
  }

  let comboHtml="";
  if(combo.length>=2){
    const comboProb = combo.reduce((a,p)=>a*p.prob,1);
    const legs = combo.map(p=>{
      let legStat = '';
      if (p.status && p.status !== 'PENDING') {
        const color = p.status === 'WON' ? '#33e0a0' : (p.status === 'LOST' ? '#ff6b6b' : '#ffb84d');
        legStat = `<span style="font-size:10px;margin-left:4px;padding:2px 4px;border-radius:3px;background:${color};color:#000;">${p.status}</span>`;
      }
      return `<div class="combo-leg"><span>${p.home} v ${p.away}</span><b>${p.label}</b><span style="color:#33e0a0">${Math.round(p.prob*100)}%${legStat}</span></div>`;
    }).join("");
    
    const statsBadge = comboStats ? `<span style="float:right;font-size:11px;background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;">Historique : <b style="color:#33e0a0">${comboStats.won}W</b> - <b style="color:#ff6b6b">${comboStats.lost}L</b></span>` : '';
    let statusBadge = '';
    if (comboStatus && comboStatus !== 'PENDING') {
      const ccolor = comboStatus === 'WON' ? '#33e0a0' : (comboStatus === 'LOST' ? '#ff6b6b' : '#ffb84d');
      statusBadge = `<span style="font-size:11px;margin-left:8px;padding:2px 6px;border-radius:3px;background:${ccolor};color:#000;vertical-align:middle;">${comboStatus}</span>`;
    }

    comboHtml = `<div class="combo-box" style="margin-top:0; height:100%;">
      <div class="combo-head">🧩 Combiné du jour ${statusBadge} ${statsBadge} <div style="font-size:11px;color:var(--muted);margin-top:4px;">${combo.length} sélections verrouillées</div></div>
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





function metricCard(label, value, sub=""){
  return `<div class="lab-metric"><span>${label}</span><b>${value}</b>${sub?`<small>${sub}</small>`:""}</div>`;
}

function savedList(key){
  const d=readStore(key, []);
  return Array.isArray(d) ? d : [];
}

function savedSelectHtml(items, activeName){
  return `<option value="">Charger un profil</option>` + items.map((x,i)=>
    `<option value="${i}"${x.name===activeName?" selected":""}>${esc(x.name)}</option>`).join("");
}

function renderStrategyLab(){
  const box=$("matchList"); if(!box) return;
  box.classList.add("lab-mode");
  const cfg={...DEFAULT_STRATEGY, ...readStore(STRATEGY_CURRENT, {})};
  const saved=savedList(STRATEGY_STORE);
  const bt=backtestStrategy(cfg);
  const sampleNote=bt.bets<25 ? "echantillon faible" : "echantillon exploitable";
  const rows=bt.rows.slice().reverse().slice(0,80).map(r=>{
    const odd=r.cand.odd ? r.cand.odd.toFixed(2) : "N/D";
    const edge=Number.isFinite(r.cand.edge) ? `${Math.round(r.cand.edge*100)} pts` : "N/D";
    const profit=r.profit==null ? "N/D" : `${r.profit>=0?"+":""}${r.profit.toFixed(2)}u`;
    return `<tr>
      <td>${esc((r.m.date||"").slice(0,16))}</td>
      <td><button class="lab-link" data-open="${esc(r.m.home)}|${esc(r.m.away)}">${esc(r.m.home)} - ${esc(r.m.away)}</button></td>
      <td>${esc(r.cand.label)}</td>
      <td>${pct(r.cand.prob)}</td>
      <td>${odd}</td>
      <td>${edge}</td>
      <td>${esc(resultScore(r.m))}</td>
      <td><span class="lab-pill ${r.won?"ok":"ko"}">${r.won?"win":"loss"}</span></td>
      <td>${profit}</td>
    </tr>`;
  }).join("");
  box.innerHTML=`
    <section class="lab-shell">
      <div class="lab-head">
        <div><span>Strategy Lab</span><h2>Backtest de strategie</h2></div>
        <p>Teste une regle sur les matchs termines, avec ROI, edge, drawdown et details bet par bet.</p>
      </div>
      <div class="lab-grid controls">
        <label>Nom<input id="strategyName" class="lab-control" value="${esc(cfg.name)}"></label>
        <label>Profil sauvegarde<select id="strategySaved">${savedSelectHtml(saved, cfg.name)}</select></label>
        <label>Marche<select id="strategyMarket" class="lab-control">${marketOptions(cfg.market)}</select></label>
        <label>Proba min<input id="strategyMinProb" class="lab-control" type="number" min="0" max="1" step="0.01" value="${cfg.minProb}"></label>
        <label>Edge min<input id="strategyMinEdge" class="lab-control" type="number" min="-1" max="1" step="0.01" value="${cfg.minEdge}"></label>
        <label>Cote min<input id="strategyMinOdd" class="lab-control" type="number" min="1" max="100" step="0.01" value="${cfg.minOdd}"></label>
        <label>Cote max<input id="strategyMaxOdd" class="lab-control" type="number" min="0" max="100" step="0.01" value="${cfg.maxOdd}"></label>
        <label>Confiance min<input id="strategyMinConf" class="lab-control" type="number" min="0" max="1" step="0.01" value="${cfg.minConf}"></label>
        <label class="lab-check"><input id="strategyRequireOdds" class="lab-control" type="checkbox"${cfg.requireOdds?" checked":""}> Cotes requises</label>
        <div class="lab-actions">
          <button type="button" class="abtn primary" id="strategySave">Enregistrer</button>
          <button type="button" class="abtn" id="strategyDelete">Supprimer</button>
        </div>
      </div>
      <div class="lab-metrics">
        ${metricCard("Bets", bt.bets, sampleNote)}
        ${metricCard("Winrate", bt.bets ? pct(bt.winRate) : "0%")}
        ${metricCard("PnL", `${bt.pnl>=0?"+":""}${bt.pnl.toFixed(2)}u`, `${bt.staked} bets avec cotes`)}
        ${metricCard("Yield", bt.staked ? `${(bt.yield*100).toFixed(1)}%` : "N/D")}
        ${metricCard("Cote moy.", bt.avgOdd ? bt.avgOdd.toFixed(2) : "N/D")}
        ${metricCard("Max DD", `${bt.maxDd.toFixed(2)}u`)}
      </div>
      <div class="lab-table-wrap">
        <table class="lab-table">
          <thead><tr><th>Date</th><th>Match</th><th>Pick</th><th>Proba</th><th>Cote</th><th>Edge</th><th>Score</th><th>Resultat</th><th>PnL</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="9">Aucun bet historique ne correspond a cette strategie.</td></tr>`}</tbody>
        </table>
      </div>
    </section>`;
  wireStrategyLab();
}

function wireStrategyLab(){
  document.querySelectorAll(".lab-control").forEach(el=>{
    el.addEventListener("change", ()=>{ writeStore(STRATEGY_CURRENT, currentStrategyConfig()); setTimeout(renderStrategyLab, 0); });
  });
  const saved=$("strategySaved");
  if(saved) saved.onchange=()=>{
    const cfg=savedList(STRATEGY_STORE)[Number(saved.value)];
    if(cfg){ writeStore(STRATEGY_CURRENT, cfg); renderStrategyLab(); }
  };
  const save=$("strategySave");
  if(save) save.onclick=()=>{
    const cfg=currentStrategyConfig();
    const items=savedList(STRATEGY_STORE).filter(x=>x.name!==cfg.name);
    items.push(cfg); writeStore(STRATEGY_STORE, items); writeStore(STRATEGY_CURRENT, cfg); renderStrategyLab();
  };
  const del=$("strategyDelete");
  if(del) del.onclick=()=>{
    const cfg=currentStrategyConfig();
    writeStore(STRATEGY_STORE, savedList(STRATEGY_STORE).filter(x=>x.name!==cfg.name)); renderStrategyLab();
  };
  document.querySelectorAll("[data-open]").forEach(btn=>{
    btn.onclick=()=>{ const [h,a]=btn.dataset.open.split("|"); openMatchByTeams(h,a); };
  });
}

function renderScanner(){
  const box=$("matchList"); if(!box) return;
  box.classList.add("lab-mode");
  const cfg={...DEFAULT_SCANNER, ...readStore(SCANNER_CURRENT, {})};
  const saved=savedList(SCANNER_STORE);
  const hits=scannerMatches(cfg);
  const rows=hits.map(({m,st,cand})=>{
    const val=Number.isFinite(cand.edge) ? `${Math.round(cand.edge*100)} pts` : "N/D";
    const odd=cand.odd ? cand.odd.toFixed(2) : "N/D";
    const p=predictionOf(m);
    const badges=[
      p.officialLineups ? "XI off." : (p.projectedLineups ? "XI proj." : ""),
      p.referee && p.referee.name ? "Arbitre" : "",
      bestValue(m) ? "Value" : "",
    ].filter(Boolean).map(x=>`<span class="lab-pill">${x}</span>`).join("");
    return `<div class="scan-row" data-open="${esc(m.home)}|${esc(m.away)}">
      <div class="scan-main">
        <div class="scan-top"><span>${esc(st)}</span><span>${esc((m.date||"").slice(0,16))}</span>${badges}</div>
        <b>${esc(m.home)} - ${esc(m.away)}</b>
        <div class="scan-pick">${esc(cand.label)} · ${pct(cand.prob)} · cote ${odd} · edge ${val}</div>
      </div>
      <div class="scan-side"><span>${countdown(m) || "maintenant"}</span><button type="button" class="abtn">Ouvrir</button></div>
    </div>`;
  }).join("");
  box.innerHTML=`
    <section class="lab-shell">
      <div class="lab-head">
        <div><span>Scanner</span><h2>Prematch / live</h2></div>
        <p>Filtre les prochains matchs et les lives selon proba, edge, cote, compos officielles et arbitres.</p>
      </div>
      <div class="lab-grid controls">
        <label>Nom<input id="scannerName" class="scan-control" value="${esc(cfg.name)}"></label>
        <label>Profil sauvegarde<select id="scannerSaved">${savedSelectHtml(saved, cfg.name)}</select></label>
        <label>Fenetre<select id="scannerStatus" class="scan-control">
          <option value="prematch"${cfg.status==="prematch"?" selected":""}>Prematch</option>
          <option value="live"${cfg.status==="live"?" selected":""}>Live</option>
          <option value="both"${cfg.status==="both"?" selected":""}>Prematch + live</option>
        </select></label>
        <label>Marche<select id="scannerMarket" class="scan-control">${marketOptions(cfg.market)}</select></label>
        <label>Proba min<input id="scannerMinProb" class="scan-control" type="number" min="0" max="1" step="0.01" value="${cfg.minProb}"></label>
        <label>Edge min<input id="scannerMinEdge" class="scan-control" type="number" min="-1" max="1" step="0.01" value="${cfg.minEdge}"></label>
        <label>Cote min<input id="scannerMinOdd" class="scan-control" type="number" min="1" max="100" step="0.01" value="${cfg.minOdd}"></label>
        <label>Cote max<input id="scannerMaxOdd" class="scan-control" type="number" min="0" max="100" step="0.01" value="${cfg.maxOdd}"></label>
        <label>Horizon h<input id="scannerMaxHours" class="scan-control" type="number" min="1" max="240" step="1" value="${cfg.maxHours}"></label>
        <label class="lab-check"><input id="scannerLineups" class="scan-control" type="checkbox"${cfg.onlyLineups?" checked":""}> XI dispo</label>
        <label class="lab-check"><input id="scannerReferee" class="scan-control" type="checkbox"${cfg.onlyReferee?" checked":""}> Arbitre connu</label>
        <div class="lab-actions">
          <button type="button" class="abtn primary" id="scannerSave">Enregistrer</button>
          <button type="button" class="abtn" id="scannerDelete">Supprimer</button>
        </div>
      </div>
      <div class="lab-metrics">
        ${metricCard("Signaux", hits.length)}
        ${metricCard("Value", hits.filter(x=>Number.isFinite(x.cand.edge) && x.cand.edge>0).length)}
        ${metricCard("Avec XI", hits.filter(x=>predictionOf(x.m).officialLineups || predictionOf(x.m).projectedLineups).length)}
        ${metricCard("Avec arbitre", hits.filter(x=>predictionOf(x.m).referee && predictionOf(x.m).referee.name).length)}
      </div>
      <div class="scan-list">${rows || `<div class="empty">Aucun match ne correspond a ce scanner.</div>`}</div>
    </section>`;
  wireScanner();
}

function wireScanner(){
  document.querySelectorAll(".scan-control").forEach(el=>{
    el.addEventListener("change", ()=>{ writeStore(SCANNER_CURRENT, currentScannerConfig()); setTimeout(renderScanner, 0); });
  });
  const saved=$("scannerSaved");
  if(saved) saved.onchange=()=>{
    const cfg=savedList(SCANNER_STORE)[Number(saved.value)];
    if(cfg){ writeStore(SCANNER_CURRENT, cfg); renderScanner(); }
  };
  const save=$("scannerSave");
  if(save) save.onclick=()=>{
    const cfg=currentScannerConfig();
    const items=savedList(SCANNER_STORE).filter(x=>x.name!==cfg.name);
    items.push(cfg); writeStore(SCANNER_STORE, items); writeStore(SCANNER_CURRENT, cfg); renderScanner();
  };
  const del=$("scannerDelete");
  if(del) del.onclick=()=>{
    const cfg=currentScannerConfig();
    writeStore(SCANNER_STORE, savedList(SCANNER_STORE).filter(x=>x.name!==cfg.name)); renderScanner();
  };
  document.querySelectorAll(".scan-row").forEach(row=>{
    row.onclick=()=>{ const [h,a]=row.dataset.open.split("|"); openMatchByTeams(h,a); };
  });
}

const TEAM_SEARCH_ALIASES = {
  "Belgium": "belgique",
  "Brazil": "bresil brasil",
  "USA": "etats unis united states etats-unis",
  "South Korea": "coree du sud",
  "Czech Republic": "tchequie republique tcheque",
  "DR Congo": "rd congo republique democratique du congo",
  "Cape Verde": "cap vert",
  "Bosnia & Herzegovina": "bosnie herzegovine bosnie-herzegovine",
  "Ivory Coast": "cote ivoire cote d ivoire",
};

function foldText(value){
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function matchSearchText(m){
  const aliases = [TEAM_SEARCH_ALIASES[m.home], TEAM_SEARCH_ALIASES[m.away]].filter(Boolean).join(" ");
  return foldText(`${m.home} ${m.away} ${m.league || ""} ${m.realScore || ""} ${aliases}`);
}

function render(){
  ensureModernDashboard();
  document.body.classList.toggle("tool-view", TAB==="SCANNER" || TAB==="STRATEGY");
  renderDecisionRadar();
  if(TAB==="BRACKET"){
    const ml = $("matchList"); if(ml) ml.classList.add("u-hidden");
    const hero = document.querySelector(".hero"); if(hero) hero.classList.add("u-hidden");
    updateSmartControls();
    renderBracket(); 
    return; 
  }
  const box=$("bracketView"); if(box) box.classList.add("u-hidden");
  const ml = $("matchList"); if(ml) ml.classList.remove("u-hidden");
  if(ml) ml.classList.remove("lab-mode");
  const hero = document.querySelector(".hero"); if(hero) hero.classList.remove("u-hidden");
  if(TAB==="BEST"){ updateSmartControls(); renderBestPicks(); return; }
  if(TAB==="GROUPS"){ updateSmartControls(); renderStandings(); return; }
  if(TAB==="SCANNER"){ updateSmartControls(); renderScanner(); return; }
  if(TAB==="STRATEGY"){ updateSmartControls(); renderStrategyLab(); return; }
  const q = foldText($("search").value.trim());
  const searchActive = q.length > 0;
  let list = searchActive
    ? MATCHES.filter(m=>matchSearchText(m).includes(q))
    : MATCHES.filter(matchInTab);
  if(GROUP!=="Tous") list = list.filter(m=>m.league===GROUP);
  const beforeSmartFilters = list.length;
  if(!searchActive) list = applySmartFilters(list);
  list = sortDisplayMatches(list);
  updateSmartControls(list.length, beforeSmartFilters);

  if(!list.length){
    const msg = beforeSmartFilters && !list.length
      ? "Aucun match ne correspond aux filtres actifs."
      : searchActive
      ? "Aucun match trouve pour cette recherche."
      : TAB==="LIVE"
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
    let htHtml = m.htScore ? ` (MT: ${m.htScore})` : "";
    if(isDone && m.realScore) scoreHtml=`<div class="mi-score">${m.realScore.replace("-"," – ")}</div><div class="mi-when">score final${htHtml}</div>`;
    else if(isLive && m.liveScore) scoreHtml=`<div class="mi-score">${m.liveScore.replace("-"," – ")}</div><div class="mi-when">en direct${htHtml}</div>`;
    else if(isKick) scoreHtml=`<div class="mi-vsmid">VS</div><div class="mi-when">en attente du direct</div>`;
    else if(isAwait) scoreHtml=`<div class="mi-vsmid">VS</div><div class="mi-when">résultat en attente</div>`;
    else if(p.topScore){
      const ts=(p.topScores&&p.topScores[0]);
      const sp=ts&&ts.p!=null ? ` ${pct(ts.p)}` : "";
      scoreHtml=`<div class="mi-vsmid">VS</div><div class="mi-when">modal ${p.topScore[0]}-${p.topScore[1]}${sp}</div>`;
    }
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
      const hasVal=!!bestValue(m);
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
        ${matchInsightStrip(m)}
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
      <div class="sc gold">${a.realScore.replace("-"," – ")}<small>score final${m.htScore ? ` (MT: ${m.htScore})` : ""}</small></div>
      <div class="tn">${m.away}</div>
    </div>
    ${vsTable(m)}
    <div class="verdict done anim-block anim-4"><b>${a.predictionCorrect?"✅":"❌"} Verdict du modèle :</b> ${a.summary}</div>
    ${formRow(m)}
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
    ${lineupsBlock(m, a)}
    <div id="live-timeline-container">${timeline(m, a)}</div>
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

/* ===== NLP MOMENTUM BLOCK (Live uniquement) ===== */
function nlpMomentumBlock(m) {
  const nlp = m.nlpMomentum;
  if (!nlp) return "";

  const homeM = nlp.homeMomentum || 0;   // [-1, +1]
  const awayM = nlp.awayMomentum || 0;
  const dom   = nlp.dominance || "balanced";
  const urgency = nlp.urgencyDetected;

  // Barres de momentum : on convertit [-1,+1] → [0%,100%]
  const homePct  = Math.round((homeM + 1) / 2 * 100);   // 0%=dominé, 100%=dominant
  const awayPct  = Math.round((awayM + 1) / 2 * 100);

  // Couleurs selon dominance
  const hCol = dom === "home"  ? "#4fc3f7"
             : dom === "away"  ? "#607d8b"
             :                   "#78909c";
  const aCol = dom === "away"  ? "#f06292"
             : dom === "home"  ? "#607d8b"
             :                   "#78909c";

  const domLabel = dom === "home"  ? `🏠 <b>${m.home}</b> domine`
                 : dom === "away"  ? `✈️ <b>${m.away}</b> domine`
                 :                   "⚖️ Équilibre";

  const urgencyBadge = urgency
    ? `<span style="background:#ff3c00;color:#fff;padding:2px 7px;border-radius:10px;font-size:11px;margin-left:8px;">⚡ Urgence</span>`
    : "";

  const lamH = nlp.homeLambdaAdj ? `×${nlp.homeLambdaAdj.toFixed(2)}` : "";
  const lamA = nlp.awayLambdaAdj ? `×${nlp.awayLambdaAdj.toFixed(2)}` : "";

  const pens = nlp.penalties;
  let penWarning = "";
  if (pens) {
    const warns = [];
    if (pens.home_adj < 1.0) warns.push(`⚠️ ${m.home} pénalisé (x${pens.home_adj}): ${pens.home_reasons.join(', ')}`);
    if (pens.away_adj < 1.0) warns.push(`⚠️ ${m.away} pénalisé (x${pens.away_adj}): ${pens.away_reasons.join(', ')}`);
    if (warns.length > 0) {
      penWarning = `<div style="margin-bottom:8px;padding:6px;background:rgba(255,60,0,0.15);border:1px solid rgba(255,60,0,0.4);border-radius:4px;font-size:12px;color:#ff8a65;">
        ${warns.join('<br>')}
      </div>`;
    }
  }

  return `
  <div style="margin:14px 0;padding:12px 14px;background:rgba(30,40,60,0.7);border:1px solid rgba(79,195,247,0.25);border-radius:8px;">
    ${penWarning}
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
      <span style="font-size:13px;font-weight:700;color:#90caf9;display:flex;align-items:center;gap:6px;">
        🧠 Momentum NLP (ESPN live)
      </span>
      <span style="font-size:12px;color:#aaa;">${domLabel}${urgencyBadge}</span>
    </div>

    <!-- Barre home -->
    <div style="margin-bottom:7px;">
      <div style="display:flex;justify-content:space-between;font-size:12px;color:#ccc;margin-bottom:3px;">
        <span>${m.home}</span>
        <span style="color:${hCol};font-weight:700;">${lamH}</span>
      </div>
      <div style="background:rgba(255,255,255,0.08);border-radius:4px;height:7px;overflow:hidden;">
        <div style="height:100%;width:${homePct}%;background:${hCol};border-radius:4px;transition:width .5s;"></div>
      </div>
    </div>

    <!-- Barre away -->
    <div>
      <div style="display:flex;justify-content:space-between;font-size:12px;color:#ccc;margin-bottom:3px;">
        <span>${m.away}</span>
        <span style="color:${aCol};font-weight:700;">${lamA}</span>
      </div>
      <div style="background:rgba(255,255,255,0.08);border-radius:4px;height:7px;overflow:hidden;">
        <div style="height:100%;width:${awayPct}%;background:${aCol};border-radius:4px;transition:width .5s;"></div>
      </div>
    </div>

    <div style="margin-top:8px;font-size:11px;color:#607d8b;">
      Analyse textuelle des ${nlp.signalsCount || 0} signaux ESPN · ajuste λ Poisson en temps réel
    </div>
  </div>`;
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
    ${exactScoresStrip(p)}
    ${scoreUncertaintyBlock(p)}
    ${probBlock(m,p)}
    ${nlpMomentumBlock(m)}
    <div class="verdict anim-block anim-5">Pronostic d'avant-match (repère). Élo ${m.homeElo} vs ${m.awayElo}.</div>
    <div id="live-timeline-container"></div>
    ${srcTags(m)}
  </div>`;
}


function hotTrendsBlock(m) {
  if (!m.hotTrends || m.hotTrends.length === 0) return "";
  let html = `<div style="margin:12px 0; padding:10px; background:rgba(255, 60, 0, 0.1); border:1px solid #ff3c00; border-radius:6px;">
    <h3 style="color:#ff6b4a; margin-bottom:8px; display:flex; align-items:center; gap:6px;">🔥 Tendances Fortes</h3>
    <ul style="margin:0; padding-left:20px; font-size:13px; color:#f0f0f0;">`;
  for(let t of m.hotTrends) {
    html += `<li style="margin-bottom:4px;">${t}</li>`;
  }
  html += `</ul></div>`;
  return html;
}

/* match À VENIR : pronostic complet.
   mode : undefined = à venir | "kickoff" = coup d'envoi atteint | "awaiting" = résultat en attente */
function missingKeyPlayersBlock(m) {
  const p = predictionOf(m);
  const av = p.availability || {};
  const parts = [];
  const add = (team, side) => {
    const x = av[side] || {};
    const missing = (x.missing || []).map(z => z.name).filter(Boolean);
    if (x.applied && missing.length) {
      const hit = x.factor != null ? `−${Math.round((1 - x.factor) * 100)}% λ` : "impact λ";
      parts.push(`${team}: ${missing.join(", ")} (${hit})`);
    }
  };
  add(m.home, "home");
  add(m.away, "away");
  if (!parts.length) return "";
  return `<div style="background:var(--card-bg); border-left:4px solid #ff6b7d; padding:10px 14px; margin-bottom:15px; border-radius:4px;">
    <div style="font-weight:700; color:#ff6b7d; font-size:13px; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
      ABSENCES CLÉS
    </div>
    <div style="font-size:12px; color:var(--text); opacity:0.9;">
      Joueurs majeurs absents du XI officiel : <b>${parts.join(" · ")}</b>. Le modèle ajuste les buts attendus avant les probabilités.
    </div>
  </div>`;
}

function projectedLineupsBlock(m,p){
  const official=p.officialLineups||{};
  const projected=p.projectedLineups||{};
  const hasOfficial=(official.homeXi&&official.homeXi.length>=11)||(official.awayXi&&official.awayXi.length>=11);
  const activeLineup=hasOfficial ? official : projected;
  const hasProjected=!hasOfficial && ((projected.homeXi&&projected.homeXi.length>=11)||(projected.awayXi&&projected.awayXi.length>=11));
  const hasLineup=hasOfficial || hasProjected;
  const forms=p.formations||{};
  const li=p.lineupImpact||m.lineupImpact||{};
  const pp=p.playerProps||{};
  if(!hasLineup && !forms.home && !forms.away && !li.tacticalMod && !pp.home && !pp.away) return "";
  const namesFor=(side)=>{
    if(hasLineup){
      const xi=activeLineup[side==="home"?"homeXi":"awayXi"]||[];
      return xi.map((name,i)=>({role:i===0?"Gardien":"Titulaire", name}));
    }
    const team=pp[side]||{};
    const out=[];
    if(team.keeper&&team.keeper.name) out.push({role:"Gardien", name:team.keeper.name});
    if(team.creator&&team.creator.name) out.push({role:"Créateur", name:team.creator.name});
    (team.scorers||[]).slice(0,3).forEach(s=>out.push({role:s.poste||"Attaque", name:s.name, p:s.p}));
    return out;
  };
  const side=(label,key,form)=>`<div class="lineup-side">
    <div class="lineup-head"><b>${label}</b><span>${form||"formation N/D"}</span></div>
    <div class="lineup-names">
      ${namesFor(key).map(x=>`<span><b>${clean(x.name)}</b><small>${x.role}${x.p!=null?` · ${pct(x.p)}`:""}</small></span>`).join("") || '<em>Joueurs N/D</em>'}
    </div>
  </div>`;
  const impact = li.tacticalMod!=null
    ? `<div class="lineup-impact">Impact modèle : tactique ×${li.tacticalMod} · rotation ${m.home} ${Math.round((li.rotationDeltaHome||0)*100)}% / ${m.away} ${Math.round((li.rotationDeltaAway||0)*100)}%</div>`
    : "";
  const status = hasOfficial
    ? `XI officiel reçu (${official.source||"source officielle"}) — le modèle l'utilise dans ses probabilités.`
    : hasProjected
    ? `XI projeté reçu (${projected.source||"source projetée"}) — utilisé par le modèle jusqu'au XI officiel.${projected.url?` <a href="${projected.url}" target="_blank" rel="noopener">Source</a>`:""}`
    : "XI officiel non reçu dans le flux. Projection modèle ci-dessous.";
  const homeForm = hasLineup ? (activeLineup.homeFormation || forms.home) : forms.home;
  const awayForm = hasLineup ? (activeLineup.awayFormation || forms.away) : forms.away;
  return `<div class="module lineup-proj">
    <h3>👥 Compos & disponibilité</h3>
    <div class="lineup-status">${status}</div>
    <div class="lineup-grid">
      ${side(m.home,"home",homeForm)}
      ${side(m.away,"away",awayForm)}
    </div>
    ${impact}
  </div>`;
}

/* bloc commun : barres 1N2 + marchés */
/* forme W/D/L en pastilles colorées (le plus récent à gauche) */
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
    ${exactScoresStrip(p)}
    ${scoreUncertaintyBlock(p)}
    ${coherenceHint(m,p)}
    ${marketIntelligenceBlock(m,p)}
    ${missingKeyPlayersBlock(m)}
    ${projectedLineupsBlock(m,p)}
    ${h2hBlock(m)}
    ${scorersVsBlock(m)}
    ${keyEventsBlock(m)}
    ${playerPropsBlock(m, p)}
    ${hotTrendsBlock(m)}
    ${probBlock(m,p)}
    ${nlpMomentumBlock(m)}
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
  return str.split("").reverse().map(r=>`<span style="display:inline-block;width:18px;height:18px;line-height:18px;
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
    <h3>📈 Forme (5 derniers, le + récent à droite)</h3>
    <div class="stat"><span>${m.home}</span><span>${formCell(m.homeForm5, m.homeFormDetail)}</span></div>
    <div class="stat"><span>${m.away}</span><span>${formCell(m.awayForm5, m.awayFormDetail)}</span></div>
  </div>`;
}

/* intelligence contextuelle : enjeu (MWI), confiance (métacognition), Kelly, trap */
/* indice de surprise — facteurs au-delà des maths */







function marketNameLabel(market){
  return {
    "1N2": "Résultat du match",
    OU: "Total buts",
    BTTS: "Les deux équipes marquent",
    CORNERS: "Corners",
    CARTONS: "Cartons",
  }[market] || market;
}

function humanPickLabel(pick){
  if(!pick) return "";
  return String(pick)
    .replace(/^Over ([0-9.]+)$/i, "Plus de $1 buts")
    .replace(/^Under ([0-9.]+)$/i, "Moins de $1 buts")
    .replace(/^BTTS Oui$/i, "Oui, les deux équipes marquent")
    .replace(/^BTTS Non$/i, "Non, les deux équipes ne marquent pas toutes les deux")
    .replace(/^Corners Over ([0-9.]+)$/i, "Plus de $1 corners")
    .replace(/^Corners Under ([0-9.]+)$/i, "Moins de $1 corners")
    .replace(/^Cartons Over ([0-9.]+)$/i, "Plus de $1 cartons")
    .replace(/^Cartons Under ([0-9.]+)$/i, "Moins de $1 cartons");
}

function humanMarketReason(reason){
  const text = String(reason || "").trim();
  if(!text) return "Pas assez de signal récent pour expliquer ce marché.";
  const parts = text.split(/\s*;\s*/).map(x=>x.trim()).filter(Boolean);
  const mapped = parts.map(part=>{
    let m = part.match(/^moyenne cartons recente ([0-9.]+) sous la ligne ([0-9.]+)/i);
    if(m) return `Les derniers matchs donnent en moyenne ${m[1]} cartons, donc sous la ligne ${m[2]}.`;
    m = part.match(/^moyenne cartons recente ([0-9.]+) au-dessus de la ligne ([0-9.]+)/i);
    if(m) return `Les derniers matchs donnent en moyenne ${m[1]} cartons, donc au-dessus de la ligne ${m[2]}.`;
    m = part.match(/^moyenne corners recente ([0-9.]+) sous la ligne ([0-9.]+)/i);
    if(m) return `Les derniers matchs donnent en moyenne ${m[1]} corners, donc sous la ligne ${m[2]}.`;
    m = part.match(/^moyenne corners recente ([0-9.]+) > ligne ([0-9.]+)/i);
    if(m) return `Les derniers matchs donnent en moyenne ${m[1]} corners, donc au-dessus de la ligne ${m[2]}.`;
    m = part.match(/^moyenne corners recente ([0-9.]+) au-dessus de la ligne ([0-9.]+)/i);
    if(m) return `Les derniers matchs donnent en moyenne ${m[1]} corners, donc au-dessus de la ligne ${m[2]}.`;
    m = part.match(/^BTTS recent faible \(([0-9]+)%\)/i);
    if(m) return `Le pari "les deux équipes marquent" sort seulement à ${m[1]}% récemment.`;
    m = part.match(/^BTTS recent eleve \(([0-9]+)%\)/i);
    if(m) return `Le pari "les deux équipes marquent" sort souvent récemment (${m[1]}%).`;
    m = part.match(/^BTTS recent moyen ([0-9]+)%/i);
    if(m) return `Le pari "les deux équipes marquent" est fréquent récemment (${m[1]}%).`;
    m = part.match(/^historique recent Over2\.5 moyen ([0-9]+)%/i);
    if(m) return `Les matchs récents dépassent 2.5 buts dans ${m[1]}% des cas.`;
    m = part.match(/^historique recent plutot Under \(([0-9]+)% Under2\.5\)/i);
    if(m) return `Les matchs récents restent sous 2.5 buts dans ${m[1]}% des cas.`;
    m = part.match(/^historique recent Under2\.5 ([0-9]+)%/i);
    if(m) return `Les matchs récents restent sous 2.5 buts dans ${m[1]}% des cas.`;
    m = part.match(/^historique recent trop ouvert \(([0-9]+)% Over2\.5\)/i);
    if(m) return `Les matchs récents sont très ouverts: plus de 2.5 buts dans ${m[1]}% des cas.`;
    m = part.match(/^signal historique >8\.5 corners ([0-9]+)%/i);
    if(m) return `Le seuil de 8.5 corners est souvent dépassé récemment (${m[1]}%).`;
    m = part.match(/^historique >3\.5 cartons ([0-9]+)%/i);
    if(m) return `Le seuil de 3.5 cartons est souvent dépassé récemment (${m[1]}%).`;
    if(part === "deux defenses recentes solides") return "Les deux défenses encaissent peu récemment.";
    if(part === "au moins une defense recente fragile") return "Au moins une défense encaisse beaucoup récemment.";
    if(part === "une equipe marque rarement") return "Une des deux équipes marque rarement récemment.";
    if(part === "clean sheets frequents d'un cote") return "Une des deux équipes garde souvent sa cage inviolée.";
    return part
      .replaceAll("recent", "récent")
      .replaceAll("defense", "défense")
      .replaceAll("equipe", "équipe")
      .replaceAll("eleve", "élevé")
      .replaceAll("plutot", "plutôt");
  });
  return mapped.join(" ");
}

function humanIntelSummary(summary){
  return String(summary || "")
    .replace("Prudence forte: un marche principal est contredit par le bilan recent des equipes.", "Prudence forte: un marché principal est contredit par le bilan récent des équipes.")
    .replace("Prudence: certains marches secondaires ou signaux terrain contredisent le modele.", "Prudence: certains marchés secondaires ou signaux terrain contredisent le modèle.")
    .replace("Bilan equipes plutot aligne avec les marches principaux.", "Bilan équipes plutôt aligné avec les marchés principaux.")
    .replace("Bilan equipes neutre ou echantillon encore limite.", "Bilan équipes neutre ou échantillon encore limité.");
}

function marketSignalLabel(verdict, impact){
  if(verdict==="avoid") return "À éviter";
  if(verdict==="watch") return "Prudence";
  if(verdict==="support") return impact >= 2 ? "Très cohérent" : "Cohérent";
  return "Neutre";
}

function impactText(impact){
  if(impact >= 2) return "Signal positif fort";
  if(impact === 1) return "Petit signal positif";
  if(impact === 0) return "Signal neutre";
  if(impact === -1) return "Petit signal de prudence";
  return "Contradiction forte";
}

function marketIntelligenceBlock(m,p){
  const intel = p.marketIntelligence;
  if(!intel) return "";
  const tone = intel.verdict==="no_bet" ? "#ff6b7d"
    : intel.verdict==="watch" ? "#ffd34e"
    : intel.verdict==="aligned" ? "#33e0a0"
    : "var(--muted)";
  const label = {
    no_bet: "No bet / prudence forte",
    watch: "Prudence",
    aligned: "Aligné",
    neutral: "Neutre",
  }[intel.verdict] || intel.verdict;
  const checks = (intel.checks || []).map(c=>{
    const cTone = c.verdict==="avoid" ? "#ff6b7d" : c.verdict==="watch" ? "#ffd34e" : c.verdict==="support" ? "#33e0a0" : "var(--muted)";
    return `<div class="market-check">
      <div class="market-check-top">
        <span class="market-name">${esc(marketNameLabel(c.market))}</span>
        <span class="market-pick">${esc(humanPickLabel(c.pick))}${c.prob!=null?` · ${pct(c.prob)}`:""}</span>
        <span class="market-signal" style="color:${cTone};border-color:${cTone}">${esc(marketSignalLabel(c.verdict, c.impact))}</span>
      </div>
      <div class="market-reason">${esc(humanMarketReason(c.reason))}</div>
      <div class="market-impact" style="color:${cTone}">${esc(impactText(c.impact))}</div>
    </div>`;
  }).join("");
  const prof = intel.profiles || {};
  const line = (side, name)=> {
    const x = prof[side] || {};
    if(!x.n) return `<div class="market-profile"><b>${esc(name)}</b><span>Historique récent limité</span></div>`;
    return `<div class="market-profile">
      <b>${esc(name)}</b>
      <span>${x.n} matchs récents</span>
      <span>Marque ${x.gfAvg} but/match</span>
      <span>Encaisse ${x.gaAvg} but/match</span>
      <span>+2.5 buts: ${pct(x.over25Rate)}</span>
      <span>Les deux marquent: ${pct(x.bttsRate)}</span>
      ${x.cornersAvg!=null?`<span>Corners: ${x.cornersAvg}/match</span>`:""}
    </div>`;
  };
  return `<div class="coh-note" style="border-color:${tone}; margin-top:12px;">
    <b>Bilan des marchés : ${label}</b>
    <div class="market-summary">${esc(humanIntelSummary(intel.summary))} Confiance du modèle : <b>${pct(intel.adjustedConfidence)}</b>${intel.confidenceAdj?` (${intel.confidenceAdj>0?"+":""}${Math.round(intel.confidenceAdj*100)} pts après contrôle des marchés)`:""}.</div>
    <div class="market-profiles">${line("home", m.home)}${line("away", m.away)}</div>
    ${checks?`<div class="market-checks">${checks}</div>`:""}
  </div>`;
}

function probBlock(m,p){
  const accordion = (title, content, delay, icon, open=false) => {
    if (!content || content.trim() === '') return '';
    return `<details class="anim-block anim-${delay}" ${open ? 'open' : ''}><summary>${icon} ${title}</summary><div style="padding-top:10px">${content}</div></details>`;
  };
  
  const marketsHtml = [marketsBlock(m,p), shotsBlock(m,p), cornersBlock(m,p), cardsBlock(m,p)].filter(Boolean).join('');
  const scenHalftime = [halftimeBlock(m,p), scenariosBlock(m,p)].filter(Boolean).join('');
  const contextHtml = [refereeBlock(p), h2hBlock(m), contextBlock(m,p), oddsBlock(m,p)].filter(Boolean).join('');
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

/* ===== ARBITRE ===== */
function refereeBlock(p) {
  if (!p || !p.referee || !p.referee.name) return "";
  const r = p.referee;
  return `<div style="margin:12px 0; padding:10px; background:var(--card-bg); border-left:4px solid #ffd34e; border-radius:4px;">
    <h3 style="color:#ffd34e; margin-bottom:4px; display:flex; align-items:center; gap:6px;">🧑‍⚖️ Arbitre : ${r.name} ${r.nation ? '('+r.nation+')' : ''}</h3>
    <ul style="margin:0; padding-left:20px; font-size:13px; color:var(--muted);">
      <li>Sévérité relative : <b>${r.severity?.toFixed(2) || 'N/D'}</b> <small>(${r.severitySrc || ''})</small></li>
      <li>Cartons par match : <b>${r.cardsAvg || 'N/D'}</b></li>
    </ul>
  </div>`;
}

/* ===== HEAD-TO-HEAD (confrontations directes réelles ESPN) ===== */


/* ===== COTES réelles + VALUE + KELLY (données ESPN/DraftKings) ===== */


/* Buts : total xG projeté + Over/Under multi-lignes (1.5 / 2.5 / 3.5).
   Tout dérivé de la grille Dixon-Coles réelle. */


/* BTTS (les deux marquent) Oui/Non + niveau de confiance (métacognition + netteté du marché) */


/* libellé du score : sa vraie probabilité (souvent ~12-15%, pas une certitude !) */
function scoreNote(p){
  const ts=(p.topScores&&p.topScores[0]);
  if(ts) return `score modal exact (${pct(ts.p)})`;
  return "score modal exact";
}

function exactScoresStrip(p){
  const scores=(p.topScores||[]).slice(0,5);
  if(!scores.length) return "";
  return `<div class="exact-strip anim-block anim-2">
    ${scores.map((s,i)=>`<div class="exact-chip ${i===0?"lead":""}">
      <span>${String(s.score).replace("-"," – ")}</span><b>${pct(s.p)}</b>
    </div>`).join("")}
  </div>`;
}

function scoreUncertaintyBlock(p){
  const scores=(p.topScores||[]).filter(s=>s&&s.p!=null);
  if(scores.length<2) return "";
  const top=scores[0], second=scores[1];
  const tight=(top.p-second.p)<0.02;
  const lowTop=top.p<0.16;
  if(!tight && !lowTop) return "";
    const near=scores.slice(0,5).map(s=>`${s.score} (${pct(s.p)})`).join(" · ");
  return `<div class="coh-note score-risk"><b>Score exact dispersé.</b> Le modal est à ${pct(top.p)}${tight?`, avec plusieurs scores au contact`:""}. Alternatives proches : ${near}.</div>`;
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


/* Marchés dérivés : Double Chance, Draw No Bet, top scores exacts.
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
    // le filtre par groupe n'a pas de sens dans ces vues agrégées.
    const gf=$("groupFilter"); if(gf) gf.style.display = (TAB==="BEST"||TAB==="GROUPS"||TAB==="BRACKET"||TAB==="SCANNER"||TAB==="STRATEGY")?"none":"";
    buildGroupFilter(); render();
    closeSidebar();   // referme la sidebar sur mobile après sélection
  };
});
$("groupFilter").onchange=()=>{ setGroup($("groupFilter").value); render(); };
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
let SERVER_READONLY = false;
async function checkServer(){
  try{ const r=await fetch("api/status",{cache:"no-store"});
    if(r.ok){ const st=await r.json(); SERVER_OK=true; SERVER_READONLY=!!st.readonly; return st; } }catch(_){}
  SERVER_OK=false; SERVER_READONLY=false; return null;
}
function fillAdminMatches(){
  const sel=$("adminMatch"); if(!sel) return;
  // matchs pertinents : à venir / en cours / déjà commencés
  const opts = MATCHES.map(m=>`<option value="${m.home}|${m.away}">${m.home} – ${m.away} (${(m.date||"").slice(5,16)})</option>`).join("");
  sel.innerHTML = opts;
}
function setAdminStatus(txt){ const e=$("adminStatus"); if(e) e.textContent=txt; }

function applyPublicSurface(){
  if(!IS_PUBLIC_SURFACE) return;
  document.documentElement.dataset.surface = "public";
  const adminToggle = $("toggleAdmin");
  if(adminToggle) adminToggle.remove();
  const adminPanel = $("adminPanel");
  if(adminPanel) adminPanel.remove();
  const roleSelect = $("roleSelect");
  if(roleSelect){
    roleSelect.querySelector('option[value="admin"]')?.remove();
    roleSelect.value = "analyst";
    roleSelect.classList.add("u-hidden");
    roleSelect.setAttribute("aria-hidden", "true");
  }
}


async function adminAction(act){
  if(SERVER_READONLY){
    setAdminStatus("Mode public lecture seule : actions administrateur desactivees.");
    $("adminHint").innerHTML = "Le site peut etre partage sans risque. Le refresh public passe par GitHub Actions, sans serveur local ni cle payante.";
    return;
  }
  if(!SERVER_OK){
    // mode hors-serveur : on ne peut pas exécuter Python -> on guide l'utilisateur
    // Windows : python | Linux/Mac : python3
    const py = navigator.platform.startsWith("Win") ? "python" : "python3";
    const cmds={refresh:`${py} -m collector.refresh`,
      predict:`${py} -m collector.pipeline predict && ${py} -m collector.embed`,
      sync:`${py} -m collector.live --sync && ${py} -m collector.refresh`};
    const c=cmds[act]||`${py} -m collector.refresh`;
    setAdminStatus("⚠️ Serveur non détecté — lance l'app via le serveur de contrôle.");
    $("adminHint").innerHTML = `En local : lance <code>${py} -m collector.server</code> ou execute <code>${c}</code>.<br>En public gratuit : declenche le workflow <code>Free Static Refresh</code> sur GitHub Actions.`;
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

const adminToggle = $("toggleAdmin");
if(adminToggle) adminToggle.onclick=async ()=>{
  const p=$("adminPanel");
  if(!p) return;
  const show = p.classList.contains("u-hidden");
  if(show) p.classList.remove("u-hidden"); else p.classList.add("u-hidden");
  if(show){
    fillAdminMatches();
    const st=await checkServer();
    if(st && st.readonly){
      setAdminStatus(`Mode public lecture seule · ${st.finished} termines / ${st.live} en cours / ${st.scheduled} a venir`);
      $("adminHint").innerHTML = "Actions administrateur desactivees sur l'URL publique. Les donnees se rafraichissent via GitHub Actions.";
      return;
    }
    if(st) setAdminStatus(`🎛️ Serveur connecté · ${st.finished} terminés / ${st.live} en cours / ${st.scheduled} à venir`);
    else { setAdminStatus("⚠️ Serveur non détecté (boutons en mode lecture seule).");
      const py2 = navigator.platform.startsWith("Win") ? "python" : "python3";
      $("adminHint").innerHTML = `Local : lance <code>${py2} -m collector.server</code>. Public gratuit : utilise le workflow <code>Free Static Refresh</code>.`; }
  }
};
document.querySelectorAll(".abtn").forEach(b=> b.onclick=()=>adminAction(b.dataset.act));

applyPublicSurface();
load();
