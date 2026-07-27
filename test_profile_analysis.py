# -*- coding: utf-8 -*-
"""
Tests de l'analyse de profil (phase 19/24) — logic/profile_analysis.py, et
de son branchement ADDITIF dans logic/recommendation/scoring.py,
selector.py, workout_generator.py (aucune signature publique changée, aucune
valeur déjà validée modifiée — cf. commentaires "phase 19/24" dans ces trois
fichiers).
"""
import app as appmod
from logic.models import Exercise, ProfileSnapshot
from logic.profile_analysis import analyze_profile
from logic.recommendation import evaluate_exercises, generate_workout, score_exercise, select_exercises


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
        morphologie_adaptee={}, objectifs_adaptes={}, score_tension_mecanique=5,
        score_contraction_max=5, potentiel_hypertrophique=5, substitutes=[],
        contre_indications=[], actif=True,
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def run():
    with appmod.app.app_context():

        # ------------------------------------------------------------------
        # 1) Débutant sans contrainte
        # ------------------------------------------------------------------
        p1 = profil(niveau_musculation="Débutant complet", exercices_maitrises=[])
        a1 = analyze_profile(p1)
        assert set(a1.keys()) == {"niveau", "objectif_dominant", "contraintes", "forces", "faiblesses", "risques", "priorites_moteur"}
        assert a1["niveau"] == "Débutant complet"
        assert a1["contraintes"] == [], "aucune contrainte attendue (pas de blessure, amplitude neutre)"
        assert a1["risques"] == []
        assert any("Niveau débutant complet" in f for f in a1["faiblesses"])
        assert any("Aucun mouvement technique maîtrisé" in f for f in a1["faiblesses"])
        assert a1["priorites_moteur"]["aucun_mouvement_maitrise"] is True
        print("OK 1 — débutant sans contrainte : niveau/faiblesses corrects, aucune contrainte")

        # ------------------------------------------------------------------
        # 2) Athlète avancé
        # ------------------------------------------------------------------
        p2 = profil(
            niveau_musculation="Avancé", exercices_maitrises=["Squat barre", "Développé couché barre"],
            tolerance_technique=4, mobilite_generale=4,
        )
        a2 = analyze_profile(p2)
        assert a2["niveau"] == "Avancé"
        assert any("Niveau avancé" in f for f in a2["forces"])
        assert any("maîtrisés" in f for f in a2["forces"])
        assert any("Bonne mobilité" in f for f in a2["forces"])
        assert a2["priorites_moteur"]["aucun_mouvement_maitrise"] is False
        assert a2["faiblesses"] == []
        print("OK 2 — athlète avancé : niveau/forces corrects, aucune faiblesse")

        # ------------------------------------------------------------------
        # 3) Mobilité faible
        # ------------------------------------------------------------------
        p3 = profil(mobilite_generale=1)
        a3 = analyze_profile(p3)
        assert any("Mobilité générale faible" in f for f in a3["faiblesses"])
        print("OK 3 — mobilité faible détectée dans les faiblesses")

        # ------------------------------------------------------------------
        # 4) Blessure épaule
        # ------------------------------------------------------------------
        p4 = profil(blessures={"Épaule": "Douleur invalidante"})
        a4 = analyze_profile(p4)
        assert len(a4["risques"]) == 1 and a4["risques"][0]["zone"] == "Épaule"
        assert a4["risques"][0]["rang"] == 3
        assert any("Blessure déclarée sur 'Épaule'" in c for c in a4["contraintes"])
        assert a4["priorites_moteur"]["nombre_risques_declares"] == 1
        print("OK 4 — blessure épaule : risque et contrainte correctement identifiés")

        # ------------------------------------------------------------------
        # 5) Objectif force (principal + secondaire "Gagner en force")
        # ------------------------------------------------------------------
        p5 = profil(objectif_principal="Recomposition (sec + muscle)", objectif_secondaire="Gagner en force")
        a5 = analyze_profile(p5)
        assert a5["objectif_dominant"] == "force", a5["priorites_moteur"]["vecteur_objectif"]
        print(f"OK 5 — objectif force : dominant='{a5['objectif_dominant']}' ({a5['priorites_moteur']['vecteur_objectif']})")

        # ------------------------------------------------------------------
        # 6) Objectif perte de gras
        # ------------------------------------------------------------------
        p6 = profil(objectif_principal="Perte de gras", objectif_secondaire=None)
        a6 = analyze_profile(p6)
        assert a6["objectif_dominant"] == "perte_de_gras"
        print(f"OK 6 — objectif perte de gras : dominant='{a6['objectif_dominant']}'")

        # ------------------------------------------------------------------
        # Branchement additif : scoring.py (score_exercise/evaluate_exercises)
        # ------------------------------------------------------------------
        ex_pecs = exo(exercise_id="pecs_x", muscle_principal="pecs")
        resultat_score = score_exercise(p1, ex_pecs)
        assert resultat_score["profile_analysis"] == a1, "scoring.score_exercise doit exposer le même analyze_profile"
        resultats_eval = evaluate_exercises(p2, [ex_pecs])
        assert resultats_eval[0]["profile_analysis"] == a2
        print("OK branchement scoring.py — clé 'profile_analysis' additive présente et cohérente")

        # ------------------------------------------------------------------
        # Branchement additif : selector.py (select_exercises)
        # ------------------------------------------------------------------
        pecs_force = exo(exercise_id="pecs_force", muscle_principal="pecs",
                          objectifs_adaptes={"force": 9, "hypertrophie": 5, "endurance_musculaire": 1, "perte_de_gras": 1, "explosivite": 3})
        pecs_gras = exo(exercise_id="pecs_gras", muscle_principal="pecs", difficulty_level="debutant", technical_complexity=1,
                         stability_demand="faible", equipment=["poids_du_corps"],
                         objectifs_adaptes={"force": 1, "hypertrophie": 3, "endurance_musculaire": 6, "perte_de_gras": 9, "explosivite": 1})
        selection = select_exercises(p1, [pecs_force, pecs_gras], "pecs", 2)
        assert all("profile_analysis" in c for c in selection)
        assert selection[0]["profile_analysis"] == a1
        print("OK branchement selector.py — clé 'profile_analysis' additive présente dans chaque candidat retenu")

        # ------------------------------------------------------------------
        # Vérification centrale : la sélection change réellement selon le
        # profil (objectif force vs perte de gras, sur les 2 mêmes exercices)
        # ------------------------------------------------------------------
        top_force = select_exercises(p5, [pecs_force, pecs_gras], "pecs", 1)
        top_gras = select_exercises(p6, [pecs_force, pecs_gras], "pecs", 1)
        assert top_force[0]["exercise"].exercise_id == "pecs_force", "objectif force doit privilégier l'exercice orienté force"
        assert top_gras[0]["exercise"].exercise_id == "pecs_gras", "objectif perte de gras doit privilégier l'exercice orienté perte de gras"
        assert top_force[0]["exercise"].exercise_id != top_gras[0]["exercise"].exercise_id
        print("OK — la sélection change réellement selon le profil (force -> pecs_force, perte de gras -> pecs_gras)")

        # Niveau : débutant vs avancé sur un exercice avancé de quadriceps.
        quad_avance = exo(exercise_id="quad_avance", muscle_principal="quadriceps", pattern="squat",
                           equipment=["barre"], difficulty_level="avance", technical_complexity=4, stability_demand="eleve")
        quad_debutant = exo(exercise_id="quad_debutant", muscle_principal="quadriceps", pattern="leg_press",
                             equipment=["machine"], difficulty_level="debutant", technical_complexity=1, stability_demand="faible")
        top_debutant = select_exercises(p1, [quad_avance, quad_debutant], "quadriceps", 1)
        top_avance = select_exercises(p2, [quad_avance, quad_debutant], "quadriceps", 1)
        assert top_debutant[0]["exercise"].exercise_id == "quad_debutant", "un débutant doit être pénalisé sur l'exercice avancé"
        # Un athlète avancé ayant maîtrisé le squat ne doit plus être pénalisé dessus.
        assert top_avance[0]["exercise"].exercise_id == "quad_avance", "un mouvement maîtrisé par un avancé doit primer"
        print("OK — la sélection change réellement selon le niveau (débutant -> quad_debutant, avancé -> quad_avance)")

        # ------------------------------------------------------------------
        # Branchement additif : workout_generator.py (generate_workout) +
        # blessure épaule : exercice dangereux exclu de la séance générée.
        # ------------------------------------------------------------------
        epaule_risque = exo(exercise_id="epaule_risque", muscle_principal="epaules", pattern="developpe_militaire",
                             equipment=["barre"], joint_stress={"epaule": 3})
        epaule_sure = exo(exercise_id="epaule_sure", muscle_principal="epaules", pattern="elevation_laterale",
                           equipment=["haltere"], joint_stress={})
        workout4 = generate_workout(p4, ["epaules"], [epaule_risque, epaule_sure], "1h - 1h30")
        assert "profile_analysis" in workout4
        assert workout4["profile_analysis"] == a4
        ids4 = {e["exercise_id"] for e in workout4["exercises"]}
        assert "epaule_risque" not in ids4, "un exercice dangereux pour la blessure déclarée ne doit jamais être sélectionné"
        for ex in workout4["exercises"]:
            assert set(ex.keys()) == {"exercise_id", "name", "family", "muscle_principal", "score", "raison_selection"}, (
                "le contrat existant des exercices d'une séance ne doit pas changer (phase 8, inchangé)"
            )
        print("OK branchement workout_generator.py — 'profile_analysis' additif présent, exercice dangereux toujours exclu")

    print("\nTOUS LES TESTS DE L'ANALYSE DE PROFIL SONT PASSÉS")


if __name__ == "__main__":
    run()
