# -*- coding: utf-8 -*-
"""
Tests de la prescription d'entraînement (phase 9/16) —
logic/recommendation/prescription.py, intensity.py, rest_time.py.

Retour Samy (composition corporelle / sport / volume) : la nouvelle règle de
volume positionnel par muscle (`volume.calculer_repartition_seance`, voir
`workout_generator.py`) ne s'applique qu'"à partir d'une heure" (durée >=
`SEUIL_NOUVELLE_REPARTITION_MINUTES` = 60 min), selon la formulation exacte
de Samy. Les tests 1 à 5 utilisent donc "45 min" comme durée passée à
`generate_workout`, volontairement SOUS ce seuil, pour isoler la logique de
prescription (séries/repos/intensité selon niveau/objectif) de la logique de
volume par muscle (déjà testée séparément dans test_workout_generator.py et
au niveau séance réelle dans test_min_exos_and_families.py). Sur les
catalogues synthétiques minuscules (4 exercices/muscle) utilisés ici, une
durée >= 1h forcerait l'ajout de TOUS les exercices disponibles (y compris
isolation) et fausserait ces assertions. Le test 6 reste en "1h30+" à
dessein (scénario explicitement "fatigue élevée") : son assertion porte sur
le budget de SÉRIES de `prescription.py` (mécanisme indépendant, en aval),
pas sur le nombre d'exercices."""
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
        w1 = generate_workout(p1, ["pecs"], catalogue1, "45 min")
        presc1 = generate_prescription(p1, w1, catalogue1)
        for e in presc1["exercises"]:
            # Retour Samy (prompt hors 24 phases, "minimum 3 série") : plancher
            # relevé de 2 à 3 (NIVEAU_SETS_RANGE["Débutant complet"] = (3, 4)).
            # Borne haute à 5 (pas 4) : mouvements composés (principal/secondaire)
            # peuvent recevoir le "+1 série possible" si le budget de fatigue le
            # permet (cf. _ajuster_series_selon_budget, mécanisme préexistant).
            assert 3 <= e["sets"] <= 5, e
            # Retour Samy ("les répétitions sont presque toujours entre 6 et 8,
            # je n'aime pas du tout") : la plage dépend désormais du PALIER du
            # mouvement, plus seulement de l'objectif. On ne peut donc plus
            # attendre une valeur unique pour toute la séance — on vérifie que
            # chaque plage reste dans le domaine hypertrophie, et la variété
            # entre paliers est contrôlée plus bas (test 5).
            bas, haut = (int(x) for x in e["reps"].split("-"))
            assert 6 <= bas <= 12 and 9 <= haut <= 20, e
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
        w2 = generate_workout(p2, ["dos"], catalogue2, "45 min")
        presc2 = generate_prescription(p2, w2, catalogue2)
        for e in presc2["exercises"]:
            # Dominant = force. Le mouvement principal descend en 3-6 (série
            # lourde), les accessoires restent en zone hypertrophie : c'est
            # exactement ce qui manquait avant, où tout sortait en 6-8.
            bas, haut = (int(x) for x in e["reps"].split("-"))
            assert 1 <= bas <= 10 and haut <= 15, e
        rest_moyen_1 = sum(e["rest_seconds"] for e in presc1["exercises"]) / len(presc1["exercises"])
        rest_moyen_2 = sum(e["rest_seconds"] for e in presc2["exercises"]) / len(presc2["exercises"])
        assert rest_moyen_2 > rest_moyen_1, (rest_moyen_2, rest_moyen_1)
        print(f"OK 2 — avancé force : reps réduites (3-6), repos plus longs ({rest_moyen_2:.0f}s > {rest_moyen_1:.0f}s)")

        # --------------------------------------------------------------
        # 3) Recomposition : choix cohérent
        # --------------------------------------------------------------
        p3 = profil(niveau_musculation="Intermédiaire", objectif_principal="Recomposition (sec + muscle)")
        catalogue3 = catalogue_muscle("quadriceps", "squat")
        w3 = generate_workout(p3, ["quadriceps"], catalogue3, "45 min")
        presc3 = generate_prescription(p3, w3, catalogue3)
        for e in presc3["exercises"]:
            bas, haut = (int(x) for x in e["reps"].split("-"))
            assert 6 <= bas <= 12 and haut <= 20, e
            assert e["intensity"] in ("faible", "modérée", "élevée"), e
            assert e["notes"], e
        print("OK 3 — recomposition : choix cohérent (reps 6-12, notes présentes)", presc3["exercises"][0])

        # --------------------------------------------------------------
        # 4) Explosivité : repos longs et faible volume
        # --------------------------------------------------------------
        p4 = profil(niveau_musculation="Avancé", objectif_principal="Performance / explosivité")
        catalogue4 = catalogue_muscle("pecs", "push")
        w4 = generate_workout(p4, ["pecs"], catalogue4, "45 min")
        presc4 = generate_prescription(p4, w4, catalogue4)
        for e in presc4["exercises"]:
            # Explosivité : séries courtes sur les mouvements principaux
            # (qualité du geste et vitesse, pas épuisement).
            bas, haut = (int(x) for x in e["reps"].split("-"))
            assert bas <= 8 and haut <= 12, e
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
        w5 = generate_workout(p5_normale, ["epaules"], catalogue5, "45 min")
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

        from logic.recommendation.prescription import _cout_fatigue_par_serie, MIN_SETS_FLOOR
        total_projete = sum(
            e["sets"] * _cout_fatigue_par_serie(lookup6[e["exercise_id"]]) for e in presc6["exercises"]
        )
        # Retour Samy (prompt hors 24 phases, plancher de volume par muscle) :
        # le budget de fatigue n'est plus un plafond ABSOLU — à partir d'1h de
        # séance, le plancher positionnel par muscle (`w6["muscle_floors"]`,
        # ici {"pecs": 4, "dos": 4} pour 2 muscles) prime dessus. Ici, le
        # catalogue synthétique (4 exercices/muscle) correspond exactement au
        # plancher : aucun exercice n'est retirable (`_retirer_exercices_si_
        # besoin` ne retire jamais en dessous du plancher), donc le budget
        # PEUT être dépassé une fois toutes les séries au plancher `MIN_SETS_
        # FLOOR`. L'invariant réel à vérifier n'est donc plus "jamais de
        # dépassement" mais : soit le budget est respecté, soit le
        # dépassement est explicable par le plancher (séries toutes au
        # plancher + avertissement dédié émis par `workout_generator` au
        # niveau séance, cf. `MESSAGE_BUDGET_PLANCHER`).
        if total_projete > budget6 + 1e-6:
            assert all(e["sets"] == MIN_SETS_FLOOR for e in presc6["exercises"]), presc6["exercises"]
            warnings_texte = " ".join(w6.get("warnings", []))
            assert "plancher" in warnings_texte.lower(), w6.get("warnings")
        for e in presc6["exercises"]:
            assert e["sets"] >= 1, e
        print(f"OK 6 — profil extrême (fatigue élevée) : {total_projete:.1f}/{budget6:.1f} (dépassement explicable par le plancher de volume), {len(presc6['exercises'])} exercices, tous sets>=1")

        # --------------------------------------------------------------
        # 7. Non-régression du retour Samy : « je ne veux pas voir quasiment
        #    tous les exercices en 6-8 répétitions ».
        #    Ce test échouerait sur l'ancienne implémentation, où
        #    determine_rep_range ignorait l'exercice et renvoyait une plage
        #    unique par objectif.
        # --------------------------------------------------------------
        import collections
        from logic.recommendation.prescription import determine_rep_range

        class _Exo:
            def __init__(self, movement_type, unilateral=False):
                self.movement_type = movement_type
                self.unilateral = unilateral
                self.technical_complexity = 2
                self.pattern = "p"

        # Séance type : 2 mouvements composés, 1 unilatéral, 3 isolations.
        seance_type = [_Exo("squat"), _Exo("push"), _Exo("pull", unilateral=True),
                       _Exo("autre"), _Exo("autre"), _Exo("autre")]
        objectifs = ["Prise de muscle", "Perte de gras", "Recomposition (sec + muscle)",
                     "Condition physique générale", "Performance / explosivité"]
        niveaux = ["Débutant complet", "Quelques mois d'expérience", "Intermédiaire", "Avancé"]

        plages = collections.Counter()
        for objectif in objectifs:
            for niveau in niveaux:
                p7 = profil(niveau_musculation=niveau, objectif_principal=objectif)
                for semaine in (1, 2, 3, 4):
                    for exo in seance_type:
                        plages[determine_rep_range(p7, exo, semaine=semaine)] += 1

        total = sum(plages.values())
        part_6_8 = plages["6-8"] / total

        # Au moins 10 plages distinctes sur l'ensemble des profils testés.
        assert len(plages) >= 10, plages
        # Le 6-8 reste possible (débutant en force notamment) mais ne doit plus
        # jamais dominer : plafond à 10% des prescriptions.
        assert part_6_8 <= 0.10, (part_6_8, plages)
        # Sur un même profil et une même séance, les paliers doivent produire
        # des plages différentes — c'est le cœur de la correction.
        p_hyper = profil(niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle")
        plages_seance = {determine_rep_range(p_hyper, e) for e in seance_type}
        assert len(plages_seance) >= 2, plages_seance

        print(f"OK 7 — répétitions variées : {len(plages)} plages distinctes, "
              f"6-8 réduit à {100 * part_6_8:.1f}% des prescriptions")

    print("\nTOUS LES TESTS DE LA PRESCRIPTION SONT PASSÉS")


if __name__ == "__main__":
    run()
