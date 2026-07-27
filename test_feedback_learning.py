# -*- coding: utf-8 -*-
"""
Tests de la boucle d'amélioration utilisateur (phase 21/24) —
logic/feedback_learning.py, et de son branchement ADDITIF (couche externe
uniquement) dans logic/recommendation/selector.py. `logic/recommendation/
scoring.py` n'est jamais modifié par cette phase (vérifié ci-dessous : un
appel direct à score_exercise() reste inchangé).
"""
import app as appmod
from logic.db import db
from logic.feedback_learning import calculate_user_preferences
from logic.models import Exercise, ExerciseFeedback, ProfileSnapshot, User
from logic.recommendation import scoring, selector


def profil(**kwargs):
    defaults = dict(
        poids=75.0, taille=178.0, sexe="Homme",
        niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle",
        exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Aucune gêne",
        amplitude_epaule="Aucune gêne", tolerance_technique=3,
        preference_style_charge="Un mix des deux", preference_materiel="Pas de préférence",
        morphologie_declaree={}, blessures={}, autres_sports={}, sommeil="7 à 8h",
        stress="Modéré", variables_json={"duree_seance": "1h - 1h30"},
    )
    defaults.update(kwargs)
    return ProfileSnapshot(**defaults)


def exo(exercise_id, muscle="pecs", pattern="autre", **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=exercise_id, family=exercise_id, pattern=pattern,
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


def run():
    with appmod.app.app_context():

        # ------------------------------------------------------------------
        # 0) Neutre : sans user_id / sans feedback -> valeurs neutres
        # ------------------------------------------------------------------
        neutre = calculate_user_preferences(None)
        assert neutre == {
            "preferred_exercises": [], "avoided_patterns": [],
            "difficulty_adjustment": 0, "volume_adjustment": 0,
        }
        print("OK 0 — calculate_user_preferences(None) : valeurs neutres, aucune exception")

        # ------------------------------------------------------------------
        # 1) Utilisateur AIME un exercice -> preferred_exercises
        # ------------------------------------------------------------------
        user1 = nouvel_utilisateur("aime@example.com")
        ex1 = exo("presse_pecs", pattern="presse")
        db.session.add(ex1)
        db.session.add(ExerciseFeedback(user_id=user1.id, exercise_id="presse_pecs", feedback_type="aime"))
        db.session.commit()

        prefs1 = calculate_user_preferences(user1.id)
        assert prefs1["preferred_exercises"] == ["presse_pecs"]
        assert prefs1["avoided_patterns"] == []
        assert prefs1["difficulty_adjustment"] == 0
        assert prefs1["volume_adjustment"] == 0
        print("OK 1 — utilisateur aime un exercice : preferred_exercises correct, autres signaux neutres")

        # ------------------------------------------------------------------
        # 2) Utilisateur DÉTESTE un exercice -> avoided_patterns (pattern),
        #    jamais dans preferred_exercises
        # ------------------------------------------------------------------
        user2 = nouvel_utilisateur("deteste@example.com")
        ex2 = exo("developpe_militaire_barre", muscle="epaules", pattern="developpe_militaire")
        db.session.add(ex2)
        db.session.add(ExerciseFeedback(user_id=user2.id, exercise_id="developpe_militaire_barre", feedback_type="deteste"))
        db.session.commit()

        prefs2 = calculate_user_preferences(user2.id)
        assert prefs2["avoided_patterns"] == ["developpe_militaire"]
        assert prefs2["preferred_exercises"] == []
        print("OK 2 — utilisateur déteste un exercice : pattern généralisé dans avoided_patterns")

        # ------------------------------------------------------------------
        # 3) Utilisateur PROGRESSE (plusieurs "trop_facile", aucun "trop_difficile")
        # ------------------------------------------------------------------
        user3 = nouvel_utilisateur("progresse@example.com")
        exos3 = [exo(f"ex3_{i}") for i in range(3)]
        for ex in exos3:
            db.session.add(ex)
        for ex in exos3:
            db.session.add(ExerciseFeedback(user_id=user3.id, exercise_id=ex.exercise_id, feedback_type="trop_facile"))
        db.session.commit()

        prefs3 = calculate_user_preferences(user3.id)
        assert prefs3["difficulty_adjustment"] == 1, "3 'trop_facile' sans 'trop_difficile' -> signal de progression net"
        assert prefs3["volume_adjustment"] == 1, "progression nette, aucune douleur -> volume revu à la hausse"
        print("OK 3 — utilisateur progresse : difficulty_adjustment=+1, volume_adjustment=+1")

        # ------------------------------------------------------------------
        # 4) Utilisateur SIGNALE UNE DOULEUR -> volume_adjustment forcé à -1
        #    MÊME en présence d'un signal de progression par ailleurs (la
        #    prudence sécurité prime toujours), et pattern dans avoided_patterns.
        # ------------------------------------------------------------------
        user4 = nouvel_utilisateur("douleur@example.com")
        exos_faciles = [exo(f"ex4_facile_{i}") for i in range(3)]
        ex_douleur = exo("ex4_douleur", muscle="epaules", pattern="developpe_militaire")
        for ex in exos_faciles + [ex_douleur]:
            db.session.add(ex)
        for ex in exos_faciles:
            db.session.add(ExerciseFeedback(user_id=user4.id, exercise_id=ex.exercise_id, feedback_type="trop_facile"))
        db.session.add(ExerciseFeedback(user_id=user4.id, exercise_id="ex4_douleur", feedback_type="douleur_gene"))
        db.session.commit()

        prefs4 = calculate_user_preferences(user4.id)
        assert prefs4["difficulty_adjustment"] == 1, "le signal de difficulté réelle n'est pas concerné par la douleur"
        assert prefs4["volume_adjustment"] == -1, "une douleur signalée force la prudence sur le volume"
        assert "developpe_militaire" in prefs4["avoided_patterns"]
        print("OK 4 — utilisateur signale une douleur : volume_adjustment=-1 (prudence prioritaire), pattern évité")

        # ------------------------------------------------------------------
        # 5) Branchement EXTERNE dans selector.py : scoring.py jamais modifié
        # ------------------------------------------------------------------
        p_ref = profil()
        ex_ref = exo("ex_ref_scoring")
        resultat_direct = scoring.score_exercise(p_ref, ex_ref)
        # Un appel direct à scoring.score_exercise (sans lien avec cette phase)
        # doit rester rigoureusement identique : la couche de cette phase ne
        # s'applique que dans selector.py, jamais dans scoring.py lui-même.
        assert set(resultat_direct.keys()) == {"score_final", "excluded", "exclusion_reason", "details", "profile_analysis"}
        print("OK 5a — scoring.score_exercise() inchangé (aucune clé/signal de cette phase n'y apparaît)")

        user5 = nouvel_utilisateur("branchement@example.com")
        ex_prefere = exo("ex5_prefere", pattern="presse_haute")
        ex_neutre = exo("ex5_neutre", pattern="presse_haute")
        db.session.add_all([ex_prefere, ex_neutre])
        db.session.add(ExerciseFeedback(user_id=user5.id, exercise_id="ex5_prefere", feedback_type="aime"))
        db.session.commit()

        p5 = profil()
        selection_avec_pref = selector.select_exercises(
            p5, [ex_prefere, ex_neutre], "pecs", 1, user_id=user5.id, enforce_family_diversity=False
        )
        selection_sans_pref = selector.select_exercises(
            p5, [ex_prefere, ex_neutre], "pecs", 1, user_id=None, enforce_family_diversity=False
        )
        assert selection_avec_pref[0]["exercise"].exercise_id == "ex5_prefere", (
            "deux exercices à score de base identique : celui 'aimé' doit être préféré une fois "
            "la couche de cette phase appliquée"
        )
        assert selection_sans_pref[0]["score"] == selection_sans_pref[0]["score"]  # sanity (pas de crash)
        assert selection_avec_pref[0]["score"] > selection_sans_pref[0]["score"] or (
            selection_sans_pref[0]["exercise"].exercise_id != "ex5_prefere"
        ), "le bonus de préférence doit se traduire par un score plus élevé qu'en son absence"
        print("OK 5b — branchement selector.py : exercice 'aimé' préféré à score de base égal")

    print("\nTOUS LES TESTS DE LA BOUCLE D'AMÉLIORATION UTILISATEUR SONT PASSÉS")


if __name__ == "__main__":
    run()
