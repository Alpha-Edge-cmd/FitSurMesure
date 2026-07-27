# -*- coding: utf-8 -*-
"""
Tests d'intégration du pipeline complet (phase 11/16) —
logic/recommendation/program_builder.py (orchestration) et
logic/program_repository.py (persistance SQLAlchemy).
"""
import app as appmod
from logic.db import db
from logic.models import Exercise, Program, ProgramExercise, ProgramSession, ProfileSnapshot, User
from logic.program_repository import create_program_from_result, delete_program, get_latest_program
from logic.recommendation.program_builder import build_program

MUSCLES_PPL = ["pecs", "epaules", "triceps", "dos", "biceps", "quadriceps", "ischio", "fessiers", "mollets", "abdos"]


def nouvel_utilisateur(email):
    user = User(email=email)
    db.session.add(user)
    db.session.commit()
    return user


def snapshot(user_id, **kwargs):
    defaults = dict(
        user_id=user_id,
        poids=75.0, taille=178.0, sexe="Homme",
        niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle",
        exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Avec difficulté",
        amplitude_epaule="Avec difficulté", tolerance_technique=3,
        preference_style_charge="Un mix des deux", preference_materiel="Pas de préférence",
        morphologie_declaree={}, blessures={}, autres_sports={}, sommeil="7 à 8h",
        stress="Modéré", variables_json={"duree_seance": "1h - 1h30", "frequence_entrainement": 3},
    )
    defaults.update(kwargs)
    snap = ProfileSnapshot(**defaults)
    db.session.add(snap)
    db.session.commit()
    return snap


def exo(exercise_id, family, muscle, pattern="autre", **kwargs):
    defaults = dict(
        exercise_id=exercise_id, name=exercise_id, family=family, pattern=pattern,
        movement_type="push", equipment=["barre"], muscle_principal=muscle,
        muscles_secondaires=[], unilateral=False, difficulty_level="intermediaire",
        joint_stress={}, technical_complexity=2, stability_demand="modere",
        morphologie_adaptee={}, objectifs_adaptes={"hypertrophie": 2}, score_tension_mecanique=5,
        score_contraction_max=5, potentiel_hypertrophique=5, substitutes=[],
        contre_indications=[], actif=True,
    )
    defaults.update(kwargs)
    return Exercise(**defaults)


def catalogue_complet(prefixe=""):
    """2 exercices par muscle des 10 muscles utilisés par le split PPL (cf.
    logic/exercises_db.SPLITS) -> suffisant pour un scénario "classique"."""
    catalogue = []
    for muscle in MUSCLES_PPL:
        catalogue.append(exo(f"{prefixe}{muscle}_a", f"{muscle}_fam_a", muscle))
        catalogue.append(exo(f"{prefixe}{muscle}_b", f"{muscle}_fam_b", muscle))
    return catalogue


def persister(exercices):
    for ex in exercices:
        db.session.add(ex)
    db.session.commit()


def toutes_les_seances(program):
    return ProgramSession.query.filter_by(program_id=program.id).order_by(ProgramSession.ordre_dans_semaine).all()


def tous_les_exercices(session):
    return ProgramExercise.query.filter_by(session_id=session.id).order_by(ProgramExercise.position_dans_seance).all()


def run():
    with appmod.app.app_context():

        # --------------------------------------------------------------
        # 1) Utilisateur classique : questionnaire -> snapshot -> génération -> DB
        # --------------------------------------------------------------
        user1 = nouvel_utilisateur("test-classique@example.com")
        snap1 = snapshot(user1.id)
        catalogue1 = catalogue_complet("u1_")
        persister(catalogue1)

        resultat1 = build_program(snap1, catalogue1)
        assert resultat1["sessions"], "au moins une séance attendue"
        assert any(s["exercises"] for s in resultat1["sessions"]), "au moins un exercice attendu"

        program1 = create_program_from_result(user1.id, snap1.id, resultat1)
        assert program1.id is not None
        seances1 = toutes_les_seances(program1)
        assert len(seances1) == len(resultat1["sessions"]) and seances1, "séances absentes en base"
        au_moins_un_exercice_en_base = False
        for s in seances1:
            exos = tous_les_exercices(s)
            if exos:
                au_moins_un_exercice_en_base = True
        assert au_moins_un_exercice_en_base, "aucun ProgramExercise trouvé en base"
        print(f"OK 1 — utilisateur classique : Program #{program1.id}, {len(seances1)} séance(s) créées en base")

        # --------------------------------------------------------------
        # 2) Blessure épaule : aucun exercice interdit dans ProgramExercise
        # --------------------------------------------------------------
        user2 = nouvel_utilisateur("test-blessure-epaule@example.com")
        snap2 = snapshot(user2.id, blessures={"Épaule": "Douleur invalidante"})
        catalogue2 = catalogue_complet("u2_") + [
            exo("u2_dev_militaire_risque", "presse_epaules", "epaules", pattern="developpe_militaire",
                joint_stress={"epaule": 3}),
        ]
        persister(catalogue2)

        resultat2 = build_program(snap2, catalogue2)
        program2 = create_program_from_result(user2.id, snap2.id, resultat2)
        ids_persistes = set()
        for s in toutes_les_seances(program2):
            for pe in tous_les_exercices(s):
                ids_persistes.add(pe.exercise_id)
        assert "u2_dev_militaire_risque" not in ids_persistes, "un exercice interdit a été persisté"
        print(f"OK 2 — blessure épaule : aucun exercice interdit parmi les {len(ids_persistes)} persistés")

        # --------------------------------------------------------------
        # 3) Régénération du même programme : aucun doublon créé
        # --------------------------------------------------------------
        user3 = nouvel_utilisateur("test-regeneration@example.com")
        snap3 = snapshot(user3.id)
        catalogue3 = catalogue_complet("u3_")
        persister(catalogue3)

        resultat3_a = build_program(snap3, catalogue3)
        resultat3_b = build_program(snap3, catalogue3)
        assert resultat3_a == resultat3_b, "le moteur doit rester déterministe pour un même profil/catalogue"

        program3_a = create_program_from_result(user3.id, snap3.id, resultat3_a)
        nb_avant = Program.query.filter_by(user_id=user3.id).count()
        program3_b = create_program_from_result(user3.id, snap3.id, resultat3_b)
        nb_apres = Program.query.filter_by(user_id=user3.id).count()
        assert program3_a.id == program3_b.id, "la régénération identique doit retourner le même Program"
        assert nb_avant == nb_apres == 1, f"aucun doublon attendu, obtenu {nb_avant} puis {nb_apres}"
        print(f"OK 3 — régénération identique : aucun doublon (Program #{program3_a.id} réutilisé)")

        # --------------------------------------------------------------
        # 4) Programme extrême avec contraintes fortes : création réussie + warnings
        # --------------------------------------------------------------
        user4 = nouvel_utilisateur("test-extreme@example.com")
        snap4 = snapshot(
            user4.id,
            niveau_musculation="Débutant complet",
            amplitude_squat="Non, pas du tout",
            amplitude_epaule="Non, pas du tout",
            mobilite_generale=1,
            blessures={"Épaule": "Douleur invalidante", "Genoux": "Gêne modérée régulière"},
            preference_materiel="Élastiques uniquement",
        )
        # Catalogue volontairement pauvre : peu d'exercices, certains à risque.
        catalogue4 = [
            exo("u4_squat_libre", "squat_family", "quadriceps", pattern="squat", equipment=["barre"]),
            exo("u4_dev_militaire", "presse_epaules", "epaules", pattern="developpe_militaire",
                joint_stress={"epaule": 3}),
            exo("u4_genou_risque", "presse_family", "quadriceps", pattern="autre", joint_stress={"genou": 3}),
        ]
        persister(catalogue4)

        resultat4 = build_program(snap4, catalogue4)
        assert resultat4["warnings"], "des avertissements sont attendus pour un profil aussi contraint"
        program4 = create_program_from_result(user4.id, snap4.id, resultat4)
        assert program4 is not None and program4.id is not None
        print(f"OK 4 — profil extrême : Program #{program4.id} créé malgré les contraintes, {len(resultat4['warnings'])} avertissement(s)")

        # --------------------------------------------------------------
        # 5) get_latest_program retourne exactement le dernier programme
        # --------------------------------------------------------------
        user5 = nouvel_utilisateur("test-latest@example.com")
        snap5_a = snapshot(user5.id)
        catalogue5 = catalogue_complet("u5_")
        persister(catalogue5)
        resultat5_a = build_program(snap5_a, catalogue5)
        program5_a = create_program_from_result(user5.id, snap5_a.id, resultat5_a)

        snap5_b = snapshot(user5.id, objectif_principal="Perte de gras")  # 2e génération, contenu différent
        resultat5_b = build_program(snap5_b, catalogue5)
        program5_b = create_program_from_result(user5.id, snap5_b.id, resultat5_b)

        assert program5_a.id != program5_b.id, "les deux générations doivent être distinctes (contenu différent)"
        dernier = get_latest_program(user5.id)
        assert dernier is not None and dernier.id == program5_b.id, (
            f"get_latest_program doit retourner le programme le plus récent (#{program5_b.id}), obtenu #{dernier.id if dernier else None}"
        )
        print(f"OK 5 — get_latest_program : Program #{dernier.id} correctement identifié comme le plus récent")

        # --------------------------------------------------------------
        # 6) Suppression : sessions/exercices supprimés, User conservé
        # --------------------------------------------------------------
        user6 = nouvel_utilisateur("test-suppression@example.com")
        snap6 = snapshot(user6.id)
        catalogue6 = catalogue_complet("u6_")
        persister(catalogue6)
        resultat6 = build_program(snap6, catalogue6)
        program6 = create_program_from_result(user6.id, snap6.id, resultat6)
        program6_id = program6.id
        seances6_ids = [s.id for s in toutes_les_seances(program6)]
        exercices6_ids = [pe.id for s in toutes_les_seances(program6) for pe in tous_les_exercices(s)]
        assert seances6_ids and exercices6_ids, "le programme à supprimer doit contenir des données"

        supprime = delete_program(program6_id)
        assert supprime is True

        assert Program.query.get(program6_id) is None
        assert ProgramSession.query.filter(ProgramSession.id.in_(seances6_ids)).count() == 0
        assert ProgramExercise.query.filter(ProgramExercise.id.in_(exercices6_ids)).count() == 0
        assert User.query.get(user6.id) is not None, "le User ne doit jamais être supprimé"
        assert ProfileSnapshot.query.get(snap6.id) is not None, "le ProfileSnapshot ne doit jamais être supprimé"
        print("OK 6 — suppression : sessions/exercices supprimés en cascade, User et ProfileSnapshot conservés")

    print("\nTOUS LES TESTS D'INTÉGRATION DU PIPELINE PROGRAMME SONT PASSÉS")


if __name__ == "__main__":
    run()
