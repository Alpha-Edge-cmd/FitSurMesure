# -*- coding: utf-8 -*-
"""
Tests de la personnalisation avancée du programme (phase 20/24) —
logic/program_personalization.py, et de son branchement ADDITIF dans
logic/recommendation/program_builder.py (build_program) : aucune clé
existante retirée/renommée, program_repository.py/program_validation.py
continuent de fonctionner normalement avec le résultat enrichi.
"""
import datetime

import app as appmod
from logic.db import db
from logic.models import Exercise, ProfileSnapshot, User
from logic.program_personalization import (
    adjust_frequency_for_availability,
    adjust_intensity_for_age,
    adjust_rest_for_age,
    compute_age,
    compute_personalization_context,
    equipements_preferes,
    generate_program_explanation,
    reorder_session_by_equipment_preference,
)
from logic.program_repository import create_program_from_result
from logic.program_validation import validate_generated_program
from logic.recommendation.program_builder import build_program

MUSCLES_PPL = ["pecs", "epaules", "triceps", "dos", "biceps", "quadriceps", "ischio", "fessiers", "mollets", "abdos"]


def profil(**kwargs):
    defaults = dict(
        poids=75.0, taille=178.0, sexe="Homme",
        niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle",
        objectif_secondaire=None,
        exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Aucune gêne",
        amplitude_epaule="Aucune gêne", tolerance_technique=3,
        preference_style_charge="Un mix des deux", preference_materiel="Pas de préférence",
        morphologie_declaree={}, blessures={}, autres_sports={}, sommeil="7 à 8h",
        stress="Modéré", variables_json={"duree_seance": "1h - 1h30"},
    )
    defaults.update(kwargs)
    return ProfileSnapshot(**defaults)


def exo(**kwargs):
    defaults = dict(
        exercise_id="ex_test", name="Exercice test", family="fam", pattern="pattern_test",
        movement_type="push", equipment=["barre"], muscle_principal="pecs",
        muscles_secondaires=[], unilateral=False, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": 2}, score_tension_mecanique=5,
        score_contraction_max=5, potentiel_hypertrophique=5, substitutes=[],
        contre_indications=[], actif=True,
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def catalogue_complet(prefixe="", equipement="barre"):
    catalogue = []
    for muscle in MUSCLES_PPL:
        catalogue.append(exo(exercise_id=f"{prefixe}{muscle}_a", family=f"{muscle}_fam_a",
                              muscle_principal=muscle, equipment=[equipement]))
        catalogue.append(exo(exercise_id=f"{prefixe}{muscle}_b", family=f"{muscle}_fam_b",
                              muscle_principal=muscle, equipment=[equipement]))
    return catalogue


def run():
    with appmod.app.app_context():

        # ------------------------------------------------------------------
        # 1) compute_age : dérivation depuis variables_json["date_naissance"]
        # ------------------------------------------------------------------
        aujourdhui = datetime.date(2026, 7, 27)
        p_age_56 = profil(variables_json={"date_naissance": "1970-01-01"})
        p_age_absent = profil(variables_json={})
        p_age_invalide = profil(variables_json={"date_naissance": "pas-une-date"})

        assert compute_age(p_age_56, aujourdhui=aujourdhui) == 56
        assert compute_age(p_age_absent, aujourdhui=aujourdhui) is None
        assert compute_age(p_age_invalide, aujourdhui=aujourdhui) is None
        print("OK 1 — compute_age : dérivation correcte depuis variables_json, jamais d'exception")

        # ------------------------------------------------------------------
        # 2) adjust_frequency_for_availability : plafond selon disponibilité
        # ------------------------------------------------------------------
        p_dispo_faible = profil(disponibilite_reelle="Moins de 2h")
        p_dispo_large = profil(disponibilite_reelle="Plus de 6h")
        p_dispo_absente = profil(disponibilite_reelle=None)
        p_dispo_libre = profil(disponibilite_reelle="Comme prévu")  # texte libre non standard

        freq, warn = adjust_frequency_for_availability(p_dispo_faible, 5)
        assert freq == 2 and warn is not None and "ramenée" in warn
        freq, warn = adjust_frequency_for_availability(p_dispo_large, 6)
        assert freq == 6 and warn is None
        freq, warn = adjust_frequency_for_availability(p_dispo_absente, 4)
        assert freq == 4 and warn is None
        freq, warn = adjust_frequency_for_availability(p_dispo_libre, 10)
        assert freq == 10 and warn is None, "texte libre non reconnu -> aucune supposition"
        print("OK 2 — adjust_frequency_for_availability : plafond correct, jamais de supposition sur texte libre")

        # ------------------------------------------------------------------
        # 3) reorder_session_by_equipment_preference : départage intra-palier
        #    uniquement, jamais de franchissement de palier
        # ------------------------------------------------------------------
        ex_principal_machine = exo(exercise_id="p_machine", movement_type="push", muscle_principal="pecs",
                                    unilateral=False, equipment=["machine"])
        ex_principal_barre = exo(exercise_id="p_barre", movement_type="push", muscle_principal="pecs",
                                  unilateral=False, equipment=["barre"])
        ex_isolation_haltere = exo(exercise_id="i_haltere", movement_type=None, muscle_principal="pecs",
                                    equipment=["haltere"])
        items = [
            {"exercise": ex_principal_machine, "w_ex": {"exercise_id": "p_machine"}},
            {"exercise": ex_principal_barre, "w_ex": {"exercise_id": "p_barre"}},
            {"exercise": ex_isolation_haltere, "w_ex": {"exercise_id": "i_haltere"}},
        ]
        reordonne = reorder_session_by_equipment_preference(items, {"barre"})
        ids_ordonnes = [it["w_ex"]["exercise_id"] for it in reordonne]
        assert ids_ordonnes == ["p_barre", "p_machine", "i_haltere"], (
            f"le mouvement barre doit passer en tête de son palier, l'isolation reste en dernier : {ids_ordonnes}"
        )

        sans_preference = reorder_session_by_equipment_preference(items, set())
        assert [it["w_ex"]["exercise_id"] for it in sans_preference] == ["p_machine", "p_barre", "i_haltere"], (
            "aucune préférence -> aucun réordonnancement (ordre d'entrée préservé)"
        )
        print("OK 3 — reorder_session_by_equipment_preference : départage intra-palier correct, ordre préservé sans préférence")

        # ------------------------------------------------------------------
        # 4) adjust_rest_for_age / adjust_intensity_for_age : seuil de prudence
        # ------------------------------------------------------------------
        assert adjust_rest_for_age(90, None) == 90
        assert adjust_rest_for_age(90, 30) == 90
        assert adjust_rest_for_age(90, 55) == 105
        assert adjust_rest_for_age(None, 55) is None

        assert adjust_intensity_for_age("élevée", None) == "élevée"
        assert adjust_intensity_for_age("élevée", 30) == "élevée"
        assert adjust_intensity_for_age("élevée", 55) == "modérée"
        assert adjust_intensity_for_age("modérée", 55) == "faible"
        assert adjust_intensity_for_age("faible", 55) == "faible", "plancher de l'échelle, jamais négatif"
        assert adjust_intensity_for_age(None, 55) is None
        print("OK 4 — adjust_rest_for_age/adjust_intensity_for_age : ajustement correct au-delà du seuil de prudence")

        # ------------------------------------------------------------------
        # 5) compute_personalization_context : les 7 axes rassemblés
        # ------------------------------------------------------------------
        p_contexte = profil(
            niveau_musculation="Avancé", objectif_principal="Recomposition (sec + muscle)",
            objectif_secondaire="Gagner en force", preference_materiel="Haltères",
            disponibilite_reelle="4 à 6h", variables_json={"date_naissance": "1980-01-01"},
        )
        contexte = compute_personalization_context(p_contexte)
        assert set(contexte.keys()) == {
            "age", "niveau", "objectif_dominant", "contraintes", "forces", "faiblesses",
            "risques", "materiel_prefere", "disponibilite_reelle", "historique_feedback_deja_integre",
        }
        assert contexte["niveau"] == "Avancé"
        assert contexte["objectif_dominant"] == "force"
        assert contexte["materiel_prefere"] == "Haltères"
        assert contexte["disponibilite_reelle"] == "4 à 6h"
        assert contexte["historique_feedback_deja_integre"] is True
        assert contexte["age"] is not None and contexte["age"] > 40
        print("OK 5 — compute_personalization_context : les 7 axes de la consigne bien rassemblés")

        # ------------------------------------------------------------------
        # 6) generate_program_explanation : structure lisible, jamais d'exception
        # ------------------------------------------------------------------
        seances_detail = [{
            "nom": "Séance Pecs",
            "exercices": [{
                "exercise_id": "pecs_a", "raison_selection": "Mouvement composé prioritaire pour ce muscle.",
                "tier": "principal", "sets": 4, "intensity": "modérée",
            }],
        }]
        explication = generate_program_explanation(p_contexte, seances_detail, contexte)
        assert "Avancé" in explication["resume_profil"]
        assert explication["seances"][0]["nom"] == "Séance Pecs"
        exo_expl = explication["seances"][0]["exercices"][0]
        assert set(exo_expl.keys()) == {"exercise_id", "pourquoi_exercice", "pourquoi_volume", "pourquoi_intensite"}
        assert "composé prioritaire" in exo_expl["pourquoi_exercice"]
        assert "4 série" in exo_expl["pourquoi_volume"]

        # Jamais d'exception sur une entrée vide/incomplète.
        vide = generate_program_explanation(p_contexte, [], contexte)
        assert vide["seances"] == []
        print("OK 6 — generate_program_explanation : structure correcte, robuste à une entrée vide")

        # ------------------------------------------------------------------
        # 7) Intégration : deux profils différents -> programmes différents
        # ------------------------------------------------------------------
        user_jeune = User(email="perso-jeune@example.com")
        user_senior = User(email="perso-senior@example.com")
        db.session.add_all([user_jeune, user_senior])
        db.session.commit()

        catalogue = catalogue_complet("pers_", equipement="barre")
        for ex in catalogue:
            db.session.add(ex)
        db.session.commit()

        snap_jeune = ProfileSnapshot(
            user_id=user_jeune.id, poids=75.0, taille=178.0, sexe="Homme",
            niveau_musculation="Débutant complet", objectif_principal="Perte de gras",
            exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Avec difficulté",
            amplitude_epaule="Avec difficulté", tolerance_technique=3,
            preference_style_charge="Un mix des deux", preference_materiel="Pas de préférence",
            morphologie_declaree={}, blessures={}, autres_sports={}, sommeil="7 à 8h",
            stress="Modéré", disponibilite_reelle="Plus de 6h",
            variables_json={"duree_seance": "1h - 1h30", "frequence_entrainement": 5, "date_naissance": "1998-01-01"},
        )
        snap_senior = ProfileSnapshot(
            user_id=user_senior.id, poids=85.0, taille=175.0, sexe="Homme",
            niveau_musculation="Avancé", objectif_principal="Prise de muscle",
            exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Avec difficulté",
            amplitude_epaule="Avec difficulté", tolerance_technique=3,
            preference_style_charge="Un mix des deux", preference_materiel="Barres libres",
            morphologie_declaree={}, blessures={}, autres_sports={}, sommeil="7 à 8h",
            stress="Modéré", disponibilite_reelle="Moins de 2h",
            variables_json={"duree_seance": "1h - 1h30", "frequence_entrainement": 5, "date_naissance": "1960-01-01"},
        )
        db.session.add_all([snap_jeune, snap_senior])
        db.session.commit()

        resultat_jeune = build_program(snap_jeune, catalogue)
        resultat_senior = build_program(snap_senior, catalogue)

        assert resultat_jeune != resultat_senior, "deux profils différents doivent produire des programmes différents"
        assert len(resultat_jeune["sessions"]) == 5, "disponibilité large -> fréquence demandée conservée (5)"
        assert len(resultat_senior["sessions"]) == 2, "disponibilité 'Moins de 2h' -> fréquence plafonnée à 2"
        assert any("ramenée" in w for w in resultat_senior["warnings"]), "avertissement de réduction de fréquence attendu"
        assert not any("ramenée" in w for w in resultat_jeune["warnings"])

        notes_senior = [
            ex.get("notes") or "" for s in resultat_senior["sessions"] for ex in s["exercises"]
        ]
        assert any("âge déclaré" in n for n in notes_senior), "note d'âge attendue pour le profil senior (66 ans)"
        assert any("matériel préféré" in n for n in notes_senior), "note de matériel préféré attendue (catalogue 100% barre)"

        notes_jeune = [
            ex.get("notes") or "" for s in resultat_jeune["sessions"] for ex in s["exercises"]
        ]
        assert not any("âge déclaré" in n for n in notes_jeune), "profil jeune (28 ans) : pas de note d'âge"
        assert not any("matériel préféré" in n for n in notes_jeune), "préférence 'Pas de préférence' : pas de note matériel"

        assert "explanation" in resultat_jeune and "explanation" in resultat_senior
        assert resultat_senior["explanation"]["resume_profil"] != resultat_jeune["explanation"]["resume_profil"]
        print(
            f"OK 7 — profils différents (jeune {len(resultat_jeune['sessions'])} séances / "
            f"senior {len(resultat_senior['sessions'])} séances) : programmes bien distincts, "
            f"notes coaching âge/matériel présentes uniquement où attendu"
        )

        # ------------------------------------------------------------------
        # 8) Déterminisme préservé après cette phase
        # ------------------------------------------------------------------
        resultat_senior_bis = build_program(snap_senior, catalogue)
        assert resultat_senior_bis == resultat_senior, "le moteur doit rester déterministe pour un même profil/catalogue"
        print("OK 8 — déterminisme préservé : build_program(snap_senior) régénère un résultat strictement identique")

        # ------------------------------------------------------------------
        # 9) Ne jamais casser program_validation / program_repository / PDF
        # ------------------------------------------------------------------
        rapport = validate_generated_program(resultat_senior, snap_senior)
        assert rapport["valid"] is True, rapport["errors"]

        program_senior = create_program_from_result(user_senior.id, snap_senior.id, resultat_senior)
        assert program_senior.id is not None
        premiere_seance = program_senior.sessions[0]
        premier_exercice_persiste = premiere_seance.exercises[0]
        # Le repos ajusté (âge) et la note enrichie doivent bien avoir été
        # persistés (program_repository lit "rest_time"/"notes" par clé,
        # additifs ou non, cf. vérification faite en amont de cette phase).
        assert premier_exercice_persiste.rest_time_seconds is not None
        assert premier_exercice_persiste.notes and "âge déclaré" in premier_exercice_persiste.notes
        print(f"OK 9 — program_validation/program_repository fonctionnent normalement avec le résultat enrichi (Program #{program_senior.id})")

    print("\nTOUS LES TESTS DE LA PERSONNALISATION AVANCÉE DU PROGRAMME SONT PASSÉS")


if __name__ == "__main__":
    run()
