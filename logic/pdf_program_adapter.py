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
            # Additif (prompt hors 24 phases, conseils d'exécution) : clé en
            # plus, lue par pdf_generator.py si présente (sinon ignorée).
            "conseil_execution": getattr(pe, "conseil_execution", None),
            # Additif (prompt hors 24 phases, retour Samy : "je veux que la
            # portion du muscle travaillé soit indiquée à côté du nom") :
            # Exercise.portion_anatomique existe déjà au catalogue (#118),
            # simplement jamais propagé jusqu'ici jusqu'au PDF.
            "portion": getattr(exercise, "portion_anatomique", None),
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


def _regrouper_exercices_par_muscle_v2(exercices_seance, exercises_by_id):
    """Même regroupement que `_regrouper_par_muscle` ci-dessus, mais à partir
    de la structure BRUTE renvoyée par `logic.recommendation.program_builder.
    build_program()` (dicts {"exercise_id","series","repetitions","rest_time",
    "intensity","notes","conseil_execution"}), PAS d'un `Program` persisté en
    base. Utilisé par `raw_result_to_pdf_data` (aperçu avant paiement et PDF
    payant définitif, depuis la bascule du moteur V2 pour ces deux routes,
    prompt hors 24 phases)."""
    par_muscle = {}
    ordre_muscles = []

    for exo in exercices_seance:
        exercise = exercises_by_id.get(exo.get("exercise_id"))
        muscle_key = getattr(exercise, "muscle_principal", None) or "?"

        if muscle_key not in par_muscle:
            par_muscle[muscle_key] = []
            ordre_muscles.append(muscle_key)

        par_muscle[muscle_key].append({
            "nom": getattr(exercise, "name", None) or exo.get("exercise_id"),
            "series": exo.get("series"),
            "reps": exo.get("repetitions"),
            "conseil_execution": exo.get("conseil_execution"),
            # Additif (prompt hors 24 phases, portion musculaire affichée à
            # côté du nom) : même logique que `_regrouper_par_muscle`
            # ci-dessus, pour la route ephémère (/generate-preview, /download).
            "portion": getattr(exercise, "portion_anatomique", None),
        })

    return [{"muscle": _label_muscle(m), "exercices": par_muscle[m]} for m in ordre_muscles]


def raw_result_to_pdf_data(result, exercises_catalog, questionnaire_data=None, profile_snapshot=None):
    """raw_result_to_pdf_data(result, exercises_catalog, questionnaire_data=None,
    profile_snapshot=None) -> dict compatible avec `pdf_generator.generate_pdf`
    ET avec `app._preview_json` (même forme "split_label"/"programme" que
    `program_to_pdf_data` ci-dessus et que l'ancien moteur
    `logic.program_builder.build_program`).

    `result` : sortie BRUTE (dict Python, jamais persistée) de
    `logic.recommendation.program_builder.build_program(profile_snapshot,
    exercises_catalog, options)` — permet de construire un aperçu PDF-ready
    SANS écrire en base (utile avant paiement, `/generate-preview`), et sert
    aussi de base pour `/download` (PDF payant définitif) depuis la bascule
    du moteur V2 pour ces deux routes (prompt hors 24 phases, décision
    explicite de Samy après le constat que le PDF payant utilisait encore
    l'ancien moteur à 111 exercices malgré tout le travail fait sur le V2).

    `questionnaire_data` : dict brut du questionnaire (facultatif), utilisé
    UNIQUEMENT pour objectif_note/niveau_note/prioritaires_labels/equipement
    (mêmes textes explicatifs que l'ancien moteur, réutilisés en LECTURE
    SEULE depuis `logic/program_builder.py`, jamais recalculés ici).
    `profile_snapshot` : facultatif, permet de calculer `morpho_labels` via
    `logic.recommendation.biomechanics._activated_morphologie_keys` (mêmes
    traits que ceux réellement utilisés par le scoring V2, plutôt que de
    redériver une règle parallèle bras/jambes comme l'ancien moteur)."""
    from logic.program_builder import NIVEAU_NOTES, OBJECTIF_NOTES
    from logic.program_repository import _parse_duree_minutes

    exercises_by_id = {getattr(ex, "exercise_id", None): ex for ex in exercises_catalog}
    questionnaire_data = questionnaire_data or {}

    programme = []
    for session in result.get("sessions", []):
        programme.append({
            "nom": session.get("name"),
            "muscles": _regrouper_exercices_par_muscle_v2(session.get("exercises", []), exercises_by_id),
            "duree_estimee_min": _parse_duree_minutes(session.get("duration")) or 0,
            "bonus_poids_du_corps": [],
        })

    split_label = (result.get("program_name") or "Programme").replace("Programme ", "", 1) or "Programme"
    objectif = result.get("objective")
    niveau = questionnaire_data.get("niveau_musculation")

    morpho_labels = []
    if profile_snapshot is not None:
        from logic.recommendation.biomechanics import _activated_morphologie_keys
        morpho_labels = sorted(
            t for t in _activated_morphologie_keys(profile_snapshot) if t != "mobilite_faible"
        )

    return {
        "split_label": split_label,
        "split_key": None,
        "programme": programme,
        "warnings": result.get("warnings", []),
        "objectif_note": OBJECTIF_NOTES.get(objectif),
        "niveau_note": NIVEAU_NOTES.get(niveau),
        "equipement": questionnaire_data.get("equipement") or "Salle complète",
        "prioritaires_labels": sorted(set(questionnaire_data.get("muscles_prioritaires") or [])),
        "morpho_labels": morpho_labels,
        "objectif": objectif,
        # Additif (prompt hors 24 phases, justification à 3 niveaux) : passe
        # tel quel "explanation" (program_personalization.generate_program_
        # explanation), déjà calculée par build_program -> pdf_generator.py
        # l'affiche si présente, l'ignore sinon (rétrocompatible avec
        # `program_to_pdf_data` ci-dessus, qui ne la fournit pas).
        "explanation": result.get("explanation"),
    }
