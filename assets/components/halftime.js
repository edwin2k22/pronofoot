// assets/components/halftime.js
import { pct } from '../core/utils.js';

export function halftimeBlock(m,p){
  const h=p.halftime;
  if(!h) return "";
  
  const realHt = (m.analysis && m.analysis.events && m.analysis.events.halftime) ? m.analysis.events.halftime : null;
  const isStarted = m.status === 'IN_PROGRESS' || m.status === 'FINISHED' || m.status === 'LIVE' || m.status === 'HT';
  
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
