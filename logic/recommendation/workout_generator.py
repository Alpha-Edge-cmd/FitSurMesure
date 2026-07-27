# -*- coding: utf-8 -*-
"""
Générateur de séance (phase 8/16) : transforme un profil + une liste de
muscles ciblés + un catalogue d'exercices disponibles + une durée en une
STRUCTURE de séance cohérente (quels exercices, dans quel ordre, pour
quels muscles) — ne gère PAS encore : séries, répétitions, charges,
progression long terme, génération PDF (hors périmètre, cf.
architecture_v2_consolidation.md, étapes ultérieures du plan d'évolution).

Ne redéfinit aucune règle déjà validée : réutilise strictement
`selector`/`scoring`/`filters` (phases 6/7, via `fallback.run_fallback_cascade`,
qui garantit déjà "jamais de liste vide silencieuse, jamais un exercice
dangereux même en secours") ainsi que `fatigue.calculate_fatigue_budget`
(phase 6). `volume.py` détermine le nombre d'exercices par muscle,
`exercise_order.py` détermine leur ordre au sein d'une séance ; ce module
se contente d'orchestrer les trois pour produire un objet "séance".
"""
from logic.recommendation import exercise_order, fallback, volume
from logic.recommendation.fatigue import calculate_fatigue_budget

# Libellé de justification affiché par exercice, un par palier de
# `exercise_order.classify_exercise` — aucune formule, un texte informatif.
RAISON_PAR_TIER = {
    exercise_order.TIER_PRINCIPAL: "Mouvement composé prioritaire pour ce muscle.",
    exercise_order.TIER_SECONDAIRE: "Mouvement composé secondaire ou unilatéral.",
    exercise_order.TIER_ISOLATION: "Travail d'isolation ciblé.",
    exercise_order.TIER_FINISSEUR: "Finisseur à faible coût de fatigue, en fin de séance.",
}

MESSAGE_BUDGET_PLANCHER = (
    "Budget de fatigue estimé dépassé même au volume plancher (1 exercice/muscle) : "
    "le volume n'est plus réduit en dessous de ce plancher pour ne pas vider la séance."
)
MESSAGE_REDUCTION_VOLUME = (
    "Volume réduit pendant la construction de la séance pour respecter le budget de "
    "fatigue estimé (finisseurs/isolation retirés en priorité)."
)
MESSAGE_SEANCE_VIDE = (
    "Aucun exercice disponible pour cette séance compte tenu de tes contraintes."
)


def estimate_exercise_fatigue_cost(exercise):
    """Coût de fatigue estimé d'UN exercice, pour arbitrer le volume total
    d'une séance face à `calculate_fatigue_budget(profile)` (section 7 de la
    consigne). `fatigue_cost` par exercice n'existe pas encore au catalogue
    (sous-ensemble critique retenu en phase 2/16, cf. Exercise) : ce proxy,
    documenté et à calibrer empiriquement, combine `technical_complexity`,
    `stability_demand` et le caractère composé du mouvement (mêmes signaux
    que ceux déjà utilisés en départage dans `exercise_order.py`)."""
    complexite = getattr(exercise, "technical_complexity", None) or 2
    stabilite = {"faible": 0, "modere": 1, "eleve": 2}.get(
        getattr(exercise, "stability_demand", None), 1
    )
    compose = getattr(exercise, "movement_type", None) in exercise_order.COMPOUND_MOVEMENT_TYPES
    return complexite + stabilite + (2 if compose else 0)


def estimate_session_fatigue(exercises):
    """Somme des coûts estimés (`estimate_exercise_fatigue_cost`) sur une
    liste d'objets `Exercise`."""
    return sum(estimate_exercise_fatigue_cost(ex) for ex in exercises)


def _nom_seance(target_muscles):
    if not target_muscles:
        return "Séance"
    return "Séance " + " / ".join(str(m).capitalize() for m in target_muscles)


def _reduire_volume_si_besoin(par_muscle, budget, warnings):
    """Section 7 : total_fatigue <= budget pendant la construction ; si
    dépassement, réduire le VOLUME (retirer des exercices) avant de
    dégrader la qualité. Retire toujours, en priorité, l'exercice du palier
    le plus "sacrifiable" (finisseur, puis isolation, puis secondaire —
    jamais un mouvement "principal" tant qu'un autre palier reste
    disponible), au score le plus bas au sein de ce palier. Ne descend
    jamais en dessous d'1 exercice par muscle ciblé (plancher explicite)."""

    def total_fatigue():
        return sum(
            estimate_exercise_fatigue_cost(item["exercise"])
            for groupe in par_muscle
            for item in groupe["exercises"]
        )

    reduction_appliquee = False
    while total_fatigue() > budget:
        pire_groupe, pire_tier = None, -1
        for groupe in par_muscle:
            if len(groupe["exercises"]) <= 1:
                continue
            for item in groupe["exercises"]:
                tier = exercise_order.TIER_ORDER[exercise_order.classify_exercise(item["exercise"])]
                if tier > pire_tier:
                    pire_tier, pire_groupe = tier, groupe

        if pire_groupe is None:
            warnings.append(MESSAGE_BUDGET_PLANCHER)
            break

        candidats = [
            i for i, item in enumerate(pire_groupe["exercises"])
            if exercise_order.TIER_ORDER[exercise_order.classify_exercise(item["exercise"])] == pire_tier
        ]
        pire_index = min(candidats, key=lambda i: pire_groupe["exercises"][i]["score"])
        pire_groupe["exercises"].pop(pire_index)
        reduction_appliquee = True

    if reduction_appliquee:
        warnings.append(MESSAGE_REDUCTION_VOLUME)


def generate_workout(profile, target_muscles, available_exercises, session_duration):
    """Point d'entrée principal de cette phase.

    profile             : ProfileSnapshot.
    target_muscles      : liste ordonnée de muscles à couvrir dans cette séance
                           (l'ordre est conservé dans la sortie).
    available_exercises : catalogue d'objets Exercise à considérer.
    session_duration     : minutes (int/float) ou libellé questionnaire
                           ("45 min", "1h", "1h - 1h30", "1h30+").

    Retourne {"name", "muscles", "exercises", "estimated_duration", "warnings",
    "profile_analysis"} ; ne prescrit ni séries, ni répétitions, ni charges
    (hors périmètre). "profile_analysis" (phase 19/24, clé ADDITIVE, cf.
    logic/profile_analysis.py) résume le profil (niveau/objectif dominant/
    contraintes/forces/faiblesses/risques) pour expliquer la séance a
    posteriori — ne participe à AUCUN calcul de volume/budget/ordre ici."""
    # Import différé pour cohérence avec scoring.py (même raison : éviter tout
    # cycle d'import, même si aucun n'existe réellement ici).
    from logic.profile_analysis import analyze_profile

    lookup = {getattr(ex, "exercise_id", None): ex for ex in available_exercises}
    budget = calculate_fatigue_budget(profile)
    warnings = []

    par_muscle = []
    for muscle in target_muscles:
        nombre = volume.calculate_exercise_count(profile, muscle, session_duration)
        resultat = fallback.run_fallback_cascade(profile, available_exercises, muscle, nombre)
        if resultat["warning"]:
            warnings.append(f"{muscle} : {resultat['warning']}")

        enrichis = []
        for e in resultat["exercises"]:
            exo_obj = lookup.get(e["exercise_id"])
            if exo_obj is None:
                continue  # sécurité redondante : l'id provient déjà de available_exercises
            enrichis.append({"exercise": exo_obj, "score": e["score"]})

        par_muscle.append({"muscle": muscle, "exercises": enrichis})

    _reduire_volume_si_besoin(par_muscle, budget, warnings)

    exercices_sortie = []
    for groupe in par_muscle:
        for item in exercise_order.sort_exercises_for_workout(groupe["exercises"]):
            ex = item["exercise"]
            tier = exercise_order.classify_exercise(ex)
            exercices_sortie.append({
                "exercise_id": ex.exercise_id,
                "name": getattr(ex, "name", None),
                "family": getattr(ex, "family", None),
                "muscle_principal": getattr(ex, "muscle_principal", None),
                "score": item["score"],
                "raison_selection": RAISON_PAR_TIER[tier],
            })

    if not exercices_sortie:
        warnings.append(MESSAGE_SEANCE_VIDE)

    minutes = len(exercices_sortie) * volume.TEMPS_PAR_EXERCICE_MINUTES
    estimated_duration = f"{minutes} min (échauffement exclu)"

    return {
        "name": _nom_seance(target_muscles),
        "muscles": list(target_muscles),
        "exercises": exercices_sortie,
        "estimated_duration": estimated_duration,
        "warnings": warnings,
        "profile_analysis": analyze_profile(profile),
    }
