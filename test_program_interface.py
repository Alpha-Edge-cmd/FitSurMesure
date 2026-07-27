# -*- coding: utf-8 -*-
"""
Tests de l'interface programme (phase 23/24) — logic/program_interaction.py
(écriture ExerciseUsageLog/ExerciseFeedback depuis les 4 boutons de
l'interface), et de la page /my-program elle-même (mobile-first : séances,
exercices, séries, répétitions, repos, conseils).

Vérifie explicitement la consigne "Ne jamais toucher au moteur backend" :
aucun des fichiers moteur (logic/recommendation/*, logic/program_builder.py,
logic/program_personalization.py, logic/feedback_learning.py, logic/
program_repository.py, logic/program_validation.py) n'est importé par
logic/program_interaction.py — ce module ne fait qu'écrire des lignes déjà
prévues par le moteur (ExerciseUsageLog/ExerciseFeedback, phase 10),
jamais appeler une règle de scoring/sélection/génération.
"""
import inspect

import app as appmod
from logic import auth, program_interaction, program_service
from logic.db import db
from logic.models import Exercise, ExerciseFeedback, ExerciseUsageLog, User

MUSCLES = ["pecs", "epaules", "triceps", "dos", "biceps", "quadriceps", "ischio", "fessiers", "mollets", "abdos"]


def exo(exercise_id, muscle, **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=f"Exercice {exercise_id}", family=f"{muscle}_fam_{exercise_id}",
        pattern="autre", movement_type="push", equipment=["barre"], muscle_principal=muscle,
        muscles_secondaires=[], unilateral=False, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": 2}, score_tension_mecanique=5,
        score_contraction_max=5, potentiel_hypertrophique=5, substitutes=[],
        contre_indications=[], actif=True, needs_review=False, review_status="approved",
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def persister_catalogue_complet(prefixe):
    catalogue = []
    for muscle in MUSCLES:
        catalogue.append(exo(f"{prefixe}_{muscle}_a", muscle))
        catalogue.append(exo(f"{prefixe}_{muscle}_b", muscle))
    for ex in catalogue:
        db.session.add(ex)
    db.session.commit()
    return catalogue


def questionnaire_complet(**kwargs):
    defaults = dict(
        prenom="Testeur",
        consentement_rgpd=True, date_naissance="1992-04-15", formule="musculation",
        poids=78, taille=180, sexe="Homme",
        niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle",
        objectif_secondaire=None, composition_corporelle="Je ne sais pas",
        frequence_entrainement=3, duree_seance="1h - 1h30", equipement="Salle complète",
        exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Avec difficulté",
        amplitude_epaule="Avec difficulté", tolerance_technique=3,
        preference_style_charge="Un mix des deux", preference_materiel="Pas de préférence",
        blessures=[], severite_blessure={}, autre_sport="Non",
        disponibilite_reelle="Comme prévu", sommeil="7 à 8h", niveau_stress="Modéré",
    )
    defaults.update(kwargs)
    return defaults


# Modules moteur backend explicitement listés par la consigne de cette phase
# ("Ne pas toucher au moteur backend") — aucun ne doit être importé par
# logic/program_interaction.py.
MODULES_MOTEUR_INTERDITS = (
    "logic.recommendation.scoring", "logic.recommendation.selector",
    "logic.recommendation.workout_generator", "logic.recommendation.prescription",
    "logic.recommendation.feedback", "logic.recommendation.program_builder",
    "logic.program_personalization", "logic.feedback_learning",
    "logic.program_repository", "logic.program_validation",
)


def run():
    with appmod.app.app_context():

        # ------------------------------------------------------------------
        # 1) logic/program_interaction.py ne dépend d'aucun module moteur
        #    (garde statique de la consigne "ne pas toucher au moteur backend")
        # ------------------------------------------------------------------
        source = inspect.getsource(program_interaction)
        for module_interdit in MODULES_MOTEUR_INTERDITS:
            assert module_interdit not in source, (
                f"logic/program_interaction.py ne doit jamais dépendre de '{module_interdit}' "
                f"(consigne : ne pas toucher au moteur backend)"
            )
        print("OK 1 — logic/program_interaction.py n'importe aucun module du moteur de recommandation")

        # ------------------------------------------------------------------
        # 2) record_exercise_action : les 4 actions de l'interface
        # ------------------------------------------------------------------
        user1 = User(email="interface-actions@example.com")
        db.session.add(user1)
        persister_catalogue_complet("pi1")
        db.session.commit()
        exercise_id = "pi1_pecs_a"

        log = program_interaction.record_exercise_action(user1.id, exercise_id, "realise")
        assert isinstance(log, ExerciseUsageLog) and log.exercise_id == exercise_id
        assert ExerciseUsageLog.query.filter_by(user_id=user1.id, exercise_id=exercise_id).count() == 1

        for action, feedback_type in (
            ("trop_facile", "trop_facile"), ("trop_difficile", "trop_difficile"), ("douleur", "douleur_gene"),
        ):
            fb = program_interaction.record_exercise_action(user1.id, exercise_id, action)
            assert isinstance(fb, ExerciseFeedback) and fb.feedback_type == feedback_type

        assert ExerciseFeedback.query.filter_by(user_id=user1.id, exercise_id=exercise_id).count() == 3
        print("OK 2 — record_exercise_action : 'realise' -> ExerciseUsageLog, les 3 autres -> ExerciseFeedback correct")

        # ------------------------------------------------------------------
        # 3) Robustesse : action inconnue / exercice inexistant -> ValueError,
        #    jamais une écriture silencieuse
        # ------------------------------------------------------------------
        nb_logs_avant = ExerciseUsageLog.query.count()
        nb_feedbacks_avant = ExerciseFeedback.query.count()
        try:
            program_interaction.record_exercise_action(user1.id, exercise_id, "action-inexistante")
            raise AssertionError("une action inconnue aurait dû lever ValueError")
        except ValueError:
            pass
        try:
            program_interaction.record_exercise_action(user1.id, "exercice-inexistant", "realise")
            raise AssertionError("un exercice inexistant aurait dû lever ValueError")
        except ValueError:
            pass
        assert ExerciseUsageLog.query.count() == nb_logs_avant
        assert ExerciseFeedback.query.count() == nb_feedbacks_avant
        print("OK 3 — action inconnue / exercice inexistant : ValueError, aucune écriture")

        # ------------------------------------------------------------------
        # 4) Interface /my-program : mobile-first, contenu complet
        # ------------------------------------------------------------------
        email4 = "interface-page@example.com"
        catalogue4 = persister_catalogue_complet("pi4")
        data4 = questionnaire_complet(prenom="Fanny")
        program4 = program_service.generate_user_program(email4, data4)
        assert program4.sessions and program4.sessions[0].exercises, "un programme avec au moins un exercice est requis pour ce test"

        client = appmod.app.test_client()
        token = auth.issue_token_for_user(User.query.filter_by(email=email4).first())
        client.post("/login", data={"token": token})

        resp = client.get("/my-program")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        # Mobile-first : la balise viewport doit être présente (condition de base
        # d'une page réellement responsive sur petit écran).
        assert 'name="viewport"' in html and "width=device-width" in html

        premiere_seance = program4.sessions[0]
        premier_exo = premiere_seance.exercises[0]
        assert premiere_seance.nom_seance in html
        assert (premier_exo.exercise.name if premier_exo.exercise else premier_exo.exercise_id) in html
        assert str(premier_exo.series) in html
        assert premier_exo.reps in html
        if premier_exo.rest_time_seconds:
            assert str(premier_exo.rest_time_seconds) in html
        if premier_exo.notes:
            assert premier_exo.notes in html

        for label in ("J'ai réalisé", "Trop facile", "Trop difficile", "Douleur"):
            assert label in html
        assert f'data-exercise-id="{premier_exo.exercise_id}"' in html
        assert 'data-action="realise"' in html
        assert 'data-action="trop_facile"' in html
        assert 'data-action="trop_difficile"' in html
        assert 'data-action="douleur"' in html
        print("OK 4 — /my-program : viewport mobile-first, séances/exercices/séries/répétitions/repos/conseils, 4 boutons présents")

        # ------------------------------------------------------------------
        # 5) Bout en bout via la route : clic bouton -> ligne persistée
        # ------------------------------------------------------------------
        nb_avant = ExerciseUsageLog.query.filter_by(
            user_id=User.query.filter_by(email=email4).first().id, exercise_id=premier_exo.exercise_id
        ).count()
        resp_action = client.post(
            "/my-program/action", json={"exercise_id": premier_exo.exercise_id, "action": "realise"}
        )
        assert resp_action.status_code == 200 and resp_action.get_json() == {"ok": True}
        nb_apres = ExerciseUsageLog.query.filter_by(
            user_id=User.query.filter_by(email=email4).first().id, exercise_id=premier_exo.exercise_id
        ).count()
        assert nb_apres == nb_avant + 1
        print("OK 5 — clic 'J'ai réalisé' via /my-program/action : ExerciseUsageLog bien créé de bout en bout")

    print("\nTOUS LES TESTS DE L'INTERFACE PROGRAMME SONT PASSÉS")


if __name__ == "__main__":
    run()
