# -*- coding: utf-8 -*-
"""
Moteur de recommandation FitSurMesure V2 (phase 6/16).

Répond uniquement à : "pour ce profil, quels exercices sont compatibles et
quel est leur score de pertinence ?" — pas de génération de séance, pas de
prescription séries/répétitions, pas de progression (hors périmètre de
cette phase, cf. resolution_11_points_bloquants.md et
architecture_v2_consolidation.md, phase 4 du plan d'évolution).

Sous-modules :
  - filters.py       : passe 1, filtrage dur (sécurité avant tout).
  - objectives.py     : mapping objectif utilisateur -> vecteur interne.
  - biomechanics.py   : compatibilité biomécanique individuelle + morphologie.
  - fatigue.py        : budget de fatigue de séance (formule seule, pas encore
                        consommée par exercice — cf. docstring de fatigue.py).
  - scoring.py        : orchestration, fonction principale score_exercise().

Phase 7/16 ajoute la sélection d'exercices par muscle (pas encore de séance) :
  - selector.py       : select_exercises(), interfaces get_recent_exercises()/
                        get_disliked_exercises() (stubs, tables futures).
  - diversity.py      : bonus/malus de diversité par famille.
  - fallback.py       : cascade de secours en 5 étapes, garantie anti-liste
                        vide, fonction principale run_fallback_cascade().

Phase 8/16 ajoute la construction de l'ARCHITECTURE d'une séance (pas encore
séries/répétitions/charges/PDF) :
  - volume.py           : calculate_exercise_count() — combien d'exercices
                          par muscle selon niveau/objectif/durée.
  - exercise_order.py   : sort_exercises_for_workout() — ordre (composé
                          d'abord, isolation/finisseur en fin).
  - workout_generator.py : generate_workout(), orchestration principale,
                          arbitrage volume vs budget de fatigue.

Phase 9/16 ajoute la PRESCRIPTION d'entraînement (pas encore de progression/
auto-régulation/PDF) :
  - intensity.py        : calculate_intensity() — faible/modérée/élevée.
  - rest_time.py        : calculate_rest_time() — repos entre séries.
  - prescription.py     : generate_prescription(), orchestration principale
                          (séries, répétitions, repos, intensité, notes).

Phase 10/16 connecte le moteur à la base de données (tables `ExerciseUsageLog`/
`ExerciseFeedback`, `logic/models.py`) sans changer aucune règle métier
déjà validée :
  - history.py    : lecture d'historique/feedback (get_recent_exercises,
                    get_exercise_feedback) — branché sur selector.py, qui
                    n'exposait jusqu'ici que des stubs retournant [].
  - feedback.py   : traduit les feedbacks en signaux moteur (exclusion douce
                    "deteste", exclusion sécurité "douleur_gene" selon la
                    règle du point 9, ajustements de score "trop_difficile"/
                    "trop_facile") — jamais de contournement de sécurité.

Phase 15/16 ajoute une façon SÉCURISÉE de fournir la liste d'exercices au
moteur, sans changer aucun des modules ci-dessus :
  - catalog_provider.py : get_recommendation_catalog() — catalogue V2
                    approuvé (logic/exercise_catalog_service.py), avec repli
                    automatique sur le catalogue legacy si aucun exercice
                    n'est encore approuvé. Non branché automatiquement dans
                    le pipeline existant (cf. limites de la phase) : une
                    simple fonction prête à être appelée par l'appelant du
                    moteur (logic/program_service.py) lors d'une phase
                    ultérieure de bascule.
"""
from logic.recommendation.scoring import score_exercise, evaluate_exercises
from logic.recommendation.fallback import run_fallback_cascade
from logic.recommendation.selector import select_exercises
from logic.recommendation.workout_generator import generate_workout
from logic.recommendation.prescription import generate_prescription, determine_rep_range
from logic.recommendation.intensity import calculate_intensity
from logic.recommendation.rest_time import calculate_rest_time
from logic.recommendation.history import get_recent_exercises, get_exercise_feedback
from logic.recommendation.feedback import get_disliked_exercise_ids
from logic.recommendation.catalog_provider import get_recommendation_catalog

__all__ = [
    "score_exercise",
    "evaluate_exercises",
    "select_exercises",
    "run_fallback_cascade",
    "generate_workout",
    "generate_prescription",
    "determine_rep_range",
    "calculate_intensity",
    "calculate_rest_time",
    "get_recent_exercises",
    "get_exercise_feedback",
    "get_disliked_exercise_ids",
    "get_recommendation_catalog",
]
