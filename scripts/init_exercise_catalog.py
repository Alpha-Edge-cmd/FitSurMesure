#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'administration (phase 17/24) : initialise proprement le catalogue
`Exercise` V2 à partir de `data/exercise_enrichment.json`.

Ne redéfinit AUCUNE règle : appelle uniquement `logic.exercise_catalog_
import.import_enriched_catalog(auto_approve=False)` (phases 13/15, inchangé)
— toujours `auto_approve=False` ici, jamais d'approbation automatique par un
script (réservé au workflow de revue humaine, `logic/exercise_review.py`,
phase 14). Un réimport ne perd jamais une décision de revue déjà prise
(`review_status`/`needs_review`/`validated_at`/`validated_by`/`review_notes`
ne sont jamais réécrits sur une ligne déjà existante, cf. `import_enriched_
catalog`) : ce script peut donc être relancé sans risque à tout moment,
avant ou après une revue humaine.

Usage :
    python scripts/init_exercise_catalog.py
    python scripts/init_exercise_catalog.py --dry-run
"""
import argparse
import os
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SITE_ROOT not in sys.path:
    sys.path.insert(0, SITE_ROOT)

import app as appmod  # noqa: E402
from logic.exercise_catalog_import import import_enriched_catalog  # noqa: E402
from logic.exercise_catalog_service import get_catalog_status  # noqa: E402
from logic.exercise_catalog_validator import _charger_fiches, validate_catalog  # noqa: E402
from logic.models import Exercise  # noqa: E402


def count_existing_exercises():
    """Vérifie si des exercices existent déjà en base — purement informatif :
    `import_enriched_catalog` gère de toute façon très bien ce cas (mise à
    jour, jamais de doublon), cf. docstring du module."""
    return Exercise.query.count()


def simulate_import(source=None):
    """Mode --dry-run : ne modifie AUCUNE donnée. Relit et valide le JSON
    exactement comme le ferait un vrai import (`validate_catalog`, phase 13,
    inchangé), puis détermine par simple LECTURE (`Exercise.query.get`,
    aucune écriture) combien de lignes seraient créées vs. mises à jour."""
    fiches = _charger_fiches(source)
    rapport = validate_catalog(fiches)
    ids_valides = set(rapport["exercise_ids_valides"])

    seraient_crees = 0
    seraient_mis_a_jour = 0
    for fiche in fiches:
        if fiche.get("exercise_id") not in ids_valides:
            continue
        existe_deja = Exercise.query.get(fiche["exercise_id"]) is not None
        if existe_deja:
            seraient_mis_a_jour += 1
        else:
            seraient_crees += 1

    return {
        "total_fiches": len(fiches),
        "valides": len(ids_valides),
        "invalides": len(fiches) - len(ids_valides),
        "seraient_crees": seraient_crees,
        "seraient_mis_a_jour": seraient_mis_a_jour,
        "erreurs": rapport["erreurs"],
    }


def _afficher_simulation(simulation):
    print("--dry-run : AUCUNE donnée modifiée.")
    print(f"  Fiches lues dans le JSON     : {simulation['total_fiches']}")
    print(f"  Fiches valides (importables) : {simulation['valides']}")
    print(f"  Fiches invalides (ignorées)  : {simulation['invalides']}")
    print(f"  Seraient créées              : {simulation['seraient_crees']}")
    print(f"  Seraient mises à jour        : {simulation['seraient_mis_a_jour']}")
    if simulation["erreurs"]:
        print(f"  Erreurs de validation ({len(simulation['erreurs'])}) :")
        for erreur in simulation["erreurs"][:10]:
            print(f"    - {erreur['exercise_id']} : {erreur['message']}")


def _afficher_rapport_final(rapport_final, erreurs):
    print("Import terminé.")
    for cle, valeur in rapport_final.items():
        print(f"  {cle} : {valeur}")
    if erreurs:
        print(f"\n{len(erreurs)} erreur(s) de validation (fiches ignorées, jamais importées) :")
        for erreur in erreurs[:10]:
            print(f"  - {erreur['exercise_id']} : {erreur['message']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Ne modifie aucune donnée, affiche uniquement les changements prévus.",
    )
    args = parser.parse_args(argv)

    with appmod.app.app_context():
        nb_avant = count_existing_exercises()
        print(f"Exercices déjà présents en base avant import : {nb_avant}\n")

        if args.dry_run:
            simulation = simulate_import()
            _afficher_simulation(simulation)
            return simulation

        resultat = import_enriched_catalog(auto_approve=False)
        statut = get_catalog_status()
        rapport_final = {
            "total": statut["total"],
            "created": resultat["created"],
            "updated": resultat["updated"],
            "pending": statut["pending"],
            "approved": statut["approved"],
            "rejected": statut["rejected"],
        }
        _afficher_rapport_final(rapport_final, resultat["errors"])
        return rapport_final


if __name__ == "__main__":
    main()
