# -*- coding: utf-8 -*-
"""
Interactions utilisateur sur un programme déjà généré (phase 23/24),
déclenchées depuis l'interface `/my-program` (cf. app.py, templates/
my_program.html, static/my_program.js).

Ce module ne fait QUE PERSISTER des lignes dans deux tables déjà prévues par
le moteur depuis la phase 10/16 (`ExerciseUsageLog`, `ExerciseFeedback`,
cf. logic/models.py) : il ne redéfinit, n'appelle et ne modifie AUCUNE règle
de scoring/sélection/recommandation. Conformément à la consigne explicite de
cette phase ("Ne pas toucher au moteur backend"), les fichiers suivants ne
sont PAS touchés : logic/recommendation/* (scoring.py, selector.py,
workout_generator.py, prescription.py, history.py, feedback.py...),
logic/recommendation/program_builder.py, logic/program_personalization.py,
logic/feedback_learning.py, logic/program_repository.py, logic/program_
validation.py. Ce module se contente d'appeler `history.record_exercise_
usage` (déjà écrit en phase 10, jamais modifié ici) et d'ajouter une ligne
`ExerciseFeedback` par l'ORM standard — la traduction de ces données en
signaux de recommandation reste entièrement la responsabilité de
`logic/recommendation/feedback.py` et `logic/feedback_learning.py`
(phases 10 et 21), qui les liront la prochaine fois qu'un programme sera
généré/affiné, sans qu'aucun changement ne soit nécessaire là-bas.
"""
from logic.db import db
from logic.models import Exercise, ExerciseFeedback
from logic.recommendation.history import record_exercise_usage

# Boutons de l'interface (consigne : "J'ai réalisé / Trop facile / Trop
# difficile / Douleur") -> feedback_type déjà défini par `ExerciseFeedback.
# FEEDBACK_TYPES` (phase 10, inchangé). Le libellé utilisateur "Douleur"
# correspond à la valeur interne "douleur_gene" DÉJÀ utilisée partout dans le
# moteur (filters.py, feedback.py) — pas une nouvelle valeur inventée ici.
ACTION_REALISE = "realise"
ACTIONS_FEEDBACK = {
    "trop_facile": "trop_facile",
    "trop_difficile": "trop_difficile",
    "douleur": "douleur_gene",
}
ACTIONS_VALIDES = {ACTION_REALISE, *ACTIONS_FEEDBACK.keys()}


def record_exercise_action(user_id, exercise_id, action, program_id=None, comment=None):
    """record_exercise_action(user_id, exercise_id, action, program_id=None,
    comment=None) -> l'objet créé (`ExerciseUsageLog` ou `ExerciseFeedback`).

    `action` doit être "realise" (-> `ExerciseUsageLog` via `history.record_
    exercise_usage`, phase 10, inchangé) ou une clé de `ACTIONS_FEEDBACK`
    ("trop_facile"/"trop_difficile"/"douleur") -> `ExerciseFeedback`. Lève
    `ValueError` sur une action inconnue ou un `exercise_id` inexistant au
    catalogue — jamais une écriture silencieuse de données incohérentes
    (même garantie que le reste du projet)."""
    if action not in ACTIONS_VALIDES:
        raise ValueError(f"action inconnue : {action!r}")

    if Exercise.query.get(exercise_id) is None:
        raise ValueError(f"exercice inconnu : {exercise_id!r}")

    if action == ACTION_REALISE:
        return record_exercise_usage(user_id, exercise_id, program_id=program_id)

    feedback = ExerciseFeedback(
        user_id=user_id,
        exercise_id=exercise_id,
        feedback_type=ACTIONS_FEEDBACK[action],
        comment=comment,
    )
    db.session.add(feedback)
    db.session.commit()
    return feedback
