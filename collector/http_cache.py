"""
Couche réseau partagée : cache intelligent + limiteur de débit (rate limiter) par API.

Indispensable parce que chaque source a des limites différentes :
  - football-data.org : 10 requêtes / minute
  - API-Football free  : 100 requêtes / JOUR
  - openfootball / ESPN : fichiers statiques (pas de limite stricte mais on cache quand même)

Le cache évite de re-télécharger et te garde sous les quotas.
Aucune dépendance externe : urllib uniquement.

Fonctionnalités améliorées :
- TTLs préconfigurés par type de données
- Rate limiters préconfigurés par API
- Gestion de la révalidation (stale-while-revalidate) asynchrone
- Nettoyage du cache (suppression des entrées trop vieilles)
- Logging structuré sans conflits de configuration
"""
from __future__ import annotations
import json, os, time, hashlib, urllib.request, urllib.error, logging
import threading
from typing import Optional

# Configuration du logging (pas de basicConfig au niveau module pour éviter conflits)
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Ajoutez un handler par défaut seulement si aucun n'existe
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# TTLs préconfigurés par type de données (en secondes)
TTL_CONFIG = {
    "schedule": 86400,  # Calendrier : 1 jour
    "live": 30,         # Live scores : 30 secondes
    "stats": 3600,      # Stats : 1 heure
    "squads": 43200,    # Effectifs : 12 heures
    "ratings": 86400,   # Ratings : 1 jour
    "default": 3600,    # Par défaut : 1 heure
}

# Rate limiters préconfigurés par API (exemples - peuvent être personnalisés)
# Exemple d'utilisation: _get_limiter_for_url(url)
RATE_LIMITERS = {}


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
                logger.info(f"  [rate-limit] pause {sleep_for:.1f}s ...")
                time.sleep(sleep_for)
        self._timestamps.append(time.time())


def _cache_path(url: str, headers: dict) -> str:
    key = hashlib.sha256((url + json.dumps(headers, sort_keys=True)).encode()).hexdigest()[:24]
    return os.path.join(CACHE_DIR, key + ".json")


def _get_ttl_for_url(url: str) -> int:
    """Détermine le TTL approprié en fonction de l'URL."""
    url_lower = url.lower()
    if any(k in url_lower for k in ["live", "score", "event"]):
        return TTL_CONFIG["live"]
    elif any(k in url_lower for k in ["schedule", "fixture", "match"]):
        return TTL_CONFIG["schedule"]
    elif any(k in url_lower for k in ["squad", "player", "team"]):
        return TTL_CONFIG["squads"]
    elif any(k in url_lower for k in ["rating", "elo", "ranking"]):
        return TTL_CONFIG["ratings"]
    elif any(k in url_lower for k in ["stat", "stats"]):
        return TTL_CONFIG["stats"]
    return TTL_CONFIG["default"]


def _get_limiter_for_url(url: str) -> Optional[RateLimiter]:
    """
    Détermine le rate limiter approprié en fonction de l'URL.
    Retourne None si pas de limite configurée.
    """
    url_lower = url.lower()
    for api_name, limiter in RATE_LIMITERS.items():
        if api_name in url_lower and limiter is not None:
            return limiter
    return RATE_LIMITERS.get("default")


def clean_cache(max_age_days: int = 7) -> int:
    """
    Nettoie le cache en supprimant les fichiers plus vieux que max_age_days.
    Retourne le nombre de fichiers supprimés.
    """
    deleted = 0
    now = time.time()
    max_age = max_age_days * 86400
    for filename in os.listdir(CACHE_DIR):
        filepath = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(filepath):
            if now - os.path.getmtime(filepath) > max_age:
                os.remove(filepath)
                deleted += 1
    if deleted > 0:
        logger.info(f"  [cache] nettoyé {deleted} fichiers vieux de plus de {max_age_days} jours")
    return deleted


def clear_cache() -> None:
    """Supprime tous les fichiers du cache."""
    count = 0
    for filename in os.listdir(CACHE_DIR):
        filepath = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
            count += 1
    logger.info(f"  [cache] vidé : {count} fichiers supprimés")


def _fetch_and_cache(url: str, headers: dict, limiter: Optional[RateLimiter], path: str):
    """
    Fonction interne pour fetch et mettre à jour le cache en arrière-plan.
    """
    try:
        if limiter:
            limiter.wait()
        req = urllib.request.Request(url, headers={"User-Agent": "PronoFoot/2.0 (Intelligent Cache)", **headers})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info(f"  [network] fresh data pour {url[:60]}...")
    except Exception as e:
        logger.debug(f"  [background] échec revalidation {url[:60]}... -> {e}")


def get_json(url: str, headers: dict | None = None,
             limiter: RateLimiter | None = None,
             ttl: Optional[int] = None,
             data_type: Optional[str] = None,
             stale_while_revalidate: bool = True) -> dict | list | None:
    """
    GET avec cache intelligent et rate limiting.
    
    Args:
        url: URL à requêter
        headers: Headers HTTP supplémentaires
        limiter: RateLimiter à utiliser (ou None pour pas de limite)
        ttl: TTL en secondes (si None, déduit automatiquement depuis l'URL)
        data_type: Type de données pour TTL préconfiguré
        stale_while_revalidate: Si True, retourne le cache périmé immédiatement et revalide en arrière-plan
    
    Returns:
        Le JSON parsé, ou None en cas d'échec (offline-friendly).
    """
    headers = headers or {}
    path = _cache_path(url, headers)
    
    # Déterminer le TTL
    if ttl is None:
        if data_type and data_type in TTL_CONFIG:
            ttl = TTL_CONFIG[data_type]
        else:
            ttl = _get_ttl_for_url(url)

    # Vérifier le cache
    if os.path.exists(path):
        cache_age = time.time() - os.path.getmtime(path)
        if cache_age < ttl:
            logger.debug(f"  [cache] hit frais pour {url[:60]}...")
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        elif stale_while_revalidate:
            logger.info(f"  [cache] hit périmé (age {cache_age:.0f}s), utilisé en attendant revalidation")
            # Charger le cache périmé
            try:
                with open(path, encoding="utf-8") as f:
                    stale_data = json.load(f)
            except Exception:
                stale_data = None
            else:
                # Lancer la revalidation en arrière-plan
                thread = threading.Thread(
                    target=_fetch_and_cache,
                    args=(url, headers, limiter, path),
                    daemon=True
                )
                thread.start()
                # Retourner immédiatement le cache périmé
                return stale_data

    # Si pas de cache ou pas de stale-while-revalidate, faire la requête en premier plan
    if limiter:
        limiter.wait()

    req = urllib.request.Request(url, headers={"User-Agent": "PronoFoot/2.0 (Intelligent Cache)", **headers})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info(f"  [network] fresh data pour {url[:60]}...")
        return data
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        logger.warning(f"  [warn] échec requête {url[:60]}... -> {e}")
        # fallback : cache périmé vaut mieux que rien
        if os.path.exists(path):
            logger.info("  [info] utilisation du cache périmé en secours")
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return None
