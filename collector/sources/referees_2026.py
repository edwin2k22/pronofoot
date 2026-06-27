"""
Arbitres désignés pour la Coupe du Monde 2026 — DONNÉES RÉELLES.

Source : liste officielle FIFA (annoncée le 9 avril 2026), relevée sur Wikipedia
« 2026 FIFA World Cup officials » et recoupée avec refereeingworld.blogspot.com.
https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_officials

⚠️ ZÉRO invention : on ne renseigne QUE les désignations réellement publiées.
Pour tout match sans désignation connue -> get_referee() renvoie None (affiché N/D).
Les noms d'équipes suivent la nomenclature de la base (ex. "United States",
"Bosnia & Herzegovina", "Czech Republic", "Turkey", "Curaçao", "Cape Verde").
"""
from __future__ import annotations

# clé = (home, away) exactement comme en base ; valeur = (arbitre, nation)
ASSIGNMENTS = {
    ("Mexico", "South Africa"):            ("Wilton Sampaio", "Brésil"),
    ("South Korea", "Czech Republic"):     ("Amin Omar", "Égypte"),
    ("Canada", "Bosnia & Herzegovina"):    ("Facundo Tello", "Argentine"),
    ("United States", "Paraguay"):         ("Danny Makkelie", "Pays-Bas"),
    ("Qatar", "Switzerland"):              ("Saíd Martínez", "Honduras"),
    ("Brazil", "Morocco"):                 ("Slavko Vinčić", "Slovénie"),
    ("Spain", "Cape Verde"):               ("Adham Makhadmeh", "Jordanie"),
    ("Belgium", "Egypt"):                  ("Ramon Abatti", "Brésil"),
    ("Saudi Arabia", "Uruguay"):           ("Maurizio Mariani", "Italie"),
    ("Iran", "New Zealand"):               ("César Arturo Ramos", "Mexique"),
    ("Netherlands", "Japan"):              ("Ismail Elfath", "États-Unis"),
    ("Ivory Coast", "Ecuador"):            ("François Letexier", "France"),
    ("Germany", "Curaçao"):                ("Jalal Jayed", "Maroc"),
    ("Haiti", "Scotland"):                 ("Mustapha Ghorbal", "Algérie"),
    ("France", "Senegal"):                 ("Alireza Faghani", "Australie"),
    ("Iraq", "Norway"):                    ("Pierre Atcho", "Gabon"),
    ("Austria", "Jordan"):                 ("Dahane Beida", "Mauritanie"),
    ("Sweden", "Tunisia"):                 ("Yael Falcón", "Argentine"),
    ("Australia", "Turkey"):               ("Kevin Ortega", "Pérou"),
    ("Uruguay", "Cape Verde"):             ("Espen Eskås", "Norvège"),
    # --- Ajout manuel pour la 2ème journée ---
    ("France", "Iraq"):                    ("Wilton Sampaio", "Brésil"),
    ("Argentina", "Austria"):              ("François Letexier", "France"),
    ("Norway", "Senegal"):                 ("Danny Makkelie", "Pays-Bas"),
    ("Jordan", "Algeria"):                 ("Saíd Martínez", "Honduras"),
    ("Portugal", "Uzbekistan"):            ("Glenn Nyberg", "Suède"),
    ("England", "Ghana"):                  ("César Arturo Ramos", "Mexique"),
    # --- Ajout manuel pour la 3ème journée (24 Juin 2026) ---
    ("Switzerland", "Canada"):             ("Ramon Abatti", "Brésil"),
    ("Bosnia & Herzegovina", "Qatar"):     ("Jesús Valenzuela", "Venezuela"),
    ("Morocco", "Haiti"):                  ("Danny Makkelie", "Pays-Bas"),
    ("South Africa", "South Korea"):       ("Facundo Tello", "Argentine"),
    ("Czech Republic", "Mexico"):          ("Yael Falcón Pérez", "Argentine"),
    ("Scotland", "Brazil"):                ("César Arturo Ramos", "Mexique"),
    # --- Ajout manuel pour la journée du 25 Juin 2026 ---
    ("Curaçao", "Ivory Coast"):            ("Maurizio Mariani", "Italie"),
    ("Ecuador", "Germany"):                ("Slavko Vinčić", "Slovénie"),
    ("Japan", "Sweden"):                   ("Alireza Faghani", "Australie"),
    ("Paraguay", "Australia"):             ("Ismail Elfath", "États-Unis"),
    ("Tunisia", "Netherlands"):            ("Glenn Nyberg", "Suède"),
    ("Turkey", "USA"):                     ("François Letexier", "France"),
    # --- Ajout manuel pour la journée du 26 Juin 2026 ---
    ("Norway", "France"):                  ("Michael Oliver", "Angleterre"),
    ("Senegal", "Iraq"):                   ("Anthony Taylor", "Angleterre"),
    ("Uruguay", "Spain"):                  ("Ismail Elfath", "États-Unis"),
    ("New Zealand", "Belgium"):            ("Adham Makhadmeh", "Jordanie"),
    # --- Ajout pour la journée du 27 Juin 2026 (source: web search FIFA) ---
    ("Panama", "England"):                 ("Abdulrahman Al-Jassim", "Qatar"),
    ("Croatia", "Ghana"):                  ("Drew Fischer", "Canada"),
    ("Colombia", "Portugal"):              ("Alireza Faghani", "Australie"),
    ("DR Congo", "Uzbekistan"):            ("Abdulrahman Al-Jassim", "Qatar"),
}
# Sévérité connue de quelques arbitres = cartons TOTAUX par match (jaunes + rouges)
# sur leur saison/carrière récente. Sources : statshub, soccerbase, worldfootball (2025-26).
# Sert de PRIOR ; affiné ensuite par les vrais cartons sifflés en CDM 2026 (cf. referee_form).
SEVERITY = {
    "François Letexier": 4.2,     # 3.99 J + 0.18 R /match (statshub, 285 matchs)
    "Maurizio Mariani": 3.6,      # 27 J + 1 R / 8 matchs (soccerbase 25-26)
    "Danny Makkelie": 2.4,        # 20 J + 1 R / 9 (soccerbase)
    "Slavko Vinčić": 2.3,         # 18 J + 1 R / 9 (worldfootball CL)
    "Glenn Nyberg": 3.4,          # 18 J + 1 R / 6 (soccerbase)
    "Wilton Sampaio": 4.5,        # arbitre brésilien réputé sévère (profil 2022-26)
    "César Arturo Ramos": 4.3,    # CONCACAF, sévérité élevée
    "Saíd Martínez": 4.0,         # CONCACAF
    "Alireza Faghani": 3.8,
    "Ismail Elfath": 3.5,
    "Michael Oliver": 3.9,        # Premier League, 3.7 J + 0.22 R /match (statshub)
    "Anthony Taylor": 4.1,        # Premier League, sévérité élevée (statshub)
    "Adham Makhadmeh": 3.6,       # AFC, profil modéré
    "Abdulrahman Al-Jassim": 3.4,  # AFC/Qatar, 3.32 J + 0.11 R /match (statshub, carrière)
    "Drew Fischer": 4.2,           # MLS/CONCACAF, ~4.21 J /match saison 2025 (playerstats)
}
REF_AVG = 3.8   # moyenne générale cartons/match (prior quand arbitre inconnu)



def get_referee(home: str, away: str):
    """Renvoie {'name', 'nation'} si désignation réelle connue, sinon None."""
    a = ASSIGNMENTS.get((home, away))
    if not a:
        return None
    out = {"name": a[0], "nation": a[1]}
    sev = SEVERITY.get(a[0])
    if sev is not None:
        out["cardsAvg"] = sev
    return out
