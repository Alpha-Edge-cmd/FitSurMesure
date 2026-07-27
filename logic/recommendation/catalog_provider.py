# -*- coding: utf-8 -*-
"""
Fournit au moteur de recommandation LA liste d'exercices à utiliser, sans
que selector.py/scoring.py/fallback.py/workout_generator.py (tous inchangés)
aient besoin de savoir d'où elle vient — catalogue V2 validé en base, ou
repli sur le catalogue legacy (phase 15/16).

Ces modules du moteur reçoivent depuis longtemps (phases 6 à 9) une simple
liste d'objets exposant les mêmes attributs qu'`Exercise` (accès par
attribut : `exercise.muscle_principal`, `exercise.joint_stress`, etc.) — que
ces objets soient de vraies lignes SQLAlchemy ou de simples objets legacy
reconstruits à la volée leur est invisible, à condition d'exposer la même
interface. C'est tout ce que ce module garantit ; il ne modifie et
n'importe aucune règle de scoring/filtrage/sélection.
"""
from types import SimpleNamespace

from logic.exercise_catalog_service import get_active_exercises


def _legacy_catalog_as_exercises():
    """Repli de sécurité : reconstruit, à la volée et en lecture seule, une
    liste d'objets "Exercise-like" (accès par attribut) à partir du
    catalogue legacy (logic.exercises_db.EXERCISES) via `exercise_migration.
    map_legacy_exercise` (phase 2, inchangé, jamais réécrit ici). Jamais
    persisté en base : un simple objet en mémoire par appel.

    N'est utilisé QUE si `get_active_exercises()` ne retourne aucun exercice
    approuvé (catalogue V2 pas encore importé, ou entièrement en attente/
    rejeté) — garantit qu'un déploiement où aucun exercice n'a encore été
    validé humainement continue de produire des programmes, exactement comme
    avant la phase 13."""
    from logic.exercise_migration import iter_legacy_exercises

    return [SimpleNamespace(**mapped) for _muscle_key, mapped in iter_legacy_exercises()]


def get_recommendation_catalog():
    """get_recommendation_catalog() -> liste d'exercices exploitable par le
    moteur de recommandation existant (workout_generator/selector/scoring/
    fallback, aucun d'entre eux modifié par cette phase) :
      1. le catalogue V2 approuvé (exercise_catalog_service.get_active_
         exercises(), review_status="approved" uniquement — jamais pending
         ni rejected) si non vide ;
      2. sinon, repli automatique sur le catalogue legacy reconstruit à la
         volée (cf. `_legacy_catalog_as_exercises` ci-dessus)."""
    approuves = get_active_exercises(include_pending=False)
    if approuves:
        return approuves
    return _legacy_catalog_as_exercises()
