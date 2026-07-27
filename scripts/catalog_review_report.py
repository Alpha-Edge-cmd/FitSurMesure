#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rapport de revue du catalogue (phase 17/24) : liste les exercices
`review_status="pending"`, leurs champs manquants, les avertissements du
quality checker (`logic/exercise_quality.py`, phase 14, inchangé), et un
score de priorité de revue simple (plus un exercice cumule de problèmes,
plus il doit être revu en premier). Lecture seule : ne modifie jamais rien,
n'approuve/ne rejette rien (cf. `logic/exercise_review.py` pour ça).

Note : ce rapport se concentre volontairement sur `review_status="pending"`
(la file d'attente de revue "normale"), pas sur `needs_review=True`
(`logic.exercise_review.get_pending_reviews`, phase 14) qui est un concept
légèrement plus large incluant aussi les exercices déjà `rejected` mais pas
encore corrigés — cf. `logic/exercise_review.py`, docstring de
`reject_exercise`. Les deux notions coexistent délibérément : celle-ci
répond à "qu'est-ce qui attend une première décision ?", l'autre à
"qu'est-ce qui reste à traiter, y compris les rejets non résolus ?".

Usage :
    python scripts/catalog_review_report.py
"""
import os
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SITE_ROOT not in sys.path:
    sys.path.insert(0, SITE_ROOT)

import app as appmod  # noqa: E402
from logic.exercise_quality import validate_exercise_quality  # noqa: E402
from logic.models import Exercise  # noqa: E402

# Mêmes champs "critiques" que logic/catalog_monitoring.py (phase 16) — pas
# redéfinis différemment ici, seulement listés par exercice plutôt qu'agrégés
# en un simple compteur.
CHAMPS_CRITIQUES = ("movement_type", "difficulty_level", "technical_complexity", "stability_demand")


def get_pending_exercises():
    """Tous les exercices `review_status="pending"`, triés par exercise_id
    pour un ordre déterministe (avant tri par priorité)."""
    return Exercise.query.filter_by(review_status="pending").order_by(Exercise.exercise_id).all()


def missing_fields(exercise):
    """Liste des champs critiques absents (None) pour cet exercice."""
    return [champ for champ in CHAMPS_CRITIQUES if getattr(exercise, champ) is None]


def build_review_report():
    """Construit le rapport (liste de dicts), sans rien afficher ni modifier
    — séparé de `main()` pour rester testable indépendamment de la sortie
    console. Trié par priorité décroissante (les exercices qui cumulent le
    plus de problèmes en tête)."""
    lignes = []
    for exercise in get_pending_exercises():
        rapport_qualite = validate_exercise_quality(exercise)
        champs = missing_fields(exercise)
        # Score simple et documenté (pas une formule scientifique) : une
        # erreur qualité pèse deux fois plus qu'un avertissement ou qu'un
        # champ manquant, pour faire remonter en premier les cas les plus
        # sûrement problématiques.
        priorite = 2 * len(rapport_qualite["errors"]) + len(rapport_qualite["warnings"]) + len(champs)
        lignes.append({
            "exercise_id": exercise.exercise_id,
            "name": exercise.name,
            "champs_manquants": champs,
            "erreurs_qualite": rapport_qualite["errors"],
            "avertissements_qualite": rapport_qualite["warnings"],
            "priorite": priorite,
        })

    lignes.sort(key=lambda ligne: (-ligne["priorite"], ligne["exercise_id"]))
    return lignes


def main():
    with appmod.app.app_context():
        lignes = build_review_report()
        print(f"{len(lignes)} exercice(s) en attente de revue (review_status='pending').\n")
        for ligne in lignes:
            print(f"[priorité {ligne['priorite']:>2}] {ligne['exercise_id']} — {ligne['name']}")
            if ligne["champs_manquants"]:
                print(f"    champs manquants  : {ligne['champs_manquants']}")
            if ligne["erreurs_qualite"]:
                print(f"    erreurs qualité   : {ligne['erreurs_qualite']}")
            if ligne["avertissements_qualite"]:
                print(f"    avertissements    : {ligne['avertissements_qualite']}")
        return lignes


if __name__ == "__main__":
    main()
