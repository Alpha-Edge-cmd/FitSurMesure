# -*- coding: utf-8 -*-
"""
Tests de l'authentification utilisateur (phase 22/24) —
logic/auth.py (jeton + session Flask), logic/models.UserAccessToken
(migration douce : nouvelle table, aucune colonne ajoutée à `users`),
routes /login, /logout, /mon-compte, /my-program (remplace ?email=), et
branchement additif dans /payment-success. Ne jamais casser Stripe/orders.py
(vérifié explicitement ci-dessous).

Phase 23/24 : /my-program est devenue une interface HTML (plus une réponse
JSON) — la section 5 est mise à jour en conséquence. Les tests dédiés à
l'interface elle-même (boutons de feedback, logic/program_interaction.py)
sont dans test_program_interface.py.
"""
import app as appmod
from logic import auth, orders
from logic.db import db
from logic.models import Exercise, User, UserAccessToken

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


def run():
    with appmod.app.app_context():

        # ------------------------------------------------------------------
        # 0) Migration douce : la nouvelle table existe, aucune donnée
        #    existante (Users déjà créés par les phases précédentes) n'est
        #    perturbée — simple lecture, aucune exception.
        # ------------------------------------------------------------------
        assert UserAccessToken.query.count() >= 0
        print("OK 0 — migration douce : nouvelle table user_access_tokens disponible, aucune régression")

        # ------------------------------------------------------------------
        # 1) issue_token_for_user / verify_token
        # ------------------------------------------------------------------
        user1 = User(email="auth-token@example.com")
        db.session.add(user1)
        db.session.commit()

        token_a = auth.issue_token_for_user(user1)
        assert token_a and isinstance(token_a, str) and len(token_a) > 20
        assert UserAccessToken.query.filter_by(user_id=user1.id).count() == 1, "au plus un jeton par utilisateur"

        retrouve = auth.verify_token(token_a)
        assert retrouve is not None and retrouve.id == user1.id
        assert auth.verify_token("jeton-invente-au-hasard") is None
        assert auth.verify_token("") is None
        assert auth.verify_token(None) is None
        print("OK 1 — issue_token_for_user/verify_token : jeton valide reconnu, jeton invalide/vide refusé")

        # ------------------------------------------------------------------
        # 2) Régénération : l'ancien jeton cesse immédiatement de fonctionner
        # ------------------------------------------------------------------
        token_b = auth.issue_token_for_user(user1)
        assert token_b != token_a, "un nouveau jeton doit être généré (jamais le même deux fois)"
        assert auth.verify_token(token_a) is None, "l'ancien jeton doit être invalidé par la régénération"
        assert auth.verify_token(token_b) is not None
        assert UserAccessToken.query.filter_by(user_id=user1.id).count() == 1, "toujours une seule ligne, pas un doublon"
        print("OK 2 — régénération : ancien jeton immédiatement invalidé, une seule ligne conservée")

        # ------------------------------------------------------------------
        # 3) Aucun jeton stocké en clair en base
        # ------------------------------------------------------------------
        ligne = UserAccessToken.query.filter_by(user_id=user1.id).first()
        assert ligne.token_hash != token_b, "le jeton brut ne doit jamais être stocké tel quel"
        assert len(ligne.token_hash) == 64, "empreinte SHA-256 attendue (64 caractères hexadécimaux)"
        print("OK 3 — aucun jeton en clair en base (seule l'empreinte SHA-256 est stockée)")

        # ------------------------------------------------------------------
        # 4) login / logout / current_user (session Flask)
        # ------------------------------------------------------------------
        with appmod.app.test_request_context("/"):
            assert auth.current_user() is None
            auth.login(user1)
            assert auth.current_user() is not None and auth.current_user().id == user1.id
            auth.logout()
            assert auth.current_user() is None
        print("OK 4 — login/logout/current_user : session Flask correctement gérée")

        # ------------------------------------------------------------------
        # 5) Routes /login, /logout, /my-program (interface HTML, phase
        #    23/24), /mon-compte (session Flask, plus de ?email=)
        # ------------------------------------------------------------------
        client = appmod.app.test_client()

        resp_my_program_anonyme = client.get("/my-program", follow_redirects=False)
        assert resp_my_program_anonyme.status_code == 302 and "/login" in resp_my_program_anonyme.headers["Location"]
        resp_my_program_email = client.get("/my-program?email=auth-token@example.com", follow_redirects=False)
        assert resp_my_program_email.status_code == 302, (
            "le paramètre ?email= ne doit plus jamais authentifier personne (remplacé par la session)"
        )
        assert client.post("/my-program/action", json={"exercise_id": "x", "action": "realise"}).status_code == 401
        resp_compte_anonyme = client.get("/mon-compte", follow_redirects=False)
        assert resp_compte_anonyme.status_code == 302
        assert "/login" in resp_compte_anonyme.headers["Location"]

        resp_login_ko = client.post("/login", data={"token": "faux-jeton"})
        assert resp_login_ko.status_code == 200
        assert "invalide" in resp_login_ko.get_data(as_text=True).lower()

        token_c = auth.issue_token_for_user(user1)
        resp_login_ok = client.post("/login", data={"token": token_c}, follow_redirects=False)
        assert resp_login_ok.status_code == 302 and resp_login_ok.headers["Location"].endswith("/mon-compte")

        resp_compte = client.get("/mon-compte")
        assert resp_compte.status_code == 200
        assert "auth-token@example.com" in resp_compte.get_data(as_text=True)

        # Aucun programme généré pour cet utilisateur -> page servie quand même
        # (état vide affiché, jamais une erreur), authentification réussie.
        resp_prog = client.get("/my-program")
        assert resp_prog.status_code == 200
        assert "Aucun programme" in resp_prog.get_data(as_text=True)

        client.get("/logout")
        assert client.get("/my-program", follow_redirects=False).status_code == 302
        assert client.post("/my-program/action", json={"exercise_id": "x", "action": "realise"}).status_code == 401
        assert client.get("/mon-compte", follow_redirects=False).status_code == 302
        print("OK 5 — /login, /logout, /my-program (interface), /my-program/action, /mon-compte : session Flask correctement appliquée partout")

        # ------------------------------------------------------------------
        # 6) Branchement dans /payment-success : jeton émis + connexion
        #    automatique, SANS jamais bloquer la confirmation de paiement.
        # ------------------------------------------------------------------
        persister_catalogue_complet("auth6")
        email6 = "auth-payment-success@example.com"
        data6 = questionnaire_complet(prenom="Eve", email=email6)
        order_id6 = orders.create_order(data6, "musculation")
        orders.mark_paid(order_id6)

        client6 = appmod.app.test_client()
        resp6 = client6.get(f"/payment-success?order_id={order_id6}")
        assert resp6.status_code == 200
        html6 = resp6.get_data(as_text=True)
        assert "Ton espace personnel" in html6, "le jeton d'accès doit être affiché sur la page de succès"

        user6 = User.query.filter_by(email=email6).first()
        assert user6 is not None, "le User doit avoir été créé/résolu à partir de l'email de la commande"
        assert UserAccessToken.query.filter_by(user_id=user6.id).count() == 1

        # Connecté automatiquement (même client, même session) : accès direct.
        resp_compte6 = client6.get("/mon-compte")
        assert resp_compte6.status_code == 200
        assert email6 in resp_compte6.get_data(as_text=True)
        print(f"OK 6 — /payment-success : jeton émis + connexion automatique pour {email6}, paiement toujours confirmé")

        # ------------------------------------------------------------------
        # 7) Ne jamais casser Stripe/orders.py : même sans email résolvable,
        #    /payment-success reste fonctionnel et la commande reste payée.
        # ------------------------------------------------------------------
        data7 = questionnaire_complet(prenom="SansEmail")  # pas de champ "email"
        order_id7 = orders.create_order(data7, "musculation")
        orders.mark_paid(order_id7)

        client7 = appmod.app.test_client()
        resp7 = client7.get(f"/payment-success?order_id={order_id7}")
        assert resp7.status_code == 200, "la page de succès doit rester accessible même sans email résolvable"
        assert "Ton espace personnel" not in resp7.get_data(as_text=True), (
            "aucun jeton ne doit être affiché quand aucun email n'a pu être résolu"
        )
        order7_apres = orders.get_order(order_id7)
        assert order7_apres["paid"] is True, "le paiement doit rester confirmé quoi qu'il arrive à l'authentification"
        print("OK 7 — /payment-success sans email résolvable : page toujours servie, paiement toujours confirmé")

    print("\nTOUS LES TESTS D'AUTHENTIFICATION UTILISATEUR SONT PASSÉS")


if __name__ == "__main__":
    run()
