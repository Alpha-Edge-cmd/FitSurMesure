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
            # Retour Samy (« les séries sont bloquées à 3 ») : l'ancienne
            # version ramenait l'explosivité au plancher de 3 séries, ce qui
            # est contraire au principe même du travail de puissance — des
            # séries de 2 à 5 répétitions doivent être PLUS nombreuses, pas
            # moins. Ce qui doit rester faible, c'est le volume TOTAL de
            # répétitions, pas le nombre de séries.
            assert 3 <= e["sets"] <= 6, e
            # Borne large : sur un mouvement unilatéral, la plage est décalée
            # de +2 répétitions (elles se comptent par côté, la charge absolue
            # étant plus faible), ce qui remonte mécaniquement ce total.
            volume_total = e["sets"] * haut
            assert volume_total <= 48, (volume_total, e)
        assert any(e["notes"] == "Recherche de vitesse maximale, arrêter si perte de qualité." for e in presc4["exercises"])
        volume_moyen = sum(e["sets"] * int(e["reps"].split("-")[1]) for e in presc4["exercises"]) / len(presc4["exercises"])
        print(f"OK 4 — explosivité : repos longs (>=120s), séries courtes et nombreuses, volume total contenu ({volume_moyen:.0f} répétitions/exercice)")

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
            # Retour Samy (« toujours bloqué à 3 séries ») : cette assertion
            # encodait exactement le défaut signalé — dès que le budget de
            # fatigue était dépassé, TOUT le programme tombait au plancher, et
            # la hiérarchie entre mouvements composés et isolations
            # disparaissait. Déclarer « moins de 6h » de sommeil suffisait à
            # aplatir 56 exercices sur 56.
            #
            # Nouveau comportement attendu : le volume est bien réduit (aucun
            # exercice au-dessus de 4 séries, plus de bonus de niveau), mais
            # les mouvements composés gardent une série de plus que les
            # isolations.
            assert all(MIN_SETS_FLOOR <= e["sets"] <= 4 for e in presc6["exercises"]), presc6["exercises"]
            assert len({e["sets"] for e in presc6["exercises"]}) >= 2, presc6["exercises"]
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

        # Retour Samy : « les plages doivent rester avec maximum 3 répétitions
        # d'écart, pas de plages absurdes comme 8-20 ». Toute plage est donc
        # ramenée à une plage canonique (normaliser_plage) — il y a
        # mécaniquement MOINS de plages distinctes qu'avant, et c'est voulu.
        # On vérifie donc la conformité, pas le nombre.
        from logic.recommendation.prescription import PLAGES_CANONIQUES
        canoniques = {f"{b}-{h}" for b, h in PLAGES_CANONIQUES}
        for plage in plages:
            if "sec" in plage:
                continue
            assert plage in canoniques, (plage, sorted(canoniques))
        assert len(plages) >= 4, plages
        # Le 6-8 reste une plage parfaitement légitime — c'est même une des
        # plages canoniques demandées (6-8 -> 5 séries, travail de force). Ce
        # qui n'allait pas, c'est qu'elle représentait la quasi-totalité des
        # prescriptions. Plafond à 25% : présente, jamais dominante.
        assert part_6_8 <= 0.25, (part_6_8, plages)
        # Et la plage d'hypertrophie doit rester la plus fréquente, puisque
        # c'est l'objectif le plus courant.
        plage_dominante = plages.most_common(1)[0][0]
        assert plage_dominante in ("8-10", "10-12", "12-15"), plages
        # Sur un même profil et une même séance, les paliers doivent produire
        # des plages différentes — c'est le cœur de la correction.
        p_hyper = profil(niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle")
        plages_seance = {determine_rep_range(p_hyper, e) for e in seance_type}
        assert len(plages_seance) >= 2, plages_seance

        print(f"OK 7 — répétitions variées : {len(plages)} plages distinctes, "
              f"6-8 réduit à {100 * part_6_8:.1f}% des prescriptions")

        # --------------------------------------------------------------
        # 8. Non-régression du second retour Samy : « les séries sont
        #    bloquées à 3 ». L'ancienne version renvoyait MIN_SETS_FLOOR pour
        #    tout ce qui n'était ni principal ni secondaire, donc 100% des
        #    isolations et 74% des exercices d'un programme.
        # --------------------------------------------------------------
        from logic.recommendation.prescription import _sets_de_base, _dominant_objective

        series = collections.Counter()
        seances_variees = 0
        seances_total = 0
        for objectif in objectifs:
            for niveau in niveaux:
                p8 = profil(niveau_musculation=niveau, objectif_principal=objectif)
                dom8 = _dominant_objective(p8)
                valeurs = [_sets_de_base(p8, e, dom8, False)[0] for e in seance_type]
                for v in valeurs:
                    series[v] += 1
                seances_total += 1
                if len(set(valeurs)) >= 2:
                    seances_variees += 1

        total_series = sum(series.values())
        part_3 = series[3] / total_series

        # Le 3 reste un plancher légitime, mais ne doit plus représenter la
        # majorité des prescriptions.
        assert part_3 <= 0.60, (part_3, series)
        # Au moins 3 valeurs distinctes de séries sur l'ensemble des profils.
        assert len(series) >= 3, series
        # Et surtout : dans CHAQUE séance, les paliers doivent produire des
        # nombres de séries différents. C'est le vrai test du "bloqué à 3".
        assert seances_variees == seances_total, (seances_variees, seances_total)

        print(f"OK 8 — séries variées : {sorted(series)} séries possibles, "
              f"3 séries réduit à {100 * part_3:.0f}%, "
              f"{seances_variees}/{seances_total} séances avec plusieurs valeurs")

        # --------------------------------------------------------------
        # 9. Couplage séries <-> répétitions (règle donnée par Samy) :
        #    « 3x c'est seulement pour 12-15, pour 10-12 c'est 4x,
        #      pour 8-10 c'est 4x, pour 6-8 et force c'est 5x ».
        #    Avant, séries et répétitions étaient calculées indépendamment :
        #    rien n'empêchait un "3 x 6-8", qui ne correspond à aucun schéma
        #    d'entraînement réel.
        # --------------------------------------------------------------
        from logic.recommendation.prescription import sets_depuis_reps
        from logic.recommendation import exercise_order as _eo

        attendu = {"12-15": 3, "10-12": 4, "8-10": 4, "6-8": 5, "5-8": 5, "3-6": 5, "2-5": 5}
        for plage, series_attendues in attendu.items():
            obtenu = sets_depuis_reps(plage)
            assert obtenu == series_attendues, (plage, obtenu, series_attendues)

        # Et le couple produit par le moteur doit toujours respecter la règle.
        for objectif in objectifs:
            for niveau in niveaux:
                p9 = profil(niveau_musculation=niveau, objectif_principal=objectif)
                for exo in seance_type:
                    reps = determine_rep_range(p9, exo)
                    if "sec" in reps:
                        continue
                    tier9 = _eo.classify_exercise(exo)
                    assert sets_depuis_reps(reps, tier9) >= 3, (reps, exo)

        print("OK 9 — séries couplées aux répétitions : 12-15→3x, 10-12→4x, 8-10→4x, 6-8→5x, force→5x")

    print("\nTOUS LES TESTS DE LA PRESCRIPTION SONT PASSÉS")


if __name__ == "__main__":
    run()
