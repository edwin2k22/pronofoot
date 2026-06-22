// assets/core/state.js

export let MATCHES = [];
export let TAB = "SCHEDULED";
export let GROUP = "Tous";
export let SELECTED = null;
export let TOPPICKS = null;
export let LIVEFEED = [];
export let PNL = null;
export let STANDINGS = [];
export let H2H = {};
export let FAV_TEAMS = [];

try { 
  FAV_TEAMS = JSON.parse(localStorage.getItem("prono_favs")) || []; 
} catch(e){}

export function setMatches(data) { MATCHES = data; window.__PRONOFOOT_MATCHES = MATCHES; }
export function setTab(tab) { TAB = tab; }
export function setGroup(group) { GROUP = group; }
export function setSelected(selected) { SELECTED = selected; }
export function setTopPicks(picks) { TOPPICKS = picks; }
export function setLiveFeed(feed) { LIVEFEED = feed; }
export function setPnl(pnl) { PNL = pnl; }
export function setStandings(st) { STANDINGS = st; }
export function setH2h(h2h) { H2H = h2h; }
export function setFavTeams(favs) { FAV_TEAMS = favs; }
