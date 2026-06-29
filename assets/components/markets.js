// assets/components/markets.js
import { pct } from '../core/utils.js';

export function marketsBlock(m,p){
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
  if(ts && ts.length) out += `<div style="font-size:11.5px;color:var(--muted);margin:9px 0 3px">Scores exacts proches (top ${Math.min(5, ts.length)})</div>
    <div class="mk-chips">
      ${ts.map(s=>`<div class="mk-chip"><span class="k">score</span><span class="v">${s.score} · ${pct(s.p)}</span></div>`).join("")}
    </div>`;
  return out + `</div>`;
}

export function ouBlock(m,p){
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

export function bttsBlock(p){
  const c=p.bttsConf;
  const yes=p.btts, no=1-yes;
  const confTxt = c ? ` · confiance <b class="conf-${c.label}">${c.label}</b>` : "";
  const pick = c ? c.pick : (yes>=0.5?"Oui":"Non");
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
