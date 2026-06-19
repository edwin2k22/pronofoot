#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════
#  ProноFoot — lancement intelligent (live auto + serveur web)
#  Le scheduler s'active TOUT SEUL quand un match commence et se met
#  en veille quand rien ne joue. Tourne jusqu'à Ctrl+C.
# ════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")"

LIVE_POLL="${1:-30}"   # secondes entre actualisations EN MATCH (défaut 30)
PORT="${2:-8077}"      # port du serveur web (défaut 8077)

echo "🏆 ProноFoot — démarrage intelligent"
echo "   • Scheduler live : s'active à chaque coup d'envoi (poll ${LIVE_POLL}s en match)"
echo "   • App web : http://localhost:${PORT}/index.html"
echo "   • Ctrl+C pour tout arrêter"
echo ""

cleanup() { echo ""; echo "👋 Arrêt..."; kill "$SMART_PID" "$SERVER_PID" 2>/dev/null; exit 0; }
trap cleanup INT TERM

# 0) un refresh complet au démarrage (calendrier + ratings + effectifs)
echo "⚙️  Initialisation (refresh complet)..."
python3 -m collector.refresh >/dev/null 2>&1
echo "   ✅ prêt."
echo ""

# 1) scheduler live intelligent en arrière-plan
python3 -m collector.smart_live --live-poll "$LIVE_POLL" &
SMART_PID=$!

# 2) serveur web en arrière-plan
python3 -m http.server "$PORT" >/dev/null 2>&1 &
SERVER_PID=$!

wait

