#!/usr/bin/env bash
# Désinstalle les services systemd ProноFoot.
# Usage :  sudo ./deploy/uninstall.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "❌ Lance en sudo :  sudo ./deploy/uninstall.sh"
  exit 1
fi

for svc in pronofoot-live pronofoot-web; do
  systemctl stop "$svc" 2>/dev/null || true
  systemctl disable "$svc" 2>/dev/null || true
  rm -f "/etc/systemd/system/${svc}.service"
  echo "   🗑  supprimé : $svc"
done

systemctl daemon-reload
echo "✅ Services ProноFoot désinstallés."
