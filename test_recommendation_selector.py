# -*- coding: utf-8 -*-
"""
Tests du module de sélection d'exercices (phase 7/16) —
logic/recommendation/selector.py, diversity.py, fallback.py.
"""
import app as appmod
from logic.models import ProfileSnapshot, Exercise
from logic.recommendation import select_exercises, run_fallback_cascade
from logic.recommendation.selector import PENALITE_RECENCE


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


def exo(exercise_id, family, pattern, muscle="pecs", **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=exercise_id, family=family, pattern=pattern,
        movement_type="push", equipment=["barre"], muscle_principal=muscle,
        muscles_secondaires=[], unilateral=False, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": 2}, score_tension_mecanique=5,
        score_contraction_max=5, potentiel_hypertrophique=5, substitutes=[],
        contre_indications=[], actif=True,
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def pecs_catalogue_riche():
    """3 familles distinctes, 2 variantes chacune -> assez pour tester la
    diversité sur une sélection de 3-4 exercices."""
    return [
        exo("dc_barre", "presse_pecs", "developpe_plat"),
        exo("dc_haltere", "presse_pecs", "developpe_plat", equipment=["haltere"]),
        exo("dc_incline", "presse_pecs", "developpe_incline"),
        exo("ecarte_poulie", "ecarte_pecs", "fly", equipment=["machine"]),
        exo("ecarte_haltere", "ecarte_pecs", "fly", equipment=["haltere"]),
        exo("dips_pecs", "dips_pompes_pecs", "dips_pecs", equipment=["poids_du_corps"]),
        exo("pompes", "dips_pompes_pecs", "pompes", equipment=["poids_du_corps"]),
    ]


def mollets_catalogue_pauvre():
    """Une seule famille disponible -> doit déclencher la cascade si on
    demande plus d'exercices que ce qu'une seule famille peut fournir sans
    répétition."""
    return [
        exo("mollet_debout", "mollets_debout", "mollet_debout", muscle="mollets"),
        exo("mollet_assis", "mollets_assis", "mollet_assis", muscle="mollets"),
    ]


def run():
    with appmod.app.app_context():

        # --------------------------------------------------------------
        # 1) Profil normal : sélection correcte de plusieurs exercices
        # --------------------------------------------------------------
        p1 = profil()
        selection = select_exercises(p1, pecs_catalogue_riche(), "pecs", 3)
        assert len(selection) == 3
        for c in selection:
            assert c["score"] is not None and 0 <= c["score"] <= 100
        print("OK 1 — profil normal : 3 exercices sélectionnés, scores valides")

        # --------------------------------------------------------------
        # 2) Muscle avec beaucoup d'exercices : diversité des familles
        # --------------------------------------------------------------
        selection4 = select_exercises(p1, pecs_catalogue_riche(), "pecs", 4)
        familles = [c["exercise"].family for c in selection4]
        assert len(set(familles)) >= 3, f"attendu au moins 3 familles distinctes sur 4 choix, obtenu {familles}"
        print("OK 2 — diversité de famille respectée sur une sélection de 4 exercices :", familles)

        # --------------------------------------------------------------
        # 3) Muscle pauvre : cascade fallback activée
        # --------------------------------------------------------------
        result_pauvre = run_fallback_cascade(p1, mollets_catalogue_pauvre(), "mollets", 4)
        assert result_pauvre["fallback_level"] >= 3, result_pauvre
        assert len(result_pauvre["exercises"]) <= 4
        assert result_pauvre["exercises"], "au moins un exercice mollet devait rester disponible"
        print(f"OK 3 — muscle pauvre : cascade déclenchée (niveau {result_pauvre['fallback_level']}), warning={result_pauvre['warning']!r}")

        # --------------------------------------------------------------
        # 4) Blessure épaule : aucun exercice interdit ne revient, même en fallback
        # --------------------------------------------------------------
        p4 = profil(blessures={"Épaule": "Douleur invalidante"})
        catalogue_epaule = [
            exo("dev_militaire_risque", "presse_epaules", "developpe_militaire", muscle="epaules",
                joint_stress={"epaule": 3}),
        ]
        result4 = run_fallback_cascade(p4, catalogue_epaule, "epaules", 2)
        assert result4["exercises"] == [], result4
        assert result4["fallback_level"] == 5
        assert "Aucun exercice disponible" in result4["warning"]
        print("OK 4 — exercice dangereux jamais retourné, même en dernier recours (niveau 5, warning explicite)")

        # exercice sain doit rester utilisable pour le même muscle malgré la blessure
        catalogue_epaule_mixte = catalogue_epaule + [
            exo("elevation_laterale_ok", "elevation_laterale", "elevation_laterale", muscle="epaules",
                joint_stress={"epaule": 0}),
        ]
        result4b = run_fallback_cascade(p4, catalogue_epaule_mixte, "epaules", 2)
        ids_retenus = {e["exercise_id"] for e in result4b["exercises"]}
        assert "dev_militaire_risque" not in ids_retenus
        assert "elevation_laterale_ok" in ids_retenus
        print("OK 4b — l'exercice sûr reste disponible, seul le dangereux est écarté")

        # --------------------------------------------------------------
        # 5) Historique futur simulé : un exercice récent est pénalisé
        # --------------------------------------------------------------
        cat_recence = [
            exo("dc_barre", "presse_pecs", "developpe_plat"),
            exo("dc_incline", "presse_pecs", "developpe_incline"),
        ]

        def fake_recent(user_id, window_weeks=8):
            return ["dc_barre"]

        selection_sans_recence = select_exercises(p1, cat_recence, "pecs", 1)
        selection_avec_recence = select_exercises(p1, cat_recence, "pecs", 1, recent_exercises_provider=fake_recent)
        # Les deux exercices ont un score identique par construction (mêmes attributs) ;
        # sans récence, l'un ou l'autre peut sortir en tête (égalité) ; avec récence
        # simulée sur dc_barre, dc_incline doit strictement passer devant.
        assert selection_avec_recence[0]["exercise"].exercise_id == "dc_incline"
        print("OK 5 — un exercice marqué récent (simulation) reçoit une pénalité et perd sa place")

        # --------------------------------------------------------------
        # 6) Profil extrême : équipement limité + contraintes multiples
        # --------------------------------------------------------------
        p6 = profil(
            blessures={"Épaule": "Gêne modérée régulière"},
            mobilite_generale=1,
            amplitude_squat="Non, pas du tout",
        )
        catalogue_extreme = [
            exo("squat_libre", "squat_family", "squat", muscle="quadriceps", equipment=["barre"]),
            exo("presse_cuisses", "presse_family", "presse", muscle="quadriceps", equipment=["machine"],
                stability_demand="faible", technical_complexity=1),
            exo("dev_militaire_leger", "presse_epaules", "developpe_militaire", muscle="epaules",
                joint_stress={"epaule": 1}),
        ]
        result6 = run_fallback_cascade(p6, catalogue_extreme, "quadriceps", 2)
        ids6 = {e["exercise_id"] for e in result6["exercises"]}
        assert "squat_libre" not in ids6, "squat profond libre doit rester exclu (amplitude_squat=non)"
        scores6 = [e["score"] for e in result6["exercises"]]
        assert scores6 == sorted(scores6, reverse=True), "les scores retournés doivent être triés décroissants"
        print(f"OK 6 — profil extrême : aucun exercice dangereux, résultat cohérent (niveau {result6['fallback_level']})")

        # --------------------------------------------------------------
        # 7) BUG CRITIQUE (retour Samy, prompt hors 24 phases) : un exercice
        # déclaré "je ne sais pas faire" au questionnaire (exercices_incapables)
        # ne doit JAMAIS revenir, même en dernier recours. Root cause du bug
        # observé : ce champ n'était lu QUE par le moteur legacy, jamais par
        # le moteur V2 (cf. logic/recommendation/filters.py,
        # _exercices_incapables_exclusion_reason). Les variantes "à la Smith
        # machine"/guidées, elles, doivent rester utilisables (mouvement
        # différent d'un "barre libre").
        # --------------------------------------------------------------
        p7 = profil(variables_json={
            "duree_seance": "1h - 1h30",
            "exercices_incapables": ["Squat barre libre", "Soulevé de terre barre"],
        })
        catalogue_incapable = [
            exo("squat_barre_libre", "squat_family", "squat", muscle="quadriceps",
                equipment=["barre"], name="Squat arrière à la barre (Back Squat)"),
            exo("squat_smith", "squat_family", "squat", muscle="quadriceps",
                equipment=["barre", "machine"], name="Squat à la Smith machine"),
            exo("dl_barre", "hinge_family", "hinge", muscle="dos",
                equipment=["barre"], name="Soulevé de terre traditionnel (Deadlift) à la barre"),
            exo("dl_haltere", "hinge_family", "hinge", muscle="dos",
                equipment=["haltere"], name="Soulevé de terre roumain aux haltères"),
        ]
        res7_quad = run_fallback_cascade(p7, catalogue_incapable, "quadriceps", 2)
        ids7_quad = {e["exercise_id"] for e in res7_quad["exercises"]}
        assert "squat_barre_libre" not in ids7_quad, "squat barre libre déclaré non maîtrisé doit être exclu"
        assert "squat_smith" in ids7_quad, "le Smith machine (guidé) doit rester proposé"

        res7_dos = run_fallback_cascade(p7, catalogue_incapable, "dos", 2)
        ids7_dos = {e["exercise_id"] for e in res7_dos["exercises"]}
        assert "dl_barre" not in ids7_dos, "soulevé de terre à la barre déclaré non maîtrisé doit être exclu"
        assert "dl_haltere" in ids7_dos, "la variante haltères doit rester proposée"
        print("OK 7 — exercices_incapables (questionnaire) bien exclus par le moteur V2, variantes guidées/haltères conservées")

    print("\nTOUS LES TESTS DU SÉLECTEUR SONT PASSÉS")


if __name__ == "__main__":
    run()
