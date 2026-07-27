# -*- coding: utf-8 -*-
"""
Tests du moteur de scoring/filtrage (phase 6/16) — logic/recommendation/.
Profils et exercices fictifs, aucune persistance nécessaire (instances
SQLAlchemy transitoires, jamais ajoutées à une session).
"""
import app as appmod
from logic.models import ProfileSnapshot, Exercise
from logic.recommendation import score_exercise, evaluate_exercises
from logic.recommendation.fatigue import calculate_fatigue_budget
from logic.recommendation.objectives import get_objective_vector


def profil(**kwargs):
    defaults = dict(
        poids=75.0, taille=178.0, sexe="Homme",
        niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle",
        exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Avec difficulté",
        amplitude_epaule="Avec difficulté", tolerance_technique=3,
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


def check_score_range(result):
    if result["excluded"]:
        assert result["score_final"] is None
        assert result["exclusion_reason"]
    else:
        assert result["score_final"] is not None
        assert 0 <= result["score_final"] <= 100, result


def run():
    with appmod.app.app_context():

        # ------------------------------------------------------------------
        # 1) Débutant sans blessure
        # ------------------------------------------------------------------
        p1 = profil(niveau_musculation="Débutant complet", exercices_maitrises=[])
        squat_avance = exo(pattern="squat", equipment=["barre"], difficulty_level="avance",
                            technical_complexity=4, stability_demand="eleve")
        r1 = score_exercise(p1, squat_avance)
        check_score_range(r1)
        assert not r1["excluded"]
        assert r1["details"]["niveau"] < 0, "un débutant face à un exercice avancé doit être pénalisé"
        print("OK 1 — débutant sans blessure : score borné, pénalité niveau appliquée")

        # ------------------------------------------------------------------
        # 2) Avancé salle complète avec mouvements maîtrisés
        # ------------------------------------------------------------------
        p2 = profil(niveau_musculation="Avancé", exercices_maitrises=["Squat barre"], tolerance_technique=4)
        r2 = score_exercise(p2, squat_avance)
        check_score_range(r2)
        assert r2["details"]["niveau"] == 0, "un mouvement maîtrisé doit annuler la pénalité de complexité"
        print("OK 2 — avancé, mouvement maîtrisé : pénalité de niveau annulée")

        # ------------------------------------------------------------------
        # 3) Mobilité faible + squat impossible
        # ------------------------------------------------------------------
        p3 = profil(mobilite_generale=1, amplitude_squat="Non, pas du tout")
        squat_libre = exo(pattern="squat", equipment=["barre"])
        r3 = score_exercise(p3, squat_libre)
        assert r3["excluded"] is True
        assert "amplitude_squat_non" in r3["exclusion_reason"]
        print("OK 3a — squat profond libre exclu quand amplitude_squat = 'Non, pas du tout'")

        squat_guide = exo(pattern="squat", equipment=["machine"], stability_demand="eleve", technical_complexity=4)
        r3b = score_exercise(p3, squat_guide)
        check_score_range(r3b)
        assert not r3b["excluded"], "un squat GUIDÉ ne doit pas être exclu par amplitude_squat"
        assert r3b["details"]["biomecanique"] <= -3, "mobilité faible doit pénaliser un exercice exigeant en stabilité"
        print("OK 3b — squat guidé non exclu, mais pénalisé par la mobilité faible")

        # ------------------------------------------------------------------
        # 4) Douleur épaule invalidante
        # ------------------------------------------------------------------
        p4 = profil(blessures={"Épaule": "Douleur invalidante"})
        dev_militaire_risque = exo(pattern="developpe_militaire", joint_stress={"epaule": 2})
        r4 = score_exercise(p4, dev_militaire_risque)
        assert r4["excluded"] is True
        assert "douleur_invalidante_Épaule" in r4["exclusion_reason"]
        print("OK 4a — douleur invalidante épaule + joint_stress>=1 => exclusion")

        curl_sans_risque = exo(pattern="curl_standard", joint_stress={"epaule": 0})
        r4b = score_exercise(p4, curl_sans_risque)
        assert not r4b["excluded"], "une zone sans joint_stress ne doit jamais être exclue par une douleur ailleurs"
        print("OK 4b — exercice sans risque sur la zone douloureuse : non exclu")

        # ------------------------------------------------------------------
        # 5) Objectif recomposition
        # ------------------------------------------------------------------
        p5 = profil(objectif_principal="Recomposition (sec + muscle)", objectif_secondaire=None)
        vec = get_objective_vector(p5)
        assert abs(vec["force"] - 0.20) < 1e-9
        assert abs(vec["hypertrophie"] - 0.40) < 1e-9
        assert abs(vec["perte_de_gras"] - 0.40) < 1e-9
        assert vec["endurance_musculaire"] == 0 and vec["explosivite"] == 0

        p5b = profil(objectif_principal="Perte de gras", objectif_secondaire="Gagner en force")
        vec_b = get_objective_vector(p5b)
        # 0.75 x Perte de gras + 0.25 x Gagner en force
        assert abs(vec_b["force"] - (0.75 * 0 + 0.25 * 1.0)) < 1e-9
        assert abs(vec_b["perte_de_gras"] - (0.75 * 0.60)) < 1e-9
        print("OK 5 — objectifs composites (recomposition seule, et perte de gras + force secondaire) corrects")

        # ------------------------------------------------------------------
        # 6) Aucun exercice maîtrisé + tolérance technique 5/5
        # ------------------------------------------------------------------
        p6 = profil(exercices_maitrises=[], tolerance_technique=5, niveau_musculation="Débutant complet")
        exo_dur = exo(difficulty_level="avance")
        r6 = score_exercise(p6, exo_dur)
        check_score_range(r6)
        # penalite_brute = (3-0)*3 = 9 ; sans garde-fou, tolerance=5 annulerait 100% -> penalite=0
        # avec garde-fou (aucun exercice maîtrisé), reduction plafonnee a 50% -> penalite effective = 4.5 -> score niveau = -4.5
        assert abs(r6["details"]["niveau"] - (-4.5)) < 1e-9, r6["details"]
        print("OK 6 — garde-fou 50% actif quand aucun exercice n'est maîtrisé, malgré tolérance 5/5")

        # ------------------------------------------------------------------
        # Robustesse : profil quasi vide (incomplet) ne doit jamais planter
        # ------------------------------------------------------------------
        p_incomplet = ProfileSnapshot(poids=70.0, taille=170.0, sexe="Homme",
                                       niveau_musculation="Intermédiaire",
                                       objectif_principal="Condition physique générale")
        exo_incomplet = Exercise(exercise_id="ex_min", name="Min", family="f", pattern="p",
                                  muscle_principal="dos")
        r_incomplet = score_exercise(p_incomplet, exo_incomplet)
        check_score_range(r_incomplet)
        budget = calculate_fatigue_budget(p_incomplet)
        assert budget >= 10
        print("OK 7 — profil et exercice incomplets : aucun crash, score et budget toujours valides")

        # ------------------------------------------------------------------
        # evaluate_exercises : liste mixte (exclus + valides)
        # ------------------------------------------------------------------
        resultats = evaluate_exercises(p4, [dev_militaire_risque, curl_sans_risque, squat_guide])
        assert resultats[0]["excluded"] is True
        assert resultats[1]["excluded"] is False
        for r in resultats:
            check_score_range(r)
        print("OK 8 — evaluate_exercises gère une liste mixte exclus/valides sans plantage")

    print("\nTOUS LES TESTS DU MOTEUR DE SCORING SONT PASSÉS")


if __name__ == "__main__":
    run()
