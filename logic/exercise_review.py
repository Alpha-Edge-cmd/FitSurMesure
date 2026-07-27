# -*- coding: utf-8 -*-
"""
Workflow de revue humaine du catalogue enrichi (phase 14/16). Opère
directement sur les lignes `Exercise` déjà importées en base (logic/
exercise_catalog_import.py, phase 13) — ne touche jamais au fichier éditorial
data/exercise_enrichment.json, ne modifie ni ne redéfinit aucune règle de
scoring/filtrage/sélection (scoring.py, filters.py, selector.py, fallback.py,
workout_generator.py, prescription.py — tous inchangés). Ne supprime jamais un
exercice (aucune suppression physique, aucune désactivation automatique) :
`approve_exercise`/`reject_exercise` gardent toujours l'exercice dans le
catalogue, ils ne font que documenter une décision de revue.

Réconciliation de nommage assumée : la consigne de la phase 14 décrit le
comportement de `reject_exercise` avec un champ "review_reason", mais la
liste des colonnes à ajouter au modèle ne mentionne que "review_notes". Un
seul champ texte (`Exercise.review_notes`) porte les deux usages (note de
revue libre ET raison de rejet) plutôt que d'ajouter une colonne dupliquée.

Décision documentée sur `needs_review` : la consigne dit explicitement que
`approve_exercise` "passe needs_review=false", mais ne dit RIEN de `needs_
review` pour `reject_exercise`. On ne le modifie donc PAS dans ce cas (aucune
supposition non demandée) : un exercice rejeté reste dans la file de revue
(`get_pending_reviews`) jusqu'à correction (`update_exercise_review`) puis
approbation explicite — un rejet documente un problème, il ne le referme pas.
"""
from datetime import datetime

from logic.db import db
from logic.exercise_catalog_validator import CHAMPS_OBLIGATOIRES, validate_exercise
from logic.models import Exercise

REVIEW_STATUSES = ("pending", "approved", "rejected")

# Champs qu'un correcteur humain peut modifier via `update_exercise_review`
# (cf. consigne section 1, liste explicite). Toute autre clé est refusée.
CHAMPS_CORRIGEABLES = (
    "movement_type",
    "difficulty_level",
    "technical_complexity",
    "stability_demand",
    "joint_stress",
    "objectifs_adaptes",
    "score_tension_mecanique",
    "score_contraction_max",
    "potentiel_hypertrophique",
    "morphologie_adaptee",
)


class ExerciseReviewError(ValueError):
    """Levée quand un exercice est introuvable ou qu'une correction proposée
    échoue la validation — dans les deux cas, aucune écriture n'a lieu."""


def _get_or_raise(exercise_id):
    exercise = Exercise.query.get(exercise_id)
    if exercise is None:
        raise ExerciseReviewError(f"exercice introuvable : {exercise_id!r}")
    return exercise


def get_pending_reviews():
    """get_pending_reviews() -> liste des `Exercise` avec needs_review=true.
    Ordonnée par exercise_id pour un résultat déterministe (utile pour une
    future interface de revue paginée)."""
    return Exercise.query.filter_by(needs_review=True).order_by(Exercise.exercise_id).all()


def approve_exercise(exercise_id, reviewer=None):
    """approve_exercise(exercise_id, reviewer=None) : needs_review=false,
    review_status="approved", validated_at=maintenant, validated_by=reviewer
    si fourni. Ne touche à AUCUN champ de contenu (cf. update_exercise_review
    pour les corrections de champs) : approuver, c'est valider les données
    déjà en place, pas les changer."""
    exercise = _get_or_raise(exercise_id)
    exercise.needs_review = False
    exercise.review_status = "approved"
    exercise.validated_at = datetime.utcnow()
    if reviewer is not None:
        exercise.validated_by = reviewer
    db.session.commit()
    return exercise


def reject_exercise(exercise_id, reason, reviewer=None):
    """reject_exercise(exercise_id, reason, reviewer=None) : garde l'exercice
    dans le catalogue (aucune désactivation, aucune suppression), documente
    review_status="rejected" + la raison dans review_notes, et validated_at/
    validated_by si un reviewer est fourni. `needs_review` n'est PAS modifié
    (cf. docstring du module) : l'exercice reste dans get_pending_reviews()
    jusqu'à correction + nouvelle décision."""
    if not reason:
        raise ExerciseReviewError("reject_exercise nécessite une raison (reason) non vide")
    exercise = _get_or_raise(exercise_id)
    exercise.review_status = "rejected"
    exercise.review_notes = reason
    exercise.validated_at = datetime.utcnow()
    if reviewer is not None:
        exercise.validated_by = reviewer
    db.session.commit()
    return exercise


def _fiche_from_exercise(exercise):
    """Reconstruit un dict "fiche" (mêmes clés que exercise_catalog_
    validator.CHAMPS_OBLIGATOIRES) à partir d'une ligne Exercise déjà en
    base, pour pouvoir réutiliser validate_exercise() sans dupliquer ses
    règles de cohérence."""
    return {champ: getattr(exercise, champ) for champ in CHAMPS_OBLIGATOIRES}


def update_exercise_review(exercise_id, fields):
    """update_exercise_review(exercise_id, fields) : corrige manuellement un
    sous-ensemble de champs (cf. CHAMPS_CORRIGEABLES). "Aucune modification
    directe sans validation des champs" (consigne section 1) : la fiche
    résultante (valeurs actuelles + `fields`) est validée par
    exercise_catalog_validator.validate_exercise AVANT toute écriture ; si la
    validation échoue, AUCUN champ n'est modifié (tout ou rien) et une
    ExerciseReviewError est levée avec le détail des erreurs.

    Ne modifie jamais needs_review/review_status/validated_at/validated_by :
    corriger un champ n'est pas une décision de revue, cf. approve_exercise/
    reject_exercise pour ça — une correction doit toujours être suivie d'une
    décision explicite du reviewer."""
    champs_inconnus = set(fields) - set(CHAMPS_CORRIGEABLES)
    if champs_inconnus:
        raise ExerciseReviewError(
            f"champ(s) non corrigeable(s) via update_exercise_review : {sorted(champs_inconnus)}"
        )

    exercise = _get_or_raise(exercise_id)
    fiche_proposee = _fiche_from_exercise(exercise)
    fiche_proposee.update(fields)

    erreurs, _avertissements = validate_exercise(fiche_proposee)
    if erreurs:
        raise ExerciseReviewError(
            f"correction refusée pour {exercise_id!r} — champs invalides : {erreurs}"
        )

    for champ, valeur in fields.items():
        setattr(exercise, champ, valeur)
    db.session.commit()
    return exercise
