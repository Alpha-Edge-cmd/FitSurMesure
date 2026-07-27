# -*- coding: utf-8 -*-
"""
Couche de normalisation questionnaire -> ProfileSnapshot (phase 4/16).

Rôle strictement limité à la VALIDATION, au NETTOYAGE et à la NORMALISATION
des données brutes du questionnaire (actuel ou futur). Explicitement hors
périmètre de ce module (contrainte de cette phase) :
  - aucune logique de scoring ;
  - aucune sélection d'exercice ;
  - aucune interprétation biomécanique.
Les "valeurs neutres" appliquées ici pour les variables moteur absentes sont
des règles de NETTOYAGE DE DONNÉES déjà actées dans resolution_11_points_
bloquants.md (point 5) — pas une décision de scoring inventée à cette phase.
Le moteur (phases futures) reste libre d'utiliser ces valeurs neutres comme
il l'a défini ; ce module se contente de garantir qu'un ProfileSnapshot n'a
jamais de valeur manquante là où une valeur neutre a été explicitement actée.

Le questionnaire actuel (static/script.js) n'envoie pas encore la plupart des
"variables moteur" ciblées par questionnaire_optimise.md (mobilité,
amplitude, tolérance technique, préférence de charge/matériel, disponibilité
réelle...). Ce module fonctionne correctement à la fois avec les données
d'AUJOURD'HUI (qui ne contiennent pas ces clés) et avec celles du FUTUR
questionnaire (phase 5+), sans qu'une seule ligne de ce fichier n'ait besoin
de changer entre les deux : toute clé absente est traitée exactement comme
une clé future pas encore posée à l'utilisateur.
"""
from logic.db import db
from logic.models import ProfileSnapshot

# --- Ensembles de valeurs autorisées (validation, pas d'interprétation) -----

NIVEAUX_MUSCULATION = {
    "Débutant complet", "Quelques mois d'expérience", "Intermédiaire", "Avancé",
}
OBJECTIFS_PRINCIPAUX = {
    "Prise de muscle", "Perte de gras", "Recomposition (sec + muscle)",
    "Performance / explosivité", "Condition physique générale",
}
# Objectifs secondaires possibles (questionnaire_optimise.md catégorie 1) ;
# "Aucun" et toute valeur vide sont normalisés vers None (voir plus bas).
OBJECTIFS_SECONDAIRES = {
    "Gagner en force", "Améliorer ma mobilité",
    "Corriger un déséquilibre postural", "Préparer un événement (compétition, vacances...)",
}
AMPLITUDES = {"Oui, facilement", "Avec difficulté", "Non, pas du tout"}
STYLES_CHARGE = {
    "Soulever lourd, peu de répétitions",
    "Contrôler le mouvement, plus de répétitions",
    "Un mix des deux",
}
MATERIELS_PREFERES = {"Barres libres", "Haltères", "Machines guidées", "Pas de préférence"}
LONGUEURS = {"Je ne sais pas", "Plutôt courts", "Moyens", "Plutôt longs",
             "Plutôt courtes", "Équilibrées", "Plutôt longues",
             # Formes au masculin singulier, pour la future question buste
             # (questionnaire_optimise.md catégorie 2, pas encore dans l'UI).
             "Plutôt court", "Équilibré", "Plutôt long"}

# Valeurs neutres pour variable manquante/invalide — cf. resolution_11_points_
# bloquants.md, point 5, table complète.
DEFAUT_MOBILITE_GENERALE = 3
DEFAUT_AMPLITUDE = "Avec difficulté"
DEFAUT_TOLERANCE_TECHNIQUE = 3
DEFAUT_STYLE_CHARGE = "Un mix des deux"
DEFAUT_MATERIEL_PREFERE = "Pas de préférence"


def _clean_str(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _to_float(value, field_name):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Champ '{field_name}' manquant ou invalide (valeur reçue : {value!r}).")


def _to_int_in_range(value, low, high, default):
    """Retourne un entier dans [low, high], ou `default` si absent/invalide —
    jamais d'exception ici : une variable moteur optionnelle mal renseignée
    doit retomber sur sa valeur neutre, pas bloquer la génération."""
    if value is None or value == "":
        return default
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return default
    if ivalue < low or ivalue > high:
        return default
    return ivalue


def _from_allowed(value, allowed, default):
    value = _clean_str(value)
    if value is None or value not in allowed:
        return default
    return value


def normalize_questionnaire_data(raw):
    """Transforme un dict brut de réponses questionnaire (actuel ou futur) en
    dict propre, aux clés alignées sur les colonnes de ProfileSnapshot.
    Lève ValueError si un champ obligatoire cœur (poids/taille/sexe/niveau/
    objectif) est manquant ou invalide. Ne lève jamais d'exception pour une
    variable moteur optionnelle : celles-ci retombent sur leur valeur neutre
    documentée."""
    raw = raw or {}

    # --- Informations générales (obligatoires) -----------------------------
    poids = _to_float(raw.get("poids"), "poids")
    taille = _to_float(raw.get("taille"), "taille")
    sexe = _clean_str(raw.get("sexe"))
    if sexe not in {"Homme", "Femme"}:
        raise ValueError(f"Champ 'sexe' manquant ou invalide (valeur reçue : {raw.get('sexe')!r}).")

    niveau_musculation = _clean_str(raw.get("niveau_musculation"))
    if niveau_musculation not in NIVEAUX_MUSCULATION:
        raise ValueError(
            f"Champ 'niveau_musculation' manquant ou invalide (valeur reçue : {raw.get('niveau_musculation')!r})."
        )

    # Objectifs multiples (prompt final, hors 24 phases) : le questionnaire
    # peut désormais envoyer une liste `objectifs` (checkboxes, plusieurs
    # objectifs cochés simultanément) au lieu d'un unique `objectif_principal`.
    # Rétrocompatible à 100% : si `objectif_principal` est fourni directement
    # (ancien format, tests existants, anciens clients), rien ne change ici.
    # `objectif_principal` reste alimenté (première valeur valide de la liste,
    # ou repli neutre) pour que tout le code existant qui lit cette colonne
    # (nutrition legacy, PDF, admin...) continue de fonctionner sans le
    # moindre changement. Le vecteur d'objectif RÉEL utilisé par le moteur
    # (logic/recommendation/objectives.py) lit directement `variables_json
    # ["objectifs"]` (déjà copié tel quel plus bas, aucune duplication de
    # règle ici) pour calculer une pondération composite sur TOUS les
    # objectifs cochés, pas seulement le premier.
    if not raw.get("objectif_principal"):
        objectifs_liste = raw.get("objectifs")
        if isinstance(objectifs_liste, list) and objectifs_liste:
            candidats_principaux = [
                _clean_str(o) for o in objectifs_liste if _clean_str(o) in OBJECTIFS_PRINCIPAUX
            ]
            if candidats_principaux:
                raw = dict(raw)
                raw["objectif_principal"] = candidats_principaux[0]

    objectif_principal = _clean_str(raw.get("objectif_principal"))
    if objectif_principal not in OBJECTIFS_PRINCIPAUX:
        raise ValueError(
            f"Champ 'objectif_principal' manquant ou invalide (valeur reçue : {raw.get('objectif_principal')!r})."
        )

    # "Aucun" (option explicite du futur questionnaire) et toute valeur vide
    # sont normalisés vers None de façon identique — nettoyage de données,
    # pas une décision de pondération (celle-ci reste au moteur, phase future).
    objectif_secondaire = _clean_str(raw.get("objectif_secondaire"))
    if objectif_secondaire in (None, "Aucun") or objectif_secondaire not in OBJECTIFS_SECONDAIRES:
        objectif_secondaire = None

    composition_corporelle = _clean_str(raw.get("composition_corporelle"))

    # --- Variables moteur (facultatives, jamais bloquantes) ----------------
    exercices_maitrises = raw.get("exercices_maitrises") or []
    if not isinstance(exercices_maitrises, list):
        exercices_maitrises = []

    mobilite_generale = _to_int_in_range(raw.get("mobilite_generale"), 1, 5, DEFAUT_MOBILITE_GENERALE)
    tolerance_technique = _to_int_in_range(raw.get("tolerance_technique"), 1, 5, DEFAUT_TOLERANCE_TECHNIQUE)

    amplitude_squat = _from_allowed(raw.get("amplitude_squat"), AMPLITUDES, DEFAUT_AMPLITUDE)
    amplitude_epaule = _from_allowed(raw.get("amplitude_epaule"), AMPLITUDES, DEFAUT_AMPLITUDE)

    preference_style_charge = _from_allowed(
        raw.get("preference_style_charge"), STYLES_CHARGE, DEFAUT_STYLE_CHARGE
    )
    preference_materiel = _from_allowed(
        raw.get("preference_materiel"), MATERIELS_PREFERES, DEFAUT_MATERIEL_PREFERE
    )

    # Morphologie déclarée : regroupe les champs existants (longueur_bras,
    # longueur_jambes) et les futurs (longueur_buste, largeur_epaules) —
    # "Je ne sais pas" par défaut si absent, cohérent avec les options déjà
    # proposées aujourd'hui pour bras/jambes.
    morphologie_declaree = {
        "longueur_bras": _from_allowed(raw.get("longueur_bras"), LONGUEURS, "Je ne sais pas"),
        "longueur_jambes": _from_allowed(raw.get("longueur_jambes"), LONGUEURS, "Je ne sais pas"),
        "longueur_buste": _from_allowed(raw.get("longueur_buste"), LONGUEURS, "Je ne sais pas"),
        "largeur_epaules": _clean_str(raw.get("largeur_epaules")) or "Je ne sais pas",
    }

    # Blessures : zones déclarées (checkbox existant) + sévérité si le futur
    # questionnaire la fournit. Une zone déclarée sans sévérité renseignée
    # (cas actuel, la question de sévérité n'existe pas encore dans l'UI)
    # reste explicitement à None plutôt que de deviner une valeur — ce choix
    # de gestion appartiendra au moteur (phase future), pas à cette
    # normalisation (cf. "problèmes rencontrés" donné à l'utilisateur).
    zones_declarees = raw.get("blessures") or []
    severites_brutes = raw.get("severite_blessure") or {}
    blessures = {
        zone: severites_brutes.get(zone) for zone in zones_declarees if zone
    }

    autres_sports = {
        "pratique": raw.get("autre_sport") == "Oui",
        "type": _clean_str(raw.get("autre_sport_type")),
        "frequence": _clean_str(raw.get("autre_sport_frequence")),
    }

    disponibilite_reelle = _clean_str(raw.get("disponibilite_reelle"))
    sommeil = _clean_str(raw.get("sommeil"))
    # Réconciliation de nom : le questionnaire actuel appelle ce champ
    # "niveau_stress", le profil moteur l'appelle "stress" (cf. facteurs de
    # scoring déjà nommés dans conception_moteur_recommandation.md).
    stress = _clean_str(raw.get("niveau_stress"))

    return {
        "poids": poids,
        "taille": taille,
        "sexe": sexe,
        "niveau_musculation": niveau_musculation,
        "objectif_principal": objectif_principal,
        "objectif_secondaire": objectif_secondaire,
        "composition_corporelle": composition_corporelle,
        "exercices_maitrises": exercices_maitrises,
        "mobilite_generale": mobilite_generale,
        "amplitude_squat": amplitude_squat,
        "amplitude_epaule": amplitude_epaule,
        "tolerance_technique": tolerance_technique,
        "preference_style_charge": preference_style_charge,
        "preference_materiel": preference_materiel,
        "morphologie_declaree": morphologie_declaree,
        "blessures": blessures,
        "autres_sports": autres_sports,
        "disponibilite_reelle": disponibilite_reelle,
        "sommeil": sommeil,
        "stress": stress,
        # Copie complète des données brutes : garantit qu'aucune information
        # n'est perdue, y compris les champs non encore mappés explicitement
        # (nutrition, mode de vie, consentement...) et les futures questions
        # pas encore nommées ci-dessus.
        "variables_json": dict(raw),
    }


def create_profile_snapshot(user_id, raw_questionnaire_data):
    """Normalise puis persiste un ProfileSnapshot pour `user_id`. Ne fait
    qu'ajouter une ligne (jamais de mise à jour d'un snapshot existant — un
    ProfileSnapshot est immuable par construction, cf. architecture_v2_
    consolidation.md). N'est appelé par aucune route pour l'instant (phase
    4 : uniquement la brique, pas encore le branchement)."""
    cleaned = normalize_questionnaire_data(raw_questionnaire_data)
    snapshot = ProfileSnapshot(user_id=user_id, **cleaned)
    db.session.add(snapshot)
    db.session.commit()
    return snapshot
