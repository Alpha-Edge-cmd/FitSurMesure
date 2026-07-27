# -*- coding: utf-8 -*-
"""
Détection automatique d'incohérences éditoriales du catalogue (phase
14/16) — une couche distincte de `logic/exercise_catalog_validator.py` :

  - `exercise_catalog_validator.validate_catalog` vérifie la FORME des
    données (types, plages, clés autorisées) et sert de porte bloquante
    avant tout import en base (logic/exercise_catalog_import.py).
  - `validate_exercise_quality`, ici, vérifie la VRAISEMBLANCE éditoriale
    d'une fiche déjà valide (est-ce que ces valeurs se tiennent ensemble ?)
    pour aider un humain à prioriser sa revue (logic/exercise_review.py).
    Ne bloque jamais un import, ne modifie jamais aucune donnée : ce module
    ne fait qu'observer et rapporter (cf. consigne "Ne jamais modifier
    automatiquement les données").

Accepte indifféremment une instance `Exercise` (ORM, déjà en base) ou un
simple dict "fiche" (JSON éditorial, phase 13) : `_valeur()` lit les deux
formes de la même façon, pour ne pas dupliquer cette logique deux fois.
"""
from logic.exercise_migration import _guess_movement_type

CHAMPS_HYPERTROPHIE = ("score_tension_mecanique", "score_contraction_max", "potentiel_hypertrophique")

# Vocabulaire d'équipement réellement utilisé par le catalogue legacy
# (cf. logic/exercises_db.py) — toute valeur en dehors est un signal de
# donnée mal saisie plutôt qu'une vraie variété d'équipement.
EQUIPEMENTS_CONNUS = {"barre", "haltere", "machine", "poids_du_corps", "elastique"}

# Écart maximal toléré entre `potentiel_hypertrophique` et la moyenne des
# deux autres scores avant de le signaler comme incohérent. Seuil éditorial
# documenté (pas une formule scientifique) : sert uniquement à prioriser la
# revue humaine, jamais à rejeter une fiche.
ECART_SCORE_INCOHERENT = 4

# joint_stress au maximum (3, cf. exercise_catalog_validator.JOINT_STRESS_MAX)
# sans aucune trace explicative ailleurs dans la fiche (contre_indications ou
# substituts documentés) est considéré comme "sans justification" — un
# proxy simple, pas une preuve absolue.
JOINT_STRESS_MAXIMAL = 3


def _valeur(exercise, champ, defaut=None):
    if isinstance(exercise, dict):
        return exercise.get(champ, defaut)
    return getattr(exercise, champ, defaut)


def _pattern_muscles_connus():
    """{pattern: {muscle_key, ...}} construit dynamiquement à partir du
    catalogue legacy réel (logic.exercises_db.EXERCISES) — pas une table de
    correspondance inventée à la main : reflète ce qui existe déjà, sert
    uniquement à repérer un muscle_principal qui s'écarte de l'historique
    connu pour ce pattern."""
    from logic.exercises_db import EXERCISES

    mapping = {}
    for muscle_key, exos in EXERCISES.items():
        for legacy in exos:
            mapping.setdefault(legacy["pattern"], set()).add(muscle_key)
    return mapping


def validate_exercise_quality(exercise):
    """validate_exercise_quality(exercise) -> {"valid", "warnings", "errors"}.

    `exercise` : instance `Exercise` ou dict fiche. Ne modifie jamais
    `exercise`, ne touche pas à la base."""
    warnings = []
    errors = []

    exercise_id = _valeur(exercise, "exercise_id", "?")
    pattern = _valeur(exercise, "pattern")
    movement_type = _valeur(exercise, "movement_type")
    equipment = _valeur(exercise, "equipment") or []
    muscle_principal = _valeur(exercise, "muscle_principal")
    difficulty_level = _valeur(exercise, "difficulty_level")
    technical_complexity = _valeur(exercise, "technical_complexity")
    stability_demand = _valeur(exercise, "stability_demand")
    joint_stress = _valeur(exercise, "joint_stress") or {}
    objectifs_adaptes = _valeur(exercise, "objectifs_adaptes") or {}
    contre_indications = _valeur(exercise, "contre_indications") or []
    substitutes = _valeur(exercise, "substitutes") or []
    actif = _valeur(exercise, "actif", True)

    # --- movement_type absent mais pattern connu ---------------------------
    if movement_type is None and pattern and _guess_movement_type(pattern) is not None:
        warnings.append(
            f"movement_type absent alors qu'un mouvement probable ('{_guess_movement_type(pattern)}') "
            f"est déductible du pattern '{pattern}'"
        )

    # --- equipment incohérent avec le mouvement -----------------------------
    if not equipment:
        warnings.append("equipment vide")
    else:
        inconnus = sorted(set(equipment) - EQUIPEMENTS_CONNUS)
        if inconnus:
            warnings.append(f"equipment contient des valeurs non reconnues : {inconnus}")

    # --- muscle_principal incompatible avec le pattern ----------------------
    if pattern and muscle_principal:
        muscles_connus = _pattern_muscles_connus().get(pattern)
        if muscles_connus and muscle_principal not in muscles_connus:
            errors.append(
                f"muscle_principal='{muscle_principal}' incompatible avec le pattern '{pattern}' "
                f"(historiquement associé à {sorted(muscles_connus)})"
            )

    # --- scores hypertrophiques incohérents ---------------------------------
    tension = _valeur(exercise, "score_tension_mecanique")
    contraction = _valeur(exercise, "score_contraction_max")
    potentiel = _valeur(exercise, "potentiel_hypertrophique")
    if tension is not None and contraction is not None and potentiel is not None:
        moyenne = (tension + contraction) / 2
        if abs(potentiel - moyenne) > ECART_SCORE_INCOHERENT:
            warnings.append(
                f"potentiel_hypertrophique={potentiel} loin de la moyenne tension/contraction ({moyenne:.1f})"
            )

    # --- joint_stress trop élevé sans justification -------------------------
    zones_maximales = [zone for zone, valeur in joint_stress.items() if valeur >= JOINT_STRESS_MAXIMAL]
    if zones_maximales and not contre_indications and not substitutes:
        warnings.append(
            f"joint_stress maximal sur {zones_maximales} sans contre_indications ni substitutes documentés"
        )

    # --- objectifs_adaptes vides ---------------------------------------------
    if not objectifs_adaptes:
        warnings.append("objectifs_adaptes vide : cet exercice ne sera jamais favorisé par un objectif")

    # --- exercise actif mais incomplet ---------------------------------------
    champs_cles_absents = [
        champ
        for champ, valeur in (
            ("movement_type", movement_type),
            ("difficulty_level", difficulty_level),
            ("technical_complexity", technical_complexity),
            ("stability_demand", stability_demand),
        )
        if valeur is None
    ]
    if actif and len(champs_cles_absents) == 4:
        errors.append(
            "exercice actif mais totalement incomplet (movement_type/difficulty_level/"
            "technical_complexity/stability_demand tous absents)"
        )

    return {
        "valid": not errors,
        "warnings": warnings,
        "errors": errors,
        "exercise_id": exercise_id,
    }
