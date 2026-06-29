"""
Serveur de contrôle ProноFoot — sert l'app ET expose des boutons-actions.

Permet de piloter l'app depuis l'interface (boutons) au lieu de la ligne de commande :
  GET  /                      -> redirige vers index.html
  GET  /<fichier>            -> sert les fichiers statiques (index.html, scouting.html, data…)
  GET  /api/status           -> état (nb matchs, terminés, calibration)
  POST /api/refresh          -> lance le refresh complet (ingest+calibrate+predict+embed)
  POST /api/predict          -> recalcule seulement les pronostics
  POST /api/setscore         -> {home, away, hg, ag, state} : saisit un score puis refresh
  POST /api/sync             -> tire les scores finaux d'openfootball puis refresh

Lancement :  python3 -m collector.server          (port 8077 par défaut)
             python3 -m collector.server 9000      (port custom)
"""
from __future__ import annotations
import sys, os, json, io, contextlib
import datetime as _dt
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # /home/user/prono-app
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
READONLY = os.getenv("PRONOFOOT_READONLY", "0").strip().lower() in ("1", "true", "yes", "on")

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
        ".css": "text/css", ".json": "application/json; charset=utf-8",
        ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml"}


def _run(fn):
    """Exécute une fonction du pipeline en capturant sa sortie (pour le log UI)."""
    buf = io.StringIO()
    ok = True
    try:
        with contextlib.redirect_stdout(buf):
            fn()
    except Exception as e:  # noqa: BLE001
        ok = False
        buf.write(f"\n❌ ERREUR : {e}")
    return ok, buf.getvalue()


def do_refresh():
    from collector import refresh
    return _run(refresh.main)


def do_predict():
    from collector import pipeline, embed
    def _f():
        pipeline.predict()
        embed.main()
    return _run(_f)


def do_setscore(home, away, hg, ag, state="FINISHED"):
    from collector import live, refresh, pipeline, embed
    def _f():
        live.set_live(home, away, int(hg), int(ag), state=state)
        if state == "FINISHED":
            refresh.main()      # ré-ingère + recalibre + predict + embed
        else:
            # LIVE / HT : on régénère les pronostics + l'embed pour refléter le live
            pipeline.predict()
            embed.main()
    return _run(_f)


def do_sync():
    from collector import live, refresh
    def _f():
        live.sync_openfootball()
        refresh.main()
    return _run(_f)


def _status():
    p = os.path.join(DATA, "predictions.json")
    out = {"matches": 0, "finished": 0, "live": 0, "scheduled": 0, "calibration": None, "readonly": READONLY}
    try:
        d = json.load(open(p, encoding="utf-8"))
        out["matches"] = len(d)
        states = [_effective_status(m) for m in d]
        out["finished"] = sum(1 for s in states if s == "FINISHED")
        out["live"] = sum(1 for s in states if s in ("LIVE", "HT", "KICKOFF"))
        out["scheduled"] = sum(1 for s in states if s in ("SCHEDULED", "AWAITING"))
    except Exception:
        pass
    try:
        out["calibration"] = json.load(open(os.path.join(DATA, "calibration.json"), encoding="utf-8"))
    except Exception:
        pass
    return out


def _parse_kickoff(date_str):
    if not date_str:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?:\s*UTC([+-]\d{1,2})(?::?(\d{2}))?)?", date_str)
    if not m:
        return None
    y, mo, d, h, mi, tz_h, tz_min = m.groups()
    t = _dt.datetime(int(y), int(mo), int(d), int(h), int(mi), tzinfo=_dt.timezone.utc)
    if tz_h is not None:
        sign = -1 if tz_h.startswith("-") else 1
        off = _dt.timedelta(minutes=abs(int(tz_h)) * 60 + (int(tz_min) if tz_min else 0))
        t -= sign * off
    return t


def _effective_status(match):
    if match.get("status") == "FINISHED":
        return "FINISHED"
    ko = _parse_kickoff(match.get("date"))
    full = 90 + 15 + 8
    stale_grace = 10
    long_grace = full + 75
    status = match.get("status") or "SCHEDULED"
    if status in ("LIVE", "HT"):
        if ko is None:
            return status
        elapsed = (_dt.datetime.now(_dt.timezone.utc) - ko).total_seconds() / 60
        if elapsed < 0:
            return "SCHEDULED"
        if not match.get("liveClock") and elapsed > full + stale_grace:
            return "AWAITING"
        if elapsed <= long_grace:
            return status
        return "AWAITING"
    if ko is None:
        return status
    elapsed = (_dt.datetime.now(_dt.timezone.utc) - ko).total_seconds() / 60
    if elapsed < 0:
        return "SCHEDULED"
    if elapsed <= full:
        return "KICKOFF"
    return "AWAITING"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass   # client a fermé la connexion (ex. rechargement) — sans gravité

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/status":
            return self._send(200, _status())
        if path == "/api/timeline":
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            home = qs.get("home", [""])[0]
            away = qs.get("away", [""])[0]
            from collector.sources import espn_stats
            ev = espn_stats.find_event(home, away)
            if not ev:
                return self._send(404, {"error": "Match non trouvé sur ESPN", "home": home, "away": away})
            return self._send(200, espn_stats.get_timeline(ev["id"]))
            
        if path in ("/", ""):
            path = "/index.html"
        # fichier statique
        rel = path.lstrip("/")
        full = os.path.normpath(os.path.join(ROOT, rel))
        if not full.startswith(ROOT) or not os.path.isfile(full):
            return self._send(404, {"error": "not found", "path": path})
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as f:
            self._send(200, f.read(), MIME.get(ext, "application/octet-stream"))

    def do_POST(self):
        if READONLY:
            return self._send(403, {
                "ok": False,
                "error": "Mode public lecture seule : actions administrateur désactivées."
            })
        path = self.path.split("?")[0]
        ln = int(self.headers.get("Content-Length", 0) or 0)
        try:
            payload = json.loads(self.rfile.read(ln) or "{}") if ln else {}
        except Exception:
            payload = {}
        if path == "/api/refresh":
            ok, log = do_refresh()
        elif path == "/api/predict":
            ok, log = do_predict()
        elif path == "/api/sync":
            ok, log = do_sync()
        elif path == "/api/setscore":
            try:
                ok, log = do_setscore(payload["home"], payload["away"],
                                      payload["hg"], payload["ag"],
                                      payload.get("state", "FINISHED"))
            except KeyError as e:
                return self._send(400, {"ok": False, "error": f"champ manquant : {e}"})
        else:
            return self._send(404, {"ok": False, "error": "route inconnue"})
        return self._send(200, {"ok": ok, "log": log, "status": _status()})

    def log_message(self, *a):   # silencieux
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("PORT", os.getenv("PRONOFOOT_PORT", "8077")))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"🎛️  ProноFoot control server : http://localhost:{port}/index.html")
    print("   Boutons actifs dans l'app (refresh / saisie score / sync).")
    print("   Ctrl+C pour arrêter.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Arrêt.")


if __name__ == "__main__":
    main()
