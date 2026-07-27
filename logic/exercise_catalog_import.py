# -*- coding: utf-8 -*-
"""
Import du catalogue enrichi vers la base (phase 13/16, `auto_approve` ajouté
phase 15/16). Ne redéfinit aucune règle de scoring/filtrage/sélection : ce
module ne fait que convertir des fiches déjà validées (`exercise_catalog_
validator.py`) en lignes `Exercise` (logic/models.py, phase 2, inchangé).
"""
from logic.db import db
from logic.exercise_catalog_validator import _charger_fiches, validate_catalog
from logic.models import Exercise

# Tous les champs du modèle Exercise à l'exception de `exercise_id` (clé
# primaire, jamais réassignée) et des colonnes gérées par le modèle lui-même
# (`created_at`/`updated_at`, phase 2).
CHAMPS_MODELE = (
    "name", "family", "pattern", "movement_type", "equipment", "muscle_principal",
    "muscles_secondaires", "unilateral", "difficulty_level", "joint_stress",
    "technical_complexity", "stability_demand", "morphologie_adaptee",
    "objectifs_adaptes", "score_tension_mecanique", "score_contraction_max",
    "potentiel_hypertrophique", "substitutes", "contre_indications", "actif",
    # Portion anatomique précise (catalogue v3, prompt final hors 24 phases) —
    # champ facultatif : `fiche.get(...)` renvoie None si absent (anciennes
    # fiches v2 encore en base tant qu'un réimport ne les a pas mises à jour).
    "portion_anatomique",
)


def import_enriched_catalog(source=None, auto_approve=False):
    """import_enriched_catalog(source=None, auto_approve=False) -> {"created",
    "updated", "skipped_invalid", "errors"}.

    Comportement (consigne section 5, phase 13 ; `auto_approve` phase 15) :
      1. lecture JSON (`source` : chemin, liste déjà chargée, ou None pour
         `exercise_catalog_validator.DEFAULT_ENRICHMENT_PATH`).
      2. validation AVANT tout import (`validate_catalog`) : une fiche avec
         au moins une erreur bloquante n'est JAMAIS importée.
      3. création/mise à jour d'`Exercise` par `exercise_id` (clé primaire
         stable depuis la phase 2) : jamais de doublon, une régénération du
         même fichier met simplement à jour les lignes déjà présentes.
      4. AUCUNE suppression automatique : un exercice retiré du fichier JSON
         reste en base tel quel (cohérent avec `Exercise.actif`, "jamais de
         suppression physique, seulement désactivation", phase 2).
      5. transaction complète : un seul commit à la fin ; toute exception
         inattendue déclenche un rollback complet (aucun import partiel).

    `auto_approve` (phase 15/16, réservé à un environnement contrôlé —
    jamais le comportement par défaut) : à la CRÉATION d'un exercice, importe
    directement avec `needs_review=False`/`review_status="approved"` au lieu
    du couple `True`/`"pending"` habituel. N'a AUCUN effet sur une mise à
    jour (branche `else` ci-dessous) : que `auto_approve` soit vrai ou faux,
    un exercice déjà en base garde son `review_status`/`needs_review`/
    `validated_at`/`validated_by`/`review_notes` existants, jamais écrasés
    par un réimport — c'est la garantie centrale de cette phase ("ne jamais
    écraser une validation humaine"), qu'il s'agisse d'une approbation, d'un
    rejet, ou d'un simple statu quo "pending"."""
    fiches = _charger_fiches(source)
    rapport = validate_catalog(fiches)
    ids_valides = set(rapport["exercise_ids_valides"])
    fiches_valides = [f for f in fiches if f.get("exercise_id") in ids_valides]

    created = 0
    updated = 0

    try:
        for fiche in fiches_valides:
            exercise_id = fiche["exercise_id"]
            exercise = Exercise.query.get(exercise_id)
            if exercise is None:
                exercise = Exercise(exercise_id=exercise_id)
                db.session.add(exercise)
                created += 1
                # `needs_review`/`review_status` (phase 14/16, `auto_approve`
                # phase 15/16) ne sont initialisés qu'à la CRÉATION, jamais à
                # la mise à jour : cf. docstring ci-dessus.
                if auto_approve:
                    exercise.needs_review = False
                    exercise.review_status = "approved"
                else:
                    exercise.needs_review = fiche.get("needs_review", True)
                    exercise.review_status = "pending"
            else:
                updated += 1
                # Ne JAMAIS toucher, sur une ligne déjà existante :
                # review_status, needs_review, validated_at, validated_by,
                # review_notes — même si le JSON contient une valeur
                # différente (consigne phase 15, section 2 "Important").

            for champ in CHAMPS_MODELE:
                setattr(exercise, champ, fiche.get(champ))

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "created": created,
        "updated": updated,
        "skipped_invalid": len(fiches) - len(fiches_valides),
        "errors": rapport["erreurs"],
    }
