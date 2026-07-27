# -*- coding: utf-8 -*-
"""
Tests du catalogue enrichi (phase 13/16) —
logic/exercise_catalog_enrichment.py, exercise_catalog_validator.py,
exercise_catalog_import.py.

Prompt final (hors 24 phases) : data/exercise_enrichment.json contient
désormais le nouveau catalogue professionnel (486 exercices, cf.
scripts/build_professional_catalog.py), remplaçant l'ancien catalogue de 111
exercices — les comptes attendus ci-dessous sont mis à jour en conséquence
(486, pas 111). `iter_enriched_exercises()` (utilisé aux tests 2/3, sans
rapport avec ce fichier JSON) continue de reconstruire l'ANCIEN catalogue
legacy à la volée depuis logic/exercises_db.py, inchangé — toujours valide
pour tester la validation de fiches isolées."""
import copy

import app as appmod
from logic.exercise_catalog_enrichment import iter_enriched_exercises
from logic.exercise_catalog_import import import_enriched_catalog
from logic.exercise_catalog_validator import DEFAULT_ENRICHMENT_PATH, validate_catalog
from logic.models import Exercise
from logic.recommendation.program_builder import build_program


def run():
    with appmod.app.app_context():

        # --------------------------------------------------------------
        # 1) Catalogue complet : tous les exercices passent la validation
        # --------------------------------------------------------------
        rapport1 = validate_catalog(DEFAULT_ENRICHMENT_PATH)
        assert rapport1["erreurs"] == [], f"aucune erreur bloquante attendue, obtenu {rapport1['erreurs']}"
        assert len(rapport1["exercise_ids_valides"]) == 486, (
            f"486 exercices attendus (nouveau catalogue professionnel), obtenu {len(rapport1['exercise_ids_valides'])}"
        )
        assert len(rapport1["a_revoir"]) == len(rapport1["exercise_ids_valides"]), (
            "toutes les fiches de ce premier jet doivent être marquées needs_review"
        )
        print(f"OK 1 — catalogue complet : {len(rapport1['exercise_ids_valides'])} exercices valides, 0 erreur")

        # --------------------------------------------------------------
        # 2) Exercice avec joint_stress invalide : rejeté
        # --------------------------------------------------------------
        fiches = list(iter_enriched_exercises())
        fiche_ok = copy.deepcopy(fiches[0])
        fiche_joint_stress_invalide = copy.deepcopy(fiches[0])
        fiche_joint_stress_invalide["exercise_id"] = "test_joint_stress_invalide"
        fiche_joint_stress_invalide["joint_stress"] = {"epaule": 5}  # hors plage [0, 3]

        rapport2 = validate_catalog([fiche_ok, fiche_joint_stress_invalide])
        assert fiche_ok["exercise_id"] in rapport2["exercise_ids_valides"]
        assert "test_joint_stress_invalide" not in rapport2["exercise_ids_valides"]
        messages2 = [e["message"] for e in rapport2["erreurs"] if e["exercise_id"] == "test_joint_stress_invalide"]
        assert any("joint_stress" in m for m in messages2), messages2
        print("OK 2 — joint_stress invalide (5, hors [0,3]) : exercice rejeté")

        # --------------------------------------------------------------
        # 3) Exercice avec objectif manquant : rejeté
        # --------------------------------------------------------------
        fiche_objectif_manquant = copy.deepcopy(fiches[1])
        fiche_objectif_manquant["exercise_id"] = "test_objectif_manquant"
        del fiche_objectif_manquant["objectifs_adaptes"]

        rapport3 = validate_catalog([fiche_objectif_manquant])
        assert "test_objectif_manquant" not in rapport3["exercise_ids_valides"]
        messages3 = [e["message"] for e in rapport3["erreurs"] if e["exercise_id"] == "test_objectif_manquant"]
        assert any("objectifs_adaptes" in m for m in messages3), messages3
        print("OK 3 — champ 'objectifs_adaptes' manquant : exercice rejeté")

        # --------------------------------------------------------------
        # 4) Import : crée correctement les Exercise en base
        # --------------------------------------------------------------
        resultat4 = import_enriched_catalog()
        assert resultat4["errors"] == []
        assert resultat4["created"] == 486, resultat4
        assert resultat4["updated"] == 0

        exemple = Exercise.query.filter_by(muscle_principal="pecs").first()
        assert exemple is not None
        assert exemple.muscle_principal == "pecs"
        assert exemple.actif is True
        assert Exercise.query.count() == 486
        print(f"OK 4 — import initial : {resultat4['created']} exercices créés en base")

        # --------------------------------------------------------------
        # 5) Réimport : mise à jour sans doublon
        # --------------------------------------------------------------
        resultat5 = import_enriched_catalog()
        assert resultat5["created"] == 0, "aucune création attendue au réimport"
        assert resultat5["updated"] == 486, resultat5
        assert Exercise.query.count() == 486, "aucun doublon attendu après réimport"
        print(f"OK 5 — réimport : {resultat5['updated']} exercices mis à jour, toujours {Exercise.query.count()} en base")

        # --------------------------------------------------------------
        # 6) Programme généré avec le catalogue enrichi : aucun crash
        # --------------------------------------------------------------
        from logic.profile_normalizer import normalize_questionnaire_data

        raw = {
            "poids": 78, "taille": 180, "sexe": "Homme",
            "niveau_musculation": "Intermédiaire", "objectif_principal": "Prise de muscle",
            "frequence_entrainement": 3, "duree_seance": "1h - 1h30", "equipement": "Salle complète",
        }
        cleaned = normalize_questionnaire_data(raw)

        class _Profil:
            pass

        profil = _Profil()
        for k, v in cleaned.items():
            setattr(profil, k, v)

        catalogue = Exercise.query.filter_by(actif=True).all()
        resultat6 = build_program(profil, catalogue)
        assert resultat6["sessions"], "au moins une séance attendue avec le catalogue enrichi"
        assert any(s["exercises"] for s in resultat6["sessions"]), "au moins un exercice attendu"
        print(f"OK 6 — build_program avec catalogue enrichi ({len(catalogue)} exercices) : aucun crash, "
              f"{sum(len(s['exercises']) for s in resultat6['sessions'])} exercices programmés")

    print("\nTOUS LES TESTS DU CATALOGUE ENRICHI SONT PASSÉS")


if __name__ == "__main__":
    run()
