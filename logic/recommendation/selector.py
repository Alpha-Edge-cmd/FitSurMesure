# -*- coding: utf-8 -*-
"""
Sélection d'exercices pour un muscle donné (phase 7/16) : "pour ce muscle,
quels exercices choisir parmi les candidats compatibles ?" — pas de séance,
pas de split, pas de volume hebdomadaire, pas de séries/répétitions (hors
périmètre de cette phase, cf. architecture_v2_consolidation.md phase 4/7 du
plan d'évolution).

Réutilise strictement `recommendation.filters` (passe 1) et
`recommendation.scoring` (passe 2), sans les redéfinir.

Phase 10/16 : `get_recent_exercises`/`get_disliked_exercises` étaient de
simples stubs retournant toujours [] (tables futures non créées). Elles
délèguent désormais à `history.py`/`feedback.py` (tables `ExerciseUsageLog`/
`ExerciseFeedback`, créées dans cette même phase) — signatures inchangées,
seul le corps change (aucun appelant existant n'est impacté). `select_exercises`
intègre en plus les signaux de `feedback.py` (blessures dérivées, exclusion
ciblée, ajustements de score) sans jamais modifier `filters.py`/`scoring.py`
eux-mêmes, ni relâcher une exclusion de sécurité.
"""
import hashlib

from logic.feedback_learning import apply_user_preferences_to_score, calculate_user_preferences
from logic.recommendation import diversity, feedback, filters, history, scoring

# Phase 21/24 : `logic/feedback_learning.py` (voir docstring de ce module)
# apporte une lecture AGRÉGÉE (pas exercice par exercice) des feedbacks d'un
# utilisateur — préférence/douleur/difficulté réelle/progression -> bonus/
# malus de score appliqués ICI, en aval de `scoring.score_exercise`, jamais
# dans `scoring.py` lui-même (consigne : "ne jamais modifier le scoring de
# base"). Couche additionnelle, purement externe, au même titre que la
# pénalité de récence et `feedback.apply_score_adjustments` déjà en place.

RECENCE_FENETRE_NORMALE = 8  # semaines
RECENCE_FENETRE_REDUITE = 4  # semaines (fallback étape 1)

# Pénalité de récence : aucune valeur chiffrée n'a été validée dans les
# documents de conception pour ce point précis (contrairement aux facteurs de
# scoring.py, qui ont des formules exactes) — valeur de départ documentée,
# à calibrer empiriquement, cohérente avec l'esprit de
# resolution_11_points_bloquants.md (pénalité dégressive, jamais une
# exclusion).
PENALITE_RECENCE = 15


# --- Interfaces préparées pour l'historique/feedback (tables futures) ------

def get_recent_exercises(user_id, window_weeks=RECENCE_FENETRE_NORMALE):
    """Branché sur `ExerciseUsageLog` depuis la phase 10/16 (`history.py`).
    Retourne toujours [] si `user_id` est None ou en l'absence d'historique
    — comportement identique à l'ancien stub dans ce cas, donc aucune
    régression pour les appels existants sans `user_id` (phases 6 à 9)."""
    if user_id is None:
        return []
    details = history.get_recent_exercises(user_id, weeks=window_weeks)
    return [d["exercise_id"] for d in details]


def get_disliked_exercises(user_id):
    """Branché sur `ExerciseFeedback` ("deteste") depuis la phase 10/16
    (`feedback.py`). Retourne toujours [] si `user_id` est None. Ne concerne
    JAMAIS les exclusions de sécurité (douleur/blessure), qui passent
    exclusivement par `filters.py` (inchangé)."""
    if user_id is None:
        return []
    return feedback.get_disliked_exercise_ids(user_id)


def _survivants_passe1(profile, candidats, disliked_ids, feedback_repository):
    survivants = []
    for ex in candidats:
        if ex.exercise_id in disliked_ids:
            continue  # exclusion "goût" (jamais sécurité) — retirée à l'étape 2 du fallback
        if filters.exclusion_reason(profile, ex, feedback_repository=feedback_repository):
            continue
        survivants.append(ex)
    return survivants


# Écart de score en dessous duquel deux exercices sont considérés comme
# équivalents pour ce profil. Sur un score composite qui agrège objectif,
# anatomie, morphologie, niveau, matériel et historique, quelques points
# d'écart ne traduisent aucune supériorité réelle d'un mouvement sur l'autre.
# C'est cette marge qui rend la rotation possible sans jamais dégrader la
# qualité de la sélection.
TOLERANCE_EQUIVALENCE = 6


def _graine_rotation(profile, target_muscle, user_id):
    """Décalage stable, propre à ce profil et à ce muscle.

    Déterministe (même profil + même muscle -> même décalage, donc même
    programme si rien ne change), mais différent d'un utilisateur à l'autre et
    d'un muscle à l'autre — c'est ce qui fait que deux personnes au profil
    voisin n'obtiennent pas la même séance, et que les blocs "pectoraux" et
    "dos" d'une même séance ne piochent pas tous au même rang.

    Reprend le principe de `_variante_jitter` (cardio_builder.py) et de
    `_signature_jitter` (program_builder.py), déjà utilisés ailleurs dans le
    moteur pour exactement le même besoin.
    """
    parts = [
        str(user_id or ""),
        str(target_muscle or ""),
        str(getattr(profile, "objectif_principal", "") or ""),
        str(getattr(profile, "niveau_musculation", "") or ""),
        str(getattr(profile, "signature", "") or ""),
    ]
    graine = "|".join(parts)
    return int(hashlib.sha256(graine.encode("utf-8")).hexdigest()[:8], 16)


def select_exercises(
    profile,
    available_exercises,
    target_muscle,
    number_required,
    user_id=None,
    recent_exercises_provider=None,
    recency_window_weeks=RECENCE_FENETRE_NORMALE,
    enforce_family_diversity=True,
    reintegrate_disliked=False,
    disliked_provider=None,
    feedback_repository=None,
):
    """Sélectionne jusqu'à `number_required` exercices pour `target_muscle`,
    triés par score décroissant puis réajustés par la diversité de famille à
    chaque étape (glouton : on ne prend pas juste le top-N brut, on
    recalcule l'ajustement de diversité après chaque choix). Peut retourner
    moins de `number_required` si le pool de candidats est insuffisant —
    c'est à l'appelant (fallback.py) de décider quoi en faire.

    Les paramètres `recency_window_weeks`/`enforce_family_diversity`/
    `reintegrate_disliked` sont les leviers de relâchement utilisés par la
    cascade de secours (fallback.py) : ce module ne connaît pas la cascade
    lui-même, il expose juste les boutons nécessaires."""
    if number_required <= 0:
        return []

    # --- Phase 10/16 : signaux de feedback réels (remplacent les stubs) ------
    # Chargés une seule fois par appel (évite une requête par exercice dans
    # les boucles ci-dessous). `feedbacks` reste [] si `user_id` est None ou
    # en l'absence de feedback -> tout le bloc suivant est un no-op strict,
    # donc aucune régression pour les appels existants des phases 6 à 9.
    feedbacks = feedback.load_feedback(user_id)

    effective_profile = profile
    if feedbacks:
        blessures_effectives = feedback.compute_effective_blessures(profile, feedbacks, available_exercises)
        if blessures_effectives != (getattr(profile, "blessures", None) or {}):
            effective_profile = feedback.EffectiveProfileView(profile, blessures=blessures_effectives)

    # Exclusion ciblée (point 9, cas "sans dominante claire") : ne construit
    # un repository dérivé que si l'appelant n'en a pas déjà fourni un
    # (ex. interface `feedback_repository` d'un futur appelant explicite) —
    # dans ce cas, on respecte le choix de l'appelant plutôt que de l'écraser.
    effective_feedback_repository = feedback_repository
    if effective_feedback_repository is None and feedbacks:
        effective_feedback_repository = feedback.build_feedback_repository(feedbacks, available_exercises)

    candidats_muscle = [
        ex for ex in available_exercises
        if getattr(ex, "muscle_principal", None) == target_muscle and getattr(ex, "actif", True)
    ]

    disliked_ids = set()
    if not reintegrate_disliked:
        disliked_get = disliked_provider or get_disliked_exercises
        disliked_ids = set(disliked_get(user_id))

    survivants = _survivants_passe1(effective_profile, candidats_muscle, disliked_ids, effective_feedback_repository)

    recent_get = recent_exercises_provider or get_recent_exercises
    recent_ids = set(recent_get(user_id, window_weeks=recency_window_weeks))

    # Phase 21/24 : signaux agrégés (préférence/douleur/difficulté réelle/
    # progression), calculés une seule fois par appel — reste {} neutre si
    # `user_id` est None ou en l'absence de tout feedback (aucune régression
    # pour les appels existants des phases 6 à 20, cf. logic/feedback_
    # learning.calculate_user_preferences).
    preferences_utilisateur = calculate_user_preferences(user_id)

    scored = []
    for ex in survivants:
        result = scoring.score_exercise(effective_profile, ex, feedback_repository=effective_feedback_repository)
        if result["excluded"]:
            continue  # ne devrait plus arriver (déjà filtré ci-dessus), sécurité redondante assumée
        score = result["score_final"]
        if ex.exercise_id in recent_ids:
            score = max(0, score - PENALITE_RECENCE)
        if feedbacks:
            score = feedback.apply_score_adjustments(effective_profile, ex, score, feedbacks)
        # Phase 21/24 : couche EXTERNE supplémentaire (logic/feedback_learning.py),
        # jamais dans scoring.py — bonus/malus agrégés sur l'historique complet
        # de l'utilisateur, distincts des ajustements ponctuels ci-dessus.
        score = apply_user_preferences_to_score(effective_profile, ex, score, preferences_utilisateur)
        # "profile_analysis" (phase 19/24) : propagé tel quel depuis
        # scoring.score_exercise (qui l'a déjà calculé, cf. logic/profile_
        # analysis.py) — clé ADDITIVE, ne change ni le score ni le tri.
        scored.append({
            "exercise": ex, "score": score, "details": result["details"],
            "profile_analysis": result.get("profile_analysis"),
        })

    scored.sort(key=lambda c: c["score"], reverse=True)

    # --- Rotation par profil et par séance -----------------------------------
    # Retour Samy : « ce sont absolument toujours les mêmes exercices ».
    #
    # Diagnostic : la sélection était entièrement déterministe. Un score par
    # exercice, un tri, et on prend les N premiers. Deux profils identiques —
    # ou le même profil qui régénère son programme — obtenaient donc
    # rigoureusement la même liste. Le SEUL mécanisme anti-répétition était
    # `PENALITE_RECENCE`, qui ne s'applique qu'à un utilisateur connecté ayant
    # déjà cliqué « J'ai réalisé » sur des séances précédentes : sur un premier
    # programme, il ne se passait strictement rien.
    #
    # Correctif : on n'écrase pas le classement, on l'assouplit. Les exercices
    # dont le score est proche du meilleur sont considérés comme équivalents
    # (ils le sont : un écart de quelques points sur un score composite n'a
    # aucune signification pratique), et on départage à l'intérieur de ce
    # groupe par un décalage stable dérivé de la signature du profil et du
    # créneau demandé. Conséquences :
    #   - deux utilisateurs différents n'ont pas les mêmes exercices ;
    #   - les séances A et B d'un même programme diffèrent ;
    #   - une régénération donne autre chose ;
    #   - et un même profil régénérant à l'identique retrouve le même programme
    #     (déterminisme préservé, comme partout ailleurs dans le moteur).
    #
    # Un exercice nettement moins bon ne remonte jamais : le garde-fou est
    # l'écart de score, pas le hasard.
    rotation = _graine_rotation(profile, target_muscle, user_id)

    selected = []
    remaining = list(scored)
    while remaining and len(selected) < number_required:
        evalues = []
        for i, candidate in enumerate(remaining):
            adjusted = candidate["score"]
            if enforce_family_diversity:
                deja = [s["exercise"] for s in selected]
                adjusted += diversity.calculate_diversity_bonus(candidate["exercise"], deja)
                adjusted += diversity.calculate_family_penalty(candidate["exercise"], deja)
            evalues.append((adjusted, i, candidate))

        meilleur = max(a for a, _, _ in evalues)
        # Groupe des candidats "à égalité pratique" avec le meilleur.
        equivalents = [(a, i, c) for a, i, c in evalues if a >= meilleur - TOLERANCE_EQUIVALENCE]
        # Ordre stable (par score décroissant puis identifiant) avant rotation,
        # pour que le résultat ne dépende jamais de l'ordre d'itération du
        # catalogue.
        equivalents.sort(key=lambda t: (-t[0], getattr(t[2]["exercise"], "exercise_id", "")))

        pos = (rotation + len(selected)) % len(equivalents)
        best_adjusted, best_idx, _ = equivalents[pos]

        chosen = remaining.pop(best_idx)
        chosen["score_ajuste"] = best_adjusted
        selected.append(chosen)

    return selected
