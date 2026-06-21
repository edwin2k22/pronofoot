# Évaluation des pronostics en direct (`evaluerPronostic`)

**Date :** 2026-06-21
**Statut :** Design validé (en attente de plan d'implémentation)

## Objectif

Pendant un match en direct, évaluer en temps réel si chaque pronostic du modèle est en bonne voie, gagné définitivement, mort, ou incertain — et l'afficher par un code couleur évolutif. La fonction remplit le vide actuel : `vsTable()` compare déjà prono vs résultat pour les matchs **terminés**, mais rien ne suit l'évolution **pendant** le match.

## Décisions clés (validées en brainstorming)

| # | Décision | Alternative écartée |
|---|---|---|
| Portée | **C** : moteur + panneau de détail live + indicateur sur carte de liste | A (moteur seul), B (sans indicateur carte) |
| Nature de `prono` | **B** : `evaluerPronostic(match, m.prediction)` renvoie un tableau d'évaluations, une par marché | A (un seul pari), C (un id de marché) |
| Stats live | **C** : le pipeline enrichit `m.liveStats`, la fonction consomme l'objet enrichi | A (branchement pipeline lourd), B (frontend autonome via endpoint) |
| Approche | **B** : registre de stratégies par marché (`EVALUATORS`) | A (monolithe), C (OOP) |
| Source de données | **ESPN déjà utilisé** — `summary?event=` fournit corners/cartons/tirs/HT en live | API-Football, Sportmonks (payants) |

## Architecture & flux de données

```
Pendant un match LIVE, ESPN summary endpoint
  (DÉJÀ appelé par espn_live.py:81 via espn_ingest)
        │
        ▼
match_stats_real.json   ← corners/cartons/tirs live (déjà peuplé)
match_events_real.json  ← buts/cartons/score MT live (déjà peuplé)
        │
        ▼  (NOUVEAU — pipeline enrichit le match exposé)
m.liveStats = { homeCards, awayCards, homeCorners, awayCorners,
                homeShots, awayShots, halftime, ... }
m.liveScore = "3-0"  (déjà existant)
        │
        ▼  (smartReload recharge predictions.json toutes les 20s)
evaluerPronostic(m, m.prediction)
        │
        ▼  renvoie un tableau normalisé
[ {key, label, prono, reel, couleur, reversible, note}, ... ]
        │
        ├──► panneau de détail LIVE (tableau coloré)
        └──► indicateur compact sur la carte de match (liste)
```

**Principe directeur : zéro invention.** Si `m.liveStats` est absent (ESPN n'a pas encore renvoyé de boxscore, ou match en `KICKOFF`), seuls les marchés basés sur le score sont évalués ; les marchés stats renvoient `couleur: "INCONNU"`, jamais une couleur de devinette.

## Le moteur `evaluerPronostic`

### Signature

```js
function evaluerPronostic(match, prediction) → Evaluation[]
```

où `Evaluation` est normalisé :

```js
{
  key: "OVER_2.5",          // identifiant de marché
  label: "Over 2.5 buts",   // libellé affiché
  prono: "Over (83%)",      // ce que le modèle avait prévu
  reel: "3 buts (Over)",    // situation actuelle
  couleur: "VERT_DEFINITIF",// voir palette ci-dessous
  reversible: false,        // le prono peut-il redevenir non-vert ?
  note: null                // texte optionnel (ex: "seuil atteint")
}
```

### Palette de couleurs (6 statuts)

| Couleur | Constante | Icône | Sens |
|---|---|:---:|---|
| 🟢 Vert définitif | `VERT_DEFINITIF` | ✅ | condition remplie **et** irréversible (over atteint, BTTS validé…) ou match fini + gagné |
| 🟢 Vert provisoire | `VERT_PROVISOIRE` | 🟢 | condition remplie MAIS réversible (mène au score mais match en cours) |
| ⚪ Neutre | `NEUTRE` | ⚪ | pas encore remplie, encore atteignable |
| 🔴 Rouge provisoire | `ROUGE_PROVISOIRE` | 🔴 | mathématiquement mort (under cassé au 3e but) mais match en cours |
| 🔴 Rouge définitif | `ROUGE_DEFINITIF` | ❌ | match fini + perdu |
| ⬜ Inconnu | `INCONNU` | — | donnée live manquante (jamais deviné) |

### Registre des stratégies `EVALUATORS`

Chaque stratégie reçoit un `ctx` pré-construit et renvoie une `Evaluation` (ou `null` si la donnée n'existe pas).

```js
const EVALUATORS = {
  "1N2":         eval1N2,          // réversible
  "DC":          evalDoubleChance, // réversible
  "DNB":         evalDNB,          // réversible (nul = remboursé)
  "SCORE_EXACT": evalScoreExact,   // réversible
  "OVER":        evalOverUnder,    // réversible si under / définitif si over atteint
  "BTTS":        evalBTTS,         // Oui = définitif · Non = rouge définitif si 2 équipes ont marqué
  "CORNERS_OU":  evalCorners,      // pareil qu'Over (stats live)
  "CARDS_OU":    evalCards,        // pareil qu'Over (stats live)
  "SHOTS_OU":    evalShots,        // pareil qu'Over (stats live)
  "HT_SCORE":    evalHTScore,      // réversible puis figé au HT
};
```

### Le contexte `ctx` (extrait une fois, réutilisé par toutes les stratégies)

```js
const ctx = {
  status: "LIVE",            // LIVE / HT / FINISHED
  minute: 67,                // depuis liveClock parsé
  gh: 3, ga: 0,              // buts home/away (depuis liveScore)
  total: 3,                  // gh+ga
  bttsNow: false,            // gh>0 && ga>0
  liveStats: m.liveStats,    // corners/cartons/tirs/HT (peut être null)
  p: prediction,             // la prédiction complète
  isFinal: status === "FINISHED",
};
```

### Règle de décision commune (cœur logique)

Chaque stratégie calcule trois booléens puis la couleur suit :

```js
const conditionOK    = verifierCondition(marché, score, liveStats);
const encorePossible = peutEncoreSeRealiser(marché, score, minute, status);
const irreversible   = estIrreversible(marché);

// table de vérité -> couleur
if (isFinal)         → conditionOK ? VERT_DEFINITIF : ROUGE_DEFINITIF
if (conditionOK)     → irreversible ? VERT_DEFINITIF : VERT_PROVISOIRE
if (!encorePossible) → ROUGE_PROVISOIRE
else                 → NEUTRE
```

### Exemples concrets

| Marché | Contexte | Résultat |
|---|---|---|
| Over 2.5, 0-0 à 30' | conditionKO, encore possible | ⚪ Neutre |
| Over 2.5, 2-1 à 80' | conditionOK, irréversible | ✅ Vert définitif |
| Under 2.5, 2-1 à 80' | conditionKO, plus possible | 🔴 Rouge provisoire |
| BTTS Non, 1-1 à 50' | 2 équipes ont marqué, fait acquis | 🔴 Rouge définitif |

## Backend — enrichissement de `m.liveStats`

### Le problème

`predictions.json` expose déjà `m.liveScore` / `m.liveClock` (pipeline.py:915-918). Mais les **stats live** (corners/cartons/tirs/HT) ne sont pas exposées pendant le match — elles ne le sont qu'à travers `m.analysis` pour les matchs finis (`_analyze_finished`, pipeline.py:271-272). Il faut donc ajouter un champ `m.liveStats` **pour les matchs LIVE/HT uniquement**.

### La fonction d'enrichissement

Nouvelle fonction dans `pipeline.py`, à côté de `_analyze_finished`. Elle lit les fichiers JSON directement (comme le fait déjà la lecture inline à la ligne 399 pour `match_stats_real.json`) :

```python
def _live_stats(home, away) -> dict | None:
    """Stats temps réel d'un match en cours, lues dans les fichiers
    déjà peuplés par espn_ingest (corners/cartons/tirs/score MT).
    Renvoie None si aucune donnée live n'est encore disponible."""
    def _read(name):
        path = os.path.join(DATA_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    stats = _read("match_stats_real.json")
    events = _read("match_events_real.json")
    key = f"{home}|{away}"
    s = stats.get(key); e = events.get(key)
    if not s and not e:
        return None
    return {
        "homeCards":   s.get("home_cards"),
        "awayCards":   s.get("away_cards"),
        "homeCorners": s.get("home_corners"),
        "awayCorners": s.get("away_corners"),
        "homeShots":   s.get("home_shots"),
        "awayShots":   s.get("away_shots"),
        "homeShotsOn": s.get("home_shots_on"),
        "awayShotsOn": s.get("away_shots_on"),
        "halftime":    e.get("halftime") if e else None,
        "asOf":        s.get("source_espn"),
    }
```

(`DATA_DIR` et `json` sont déjà importés et utilisés par `_analyze_finished` et alentour — pas de nouvel import.)

### Le branchement

Dans `predict()`, bloc lignes 915-918 où `live_score` est déjà construit :

```python
live_score = ...
live_clock = ...
live_stats = _live_stats(mt["home"], mt["away"]) if mt["status"] in ("LIVE", "HT") else None
```

Et dans le dict `out.append({...})` (ligne 920), ajout du champ :

```python
"liveStats": live_stats,
```

### Respect de l'existant

1. **Zéro nouvelle source** — on lit les fichiers que `espn_ingest` peuple *déjà* pendant le live (`espn_live.py:81` appelle `ingest_match(force=True)` à chaque cycle).
2. **Zéro duplication** — `_analyze_finished` lit la base pour les matchs finis ; `_live_stats` lit les fichiers JSON pour le live. Pas de chevauchement.
3. **Contrat net** — `m.liveStats` vaut `null` pour SCHEDULED/FINISHED, et peut valoir `null` pour un LIVE récent. Le frontend gère ce `null` → marchés stats en `INCONNU`.
4. **Pas de souci de fraîcheur** — `smart_live.py` appelle déjà `pipeline.predict()` à chaque cycle live, donc `m.liveStats` se rafraîchit au rythme du poll (30s par défaut).

## UI — panneau de détail + indicateur carte

### A. Panneau de détail LIVE (`renderLive`)

On enrichit `renderLive(m)` (app.js:939) en ajoutant, **entre la scoreline et le verdict**, un tableau d'évaluation qui appelle `evaluerPronostic(m, m.prediction)`. Le tableau s'affiche **en plus** du `probBlock` existant (qui reste le repère d'avant-match — transparence sur ce que le modèle disait avant).

Une nouvelle fonction `renderLiveEval(m)` :
1. Appelle `evaluerPronostic(m, m.prediction)` → `Evaluation[]`
2. Mappe chaque `Evaluation` en ligne HTML avec classe CSS selon `couleur`
3. Renvoie une chaîne HTML insérée dans `renderLive`

**Comportement au FT** : quand le match passe `FINISHED`, `showDetail` bascule sur `renderFinished` qui utilise déjà `vsTable()`. `vsTable` est conservé intact (pas de migration du tableau live au FT — il marche déjà et on évite de réécrire).

### B. Indicateur compact sur la carte de liste (`render`)

Sur les cartes de match du tableau principal (onglets À venir / En cours), un mini-statut pour les matchs LIVE, à côté du badge minute existant (~ligne 527).

Calcul : `evaluerPronostic(m, m.prediction)` → on compte les verts (`VERT_*`) sur le total évaluable (hors `INCONNU`). Une nouvelle fonction `liveEvalBadge(m)` renvoie le HTML.

Trois variantes selon le ratio :
- `🟢 X/Y en bonne voie` (majorité de verts, fond vert clair)
- `🟡 X/Y en bonne voie` (mi-chemin, fond jaune)
- `🔴 X/Y en bonne voie` (minorité de verts, fond rouge clair)

### C. Styles CSS (nouveau bloc dans `dashboard.css`)

```css
.eval-row { display:grid; grid-template-columns: 1.2fr 1fr 1fr 0.7fr; gap:8px; padding:6px 8px; border-radius:5px; }
.eval-win-def   { background: rgba(51,224,160,.15); }
.eval-win-prov  { background: rgba(51,224,160,.08); }
.eval-neutral   { background: rgba(255,255,255,.03); }
.eval-lose-prov { background: rgba(255,107,125,.10); }
.eval-lose-def  { background: rgba(255,107,125,.18); }
.eval-unknown   { background: rgba(255,255,255,.02); color: var(--muted); }
```

### D. Contrat de rafraîchissement (déjà en place)

- **Horloge** (app.js:1654) : re-rend la liste chaque seconde → l'indicateur compact se met à jour visuellement.
- **`smartReload`** (app.js:1682) : recharge `predictions.json` toutes les 20s en live → `m.liveScore`/`m.liveStats` frais → `evaluerPronostic` rappelé → couleurs actualisées.
- **Détail ouvert** : si un match est sélectionné, `smartReload` rouvre `showDetail(m)` (app.js:1684-1686) → le tableau live se rafraîchit tout seul.

**Aucune logique de polling nouvelle à écrire** : on se branche sur ce qui existe.

## Périmètre

### Inclus

- Fonction `evaluerPronostic` + registre `EVALUATORS` (10 marchés)
- Helpers `verifierCondition` / `peutEncoreSeRealiser` / `estIrreversible`
- `_live_stats()` dans `pipeline.py` + branchement `m.liveStats`
- `renderLiveEval(m)` greffé dans `renderLive`
- `liveEvalBadge(m)` greffé dans `render` (carte liste)
- Styles CSS associés
- Tests unitaires du moteur et des stratégies

### Exclu explicitement

- Évaluation des props joueurs en live (pas de donnée individuelle par événement fiable en temps réel)
- Nouveau endpoint `/api` (le flux `predictions.json` suffit)
- Changement de source (ESPN couvre déjà tout)
- Migration de `vsTable` au FT (conservé intact)

## Tests

- **Moteur** : `evaluerPronostic` appelé sur des fixtures de matchs (LIVE à différents scores/minutes, HT, FINISHED, KICKOFF sans liveStats) → vérification du tableau renvoyé.
- **Stratégies** : chaque marché testé sur ses cas limites (over atteint, under cassé, BTTS validé, score exact vivant/mort, marché en INCONNU).
- **Helpers** : `verifierCondition` / `peutEncoreSeRealiser` / `estIrreversible` testés isolément.
- **Backend** : `_live_stats()` renvoie `None` sur clé absente, et les bonnes valeurs sur un fichier fixture (pytest, comme `tests/`).

Le framework de test existant est `pytest` (voir `pytest.ini`, `tests/`). Le moteur JS (`evaluerPronostic` + stratégies) sera placé dans un module distinct (`assets/eval.js`) exporté sur `window`, ce qui permet :
- de le tester unitairement via une page de harnais dédiée (`tests/eval_harness.html`) qui charge le module et des fixtures JSON, et affiche les résultats des assertions ;
- de l'inclure dans `index.html` et `scouting.html` via une balise `<script>` (comme `assets/app.js` et `assets/shell.js` déjà présents).

Ce découpage (moteur isolé du code de rendu) rend le moteur testable sans navigateur et réutilisable, conformément au principe d'isolation du brainstorming.
