// assets/core/utils.js

export const $ = id => document.getElementById(id);
export const pct = x => Math.round((x||0)*100) + "%";

const MATCH_MINUTES = 90, HT_BREAK = 15, STOPPAGE = 8;
const STALE_LIVE_GRACE = 10;

export function parseKickoff(dateStr){
  if(!dateStr) return null;
  const m = dateStr.match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?:\s*UTC([+-]\d{1,2})(?::?(\d{2}))?)?/);
  if(!m) return null;
  const [,Y,Mo,D,H,Mi,tzH,tzMin] = m;
  let t = Date.UTC(+Y, +Mo-1, +D, +H, +Mi);
  if(tzH!==undefined){
    const sign = tzH[0]==="-" ? -1 : 1;
    const offMin = (Math.abs(+tzH))*60 + (tzMin?+tzMin:0);
    t -= sign*offMin*60*1000;
  }
  return t;
}

export function effectiveStatus(m){
  if(m.status==="FINISHED") return "FINISHED";
  const ko = parseKickoff(m.date);
  const FULL = MATCH_MINUTES + HT_BREAK + STOPPAGE;
  const GRACE = FULL + 75;

  if(m.status==="LIVE"||m.status==="HT"){
    if(ko==null) return m.status;
    const el=(Date.now()-ko)/60000;
    if(el<0) return "SCHEDULED";
    if(!m.liveClock && el>FULL+STALE_LIVE_GRACE) return "AWAITING";
    if(el<=GRACE) return m.status;
    return "AWAITING";
  }

  if(ko==null) return m.status||"SCHEDULED";
  const elapsed = (Date.now() - ko)/60000;
  if(elapsed < 0) return "SCHEDULED";
  if(elapsed <= FULL) return "KICKOFF";
  return "AWAITING";
}

export function clockMinute(m){
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

export function fmtCountdown(ms){
  if(ms<=0) return "maintenant";
  const s=Math.floor(ms/1000), d=Math.floor(s/86400), h=Math.floor(s%86400/3600),
        mn=Math.floor(s%3600/60), sec=s%60;
  if(d>0) return `dans ${d}j ${h}h`;
  if(h>0) return `dans ${h}h ${mn}min`;
  if(mn>0) return `dans ${mn}min ${sec}s`;
  return `dans ${sec}s`;
}

export function countdown(m){
  const ko=parseKickoff(m.date); if(ko==null) return "";
  return fmtCountdown(ko - Date.now());
}

export function teamBadge(name){
  const init=(name||"?").replace(/[^A-Za-zÀ-ÿ ]/g,"").split(/\s+/).map(w=>w[0]).join("").slice(0,3).toUpperCase();
  let h=0; for(const c of (name||"")) h=(h*31+c.charCodeAt(0))%360;
  const bg=`hsl(${h},62%,58%)`;
  return `<span class="mi-badge" style="background:${bg}">${init}</span>`;
}

export function clean(n){ return (n||"").replace(/\s*\(GK\)|\s*\(C\)/g,""); }

export function dot(name){
  const s = (name||"").length % 3;
  const c = s===0?"#33e0a0":s===1?"#ffd34e":"#ff6b7d";
  const susp = /\(C\)/.test(name)?"":"";
  return `<span class="form-dot" style="background:${c}"></span>${susp}`;
}

export function ouLineRow(label, o){
  const over=o.over, under=o.under, overLead=over>=under;
  const uPct=Math.round(under*100), oPct=100-uPct;
  return `<div class="ou-row"><span class="ou-ln">${label}</span>
    <span class="ou-bar" title="Under ${pct(under)} · Over ${pct(over)}">
      <span class="ou-u${overLead?"":" win"}" style="width:${uPct}%">${uPct>=18?`U ${pct(under)}`:""}</span>
      <span class="ou-o${overLead?" win":""}" style="width:${oPct}%">${oPct>=18?`O ${pct(over)}`:""}</span>
      <span class="ou-mid"></span></span></div>`;
}

export function bioHtml(b){
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
