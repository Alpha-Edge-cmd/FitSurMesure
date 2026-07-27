# -*- coding: utf-8 -*-
"""
Volume d'exercices par muscle, pour UNE séance (phase 8/16) : "pour ce
muscle, dans cette séance, combien d'exercices inclure ?" — ne détermine
PAS les séries/répétitions/charges (hors périmètre de cette phase, cf.
architecture_v2_consolidation.md, étapes ultérieures du plan d'évolution).

Aucune formule chiffrée n'a été validée dans les documents de conception
pour ce point précis (contrairement aux 8 facteurs de scoring.py, qui ont
des formules exactes) : les valeurs ci-dessous sont les bornes fournies
explicitement dans cette phase ("Débutant : 1-2, Intermédiaire : 2-4,
Avancé : 3-5"), complétées par une interpolation documentée pour le palier
"Quelques mois d'expérience" (présent dans le questionnaire réel mais non
listé explicitement dans la consigne), et par des modulations légères
(durée de séance, objectif) qui sont de premières valeurs à calibrer
empiriquement — pas des règles métier validées.
"""

# --- Bornes de volume par niveau (min, max) exercices/muscle -----------------
NIVEAU_VOLUME_RANGE = {
    "Débutant complet": (1, 2),
    # Palier intermédiaire entre "Débutant complet" et "Intermédiaire" dans le
    # questionnaire réel (cf. scoring.NIVEAU_ORDINAL) : la consigne ne donne
    # que 3 paliers, celui-ci est interpolé (borne basse du niveau du dessus).
    "Quelques mois d'expérience": (2, 3),
    "Intermédiaire": (2, 4),
    "Avancé": (3, 5),
}
NIVEAU_VOLUME_RANGE_DEFAUT = NIVEAU_VOLUME_RANGE["Intermédiaire"]  # repli si niveau absent/inconnu

# --- Paliers de durée de séance (section 5 de la consigne) -------------------
DUREE_COURTE_SEUIL_MINUTES = 45   # < 45 min
DUREE_LONGUE_SEUIL_MINUTES = 90   # > 90 min

# Temps estimé par exercice (échauffement exclu) utilisé uniquement pour
# dimensionner le VOLUME ici (nombre d'exercices) — ce n'est pas une
# estimation de séries/temps de repos, qui restent hors périmètre.
TEMPS_PAR_EXERCICE_MINUTES = 8

# --- Modulation par objectif --------------------------------------------------
# Interprétation documentée (aucune formule validée pour ce point précis) :
# les objectifs orientés "force/performance" favorisent moins d'exercices mais
# plus lourds/composés (borne basse) ; les objectifs orientés "endurance/perte
# de gras/condition générale" favorisent davantage de volume et de variété
# (borne haute). "Prise de muscle" et "Recomposition" restent neutres (milieu
# de fourchette).
OBJECTIFS_VOLUME_BAS = {"Performance / explosivité"}
OBJECTIFS_VOLUME_HAUT = {"Perte de gras", "Condition physique générale"}


def _duree_minutes(session_duration):
    """Accepte un nombre de minutes (int/float) ou l'une des chaînes du
    questionnaire ("45 min", "1h", "1h - 1h30", "1h30+") ; jamais d'exception
    sur une valeur inconnue (repli sur la durée moyenne validée)."""
    if isinstance(session_duration, (int, float)):
        return float(session_duration)

    correspondance = {
        "45 min": 45,
        "1h": 60,
        "1h - 1h30": 75,
        "1h30+": 100,
    }
    return correspondance.get(session_duration, 75)  # repli "durée moyenne"


def duree_palier(session_duration):
    """Retourne "courte" / "moyenne" / "longue" selon les seuils de la
    consigne (< 45 min / 45-90 min / > 90 min)."""
    minutes = _duree_minutes(session_duration)
    if minutes < DUREE_COURTE_SEUIL_MINUTES:
        return "courte"
    if minutes > DUREE_LONGUE_SEUIL_MINUTES:
        return "longue"
    return "moyenne"


def _position_dans_fourchette(palier):
    """Où puiser dans la fourchette (min, max) du niveau selon la durée :
    séance courte -> borne basse (moins d'exercices mais plus importants,
    cf. consigne section 5), séance longue -> borne haute, séance moyenne ->
    milieu."""
    return {"courte": 0.0, "moyenne": 0.5, "longue": 1.0}[palier]


def calculate_exercise_count(profile, muscle, available_time):
    """Nombre d'exercices à sélectionner pour `muscle` dans une séance de
    durée `available_time` (minutes ou libellé questionnaire), pour ce
    `profile`. Combine : niveau (fourchette de base), durée de séance
    (position dans la fourchette), objectif (léger ajustement des bornes).
    Ne tient pas compte ici du budget de fatigue réel (cf. fatigue.py) :
    c'est `workout_generator.py` qui arbitre volume vs budget de fatigue au
    moment d'assembler la séance complète (section 7 de la consigne)."""
    niveau = getattr(profile, "niveau_musculation", None)
    borne_min, borne_max = NIVEAU_VOLUME_RANGE.get(niveau, NIVEAU_VOLUME_RANGE_DEFAUT)

    objectif = getattr(profile, "objectif_principal", None)
    if objectif in OBJECTIFS_VOLUME_BAS:
        borne_max = max(borne_min, borne_max - 1)
    elif objectif in OBJECTIFS_VOLUME_HAUT:
        borne_max = borne_max + 1

    palier = duree_palier(available_time)
    position = _position_dans_fourchette(palier)
    count = borne_min + round((borne_max - borne_min) * position)

    # Garde-fou : jamais moins de 1 exercice pour un muscle explicitement
    # ciblé, jamais plus que ce qu'une durée courte permet raisonnablement
    # (protection supplémentaire, redondante avec le budget de fatigue).
    count = max(1, count)
    if palier == "courte":
        count = min(count, borne_min + 1)

    return count
