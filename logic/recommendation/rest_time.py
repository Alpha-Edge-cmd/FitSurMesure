# -*- coding: utf-8 -*-
"""
Temps de repos recommandé entre séries (phase 9/16, section 6). Valeurs
initiales fournies telles quelles par la consigne ; aucun barème chiffré
n'a été validé pour la modulation par niveau/objectif/fatigue disponible
dans les documents de conception antérieurs — premier jet documenté, comme
intensity.py et prescription.py, à calibrer empiriquement.
"""
from logic.recommendation import exercise_order, objectives
from logic.recommendation.fatigue import BUDGET_PLANCHER, calculate_fatigue_budget

# (min, max) secondes par catégorie — valeurs fournies par la consigne
# section 6, reprises telles quelles.
PLAGE_REPOS_SECONDES = {
    "lourd_compose": (120, 180),
    "hypertrophie_classique": (60, 120),
    "isolation": (45, 90),
    "explosivite": (120, 180),
}

# Position dans la plage selon le niveau (repli "Intermédiaire" si niveau
# absent/inconnu) : un niveau plus avancé manipule des charges plus lourdes
# et récupère différemment -> position plus haute dans la plage. Interprétation
# documentée, pas une formule validée.
POSITION_REPOS_PAR_NIVEAU = {
    "Débutant complet": 0.0,
    "Quelques mois d'expérience": 0.33,
    "Intermédiaire": 0.66,
    "Avancé": 1.0,
}
POSITION_REPOS_PAR_NIVEAU_DEFAUT = POSITION_REPOS_PAR_NIVEAU["Intermédiaire"]

# Si le budget de fatigue de séance (fatigue.py) est proche de son plancher
# (séance courte / sommeil dégradé / stress élevé cumulés), le temps
# disponible est déjà compté : on resserre légèrement le repos plutôt que de
# sacrifier davantage de volume/qualité (cohérent avec la phase 8, section 5 :
# "séance courte -> priorité aux exercices importants dans le temps
# imparti"). Ajustement documenté, pas une formule validée.
SEUIL_BUDGET_SERRE = BUDGET_PLANCHER + 5
REDUCTION_BUDGET_SERRE_SECONDES = 20


def _categorie_repos(profile, exercise):
    """Détermine la catégorie de repos (section 6) : "explosivité" prime
    (repos longs quel que soit le palier de mouvement, la consigne la liste
    à part) ; sinon "mouvement lourd composé" si l'objectif dominant est la
    force ET que l'exercice est un mouvement composé (principal/secondaire) ;
    sinon "isolation" pour les paliers isolation/finisseur ; "hypertrophie
    classique" en repli."""
    vector = objectives.get_objective_vector(profile)
    dominant = max(vector, key=vector.get)
    tier = exercise_order.classify_exercise(exercise)

    if dominant == "explosivite":
        return "explosivite"
    if dominant == "force" and tier in (exercise_order.TIER_PRINCIPAL, exercise_order.TIER_SECONDAIRE):
        return "lourd_compose"
    if tier in (exercise_order.TIER_ISOLATION, exercise_order.TIER_FINISSEUR):
        return "isolation"
    return "hypertrophie_classique"


def calculate_rest_time(exercise, profile):
    """calculate_rest_time(exercise, profile) -> secondes (int), arrondi à 5
    secondes. Adapte la plage de base (section 6) selon le niveau (position
    dans la plage) et le budget de fatigue disponible (resserrement si le
    budget est proche de son plancher)."""
    categorie = _categorie_repos(profile, exercise)
    borne_min, borne_max = PLAGE_REPOS_SECONDES[categorie]

    niveau = getattr(profile, "niveau_musculation", None)
    position = POSITION_REPOS_PAR_NIVEAU.get(niveau, POSITION_REPOS_PAR_NIVEAU_DEFAUT)
    secondes = borne_min + (borne_max - borne_min) * position

    budget = calculate_fatigue_budget(profile)
    if budget <= SEUIL_BUDGET_SERRE:
        secondes = max(borne_min, secondes - REDUCTION_BUDGET_SERRE_SECONDES)

    return int(round(secondes / 5.0) * 5)
