# -*- coding: utf-8 -*-
"""
Budget de fatigue de séance (resolution_11_points_bloquants.md, point 4).

IMPORTANT — périmètre de cette phase : `calculate_fatigue_budget(profile)`
calcule un budget de SÉANCE (utile pour assembler plusieurs exercices dans
une séance et arbitrer entre eux), mais cette phase ne génère pas de séance
(contrainte explicite : "ne pas générer un programme complet"). De plus, le
champ `fatigue_cost` par exercice n'existe pas encore sur le modèle Exercise
(absent du sous-ensemble critique retenu en phase 2/16, cf. architecture_base_
exercices.md qui le prévoit pour une phase d'enrichissement ultérieure).

Cette fonction est donc prête et testée de façon autonome, mais le facteur
"fatigue" de scoring.py reste neutre (0) par exercice tant que ces deux
conditions ne sont pas réunies — documenté explicitement dans scoring.py.
"""

# Valeurs explicitement validées pour "1h - 1h30" et "1h30+". Le questionnaire
# propose aussi "45 min" et "1h" (cf. static/script.js) : aucune valeur n'a
# été validée pour ces deux options dans resolution_11_points_bloquants.md.
# Extrapolation linéaire raisonnable en attendant une validation explicite —
# nécessaire pour que le moteur ne plante jamais sur un profil réel (toute
# valeur du questionnaire actuel doit être gérée).
DUREE_BASE = {
    "45 min": 14,
    "1h": 17,
    "1h - 1h30": 20,
    "1h30+": 26,
}
DUREE_BASE_DEFAUT = DUREE_BASE["1h - 1h30"]  # repli si durée absente/inconnue

NIVEAU_MULTIPLIER = {
    "Débutant complet": 0.8,
    "Quelques mois d'expérience": 0.9,
    "Intermédiaire": 1.0,
    "Avancé": 1.15,
}
NIVEAU_MULTIPLIER_DEFAUT = 1.0

# Le questionnaire actuel propose 4 paliers de sommeil ; resolution_11_points_
# bloquants.md n'en valide que 3 (suffisant/réduit/insuffisant). Mapping :
# "8h et plus"/"7 à 8h" -> suffisant, "6 à 7h" -> réduit, "Moins de 6h" -> insuffisant.
SOMMEIL_MODIFIER = {
    "8h et plus": 0,
    "7 à 8h": 0,
    "6 à 7h": -3,
    "Moins de 6h": -6,
}
SOMMEIL_MODIFIER_DEFAUT = 0  # absent -> on ne pénalise pas sans information

STRESS_MODIFIER = {
    "Faible": 0,
    "Modéré": -2,
    "Élevé": -4,
}
STRESS_MODIFIER_DEFAUT = 0

BUDGET_PLANCHER = 10


def calculate_fatigue_budget(profile):
    """budget_fatigue = base(durée) × multiplicateur(niveau) + modificateur
    (sommeil) + modificateur(stress), jamais sous le plancher (10)."""
    variables = getattr(profile, "variables_json", None) or {}
    duree = variables.get("duree_seance")
    base = DUREE_BASE.get(duree, DUREE_BASE_DEFAUT)

    niveau = getattr(profile, "niveau_musculation", None)
    multiplicateur = NIVEAU_MULTIPLIER.get(niveau, NIVEAU_MULTIPLIER_DEFAUT)

    sommeil = getattr(profile, "sommeil", None)
    mod_sommeil = SOMMEIL_MODIFIER.get(sommeil, SOMMEIL_MODIFIER_DEFAUT)

    stress = getattr(profile, "stress", None)
    mod_stress = STRESS_MODIFIER.get(stress, STRESS_MODIFIER_DEFAUT)

    budget = base * multiplicateur + mod_sommeil + mod_stress
    return max(budget, BUDGET_PLANCHER)
