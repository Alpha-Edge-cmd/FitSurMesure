# -*- coding: utf-8 -*-
"""
Mapping objectif utilisateur -> vecteur interne `objectifs_adaptes`
(resolution_11_points_bloquants.md, point 2 — valeurs reprises telles quelles,
aucune réinterprétation).
"""

OBJECTIVE_KEYS = ("force", "hypertrophie", "endurance_musculaire", "perte_de_gras", "explosivite")

# Vecteurs par objectif principal (somme = 1.0 pour chacun).
PRINCIPAL_VECTORS = {
    "Prise de muscle": {
        "force": 0.30, "hypertrophie": 0.70, "endurance_musculaire": 0, "perte_de_gras": 0, "explosivite": 0,
    },
    "Perte de gras": {
        "force": 0, "hypertrophie": 0.10, "endurance_musculaire": 0.30, "perte_de_gras": 0.60, "explosivite": 0,
    },
    "Recomposition (sec + muscle)": {
        "force": 0.20, "hypertrophie": 0.40, "endurance_musculaire": 0, "perte_de_gras": 0.40, "explosivite": 0,
    },
    "Condition physique générale": {
        "force": 0.30, "hypertrophie": 0.30, "endurance_musculaire": 0.40, "perte_de_gras": 0, "explosivite": 0,
    },
    "Performance / explosivité": {
        "force": 0.40, "hypertrophie": 0.10, "endurance_musculaire": 0, "perte_de_gras": 0, "explosivite": 0.50,
    },
}

# Repli neutre pour un objectif_principal manquant/non reconnu (profil incomplet) :
# le vecteur "Condition physique générale" est le plus équilibré des cinq, donc le
# moins susceptible de biaiser fortement un profil dont on ne sait rien encore.
DEFAULT_PRINCIPAL_VECTOR = PRINCIPAL_VECTORS["Condition physique générale"]

# Objectifs secondaires : seul "Gagner en force" a un vecteur propre (resolution_
# 11_points_bloquants.md point 2). Les autres options ("Améliorer ma mobilité",
# "Corriger un déséquilibre postural", "Préparer un événement...") agissent sur
# d'autres mécanismes (facteur biomécanique, ciblage postural) et ne participent
# pas à ce vecteur objectif — ce n'est pas un oubli, c'est la règle déjà validée.
SECONDARY_VECTORS = {
    "Gagner en force": {
        "force": 1.0, "hypertrophie": 0, "endurance_musculaire": 0, "perte_de_gras": 0, "explosivite": 0,
    },
}

PRINCIPAL_WEIGHT = 0.75
SECONDARY_WEIGHT = 0.25

# Objectifs multiples (prompt final, hors 24 phases) : union des vecteurs
# principaux + secondaires porteurs d'un vecteur ("Gagner en force" est le
# seul objectif secondaire à en avoir un, cf. SECONDARY_VECTORS ci-dessus) —
# tous les objectifs qu'un utilisateur peut cocher simultanément dans le
# nouveau champ "objectifs" (checkbox-group) du questionnaire.
OBJECTIFS_VECTORS_TOUS = {**PRINCIPAL_VECTORS, **SECONDARY_VECTORS}


def _vecteur_compose_depuis_liste(objectifs_multiples):
    """Moyenne simple (poids égal) des vecteurs de chaque objectif VALIDE de
    la liste (ignore silencieusement toute valeur non reconnue, ex: options
    d'objectif secondaire sans vecteur comme "Améliorer ma mobilité", qui
    agissent sur d'autres mécanismes, pas sur ce vecteur). Retourne None si
    aucun objectif de la liste n'a de vecteur connu (repli au niveau de
    l'appelant sur le comportement principal/secondaire existant)."""
    vecteurs = [OBJECTIFS_VECTORS_TOUS[o] for o in objectifs_multiples if o in OBJECTIFS_VECTORS_TOUS]
    if not vecteurs:
        return None
    n = len(vecteurs)
    return {k: sum(v[k] for v in vecteurs) / n for k in OBJECTIVE_KEYS}


def get_objective_vector(profile):
    """Retourne le vecteur final {force, hypertrophie, endurance_musculaire,
    perte_de_gras, explosivite} pour ce profil.

    Priorité (prompt final, hors 24 phases) : si le questionnaire a envoyé
    plusieurs objectifs cochés simultanément (`variables_json["objectifs"]`,
    liste — nouveau champ "checkbox-group" du questionnaire, cf. static/
    script.js), on calcule un vecteur composite à poids égal sur TOUS les
    objectifs reconnus de cette liste. Sinon (ancien format, tous les
    profils/tests existants), comportement STRICTEMENT inchangé : objectif
    principal + secondaire pondérés 0.75/0.25."""
    variables = getattr(profile, "variables_json", None) or {}
    objectifs_multiples = variables.get("objectifs")
    if isinstance(objectifs_multiples, list) and objectifs_multiples:
        vecteur_compose = _vecteur_compose_depuis_liste(objectifs_multiples)
        if vecteur_compose is not None:
            return vecteur_compose

    principal = PRINCIPAL_VECTORS.get(
        getattr(profile, "objectif_principal", None), DEFAULT_PRINCIPAL_VECTOR
    )

    objectif_secondaire = getattr(profile, "objectif_secondaire", None)
    secondaire = SECONDARY_VECTORS.get(objectif_secondaire) if objectif_secondaire else None

    if not secondaire:
        return dict(principal)

    return {
        k: PRINCIPAL_WEIGHT * principal[k] + SECONDARY_WEIGHT * secondaire[k]
        for k in OBJECTIVE_KEYS
    }


def score_objectif_exercise(profile, exercise):
    """Score brut du facteur "Objectif" pour un exercice donné : produit
    scalaire entre le vecteur utilisateur et `exercise.objectifs_adaptes`
    (dict potentiellement vide si le catalogue n'est pas encore rempli pour
    cet exercice, auquel cas le score vaut simplement 0 — jamais d'exception)."""
    vector = get_objective_vector(profile)
    adaptes = getattr(exercise, "objectifs_adaptes", None) or {}
    return sum(vector[k] * adaptes.get(k, 0) for k in OBJECTIVE_KEYS)
