# -*- coding: utf-8 -*-
"""
Préparation de la migration du catalogue existant (logic/exercises_db.py)
vers le modèle Exercise (logic/models.py).

IMPORTANT : ce module ne migre RIEN. Il ne fait qu'exposer, sous forme de
fonctions pures (aucun accès à la base de données ici), la façon dont
chaque exercice actuel (dict `name`/`pattern`/`equip`/`kind`/`force`/`avoid`/
`priority`/`morpho`) se transformera en ligne `Exercise` le jour où la
migration réelle sera lancée (phase ultérieure, non planifiée dans ce
prompt). Objectif : que cette transformation soit déjà écrite, revue et
testable dès maintenant, plutôt que de l'improviser plus tard.

Ce que la transformation peut déduire automatiquement, sans intervention
humaine :
  - exercise_id (généré, stable, slug du nom)
  - name, pattern, muscle_principal, equipment (mapping direct)
  - family (via program_builder.FAMILY_MAP, avec repli sur le pattern)
  - unilateral (détecté par mot-clé dans le nom, à vérifier ensuite)

Ce que la transformation NE PEUT PAS déduire, et qui nécessitera un vrai
travail éditorial (cf. architecture_base_exercices.md, partie 1 et 3) :
  - movement_type (heuristique fournie à titre de brouillon uniquement)
  - muscles_secondaires, difficulty_level, joint_stress, technical_
    complexity, stability_demand, morphologie_adaptee, objectifs_adaptes,
    les scores hypertrophiques, substitutes, contre_indications
Ces champs sont volontairement laissés à une valeur neutre/vide dans la
sortie de `map_legacy_exercise`, pour qu'ils soient visuellement identifiables
comme "à remplir" plutôt que remplis par une supposition risquée.
"""
import re
import unicodedata


def _slugify(name):
    """"Développé couché barre" -> "developpe_couche_barre" """
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized


# Heuristique de brouillon uniquement (cf. docstring du module) : à valider
# exercice par exercice avant tout remplissage réel du catalogue.
_MOVEMENT_TYPE_HINTS = [
    (("developpe", "dips", "pompes", "close_grip_press", "skull_crusher", "pushdown", "overhead_extension", "kickback"), "push"),
    (("tirage", "rowing", "traction", "pull_over", "shrugs", "curl", "face_pull", "rear_delt", "y_raises"), "pull"),
    (("squat", "presse_cuisses", "leg_extension", "fente", "step_up"), "squat"),
    (("souleve", "hip_thrust", "good_morning", "leg_curl"), "hinge"),
    (("elevation", "upright_row", "cuban_press"), "rotation"),
    (("mollet",), "isometrique"),
    (("gainage", "planche", "abdo", "crunch"), "isometrique"),
]


def _guess_movement_type(pattern):
    pattern_low = pattern.lower()
    for keywords, movement_type in _MOVEMENT_TYPE_HINTS:
        if any(kw in pattern_low for kw in keywords):
            return movement_type
    return None  # nécessite une revue humaine, pas de supposition par défaut


def map_legacy_exercise(muscle_key, legacy):
    """Transforme un dict de logic.exercises_db.EXERCISES[muscle_key] en dict
    prêt à instancier logic.models.Exercise. Ne touche à aucune base de
    données — retourne un simple dict Python."""
    from logic.program_builder import FAMILY_MAP  # import tardif, lecture seule

    name = legacy["name"]
    pattern = legacy["pattern"]

    return {
        "exercise_id": _slugify(name),
        "name": name,
        "family": FAMILY_MAP.get(pattern, pattern),
        "pattern": pattern,
        "movement_type": _guess_movement_type(pattern),
        "equipment": [legacy["equip"]],
        "muscle_principal": muscle_key,
        "muscles_secondaires": [],
        "unilateral": "unilatéral" in name.lower() or "unilatérale" in name.lower(),
        "difficulty_level": None,
        "joint_stress": {tag: 3 for tag in legacy.get("avoid", [])},  # départ prudent : tag présent -> risque maximal, à affiner
        "technical_complexity": None,
        "stability_demand": None,
        "morphologie_adaptee": _morpho_to_dict(legacy.get("morpho", [])),
        "objectifs_adaptes": {"force": 3} if legacy.get("force") else {},
        "score_tension_mecanique": None,
        "score_contraction_max": None,
        "potentiel_hypertrophique": None,
        "substitutes": [],
        "contre_indications": [],
        "actif": True,
    }


def _morpho_to_dict(morpho_tags):
    """legacy `morpho: ["bras_longs"]` -> {"bras_longs": 2} (bonus de départ,
    à affiner par un vrai travail éditorial, cf. resolution_11_points_
    bloquants.md #3 pour les 9 clés cibles)."""
    return {tag: 2 for tag in morpho_tags}


def iter_legacy_exercises():
    """Générateur (muscle_key, dict_mappé) pour la totalité du catalogue
    actuel — utile pour vérifier la transformation (unicité des exercise_id,
    complétude) avant toute écriture réelle en base."""
    from logic.exercises_db import EXERCISES

    for muscle_key, exos in EXERCISES.items():
        for legacy in exos:
            yield muscle_key, map_legacy_exercise(muscle_key, legacy)
