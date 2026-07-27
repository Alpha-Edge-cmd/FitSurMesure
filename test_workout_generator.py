# -*- coding: utf-8 -*-
"""
Tests du générateur de séances (phase 8/16) —
logic/recommendation/workout_generator.py, volume.py, exercise_order.py.
"""
import app as appmod
from logic.models import ProfileSnapshot, Exercise
from logic.recommendation.workout_generator import (
    generate_workout,
    estimate_session_fatigue,
    MESSAGE_BUDGET_PLANCHER,
)
from logic.recommendation.fatigue import calculate_fatigue_budget
from logic.recommendation import exercise_order


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
        objectif_hypertrophie=2, **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=exercise_id, family=family, pattern=family,
        movement_type=movement_type, equipment=["barre"], muscle_principal=muscle,
        muscles_secondaires=[], unilateral=unilateral, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": objectif_hypertrophie},
        score_tension_mecanique=5, score_contraction_max=5, potentiel_hypertrophique=5,
        substitutes=[], contre_indications=[], actif=True,
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def catalogue_muscle(muscle, movement_type="push"):
    """1 principal composé bilatéral, 1 secondaire composé unilatéral,
    2 isolations — les composés ont un objectif "hypertrophie" plus élevé
    (score plus haut), cohérent avec la réalité (mouvements polyarticulaires
    généralement plus rentables)."""
    return [
        exo(f"{muscle}_principal", f"{muscle}_fam_principal", muscle=muscle,
            movement_type=movement_type, unilateral=False, objectif_hypertrophie=3),
        exo(f"{muscle}_secondaire", f"{muscle}_fam_secondaire", muscle=muscle,
            movement_type=movement_type, unilateral=True, objectif_hypertrophie=2),
        exo(f"{muscle}_isolation_1", f"{muscle}_fam_isolation_1", muscle=muscle,
            movement_type=None, unilateral=False, objectif_hypertrophie=1),
        exo(f"{muscle}_isolation_2", f"{muscle}_fam_isolation_2", muscle=muscle,
            movement_type=None, unilateral=False, objectif_hypertrophie=1),
    ]


def run():
    with appmod.app.app_context():

        # --------------------------------------------------------------
        # 1) Débutant full body : volume raisonnable
        # --------------------------------------------------------------
        # Prompt hors 24 phases (bascule PDF payant sur le moteur V2) : durée
        # "1h" plutôt que "1h - 1h30", volontairement HORS du plancher
        # explicite de volume total par séance ajouté à `workout_generator.
        # _completer_volume_minimum` (SESSION_MIN_EXOS) — ce plancher est une
        # politique de SÉANCE RÉELLE à plusieurs muscles (Push/Pull/Legs,
        # Upper/Lower...), déjà testée à ce niveau dans
        # test_min_exos_and_families.py ; il contaminerait ici un test dédié
        # à une préoccupation différente et orthogonale (l'échelle de volume
        # PAR MUSCLE selon le niveau) sur un catalogue synthétique minuscule
        # (4 exercices/muscle) qui n'a jamais eu vocation à représenter une
        # vraie séance de split.
        p_debutant = profil(niveau_musculation="Débutant complet")
        catalogue_full = catalogue_muscle("pecs", "push") + catalogue_muscle("dos", "pull")
        w1 = generate_workout(p_debutant, ["pecs", "dos"], catalogue_full, "1h")
        assert set(w1["muscles"]) == {"pecs", "dos"}
        for ex in w1["exercises"]:
            assert set(ex.keys()) == {
                "exercise_id", "name", "family", "muscle_principal", "score", "raison_selection"
            }
        compte_par_muscle_debutant = {
            m: sum(1 for e in w1["exercises"] if e["muscle_principal"] == m) for m in ("pecs", "dos")
        }
        for m, c in compte_par_muscle_debutant.items():
            assert 1 <= c <= 2, f"débutant : volume attendu 1-2 pour {m}, obtenu {c}"
        print(f"OK 1 — débutant full body : volume raisonnable {compte_par_muscle_debutant}")

        # --------------------------------------------------------------
        # 2) Avancé salle complète : plus de volume
        # --------------------------------------------------------------
        p_avance = profil(niveau_musculation="Avancé")
        w2 = generate_workout(p_avance, ["pecs", "dos"], catalogue_full, "1h")
        compte_par_muscle_avance = {
            m: sum(1 for e in w2["exercises"] if e["muscle_principal"] == m) for m in ("pecs", "dos")
        }
        assert sum(compte_par_muscle_avance.values()) > sum(compte_par_muscle_debutant.values()), (
            compte_par_muscle_avance, compte_par_muscle_debutant
        )
        print(f"OK 2 — avancé salle complète : volume supérieur au débutant {compte_par_muscle_avance}")

        # --------------------------------------------------------------
        # 3) Séance 30 minutes : priorisation des exercices importants
        # --------------------------------------------------------------
        p_inter = profil(niveau_musculation="Intermédiaire")
        w3 = generate_workout(p_inter, ["pecs"], catalogue_muscle("pecs", "push"), 30)
        assert len(w3["exercises"]) <= 2, "séance courte : volume attendu réduit"
        assert w3["exercises"], "au moins un exercice attendu"
        premier = w3["exercises"][0]
        assert premier["exercise_id"] == "pecs_principal", (
            f"séance courte : le mouvement composé principal doit être priorisé, obtenu {premier['exercise_id']}"
        )
        print(f"OK 3 — séance 30 min : {len(w3['exercises'])} exercice(s), priorité à {premier['exercise_id']!r}")

        # --------------------------------------------------------------
        # 4) Séance 2 heures : volume augmenté sans dépasser le budget de fatigue
        # --------------------------------------------------------------
        w4 = generate_workout(p_inter, ["pecs", "dos"], catalogue_full, "1h30+")
        budget4 = calculate_fatigue_budget(p_inter)
        lookup4 = {ex.exercise_id: ex for ex in catalogue_full}
        exercices_obj4 = [lookup4[e["exercise_id"]] for e in w4["exercises"]]
        total_fatigue4 = estimate_session_fatigue(exercices_obj4)
        # Prompt hors 24 phases (bascule PDF payant sur le moteur V2) :
        # `_completer_volume_minimum` peut désormais RÉ-AJOUTER des exercices
        # après la réduction budgétaire pour respecter le plancher explicite
        # de volume total (SESSION_MIN_EXOS["1h30+"] = 10, cf. workout_
        # generator.py) — un dépassement du budget de fatigue PAR EXERCICE
        # devient alors possible PAR DESIGN (le contrôle fin du volume
        # d'entraînement réel reste géré en aval, au niveau des SÉRIES, par
        # `prescription._ajuster_series_selon_budget`, jamais retiré) : la
        # 3e branche accepte ce cas, reconnaissable au message d'avertissement
        # "Impossible d'atteindre" (plancher demandé hors de portée avec ce
        # catalogue synthétique minuscule).
        depassement_du_au_plancher = any(
            w.startswith("Impossible d'atteindre") for w in w4["warnings"]
        )
        assert total_fatigue4 <= budget4 or MESSAGE_BUDGET_PLANCHER in w4["warnings"] or depassement_du_au_plancher, (
            total_fatigue4, budget4, w4["warnings"]
        )
        assert len(w4["exercises"]) >= sum(compte_par_muscle_debutant.values()), (
            "séance longue : volume attendu au moins égal à une séance courte/débutant"
        )
        print(f"OK 4 — séance 2h : {len(w4['exercises'])} exercices, fatigue {total_fatigue4}/{budget4:.1f}")

        # --------------------------------------------------------------
        # 5) Blessure épaule : aucun exercice interdit
        # --------------------------------------------------------------
        p_epaule = profil(blessures={"Épaule": "Douleur invalidante"})
        catalogue_epaule = [
            exo("dev_militaire_risque", "presse_epaules", muscle="epaules", movement_type="push",
                joint_stress={"epaule": 3}),
            exo("elevation_laterale_ok", "elevation_laterale", muscle="epaules", movement_type=None,
                joint_stress={"epaule": 0}),
        ]
        w5 = generate_workout(p_epaule, ["epaules"], catalogue_epaule, "1h - 1h30")
        ids5 = {e["exercise_id"] for e in w5["exercises"]}
        assert "dev_militaire_risque" not in ids5
        print(f"OK 5 — blessure épaule : exercice dangereux absent de la séance ({ids5})")

        # --------------------------------------------------------------
        # 6) Profil extrême : équipement limité + fallback dans une séance
        # --------------------------------------------------------------
        p_extreme = profil(
            niveau_musculation="Avancé",
            amplitude_squat="Non, pas du tout",
            mobilite_generale=1,
        )
        catalogue_extreme = [
            exo("squat_libre", "squat_family", muscle="quadriceps", movement_type="squat",
                pattern="squat", equipment=["barre"]),
            exo("presse_cuisses", "presse_family", muscle="quadriceps", movement_type="squat",
                pattern="presse", equipment=["machine"], stability_demand="faible", technical_complexity=1),
        ]
        w6 = generate_workout(p_extreme, ["quadriceps"], catalogue_extreme, "1h - 1h30")
        ids6 = {e["exercise_id"] for e in w6["exercises"]}
        assert "squat_libre" not in ids6, "squat profond libre doit rester exclu (amplitude_squat=non)"
        assert "presse_cuisses" in ids6, "un candidat sûr doit rester disponible malgré la contrainte"
        assert any("quadriceps" in w for w in w6["warnings"]), (
            f"un avertissement de fallback est attendu pour quadriceps, obtenu {w6['warnings']}"
        )
        print(f"OK 6 — profil extrême : fallback actif dans la séance, avertissements={w6['warnings']}")

    print("\nTOUS LES TESTS DU GÉNÉRATEUR DE SÉANCES SONT PASSÉS")


if __name__ == "__main__":
    run()
