#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════
#  ProноFoot — installation des services systemd (vrai 24/7)
#
#  Installe deux services :
#    • pronofoot-live  : scheduler live intelligent (s'active aux coups d'envoi)
#    • pronofoot-web   : serveur web (app sur le port 8077)
#
#  Ils démarrent au boot et redémarrent automatiquement en cas de crash.
#
#  Usage :   sudo ./deploy/install.sh
#  (à lancer depuis le dossier prono-app/, en sudo pour écrire dans /etc/systemd)
# ════════════════════════════════════════════════════════════════════
set -euo pipefail

# --- détection automatique du contexte ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# l'utilisateur réel (pas root) qui fera tourner les services
RUN_USER="${SUDO_USER:-$(id -un)}"
SYSTEMD_DIR="/etc/systemd/system"

echo "🏆 Installation ProноFoot (systemd)"
echo "   • Projet      : $PROJECT_DIR"
echo "   • Utilisateur : $RUN_USER"
echo ""

if [ "$(id -u)" -ne 0 ]; then
  echo "❌ Lance ce script en sudo :  sudo ./deploy/install.sh"
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "❌ systemd introuvable sur ce système."
  echo "   Sans systemd, utilise plutôt :  nohup ./start.sh &"
  exit 1
fi

# --- génère les unités avec le bon chemin/utilisateur ---
for svc in pronofoot-live pronofoot-web; do
  src="$PROJECT_DIR/deploy/${svc}.service"
  dst="$SYSTEMD_DIR/${svc}.service"
  sed -e "s|__USER__|$RUN_USER|g" -e "s|__DIR__|$PROJECT_DIR|g" "$src" > "$dst"
  echo "   ✅ installé : $dst"
done

# --- (re)chargement + activation + démarrage ---
systemctl daemon-reload
systemctl enable pronofoot-live pronofoot-web
systemctl restart pronofoot-live pronofoot-web

echo ""
echo "✅ Services démarrés et activés au boot."
echo ""
echo "📋 Commandes utiles :"
echo "   systemctl status pronofoot-live      # état du scheduler"
echo "   systemctl status pronofoot-web       # état du serveur web"
echo "   journalctl -u pronofoot-live -f      # voir le live en direct"
echo "   sudo systemctl restart pronofoot-live"
echo "   sudo systemctl stop pronofoot-live pronofoot-web"
echo ""
echo "🌐 App : http://localhost:8077/index.html"
