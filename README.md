# ⚽ ProноFoot — pronostics Coupe du Monde 2026 🏆

Système de pronostics **100% dédié à la CDM 2026** (Canada/USA/Mexique, 11 juin – 19 juillet).
Modèle Bayésien évolutif : prior de force → mise à jour après chaque match → probabilités.

> ℹ️ Toutes les données 2018/2022 ont été retirées. Le système n'utilise que des
> données **2026** (calendrier, effectifs, résultats) + des **ratings FIFA/Elo** comme prior.

## 🏆 Données réelles 2026

| Donnée | Source | Statut |
|--------|--------|--------|
| **Calendrier (104 matchs)** | openfootball/worldcup.json | ✅ réel |
| **Résultats / scores** | openfootball (MAJ quotidienne) | ✅ réel, au fil du tournoi |
| **Effectifs (1245 joueurs)** | openfootball squads 2026 | ✅ réel (n°, poste, âge) |
| **Force des équipes** | ratings FIFA/Elo (`team_ratings.py`) | prior, affiné par les résultats 2026 |
| **Stats joueur 2026** | (à ingérer quand dispo) | `N/D` jusqu'aux matchs |

Tout est en JSON domaine public, **sans clé API**.

Mode gratuit verifiable :

```bash
python3 -m collector.sources.free_sources --audit
```

Pour partager l'app sans `runlocal`, utilise le workflow GitHub Actions
`Free Static Refresh` : il rafraichit les donnees statiques toutes les 30 minutes
et republie `index.html` / `scouting.html` sans serveur payant.

## 🧠 Système Bayésien évolutif (les 6 points)

| # | Besoin | Implémentation |
|---|--------|----------------|
| 1 | Calendrier officiel réel | `sources/openfootball_wc.py` (104 matchs) |
| 2 | Prior de force | `sources/team_ratings.py` → Elo initial par sélection |
| 3 | **Modèles séparés** | `models/markets.py` : résultat (1X2), buts (O/U, BTTS), corners, cartons |
| 4 | MAJ après chaque match | `pipeline.py ingest/update` → Elo + moyennes ajustés sur résultats 2026 |
| 5 | **Anti-overreaction** | `models/elo.py` (K décroissant) + `models/shrinkage.py` (shrinkage Bayésien) |
| 6 | **Base locale** | `db/database.py` → SQLite (`db/pronofoot.db`), audit complet |

## 🚀 Démarrage

```bash
cd prono-app
pip install -r requirements-dev.txt        # dépendances dev (pytest, flake8...) — optionnel pour juste lancer
python3 -m collector.refresh                # tout-en-un : web → seed → ingest → predict → embed
python3 -m collector.selftest               # test de santé (modules, données, cohérence)
python3 -m http.server 8077                 # ouvre http://localhost:8077/index.html
```

Ou étape par étape : `pipeline seed` → `pipeline run` → `player_ingest --export` → `embed`.

> ⚠️ `index.html` et `scouting.html` **ne sont pas dans le dépôt git** : ce sont des
> artefacts de build (données embarquées via `embed.py`). Le premier `refresh` (ou
> `python3 -m collector.embed`) les régénère localement. Sans serveur, ils s'ouvrent
> aussi en `file://` (données embarquées). Idem pour la base `pronofoot.db`,
> créée par `pipeline seed`.

- `index.html` → pronostics des 102 matchs à venir (filtre par groupe, marchés 1X2/buts/corners/cartons)
- `scouting.html` → effectifs réels 2026 par équipe (stats N/D en attendant les matchs)

**Après chaque journée du Mondial**, relance `python3 -m collector.pipeline run` :
le système ingère les nouveaux scores et régénère les pronostics affinés.

> 💡 Les données sont **embarquées dans index.html** (via `collector/embed.py`, lancé
> automatiquement par `refresh`) pour que le dashboard s'affiche **toujours**, même
> hors-ligne ou dans un aperçu sans serveur. Si un serveur tourne, le fetch live
> remplace les données embarquées par la version à jour.

## 🧠 Dashboard à onglets (intelligent selon le statut)

`index.html` est un dashboard 100% automatique organisé en **3 onglets** :

| Onglet | Contenu au clic sur un match |
|--------|------------------------------|
| 🔴 **En cours** | Score live + pronostic d'avant-match en repère |
| ⏳ **À venir** | Pronostic complet : 1X2, score probable, buts, corners, cartons, confiance |
| 🏁 **Terminés** | **Score final + analyse** : verdict du modèle (réussi/raté), stats du match (xG/tirs/corners/cartons), + le prono d'avant-match pour comparaison |

- Filtre par phase (groupes A→L, knockouts) + recherche d'équipe.
- **Aucune saisie manuelle** : tout vient des vrais matchs CDM 2026.
- Un match **terminé n'affiche jamais de "calcul de pronostic"** — uniquement le
  résultat et l'analyse (le quoi/pourquoi).
- Rechargement auto : 20 s s'il y a un match live, 5 min sinon ; garde le match ouvert.

Exemple (Corée 2-1 Tchéquie) : onglet 🏁 Terminés → *« ✅ le modèle donnait Corée
favori 59%, issue correctement anticipée, score prévu 2-0 vs réel 2-1, Over 2.5, BTTS oui »*.

> Stats détaillées affichées si la source les fournit (sinon `N/D`) : openfootball donne
> le score, les stats fines viennent du live (`collector/live.py --set`).

### Stats & déroulé réels des matchs terminés
Les vraies stats (xG, tirs, corners, cartons), le **déroulé** (buteurs, cartons, MOTM)
et les **compositions de départ** des matchs joués sont stockés dans :
- `collector/data/match_stats_real.json` — stats collectives
- `collector/data/match_events_real.json` — buteurs / cartons / MOTM
- `collector/data/match_lineups_real.json` — compos (formation, entraîneur, XI)

Importés en base par `collector/import_stats.py` (lancé automatiquement par `refresh`),
puis affichés dans le panneau du match terminé sous forme de **timeline ⏱️**.

```bash
python3 -m collector.import_stats   # injecte stats + déroulé des matchs finis
```

> Données collectées sur les box scores publics (Opta, Sofascore, 365scores, FOX...).
> Pour un nouveau match terminé, ajoute son entrée dans les deux fichiers JSON.

## 📈 Forme récente réelle (10 derniers matchs)

`collector/data/recent_form.json` stocke les **10 derniers matchs réels** de chaque
sélection (qualifs + amicaux, collectés sur 11v11/Goal/AiScore) : adversaire, lieu,
score, W/D/L, compétition. Via `collector/sources/recent_form.py`, ça sert à :
- **calibrer λ** : `λ × (0.90 + form_index×0.20)` → une équipe en forme attaque mieux ;
- **initialiser** les moyennes gf/ga d'une équipe avant son 1er match CDM (au lieu du seul prior) ;
- **afficher** la forme W/D/L en pastilles 🟢🟡🔴 + (points/10, buts pour/contre).

> Vérifié : France WLWWW (25 pts/10) → λ relevé ; Brésil WWWLL (19 pts/10) → λ modéré.
>
> **Couverture : 48/48 équipes en données 100% RÉELLES** (10 derniers matchs détaillés —
> qualifs CDM, AFCON 2025, Nations League, amicaux — collectés sur 11v11, Goal, UEFA,
> ESPN, FotMob, RSSSF, SoccerPunter). **Aucune donnée estimée** : si une équipe n'a pas
> de vraies données, sa forme est `N/D` (on n'invente jamais de scores).

## 🧬 La composition comme système de variables (impact sur les probas)

La compo n'est pas qu'un alignement de noms : elle **modifie directement λ** et les marchés.
Module `collector/models/lineup_impact.py` — 3 angles :

1. **Data — VORP / Delta de rotation** : chaque joueur a un sous-rating (hybride :
   positionnel × Elo équipe, et vrai xG/xA dès qu'il est dispo). Un XI affaibli/tourné
   réduit l'attaque : `λ_ajusté = λ_base × (1 − Delta_rotation)`.
2. **Tactique — duel des systèmes + banc** : matrice ÉTENDUE de modificateurs formation
   vs formation (4-3-3, 3-5-2, 4-2-3-1, 4-4-2, 3-4-3, 5-3-2, 5-4-1, 4-5-1… ~40 duels).
   Ex. un 3-5-2 étouffe un 4-3-3 (×0.94), un 5-4-1 verrouille (×0.90). Le **Bench Impact
   Score** (qualité des finisseurs sur le banc) ajoute jusqu'à +6 % sur l'Over 2.5
   (5 changements possibles). Les bancs sont affichés sous le terrain.
3. **UI — cartographie spatiale** : la liste verticale est remplacée par un **mini-terrain
   CSS** où chaque joueur est un nœud avec une **pastille de forme** (🟢/🟡/🔴, basée sur
   le xG récent dès qu'il est disponible) ; emplacement prévu pour 🟨 suspension.

> Vérifié : Mexique (4-3-3) vs Afrique du Sud (5-3-2) → modificateur tactique ×0.96
> appliqué à λ. Toutes les prédictions exposent `prediction.lineupImpact`.

## 📐 Moteur de scores avancé (Dixon-Coles + bivarié + knockout)

Le Poisson naïf suppose l'indépendance des scores (faux au foot : il sous-estime les
scores serrés). Trois corrections dans `collector/models/score_grid.py` et `knockout.py` :

1. **Dixon-Coles (1997)** : paramètre ρ (≈ −0.06) qui corrige les 4 scores critiques
   (0-0, 1-0, 0-1, 1-1). → meilleur marché « Nul » et « Under 1.5 ».
   *Vérifié : nul 28.3% → 29.9%, 0-0 10.0% → 10.8%.*
2. **Poisson bivarié — effet de choc (γ)** : variable latente commune Z₃~Poisson(γ)
   pour les événements macro (carton rouge, penalty, arbitrage…). Gonfle les scénarios
   extrêmes sur les matchs à haute tension (J3, knockout, matchs serrés).
   *Vérifié : BTTS 57% → 62% avec choc.*
3. **Transition knockout** : marché « qui se qualifie ? » via chaîne 90' →
   prolongations (λ réduits de 70%) → tirs au but (proba selon Elo + sang-froid/forme,
   jamais un 50/50). S'active automatiquement en phase à élimination directe.

**Calibration automatique** (`models/calibrate.py`) : ρ et γ ne restent pas figés sur
les valeurs de littérature — ils sont **recalibrés par maximum de vraisemblance** sur
les vrais scores du tournoi à chaque `refresh`, avec un shrinkage vers le prior tant
qu'il y a peu de matchs. *Ex. après 4 matchs : ρ −0.06 → −0.08.* Résultat dans
`data/calibration.json`, utilisé automatiquement par le moteur de scores.

## 🎲 Intelligence contextuelle (3 angles avancés)

Module `collector/models/context.py` — au-dessus du calcul brut :

1. **Théorie des jeux — Must-Win Index (MWI)** : l'enjeu modifie le comportement.
   Le 3e match de poule a un enjeu max (0.9) vs J1 (0.3). Une équipe qui doit gagner
   reçoit un multiplicateur d'urgence sur λ ; une équipe démotivée/qualifiée, un malus.
   La journée de poule (1/2/3) est calculée par chronologie.
   **Classements de groupe en temps réel** (`models/standings.py`) : après chaque
   journée, le système calcule mathématiquement qui est `qualifié` / `éliminé` / `en lice`
   et le MWI en tient compte (une équipe déjà qualifiée lève le pied en J3 → variance).
   Affiché dans le dashboard (✅ qualifié / ❌ éliminé / ⚪ en lice).
2. **Métacognition — Indice de Confiance** : le modèle s'auto-évalue (forme réelle ?
   volatile ? assez de matchs CDM ?) → confiance ∈ [0,1] avec ses raisons. Elle
   **fractionne le Kelly** : `f* = (b·p−q)/b × confiance`, plafonné à 5% (mise prudente).
3. **Risque quantitatif — Line Movement / Trap Game** : compare la prédiction au
   mouvement de cote (ouverture → actuelle). Value détectée mais marché qui fuit
   → ⚠️ alerte « Trap Game » (blessure/info de dernière minute ?). *Prêt, activable
   dès qu'on saisit des cotes ouverture/actuelle.*

> Affiché dans le dashboard : section « 🧠 Contexte & confiance » (enjeu, confiance,
> mise Kelly conseillée, mouvement de cote).

## 🔴 Mode LIVE + refresh automatique

**Refresh régulier (recommandé pendant le tournoi)** — dans un terminal :
```bash
python3 -m collector.autorefresh --interval 300   # va chercher tout sur le web toutes les 5 min
```
Et dans un autre terminal : `python3 -m http.server 8077`.
La page web se recharge seule toutes les 60 s pour afficher les nouveautés.

**⭐ Tout-en-un INTELLIGENT (recommandé)** :
```bash
./start.sh              # scheduler intelligent + serveur sur :8077
./start.sh 20 8080      # poll 20s en match, serveur sur :8080
```
Le scheduler `smart_live` connaît le calendrier et **s'active tout seul** :
- 🔴 **LIVE** (un match en cours) → actualisation rapide (30 s par défaut)
- ⏳ **SOON** (coup d'envoi < 10 min) → veille active, prêt à démarrer
- 💤 **IDLE** (rien ne joue) → dort jusqu'à 5 min avant le prochain match

Il ne martèle donc jamais l'API la nuit, mais ne rate aucun coup d'envoi.
La page web se recharge aussi intelligemment (20 s s'il y a un live, 5 min sinon).

Diagnostic instantané : `python3 -m collector.smart_live --status`
24/7 en fond : `nohup ./start.sh &` (ou un service systemd, voir ci-dessous).

## 🛠️ Déploiement 24/7 (systemd)

Pour un vrai 24/7 (démarrage au boot + redémarrage automatique si crash) :

```bash
cd prono-app
sudo ./deploy/install.sh          # installe 2 services et les démarre
```

Cela crée :
- **pronofoot-live** — le scheduler live intelligent (s'active aux coups d'envoi)
- **pronofoot-web** — le serveur web (app sur le port 8077)

Les deux redémarrent seuls en cas de crash ou de coupure réseau, et au boot.

**Commandes utiles :**
```bash
systemctl status pronofoot-live          # état du scheduler
journalctl -u pronofoot-live -f          # suivre le live en direct
sudo systemctl restart pronofoot-live    # redémarrer
sudo ./deploy/uninstall.sh               # tout désinstaller
```

> Le script détecte automatiquement le chemin du projet et l'utilisateur.
> Sans systemd (Mac, Windows), utilise `nohup ./start.sh &`.

**Suivi live AUTOMATIQUE (temps réel)** via l'API gratuite worldcup26.ir :
```bash
python3 -m collector.live --auto       # tire les live scores en temps réel (sans clé)
python3 -m collector.live --status     # voir les matchs LIVE
python3 -m collector.live --sync       # filet de sécurité : scores finaux openfootball
```
> L'`autorefresh` appelle `--auto` à chaque passage → l'app suit les matchs en direct
> automatiquement (worldcup26.ir met à jour pendant les matchs, contrairement à
> openfootball qui est quotidien).

**Saisie manuelle avec stats détaillées** (si tu veux ajouter xG/corners/cartons) :
```bash
python3 -m collector.live --set "Canada" "Bosnia & Herzegovina" 0 1 \
        --state LIVE --minute 50 --xg 0.6 0.8 --shots 8 4 --corners 9 1 --cards 1 2
```

> 🛡️ Sécurité anti-overreaction : un match `LIVE` est affiché (badge 🔴 dans l'app)
> mais **n'impacte PAS les ratings Elo** tant qu'il n'est pas `FINISHED`. Un re-seed
> ne réécrit jamais un match déjà LIVE/terminé.

> Exemple : Mexique 2-0 Afrique du Sud → Elo Mexique 1845→1854.
> Corée 2-1 Tchéquie → Corée 1785→1799. (anti-overreaction : K décroissant + shrinkage)

## 📋 Effectifs 2026 + remplissage automatique des stats joueur

Les **1245 joueurs réellement sélectionnés** sont en base (identité 100% réelle).
Leurs stats de match sont `N/D` tant qu'aucun match 2026 n'est disponible.

```bash
# dès qu'un match 2026 a un rapport joueur (format JSON attendu) :
python3 -m collector.player_ingest --file rapport.json --ref "2026-FRA-SEN"
python3 -m collector.player_ingest --export
# → les joueurs concernés passent de N/D à leurs vraies stats (cumuls auto)
```

**Colonnes joueur** (26) : Joueur, Poste, Minutes, Note, Buts, Passes déc., Tirs,
Tirs cadrés, xG, xA, Passes réussies, Passes progressives, Touches, Touches surface,
Dribbles, Duels, Tacles, Interceptions, Blocks, Dégagements, Pressions, Ballons récupérés,
Fautes commises, Fautes subies, Hors-jeu, Cartons (avec motif).

> La **Note** reste `N/D` : métrique propriétaire (FotMob/Sofascore), pas dans l'open data.

## Architecture

```
prono-app/
├── index.html                    # app web : pronostics 2026 (régénéré par embed.py)
├── scouting.html                 # effectifs joueurs 2026 (régénéré par embed.py)
├── requirements.txt              # runtime (stdlib uniquement)
├── requirements-dev.txt          # pytest, flake8, mypy, black, isort
├── .github/workflows/ci.yml      # CI : pytest + flake8 à chaque push
├── scripts/                      # utilitaires de maintenance (reset_elo, enrich_*)
├── tests/                        # suite de tests du cœur statistique
└── collector/
    ├── pipeline.py               # orchestrateur (seed / ingest / update / predict)
    ├── refresh.py                # tout-en-un + embarquement HTML
    ├── embed.py                  # injecte predictions.json/squads dans les HTML
    ├── player_ingest.py          # ingestion stats joueur 2026 + export effectifs
    ├── db/database.py            # base locale SQLite
    ├── models/                   # cœur statistique
    │   ├── elo.py                # prior de force + update (K décroissant, xG-blend)
    │   ├── shrinkage.py          # anti-overreaction Bayésien
    │   ├── score_grid.py         # Dixon-Coles + Poisson bivarié (effet de choc)
    │   ├── markets.py            # 1X2 / buts / corners / cartons / tirs
    │   ├── calibrate.py          # recalage ρ/γ par max. de vraisemblance
    │   ├── context.py            # enjeu (MWI), confiance, mouvement de cote
    │   ├── standings.py          # classements live + qualifié/éliminé
    │   ├── lineup_impact.py      # impact compo (VORP + duels tactiques)
    │   └── ensemble.py           # pondération des modèles
    └── sources/                  # ingestion (openfootball, ESPN, cotes, arbitres...)
```

## 🧪 Tests & CI

Le cœur statistique est couvert par des tests d'invariants mathématiques (normalisation
des grilles, partition 1X2, conservation de l'Elo, bornes des probabilités) :

```bash
pip install -r requirements-dev.txt
pytest tests/                    # 77 tests (~0.3 s)
flake8 collector/ tests/         # erreurs F (imports cassés, vars non définies)
```

La CI GitHub Actions (`.github/workflows/ci.yml`) lance ces deux vérifications sur
Python 3.11 et 3.12 à chaque push/PR — empêche les régressions silencieuses sur le
moteur de pronostic.

## Le moteur de pronostic
1. **Prior** — rating Elo par sélection (basé classement FIFA).
2. **Scénario** — buts attendus λ via les moyennes (shrinkées) modulées par l'écart Elo.
3. **Probabilité** — loi de Poisson → 1/N/2, Over/Under 2.5, BTTS, corners, cartons.
4. **Évolution** — après chaque match 2026, Elo + moyennes mis à jour (K décroissant).

---
⚠️ Outil d'aide à la décision statistique. Aucun pronostic garanti. Paris responsables (+18). 🔞
