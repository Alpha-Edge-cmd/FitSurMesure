# -*- coding: utf-8 -*-
"""
Lecture de l'historique d'utilisation et du feedback utilisateur (phase
10/16), branchée sur les tables `ExerciseUsageLog`/`ExerciseFeedback`
créées dans cette même phase (`logic/models.py`). Ne contient aucune règle
de scoring/filtrage : ce module lit et agrège des données, la traduction en
signaux moteur (exclusions, pénalités, bonus) est faite par
`logic/recommendation/feedback.py`, jamais ici.
"""
from datetime import datetime, timedelta

from logic.models import ExerciseFeedback, ExerciseUsageLog

WEEKS_DEFAUT = 8


def get_recent_exercises(user_id, weeks=WEEKS_DEFAUT):
    """Exercices utilisés par `user_id` au cours des `weeks` dernières
    semaines. Retourne une liste de dicts {"exercise_id", "occurrences",
    "last_used_at"}, triée par date d'utilisation la plus récente d'abord.
    Retourne toujours [] si `user_id` est None ou si aucun usage n'existe —
    jamais d'exception (même principe que les anciens stubs de selector.py,
    phase 7)."""
    if user_id is None:
        return []

    seuil = datetime.utcnow() - timedelta(weeks=weeks)
    logs = (
        ExerciseUsageLog.query
        .filter(ExerciseUsageLog.user_id == user_id, ExerciseUsageLog.used_at >= seuil)
        .all()
    )

    agrege = {}
    for log in logs:
        entree = agrege.setdefault(
            log.exercise_id, {"exercise_id": log.exercise_id, "occurrences": 0, "last_used_at": None}
        )
        entree["occurrences"] += 1
        if entree["last_used_at"] is None or log.used_at > entree["last_used_at"]:
            entree["last_used_at"] = log.used_at

    return sorted(agrege.values(), key=lambda e: e["last_used_at"], reverse=True)


def get_exercise_feedback(user_id):
    """Tous les feedbacks de `user_id`, les plus récents d'abord. Retourne
    une liste de dicts {"exercise_id", "feedback_type", "comment",
    "created_at"} — exploitable directement par `feedback.py`, jamais
    d'objets ORM exposés hors de ce module (limite l'accouplement)."""
    if user_id is None:
        return []

    feedbacks = (
        ExerciseFeedback.query
        .filter_by(user_id=user_id)
        .order_by(ExerciseFeedback.created_at.desc())
        .all()
    )
    return [
        {
            "exercise_id": fb.exercise_id,
            "feedback_type": fb.feedback_type,
            "comment": fb.comment,
            "created_at": fb.created_at,
        }
        for fb in feedbacks
    ]


def record_exercise_usage(user_id, exercise_id, program_id=None, used_at=None):
    """Écrit une ligne d'historique. Non demandée explicitement par la
    consigne (qui ne liste que les 2 fonctions de lecture ci-dessus), mais
    nécessaire en pratique pour qu'il existe un historique à lire — utilisée
    par les tests de cette phase pour simuler un usage passé. Le branchement
    réel (écrire une ligne à chaque génération de séance) revient à un futur
    appel applicatif (route/app.py), volontairement hors périmètre ici (cf.
    consigne : "ne pas toucher app.py sauf strictement nécessaire")."""
    from logic.db import db

    log = ExerciseUsageLog(
        user_id=user_id,
        exercise_id=exercise_id,
        program_id=program_id,
        used_at=used_at or datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
    return log
