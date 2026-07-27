# -*- coding: utf-8 -*-
"""
Tests de la persistance recommandation et du suivi utilisateur (phase
10/16) — logic/models.py (ExerciseUsageLog, ExerciseFeedback),
logic/recommendation/history.py, logic/recommendation/feedback.py, et leur
branchement dans selector.py (remplace les stubs de la phase 7).
"""
from datetime import datetime, timedelta

import app as appmod
from logic.db import db
from logic.models import Exercise, ExerciseFeedback, ProfileSnapshot, User
from logic.recommendation import fallback, history, selector
from logic.recommendation import feedback as feedback_engine


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


def exo(exercise_id, family, muscle="pecs", pattern=None, **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=exercise_id, family=family, pattern=pattern or family,
        movement_type="push", equipment=["barre"], muscle_principal=muscle,
        muscles_secondaires=[], unilateral=False, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": 2}, score_tension_mecanique=5,
        score_contraction_max=5, potentiel_hypertrophique=5, substitutes=[],
        contre_indications=[], actif=True,
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def nouvel_utilisateur(email):
    user = User(email=email)
    db.session.add(user)
    db.session.commit()
    return user


def persister_exercices(exercices):
    for ex in exercices:
        db.session.add(ex)
    db.session.commit()


def run():
    with appmod.app.app_context():

        # --------------------------------------------------------------
        # 1) Utilisateur ayant utilisé le squat récemment : pénalité de récence
        # --------------------------------------------------------------
        user1 = nouvel_utilisateur("test-recence@example.com")
        catalogue1 = [
            exo("squat_barre", "squat_family", muscle="quadriceps", pattern="autre"),
            exo("presse_cuisses", "presse_family", muscle="quadriceps", pattern="autre"),
        ]
        persister_exercices(catalogue1)
        history.record_exercise_usage(user1.id, "squat_barre", used_at=datetime.utcnow() - timedelta(days=3))

        p1 = profil()
        selection_avec_historique = selector.select_exercises(p1, catalogue1, "quadriceps", 1, user_id=user1.id)
        selection_sans_historique = selector.select_exercises(p1, catalogue1, "quadriceps", 1, user_id=None)
        assert selection_avec_historique[0]["exercise"].exercise_id == "presse_cuisses", (
            "le squat récemment utilisé doit être pénalisé et passer derrière la presse"
        )
        assert selection_sans_historique[0]["exercise"].exercise_id in ("squat_barre", "presse_cuisses")
        print("OK 1 — squat utilisé récemment : pénalité de récence appliquée, presse choisie en premier")

        # --------------------------------------------------------------
        # 2) "deteste" : absent en sélection normale, revient seulement au fallback étape 2
        # --------------------------------------------------------------
        user2 = nouvel_utilisateur("test-deteste@example.com")
        catalogue2 = [
            exo("dc_barre", "presse_pecs", muscle="pecs", pattern="autre"),
        ]
        persister_exercices(catalogue2)
        db.session.add(ExerciseFeedback(user_id=user2.id, exercise_id="dc_barre", feedback_type="deteste"))
        db.session.commit()

        p2 = profil()
        selection_normale = selector.select_exercises(p2, catalogue2, "pecs", 1, user_id=user2.id)
        assert selection_normale == [], "l'exercice détesté ne doit pas apparaître en sélection normale"

        resultat_fallback = fallback.run_fallback_cascade(p2, catalogue2, "pecs", 1, user_id=user2.id)
        ids_fallback = {e["exercise_id"] for e in resultat_fallback["exercises"]}
        assert "dc_barre" in ids_fallback, "l'exercice détesté doit revenir dès l'étape 2 du fallback"
        assert resultat_fallback["fallback_level"] >= 2
        print(f"OK 2 — 'deteste' : absent en sélection normale, réintégré au fallback (niveau {resultat_fallback['fallback_level']})")

        # --------------------------------------------------------------
        # 3) "douleur_gene" sur développé militaire : sévérité épaule augmentée,
        #    autres exercices épaule à risque filtrés
        # --------------------------------------------------------------
        user3 = nouvel_utilisateur("test-douleur-dominante@example.com")
        catalogue3 = [
            exo("dev_militaire", "presse_epaules", muscle="epaules", pattern="developpe_militaire",
                joint_stress={"epaule": 3, "coude": 1}),
            exo("elevation_laterale", "elevation_laterale", muscle="epaules", pattern="autre",
                joint_stress={"epaule": 2}),
            exo("face_pull_leger", "face_pull", muscle="epaules", pattern="autre",
                joint_stress={"epaule": 0}),
        ]
        persister_exercices(catalogue3)
        db.session.add(ExerciseFeedback(user_id=user3.id, exercise_id="dev_militaire", feedback_type="douleur_gene"))
        db.session.commit()

        p3 = profil(blessures={})  # aucune blessure déclarée au questionnaire, seulement le feedback
        selection3 = selector.select_exercises(p3, catalogue3, "epaules", 3, user_id=user3.id)
        ids3 = {c["exercise"].exercise_id for c in selection3}
        assert "dev_militaire" not in ids3, "l'exercice signalé doit rester exclu"
        assert "elevation_laterale" not in ids3, (
            "un autre exercice sollicitant l'épaule (joint_stress=2) doit désormais être filtré "
            "(exclusion généralisée suite à l'élévation de sévérité)"
        )
        assert "face_pull_leger" in ids3, "un exercice sans risque sur l'épaule doit rester disponible"
        print(f"OK 3 — douleur (articulation dominante) : sévérité épaule augmentée, exclusion généralisée ({ids3})")

        # --------------------------------------------------------------
        # 4) Feedback douleur sur exercice multi-articulations SANS dominante :
        #    seul cet exercice est exclu
        # --------------------------------------------------------------
        user4 = nouvel_utilisateur("test-douleur-sans-dominante@example.com")
        catalogue4 = [
            exo("tirage_mixte", "tirage_mixte_fam", muscle="dos", pattern="autre",
                joint_stress={"epaule": 2, "genou": 2}),  # ex-aequo -> pas de dominante claire
            exo("tirage_epaule_seule", "tirage_epaule_fam", muscle="dos", pattern="autre",
                joint_stress={"epaule": 2}),
        ]
        persister_exercices(catalogue4)
        db.session.add(ExerciseFeedback(user_id=user4.id, exercise_id="tirage_mixte", feedback_type="douleur_gene"))
        db.session.commit()

        p4 = profil(blessures={})
        selection4 = selector.select_exercises(p4, catalogue4, "dos", 2, user_id=user4.id)
        ids4 = {c["exercise"].exercise_id for c in selection4}
        assert "tirage_mixte" not in ids4, "l'exercice signalé (sans dominante) doit être exclu"
        assert "tirage_epaule_seule" in ids4, (
            "sans dominante claire, l'exclusion doit rester CIBLÉE : les autres exercices sollicitant "
            "la même articulation ne doivent pas être affectés"
        )
        print(f"OK 4 — douleur (sans dominante) : exclusion ciblée uniquement, aucune généralisation ({ids4})")

        # --------------------------------------------------------------
        # 5) Aucun historique/feedback : comportement identique au moteur actuel
        # --------------------------------------------------------------
        user5 = nouvel_utilisateur("test-nouvel-utilisateur@example.com")
        catalogue5 = [
            exo("dc_barre_5", "presse_pecs", muscle="pecs", pattern="autre"),
            exo("ecarte_5", "ecarte_pecs", muscle="pecs", pattern="autre"),
        ]
        persister_exercices(catalogue5)

        p5 = profil()
        selection_utilisateur_neuf = selector.select_exercises(p5, catalogue5, "pecs", 2, user_id=user5.id)
        selection_sans_user_id = selector.select_exercises(p5, catalogue5, "pecs", 2, user_id=None)
        ids_neuf = [c["exercise"].exercise_id for c in selection_utilisateur_neuf]
        ids_sans = [c["exercise"].exercise_id for c in selection_sans_user_id]
        scores_neuf = [c["score"] for c in selection_utilisateur_neuf]
        scores_sans = [c["score"] for c in selection_sans_user_id]
        assert ids_neuf == ids_sans and scores_neuf == scores_sans, (
            "un utilisateur sans aucun historique/feedback doit obtenir un résultat "
            "strictement identique à un appel sans user_id (aucune régression)"
        )
        print("OK 5 — aucun historique/feedback : comportement strictement identique au moteur actuel")

        # --------------------------------------------------------------
        # 6) Aucun feedback ne peut contourner une exclusion de sécurité
        # --------------------------------------------------------------
        user6 = nouvel_utilisateur("test-securite@example.com")
        catalogue6 = [
            exo("dev_militaire_risque", "presse_epaules", muscle="epaules", pattern="developpe_militaire",
                joint_stress={"epaule": 3}),
        ]
        persister_exercices(catalogue6)
        # L'utilisateur "aime" et trouve "trop facile" un exercice pourtant
        # dangereux pour lui (blessure déjà déclarée au questionnaire) :
        # aucun signal de préférence ne doit pouvoir lever l'exclusion.
        db.session.add(ExerciseFeedback(user_id=user6.id, exercise_id="dev_militaire_risque", feedback_type="aime"))
        db.session.add(ExerciseFeedback(user_id=user6.id, exercise_id="dev_militaire_risque", feedback_type="trop_facile"))
        db.session.commit()

        p6 = profil(blessures={"Épaule": "Douleur invalidante"})
        resultat6 = fallback.run_fallback_cascade(p6, catalogue6, "epaules", 1, user_id=user6.id)
        assert resultat6["exercises"] == [], "un exercice exclu par blessure critique ne doit jamais réapparaître"
        assert resultat6["fallback_level"] == 5
        print("OK 6 — aucun feedback ('aime'/'trop_facile') ne peut contourner une exclusion de sécurité")

    print("\nTOUS LES TESTS DE L'HISTORIQUE ET DU FEEDBACK SONT PASSÉS")


if __name__ == "__main__":
    run()
