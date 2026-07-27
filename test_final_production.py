# -*- coding: utf-8 -*-
"""
Audit final production (phase 16/16) — bascule du moteur vers le catalogue
sécurisé V2 (logic/program_service.py + recommendation/catalog_provider.py),
logic/program_validation.py, logic/catalog_monitoring.py.

Prompt final (hors 24 phases) : data/exercise_enrichment.json contient
désormais le catalogue v3 (365 exercices, liste exacte fournie par Samy, cf.
scripts/build_catalog_v3_samy.py) — les comptes et exercise_id de ce fichier
sont mis à jour en conséquence. Le repli legacy (catalogue_fallback, ligne
~82) reste volontairement à 111 : il reconstruit l'ANCIEN catalogue depuis
logic/exercises_db.py, indépendamment de ce fichier JSON (cf. logic/
recommendation/catalog_provider.py, jamais modifié).

Depuis le correctif "catalogue jamais chargé en prod" (logic/db.init_db
importe et auto-approuve désormais le catalogue à chaque démarrage de
l'app), la table Exercise n'est plus vide après un simple `import app` :
ce test la vide explicitement au départ pour retrouver le scénario "zéro
approuvé" qu'il vérifie en premier."""
import io

import app as appmod
import logic.program_service as program_service_module
from logic import orders, program_service
from logic.catalog_monitoring import catalog_health_report
from logic.db import db
from logic.exercise_catalog_import import import_enriched_catalog
from logic.exercise_catalog_service import get_catalog_status
from logic.exercise_review import approve_exercise, reject_exercise
from logic.models import Exercise, Program
from logic.pdf_generator import generate_pdf
from logic.pdf_program_adapter import program_to_pdf_data
from logic.program_validation import ProgramValidationError, validate_generated_program
from logic.recommendation.catalog_provider import get_recommendation_catalog

MUSCLES = ["pecs", "epaules", "triceps", "dos", "biceps", "quadriceps", "ischio", "fessiers", "mollets", "abdos"]


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


def _ids_utilises(program):
    return {pe.exercise_id for s in program.sessions for pe in s.exercises}


def run():
    with appmod.app.app_context():
        # `import app` (logic.db.init_db) a déjà importé/auto-approuvé le
        # catalogue (correctif "catalogue jamais chargé en prod") : on
        # repart d'une table vide pour tester le scénario "zéro approuvé".
        Exercise.query.delete()
        db.session.commit()

        resultat_import = import_enriched_catalog()
        assert resultat_import["errors"] == []
        assert Exercise.query.count() == 365

        # --------------------------------------------------------------
        # 2) Catalogue V2 vide (aucun approuvé) -> fallback legacy
        #    (fait AVANT toute approbation, pour tester le cas "zéro approuvé")
        #
        # Prompt final (hors 24 phases) : le repli legacy (get_recommendation_
        # catalog() sans aucun approuvé) continue de renvoyer les 111 anciens
        # exercice_ids (reconstruits à la volée depuis logic/exercises_db.py,
        # cf. catalog_provider.py, jamais modifié). MAIS la table Exercise ne
        # contient plus ces anciens exercise_id depuis le remplacement du
        # catalogue (365 exercices, nouveaux exercise_id) : validate_generated_
        # program() (phase 16, "protège la contrainte FK avant écriture") rejette
        # donc désormais correctement tout programme basé sur ce repli, faute
        # d'exercice existant en base. C'est le comportement voulu : le moteur
        # ne doit plus jamais exposer l'ancien catalogue, et cette passe de
        # sécurité l'empêche activement plutôt que de le laisser passer en
        # silence. En production réelle ce cas ne se produit jamais : la
        # migration (scripts/migrate_professional_catalog.py) approuve
        # automatiquement le nouveau catalogue, donc "0 approuvé" n'arrive
        # jamais après la bascule.
        # --------------------------------------------------------------
        assert get_catalog_status()["approved"] == 0
        catalogue_fallback = get_recommendation_catalog()
        assert len(catalogue_fallback) == 111, "repli attendu sur l'intégralité du catalogue legacy"

        email_fallback = "final-fallback@example.com"
        try:
            program_service.generate_user_program(
                email_fallback, questionnaire_complet(prenom="Fallback", email=email_fallback)
            )
            raise AssertionError(
                "generate_user_program() aurait dû lever ProgramValidationError : le repli legacy "
                "référence des exercise_id qui n'existent plus dans la table Exercise (nouveau catalogue)"
            )
        except ProgramValidationError:
            pass
        print("OK 2 — catalogue V2 sans approuvé : repli legacy renvoie l'ancien catalogue (111), "
              "mais la validation FK bloque désormais correctement la sauvegarde (exercise_id inexistants "
              "dans le nouveau catalogue) — aucun programme basé sur l'ancien catalogue n'est jamais sauvegardé")

        # --------------------------------------------------------------
        # 1) Catalogue V2 avec approved -> programme généré uniquement avec eux
        # --------------------------------------------------------------
        approuves_principal = {}
        for muscle in MUSCLES:
            candidat = Exercise.query.filter_by(muscle_principal=muscle).order_by(Exercise.exercise_id).first()
            approve_exercise(candidat.exercise_id, reviewer="qa")
            approuves_principal[muscle] = candidat.exercise_id

        catalogue_moteur = get_recommendation_catalog()
        assert {e.exercise_id for e in catalogue_moteur} == set(approuves_principal.values()), (
            "seul le sous-ensemble approuvé doit être exposé au moteur"
        )

        email1 = "final-approved-only@example.com"
        program1 = program_service.generate_user_program(
            email1, questionnaire_complet(prenom="Approved", email=email1)
        )
        ids1 = _ids_utilises(program1)
        assert ids1, "au moins un exercice attendu"
        assert ids1 <= set(approuves_principal.values()), (
            f"exercice(s) hors du sous-ensemble approuvé utilisé(s) : {ids1 - set(approuves_principal.values())}"
        )
        print(f"OK 1 — catalogue V2 avec {len(approuves_principal)} approuvés : Program #{program1.id} n'utilise qu'eux ({ids1})")

        # --------------------------------------------------------------
        # 3) Exercice rejected actif=True -> jamais utilisé
        # --------------------------------------------------------------
        pecs_b = (
            Exercise.query.filter_by(muscle_principal="pecs")
            .filter(Exercise.exercise_id != approuves_principal["pecs"])
            .order_by(Exercise.exercise_id)
            .first()
        )
        approve_exercise(pecs_b.exercise_id, reviewer="qa")  # d'abord approuvé...
        rejete = reject_exercise(pecs_b.exercise_id, reason="Test phase 16 : jamais utilisé malgré actif=True", reviewer="qa")
        assert rejete.actif is True, "aucune désactivation automatique"

        catalogue_moteur3 = get_recommendation_catalog()
        assert pecs_b.exercise_id not in {e.exercise_id for e in catalogue_moteur3}

        email3 = "final-rejected-excluded@example.com"
        program3 = program_service.generate_user_program(
            email3, questionnaire_complet(prenom="Rejected", email=email3)
        )
        ids3 = _ids_utilises(program3)
        assert pecs_b.exercise_id not in ids3, "un exercice rejeté a été utilisé"
        print(f"OK 3 — exercice rejeté '{pecs_b.exercise_id}' (actif=True) jamais utilisé (Program #{program3.id})")

        # --------------------------------------------------------------
        # 4) Programme généré avec blessure critique -> aucun exercice interdit
        # --------------------------------------------------------------
        approve_exercise("developpe_epaules_assis_aux_halteres_epaules", reviewer="qa")  # dangereux (joint_stress epaule=2)
        approve_exercise("elevations_frontales_aux_halteres_alternees_simultanees_epaules", reviewer="qa")  # sûr (aucun joint_stress)

        email4 = "final-blessure-critique@example.com"
        data4 = questionnaire_complet(
            prenom="Blessure", email=email4, blessures=["Épaule"], severite_blessure={"Épaule": "Douleur invalidante"},
        )
        program4 = program_service.generate_user_program(email4, data4)
        ids4 = _ids_utilises(program4)
        assert "developpe_epaules_assis_aux_halteres_epaules" not in ids4, "un exercice dangereux pour l'épaule a été sauvegardé"
        print(f"OK 4 — profil blessure critique : Program #{program4.id} ({len(ids4)} exercices), aucun exercice interdit")

        # --------------------------------------------------------------
        # 5) Programme invalide simulé -> sauvegarde bloquée
        # --------------------------------------------------------------
        # validate_generated_program(), isolément : un résultat référençant un
        # exercice rejeté doit être détecté invalide, sans jamais rien modifier.
        resultat_corrompu = {
            "program_name": "Programme corrompu (test)",
            "objective": "Test",
            "sessions": [{
                "name": "Séance corrompue", "duration": "1h",
                "exercises": [{
                    "exercise_id": pecs_b.exercise_id, "series": 3, "repetitions": "8-10",
                    "rest_time": 90, "intensity": "modérée", "notes": None,
                }],
            }],
            "warnings": [],
        }
        rapport5 = validate_generated_program(resultat_corrompu)
        assert rapport5["valid"] is False
        assert any("rejeté" in e for e in rapport5["errors"])

        # De bout en bout, via generate_user_program() : un build_program() qui
        # renverrait ce résultat corrompu ne doit jamais aboutir à un Program
        # sauvegardé (remplacement temporaire, restauré dans le `finally`).
        build_program_original = program_service_module.build_program

        def _build_program_corrompu(*_args, **_kwargs):
            return resultat_corrompu

        program_service_module.build_program = _build_program_corrompu
        nb_programs_avant = Program.query.count()
        email5 = "final-programme-invalide@example.com"
        try:
            try:
                program_service.generate_user_program(email5, questionnaire_complet(prenom="Invalide", email=email5))
                raise AssertionError("generate_user_program() aurait dû lever ProgramValidationError")
            except ProgramValidationError:
                pass
        finally:
            program_service_module.build_program = build_program_original

        nb_programs_apres = Program.query.count()
        assert nb_programs_apres == nb_programs_avant, "aucun programme corrompu ne doit être sauvegardé"
        print("OK 5 — programme invalide simulé : validation refusée, ProgramValidationError levée, aucune sauvegarde")

        # --------------------------------------------------------------
        # 6) Rapport monitoring : compteurs cohérents
        # --------------------------------------------------------------
        rapport6 = catalog_health_report()
        assert rapport6["total"] == 365
        assert rapport6["approved"] == Exercise.query.filter_by(review_status="approved").count()
        assert rapport6["pending"] == Exercise.query.filter_by(review_status="pending").count()
        assert rapport6["rejected"] == Exercise.query.filter_by(review_status="rejected").count() == 1
        assert rapport6["approved"] + rapport6["pending"] + rapport6["rejected"] == rapport6["total"]
        assert rapport6["active_without_review"] == Exercise.query.filter_by(actif=True, needs_review=True).count()
        assert isinstance(rapport6["missing_fields"], int) and rapport6["missing_fields"] >= 0
        assert isinstance(rapport6["quality_warnings"], int) and rapport6["quality_warnings"] >= 0
        print(f"OK 6 — monitoring catalogue cohérent : {rapport6}")

        # --------------------------------------------------------------
        # 7) Régression complète : anciens comportements inchangés
        # --------------------------------------------------------------
        email7 = "final-regression@example.com"
        data7 = questionnaire_complet(prenom="Regression", email=email7)
        order_id7 = orders.create_order(data7, "musculation")
        orders.mark_paid(order_id7)
        order7 = orders.get_order(order_id7)
        assert order7["paid"] is True

        appmod._essayer_generer_programme_v2(order_id7, order7)  # ne doit jamais lever d'exception
        order7_apres = orders.get_order(order_id7)
        assert order7_apres["paid"] is True, "le paiement doit rester indépendant de la génération/validation du programme"

        programme7 = program_service.get_user_current_program(email7)
        assert programme7 is not None, "le programme doit avoir été généré automatiquement après paiement"

        adapted7 = program_to_pdf_data(programme7)
        assert isinstance(adapted7["programme"], list) and adapted7["programme"]

        error, profile, nutrition, _programme_legacy, cardio, lifestyle = appmod._build_everything(data7)
        assert error is None
        buffer = io.BytesIO()
        generate_pdf(buffer, profile, nutrition, adapted7, cardio, lifestyle)
        pdf_bytes = buffer.getvalue()
        assert pdf_bytes.startswith(b"%PDF"), "le PDF doit toujours se générer normalement après la bascule catalogue"
        print(f"OK 7 — régression : paiement Stripe/orders inchangé, programme + PDF générés normalement ({len(pdf_bytes)} octets)")

    print("\nTOUS LES TESTS DE L'AUDIT FINAL PRODUCTION SONT PASSÉS")


if __name__ == "__main__":
    run()
