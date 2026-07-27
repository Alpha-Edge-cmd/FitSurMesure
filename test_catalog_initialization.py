# -*- coding: utf-8 -*-
"""
Tests des scripts d'administration du catalogue (phase 17/24) —
scripts/init_exercise_catalog.py, scripts/catalog_review_report.py.

Prompt final (hors 24 phases) : catalogue v3 (365 exercices, liste exacte
fournie par Samy, cf. scripts/build_catalog_v3_samy.py) — comptes et
exercise_id mis à jour en conséquence. Depuis le correctif "catalogue jamais
chargé en prod" (logic/db.init_db appelle désormais import_enriched_catalog
à chaque démarrage de l'app), la table Exercise n'est plus vide après un
simple `import app` : ce test vide explicitement la table au départ pour
retrouver le scénario "base vide" qu'il vérifie."""
import app as appmod
from logic.db import db
from logic.exercise_review import approve_exercise
from logic.models import Exercise
from scripts.catalog_review_report import build_review_report
from scripts.init_exercise_catalog import count_existing_exercises, main as init_main, simulate_import


def run():
    with appmod.app.app_context():
        # `import app` (logic.db.init_db) a déjà importé/auto-approuvé le
        # catalogue à cette étape (correctif "catalogue jamais chargé en
        # prod") : on repart d'une table vide pour tester le scénario
        # "première installation" que ce fichier vérifie.
        Exercise.query.delete()
        db.session.commit()

        # --------------------------------------------------------------
        # 1) Import première fois : base vide -> 365 créés, tous pending
        # --------------------------------------------------------------
        assert count_existing_exercises() == 0
        rapport1 = init_main(argv=[])
        assert rapport1["total"] == 365
        assert rapport1["created"] == 365
        assert rapport1["updated"] == 0
        assert rapport1["pending"] == 365
        assert rapport1["approved"] == 0
        assert rapport1["rejected"] == 0
        assert Exercise.query.count() == 365
        print(f"OK 1 — import première fois : {rapport1}")

        # --------------------------------------------------------------
        # 2) Réimport sans perte de validation humaine
        # --------------------------------------------------------------
        cible = "developpe_couche_a_la_barre_libre_pecs"
        approve_exercise(cible, reviewer="qa-init")
        avant_reimport = Exercise.query.get(cible)
        assert avant_reimport.review_status == "approved"

        rapport2 = init_main(argv=[])
        assert rapport2["created"] == 0
        assert rapport2["updated"] == 365
        assert rapport2["approved"] == 1, "l'approbation ne doit jamais être perdue par un réimport"

        apres_reimport = Exercise.query.get(cible)
        assert apres_reimport.review_status == "approved"
        assert apres_reimport.validated_by == "qa-init"
        print(f"OK 2 — réimport : approbation de '{cible}' conservée ({rapport2})")

        # --------------------------------------------------------------
        # 3) Dry-run : aucune modification
        # --------------------------------------------------------------
        nb_avant_dry_run = Exercise.query.count()
        statut_approved_avant = Exercise.query.filter_by(review_status="approved").count()

        simulation = init_main(argv=["--dry-run"])
        assert simulation["total_fiches"] == 365
        assert simulation["valides"] == 365
        assert simulation["invalides"] == 0
        assert simulation["seraient_crees"] == 0, "tout le catalogue existe déjà : rien ne devrait être 'créé'"
        assert simulation["seraient_mis_a_jour"] == 365

        assert Exercise.query.count() == nb_avant_dry_run, "--dry-run ne doit modifier aucune ligne"
        assert Exercise.query.filter_by(review_status="approved").count() == statut_approved_avant
        assert Exercise.query.get(cible).review_status == "approved", "--dry-run ne doit toucher aucun statut de revue"

        # Vérification directe de la fonction de simulation elle-même (pas
        # seulement via main()) — même garantie, aucune écriture.
        simulation_directe = simulate_import()
        assert simulation_directe == simulation
        assert Exercise.query.count() == nb_avant_dry_run
        print(f"OK 3 — dry-run : aucune donnée modifiée ({simulation})")

        # --------------------------------------------------------------
        # 4) Rapport de revue cohérent
        # --------------------------------------------------------------
        lignes = build_review_report()
        assert len(lignes) == Exercise.query.filter_by(review_status="pending").count() == 364
        assert cible not in {l["exercise_id"] for l in lignes}, "un exercice approuvé ne doit pas apparaître dans le rapport"

        # Trié par priorité décroissante.
        priorites = [l["priorite"] for l in lignes]
        assert priorites == sorted(priorites, reverse=True), "le rapport doit être trié par priorité décroissante"

        for ligne in lignes:
            assert set(ligne.keys()) == {
                "exercise_id", "name", "champs_manquants", "erreurs_qualite",
                "avertissements_qualite", "priorite",
            }
            assert ligne["priorite"] >= 0
            attendu = (
                2 * len(ligne["erreurs_qualite"]) + len(ligne["avertissements_qualite"]) + len(ligne["champs_manquants"])
            )
            assert ligne["priorite"] == attendu, "la priorité doit refléter exactement erreurs/avertissements/champs manquants"

        print(f"OK 4 — rapport de revue cohérent : {len(lignes)} exercice(s) pending, trié par priorité")

    print("\nTOUS LES TESTS D'INITIALISATION DU CATALOGUE SONT PASSÉS")


if __name__ == "__main__":
    run()
