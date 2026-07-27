#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import des décisions de revue humaine (phase 18/24) : lit un fichier CSV
(colonnes exercise_id, decision, notes, validated_by) et applique chaque
décision via le workflow déjà existant (`logic/exercise_review.py`, phase
14, inchangé : `approve_exercise`/`reject_exercise`) — ce script ne fait QUE
relayer une décision déjà prise par un humain, il n'en invente ni n'en
devine aucune.

Garantie centrale (consigne phase 18) : un exercice qui a DÉJÀ une décision
(`review_status` != "pending") est TOUJOURS ignoré, quelle que soit la
décision présente dans le fichier — jamais d'écrasement d'une décision
existante (approuvée ou rejetée), jamais de perte de l'historique de
validation déjà en place (`validated_at`/`validated_by`/`review_notes`). Un
réimport du même fichier de décisions, ou d'un fichier redondant/obsolète,
est donc toujours sans danger.

Format attendu (CSV, en-tête obligatoire) :
    exercise_id,decision,notes,validated_by
    developpe_couche_barre,approved,,qa-team
    squat_barre_back_squat,rejected,"difficulty_level à revoir",qa-team

`decision` : "approved" ou "rejected" uniquement (toute autre valeur, y
compris vide ou inconnue, est ignorée — pas de supposition sur une décision
absente ou mal formée).

Usage :
    python scripts/import_review_decisions.py chemin_decisions.csv
    python scripts/import_review_decisions.py chemin_decisions.csv --dry-run
"""
import argparse
import csv
import os
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SITE_ROOT not in sys.path:
    sys.path.insert(0, SITE_ROOT)

import app as appmod  # noqa: E402
from logic.exercise_review import approve_exercise, reject_exercise  # noqa: E402
from logic.models import Exercise  # noqa: E402

DECISIONS_VALIDES = {"approved", "rejected"}


def _lire_decisions(source):
    """Lit un fichier CSV (chemin, chaîne) ou accepte directement une liste
    de dicts déjà chargée (pratique pour les tests, sans dépendre du
    disque) — même contrat que `exercise_catalog_validator._charger_fiches`."""
    if isinstance(source, str):
        with open(source, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    return list(source)


def import_review_decisions(source, dry_run=False):
    """import_review_decisions(source, dry_run=False) -> {"applied",
    "skipped_existing", "skipped_unknown_exercise", "skipped_invalid_decision",
    "details"}.

      - "applied"                    : décisions réellement appliquées
        (`approve_exercise`/`reject_exercise` appelés).
      - "skipped_existing"           : exercice déjà décidé (`review_status`
        != "pending") — JAMAIS écrasé, cf. docstring du module.
      - "skipped_unknown_exercise"   : `exercise_id` absent du catalogue.
      - "skipped_invalid_decision"   : `decision` ni "approved" ni "rejected"
        (ou absente/vide).

    `dry_run=True` : ne modifie AUCUNE donnée ; "applied" compte alors les
    décisions qui SERAIENT appliquées (mêmes règles de filtrage)."""
    decisions = _lire_decisions(source)

    applied = 0
    skipped_existing = 0
    skipped_unknown_exercise = 0
    skipped_invalid_decision = 0
    details = []

    for ligne in decisions:
        exercise_id = (ligne.get("exercise_id") or "").strip()
        decision = (ligne.get("decision") or "").strip()
        notes = ligne.get("notes") or ""
        validated_by = ligne.get("validated_by") or None

        if decision not in DECISIONS_VALIDES:
            skipped_invalid_decision += 1
            details.append({"exercise_id": exercise_id, "resultat": "decision_invalide"})
            continue

        exercise = Exercise.query.get(exercise_id)
        if exercise is None:
            skipped_unknown_exercise += 1
            details.append({"exercise_id": exercise_id, "resultat": "exercice_inconnu"})
            continue

        if exercise.review_status != "pending":
            # Ne JAMAIS écraser une décision déjà prise — garantie centrale
            # de cette phase (approbation, rejet, historique de validation).
            skipped_existing += 1
            details.append({
                "exercise_id": exercise_id, "resultat": "deja_decide",
                "review_status_actuel": exercise.review_status,
            })
            continue

        if dry_run:
            applied += 1
            details.append({"exercise_id": exercise_id, "resultat": f"serait_{decision}"})
            continue

        if decision == "approved":
            approve_exercise(exercise_id, reviewer=validated_by)
        else:
            reject_exercise(
                exercise_id,
                reason=notes or "Rejeté via import_review_decisions (aucune raison fournie dans le fichier)",
                reviewer=validated_by,
            )
        applied += 1
        details.append({"exercise_id": exercise_id, "resultat": decision})

    return {
        "applied": applied,
        "skipped_existing": skipped_existing,
        "skipped_unknown_exercise": skipped_unknown_exercise,
        "skipped_invalid_decision": skipped_invalid_decision,
        "details": details,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chemin", help="Chemin du fichier CSV de décisions.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Ne modifie aucune donnée, affiche seulement ce qui serait appliqué.",
    )
    args = parser.parse_args(argv)

    with appmod.app.app_context():
        rapport = import_review_decisions(args.chemin, dry_run=args.dry_run)
        entete = "SIMULATION (--dry-run, aucune donnée modifiée)" if args.dry_run else "Import terminé"
        print(f"{entete} :")
        print(f"  décisions appliquées        : {rapport['applied']}")
        print(f"  déjà décidés (ignorés)      : {rapport['skipped_existing']}")
        print(f"  exercice inconnu (ignorés)  : {rapport['skipped_unknown_exercise']}")
        print(f"  décision invalide (ignorés) : {rapport['skipped_invalid_decision']}")
        return rapport


if __name__ == "__main__":
    main()
