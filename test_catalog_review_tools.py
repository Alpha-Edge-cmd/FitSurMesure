# -*- coding: utf-8 -*-
"""
Tests des outils d'aide à la revue du catalogue (phase 18/24) —
logic/exercise_review_assistant.py, scripts/export_review_sheet.py,
scripts/import_review_decisions.py.

Prompt final (hors 24 phases) : catalogue professionnel (486 exercices) —
exercise_id et comptes mis à jour en conséquence."""
import csv
import os
import tempfile

import app as appmod
from logic.exercise_catalog_import import import_enriched_catalog
from logic.exercise_review_assistant import (
    detect_conflicting_metadata,
    generate_review_summary,
    suggest_review_decision,
)
from logic.models import Exercise
from scripts.export_review_sheet import COLONNES, build_review_rows, write_review_sheet
from scripts.import_review_decisions import import_review_decisions


def run():
    with appmod.app.app_context():
        resultat_import = import_enriched_catalog()
        assert resultat_import["errors"] == []
        assert Exercise.query.count() == 486

        # --------------------------------------------------------------
        # 0) Assistant de revue : sanity check sur un exercice connu
        # --------------------------------------------------------------
        exemple = Exercise.query.get("developpe_couche_barre_pecs")
        conflits = detect_conflicting_metadata(exemple)
        assert set(conflits.keys()) == {"muscle_pattern", "equipement", "difficulte", "objectifs", "scores_hypertrophiques"}
        assert all(isinstance(v, list) for v in conflits.values())

        suggestion = suggest_review_decision(exemple)
        assert suggestion["decision"] in ("approve", "reject", "needs_changes")

        resume = generate_review_summary(exemple)
        assert resume["identite"]["exercise_id"] == "developpe_couche_barre_pecs"
        assert isinstance(resume["resume_texte"], str) and resume["resume_texte"]

        # Fiche fabriquée pour vérifier une incohérence muscle/pattern ET
        # difficulté ET objectifs, détectées sans planter.
        fiche_incoherente = {
            "exercise_id": "test_incoherent_phase18",
            "name": "Test incohérent",
            "family": "test", "pattern": "squat", "muscle_principal": "pecs",
            "movement_type": "rotation", "equipment": ["machine"],
            "muscles_secondaires": [], "unilateral": False,
            "difficulty_level": "debutant", "technical_complexity": 5,
            "joint_stress": {}, "stability_demand": "faible",
            "morphologie_adaptee": {}, "objectifs_adaptes": {"force": 9, "explosivite": 8, "hypertrophie": 5, "endurance_musculaire": 2, "perte_de_gras": 2},
            "score_tension_mecanique": 2, "score_contraction_max": 2, "potentiel_hypertrophique": 9,
            "substitutes": [], "contre_indications": [], "actif": True,
            "review_status": "pending", "needs_review": True,
        }
        conflits2 = detect_conflicting_metadata(fiche_incoherente)
        assert conflits2["muscle_pattern"], "muscle/pattern incohérent attendu"
        assert conflits2["difficulte"], "difficulté incohérente attendue (debutant + technical_complexity=5)"
        assert conflits2["objectifs"], "objectifs incompatibles attendus (force/explosivite élevés + isolation/machine)"
        assert conflits2["scores_hypertrophiques"], "score hypertrophique suspect attendu"
        suggestion2 = suggest_review_decision(fiche_incoherente)
        assert suggestion2["decision"] == "reject", "une incohérence muscle/pattern doit suggérer un rejet"
        print("OK 0 — exercise_review_assistant : conflits détectés correctement, suggestions cohérentes")

        # --------------------------------------------------------------
        # 1) Export complet
        # --------------------------------------------------------------
        lignes = build_review_rows()
        assert len(lignes) == 486
        for ligne in lignes:
            assert set(ligne.keys()) == set(COLONNES)
        assert all(l["statut_revue"] == "pending" for l in lignes)

        with tempfile.TemporaryDirectory() as tmpdir:
            chemin_sortie = os.path.join(tmpdir, "review_sheet.csv")
            chemin_utilise, nb_lignes = write_review_sheet(chemin_sortie)
            assert chemin_utilise == chemin_sortie
            assert nb_lignes == 486
            assert os.path.isfile(chemin_sortie)
            with open(chemin_sortie, encoding="utf-8", newline="") as f:
                lignes_csv = list(csv.DictReader(f))
            assert len(lignes_csv) == 486
            assert set(lignes_csv[0].keys()) == set(COLONNES)
        print(f"OK 1 — export complet : {nb_lignes} exercice(s), colonnes {COLONNES}")

        # --------------------------------------------------------------
        # 2) Import décision (approve + reject, via une liste de dicts)
        # --------------------------------------------------------------
        cible_approuvee = "curl_barre_droite_biceps"
        cible_rejetee = "squat_arriere_barre_back_squat_quadriceps"
        decisions = [
            {"exercise_id": cible_approuvee, "decision": "approved", "notes": "", "validated_by": "qa-phase18"},
            {"exercise_id": cible_rejetee, "decision": "rejected", "notes": "Pattern à revérifier", "validated_by": "qa-phase18"},
            {"exercise_id": "id_inexistant_xyz", "decision": "approved", "notes": "", "validated_by": "qa-phase18"},
            {"exercise_id": "curl_halteres", "decision": "peut_etre", "notes": "", "validated_by": "qa-phase18"},
        ]
        rapport2 = import_review_decisions(decisions)
        assert rapport2["applied"] == 2
        assert rapport2["skipped_unknown_exercise"] == 1
        assert rapport2["skipped_invalid_decision"] == 1
        assert rapport2["skipped_existing"] == 0

        approuve = Exercise.query.get(cible_approuvee)
        assert approuve.review_status == "approved"
        assert approuve.validated_by == "qa-phase18"
        assert approuve.needs_review is False

        rejete = Exercise.query.get(cible_rejetee)
        assert rejete.review_status == "rejected"
        assert rejete.review_notes == "Pattern à revérifier"
        assert rejete.validated_by == "qa-phase18"
        assert rejete.actif is True
        print(f"OK 2 — import décision : {rapport2['applied']} appliquée(s) ('{cible_approuvee}' approuvé, '{cible_rejetee}' rejeté)")

        # --------------------------------------------------------------
        # 3) Conservation de la validation humaine (pas d'écrasement)
        # --------------------------------------------------------------
        decisions_conflictuelles = [
            {"exercise_id": cible_approuvee, "decision": "rejected", "notes": "tentative d'écrasement", "validated_by": "quelquun-dautre"},
            {"exercise_id": cible_rejetee, "decision": "approved", "notes": "tentative d'écrasement", "validated_by": "quelquun-dautre"},
        ]
        rapport3 = import_review_decisions(decisions_conflictuelles)
        assert rapport3["applied"] == 0
        assert rapport3["skipped_existing"] == 2

        approuve_apres = Exercise.query.get(cible_approuvee)
        assert approuve_apres.review_status == "approved", "l'approbation existante ne doit jamais être écrasée"
        assert approuve_apres.validated_by == "qa-phase18", "le validated_by d'origine ne doit jamais être perdu"

        rejete_apres = Exercise.query.get(cible_rejetee)
        assert rejete_apres.review_status == "rejected", "le rejet existant ne doit jamais être écrasé"
        assert rejete_apres.review_notes == "Pattern à revérifier", "la note de rejet d'origine ne doit jamais être perdue"
        print("OK 3 — conservation de la validation humaine : aucune décision existante écrasée")

        # --------------------------------------------------------------
        # 4) Rejet conservé après réimport (catalogue JSON + décisions)
        # --------------------------------------------------------------
        resultat_reimport = import_enriched_catalog()  # réimport du catalogue JSON (phase 13/15)
        assert resultat_reimport["created"] == 0
        assert resultat_reimport["updated"] == 486
        assert Exercise.query.get(cible_rejetee).review_status == "rejected", "un réimport du catalogue JSON ne doit jamais réinitialiser un rejet"

        with tempfile.TemporaryDirectory() as tmpdir:
            chemin_decisions = os.path.join(tmpdir, "decisions.csv")
            with open(chemin_decisions, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["exercise_id", "decision", "notes", "validated_by"])
                writer.writeheader()
                writer.writerow({"exercise_id": cible_rejetee, "decision": "approved", "notes": "", "validated_by": "tentative-tardive"})

            rapport4 = import_review_decisions(chemin_decisions)
            assert rapport4["applied"] == 0
            assert rapport4["skipped_existing"] == 1

        assert Exercise.query.get(cible_rejetee).review_status == "rejected", "le rejet doit survivre à un réimport du fichier de décisions (CSV)"
        print(f"OK 4 — rejet de '{cible_rejetee}' conservé après réimport catalogue JSON + réimport décisions CSV")

    print("\nTOUS LES TESTS DES OUTILS DE REVUE DU CATALOGUE SONT PASSÉS")


if __name__ == "__main__":
    run()
