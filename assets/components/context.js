// assets/components/context.js
import { pct } from '../core/utils.js';

export function attackQualityBlock(m,p){
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

export function availabilityBlock(m,p){
  const av=p.availability; if(!av) return "";
  const h=av.home||{}, a=av.away||{};
  const hHit=(h.applied && h.factor<1), aHit=(a.applied && a.factor<1);
  if(!hHit && !aHit) return "";
  const side=(t,x)=>{
    if(!(x.applied && x.factor<1)) return "";
    const pval=Math.round((1-x.factor)*100);
    const who=(x.missing||[]).map(z=>z.name).join(", ");
    return `<div style="flex:1">
      <div style="font-size:11px;color:var(--muted)">${t}</div>
      <div style="font-size:15px;font-weight:700;color:var(--danger)">−${pval}% <span style="font-size:11px;color:var(--muted)">buts attendus</span></div>
      <div style="font-size:10px;color:var(--muted)">absent(s) : ${who||"—"}</div>
    </div>`;
  };
  return `<div class="module"><h3 style="color:#ff7a7a">🩹 Absences clés <span class="mod-hint">compo officielle ESPN</span></h3>
    <div style="display:flex;gap:14px">${side(m.home,h)}${side(m.away,a)}</div>
    <div class="note" style="margin-top:8px">Quand un joueur majeur manque dans le XI officiel, le modèle réduit dynamiquement les buts attendus (λ) <b>avant</b> le calcul des probabilités. Aucun ajustement tant que la compo réelle n'est pas publiée.</div>
  </div>`;
}

export function upsetBlock(m,p){
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

export function contextBlock(m,p){
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
  const k=p.kelly;
  if(k){
    const lines=[["home",m.home],["draw","Nul"],["away",m.away]]
      .map(([key,lbl])=> k[key]&&k[key].kelly>0 ? `<div class="stat"><span>💰 Mise conseillée (${lbl})</span><span>${(k[key].kelly*100).toFixed(1)}% bankroll</span></div>`:"")
      .join("");
    if(lines) html += lines;
    else html += `<div class="note" style="margin-top:6px">💰 Kelly : aucune mise (pas de cotes saisies ou pas de value).</div>`;
  }
  const lm=p.lineMovement;
  if(lm && lm.opening){
    const op=lm.opening;
    const cur={odd1:m.odd1, oddX:m.oddX, odd2:m.odd2};
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
      html += `<div class="stat" style="margin-top:8px"><span>🎰 Cotes (ouverture)</span>
          <span>${op.odd1}/${op.oddX}/${op.odd2} <span style="color:var(--muted);font-size:11px">· ${lm.provider||""} · stables</span></span></div>`;
    }
  }
  html += `</div>`;

  const ko=p.knockout;
  if(ko){
    html += `<div style="margin-top:14px"><h3>🏆 Qualification (90' + prolong. + TAB)</h3>
      <div class="probbar"><div class="lbl"><span>${m.home} se qualifie</span><b>${pct(ko.qualifyHome)}</b></div><div class="track"><div class="b1" style="width:${ko.qualifyHome*100}%"></div></div></div>
      <div class="probbar"><div class="lbl"><span>${m.away} se qualifie</span><b>${pct(ko.qualifyAway)}</b></div><div class="track"><div class="b2" style="width:${ko.qualifyAway*100}%"></div></div></div>
      <div class="note" style="margin-top:4px">Si tirs au but : ${m.home} ${pct(ko.shootoutHome)} (Elo + sang-froid). ${ko.note}</div>
    </div>`;
  }
  if(p.ensemble && p.ensemble.weights){
    const w=p.ensemble.weights;
    const pc=v=>Math.round(v*100);
    const market = w.market!=null ? ` · Marché ${pc(w.market)}%` : "";
    html += `<div class="note" style="margin-top:8px">🧠 Modèle d'ensemble (poids appris sur les résultats) :
      Elo ${pc(w.elo)}% · Buts/xG ${pc(w.grid)}% · Forme ${pc(w.form)}%${market}${p.ensemble.T&&Math.abs(p.ensemble.T-1)>0.02?` · calibration T=${p.ensemble.T}`:""}</div>`;
  }
  if(p.dixonColes){
    html += `<div class="note" style="margin-top:8px">📐 Modèle : Dixon-Coles (ρ=${p.dixonColes.rho})${p.dixonColes.gamma>0?` + effet de choc (γ=${p.dixonColes.gamma})`:""}</div>`;
  }
  return html;
}
