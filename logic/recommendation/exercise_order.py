# -*- coding: utf-8 -*-
"""
Ordre des exercices AU SEIN d'une séance (phase 8/16, section 6 de la
consigne) : ne décide rien du choix des exercices (cf. selector.py) ni de
leur nombre (cf. volume.py), seulement dans quel ordre les exécuter.

Classification en 4 paliers, cohérente avec l'exemple fourni dans la
consigne ("Jambes : squat/presse, hinge, unilatéral, isolation quadriceps,
mollets") :
  1. principal    : mouvement composé, bilatéral (squat/presse, développé
                    principal, tirage vertical...).
  2. secondaire    : mouvement composé mais unilatéral (fentes, RDL unilatéral,
                    développé unilatéral...) ou variante secondaire.
  3. isolation     : mouvement non composé (mono-articulaire).
  4. finisseur     : muscles à faible coût de fatigue / travail complémentaire
                    (mollets, abdos, avant-bras dans l'exemple fourni).

Aucun barème chiffré n'a été validé pour cette classification dans les
documents de conception (contrairement aux facteurs de scoring.py) : c'est
une interprétation documentée de l'exemple donné dans cette phase, pas une
règle métier déjà tranchée en amont.
"""

# Cf. `Exercise.movement_type` (logic/models.py) : push/pull/squat/hinge/
# lunge/carry/rotation/isometrique. Tous sauf rotation/isometrique/None sont
# considérés "composés" (patterns polyarticulaires).
COMPOUND_MOVEMENT_TYPES = {"squat", "hinge", "push", "pull", "lunge", "carry"}

# Muscles à faible coût de fatigue / travail complémentaire habituellement
# placé en fin de séance (cf. exemple "mollets" de la consigne). Liste
# volontairement restreinte et documentée, à étendre si besoin.
FINISHER_MUSCLES = {"mollets", "abdos", "avant_bras"}

TIER_PRINCIPAL = "principal"
TIER_SECONDAIRE = "secondaire"
TIER_ISOLATION = "isolation"
TIER_FINISSEUR = "finisseur"

TIER_ORDER = {TIER_PRINCIPAL: 0, TIER_SECONDAIRE: 1, TIER_ISOLATION: 2, TIER_FINISSEUR: 3}


def classify_exercise(exercise):
    """Retourne l'un des 4 paliers ci-dessus pour un exercice donné. Ne
    lève jamais d'exception sur un catalogue incomplet (repli "isolation" si
    `movement_type` est absent/inconnu, choix conservateur : mieux vaut sous-
    prioriser un exercice mal renseigné que le traiter à tort comme un
    mouvement principal lourd)."""
    muscle = getattr(exercise, "muscle_principal", None)
    if muscle in FINISHER_MUSCLES:
        return TIER_FINISSEUR

    movement_type = getattr(exercise, "movement_type", None)
    if movement_type in COMPOUND_MOVEMENT_TYPES:
        return TIER_SECONDAIRE if getattr(exercise, "unilateral", False) else TIER_PRINCIPAL

    return TIER_ISOLATION


def _fatigue_cost_proxy(exercise):
    """`fatigue_cost` par exercice n'existe pas encore au catalogue (même
    limitation déjà documentée dans fatigue.py/scoring.py pour le facteur
    "Fatigue" du scoring) : `technical_complexity` sert de signal indirect
    documenté (un mouvement technique/exigeant coûte davantage en fatigue
    nerveuse/attentionnelle qu'un mouvement simple), utilisé uniquement en
    départage, jamais comme critère principal."""
    return getattr(exercise, "technical_complexity", None) or 0


def sort_exercises_for_workout(scored_exercises):
    """Trie une liste de candidats (dicts `{"exercise": Exercise, "score": float,
    ...}`, même format que `selector.select_exercises`) selon les règles de la
    section 6 : (1) palier de mouvement (principal > secondaire > isolation >
    finisseur), (2) score décroissant au sein d'un même palier, (3) coût de
    fatigue estimé croissant en cas d'égalité de score. Le tri primaire par
    palier garantit par construction qu'un finisseur n'est jamais placé avant
    un mouvement principal, quel que soit son score."""

    def sort_key(item):
        tier = TIER_ORDER[classify_exercise(item["exercise"])]
        return (tier, -item["score"], _fatigue_cost_proxy(item["exercise"]))

    return sorted(scored_exercises, key=sort_key)
