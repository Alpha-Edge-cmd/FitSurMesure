# -*- coding: utf-8 -*-
"""
Coefficient de diversité par famille d'exercice (phase 7/16).

Objectif : sur une sélection de plusieurs exercices pour un même muscle,
favoriser des familles différentes (`exercise.family`) plutôt que de
retenir plusieurs variantes trop proches du même mouvement — même logique
que l'ancien `FAMILY_MAP` de `program_builder.py`, mais exprimée comme un
ajustement de score (bonus/malus) plutôt qu'un simple regroupement.

Valeurs de départ, à calibrer empiriquement plus tard (aucune formule
chiffrée précise n'a été validée dans les documents de conception pour ce
point — seul le principe "bonus nouvelle famille / malus répétition
excessive" l'a été)."""

BONUS_NOUVELLE_FAMILLE = 5
MALUS_PAR_REPETITION_FAMILLE = 8  # s'aggrave à chaque répétition supplémentaire


def calculate_diversity_bonus(exercise, already_selected):
    """+bonus si `exercise.family` n'apparaît dans aucun exercice déjà
    sélectionné, sinon 0. `already_selected` : liste d'objets Exercise."""
    famille = getattr(exercise, "family", None)
    familles_deja_choisies = {getattr(e, "family", None) for e in already_selected}
    if famille is not None and famille not in familles_deja_choisies:
        return BONUS_NOUVELLE_FAMILLE
    return 0


def calculate_family_penalty(exercise, already_selected):
    """-malus proportionnel au nombre de fois où cette famille a déjà été
    choisie (0 si jamais). Escalade volontairement (2e répétition pénalisée
    plus que la 1re) pour décourager une sélection à 3+ exercices de la même
    famille sans jamais l'interdire complètement (nécessité absolue possible
    sur un muscle pauvre — cf. fallback.py étape 3)."""
    famille = getattr(exercise, "family", None)
    repetitions = sum(1 for e in already_selected if getattr(e, "family", None) == famille)
    if repetitions == 0:
        return 0
    return -MALUS_PAR_REPETITION_FAMILLE * repetitions
