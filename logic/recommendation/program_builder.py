# -*- coding: utf-8 -*-
"""
Orchestrateur principal du moteur de recommandation V2 (phase 11/16) :

    ProfileSnapshot -> catalogue Exercise -> scoring -> selector
        -> workout_generator -> prescription -> structure prête à enregistrer

Ne redéfinit AUCUNE règle métier des phases précédentes : ce module ne fait
qu'appeler `workout_generator.generate_workout` et
`prescription.generate_prescription` pour chaque séance de la semaine, puis
assemble leurs résultats. La sauvegarde en base (conversion vers les modèles
SQLAlchemy) est la responsabilité de `logic/program_repository.py`, pas de
ce module — `build_program` retourne une structure Python simple (dict),
jamais un objet SQLAlchemy.

Répartition des séances par semaine : le nouveau moteur (phases 6 à 10) ne
définit pas encore sa propre notion de "split" (Full Body / Upper-Lower /
PPL / Arnold) — cette notion existe déjà, éprouvée, dans le moteur legacy
(`logic/program_builder.py`, jamais modifié ici) et ses données de référence
(`logic/exercises_db.py`, `SPLITS`). Ce module réutilise ces deux éléments
en LECTURE SEULE (`_split_key_auto` pour choisir le split selon fréquence/
objectif/niveau, `SPLITS` pour la répartition des muscles par séance) plutôt
que d'inventer une seconde logique de split parallèle et incohérente avec
l'existant.
"""
from logic.exercises_db import SPLITS
from logic.program_builder import _split_key_auto
from logic.program_personalization import (
    adjust_frequency_for_availability,
    adjust_intensity_for_age,
    adjust_rest_for_age,
    build_coaching_note,
    compute_personalization_context,
    equipements_preferes,
    generate_program_explanation,
    reorder_session_by_equipment_preference,
)
from logic.recommendation import exercise_order
from logic.recommendation.prescription import generate_prescription
from logic.recommendation.workout_generator import generate_workout

# Phase 20/24 : intègre logic/program_personalization.py (voir docstring de ce
# module) sans redéfinir aucune règle de scoring/sélection/volume/ordre/repos/
# intensité déjà validée — uniquement des ajustements additifs (fréquence vs
# disponibilité réelle, ordre au sein d'un palier vs matériel préféré, repos/
# intensité vs âge, notes coaching enrichies) et l'explication du programme
# (`generate_program_explanation`). Import direct (pas de cycle : ce module
# ne dépend que de `logic.recommendation.exercise_order`/`intensity` et, en
# différé, de `logic.profile_analysis`, jamais de `program_builder.py`).

FREQUENCE_DEFAUT = 3
DUREE_SEANCE_DEFAUT = "1h - 1h30"

MESSAGE_PROGRAMME_VIDE = (
    "Aucun exercice n'a pu être proposé pour ce programme compte tenu de tes contraintes."
)


def _resoudre_frequence(profile_snapshot, options):
    if options and options.get("frequence"):
        return int(options["frequence"])
    variables = getattr(profile_snapshot, "variables_json", None) or {}
    try:
        return int(variables.get("frequence_entrainement", FREQUENCE_DEFAUT))
    except (TypeError, ValueError):
        return FREQUENCE_DEFAUT


def _resoudre_duree_seance(profile_snapshot, options):
    if options and options.get("duree_seance"):
        return options["duree_seance"]
    variables = getattr(profile_snapshot, "variables_json", None) or {}
    return variables.get("duree_seance", DUREE_SEANCE_DEFAUT)


def _repartir_seances(jours_split, frequence):
    """Étale les `frequence` séances demandées sur le motif de jours du split
    choisi, en le répétant (cycle) si `frequence` dépasse son nombre de jours
    natif, ou en le tronquant si elle est inférieure. Numérote les séances
    répétées ("Push (2)") pour éviter des noms de séance ambigus/dupliqués
    sur la semaine."""
    if not jours_split:
        return []

    seances = []
    for i in range(frequence):
        jour = jours_split[i % len(jours_split)]
        cycle = (i // len(jours_split)) + 1
        nom = jour["nom"] if cycle == 1 else f"{jour['nom']} ({cycle})"
        seances.append({"nom": nom, "muscles": jour["muscles"]})
    return seances


def build_program(profile_snapshot, exercises_catalog, options=None):
    """Point d'entrée principal de cette phase.

    profile_snapshot   : ProfileSnapshot (phase 1/4).
    exercises_catalog   : liste d'objets Exercise (catalogue disponible).
    options             : dict optionnel, clés reconnues :
                          "frequence" (int, remplace la fréquence déclarée),
                          "duree_seance" (remplace la durée déclarée).

    Retourne {"program_name", "objective", "sessions": [{"name", "duration",
    "exercises": [{"exercise_id", "series", "repetitions", "rest_time",
    "intensity", "notes"}]}], "warnings"} — jamais d'exception, jamais une
    structure vide sans avertissement explicite (même garantie que
    `workout_generator`/`fallback`, phases 7-8).

    Phase 20/24 : le dict retourné porte désormais une clé additive
    "explanation" (cf. `logic.program_personalization.
    generate_program_explanation`) — aucune clé existante n'est renommée ni
    retirée ; `program_repository.py`/`program_validation.py` ne lisent que
    des clés précises et ignorent silencieusement celle-ci (vérifié en amont
    de cette phase)."""
    options = options or {}

    frequence_demandee = _resoudre_frequence(profile_snapshot, options)
    duree_seance = _resoudre_duree_seance(profile_snapshot, options)

    # Phase 20/24 : ajuste (jamais n'augmente) la fréquence effective selon
    # la disponibilité réelle déclarée, avec avertissement explicite en cas
    # de réduction (jamais une substitution silencieuse).
    frequence, avertissement_frequence = adjust_frequency_for_availability(
        profile_snapshot, frequence_demandee
    )

    niveau = getattr(profile_snapshot, "niveau_musculation", None)
    objectif = getattr(profile_snapshot, "objectif_principal", None)
    split_key = _split_key_auto(frequence, objectif, niveau)
    split = SPLITS[split_key]

    plan_seances = _repartir_seances(split["jours"], frequence)

    # Phase 20/24 : contexte de personnalisation (âge/niveau/objectif/
    # matériel/disponibilité/contraintes/forces/faiblesses/risques), calculé
    # UNE SEULE FOIS pour tout le programme, jamais recalculé par séance
    # (cf. logic/program_personalization.py).
    contexte_personnalisation = compute_personalization_context(profile_snapshot)
    preferences_materiel = equipements_preferes(profile_snapshot)
    exercises_by_id = {getattr(ex, "exercise_id", None): ex for ex in exercises_catalog}

    sessions = []
    warnings = []
    seances_detail = []
    total_exercices = 0

    if avertissement_frequence:
        warnings.append(avertissement_frequence)

    for jour in plan_seances:
        workout = generate_workout(profile_snapshot, jour["muscles"], exercises_catalog, duree_seance)

        # Phase 20/24 : réordonne (jamais n'exclut, jamais ne change de
        # palier `exercise_order` déjà décidé) les exercices déjà choisis
        # selon le matériel préféré, AVANT la prescription pour que l'ordre
        # final des séries/répétitions/repos reflète ce choix.
        items_pour_ordre = [
            {"exercise": exercises_by_id.get(w_ex["exercise_id"]), "w_ex": w_ex}
            for w_ex in workout["exercises"]
            if exercises_by_id.get(w_ex["exercise_id"]) is not None
        ]
        items_ordonnes = reorder_session_by_equipment_preference(items_pour_ordre, preferences_materiel)
        exercises_reordonnes = [it["w_ex"] for it in items_ordonnes]
        # Sécurité redondante : un exercise_id de `workout` introuvable dans
        # `exercises_catalog` ne devrait jamais arriver (workout_generator
        # construit déjà son `lookup` depuis ce même catalogue) ; s'il
        # arrivait quand même, on le conserve en fin de liste plutôt que de
        # le faire disparaître silencieusement.
        ids_ordonnes = {w_ex["exercise_id"] for w_ex in exercises_reordonnes}
        exercises_reordonnes += [
            w_ex for w_ex in workout["exercises"] if w_ex["exercise_id"] not in ids_ordonnes
        ]
        workout = {**workout, "exercises": exercises_reordonnes}

        prescription = generate_prescription(profile_snapshot, workout, exercises_catalog)
        prescriptions_par_id = {p["exercise_id"]: p for p in prescription["exercises"]}

        age = contexte_personnalisation.get("age")
        exercices_seance = []
        exercices_detail_seance = []
        for w_ex in workout["exercises"]:
            # Retour Samy (prompt hors 24 phases, "1x3-6 incohérent") :
            # `generate_prescription` peut désormais retirer un exercice
            # entier plutôt que de le vider à 1 série (cf. prescription.py,
            # `_retirer_exercices_si_besoin`) -> absent de
            # `prescriptions_par_id`. Avant, `.get(..., {})` retombait sur un
            # dict vide et l'exercice restait affiché dans le PDF SANS
            # séries/reps (ligne cassée) ; on l'ignore maintenant totalement,
            # cohérent avec le retrait décidé en amont.
            if w_ex["exercise_id"] not in prescriptions_par_id:
                continue
            presc = prescriptions_par_id.get(w_ex["exercise_id"], {})
            exo_obj = exercises_by_id.get(w_ex["exercise_id"])

            # Phase 20/24 : ajustements additifs repos/intensité selon
            # l'âge (cf. logic/program_personalization.py) — n'écrase jamais
            # le calcul déjà validé de rest_time.py/intensity.py, ne fait que
            # l'affiner légèrement au-delà d'un seuil prudent.
            rest_time = adjust_rest_for_age(presc.get("rest_seconds"), age)
            intensity = adjust_intensity_for_age(presc.get("intensity"), age)

            materiel_correspond = bool(
                exo_obj is not None and preferences_materiel
                and set(getattr(exo_obj, "equipment", None) or []) & preferences_materiel
            )
            notes = build_coaching_note(
                presc.get("notes"), exo_obj, contexte_personnalisation, materiel_correspond
            )

            exercices_seance.append({
                "exercise_id": w_ex["exercise_id"],
                "series": presc.get("sets"),
                "repetitions": presc.get("reps"),
                "rest_time": rest_time,
                "intensity": intensity,
                "notes": notes,
                # Additif (prompt hors 24 phases) : conseil d'exécution
                # (tempo/effort), distinct de "notes" -> propagé tel quel
                # depuis prescription.py, aucune règle recalculée ici.
                "conseil_execution": presc.get("conseil_execution"),
            })

            tier = exercise_order.classify_exercise(exo_obj) if exo_obj is not None else None
            exercices_detail_seance.append({
                "exercise_id": w_ex["exercise_id"],
                "raison_selection": w_ex.get("raison_selection"),
                "tier": tier,
                "sets": presc.get("sets"),
                "intensity": intensity,
                # Prompt final (hors 24 phases) : référence brute vers l'objet
                # Exercise (déjà résolu ci-dessus, `exo_obj`), pour que
                # `generate_program_explanation` (program_personalization.py)
                # puisse citer explicitement morphologie/objectif dans le
                # "pourquoi cet exercice" sans recalculer aucune règle ici.
                "exercise": exo_obj,
            })

        total_exercices += len(exercices_seance)
        sessions.append({
            "name": jour["nom"],
            "duration": workout["estimated_duration"],
            "exercises": exercices_seance,
        })
        seances_detail.append({"nom": jour["nom"], "exercices": exercices_detail_seance})
        warnings.extend(workout["warnings"])
        # Additif (prompt hors 24 phases) : avertissement de
        # `generate_prescription` (exercices retirés faute de budget de
        # fatigue suffisant même au plancher de séries), distinct de ceux de
        # `generate_workout` ci-dessus mais agrégé de la même façon (dédupliqué
        # plus bas avec le reste).
        warnings.extend(prescription.get("warnings", []))

    if total_exercices == 0:
        warnings.append(MESSAGE_PROGRAMME_VIDE)

    # Retour Samy (prompt hors 24 phases, test en conditions réelles) : un
    # même avertissement générique (ex: "budget de fatigue dépassé même au
    # volume plancher") revenait identique une fois PAR SÉANCE dans la
    # section "Pourquoi CE programme" du PDF dès que plusieurs séances de la
    # semaine se ressemblent (ex: Full Body x3/semaine) -> déduplique en
    # conservant l'ordre d'apparition, jamais l'information elle-même
    # (un avertissement réellement différent reste affiché).
    warnings = list(dict.fromkeys(warnings))

    # Phase 20/24 : generate_program_explanation() — reformule en phrases
    # lisibles ce qui a déjà été calculé ci-dessus (raison de sélection,
    # palier, séries, intensité), ne recalcule rien.
    explanation = generate_program_explanation(
        profile_snapshot, seances_detail, contexte_personnalisation,
        split_label=split["label"], frequence=frequence,
    )

    return {
        "program_name": f"Programme {split['label']}",
        "objective": objectif,
        "sessions": sessions,
        "warnings": warnings,
        "explanation": explanation,
    }
