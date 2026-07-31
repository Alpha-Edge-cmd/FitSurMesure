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

# --- Diversité sur plusieurs axes ---------------------------------------------
# Retour Samy : « j'ai 3x développé couché sur 4 exercices et 2x élévation
# frontale sur 4 [...] le problème c'est vraiment la diversité des exercices.
# Au pire classe les exercices force, hypertrophie, poulie, barre, haltère,
# développé, polyarticulaire, isométrique. »
#
# La famille de mouvement seule ne suffit pas : quatre développés à la barre
# appartenant à quatre familles différentes restent quatre fois le même type
# de stimulus, avec le même matériel et le même angle. On pénalise donc
# séparément trois axes, qui se cumulent :
#
#   1. la FAMILLE de mouvement (déjà en place) ;
#   2. le MATÉRIEL — quatre exercices à la poulie d'affilée, c'est monotone
#      et ça ne varie ni la courbe de résistance ni la stabilité demandée ;
#   3. le FORMAT de travail (force / hypertrophie / isolation / isométrique),
#      pour qu'une séance mélange lourd et léger plutôt que d'empiler quatre
#      mouvements du même registre.
#
# Les malus sont volontairement élevés : ils doivent dépasser la tolérance
# d'équivalence du sélecteur (`selector.TOLERANCE_EQUIVALENCE`), sinon un
# doublon reste dans le groupe des candidats jugés équivalents et peut être
# retenu par la rotation.
MALUS_PAR_REPETITION_EQUIPEMENT = 7
MALUS_PAR_REPETITION_FORMAT = 6


def _equipement_principal(exercise):
    """Matériel dominant d'un exercice, en une valeur comparable."""
    equipement = [str(e).lower() for e in (getattr(exercise, "equipment", None) or [])]
    for cle in ("machine", "barre", "haltere", "elastique", "poids_du_corps"):
        if cle in equipement:
            return cle
    return None


def _format_travail(exercise):
    """Format de travail, réutilisé depuis `prescription` pour ne pas
    dupliquer la règle (import différé : `prescription` importe déjà ce
    module indirectement via le sélecteur)."""
    from logic.recommendation.prescription import format_de_travail
    return format_de_travail(exercise)


def calculate_equipment_penalty(exercise, already_selected):
    """Malus proportionnel au nombre d'exercices déjà retenus utilisant le
    même matériel. Escalade comme le malus de famille."""
    equipement = _equipement_principal(exercise)
    if equipement is None:
        return 0
    repetitions = sum(
        1 for e in already_selected if _equipement_principal(e) == equipement
    )
    return -MALUS_PAR_REPETITION_EQUIPEMENT * repetitions if repetitions else 0


def calculate_format_penalty(exercise, already_selected):
    """Malus proportionnel au nombre d'exercices déjà retenus dans le même
    format de travail (force / hypertrophie / isolation / isométrique)."""
    try:
        format_exercice = _format_travail(exercise)
    except Exception:
        return 0
    repetitions = 0
    for e in already_selected:
        try:
            if _format_travail(e) == format_exercice:
                repetitions += 1
        except Exception:
            continue
    return -MALUS_PAR_REPETITION_FORMAT * repetitions if repetitions else 0


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
