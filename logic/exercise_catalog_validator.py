# -*- coding: utf-8 -*-
"""
Validation du catalogue enrichi (phase 13/16) : garantit qu'aucune fiche
incohérente ne puisse être importée en base (`exercise_catalog_import.py`
appelle ce module AVANT toute écriture). Ne redéfinit aucune règle de
scoring/filtrage — ce module ne fait que vérifier la FORME des données,
jamais leur interprétation par le moteur (scoring.py, filters.py, etc.,
tous inchangés).

`data/exercise_enrichment.json` est un fichier ÉDITORIAL versionné avec le
code (comme `logic/exercises_db.py`), pas une donnée runtime mutable comme
`data/orders.json`/`data/promo_codes.json` : son chemin est donc résolu par
rapport à la racine du projet, INDÉPENDAMMENT de `DATA_DIR`
(`logic/data_dir.py`, réservé au stockage runtime sur disque persistant en
production) — utiliser `get_data_dir()` ici pointerait vers le mauvais
dossier en production (le disque persistant ne contient pas ce fichier).
"""
import json
import os

from logic.exercise_catalog_enrichment import MORPHOLOGIE_KEYS_VALIDES, OBJECTIFS_VALIDES

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ENRICHMENT_PATH = os.path.join(PROJECT_ROOT, "data", "exercise_enrichment.json")

CHAMPS_OBLIGATOIRES = (
    "exercise_id", "name", "family", "pattern", "movement_type", "equipment",
    "muscle_principal", "muscles_secondaires", "unilateral", "difficulty_level",
    "joint_stress", "technical_complexity", "stability_demand", "morphologie_adaptee",
    "objectifs_adaptes", "score_tension_mecanique", "score_contraction_max",
    "potentiel_hypertrophique", "substitutes", "contre_indications", "actif",
)

DIFFICULTY_LEVELS_VALIDES = {"debutant", "intermediaire", "avance", None}

# Choix documenté : le modèle Exercise (phase 2, inchangé) stocke
# `stability_demand` comme une chaîne faible/modere/eleve, déjà consommée
# telle quelle par biomechanics.py (phase 6) et exercise_order.py (phase 8).
# La consigne de cette phase parle de "stability_demand entre 1 et 5", ce qui
# entrerait en conflit avec ce type déjà validé et casserait silencieusement
# ces deux modules si on le réinterprétait en entier. On valide donc ici la
# forme RÉELLEMENT exploitée par le moteur (les 3 valeurs de chaîne), pas la
# formulation littérale de la consigne — cf. "limites" fournies à l'utilisateur.
STABILITY_DEMAND_VALIDES = {"faible", "modere", "eleve", None}

JOINT_STRESS_MIN, JOINT_STRESS_MAX = 0, 3
TECHNICAL_COMPLEXITY_MIN, TECHNICAL_COMPLEXITY_MAX = 1, 5
SCORE_MIN, SCORE_MAX = 0, 10  # objectifs_adaptes (valeurs) + les 3 scores hypertrophiques


def _erreur(exercise_id, message):
    return {"exercise_id": exercise_id, "message": message}


def validate_exercise(fiche):
    """Valide UNE fiche (dict). Retourne (erreurs, avertissements) — deux
    listes de chaînes. Une fiche avec au moins une erreur ne doit jamais
    être importée (cf. `exercise_catalog_import.py`) ; les avertissements
    n'empêchent pas l'import mais signalent un point à surveiller."""
    erreurs = []
    avertissements = []
    exercise_id = fiche.get("exercise_id", "?")

    for champ in CHAMPS_OBLIGATOIRES:
        if champ not in fiche:
            erreurs.append(f"champ obligatoire manquant : {champ}")

    if erreurs:
        # Sans les champs de base, les vérifications suivantes n'ont pas de
        # sens (risque de KeyError) — on s'arrête ici pour cette fiche.
        return erreurs, avertissements

    # --- unilateral=true uniquement pour mouvements réellement unilatéraux ---
    # Signal disponible : le nom de l'exercice (même heuristique que
    # exercise_migration.map_legacy_exercise, phase 2 — pas de second critère
    # indépendant disponible). Incohérence si `unilateral=True` mais le nom
    # ne contient aucun indice unilatéral : avertissement (pas une erreur
    # bloquante, un faux positif nominal reste possible).
    nom = (fiche.get("name") or "").lower()
    if fiche["unilateral"] and not any(mot in nom for mot in ("unilatéral", "unilatérale", "unilateral")):
        avertissements.append("unilateral=true sans indice unilatéral dans le nom : à vérifier")

    # --- joint_stress : valeurs entre 0 et 3 ---
    joint_stress = fiche["joint_stress"]
    if not isinstance(joint_stress, dict):
        erreurs.append("joint_stress doit être un dict")
    else:
        for zone, valeur in joint_stress.items():
            if not isinstance(valeur, (int, float)) or not (JOINT_STRESS_MIN <= valeur <= JOINT_STRESS_MAX):
                erreurs.append(f"joint_stress[{zone}]={valeur!r} hors plage [{JOINT_STRESS_MIN}, {JOINT_STRESS_MAX}]")

    # --- technical_complexity entre 1 et 5 ---
    tc = fiche["technical_complexity"]
    if tc is not None and (not isinstance(tc, (int, float)) or not (TECHNICAL_COMPLEXITY_MIN <= tc <= TECHNICAL_COMPLEXITY_MAX)):
        erreurs.append(f"technical_complexity={tc!r} hors plage [{TECHNICAL_COMPLEXITY_MIN}, {TECHNICAL_COMPLEXITY_MAX}]")

    # --- stability_demand ---
    if fiche["stability_demand"] not in STABILITY_DEMAND_VALIDES:
        erreurs.append(f"stability_demand={fiche['stability_demand']!r} invalide (attendu : faible/modere/eleve)")

    # --- difficulty_level ---
    if fiche["difficulty_level"] not in DIFFICULTY_LEVELS_VALIDES:
        erreurs.append(f"difficulty_level={fiche['difficulty_level']!r} invalide (attendu : debutant/intermediaire/avance)")

    # --- scores objectifs entre 0 et 10 ---
    for champ_score in ("score_tension_mecanique", "score_contraction_max", "potentiel_hypertrophique"):
        valeur = fiche[champ_score]
        if valeur is not None and (not isinstance(valeur, (int, float)) or not (SCORE_MIN <= valeur <= SCORE_MAX)):
            erreurs.append(f"{champ_score}={valeur!r} hors plage [{SCORE_MIN}, {SCORE_MAX}]")

    # --- morphologie_adaptee : uniquement les 9 clés validées ---
    morphologie = fiche["morphologie_adaptee"]
    if not isinstance(morphologie, dict):
        erreurs.append("morphologie_adaptee doit être un dict")
    else:
        cles_invalides = set(morphologie) - set(MORPHOLOGIE_KEYS_VALIDES)
        if cles_invalides:
            erreurs.append(f"morphologie_adaptee contient des clés invalides : {sorted(cles_invalides)}")

    # --- objectifs_adaptes : uniquement les 5 clés validées + valeurs 0-10 ---
    objectifs = fiche["objectifs_adaptes"]
    if not isinstance(objectifs, dict):
        erreurs.append("objectifs_adaptes doit être un dict")
    else:
        cles_invalides = set(objectifs) - set(OBJECTIFS_VALIDES)
        if cles_invalides:
            erreurs.append(f"objectifs_adaptes contient des clés invalides : {sorted(cles_invalides)}")
        for cle, valeur in objectifs.items():
            if not isinstance(valeur, (int, float)) or not (SCORE_MIN <= valeur <= SCORE_MAX):
                erreurs.append(f"objectifs_adaptes[{cle}]={valeur!r} hors plage [{SCORE_MIN}, {SCORE_MAX}]")

    # --- needs_review manquant : avertissement (pas obligatoire dans le schéma
    # Exercise lui-même, mais requis par la consigne éditoriale de cette phase) ---
    if "needs_review" not in fiche:
        avertissements.append("champ 'needs_review' absent (attendu par la consigne éditoriale de la phase 13)")

    return erreurs, avertissements


def _charger_fiches(source):
    if source is None:
        source = DEFAULT_ENRICHMENT_PATH
    if isinstance(source, str):
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("exercises", [])
    return list(source)  # déjà une liste de fiches (tests, appels directs)


def validate_catalog(source=None):
    """validate_catalog(source=None) : `source` peut être un chemin JSON
    (repli sur `DEFAULT_ENRICHMENT_PATH`) ou directement une liste de fiches
    (dicts) déjà chargées — pratique pour les tests, sans dépendre du disque.

    Retourne {"erreurs": [...], "avertissements": [...], "a_revoir": [...],
    "exercise_ids_valides": [...]} :
      - "erreurs"  : liste de {"exercise_id", "message"} — un exercice avec
        au moins une erreur ne doit jamais être importé.
      - "avertissements" : idem, mais n'empêche pas l'import.
      - "a_revoir" : exercise_id des fiches marquées `needs_review: true`
        (valides ou non).
      - "exercise_ids_valides" : exercise_id des fiches SANS erreur bloquante
        (celles que `exercise_catalog_import.py` importera)."""
    fiches = _charger_fiches(source)

    erreurs = []
    avertissements = []
    a_revoir = []
    exercise_ids_valides = []

    ids_vus = {}
    for fiche in fiches:
        exercise_id = fiche.get("exercise_id", "?")
        erreurs_fiche, avertissements_fiche = validate_exercise(fiche)

        # Unicité de exercise_id : erreur bloquante si doublon (jamais deux
        # fiches pour la même clé primaire, cf. Exercise.exercise_id).
        if exercise_id in ids_vus:
            erreurs_fiche = list(erreurs_fiche) + [f"exercise_id en double : {exercise_id!r}"]
        ids_vus[exercise_id] = ids_vus.get(exercise_id, 0) + 1

        erreurs.extend(_erreur(exercise_id, m) for m in erreurs_fiche)
        avertissements.extend(_erreur(exercise_id, m) for m in avertissements_fiche)

        if fiche.get("needs_review"):
            a_revoir.append(exercise_id)

        if not erreurs_fiche:
            exercise_ids_valides.append(exercise_id)

    return {
        "erreurs": erreurs,
        "avertissements": avertissements,
        "a_revoir": a_revoir,
        "exercise_ids_valides": exercise_ids_valides,
    }
