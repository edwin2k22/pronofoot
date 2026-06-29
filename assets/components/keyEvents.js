export function keyEventsBlock(m) {
  const ev = m.analysis && m.analysis.events;
  if (!ev) return "";
  const keyEvents = ev.key_events || [];
  if (keyEvents.length === 0) return "";
  
  const rows = keyEvents.map(k => {
    let teamName = k.team ? ` <small style="color:var(--muted)">(${k.team})</small>` : '';
    let playerText = k.player ? `<b>${k.player}</b>` : '';
    if (k.type === 'substitution') {
      playerText = `<b>${k.player_in}</b> 🟢 / <b>${k.player_out}</b> 🔴`;
    }
    
    return `<div class="stat">
      <span>${k.minute}' ${k.desc}</span>
      <span>${playerText}${teamName}</span>
    </div>`;
  }).join("");
  
  return `<div class="module mod-players"><h3>⏱ Faits Marquants (Extraits par NLP)</h3>
    <div style="display:flex;flex-direction:column;gap:4px">
      ${rows}
    </div>
  </div>`;
}
