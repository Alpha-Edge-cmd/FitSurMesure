#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export d'une feuille de revue exploitable (phase 18/24) : un fichier CSV,
une ligne par exercice du catalogue, colonnes exercise_id/nom/famille/
pattern/muscles/difficulté/scores/warnings qualité/statut revue — pensé pour
être ouvert dans un tableur par un humain qui doit décider approve/reject
(cf. `logic/exercise_review.py`, phase 14, et `scripts/import_review_
decisions.py`, phase 18, pour appliquer ensuite les décisions prises).

Lecture seule : ne modifie jamais aucune donnée, n'appelle jamais
`approve_exercise`/`reject_exercise`/`update_exercise_review`.

Usage :
    python scripts/export_review_sheet.py
    python scripts/export_review_sheet.py chemin_de_sortie.csv
"""
import csv
import os
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SITE_ROOT not in sys.path:
    sys.path.insert(0, SITE_ROOT)

import app as appmod  # noqa: E402
from logic.exercise_quality import validate_exercise_quality  # noqa: E402
from logic.models import Exercise  # noqa: E402

DEFAULT_OUTPUT_PATH = os.path.join(SITE_ROOT, "data", "review_sheet.csv")

COLONNES = (
    "exercise_id", "nom", "famille", "pattern", "muscles",
    "difficulte", "scores", "warnings_qualite", "statut_revue",
)


def _muscles(exercise):
    muscles = [exercise.muscle_principal] if exercise.muscle_principal else []
    muscles.extend(exercise.muscles_secondaires or [])
    return ", ".join(muscles)


def _scores(exercise):
    return (
        f"tension={exercise.score_tension_mecanique}, "
        f"contraction={exercise.score_contraction_max}, "
        f"potentiel={exercise.potentiel_hypertrophique}"
    )


def build_review_rows():
    """Construit les lignes de la feuille de revue (liste de dicts), sans
    rien écrire sur disque — séparé de `write_review_sheet` pour rester
    testable indépendamment du système de fichiers."""
    lignes = []
    for exercise in Exercise.query.order_by(Exercise.exercise_id).all():
        rapport_qualite = validate_exercise_quality(exercise)
        warnings_qualite = rapport_qualite["errors"] + rapport_qualite["warnings"]
        lignes.append({
            "exercise_id": exercise.exercise_id,
            "nom": exercise.name,
            "famille": exercise.family,
            "pattern": exercise.pattern,
            "muscles": _muscles(exercise),
            "difficulte": exercise.difficulty_level,
            "scores": _scores(exercise),
            "warnings_qualite": " | ".join(warnings_qualite),
            "statut_revue": exercise.review_status,
        })
    return lignes


def write_review_sheet(output_path=None):
    """Écrit le CSV. Retourne (chemin_utilise, nombre_de_lignes)."""
    output_path = output_path or DEFAULT_OUTPUT_PATH
    lignes = build_review_rows()

    dossier = os.path.dirname(output_path)
    if dossier:
        os.makedirs(dossier, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES)
        writer.writeheader()
        for ligne in lignes:
            writer.writerow(ligne)

    return output_path, len(lignes)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    output_path = argv[0] if argv else None

    with appmod.app.app_context():
        chemin, nb_lignes = write_review_sheet(output_path)
        print(f"Feuille de revue exportée : {chemin} ({nb_lignes} exercice(s))")
        return {"path": chemin, "count": nb_lignes}


if __name__ == "__main__":
    main()
