# -*- coding: utf-8 -*-
"""
Tests du branchement applicatif (phase 12/16) —
logic/program_service.py, logic/pdf_program_adapter.py, hook post-paiement
(app._essayer_generer_programme_v2) et route GET /my-program.

Phase 22/24 : la section 5 (GET /my-program) a été mise à jour pour refléter
le remplacement de `?email=` par une authentification par session Flask
(cf. logic/auth.py, test_auth.py pour les tests dédiés à ce nouveau module).

Phase 23/24 : la section 5 est mise à jour une seconde fois — /my-program
est désormais une interface HTML mobile-first (plus une réponse JSON), et
POST /my-program/action (cf. logic/program_interaction.py) est testé pour
vérifier la création réelle des lignes ExerciseUsageLog/ExerciseFeedback.
Aucune autre section de ce fichier n'est modifiée.
"""
import io

import app as appmod
from logic import auth, orders, program_service
from logic.db import db
from logic.models import Exercise, Program, User
from logic.pdf_generator import generate_pdf
from logic.pdf_program_adapter import program_to_pdf_data

MUSCLES = ["pecs", "epaules", "triceps", "dos", "biceps", "quadriceps", "ischio", "fessiers", "mollets", "abdos"]


def exo(exercise_id, muscle, **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=f"Exercice {exercise_id}", family=f"{muscle}_fam_{exercise_id}",
        pattern="autre", movement_type="push", equipment=["barre"], muscle_principal=muscle,
        muscles_secondaires=[], unilateral=False, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": 2}, score_tension_mecanique=5,
        score_contraction_max=5, potentiel_hypertrophique=5, substitutes=[],
        contre_indications=[], actif=True,
        # Phase 16/16 : program_service.generate_user_program() charge
        # désormais le catalogue via recommendation.catalog_provider.
        # get_recommendation_catalog(), qui ne retient que les exercices
        # review_status="approved" (sinon repli sur le catalogue legacy,
        # cf. phase 15). Ces fixtures de test représentent un catalogue déjà
        # prêt pour le moteur : elles doivent donc être explicitement
        # "approved", sinon elles seraient invisibles pour generate_user_
        # program() et chaque scénario basculerait silencieusement sur le
        # catalogue legacy réel au lieu du petit catalogue contrôlé voulu ici.
        needs_review=False, review_status="approved",
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


def run():
    with appmod.app.app_context():

        # --------------------------------------------------------------
        # 1) Questionnaire complet : User + Snapshot + Program créés
        # --------------------------------------------------------------
        persister_catalogue_complet("s1")
        email1 = "test-service-classique@example.com"
        data1 = questionnaire_complet(prenom="Alice")
        program1 = program_service.generate_user_program(email1, data1)

        user1 = User.query.filter_by(email=email1).first()
        assert user1 is not None, "User attendu en base"
        assert program1 is not None and program1.id is not None
        assert program1.user_id == user1.id
        assert program1.profile_snapshot_id is not None
        assert len(program1.sessions) > 0, "au moins une séance attendue"
        assert any(len(s.exercises) > 0 for s in program1.sessions), "au moins un exercice attendu"
        print(f"OK 1 — questionnaire complet : User #{user1.id}, Snapshot #{program1.profile_snapshot_id}, Program #{program1.id}")

        # --------------------------------------------------------------
        # 2) Utilisateur existant : aucun doublon User
        # --------------------------------------------------------------
        data1_bis = questionnaire_complet(prenom="Alice", objectif_principal="Perte de gras")
        program1_bis = program_service.generate_user_program(email1, data1_bis)
        nb_users_email1 = User.query.filter_by(email=email1).count()
        assert nb_users_email1 == 1, f"un seul User attendu pour {email1}, obtenu {nb_users_email1}"
        assert program1_bis.id != program1.id, "un profil différent doit donner un nouveau Program"
        print(f"OK 2 — utilisateur existant : toujours 1 seul User (#{user1.id}), 2e génération {program1_bis.id} distincte")

        # --------------------------------------------------------------
        # 3) Paiement valide : programme créé automatiquement
        # --------------------------------------------------------------
        persister_catalogue_complet("s3")
        email3 = "test-paiement-valide@example.com"
        data3 = questionnaire_complet(prenom="Bob", email=email3)
        order_id3 = orders.create_order(data3, "musculation")
        orders.mark_paid(order_id3)
        order3 = orders.get_order(order_id3)

        nb_programs_avant = Program.query.join(User).filter(User.email == email3).count()
        assert nb_programs_avant == 0
        appmod._essayer_generer_programme_v2(order_id3, order3)
        nb_programs_apres = Program.query.join(User).filter(User.email == email3).count()
        assert nb_programs_apres == 1, "le paiement validé doit déclencher la génération automatique du programme"
        print(f"OK 3 — paiement valide (order {order_id3}) : programme créé automatiquement")

        # --------------------------------------------------------------
        # 4) Email absent : paiement non bloqué, programme différé possible
        # --------------------------------------------------------------
        data4 = questionnaire_complet(prenom="Charlie")  # pas de champ "email"
        order_id4 = orders.create_order(data4, "musculation")
        orders.mark_paid(order_id4)
        order4 = orders.get_order(order_id4)
        assert order4["paid"] is True, "le paiement doit rester validé indépendamment de la génération du programme"

        # Ne doit jamais lever d'exception, même sans email résolvable.
        appmod._essayer_generer_programme_v2(order_id4, order4)
        order4_apres = orders.get_order(order_id4)
        assert order4_apres["paid"] is True, "la commande doit rester payée même si le programme n'a pas pu être généré"

        # Génération différée : possible dès qu'un email est connu par un autre moyen.
        email4_differe = "test-email-differe@example.com"
        program4 = program_service.generate_user_program(email4_differe, order4["data"])
        assert program4 is not None and program4.id is not None
        print("OK 4 — email absent : paiement non bloqué, programme généré plus tard avec succès")

        # --------------------------------------------------------------
        # 5) GET /my-program (phase 22/24 : session Flask, plus ?email= ;
        #    phase 23/24 : interface HTML, plus une réponse JSON brute) et
        #    POST /my-program/action (phase 23/24, cf. logic/program_
        #    interaction.py) : retourne/alimente le bon programme.
        # --------------------------------------------------------------
        client = appmod.app.test_client()

        # Sans session active : redirection vers /login (page HTML protégée
        # par _login_required, comme /mon-compte), jamais l'ancien comportement
        # par email et jamais un my-program public.
        resp_anonyme = client.get("/my-program", follow_redirects=False)
        assert resp_anonyme.status_code == 302 and "/login" in resp_anonyme.headers["Location"]
        resp_ancien_param = client.get(f"/my-program?email={email1}", follow_redirects=False)
        assert resp_ancien_param.status_code == 302, "le paramètre ?email= ne doit plus jamais authentifier personne"
        assert client.post("/my-program/action", json={"exercise_id": "x", "action": "realise"}).status_code == 401

        # Jeton invalide : /login refuse, aucune session ouverte.
        resp_login_invalide = client.post("/login", data={"token": "ceci-nest-pas-un-jeton-valide"})
        assert resp_login_invalide.status_code == 200  # ré-affiche le formulaire avec une erreur
        assert client.get("/my-program", follow_redirects=False).status_code == 302

        # Jeton valide (émis directement via logic/auth.py, comme le fait
        # app.payment_success en production) : connexion puis accès au programme.
        with appmod.app.app_context():
            token = auth.issue_token_for_user(user1)
        resp_login = client.post("/login", data={"token": token}, follow_redirects=False)
        assert resp_login.status_code == 302 and resp_login.headers["Location"].endswith("/mon-compte")

        resp = client.get("/my-program")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        html = resp.get_data(as_text=True)
        premiere_seance = program1_bis.sessions[0]
        assert premiere_seance.nom_seance in html, "le nom de la séance doit apparaître dans l'interface"
        assert "J'ai réalisé" in html and "Trop facile" in html and "Trop difficile" in html and "Douleur" in html, (
            "les 4 boutons de feedback doivent être présents"
        )
        premier_exo_id = None
        if premiere_seance.exercises:
            premier_exo_id = premiere_seance.exercises[0].exercise_id
            assert premier_exo_id in html, "l'exercise_id doit être porté par les boutons d'action"

        # POST /my-program/action : action inconnue -> 400, action valide -> 200
        # et persistance réelle dans ExerciseUsageLog/ExerciseFeedback (phase 10,
        # inchangé) — aucune règle de scoring impliquée ici (phase 23/24).
        if premier_exo_id:
            resp_action_ko = client.post("/my-program/action", json={"exercise_id": premier_exo_id, "action": "nawak"})
            assert resp_action_ko.status_code == 400

            from logic.models import ExerciseFeedback, ExerciseUsageLog

            nb_usage_avant = ExerciseUsageLog.query.filter_by(user_id=user1.id, exercise_id=premier_exo_id).count()
            resp_realise = client.post("/my-program/action", json={"exercise_id": premier_exo_id, "action": "realise"})
            assert resp_realise.status_code == 200 and resp_realise.get_json()["ok"] is True
            nb_usage_apres = ExerciseUsageLog.query.filter_by(user_id=user1.id, exercise_id=premier_exo_id).count()
            assert nb_usage_apres == nb_usage_avant + 1, "'J'ai réalisé' doit créer une ligne ExerciseUsageLog"

            for bouton, feedback_type in (("trop_facile", "trop_facile"), ("trop_difficile", "trop_difficile"), ("douleur", "douleur_gene")):
                nb_avant = ExerciseFeedback.query.filter_by(
                    user_id=user1.id, exercise_id=premier_exo_id, feedback_type=feedback_type
                ).count()
                resp_fb = client.post("/my-program/action", json={"exercise_id": premier_exo_id, "action": bouton})
                assert resp_fb.status_code == 200
                nb_apres = ExerciseFeedback.query.filter_by(
                    user_id=user1.id, exercise_id=premier_exo_id, feedback_type=feedback_type
                ).count()
                assert nb_apres == nb_avant + 1, f"le bouton '{bouton}' doit créer un ExerciseFeedback('{feedback_type}')"

        # Espace personnel accessible une fois connecté.
        resp_compte = client.get("/mon-compte")
        assert resp_compte.status_code == 200
        assert "Programme actuel" in resp_compte.get_data(as_text=True)

        # Déconnexion : /my-program, /my-program/action et /mon-compte
        # redeviennent inaccessibles.
        client.get("/logout")
        assert client.get("/my-program", follow_redirects=False).status_code == 302
        assert client.post("/my-program/action", json={"exercise_id": "x", "action": "realise"}).status_code == 401
        assert client.get("/mon-compte", follow_redirects=False).status_code == 302
        print(f"OK 5 — /my-program (interface HTML) + /my-program/action (feedback) : session Flask appliquée, ExerciseUsageLog/ExerciseFeedback bien alimentés")

        # --------------------------------------------------------------
        # 6) PDF adapter : structure compatible avec le générateur PDF existant
        # --------------------------------------------------------------
        adapted = program_to_pdf_data(program1_bis)
        assert set(adapted.keys()) >= {
            "split_label", "warnings", "programme", "objectif_note", "niveau_note",
            "equipement", "prioritaires_labels", "morpho_labels",
        }
        assert isinstance(adapted["programme"], list) and adapted["programme"]
        premier_jour = adapted["programme"][0]
        assert set(premier_jour.keys()) >= {"nom", "muscles", "duree_estimee_min", "bonus_poids_du_corps"}
        if premier_jour["muscles"]:
            bloc = premier_jour["muscles"][0]
            assert set(bloc.keys()) == {"muscle", "exercices"}
            if bloc["exercices"]:
                assert set(bloc["exercices"][0].keys()) == {"nom", "series", "reps"}

        # Preuve d'intégration réelle : le générateur PDF existant doit fonctionner
        # tel quel avec les données adaptées, aux côtés d'un profil/nutrition/
        # cardio/lifestyle légitimes construits par le moteur legacy (_build_everything).
        error, profile, nutrition, _programme_legacy, cardio, lifestyle = appmod._build_everything(data1)
        assert error is None
        buffer = io.BytesIO()
        generate_pdf(buffer, profile, nutrition, adapted, cardio, lifestyle)
        pdf_bytes = buffer.getvalue()
        assert pdf_bytes.startswith(b"%PDF"), "le PDF généré avec les données adaptées doit être un PDF valide"
        print(f"OK 6 — adaptateur PDF : structure compatible, PDF généré avec succès ({len(pdf_bytes)} octets)")

        # --------------------------------------------------------------
        # 7) Profil blessure critique : sauvegardé sans exercice interdit
        # --------------------------------------------------------------
        persister_catalogue_complet("s7")
        db.session.add(exo("s7_epaule_risque", "epaules", pattern="developpe_militaire",
                            joint_stress={"epaule": 3}))
        db.session.commit()

        email7 = "test-blessure-critique@example.com"
        data7 = questionnaire_complet(
            prenom="Dana", blessures=["Épaule"], severite_blessure={"Épaule": "Douleur invalidante"},
        )
        program7 = program_service.generate_user_program(email7, data7)
        ids_persistes7 = {
            pe.exercise_id for s in program7.sessions for pe in s.exercises
        }
        assert "s7_epaule_risque" not in ids_persistes7, "un exercice interdit a été sauvegardé"
        print(f"OK 7 — profil blessure critique : programme sauvegardé ({len(ids_persistes7)} exercices), aucun interdit")

    print("\nTOUS LES TESTS DU BRANCHEMENT APPLICATIF SONT PASSÉS")


if __name__ == "__main__":
    run()
