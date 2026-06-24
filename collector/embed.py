#!/usr/bin/env python3
"""
Embarque les données directement dans les pages HTML.

Pourquoi : l'aperçu sandbox (et l'ouverture en file://) bloque fetch() vers un
fichier local. En injectant les données dans la page, le dashboard s'affiche
TOUJOURS, même hors-ligne. Quand un vrai serveur tourne, le fetch live les
remplace automatiquement par la version à jour.

  - predictions.json -> index.html    (#embedded-data)
  - squads_2026.json -> scouting.html (#embedded-squads)

À lancer après chaque predict/refresh :
    python3 -m collector.embed
"""
from __future__ import annotations
import os, json, re, sys, datetime
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")


def _inject(html_path, data_path, marker_id, label):
    if not os.path.exists(data_path):
        print(f"❌ {data_path} introuvable — lance d'abord le pipeline.")
        return False
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    rx = re.compile(rf'(<script id="{marker_id}" type="application/json">)(.*?)(</script>)', re.S)
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    if not rx.search(html):
        print(f"❌ balise <script id=\"{marker_id}\"> absente de {os.path.basename(html_path)}")
        return False
    html = rx.sub(lambda m: m.group(1) + payload + m.group(3), html)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    cnt = len(data) if isinstance(data, list) else (len(data.get("picks", [])) if isinstance(data, dict) else 0)
    print(f"✅ {cnt} {label} embarqués dans {os.path.basename(html_path)} ({len(payload)//1024} Ko).")
    return True


def _stamp_build(html_path):
    """Injecte l'horodatage de génération (anti-cache visuel) dans <body data-build=...>."""
    build = datetime.datetime.now().strftime("%d/%m %H:%M")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    # met à jour ou ajoute l'attribut data-build sur <body>
    if re.search(r'<body[^>]*\sdata-build="[^"]*"', html):
        html = re.sub(r'(<body[^>]*\sdata-build=")[^"]*(")', rf'\g<1>{build}\g<2>', html, count=1)
    else:
        html = re.sub(r'<body(\s|>)', f'<body data-build="{build}"\\1', html, count=1)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return build


def main():
    _inject(os.path.join(ROOT, "index.html"),
            os.path.join(DATA, "predictions.json"), "embedded-data", "matchs")
    tp_path = os.path.join(DATA, "top_picks.json")
    if os.path.exists(tp_path):
        _inject(os.path.join(ROOT, "index.html"),
                tp_path, "embedded-toppicks", "meilleurs choix")
    feed_path = os.path.join(DATA, "live_feed.json")
    if os.path.exists(feed_path):
        _inject(os.path.join(ROOT, "index.html"),
                feed_path, "embedded-feed", "événements live")
    pnl_path = os.path.join(DATA, "pnl.json")
    if os.path.exists(pnl_path):
        _inject(os.path.join(ROOT, "index.html"),
                pnl_path, "embedded-pnl", "PnL/ROI")
    combo_path = os.path.join(DATA, "combo_history.json")
    if os.path.exists(combo_path):
        _inject(os.path.join(ROOT, "index.html"),
                combo_path, "embedded-combo", "Historique combinés")
    st_path = os.path.join(DATA, "standings.json")
    if os.path.exists(st_path):
        _inject(os.path.join(ROOT, "index.html"),
                st_path, "embedded-standings", "classements groupes")
    h2h_path = os.path.join(DATA, "h2h.json")
    if os.path.exists(h2h_path):
        _inject(os.path.join(ROOT, "index.html"),
                h2h_path, "embedded-h2h", "confrontations H2H")
    _inject(os.path.join(ROOT, "scouting.html"),
            os.path.join(DATA, "squads_2026.json"), "embedded-squads", "effectifs")
    b = _stamp_build(os.path.join(ROOT, "index.html"))
    _stamp_build(os.path.join(ROOT, "scouting.html"))
    print(f"🕒 build estampillé : {b}")


if __name__ == "__main__":
    main()
