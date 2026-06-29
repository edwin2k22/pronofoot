"""
Pondération dynamique des effectifs — impact des ABSENCES sur λ (buts attendus).

Problème (point 4) : l'Elo collectif reste artificiellement haut quand un joueur
central (buteur/meneur) est blessé ou suspendu, jusqu'au prochain match perdu.

Solution : avant la grille de scores, si la COMPOSITION RÉELLE (XI officiel ESPN,
publié ~1 h avant le coup d'envoi) ne contient PAS un joueur à forte importance
offensive, on réduit λ proportionnellement à son poids dans la production de l'équipe.

RÈGLE N°1 — ZÉRO INVENTION :
  - On n'applique le malus QUE si l'on dispose d'un XI réel (officiel/probable ESPN).
  - Sans XI réel -> aucun ajustement (boost = 1.0), on ne devine pas les absents.

Importance offensive d'un joueur = mélange de données réelles :
  1) production réelle CDM 2026 (buts×3 + passes_déc×2 + tirs×0.3) si déjà joué
  2) statut "star" (présence d'une bio sourcée) -> poids plancher
  3) poids de poste (attaquant/meneur > défenseur)
Le poids relatif d'un joueur = sa part dans la somme des importances offensives
de l'effectif. Le malus de λ = part_du_joueur_absent × SENSIBILITÉ, borné.
"""
from __future__ import annotations
from collector.sources import player_bios as bios
from collector.models.lineup_impact import POS_OFFENSIVE

# fraction de l'importance offensive d'un absent réellement répercutée sur λ.
# 0.6 = prudent (un remplaçant compense en partie). Borné par MAX_DROP.
SENSITIVITY = 0.60
MAX_DROP = 0.22          # un seul XI ne peut pas faire chuter λ de plus de 22 %
MIN_IMPORTANCE = 0.05    # ignore le bruit (joueurs marginaux)


def _pos_off(poste, role=None):
    p = str(poste or "").upper().split("/")[0].strip()
    for key, w in POS_OFFENSIVE.items():
        if p.startswith(key):
            return w
    # repli via le rôle de la bio (texte FR)
    r = str(role or "").lower()
    if any(k in r for k in ("attaquant", "buteur", "avant-centre", "ailier")):
        return 1.0
    if any(k in r for k in ("meneur", "offensif", "créateur")):
        return 0.8
    if "milieu" in r:
        return 0.5
    if any(k in r for k in ("défenseur", "latéral", "arrière")):
        return 0.15
    if "gardien" in r:
        return 0.0
    return 0.4


def player_importance(player, real_stats=None):
    """Importance offensive brute d'un joueur (mélange données réelles)."""
    name = player.get("joueur") or player.get("name")
    if not name:
        return 0.0, name
    b = bios.get_bio(name)
    pos_w = _pos_off(player.get("poste"), (b or {}).get("role"))

    prod = 0.0
    if real_stats and name in real_stats:
        st = real_stats[name]
        prod = (st.get("buts", 0) or 0) * 3 + (st.get("passes_dec", 0) or 0) * 2 \
            + (st.get("tirs", 0) or 0) * 0.3

    # base de poste (toujours > 0 pour les postes offensifs) + bonus star + production réelle
    star_bonus = 1.2 if b else 0.0
    imp = pos_w * (1.0 + 0.4 * prod) + star_bonus
    return round(imp, 3), name


def availability_factor(roster, real_xi, real_stats=None):
    """
    roster   : effectif complet (liste de {joueur, poste, ...})
    real_xi  : liste de noms du XI RÉEL (officiel/probable ESPN) — ou None
    real_stats : dict {nom -> stats CDM} (optionnel)

    Renvoie {factor, missing, applied} :
      factor  = multiplicateur de λ (1.0 si pas de XI réel ou aucun absent notable)
      missing = liste des absents notables [{name, weight}]
      applied = bool (un XI réel a-t-il été utilisé ?)
    """
    out = {"factor": 1.0, "missing": [], "applied": False}
    if not roster or not real_xi:
        return out  # pas de compo réelle -> on ne devine rien (zéro invention)

    xi = {_norm(n) for n in real_xi}
    # index par nom de famille pour tolérer les variantes d'orthographe ESPN/bio
    xi_last = {_norm(n).split()[-1] for n in real_xi if _norm(n)}
    out["applied"] = True

    def _in_xi(name):
        nn = _norm(name)
        if nn in xi:
            return True
        last = nn.split()[-1] if nn else ""
        return bool(last) and last in xi_last

    # On ne pénalise QUE l'absence de joueurs CLÉS DOCUMENTÉS, c'est-à-dire :
    #   - soit une star (bio sourcée),
    #   - soit un joueur à forte production réelle CDM 2026.
    # La rotation de la profondeur de banc (remplaçants équivalents) n'est PAS
    # pénalisée : on évite le bruit et on reste honnête (zéro spéculation).
    #
    # "référence offensive" = somme des importances des joueurs CLÉS de l'effectif.
    key_players = []
    for pl in roster:
        name = pl.get("joueur") or pl.get("name")
        if not name:
            continue
        b = bios.get_bio(name)
        prod = 0.0
        if real_stats and name in real_stats:
            st = real_stats[name]
            prod = (st.get("buts", 0) or 0) * 3 + (st.get("passes_dec", 0) or 0) * 2
        is_key = bool(b) or prod >= 3          # star OU vrai producteur (≥1 but ou équiv.)
        if not is_key:
            continue
        imp, _ = player_importance(pl, real_stats)
        key_players.append((name, imp))

    if not key_players:
        return out                              # aucune star identifiée -> pas de malus

    ref_total = sum(i for _, i in key_players)
    drop = 0.0
    for name, imp in key_players:
        weight = imp / ref_total if ref_total else 0.0
        if not _in_xi(name):
            drop += weight
            out["missing"].append({"name": name, "weight": round(weight, 3)})

    # drop = part des stars absentes parmi les stars de l'effectif.
    # La part offensive d'une équipe portée par ses stars ≈ STAR_SHARE.
    STAR_SHARE = 0.55
    factor = 1.0 - min(MAX_DROP, drop * STAR_SHARE * SENSITIVITY)
    out["factor"] = round(factor, 4)
    out["missing"].sort(key=lambda x: -x["weight"])
    return out


def _norm(s):
    import re, unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s*\((G|D|M|F|GK|DF|CB|RB|LB|MF|DM|CM|AM|FW|CF|RW|LW|ST|SUB|C)\)\s*$", "", s, flags=re.I)
    return s.lower().strip()
