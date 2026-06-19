"""
Bios + forces/faiblesses des JOUEURS CLÉS — données réelles, sourcées sur le web.

⚠️ ZÉRO invention : chaque profil s'appuie sur de vraies analyses tactiques publiées
(scout reports, Coaches' Voice, The Athletic, Total Football Analysis, FOX, esosoccer…).
Couverture volontairement LIMITÉE aux joueurs phares des matchs du 13-14 juin 2026.
Tout joueur absent de ce fichier => bio "N/D" (on n'invente pas).

Clé = nom EXACT tel qu'il apparaît dans squads_2026.json.
"""
from __future__ import annotations

BIOS = {
    # ---- Suisse (vs Qatar, 13/06) ----
    "Gregor Kobel": {
        "club": "Borussia Dortmund", "role": "Gardien",
        "bio": "Gardien n°1 de la Suisse (Dortmund), finaliste de la Ligue des champions 2024.",
        "forces": ["Réflexes d'élite sur sa ligne", "Sang-froid et relance propre"],
        "faiblesses": ["Encore peu de sélections (expérience internationale limitée)"],
        "source": "FOX Sports / esosoccer (2026)",
    },
    "Granit Xhaka": {
        "club": "Sunderland", "role": "Milieu (capitaine)",
        "bio": "Capitaine le plus capé de l'histoire suisse, métronome du jeu.",
        "forces": ["Distribution et contrôle du tempo", "Leadership, qualité sur coups de pied arrêtés"],
        "faiblesses": ["Manque de vitesse", "Cartons : engagement parfois imprudent"],
        "source": "FOX Sports / The Athletic",
    },
    "Breel Embolo": {
        "club": "Rennes", "role": "Attaquant",
        "bio": "Avant-centre physique, capable de moments décisifs en tournoi.",
        "forces": ["Présence physique et jeu dos au but", "Pointe de vitesse"],
        "faiblesses": ["Constance dans la finition", "Création limitée face aux blocs bas"],
        "source": "esosoccer (analyse 2026)",
    },
    "Manuel Akanji": {
        "club": "Inter Milan", "role": "Défenseur central",
        "bio": "Roc défensif, excellent dans la relance.",
        "forces": ["Stabilité défensive", "Progression de balle propre"],
        "faiblesses": ["Peut être pris dans le dos sur ligne haute"],
        "source": "esosoccer / FOX",
    },

    # ---- Brésil (vs Maroc, 13/06) ----
    "Vinícius Júnior": {
        "club": "Real Madrid", "role": "Ailier gauche",
        "bio": "Ailier explosif du Real Madrid, l'une des plus grandes menaces du tournoi.",
        "forces": ["Vitesse et dribble en 1v1 dévastateurs", "Appels dans la profondeur, centres au second poteau"],
        "faiblesses": ["Décisions parfois hâtives dans le dernier tiers", "Apport défensif faible"],
        "source": "The Football Analyst / Futbollab",
    },
    "Vinicius Junior": {  # alias orthographe sans accents
        "club": "Real Madrid", "role": "Ailier gauche",
        "bio": "Ailier explosif du Real Madrid, l'une des plus grandes menaces du tournoi.",
        "forces": ["Vitesse et dribble en 1v1 dévastateurs", "Appels dans la profondeur, centres au second poteau"],
        "faiblesses": ["Décisions parfois hâtives dans le dernier tiers", "Apport défensif faible"],
        "source": "The Football Analyst / Futbollab",
    },
    "Raphinha": {
        "club": "Barcelona", "role": "Ailier",
        "bio": "Ailier travailleur du Barça, gros volume de jeu et frappe.",
        "forces": ["Frappe puissante", "Activité défensive rare pour un ailier", "Tireur de coups de pied arrêtés"],
        "faiblesses": ["Peut forcer ses frappes de loin"],
        "source": "scout reports (2025-26)",
    },
    "Alisson": {
        "club": "Liverpool", "role": "Gardien",
        "bio": "Gardien n°1 du Brésil (Liverpool), référence mondiale.",
        "forces": ["Jeu au pied exceptionnel", "Sorties et 1v1"],
        "faiblesses": ["Sujet à des passages à vide après blessures"],
        "source": "profils publics",
    },

    # ---- Maroc (vs Brésil, 13/06) ----
    "Achraf Hakimi": {
        "club": "Paris Saint-Germain", "role": "Latéral droit",
        "bio": "Latéral/piston droit du PSG, moteur offensif du Maroc demi-finaliste 2022.",
        "forces": ["Stamina et vitesse (record de sprint en Bundesliga)", "Jeu sans ballon, combinaisons, positionnement défensif"],
        "faiblesses": ["Précision des centres (~30%) perfectible", "Dribble peu agressif en 1v1"],
        "source": "Total Football Analysis (scout report)",
    },
    "Yassine Bounou": {
        "club": "Al-Hilal", "role": "Gardien",
        "bio": "Gardien héros du parcours 2022 (arrêts décisifs, tirs au but).",
        "forces": ["Spécialiste des tirs au but", "Présence et lecture des trajectoires"],
        "faiblesses": ["Relance parfois hésitante sous pression"],
        "source": "World Soccer Talk / profils 2022",
    },
    "Brahim Díaz": {
        "club": "Real Madrid", "role": "Meneur / ailier",
        "bio": "Créateur du Real Madrid, conduites de balle dans les petits espaces.",
        "forces": ["Dribble en zone serrée", "Percussion entre les lignes"],
        "faiblesses": ["Apport défensif limité", "Constance sur 90 min"],
        "source": "profils 2025-26",
    },

    # ---- Allemagne (vs Curaçao, 14/06) ----
    "Kai Havertz": {
        "club": "Arsenal", "role": "Attaquant / milieu offensif",
        "bio": "Polyvalent offensif d'Arsenal, faux 9 ou soutien.",
        "forces": ["Polyvalence, jeu dans les intervalles", "Jeu de tête et timing dans la surface"],
        "faiblesses": ["Irrégularité devant le but", "Peut s'effacer dans les gros matchs"],
        "source": "scout reports (2025-26)",
    },
    "Florian Wirtz": {
        "club": "Liverpool", "role": "Milieu offensif",
        "bio": "Meneur créatif (Liverpool), l'un des meilleurs jeunes du monde.",
        "forces": ["Vision et dernière passe", "Conduite de balle en mouvement"],
        "faiblesses": ["Peut être ciblé physiquement"],
        "source": "ESPN / profils 2026",
    },
    "Joshua Kimmich": {
        "club": "Bayern Munich", "role": "Milieu / arrière droit (capitaine)",
        "bio": "Capitaine, chef d'orchestre du Bayern.",
        "forces": ["Distribution longue", "Intelligence tactique, coups de pied arrêtés"],
        "faiblesses": ["Vulnérable dans le dos en latéral face aux ailiers rapides"],
        "source": "profils publics",
    },

    # ---- Pays-Bas (vs Japon, 14/06) ----
    "Memphis Depay": {
        "club": "Corinthians", "role": "Attaquant",
        "bio": "Meilleur buteur de l'histoire des Pays-Bas, polyvalent offensif.",
        "forces": ["Frappe de balle et coups de pied arrêtés", "Dribble, centres rentrants du côté gauche"],
        "faiblesses": ["Vitesse de pointe limitée", "Régularité sur les coups francs"],
        "source": "Coaches' Voice / Football-Oranje",
    },
    "Cody Gakpo": {
        "club": "Liverpool", "role": "Ailier / attaquant",
        "bio": "Ailier gauche puissant de Liverpool, buteur régulier en sélection.",
        "forces": ["Puissance et finition du gauche", "Polyvalence sur le front offensif"],
        "faiblesses": ["Constance dans le dribble"],
        "source": "profils 2025-26",
    },

    # ---- Japon (vs Pays-Bas, 14/06) ----
    "Ritsu Doan": {
        "club": "Eintracht Frankfurt", "role": "Ailier",
        "bio": "Ailier japonais buteur en tournoi (déjà décisif vs grandes nations).",
        "forces": ["Frappe rentrante du gauche", "Sens du but dans les grands matchs"],
        "faiblesses": ["Irrégularité dans le un-contre-un"],
        "source": "Sporting News (golden boot tracker)",
    },

    # ---- Turquie (vs Australie, 13/06) ----
    "Hakan Çalhanoğlu": {
        "club": "Inter Milan", "role": "Milieu organisateur",
        "bio": "Régulateur de l'Inter et de la Turquie, expert des coups de pied arrêtés.",
        "forces": ["Distribution et tempo", "Coups francs et penaltys d'élite"],
        "faiblesses": ["Manque de vitesse", "Couvre moins de surface défensive"],
        "source": "The Athletic (NYT)",
    },
    "Arda Güler": {
        "club": "Real Madrid", "role": "Milieu offensif",
        "bio": "Jeune talent du Real Madrid, gaucher créatif.",
        "forces": ["Qualité de passe et de frappe du gauche", "Vision"],
        "faiblesses": ["Jeune (gestion du rythme tournoi)", "Apport défensif léger"],
        "source": "profils 2025-26",
    },

    # ---- Suède (vs Tunisie, 14/06) ----
    "Alexander Isak": {
        "club": "Liverpool", "role": "Attaquant",
        "bio": "Attaquant suédois technique, associé à Gyökeres.",
        "forces": ["Technique et composure devant le but", "Capacité à décrocher du côté gauche"],
        "faiblesses": ["Sujet aux blessures", "Peut s'isoler face aux blocs bas"],
        "source": "FOX Sports (2026)",
    },
    "Viktor Gyökeres": {
        "club": "Arsenal", "role": "Avant-centre",
        "bio": "Buteur prolifique, complément physique d'Isak.",
        "forces": ["Puissance et appels en profondeur", "Finition des deux pieds"],
        "faiblesses": ["Jeu de combinaison moins fin"],
        "source": "FOX Sports (2026)",
    },

    # ---- Écosse (vs Haïti) / Australie ----
    "Scott McTominay": {
        "club": "Napoli", "role": "Milieu box-to-box",
        "bio": "Milieu décisif de Naples, arrivées dans la surface.",
        "forces": ["Projection offensive et jeu de tête", "Volume de course"],
        "faiblesses": ["Première relance sous pression"],
        "source": "profils 2025-26",
    },

    # ---- France (Groupe I) ----
    "Kylian Mbappé": {
        "club": "Real Madrid", "role": "Attaquant (capitaine)",
        "bio": "Capitaine des Bleus, double médaillé en CDM ; meilleur buteur LdC & Liga 2025-26.",
        "forces": ["Explosivité et vitesse pure", "Finition clinique, crée et conclut"],
        "faiblesses": ["Apport défensif limité", "Peut s'isoler quand l'équipe souffre"],
        "source": "FOX Sports (Golden Ball power rankings 2026)",
    },
    "Ousmane Dembélé": {
        "club": "Paris Saint-Germain", "role": "Ailier",
        "bio": "Ballon d'Or en titre, champion d'Europe avec le PSG.",
        "forces": ["Ambidextrie et dribble", "Percussion sur les deux ailes"],
        "faiblesses": ["Historique de blessures", "Choix parfois précipités"],
        "source": "FOX Sports (2026)",
    },
    "Michael Olise": {
        "club": "Bayern Munich", "role": "Ailier",
        "bio": "Révélation du Bayern (20 buts, 25 passes déc. en 2025-26), triplé en amical.",
        "forces": ["Contrôle, pace et finition", "Création de occasions en série"],
        "faiblesses": ["Jeune en sélection (gestion d'un tournoi)"],
        "source": "FOX Sports (2026)",
    },

    # ---- Argentine (Groupe J) ----
    "Lionel Messi": {
        "club": "Inter Miami", "role": "Attaquant / meneur (capitaine)",
        "bio": "Champion du monde 2022 et meilleur joueur du tournoi ; double Golden Ball.",
        "forces": ["Vision et dernière passe d'exception", "Coups francs, leadership, finition"],
        "faiblesses": ["Âge (39 ans) : gestion de la charge", "Pressing limité"],
        "source": "FOX Sports (Golden Ball rankings 2026)",
    },
    "Julián Álvarez": {
        "club": "Atlético Madrid", "role": "Attaquant",
        "bio": "Attaquant mobile, champion du monde 2022.",
        "forces": ["Pressing et générosité", "Finition et appels intelligents"],
        "faiblesses": ["Moins dominant dos au but que les n°9 classiques"],
        "source": "profils 2025-26",
    },

    # ---- Espagne (Groupe H) ----
    "Lamine Yamal": {
        "club": "Barcelona", "role": "Ailier droit",
        "bio": "Prodige du Barça, champion d'Europe 2024 ; leader du dribble 1v1 en Europe.",
        "forces": ["Dribble 1v1 quasi imparable", "Accélération, équilibre, dernier geste"],
        "faiblesses": ["Très jeune (gestion physique)", "Repli défensif perfectible"],
        "source": "World Soccer Talk / ESPN (2025-26)",
    },
    "Pedri": {
        "club": "Barcelona", "role": "Milieu central",
        "bio": "Métronome du Barça double champion, chef d'orchestre de la Roja.",
        "forces": ["Conservation et passes qui cassent les lignes", "Vision rare"],
        "faiblesses": ["Peu de buts", "A connu des pépins physiques"],
        "source": "ESPN / FOX (2025-26)",
    },
    "Mikel Oyarzabal": {
        "club": "Real Sociedad", "role": "Attaquant",
        "bio": "Buteur du sacre Euro 2024, finisseur fiable.",
        "forces": ["Sang-froid devant le but", "Jeu collectif"],
        "faiblesses": ["Moins explosif que les ailiers purs"],
        "source": "profils 2024-26",
    },

    # ---- Angleterre (Groupe L) ----
    "Harry Kane": {
        "club": "Bayern Munich", "role": "Avant-centre (capitaine)",
        "bio": "Capitaine et recordman de buts de l'Angleterre, buteur prolifique au Bayern.",
        "forces": ["Finition d'élite des deux pieds", "Jeu en remise et passes décisives"],
        "faiblesses": ["Manque de vitesse pure", "Peut décrocher trop loin du but"],
        "source": "profils 2025-26",
    },
    "Jude Bellingham": {
        "club": "Real Madrid", "role": "Milieu offensif",
        "bio": "Milieu complet du Real, box-to-box moderne.",
        "forces": ["Résistance au pressing, passe et dribble", "Arrivées dans la surface et buts"],
        "faiblesses": ["Peut forcer en zone offensive"],
        "source": "Reddit r/Barca analysis / profils 2025-26",
    },
    "Bukayo Saka": {
        "club": "Arsenal", "role": "Ailier droit",
        "bio": "Ailier d'Arsenal, créateur et buteur régulier des Three Lions.",
        "forces": ["Dribble rentrant et centres", "Régularité dans le dernier tiers"],
        "faiblesses": ["Ciblé par les fautes (usure)"],
        "source": "profils 2025-26",
    },

    # ---- Portugal (Groupe K) ----
    "Cristiano Ronaldo": {
        "club": "Al-Nassr", "role": "Attaquant (capitaine)",
        "bio": "Recordman absolu de sélections et de buts internationaux.",
        "forces": ["Jeu de tête et finition dans la surface", "Mentalité et coups de pied arrêtés"],
        "faiblesses": ["Mobilité réduite avec l'âge", "Pressing limité"],
        "source": "profils publics",
    },
    "Bruno Fernandes": {
        "club": "Manchester United", "role": "Milieu offensif",
        "bio": "Moteur créatif de Man United (record de passes déc. en une saison PL).",
        "forces": ["Passes clés et frappe", "Coups de pied arrêtés, volume"],
        "faiblesses": ["Choix parfois précipités", "Perd des ballons en tentant le jeu vertical"],
        "source": "FOX Sports (2026)",
    },

    # ---- Norvège (Groupe I) ----
    "Erling Haaland": {
        "club": "Manchester City", "role": "Avant-centre",
        "bio": "Machine à buts de Man City, fer de lance de la Norvège.",
        "forces": ["Finition et puissance physique", "Appels en profondeur dévastateurs"],
        "faiblesses": ["Peu impliqué dans la construction", "Dépendant du service"],
        "source": "profils 2025-26",
    },
    "Martin Ødegaard": {
        "club": "Arsenal", "role": "Milieu offensif (capitaine)",
        "bio": "Capitaine d'Arsenal et de la Norvège, créateur principal.",
        "forces": ["Vision et dernière passe", "Qualité technique en zone serrée"],
        "faiblesses": ["Présence physique limitée"],
        "source": "profils 2025-26",
    },
}


def get_bio(name: str):
    """Renvoie le profil réel d'un joueur, ou None si non documenté (=> N/D)."""
    return BIOS.get(name)


# ---- Sénégal (Groupe I) — ajout suite à l'analyse France-Sénégal ----
BIOS["Sadio Mané"] = {
    "club": "Al-Nassr", "role": "Ailier / attaquant",
    "bio": "Leader emblématique du Sénégal, ballon d'or africain, vainqueur CAN 2021.",
    "forces": ["Vitesse et percussion", "Finition et expérience des grands matchs"],
    "faiblesses": ["Âge (34 ans), rythme à gérer", "Moins décisif qu'à son pic"],
    "source": "profils 2025-26 / Sportskeeda",
}
BIOS["Nicolas Jackson"] = {
    "club": "Bayern Munich", "role": "Avant-centre",
    "bio": "Buteur sénégalais au Bayern, pointe rapide et mobile.",
    "forces": ["Appels en profondeur", "Puissance et vitesse"],
    "faiblesses": ["Irrégularité dans la finition"],
    "source": "Total Football Analysis (2026)",
}
BIOS["Ismaïla Sarr"] = {
    "club": "Crystal Palace", "role": "Ailier",
    "bio": "Ailier rapide du Sénégal, danger sur les transitions.",
    "forces": ["Vitesse, dribble", "Menace sur le côté droit"],
    "faiblesses": ["Constance"],
    "source": "profils 2025-26",
}
BIOS["Iliman Ndiaye"] = {
    "club": "Everton", "role": "Attaquant / meneur",
    "bio": "Créateur technique du Sénégal, polyvalent offensivement.",
    "forces": ["Conduite de balle, créativité"],
    "faiblesses": ["Encore en affirmation au haut niveau"],
    "source": "profils 2025-26",
}
BIOS["Kalidou Koulibaly"] = {
    "club": "Al-Hilal", "role": "Défenseur central (capitaine)",
    "bio": "Patron de la défense sénégalaise, expérience d'élite.",
    "forces": ["Lecture du jeu, puissance, leadership"],
    "faiblesses": ["Vitesse de récupération (34 ans) face aux attaquants rapides"],
    "source": "Total Football Analysis (2026)",
}
