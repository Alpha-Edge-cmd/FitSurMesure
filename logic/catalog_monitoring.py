# -*- coding: utf-8 -*-
"""
Monitoring catalogue (phase 16/16) : une vue d'ensemble en lecture seule pour
un contrôle rapide avant mise en production — "où en est le catalogue,
combien reste-t-il à faire, y a-t-il des signaux d'alerte ?". N'invente
aucune règle : agrège `exercise_catalog_service.py` (phase 15) et `exercise_
quality.py` (phase 14), tous deux inchangés."""
from logic.exercise_catalog_service import get_catalog_status
from logic.exercise_quality import validate_exercise_quality
from logic.models import Exercise

# Champs jugés "critiques" pour qu'un exercice soit réellement exploitable
# par le moteur (mêmes 4 champs que le contrôle "exercice actif mais
# incomplet" de exercise_quality.py, réutilisés ici à l'identique plutôt que
# redéfinis) : movement_type/difficulty_level/technical_complexity/
# stability_demand.
CHAMPS_CRITIQUES = ("movement_type", "difficulty_level", "technical_complexity", "stability_demand")


def catalog_health_report():
    """catalog_health_report() -> {"total", "approved", "pending", "rejected",
    "active_without_review", "missing_fields", "quality_warnings"}.

      - "total"/"approved"/"pending"/"rejected" : cf. exercise_catalog_
        service.get_catalog_status() (aucune règle dupliquée ici).
      - "active_without_review" : exercices `actif=True` ET `needs_review=
        True` — potentiellement déjà exposés (si un jour approuvés) sans
        qu'une revue humaine n'ait jamais eu lieu.
      - "missing_fields" : nombre d'exercices auxquels il manque AU MOINS UN
        des champs critiques ci-dessus (pas nécessairement les 4 à la fois,
        contrairement au contrôle bloquant de exercise_quality.py — ce
        rapport est un signal d'alerte agrégé, pas une porte de validation).
      - "quality_warnings" : somme des avertissements de `exercise_quality.
        validate_exercise_quality()` sur l'ensemble du catalogue."""
    statut = get_catalog_status()

    active_without_review = Exercise.query.filter_by(actif=True, needs_review=True).count()

    missing_fields = 0
    quality_warnings = 0
    for exercise in Exercise.query.all():
        rapport_qualite = validate_exercise_quality(exercise)
        quality_warnings += len(rapport_qualite["warnings"])
        if any(getattr(exercise, champ) is None for champ in CHAMPS_CRITIQUES):
            missing_fields += 1

    return {
        "total": statut["total"],
        "approved": statut["approved"],
        "pending": statut["pending"],
        "rejected": statut["rejected"],
        "active_without_review": active_without_review,
        "missing_fields": missing_fields,
        "quality_warnings": quality_warnings,
    }
