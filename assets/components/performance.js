// assets/components/performance.js
import { PNL, MATCHES } from '../core/state.js';
import { $ } from '../core/utils.js';

export function renderPerf(){
  const roiEl=$("heroRoi"), subEl=$("heroRoiSub");
  if(roiEl && PNL && PNL.value){
    const v=PNL.value, y=v.yield, n=v.bets, small=(n||0)<25;
    if(y==null){ roiEl.textContent="N/D"; roiEl.style.color="var(--muted)"; subEl.textContent="cotes insuffisantes"; }
    else{
      roiEl.textContent=(y>0?"+":"")+y+"%";
      roiEl.style.color = small ? "var(--muted)" : (y>0?"var(--acc)":(y<0?"var(--danger)":"var(--muted)"));
      subEl.innerHTML = small
        ? `${v.pnl>0?"+":""}${v.pnl}u · <span style="color:var(--warn)">échantillon ${n} (peu fiable)</span>`
        : `${v.pnl>0?"+":""}${v.pnl}u sur ${n} value bets`;
    }
    const card=$("heroPerfCard");
    if(card) card.title=`ROI value: ${y}% (${n} paris) · favori 1N2: ${PNL.favorite?PNL.favorite.yield:"—"}% · échantillon ${PNL.sampleWithOdds} matchs avec cotes`;
  } else if(roiEl){ roiEl.textContent="—"; subEl.textContent="en attente de cotes"; }
  drawSpark();
}

export function drawSpark(){
  const svg=$("perfSpark"); if(!svg) return;
  const played=MATCHES.filter(m=>m.status==="FINISHED"&&m.analysis)
    .sort((a,b)=>(a.date||"").localeCompare(b.date||""));
  if(played.length<2){ svg.innerHTML=""; return; }
  let ok=0; const pts=[];
  played.forEach((m,i)=>{ if(m.analysis.predictionCorrect)ok++; pts.push(ok/(i+1)); });
  const W=120,H=28,n=pts.length;
  const x=i=>i/(n-1)*W;
  const y=v=>H-2-v*(H-4);
  const d=pts.map((v,i)=>`${i?"L":"M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last=pts[pts.length-1];
  const col=last>=0.5?"#4ee1a0":"#ffcf5c";
  svg.innerHTML=`<polyline points="${pts.map((v,i)=>x(i).toFixed(1)+","+y(v).toFixed(1)).join(" ")}"
      fill="none" stroke="${col}" stroke-width="1.6"/>
      <line x1="0" y1="${y(0.5)}" x2="${W}" y2="${y(0.5)}" stroke="#ffffff22" stroke-dasharray="2 2"/>`;
}
