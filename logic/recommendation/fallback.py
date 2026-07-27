# -*- coding: utf-8 -*-
"""
Cascade de secours (resolution_11_points_bloquants.md, point 8) : dégrade
progressivement les contraintes de VARIÉTÉ/PRÉFÉRENCE quand le pool de
candidats est insuffisant — ne touche JAMAIS à la sécurité (douleur,
blessure, exclusion dure), qui reste appliquée à chaque étape via
`filters.exclusion_reason`, systématiquement.

Étapes :
  0. Filtrage complet (fenêtre de récence 8 semaines, exercices détestés
     écartés, diversité de famille appliquée).
  1. Fenêtre de récence réduite à 4 semaines.
  2. Exercices détestés sans raison physique réintégrés (jamais douleur/
     blessure/sécurité, cf. selector._survivants_passe1).
  3. Diversité de famille relâchée (répétition de famille autorisée).
  4. Nombre d'exercices demandé réduit à ce qui est réellement disponible
     (avertissement explicite, pas d'exercice inventé).
  5. Dernier recours : aucun candidat trouvé même dégradé -> liste vide avec
     avertissement explicite (jamais un exercice dangereux, jamais une
     liste vide silencieuse).
"""
from logic.recommendation import selector

RECENCE_FENETRE_REDUITE = selector.RECENCE_FENETRE_REDUITE


def _to_result(selection, warning, fallback_level):
    return {
        "exercises": [
            {
                "exercise_id": c["exercise"].exercise_id,
                "name": getattr(c["exercise"], "name", None),
                "family": getattr(c["exercise"], "family", None),
                "score": c["score"],
            }
            for c in selection
        ],
        "warning": warning,
        "fallback_level": fallback_level,
    }


def run_fallback_cascade(
    profile,
    available_exercises,
    target_muscle,
    number_required,
    user_id=None,
    recent_exercises_provider=None,
    disliked_provider=None,
    feedback_repository=None,
):
    """Point d'entrée principal de cette phase : garantit un résultat
    structuré, jamais une liste vide sans explication (contrainte "garantie
    anti-liste vide")."""
    common_kwargs = dict(
        user_id=user_id,
        recent_exercises_provider=recent_exercises_provider,
        disliked_provider=disliked_provider,
        feedback_repository=feedback_repository,
    )

    # Étape 0 — filtrage complet, rien de dégradé.
    selection = selector.select_exercises(
        profile, available_exercises, target_muscle, number_required,
        recency_window_weeks=selector.RECENCE_FENETRE_NORMALE,
        enforce_family_diversity=True, reintegrate_disliked=False,
        **common_kwargs,
    )
    if len(selection) >= number_required:
        return _to_result(selection[:number_required], None, 0)

    # Étape 1 — fenêtre de récence réduite (8 -> 4 semaines).
    selection = selector.select_exercises(
        profile, available_exercises, target_muscle, number_required,
        recency_window_weeks=RECENCE_FENETRE_REDUITE,
        enforce_family_diversity=True, reintegrate_disliked=False,
        **common_kwargs,
    )
    if len(selection) >= number_required:
        return _to_result(selection[:number_required], None, 1)

    # Étape 2 — réintégration des exercices détestés sans raison physique
    # (jamais douleur/blessure : filters.exclusion_reason reste appliqué).
    selection = selector.select_exercises(
        profile, available_exercises, target_muscle, number_required,
        recency_window_weeks=RECENCE_FENETRE_REDUITE,
        enforce_family_diversity=True, reintegrate_disliked=True,
        **common_kwargs,
    )
    if len(selection) >= number_required:
        return _to_result(selection[:number_required], None, 2)

    # Étape 3 — diversité de famille relâchée (répétition autorisée).
    selection = selector.select_exercises(
        profile, available_exercises, target_muscle, number_required,
        recency_window_weeks=RECENCE_FENETRE_REDUITE,
        enforce_family_diversity=False, reintegrate_disliked=True,
        **common_kwargs,
    )
    if len(selection) >= number_required:
        return _to_result(selection[:number_required], None, 3)

    # Étape 4 — on a au moins un candidat, mais pas assez : on réduit le
    # nombre demandé plutôt que d'inventer un exercice ou de forcer un
    # mauvais choix.
    if len(selection) > 0:
        warning = (
            f"Nombre d'exercices réduit à {len(selection)} (au lieu de {number_required}) "
            f"pour ce muscle, faute de candidats suffisants compte tenu de tes contraintes."
        )
        return _to_result(selection, warning, 4)

    # Étape 5 — dernier recours : même dégradé au maximum, aucun candidat ne
    # passe le filtrage de sécurité. Jamais de liste vide silencieuse.
    warning = "Aucun exercice disponible pour ce muscle compte tenu de tes contraintes."
    return _to_result([], warning, 5)
