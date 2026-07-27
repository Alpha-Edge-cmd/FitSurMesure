# -*- coding: utf-8 -*-
"""
Couche d'enrichissement éditorial du catalogue (phase 13/16) : transforme
chaque exercice de `logic/exercises_db.EXERCISES` (catalogue legacy, dicts
name/pattern/equip/kind/force/avoid/priority/morpho) en une fiche `Exercise`
COMPLÈTE (tous les champs du modèle SQLAlogic/models.py, phase 2), prête à
être validée puis importée en base.

Ne modifie ni ne redéfinit aucune règle de scoring/filtrage déjà validée
(scoring.py, filters.py, selector.py, fallback.py, workout_generator.py,
prescription.py, program_service.py — inchangés). Réutilise en lecture
seule : `exercise_migration.map_legacy_exercise` (phase 2, pour les champs
"sûrs" : exercise_id/name/family/pattern/equipment/muscle_principal/
unilateral), `program_builder.FAMILY_MAP`, et
`recommendation.objectives.OBJECTIVE_KEYS` (source unique des 5 clés
d'objectif valides, pas de duplication de cette liste).

Limite assumée et documentée (cf. consigne : "aucune valeur inventée
silencieusement") : le catalogue legacy n'a jamais encodé difficulty_level,
technical_complexity, stability_demand, muscles_secondaires, substitutes,
contre_indications, les 3 scores hypertrophiques, ni un vecteur objectifs_
adaptes complet (seul un flag "force" booléen existe). Ces champs sont donc
dérivés par des règles simples et documentées ci-dessous (à partir des deux
seuls signaux éditoriaux réels du legacy : `kind` compose/isolation et
`equip`), PAS par une recherche individuelle par exercice — chaque fiche
produite porte `"needs_review": true` pour signaler que ces valeurs sont un
premier jet à valider par un humain, jamais une vérité déjà établie.
"""
from logic.exercise_migration import map_legacy_exercise

# Source unique des 5 clés d'objectif valides (phase 6) — pas de duplication.
from logic.recommendation.objectives import OBJECTIVE_KEYS as OBJECTIFS_VALIDES

# Les 9 clés validées de `morphologie_adaptee` (resolution_points_bloquants_v2.md
# point 3 ; cf. biomechanics.py, phase 6, jamais modifié ici). Seules 4 ont un
# signal legacy réel (tags "morpho" existants) ; les 5 autres n'ont jamais été
# renseignées dans le catalogue actuel et resteront donc absentes (= neutres).
MORPHOLOGIE_KEYS_VALIDES = (
    "bras_longs", "bras_courts", "jambes_longues", "jambes_courtes",
    "buste_long", "buste_court", "epaules_larges", "epaules_etroites",
    "mobilite_faible",
)

# Tags `avoid` du catalogue legacy qui désignent une VRAIE zone anatomique
# (cf. logic/exercises_db.py, docstring "Tags possibles"), traduits vers la
# convention courte de `Exercise.joint_stress` (cf. filters.
# ZONE_LABEL_TO_JOINT_STRESS_KEY, phase 6 : epaule/dos_lombaire/genou/
# cheville/poignet). "talon" (legacy) correspond à la même question
# utilisateur que "cheville" ("Chevilles / talons") -> mappé dessus.
_ZONE_AVOID_VERS_JOINT_STRESS = {
    "epaule": "epaule",
    "dos_lombaire": "dos_lombaire",
    "genou": "genou",
    "talon": "cheville",
    "poignet": "poignet",
}

# Les autres tags `avoid` du legacy ("cant_do_pullups", "cant_do_dips",
# "squat_libre_non", "deadlift_barre_non") NE sont PAS des zones anatomiques :
# les deux premiers décrivent une incapacité déclarée par l'utilisateur (un
# concept legacy sans équivalent dans le moteur V2 à ce jour, cf. limites en
# fin de phase) ; les deux derniers sont déjà couverts, en mieux, par le
# mécanisme `biomechanics.amplitude_hard_exclusion_reason` (phase 6, pattern +
# équipement, pas un tag). Volontairement exclus de la conversion joint_stress
# pour ne pas polluer ce champ avec des clés non anatomiques.

_PATTERNS_TECHNIQUES_AVANCES = {"squat", "front_squat", "rdl", "developpe_militaire"}


def _difficulty_level(equip, kind, pattern):
    """Heuristique documentée (aucune donnée legacy directe) : le matériel
    guidé/assisté est jugé plus accessible ; un mouvement composé libre à la
    barre sur un pattern technique reconnu est jugé avancé. Toujours
    accompagné de `needs_review: true` au niveau de la fiche."""
    if equip in ("machine", "elastique"):
        return "debutant"
    if equip == "barre" and kind == "compose" and pattern in _PATTERNS_TECHNIQUES_AVANCES:
        return "avance"
    return "intermediaire"


def _technical_complexity(equip, kind):
    """1-5, heuristique documentée à partir de equip/kind (mêmes limites que
    `_difficulty_level`)."""
    if equip == "barre" and kind == "compose":
        return 4
    if equip == "barre":
        return 3
    if equip == "haltere" and kind == "compose":
        return 3
    if equip in ("machine", "elastique"):
        return 2
    if equip == "poids_du_corps" and kind == "compose":
        return 3
    return 2


def _stability_demand(equip, kind, unilateral):
    """faible/modere/eleve — conserve le type STRING déjà validé du modèle
    Exercise (phase 2) et consommé tel quel par biomechanics.py/
    exercise_order.py (phases 6/8) : ne réinterprète PAS ce champ comme une
    échelle numérique 1-5, cf. "limites" en fin de phase pour la justification
    de cet écart assumé avec l'énoncé littéral de la consigne."""
    if unilateral:
        return "eleve"
    if equip == "machine":
        return "faible"
    if equip in ("barre", "haltere") and kind == "compose":
        return "modere"
    return "faible"


def _objectifs_adaptes(kind, force_flag):
    """Vecteur 0-10 sur les 5 clés validées, dérivé du seul signal legacy
    réel disponible (kind compose/isolation, flag force) — première
    différenciation utile du catalogue, pas une mesure scientifique."""
    if kind == "compose":
        return {
            "force": 6 if force_flag else 4,
            "hypertrophie": 7,
            "endurance_musculaire": 3,
            "perte_de_gras": 4,
            "explosivite": 4 if force_flag else 2,
        }
    return {
        "force": 2,
        "hypertrophie": 7,
        "endurance_musculaire": 5,
        "perte_de_gras": 4,
        "explosivite": 1,
    }


def _scores_hypertrophiques(kind):
    """(tension_mecanique, contraction_max, potentiel_hypertrophique), 1-10,
    heuristique compose/isolation classique (mouvements composés = tension
    mécanique plus élevée ; isolation = contraction de pointe plus élevée) —
    documentée, pas calculée à partir d'une vraie mesure biomécanique."""
    if kind == "compose":
        return 7, 5, 7
    return 4, 7, 6


def _joint_stress_depuis_avoid(avoid_tags):
    """Ne garde que les tags `avoid` correspondant à une vraie zone
    anatomique (cf. `_ZONE_AVOID_VERS_JOINT_STRESS`) ; départ prudent
    "présent -> risque maximal (3)", à affiner par une vraie revue
    éditoriale (même logique de départ que `exercise_migration.py`, phase 2,
    ici restreinte aux tags réellement anatomiques)."""
    return {
        _ZONE_AVOID_VERS_JOINT_STRESS[tag]: 3
        for tag in (avoid_tags or [])
        if tag in _ZONE_AVOID_VERS_JOINT_STRESS
    }


def _morphologie_depuis_tags(morpho_tags):
    """Ne garde que les tags figurant parmi les 9 clés validées (les 4 ayant
    un signal legacy réel) ; bonus de départ (2), à affiner."""
    return {tag: 2 for tag in (morpho_tags or []) if tag in MORPHOLOGIE_KEYS_VALIDES}


def enrich_exercise(legacy_exercise):
    """enrich_exercise(legacy_exercise) -> dict "fiche Exercise" complète.

    `legacy_exercise` : dict fusionnant UNE entrée de
    `logic.exercises_db.EXERCISES[muscle_key]` avec sa clé `"muscle_key"`
    (cf. `iter_enriched_exercises` ci-dessous, qui construit ce dict pour
    tout le catalogue) — nécessaire car le catalogue legacy est organisé par
    muscle et une entrée seule ne porte pas cette information.

    Retourne une fiche portant TOUS les champs obligatoires de la consigne
    (identité, classification, biomécanique, objectifs, autres), plus
    `"needs_review": true` (aucun champ éditorial de cette fiche ne provient
    d'une vraie revue humaine à ce stade, cf. docstring du module)."""
    muscle_key = legacy_exercise["muscle_key"]
    base = map_legacy_exercise(muscle_key, legacy_exercise)

    equip = legacy_exercise.get("equip")
    kind = legacy_exercise.get("kind")
    pattern = legacy_exercise.get("pattern", "")
    unilateral = base["unilateral"]

    tension, contraction, potentiel = _scores_hypertrophiques(kind)

    fiche = dict(base)
    fiche.update({
        "muscles_secondaires": [],  # aucun signal legacy -> neutre, needs_review
        "difficulty_level": _difficulty_level(equip, kind, pattern),
        "joint_stress": _joint_stress_depuis_avoid(legacy_exercise.get("avoid")),
        "technical_complexity": _technical_complexity(equip, kind),
        "stability_demand": _stability_demand(equip, kind, unilateral),
        "morphologie_adaptee": _morphologie_depuis_tags(legacy_exercise.get("morpho")),
        "objectifs_adaptes": _objectifs_adaptes(kind, bool(legacy_exercise.get("force"))),
        "score_tension_mecanique": tension,
        "score_contraction_max": contraction,
        "potentiel_hypertrophique": potentiel,
        "substitutes": [],  # aucun signal legacy -> neutre, needs_review
        "contre_indications": [],  # concept distinct de joint_stress, jamais renseigné côté legacy
        "actif": True,
        "needs_review": True,
    })
    return fiche


def iter_enriched_exercises():
    """Générateur de fiches enrichies pour la TOTALITÉ du catalogue legacy
    actuel (`logic.exercises_db.EXERCISES`) — utilisé pour produire
    `data/exercise_enrichment.json` (section 2 de la consigne)."""
    from logic.exercises_db import EXERCISES

    for muscle_key, exos in EXERCISES.items():
        for legacy in exos:
            yield enrich_exercise(dict(legacy, muscle_key=muscle_key))
