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
from logic.recommendation.sport_profiles import resolve_sport_muscles
# Réutilisation en LECTURE SEULE du moteur legacy (même pattern déjà établi
# ailleurs dans ce module pour `logic.exercises_db.SPLITS`/`logic.program_
# builder._split_key_auto`, cf. logic/recommendation/program_builder.py) :
# pas de raison de dupliquer une seconde table muscle-checkbox -> clé moteur
# ni une seconde fonction de réordonnancement par priorité, déjà écrites et
# testées côté legacy.
from logic.program_builder import _resolve_prioritaires, _reorder_by_priority

# Libellé de justification affiché par exercice, un par palier de
# `exercise_order.classify_exercise` — aucune formule, un texte informatif.
RAISON_PAR_TIER = {
    exercise_order.TIER_PRINCIPAL: "Mouvement composé prioritaire pour ce muscle.",
    exercise_order.TIER_SECONDAIRE: "Mouvement composé secondaire ou unilatéral.",
    exercise_order.TIER_ISOLATION: "Travail d'isolation ciblé.",
    exercise_order.TIER_FINISSEUR: "Finisseur à faible coût de fatigue, en fin de séance.",
}

MESSAGE_BUDGET_PLANCHER = (
    "Budget de fatigue estimé dépassé même au volume plancher visé pour chaque muscle : "
    "le volume n'est plus réduit en dessous de ce plancher pour ne pas vider la séance."
)
MESSAGE_REDUCTION_VOLUME = (
    "Volume réduit pendant la construction de la séance pour respecter le budget de "
    "fatigue estimé (finisseurs/isolation retirés en priorité)."
)
MESSAGE_SEANCE_VIDE = (
    "Aucun exercice disponible pour cette séance compte tenu de tes contraintes."
)

# Prompt hors 24 phases (retour Samy, test en conditions réelles : "ça ne va
# pas du tout une séance fait 4 exercices, minimum 3 exercice par muscle et 4
# pour le muscle principal ou le muscle priorisé choisi par la personne").
# REMPLACE l'ancien plancher de VOLUME TOTAL par séance (SESSION_MIN_EXOS,
# 9/10 selon durée) par une répartition explicite PAR MUSCLE ET PAR POSITION
# DE PRIORITÉ (cf. `volume.calculer_repartition_seance`), jugée par Samy plus
# fidèle à un vrai programme (le muscle principal/prioritaire mérite plus de
# volume que les autres, pas un simple total à atteindre peu importe la
# répartition). Cf. `_muscles_ordonnes_par_priorite` ci-dessous pour la
# résolution du muscle prioritaire (choix utilisateur ou sport pratiqué).
MESSAGE_VOLUME_CIBLE_INATTEIGNABLE = (
    "{muscle} : {cible} exercices visés pour ce muscle mais seulement {obtenu} disponible(s) compte "
    "tenu de tes contraintes actuelles (équipement/blessures/exclusions)."
)


def _muscles_ordonnes_par_priorite(profile, target_muscles):
    """Réordonne `target_muscles` pour placer en tête les muscles prioritaires
    de la séance : ceux explicitement cochés par l'utilisateur
    (`variables_json["muscles_prioritaires"]`, réutilise `logic.program_
    builder.MUSCLE_PRIORITY_MAP`/`_resolve_prioritaires` en lecture seule,
    même mécanisme que le moteur legacy) ET ceux sollicités par le sport
    pratiqué en parallèle si l'utilisateur a demandé l'adaptation (cf.
    `sport_profiles.resolve_sport_muscles`). Si aucune priorité n'est
    déclarée, l'ordre natif du split (déjà pensé pour mettre le muscle
    "principal" de la séance en premier, cf. logic/exercises_db.SPLITS) est
    conservé tel quel : c'est LUI qui devient alors le muscle "principal" au
    sens de la répartition positionnelle ci-dessous."""
    variables = getattr(profile, "variables_json", None) or {}
    prioritaires = _resolve_prioritaires(variables.get("muscles_prioritaires"))
    prioritaires = prioritaires | resolve_sport_muscles(profile)
    if not prioritaires:
        return list(target_muscles)
    return _reorder_by_priority(list(target_muscles), prioritaires)


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


def _reduire_volume_si_besoin(par_muscle, budget, warnings, planchers=None):
    """Section 7 : total_fatigue <= budget pendant la construction ; si
    dépassement, réduire le VOLUME (retirer des exercices) avant de
    dégrader la qualité. Retire toujours, en priorité, l'exercice du palier
    le plus "sacrifiable" (finisseur, puis isolation, puis secondaire —
    jamais un mouvement "principal" tant qu'un autre palier reste
    disponible), au score le plus bas au sein de ce palier. Ne descend
    jamais en dessous du plancher explicite du muscle (`planchers[muscle]`,
    cf. `volume.calculer_repartition_seance` — plancher à 1 par défaut si
    absent, comportement historique préservé pour les appelants qui ne
    passent pas ce paramètre)."""
    planchers = planchers or {}

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
            plancher_groupe = planchers.get(groupe["muscle"], 1)
            if len(groupe["exercises"]) <= plancher_groupe:
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


def generate_workout(profile, target_muscles, available_exercises, session_duration,
                      recent_exercises_provider=None):
    """Point d'entrée principal de cette phase.

    profile             : ProfileSnapshot.
    target_muscles      : liste ordonnée de muscles à couvrir dans cette séance
                           (l'ordre est conservé dans la sortie).
    available_exercises : catalogue d'objets Exercise à considérer.
    session_duration     : minutes (int/float) ou libellé questionnaire
                           ("45 min", "1h", "1h - 1h30", "1h30+").
    recent_exercises_provider : callable optionnel `(user_id, window_weeks) ->
                           [exercise_id]`, transmis tel quel à
                           `fallback.run_fallback_cascade`/`selector.
                           select_exercises` (mécanisme de pénalité de
                           récence déjà existant, phases 7/10). Additif
                           (prompt hors 24 phases, retour Samy : "les séances
                           A et B sont souvent identiques") : permet à
                           l'appelant (`logic.recommendation.program_builder.
                           build_program`) de pénaliser les exercices déjà
                           choisis PLUS TÔT DANS LA MÊME SEMAINE (Upper A vs
                           Upper B, PPL x2...), en réutilisant le même levier
                           que la récence inter-semaines plutôt que d'inventer
                           un second mécanisme parallèle. Absent -> comportement
                           strictement inchangé (repli sur l'historique DB
                           habituel, cf. `selector.get_recent_exercises`).

    Retourne {"name", "muscles", "exercises", "estimated_duration", "warnings",
    "profile_analysis", "muscle_floors"} ; ne prescrit ni séries, ni
    répétitions, ni charges (hors périmètre). "profile_analysis" (phase
    19/24, clé ADDITIVE, cf. logic/profile_analysis.py) résume le profil
    (niveau/objectif dominant/contraintes/forces/faiblesses/risques) pour
    expliquer la séance a posteriori — ne participe à AUCUN calcul de
    volume/budget/ordre ici. "muscle_floors" (clé ADDITIVE, prompt hors 24
    phases) expose le plancher d'exercices retenu par muscle (cf.
    `_muscles_ordonnes_par_priorite`/`volume.calculer_repartition_seance`) —
    consommé par `prescription._retirer_exercices_si_besoin` pour ne jamais
    retirer un exercice en dessous de ce plancher lors de l'ajustement du
    budget de fatigue par les séries."""
    # Import différé pour cohérence avec scoring.py (même raison : éviter tout
    # cycle d'import, même si aucun n'existe réellement ici).
    from logic.profile_analysis import analyze_profile

    lookup = {getattr(ex, "exercise_id", None): ex for ex in available_exercises}
    budget = calculate_fatigue_budget(profile)
    warnings = []

    # Le muscle prioritaire (choix utilisateur ou sport pratiqué) est placé
    # en tête -> devient le muscle "principal" au sens de la répartition
    # positionnelle ci-dessous (cf. docstring de `_muscles_ordonnes_par_
    # priorite`). Sans priorité déclarée, l'ordre natif du split (déjà pensé
    # pour mettre son muscle principal en premier) est conservé.
    target_muscles = _muscles_ordonnes_par_priorite(profile, target_muscles)

    # Prompt hors 24 phases (retour Samy) : à partir d'1h de séance, le
    # nombre d'exercices par muscle est fixé par la répartition positionnelle
    # + portions anatomiques (`volume.calculer_repartition_seance`), qui
    # remplace le barème niveau/objectif habituel. En dessous (45 min),
    # l'ancien barème reste utilisé (Samy : "à partir d'une heure").
    nouvelle_repartition = volume._duree_minutes(session_duration) >= volume.SEUIL_NOUVELLE_REPARTITION_MINUTES
    if nouvelle_repartition:
        planchers = volume.calculer_repartition_seance(target_muscles, available_exercises)
    else:
        planchers = {muscle: 1 for muscle in target_muscles}

    par_muscle = []
    for muscle in target_muscles:
        if nouvelle_repartition:
            nombre = planchers[muscle]
        else:
            nombre = volume.calculate_exercise_count(profile, muscle, session_duration)
        resultat = fallback.run_fallback_cascade(
            profile, available_exercises, muscle, nombre,
            recent_exercises_provider=recent_exercises_provider,
        )
        if resultat["warning"]:
            warnings.append(f"{muscle} : {resultat['warning']}")
        if nouvelle_repartition and len(resultat["exercises"]) < nombre:
            warnings.append(MESSAGE_VOLUME_CIBLE_INATTEIGNABLE.format(
                muscle=muscle, cible=nombre, obtenu=len(resultat["exercises"]),
            ))

        enrichis = []
        for e in resultat["exercises"]:
            exo_obj = lookup.get(e["exercise_id"])
            if exo_obj is None:
                continue  # sécurité redondante : l'id provient déjà de available_exercises
            enrichis.append({"exercise": exo_obj, "score": e["score"]})

        par_muscle.append({"muscle": muscle, "exercises": enrichis})

    _reduire_volume_si_besoin(par_muscle, budget, warnings, planchers=planchers)

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
        "muscle_floors": planchers,
    }
