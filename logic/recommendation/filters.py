# -*- coding: utf-8 -*-
"""
Passe 1 du moteur : filtrage dur (sécurité et faisabilité, non négociable).
Un exercice exclu ici ne doit JAMAIS être scoré ni proposé, quelle que soit
sa pertinence par ailleurs. La sécurité prime toujours sur la préférence.

Ce module ne fait AUCUNE exclusion liée au goût de l'utilisateur ("je n'aime
pas cet exercice" sans raison physique) — cette pénalité relève de la passe 2
(scoring), pas du filtrage dur.
"""
from logic.recommendation import biomechanics

# Sévérité déclarée -> rang (resolution_11_points_bloquants.md point 6).
SEVERITE_RANG = {
    "Légère gêne occasionnelle": 1,
    "Gêne modérée régulière": 2,
    "Douleur invalidante": 3,
}

# `blessures` (ProfileSnapshot) est keyé par le libellé de la question ("Épaule",
# "Dos / lombaires"...) ; `joint_stress` (Exercise) est keyé par une convention
# anatomique courte (architecture_base_exercices.md partie 2 : epaule, genou,
# dos_lombaire, poignet, coude, cheville). Sans cette table de correspondance,
# les deux dicts ne se croisent jamais (clés différentes) — bug repéré par les
# tests de cette phase, corrigé ici plutôt que silencieusement laissé de côté.
ZONE_LABEL_TO_JOINT_STRESS_KEY = {
    "Épaule": "epaule",
    "Dos / lombaires": "dos_lombaire",
    "Genoux": "genou",
    "Chevilles / talons": "cheville",
    "Poignets": "poignet",
}


def _joint_stress_value(joint_stress, zone_label):
    key = ZONE_LABEL_TO_JOINT_STRESS_KEY.get(zone_label, zone_label)
    return joint_stress.get(key, 0) or 0


def _blessure_exclusion_reason(profile, exercise):
    """Grille exacte resolution_11_points_bloquants.md point 6 : croise la
    sévérité déclarée par zone avec joint_stress[zone] de l'exercice. Une zone
    non déclarée n'a jamais d'effet, quelle que soit la valeur de joint_stress
    (cf. dernière ligne de la grille)."""
    blessures = getattr(profile, "blessures", None) or {}
    joint_stress = getattr(exercise, "joint_stress", None) or {}

    for zone, severite in blessures.items():
        rang = SEVERITE_RANG.get(severite)
        if rang is None:
            continue  # sévérité pas encore renseignée (limite connue de la phase 5) -> aucun effet ici
        stress_zone = _joint_stress_value(joint_stress, zone)

        if rang == 3 and stress_zone >= 1:
            return f"douleur_invalidante_{zone} : joint_stress={stress_zone}"
        if rang == 2 and stress_zone >= 2:
            return f"gene_moderee_{zone} : joint_stress={stress_zone}"
        # rang == 1 (légère gêne) n'exclut jamais, quelle que soit la valeur de
        # joint_stress — seulement une pénalité douce (voir blessure_soft_penalty).

    return None


def _feedback_douleur_exclusion_reason(profile, exercise, feedback_repository=None):
    """Prépare l'interface pour un futur `ExerciseFeedback` (phase historique/
    feedback, pas encore créée) : un feedback "douleur/gêne" sur cet exercice
    doit rejoindre la passe 1 comme une blessure déclarée (resolution_11_
    points_bloquants.md point 9), jamais rester une simple pénalité de score.

    `feedback_repository`, si fourni, est un callable
    `feedback_repository(user_id, exercise_id) -> raison|None` — laissé
    optionnel et sans valeur par défaut fonctionnelle tant que la table
    n'existe pas, pour ne jamais planter en son absence."""
    if feedback_repository is None:
        return None
    raison = feedback_repository(getattr(profile, "user_id", None), getattr(exercise, "exercise_id", None))
    if raison in ("douleur", "douleur_gene", "Douleur / gêne"):
        return f"feedback_douleur_{exercise.exercise_id}"
    return None


def exclusion_reason(profile, exercise, feedback_repository=None):
    """Point d'entrée unique de la passe 1. Retourne une chaîne expliquant
    l'exclusion, ou None si l'exercice passe le filtrage dur."""
    reason = _blessure_exclusion_reason(profile, exercise)
    if reason:
        return reason

    reason = biomechanics.amplitude_hard_exclusion_reason(profile, exercise)
    if reason:
        return reason

    reason = _feedback_douleur_exclusion_reason(profile, exercise, feedback_repository)
    if reason:
        return reason

    return None


def blessure_soft_penalty(profile, exercise):
    """Pénalité douce (passe 2, exprimée en pourcentage à appliquer au score
    final) pour les gênes qui n'atteignent pas le seuil d'exclusion : -40%
    pour une gêne modérée avec joint_stress=1, -20% pour une gêne légère avec
    joint_stress=3. Zéro dans tous les autres cas (y compris zone non
    déclarée). Cf. resolution_11_points_bloquants.md point 6."""
    blessures = getattr(profile, "blessures", None) or {}
    joint_stress = getattr(exercise, "joint_stress", None) or {}

    penalty_pct = 0
    for zone, severite in blessures.items():
        rang = SEVERITE_RANG.get(severite)
        if rang is None:
            continue
        stress_zone = _joint_stress_value(joint_stress, zone)

        if rang == 2 and stress_zone == 1:
            penalty_pct = min(penalty_pct, -40)
        elif rang == 1 and stress_zone == 3:
            penalty_pct = min(penalty_pct, -20)

    return penalty_pct
