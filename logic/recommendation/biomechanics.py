# -*- coding: utf-8 -*-
"""
Facteur "Compatibilité biomécanique individuelle" (8e facteur de scoring) +
facteur "Morphologie" (3e facteur) — resolution_11_points_bloquants.md
points 1 et 3.

Convention de catalogue (limite assumée, cf. explication donnée à
l'utilisateur) : le catalogue Exercise n'a pas encore été rempli (phase 2
préparée, non exécutée) et son schéma actuel n'a pas de champ dédié pour
distinguer un squat "libre" d'un squat guidé, ou un développé militaire
"strict" d'une variante machine. On approxime donc :
  - "squat profond libre" = pattern squat/front_squat SANS équipement "machine"
    (cohérent avec logic/exercises_db.py où pattern="squat" regroupe déjà
    barre/machine/haltère — la nuance "libre vs guidé" vient de l'équipement).
  - "développé militaire strict amplitude complète" = pattern developpe_militaire
    SANS équipement "machine", même logique.
Ces conventions devront être vérifiées/affinées quand le catalogue sera
réellement rempli (un champ `chain_type` dédié, déjà prévu dans
architecture_base_exercices.md mais pas dans le sous-ensemble critique de la
phase 2, réglerait cela plus proprement).
"""

PATTERNS_SQUAT_LIBRE = {"squat", "front_squat"}
PATTERNS_DEVELOPPE_MILITAIRE = {"developpe_militaire"}


def _is_squat_profond_libre(exercise):
    pattern = getattr(exercise, "pattern", None)
    equipment = getattr(exercise, "equipment", None) or []
    return pattern in PATTERNS_SQUAT_LIBRE and "machine" not in equipment


def _is_developpe_militaire_strict(exercise):
    pattern = getattr(exercise, "pattern", None)
    equipment = getattr(exercise, "equipment", None) or []
    return pattern in PATTERNS_DEVELOPPE_MILITAIRE and "machine" not in equipment


# --- Amplitude (exclusion dure "non", pénalité douce "avec difficulté") ----

def amplitude_hard_exclusion_reason(profile, exercise):
    """Retourne une raison d'exclusion (passe 1) si amplitude_squat/epaule
    vaut "non", uniquement sur le pattern précis concerné — jamais sur tout
    le movement_type (resolution_11_points_bloquants.md point 1)."""
    if getattr(profile, "amplitude_squat", None) == "Non, pas du tout" and _is_squat_profond_libre(exercise):
        return "amplitude_squat_non : squat profond libre exclu"
    if getattr(profile, "amplitude_epaule", None) == "Non, pas du tout" and _is_developpe_militaire_strict(exercise):
        return "amplitude_epaule_non : développé militaire strict exclu"
    return None


def _amplitude_penalty(profile, exercise):
    """Pénalité douce (passe 2) pour "avec difficulté" — "non" est déjà géré
    en exclusion dure et ne doit pas être re-pénalisé ici (l'exercice n'atteint
    de toute façon jamais le scoring dans ce cas)."""
    penalty = 0
    if getattr(profile, "amplitude_squat", None) == "Avec difficulté" and _is_squat_profond_libre(exercise):
        penalty -= 2
    if getattr(profile, "amplitude_epaule", None) == "Avec difficulté" and _is_developpe_militaire_strict(exercise):
        penalty -= 2
    return penalty


# --- Mobilité générale ------------------------------------------------------

def _mobilite_penalty(profile, exercise):
    mobilite = getattr(profile, "mobilite_generale", None)
    if mobilite is None:
        mobilite = 3  # valeur neutre (resolution_11_points_bloquants.md point 5)

    exigeant = (getattr(exercise, "stability_demand", None) == "eleve") or (
        (getattr(exercise, "technical_complexity", None) or 0) >= 4
    )
    if not exigeant:
        return 0
    if mobilite <= 2:
        return -3
    if mobilite >= 4:
        return 1
    return 0  # mobilite == 3, neutre


# --- Préférence de style de charge -----------------------------------------

def _style_charge_bonus(profile, exercise):
    style = getattr(profile, "preference_style_charge", None)
    if style == "Soulever lourd, peu de répétitions":
        if (getattr(exercise, "score_tension_mecanique", None) or 0) >= 7:
            return 2
    elif style == "Contrôler le mouvement, plus de répétitions":
        if (getattr(exercise, "score_contraction_max", None) or 0) >= 7:
            return 2
    return 0


def score_biomecanique_individuelle(profile, exercise):
    """8e facteur : somme des sous-règles mobilité + amplitude (pénalité douce
    uniquement, l'exclusion dure est traitée par filters.py en amont) +
    préférence de style de charge. La tolérance technique n'apparaît PAS ici :
    elle module la pénalité du facteur "Niveau" (cf. scoring.py et
    apply_tolerance_modulation ci-dessous), pas un score additif indépendant."""
    return _mobilite_penalty(profile, exercise) + _amplitude_penalty(profile, exercise) + _style_charge_bonus(profile, exercise)


# --- Tolérance technique (module la pénalité du facteur Niveau) ------------

def apply_tolerance_modulation(profile, penalite_brute):
    """penalite_effective = penalite_brute × (1 - (tolerance_technique-1)/4).
    Garde-fou : si aucun exercice maîtrisé, la réduction ne peut jamais
    dépasser 50% (resolution_11_points_bloquants.md point 1) — évite qu'une
    tolérance déclarée à 5/5 sans aucune expérience réelle annule toute
    prudence de complexité."""
    tolerance = getattr(profile, "tolerance_technique", None)
    if tolerance is None:
        tolerance = 3  # valeur neutre

    reduction = (tolerance - 1) / 4  # 0.0 (tolerance=1) a 1.0 (tolerance=5)

    exercices_maitrises = getattr(profile, "exercices_maitrises", None) or []
    aucun_maitrise = len(exercices_maitrises) == 0 or exercices_maitrises == ["Aucun de ces mouvements"]
    if aucun_maitrise:
        reduction = min(reduction, 0.5)

    return penalite_brute * (1 - reduction)


# --- Morphologie (3e facteur) ------------------------------------------------

_LONGUEUR_BRAS_MAP = {"Plutôt longs": "bras_longs", "Plutôt courts": "bras_courts"}
_LONGUEUR_JAMBES_MAP = {"Plutôt longues": "jambes_longues", "Plutôt courtes": "jambes_courtes"}
_LONGUEUR_BUSTE_MAP = {"Plutôt long": "buste_long", "Plutôt court": "buste_court"}
_LARGEUR_EPAULES_MAP = {"Plutôt larges": "epaules_larges", "Plutôt étroites": "epaules_etroites"}


def _activated_morphologie_keys(profile):
    """Les 9 clés possibles de `morphologie_adaptee` (architecture_base_
    exercices.md partie 2, resolution_11_points_bloquants.md point 3) ;
    seules celles correspondant à un trait réellement déclaré sont activées —
    jamais les deux extrêmes d'un même axe en même temps."""
    morpho = getattr(profile, "morphologie_declaree", None) or {}
    keys = []

    bras = _LONGUEUR_BRAS_MAP.get(morpho.get("longueur_bras"))
    if bras:
        keys.append(bras)
    jambes = _LONGUEUR_JAMBES_MAP.get(morpho.get("longueur_jambes"))
    if jambes:
        keys.append(jambes)
    buste = _LONGUEUR_BUSTE_MAP.get(morpho.get("longueur_buste"))
    if buste:
        keys.append(buste)
    epaules = _LARGEUR_EPAULES_MAP.get(morpho.get("largeur_epaules"))
    if epaules:
        keys.append(epaules)

    mobilite = getattr(profile, "mobilite_generale", None)
    if mobilite is not None and mobilite <= 2:
        keys.append("mobilite_faible")

    return keys


def score_morphologie(profile, exercise):
    """Score du facteur "Morphologie" : somme des valeurs de
    `exercise.morphologie_adaptee` pour les traits activés du profil."""
    adaptee = getattr(exercise, "morphologie_adaptee", None) or {}
    return sum(adaptee.get(k, 0) for k in _activated_morphologie_keys(profile))
