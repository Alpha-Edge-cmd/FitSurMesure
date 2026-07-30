# -*- coding: utf-8 -*-
"""
Référentiel des zones d'intensité et des types de séance cardio.

Source : document « Les bases du cardio » fourni par Samy — les 5 zones, leurs
pourcentages de FCmax, leur filière énergétique dominante et leur carburant
sont repris tels quels de son tableau récapitulatif, de façon à ce que le
programme généré parle exactement le même langage que sa documentation.

Ce module ne contient QUE des données (zones + définition des types de séance).
Les protocoles concrets par discipline vivent dans `cardio_builder.py`
(PROTOCOLS_VARIANTS), et la répartition hebdomadaire dans
`cardio_builder._session_mix`. Séparation volontaire : on peut enrichir le
catalogue de séances sans toucher à la logique de planification, et
inversement.

Motivation (retour Samy) : « sur 5 séances proposées, il y en a 4 en endurance
fondamentale, ce n'est absolument pas assez varié ». La cause n'était pas le
contenu des protocoles (déjà corrects) mais le fait qu'il n'existait que
4 étiquettes de séance en tout. On passe ici à 15 types distincts, chacun
rattaché à une zone, donc à un effet physiologique identifiable.
"""

# --- Zones d'intensité (tableau du document) ---------------------------------
# fc_min/fc_max : bornes en % de la FCmax (FCmax ≈ 220 − âge, ou test réel).
ZONES = {
    "Z1": {
        "nom": "Zone 1 — Récupération",
        "fc_min": 50, "fc_max": 60,
        "effet": "Récupération, circulation sanguine, régénération",
        "filiere": "Aérobie",
        "carburant": "Graisses",
    },
    "Z2": {
        "nom": "Zone 2 — Endurance fondamentale",
        "fc_min": 60, "fc_max": 70,
        "effet": "Base aérobie, capillarisation, utilisation des graisses",
        "filiere": "Aérobie",
        "carburant": "Graisses + glucides",
    },
    "Z3": {
        "nom": "Zone 3 — Tempo / seuil aérobie",
        "fc_min": 70, "fc_max": 80,
        "effet": "Améliore l'endurance sur longue durée",
        "filiere": "Aérobie",
        "carburant": "Glucides + graisses",
    },
    "Z4": {
        "nom": "Zone 4 — Seuil anaérobie",
        "fc_min": 80, "fc_max": 90,
        "effet": "Augmente la tolérance au lactate, prépare à la compétition",
        "filiere": "Aérobie + anaérobie lactique",
        "carburant": "Glucides",
    },
    "Z5": {
        "nom": "Zone 5 — Haute intensité / VO₂max",
        "fc_min": 90, "fc_max": 100,
        "effet": "Développe la VO₂max, l'explosivité et la vitesse",
        "filiere": "Anaérobie lactique + alactique",
        "carburant": "Glucides (ATP-CP en sprint)",
    },
}

# Seuils repris du document, réutilisés dans les explications du PDF.
SEUIL_AEROBIE_PCT = (65, 70)
SEUIL_ANAEROBIE_PCT = (85, 90)


# --- Types de séance ----------------------------------------------------------
# Chaque type déclare :
#   zone        : zone dominante (clé de ZONES ci-dessus)
#   intensite   : 1 (très facile) à 5 (maximal) — sert au calcul de la charge
#                 hebdomadaire et à l'ordre d'allègement (TYPE_DOWNGRADE)
#   facile      : True si la séance compte comme "volume facile" dans la
#                 répartition polarisée (cf. _session_mix). Une semaine bien
#                 construite est majoritairement facile : environ 75-80% du
#                 volume en Z1-Z2, 20-25% en Z3-Z5. C'est le principe le plus
#                 constant de la littérature endurance, et c'est exactement ce
#                 que l'ancienne version ratait — elle empilait de l'endurance
#                 fondamentale faute d'alternatives, pas par choix.
#   distances   : distances de course pour lesquelles ce type est spécifique
#                 (None = pertinent quelle que soit la distance)
#   description : phrase courte affichée dans le PDF sous le nom de la séance
TYPES_SEANCE = {
    "Récupération active": {
        "zone": "Z1", "intensite": 1, "facile": True, "distances": None,
        "description": "Effort très léger destiné à accélérer la récupération sans "
                       "ajouter de fatigue : on doit finir plus frais qu'en commençant.",
    },
    "Endurance fondamentale": {
        "zone": "Z2", "intensite": 2, "facile": True, "distances": None,
        "description": "La base de tout travail d'endurance : allure à laquelle tu peux "
                       "tenir une conversation. C'est elle qui développe le cœur, les "
                       "capillaires et l'économie de mouvement.",
    },
    "Sortie longue": {
        "zone": "Z2", "intensite": 3, "facile": True, "distances": None,
        "description": "Sortie la plus longue de la semaine, à allure d'endurance. "
                       "Développe l'endurance structurelle et l'utilisation des graisses.",
    },
    "Fartlek": {
        "zone": "Z3", "intensite": 3, "facile": False, "distances": None,
        "description": "Jeu d'allures libre : accélérations de durées variables au feeling, "
                       "sans chronomètre. Travaille les changements de rythme en restant ludique.",
    },
    "Tempo": {
        "zone": "Z3", "intensite": 3, "facile": False, "distances": None,
        "description": "Allure soutenue mais contrôlée, tenable environ une heure. "
                       "Repousse le seuil aérobie et l'endurance sur longue durée.",
    },
    "Seuil": {
        "zone": "Z4", "intensite": 4, "facile": False, "distances": None,
        "description": "Travail au seuil anaérobie : l'allure où le lactate commence à "
                       "s'accumuler plus vite qu'il n'est éliminé. Améliore la tolérance à l'effort dur.",
    },
    "VMA longue": {
        "zone": "Z5", "intensite": 4, "facile": False, "distances": None,
        "description": "Intervalles de 2 à 5 minutes proches de la VO₂max. "
                       "C'est le format le plus efficace pour élever le plafond aérobie.",
    },
    "VMA courte": {
        "zone": "Z5", "intensite": 5, "facile": False, "distances": None,
        "description": "Intervalles courts (30 sec à 1 min 30) à intensité très élevée. "
                       "Développe la VMA avec moins de fatigue accumulée que les intervalles longs.",
    },
    "Côtes": {
        "zone": "Z4", "intensite": 4, "facile": False, "distances": None,
        "description": "Répétitions en montée : développe la force spécifique et la "
                       "puissance, avec un impact articulaire plus faible qu'à plat à intensité égale.",
    },
    "Fractionné": {
        "zone": "Z4", "intensite": 4, "facile": False, "distances": None,
        "description": "Alternance de phases intenses et de récupérations. "
                       "Format polyvalent quand aucun objectif chronométrique précis n'est visé.",
    },
    "Sprints / explosivité": {
        "zone": "Z5", "intensite": 5, "facile": False, "distances": None,
        "description": "Efforts maximaux de moins de 10 à 15 secondes, filière "
                       "anaérobie alactique. Développe la vitesse pure et le recrutement nerveux.",
    },
    "Allure spécifique 5 km": {
        "zone": "Z4", "intensite": 4, "facile": False, "distances": ["5km"],
        "description": "Fractions courues exactement à l'allure visée sur 5 km, "
                       "pour ancrer le rythme de course et l'automatiser.",
    },
    "Allure spécifique 10 km": {
        "zone": "Z4", "intensite": 4, "facile": False, "distances": ["10km"],
        "description": "Fractions à l'allure visée sur 10 km, entre le seuil et "
                       "le tempo. Le format le plus proche des conditions de course.",
    },
    "Allure semi-marathon": {
        "zone": "Z3", "intensite": 3, "facile": False, "distances": ["semi"],
        "description": "Blocs longs à l'allure visée sur semi-marathon, pour "
                       "apprendre à tenir une allure soutenue dans la durée.",
    },
    "Allure marathon": {
        "zone": "Z3", "intensite": 3, "facile": False, "distances": ["marathon", "trail_ultra"],
        "description": "Portions à l'allure visée sur marathon, insérées dans "
                       "des sorties longues. Prépare le corps à l'allure de course sur fatigue.",
    },
}

# Type de séance à allure spécifique correspondant à chaque distance visée.
ALLURE_SPECIFIQUE_PAR_DISTANCE = {
    "5km": "Allure spécifique 5 km",
    "10km": "Allure spécifique 10 km",
    "semi": "Allure semi-marathon",
    "marathon": "Allure marathon",
    "trail_ultra": "Allure marathon",
}

DISTANCE_LABELS = {
    "5km": "5 km",
    "10km": "10 km",
    "semi": "semi-marathon",
    "marathon": "marathon",
    "trail_ultra": "trail / ultra",
}


def zone_de(type_seance):
    """Zone dominante d'un type de séance (dict de ZONES), ou None si inconnu."""
    meta = TYPES_SEANCE.get(type_seance)
    return ZONES.get(meta["zone"]) if meta else None


def intensite_de(type_seance):
    """Intensité 1-5 d'un type de séance (2 par défaut si inconnu)."""
    meta = TYPES_SEANCE.get(type_seance)
    return meta["intensite"] if meta else 2


def est_facile(type_seance):
    """True si la séance compte comme volume facile (Z1-Z2)."""
    meta = TYPES_SEANCE.get(type_seance)
    return meta["facile"] if meta else True


def description_de(type_seance):
    """Phrase explicative affichée sous le nom de la séance dans le PDF."""
    meta = TYPES_SEANCE.get(type_seance)
    return meta["description"] if meta else ""


def libelle_zone(type_seance):
    """Ex : "Zone 2 — Endurance fondamentale (60-70% FCmax)". Chaîne vide si
    le type n'est pas répertorié (ne doit pas arriver, mais on ne casse pas
    la génération du PDF pour autant)."""
    zone = zone_de(type_seance)
    if not zone:
        return ""
    return f"{zone['nom']} ({zone['fc_min']}-{zone['fc_max']}% FCmax)"
