#!/usr/bin/env python3
"""
Test de fumée — vérifie la santé du projet en une commande.

Usage : python3 -m collector.selftest
Sort un code 0 si tout va bien, 1 sinon. Idéal avant un déploiement / après une modif.
"""
from __future__ import annotations
import sys, os, json, importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.path.dirname(__file__), "data")

ok = True
def check(label, cond):
    global ok
    print(f"  {'✅' if cond else '❌'} {label}")
    ok = ok and cond


def main():
    print("🔎 ProноFoot — test de santé\n")

    # 1) imports des modules actifs
    print("Modules :")
    mods = ["collector.pipeline", "collector.refresh", "collector.smart_live",
            "collector.live", "collector.import_stats", "collector.embed",
            "collector.player_ingest", "collector.schedule_clock",
            "collector.models.context", "collector.models.standings",
            "collector.models.lineup_impact", "collector.models.elo",
            "collector.sources.recent_form", "collector.sources.openfootball_wc",
            "collector.sources.free_sources"]
    for m in mods:
        try:
            importlib.import_module(m); check(m, True)
        except Exception as e:
            check(f"{m} ({e})", False)

    # 1bis) contrat "100% gratuit" : aucune dependance a cle payante dans le code actif
    print("\nMode gratuit :")
    try:
        from collector.sources import free_sources
        hits = free_sources.scan_for_paid_dependencies()
        check("aucune API payante obligatoire detectee", len(hits) == 0)
        manifest = free_sources.manifest()
        check(f"sources gratuites referencees ({len(manifest['sources'])})",
              len(manifest["sources"]) >= 5)
    except Exception as e:
        check(f"audit sources gratuites ({e})", False)

    # 2) données présentes et valides
    print("\nDonnées :")
    for f in ["predictions.json", "squads_2026.json", "recent_form.json"]:
        p = os.path.join(DATA, f)
        try:
            d = json.load(open(p, encoding="utf-8"))
            check(f"{f} ({len(d)} entrées)", len(d) > 0)
        except Exception as e:
            check(f"{f} ({e})", False)

    # 3) cohérence des pronostics
    print("\nCohérence pronostics :")
    try:
        d = json.load(open(os.path.join(DATA, "predictions.json"), encoding="utf-8"))
        sums_ok = all(abs(m["prediction"]["p1"] + m["prediction"]["pX"] + m["prediction"]["p2"] - 1) < 0.02 for m in d)
        keys_ok = all(all(k in m["prediction"] for k in ("mwi", "meta", "kelly", "corners", "cards")) for m in d)
        check("sommes 1N2 ≈ 100%", sums_ok)
        check("toutes les clés contextuelles présentes", keys_ok)
        # marchés dérivés + scénarios (100% issus de la grille)
        mk_ok = all(all(k in m["prediction"] for k in ("doubleChance", "drawNoBet", "topScores", "scenarios")) for m in d)
        check("marchés dérivés + scénarios présents", mk_ok)
        # buts : O/U multi-lignes, total xG, BTTS+confiance, mi-temps
        goals_ok = all(all(k in m["prediction"] for k in ("overUnder", "totalXg", "bttsConf", "halftime")) for m in d)
        check("marchés buts (O/U multi-lignes, xG, BTTS, mi-temps) présents", goals_ok)
        # modules corners & cartons autonomes
        mod_ok = all(
            "lines" in m["prediction"]["corners"] and "lines" in m["prediction"]["cards"]
            and "redProb" in m["prediction"]["cards"] and "riskPlayers" in m["prediction"]
            and ("referee" in m["prediction"])
            for m in d)
        check("modules corners/cartons (lignes, rouge, arbitre, risque) présents", mod_ok)
        # au moins un arbitre réel renseigné (désignations FIFA)
        ref_count = sum(1 for m in d if m["prediction"].get("referee"))
        check(f"arbitres réels désignés ({ref_count} matchs)", ref_count > 0)
        # tirs : bloc présent partout, et tirs RÉELS pour les matchs joués
        shots_ok = all("shots" in m["prediction"] for m in d)
        check("bloc tirs présent", shots_ok)
        finished = [m for m in d if m["status"] == "FINISHED"]
        shots_real = sum(1 for m in finished if m["prediction"]["shots"].get("real"))
        check(f"tirs réels sur matchs joués ({shots_real}/{len(finished)})",
              len(finished) == 0 or shots_real == len(finished))
        # tirs PRÉDITS pour les matchs à venir (expShots renseigné)
        upcoming = [m for m in d if m["status"] != "FINISHED"]
        shots_pred = sum(1 for m in upcoming if m["prediction"]["shots"].get("expShots") is not None)
        check(f"pronos tirs sur matchs à venir ({shots_pred}/{len(upcoming)})",
              len(upcoming) == 0 or shots_pred == len(upcoming))
        # pronos joueurs (6 rôles) présents et probabilités buteurs valides (0..1)
        pp_ok = all("playerProps" in m["prediction"] for m in d)
        check("pronos joueurs présents", pp_ok)
        prob_ok = True
        for m in d:
            for side in ("home", "away"):
                pp = (m["prediction"].get("playerProps") or {}).get(side)
                if pp:
                    for s in pp.get("scorers", []):
                        if not (0 <= s["p"] <= 1):
                            prob_ok = False
        check("probabilités buteurs ∈ [0,1]", prob_ok)
        # bios réelles attachées à au moins quelques joueurs clés
        bio_count = 0
        for m in d:
            for side in ("home", "away"):
                pp = (m["prediction"].get("playerProps") or {}).get(side)
                if pp:
                    bio_count += sum(1 for s in pp.get("scorers", []) if s.get("bio"))
                    if pp.get("keeper") and pp["keeper"].get("bio"):
                        bio_count += 1
        check(f"bios réelles attachées ({bio_count} occurrences)", bio_count > 0)
        # cohérence marché : si le score modal est un BTTS (les 2 marquent),
        # le pronostic BTTS ne doit plus afficher un "Non" tranché (zone indécise tolérée)
        incoh = 0
        for m in d:
            p = m["prediction"]
            modal_btts = p["topScore"][0] > 0 and p["topScore"][1] > 0
            pick = (p.get("bttsConf") or {}).get("pick")
            if modal_btts and pick == "Non":
                incoh += 1
        check(f"cohérence score modal ↔ BTTS ({incoh} conflits durs)", incoh == 0)
        # correctif empirique présent dès qu'il y a des matchs joués
        mc = d[0]["prediction"].get("marketCalib")
        check("correctif empirique BTTS/Over présent", mc is not None)
        # comparaison prédictions↔résultat dispo pour TOUS les matchs terminés (sans exception)
        fins = [m for m in d if m["status"] == "FINISHED"]
        cmp_ok = all(
            m.get("analysis") and m.get("prediction")
            and m["analysis"].get("realScore")
            and "topScore" in m["prediction"]
            for m in fins)
        check(f"comparaison prédictions↔résultat sur tous les terminés ({len(fins)}/{len(fins)})", cmp_ok)
        # cohérence O/U : over décroît quand la ligne monte (1.5 >= 2.5 >= 3.5)
        ou_mono = all(
            m["prediction"]["overUnder"]["1.5"]["over"] >= m["prediction"]["overUnder"]["2.5"]["over"] >= m["prediction"]["overUnder"]["3.5"]["over"]
            for m in d)
        check("Over/Under monotone (1.5 ≥ 2.5 ≥ 3.5)", ou_mono)
        # les 3 scénarios principaux (hors angle) doivent totaliser ~100%
        scn_ok = all(
            abs(sum(s["p"] for s in m["prediction"]["scenarios"] if not s.get("angle")) - 1) < 0.02
            for m in d)
        check("scénarios principaux ≈ 100%", scn_ok)
    except Exception as e:
        check(f"pronostics ({e})", False)

    # 3ter) Meilleurs choix (Top Picks) : fiabilité réelle mesurée du niveau "lock"
    print("\nMeilleurs choix (sélection haute confiance) :")
    try:
        tp_path = os.path.join(os.path.dirname(__file__), "data", "top_picks.json")
        if os.path.exists(tp_path):
            with open(tp_path, encoding="utf-8") as f:
                tp = json.load(f)
            lock = tp["reliability"]["byTier"]["lock"]
            check(f"top_picks.json présent ({len(tp['picks'])} picks affichés)", len(tp["picks"]) > 0)
            # le niveau 'lock' doit afficher une fiabilité réelle élevée (≥80% mesuré)
            if lock["total"] >= 5:
                check(f"fiabilité 🔒 verrouillé mesurée = {lock['pct']}% (cible ≥80%)",
                      (lock["pct"] or 0) >= 80)
            else:
                check(f"fiabilité 🔒 (échantillon {lock['total']} — trop petit, info)", True)
        else:
            check("top_picks.json (sera créé au prochain predict)", True)
    except Exception as e:
        check(f"top picks ({e})", False)

    # 3quater) modèle d'ensemble : présent sur chaque match + poids normalisés
    print("\nModèle d'ensemble (auto-apprentissage) :")
    try:
        ens_ok = all("ensemble" in m["prediction"] and m["prediction"]["ensemble"]
                     and "weights" in m["prediction"]["ensemble"] for m in d)
        check("bloc ensemble (Elo/Buts/Forme) présent sur tous les matchs", ens_ok)
        w = d[0]["prediction"]["ensemble"]["weights"]
        wsum = sum(w.values())
        check(f"poids d'ensemble normalisés (somme={round(wsum,3)})", abs(wsum-1) < 0.02)
        wf = os.path.join(os.path.dirname(__file__), "data", "ensemble_weights.json")
        if os.path.exists(wf):
            meta = json.load(open(wf, encoding="utf-8")).get("meta", {})
            check(f"poids appris sur {meta.get('n',0)} matchs (T={meta.get('T','?')})", True)
    except Exception as e:
        check(f"ensemble ({e})", False)

    # 3quinquies) PnL / ROI (métrique reine)
    print("\nPnL / ROI (Yield) :")
    try:
        pf = os.path.join(os.path.dirname(__file__), "data", "pnl.json")
        if os.path.exists(pf):
            pn = json.load(open(pf, encoding="utf-8"))
            check(f"pnl.json présent (échantillon {pn.get('sampleWithOdds',0)} matchs avec cotes)", True)
            v = pn.get("value", {})
            check(f"value ROI calculé (yield={v.get('yield')}%, {v.get('bets',0)} paris)",
                  "yield" in v)
            check(f"top value bets du jour ({len(pn.get('topValue',[]))})", True)
        else:
            check("pnl.json (sera créé au prochain predict)", True)
    except Exception as e:
        check(f"PnL ({e})", False)

    # 3bis) calibration Dixon-Coles présente et dans les bornes
    print("\nCalibration ρ/γ :")
    try:
        from collector.models import calibrate as cal
        c = cal.load()
        check(f"ρ={c['rho']} (∈ [-0.15,0])", -0.15 <= c["rho"] <= 0)
        check(f"γ={c['gamma']} (∈ [0,0.2])", 0 <= c["gamma"] <= 0.2)
    except Exception as e:
        check(f"calibration ({e})", False)

    # 4) couverture forme 100% réelle
    print("\nForme :")
    try:
        from collector.sources import recent_form as rf
        from collector.sources.openfootball_wc import load_schedule
        sched = load_schedule()
        teams = {t for mt in sched.get("matches", []) for t in (mt.get("team1"), mt.get("team2"))
                 if t and not any(c in t for c in "0123456789/")}
        covered = sum(1 for t in teams if rf.team_form(t))
        check(f"forme réelle {covered}/{len(teams)} équipes", covered == len(teams))
    except Exception as e:
        check(f"forme ({e})", False)

    # 5) données embarquées à jour dans index.html
    print("\nFrontend :")
    try:
        import re
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        emb = json.loads(re.search(r'<script id="embedded-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        check(f"index.html : {len(emb)} matchs embarqués", len(emb) > 0)
        sc = open(os.path.join(ROOT, "scouting.html"), encoding="utf-8").read()
        embs = json.loads(re.search(r'<script id="embedded-squads"[^>]*>(.*?)</script>', sc, re.S).group(1))
        check(f"scouting.html : {len(embs)} effectifs embarqués", len(embs) > 0)
    except Exception as e:
        check(f"embed ({e})", False)

    print("\n" + ("✅ TOUT EST OK" if ok else "❌ DES PROBLÈMES DÉTECTÉS"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
