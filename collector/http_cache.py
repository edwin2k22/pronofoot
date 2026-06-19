"""
Couche réseau partagée : cache disque + limiteur de débit (rate limiter).

Indispensable parce que chaque source a des limites différentes :
  - football-data.org : 10 requêtes / minute
  - API-Football free  : 100 requêtes / JOUR
  - StatsBomb / co.uk  : fichiers statiques (pas de limite stricte mais on cache quand même)

Le cache évite de re-télécharger et te garde sous les quotas.
Aucune dépendance externe : urllib uniquement.
"""
from __future__ import annotations
import json, os, time, hashlib, urllib.request, urllib.error

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class RateLimiter:
    """Limiteur simple : N appels max par fenêtre de `period` secondes."""
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._timestamps: list[float] = []

    def wait(self):
        now = time.time()
        # purge les timestamps hors fenêtre
        self._timestamps = [t for t in self._timestamps if now - t < self.period]
        if len(self._timestamps) >= self.max_calls:
            sleep_for = self.period - (now - self._timestamps[0]) + 0.05
            if sleep_for > 0:
                print(f"  [rate-limit] pause {sleep_for:.1f}s ...")
                time.sleep(sleep_for)
        self._timestamps.append(time.time())


def _cache_path(url: str, headers: dict) -> str:
    key = hashlib.sha256((url + json.dumps(headers, sort_keys=True)).encode()).hexdigest()[:24]
    return os.path.join(CACHE_DIR, key + ".json")


def get_json(url: str, headers: dict | None = None,
             limiter: RateLimiter | None = None,
             ttl: int = 3600) -> dict | list | None:
    """
    GET avec cache disque (TTL en secondes) et rate limiting.
    Retourne le JSON parsé, ou None en cas d'échec (offline-friendly).
    """
    headers = headers or {}
    path = _cache_path(url, headers)

    # cache frais ?
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    if limiter:
        limiter.wait()

    req = urllib.request.Request(url, headers={"User-Agent": "PronoFoot/1.0", **headers})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return data
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        print(f"  [warn] échec requête {url[:60]}... -> {e}")
        # fallback : cache périmé vaut mieux que rien
        if os.path.exists(path):
            print("  [info] utilisation du cache périmé en secours")
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return None
