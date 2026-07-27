# -*- coding: utf-8 -*-
"""
Adaptateur PDF (phase 12/16) : traduit un `Program` SQLAlchemy (moteur V2,
phases 6-11) vers le format de dict attendu par le générateur PDF EXISTANT
(`logic/pdf_generator.generate_pdf`, jamais modifié). N'implémente AUCUNE
règle de recommandation/mise en page : ce module ne fait que reformer des
données déjà décidées ailleurs.

Format de sortie calqué exactement sur celui produit par l'ancien moteur
(`logic/program_builder.build_program`, jamais modifié non plus), déterminé
en lisant les clés effectivement utilisées par `pdf_generator.py` :
  - `split_label` (str, requis, affiché tel quel).
  - `warnings` (liste, requise, peut être vide).
  - `programme` (liste de séances), chacune :
      `nom` (str), `duree_estimee_min` (int), `muscles` (liste de blocs),
      `bonus_poids_du_corps` (optionnel, toujours [] ici — le moteur V2 ne
      génère pas encore cette section facultative, hors périmètre de cette
      phase).
    chaque bloc "muscles" : `muscle` (label FR), `exercices` (liste de
      `{"nom", "series", "reps"}`, seules clés lues par pdf_generator.py).
  - `objectif_note`/`niveau_note`/`equipement`/`prioritaires_labels`/
    `morpho_labels` : lus via `.get()` par pdf_generator.py, donc optionnels
    -> valeurs neutres (None/[]/str par défaut), le moteur V2 ne produit pas
    encore ces textes explicatifs (hors périmètre de cette phase).
"""
from logic.exercises_db import MUSCLE_LABELS
from logic.models import Exercise


def _label_muscle(muscle_key):
    return MUSCLE_LABELS.get(muscle_key, muscle_key)


def _regrouper_par_muscle(program_exercises):
    """Reconstruit le regroupement "un bloc par muscle" attendu par le PDF
    (`bloc["muscle"]`/`bloc["exercices"]`) à partir de `ProgramExercise`
    (qui ne porte pas directement le muscle : on le résout via la relation
    `Exercise.muscle_principal`, cf. même logique que
    `program_repository._muscles_de_la_seance`, phase 11). Préserve l'ordre
    d'apparition des muscles (premier exercice rencontré pour ce muscle)."""
    par_muscle = {}
    ordre_muscles = []

    for pe in program_exercises:
        exercise = pe.exercise
        if exercise is None:
            exercise = Exercise.query.get(pe.exercise_id)
        muscle_key = getattr(exercise, "muscle_principal", None) or "?"

        if muscle_key not in par_muscle:
            par_muscle[muscle_key] = []
            ordre_muscles.append(muscle_key)

        par_muscle[muscle_key].append({
            "nom": getattr(exercise, "name", None) or pe.exercise_id,
            "series": pe.series,
            "reps": pe.reps,
        })

    return [{"muscle": _label_muscle(m), "exercices": par_muscle[m]} for m in ordre_muscles]


def program_to_pdf_data(program):
    """program_to_pdf_data(program) -> dict compatible avec
    `pdf_generator.generate_pdf(output, profile, nutrition, program, cardio,
    lifestyle)`. Retourne None si `program` est None (le PDF gère déjà ce
    cas : `if program:` avant toute lecture, cf. pdf_generator.py)."""
    if program is None:
        return None

    programme = []
    for session in program.sessions:
        programme.append({
            "nom": session.nom_seance,
            "muscles": _regrouper_par_muscle(session.exercises),
            "duree_estimee_min": session.duree_estimee_minutes or 0,
            "bonus_poids_du_corps": [],
        })

    split_label = (program.formule or "Programme").replace("Programme ", "", 1) or "Programme"

    profile_snapshot = program.profile_snapshot
    objectif = profile_snapshot.objectif_principal if profile_snapshot else None
    variables = (getattr(profile_snapshot, "variables_json", None) or {}) if profile_snapshot else {}
    # "equipement" reste le nom du champ questionnaire depuis l'ancien moteur
    # (préservé tel quel dans variables_json, cf. profile_normalizer.py) ;
    # repli identique à celui déjà utilisé par pdf_generator.py lui-même
    # pour ne jamais afficher une valeur vide/None dans le PDF.
    equipement = variables.get("equipement") or "Salle complète"

    return {
        "split_label": split_label,
        "split_key": None,
        "programme": programme,
        # Phase 12/16 : les avertissements de génération (build_program) ne
        # sont pas encore persistés sur Program (limite documentée en fin de
        # phase) -> toujours [] ici, jamais une clé absente (pdf_generator.py
        # lit `program["warnings"]` sans valeur par défaut).
        "warnings": [],
        "objectif_note": None,
        "niveau_note": None,
        "equipement": equipement,
        "prioritaires_labels": [],
        "morpho_labels": [],
        "objectif": objectif,
    }
