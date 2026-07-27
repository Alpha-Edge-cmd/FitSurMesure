# -*- coding: utf-8 -*-
"""
Couche unique d'accès au catalogue Exercise V2 (phase 15/16). Tout code qui a
besoin de savoir "quels exercices le moteur a le droit d'utiliser" doit
passer par ce module plutôt que d'écrire directement une requête `Exercise.
query...` — un seul endroit qui connaît la règle de visibilité (actif +
review_status), pas une requête dupliquée à chaque appelant.

Règle de visibilité (consigne section 1) :
  - jamais un exercice `review_status="rejected"`, même actif=True, même en
    demandant explicitement les "pending" (`include_pending=True` n'élargit
    qu'aux exercices encore en attente, jamais aux rejetés) ;
  - par défaut (`include_pending=False`) : uniquement actif=True ET
    review_status="approved" — c'est la garantie centrale de cette phase,
    "aucun exercice non validé utilisé par défaut" ;
  - `include_pending=True` : actif=True ET review_status in
    (approved, pending) — usage réservé à des vues d'administration/debug,
    jamais utilisé par défaut par le moteur (cf. catalog_provider.py).

Ne modifie aucune donnée, ne supprime jamais rien : pure lecture.
"""
from logic.models import Exercise

REVIEW_STATUSES_VISIBLES_PAR_DEFAUT = ("approved",)
REVIEW_STATUSES_VISIBLES_AVEC_PENDING = ("approved", "pending")


def get_active_exercises(include_pending=False):
    """get_active_exercises(include_pending=False) -> liste d'`Exercise`.

    Toujours restreint à `actif=True`. Sans argument : uniquement les
    exercices validés par un humain (`review_status="approved"`). Avec
    `include_pending=True` : ajoute les exercices encore en attente de revue
    (`"pending"`) — jamais les rejetés, quelle que soit la valeur de cet
    argument."""
    statuses = REVIEW_STATUSES_VISIBLES_AVEC_PENDING if include_pending else REVIEW_STATUSES_VISIBLES_PAR_DEFAUT
    return (
        Exercise.query.filter(Exercise.actif.is_(True), Exercise.review_status.in_(statuses))
        .order_by(Exercise.exercise_id)
        .all()
    )


def get_exercise_by_id(exercise_id):
    """get_exercise_by_id(exercise_id) -> `Exercise` ou None. Ne filtre pas
    sur actif/review_status (contrairement à get_active_exercises) : sert à
    consulter n'importe quel exercice du catalogue, y compris pour le
    workflow de revue (logic/exercise_review.py) qui doit pouvoir agir sur un
    exercice pending/rejected aussi bien qu'approved."""
    return Exercise.query.get(exercise_id)


def get_catalog_status():
    """get_catalog_status() -> {"total", "approved", "pending", "rejected",
    "needs_review"}. `needs_review` est compté indépendamment de
    `review_status` (cf. logic/exercise_review.py : un exercice rejeté reste
    `needs_review=True` tant qu'il n'a pas été corrigé puis re-décidé, donc
    ce compteur peut différer de "pending")."""
    return {
        "total": Exercise.query.count(),
        "approved": Exercise.query.filter_by(review_status="approved").count(),
        "pending": Exercise.query.filter_by(review_status="pending").count(),
        "rejected": Exercise.query.filter_by(review_status="rejected").count(),
        "needs_review": Exercise.query.filter_by(needs_review=True).count(),
    }
