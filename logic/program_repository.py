# -*- coding: utf-8 -*-
"""
Conversion de la sortie du moteur de recommandation (phase 11/16,
`logic/recommendation/program_builder.build_program`) en modèles SQLAlchemy
(`Program` / `ProgramSession` / `ProgramExercise`, phase 1/16). Ne contient
aucune règle métier de recommandation : ce module ne fait que persister une
structure déjà décidée, jamais de scoring/filtrage/sélection.

Ne modifie ni Stripe, ni `logic/orders.py`, ni `logic/promo_codes.py` : la
génération legacy (JSON à plat) continue de fonctionner en parallèle, sans
changement, exactement comme depuis la phase 1.
"""
import hashlib
import json

from logic.db import db
from logic.models import Exercise, Program, ProgramExercise, ProgramSession


def _compute_generation_id(profile_snapshot_id, result):
    """Hash de contenu déterministe (pas un UUID aléatoire) : une
    régénération strictement identique du même profil produit le même
    `generation_id`, ce qui permet de détecter et d'éviter un doublon sans
    exiger de clé d'idempotence explicite de l'appelant (cf. moteur
    déterministe depuis la correction de la tâche #79 : même profil + même
    catalogue -> même résultat)."""
    signature = json.dumps(
        {"profile_snapshot_id": profile_snapshot_id, "result": result},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def _parse_duree_minutes(duree_texte):
    """Extrait le nombre de minutes de la chaîne produite par
    `workout_generator.generate_workout` (ex: "48 min (échauffement exclu)")
    -> 48. Phase 12/16 : cette valeur était calculée en phase 8 mais jamais
    persistée (oubli corrigé ici, cf. ProgramSession.duree_estimee_minutes).
    Ne lève jamais d'exception sur un format inattendu (None si imparsable)."""
    if not duree_texte:
        return None
    premier_mot = str(duree_texte).strip().split(" ")[0]
    try:
        return int(premier_mot)
    except ValueError:
        return None


def _muscles_de_la_seance(exercices_seance):
    """Dérive la liste des muscles couverts par une séance à partir des
    exercices persistés (`ProgramSession.muscles_concernes`, colonne existant
    depuis la phase 1). La structure produite par `build_program` ne porte
    pas ce champ explicitement (cf. schéma de sortie demandé, section 1) :
    on le reconstruit ici via `Exercise.muscle_principal`, puisque les
    `exercise_id` référencés sont, à ce stade, garantis correspondre à de
    vraies lignes du catalogue (contrainte FK)."""
    muscles = []
    for exo_data in exercices_seance:
        exercise = Exercise.query.get(exo_data.get("exercise_id"))
        muscle = getattr(exercise, "muscle_principal", None) if exercise else None
        if muscle and muscle not in muscles:
            muscles.append(muscle)
    return muscles


def create_program_from_result(user_id, profile_snapshot_id, result):
    """Convertit `result` (sortie de `build_program`) en `Program` persisté,
    avec ses `ProgramSession`/`ProgramExercise`. Si une génération strictement
    identique (même profil, même contenu) a déjà été enregistrée, retourne
    le `Program` existant SANS rien recréer (aucun doublon accidentel, cf.
    consigne section 3/4)."""
    generation_id = _compute_generation_id(profile_snapshot_id, result)

    existant = Program.query.filter_by(generation_id=generation_id).first()
    if existant is not None:
        return existant

    program = Program(
        user_id=user_id,
        profile_snapshot_id=profile_snapshot_id,
        formule=result.get("program_name") or "Programme",
        generation_id=generation_id,
    )
    db.session.add(program)
    db.session.flush()  # attribue program.id sans committer déjà

    for ordre, session_data in enumerate(result.get("sessions", [])):
        exercices_seance = session_data.get("exercises", [])
        session = ProgramSession(
            program_id=program.id,
            nom_seance=session_data.get("name") or f"Séance {ordre + 1}",
            muscles_concernes=_muscles_de_la_seance(exercices_seance),
            ordre_dans_semaine=ordre,
            duree_estimee_minutes=_parse_duree_minutes(session_data.get("duration")),
        )
        db.session.add(session)
        db.session.flush()

        for position, exo_data in enumerate(exercices_seance):
            program_exercise = ProgramExercise(
                session_id=session.id,
                exercise_id=exo_data.get("exercise_id"),
                position_dans_seance=position,
                series=exo_data.get("series") or 1,
                reps=str(exo_data.get("repetitions") or ""),
                rest_time_seconds=exo_data.get("rest_time"),
                intensity=exo_data.get("intensity"),
                notes=exo_data.get("notes"),
                conseil_execution=exo_data.get("conseil_execution"),
            )
            db.session.add(program_exercise)

    db.session.commit()
    return program


def get_latest_program(user_id):
    """Retourne le dernier `Program` créé pour `user_id` (le plus récent par
    `created_at`), ou None si aucun n'existe. Le schéma actuel de `Program`
    ne porte pas de statut "actif"/"archivé" dédié (aucune colonne de ce
    type n'existe depuis la phase 1) : "dernier programme actif" est donc
    interprété ici comme "le plus récemment généré" — interprétation
    documentée, cf. limites en fin de phase."""
    return (
        Program.query
        .filter_by(user_id=user_id)
        .order_by(Program.created_at.desc())
        .first()
    )


def delete_program(program_id):
    """Supprime un `Program` et tout ce qui en dépend (`ProgramSession`,
    `ProgramExercise`, `ExerciseUsageLog` liés — cascades déjà déclarées sur
    ces relations depuis les phases 1 et 10, non modifiées ici). Ne supprime
    JAMAIS le `User` ni le `ProfileSnapshot` associés (aucune cascade
    déclarée dans ce sens, par design : un profil doit survivre à la
    suppression d'un programme qui en est issu). Retourne True si un
    programme a été supprimé, False s'il n'existait pas déjà."""
    program = Program.query.get(program_id)
    if program is None:
        return False
    db.session.delete(program)
    db.session.commit()
    return True
