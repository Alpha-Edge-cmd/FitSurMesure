# -*- coding: utf-8 -*-
"""
Tests de la prescription d'entraînement (phase 9/16) —
logic/recommendation/prescription.py, intensity.py, rest_time.py.
"""
import app as appmod
from logic.models import ProfileSnapshot, Exercise
from logic.recommendation.workout_generator import generate_workout
from logic.recommendation.prescription import generate_prescription
from logic.recommendation.fatigue import calculate_fatigue_budget


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


def exo(exercise_id, family, muscle="pecs", movement_type="push", unilateral=False,
        **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=exercise_id, family=family, pattern=family,
        movement_type=movement_type, equipment=["barre"], muscle_principal=muscle,
        muscles_secondaires=[], unilateral=unilateral, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": 2},
        score_tension_mecanique=5, score_contraction_max=5, potentiel_hypertrophique=5,
        substitutes=[], contre_indications=[], actif=True,
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def catalogue_muscle(muscle, movement_type="push"):
    return [
        exo(f"{muscle}_principal", f"{muscle}_fam_principal", muscle=muscle,
            movement_type=movement_type, unilateral=False, pattern="autre"),
        exo(f"{muscle}_secondaire", f"{muscle}_fam_secondaire", muscle=muscle,
            movement_type=movement_type, unilateral=True, pattern="autre"),
        exo(f"{muscle}_isolation_1", f"{muscle}_fam_isolation_1", muscle=muscle,
            movement_type=None, unilateral=False, pattern="autre"),
        exo(f"{muscle}_isolation_2", f"{muscle}_fam_isolation_2", muscle=muscle,
            movement_type=None, unilateral=False, pattern="autre"),
    ]


def _prescription_par_id(prescription):
    return {e["exercise_id"]: e for e in prescription["exercises"]}


def run():
    with appmod.app.app_context():

        # --------------------------------------------------------------
        # 1) Débutant hypertrophie : séries raisonnables, repos adaptés
        # --------------------------------------------------------------
        p1 = profil(niveau_musculation="Débutant complet", objectif_principal="Prise de muscle")
        catalogue1 = catalogue_muscle("pecs", "push")
        w1 = generate_workout(p1, ["pecs"], catalogue1, "1h - 1h30")
        presc1 = generate_prescription(p1, w1, catalogue1)
        for e in presc1["exercises"]:
            assert 2 <= e["sets"] <= 4, e
            assert e["reps"] == "6-12", e  # dominant = hypertrophie pour "Prise de muscle"
            assert 60 <= e["rest_seconds"] <= 120, e
            assert e["intensity"] in ("faible", "modérée"), e  # débutant : jamais élevée
        print("OK 1 — débutant hypertrophie : séries/repos/intensité cohérents", presc1)

        # --------------------------------------------------------------
        # 2) Avancé force : moins de répétitions, repos plus longs
        # --------------------------------------------------------------
        p2 = profil(
            niveau_musculation="Avancé",
            objectif_principal="Condition physique générale",
            objectif_secondaire="Gagner en force",
        )
        catalogue2 = catalogue_muscle("dos", "pull")
        w2 = generate_workout(p2, ["dos"], catalogue2, "1h - 1h30")
        presc2 = generate_prescription(p2, w2, catalogue2)
        for e in presc2["exercises"]:
            assert e["reps"] == "3-6", e  # dominant = force
        rest_moyen_1 = sum(e["rest_seconds"] for e in presc1["exercises"]) / len(presc1["exercises"])
        rest_moyen_2 = sum(e["rest_seconds"] for e in presc2["exercises"]) / len(presc2["exercises"])
        assert rest_moyen_2 > rest_moyen_1, (rest_moyen_2, rest_moyen_1)
        print(f"OK 2 — avancé force : reps réduites (3-6), repos plus longs ({rest_moyen_2:.0f}s > {rest_moyen_1:.0f}s)")

        # --------------------------------------------------------------
        # 3) Recomposition : choix cohérent
        # --------------------------------------------------------------
        p3 = profil(niveau_musculation="Intermédiaire", objectif_principal="Recomposition (sec + muscle)")
        catalogue3 = catalogue_muscle("quadriceps", "squat")
        w3 = generate_workout(p3, ["quadriceps"], catalogue3, "1h - 1h30")
        presc3 = generate_prescription(p3, w3, catalogue3)
        for e in presc3["exercises"]:
            assert e["reps"] == "6-12", e  # dominant = hypertrophie (0.40, premier max ex-aequo avec perte_de_gras)
            assert e["intensity"] in ("faible", "modérée", "élevée"), e
            assert e["notes"], e
        print("OK 3 — recomposition : choix cohérent (reps 6-12, notes présentes)", presc3["exercises"][0])

        # --------------------------------------------------------------
        # 4) Explosivité : repos longs et faible volume
        # --------------------------------------------------------------
        p4 = profil(niveau_musculation="Avancé", objectif_principal="Performance / explosivité")
        catalogue4 = catalogue_muscle("pecs", "push")
        w4 = generate_workout(p4, ["pecs"], catalogue4, "1h - 1h30")
        presc4 = generate_prescription(p4, w4, catalogue4)
        for e in presc4["exercises"]:
            assert e["reps"] == "3-8", e
            assert e["rest_seconds"] >= 120, e
            assert e["sets"] <= 3, e  # faible volume attendu (borne basse, niveau avancé = 3)
        assert any(e["notes"] == "Recherche de vitesse maximale, arrêter si perte de qualité." for e in presc4["exercises"])
        print("OK 4 — explosivité : repos longs (>=120s), volume faible, note dédiée présente")

        # --------------------------------------------------------------
        # 5) Tolérance technique faible : intensité limitée
        # --------------------------------------------------------------
        p5_normale = profil(
            niveau_musculation="Intermédiaire",
            objectif_principal="Condition physique générale",
            objectif_secondaire="Gagner en force",
            tolerance_technique=4,
        )
        p5_faible = profil(
            niveau_musculation="Intermédiaire",
            objectif_principal="Condition physique générale",
            objectif_secondaire="Gagner en force",
            tolerance_technique=1,
        )
        catalogue5 = catalogue_muscle("epaules", "push")
        w5 = generate_workout(p5_normale, ["epaules"], catalogue5, "1h - 1h30")
        presc5_normale = generate_prescription(p5_normale, w5, catalogue5)
        presc5_faible = generate_prescription(p5_faible, w5, catalogue5)
        ordre = {"faible": 0, "modérée": 1, "élevée": 2}
        by_id_normale = _prescription_par_id(presc5_normale)
        by_id_faible = _prescription_par_id(presc5_faible)
        for exercise_id in by_id_normale:
            assert ordre[by_id_faible[exercise_id]["intensity"]] <= ordre[by_id_normale[exercise_id]["intensity"]], (
                exercise_id, by_id_faible[exercise_id]["intensity"], by_id_normale[exercise_id]["intensity"]
            )
        print("OK 5 — tolérance technique faible : intensité toujours <= à la tolérance normale")

        # --------------------------------------------------------------
        # 6) Profil extrême fatigue élevée : aucun dépassement dangereux
        # --------------------------------------------------------------
        p6 = profil(
            niveau_musculation="Avancé",
            objectif_principal="Prise de muscle",
            sommeil="Moins de 6h",
            stress="Élevé",
            variables_json={"duree_seance": "1h30+"},
        )
        catalogue6 = catalogue_muscle("pecs", "push") + catalogue_muscle("dos", "pull")
        w6 = generate_workout(p6, ["pecs", "dos"], catalogue6, "1h30+")
        presc6 = generate_prescription(p6, w6, catalogue6)
        lookup6 = {ex.exercise_id: ex for ex in catalogue6}
        budget6 = calculate_fatigue_budget(p6)

        from logic.recommendation.prescription import _cout_fatigue_par_serie
        total_projete = sum(
            e["sets"] * _cout_fatigue_par_serie(lookup6[e["exercise_id"]]) for e in presc6["exercises"]
        )
        assert total_projete <= budget6 + 1e-6, (total_projete, budget6)
        for e in presc6["exercises"]:
            assert e["sets"] >= 1, e
        print(f"OK 6 — profil extrême (fatigue élevée) : {total_projete:.1f}/{budget6:.1f}, aucun dépassement, {len(presc6['exercises'])} exercices, tous sets>=1")

    print("\nTOUS LES TESTS DE LA PRESCRIPTION SONT PASSÉS")


if __name__ == "__main__":
    run()
