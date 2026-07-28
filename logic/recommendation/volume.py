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


# ==============================================================================
# Prompt hors 24 phases (retour Samy, test en conditions réelles : "ça ne va
# pas du tout une séance fait 4 exercices, minimum 3 exercice par muscle et 4
# pour le muscle principal ou le muscle priorisé"). Après clarification
# explicite de Samy sur le cas des séances courtes : la répartition ci-dessous
# remplace `calculate_exercise_count` UNIQUEMENT à partir d'1h de séance
# ("à partir d'une heure") ; en dessous (45 min), l'ancien barème
# niveau/objectif/durée ci-dessus reste utilisé tel quel (moins d'exercices,
# priorisation du plus important, cf. section courte de la consigne d'origine).
#
# Répartition demandée explicitement par Samy, par POSITION de priorité dans
# la séance (position 0 = muscle principal de la séance ou muscle prioritaire
# de l'utilisateur, après réordonnancement fait par l'appelant, cf.
# `workout_generator._muscles_ordonnes_par_priorite`) : "si il y'a 3 muscles
# tu fais 4 3 2 et si il y'en a deux 4 4" -> généralisé au-delà de 3 par une
# dégression jusqu'à un plancher de 2 (pas de formule au-delà de 3 muscles
# donnée explicitement par Samy, ce plancher est l'extrapolation la plus
# directe de son exemple, à recalibrer si besoin).
# ==============================================================================
SEUIL_NOUVELLE_REPARTITION_MINUTES = 60  # "à partir d'une heure" (Samy)

# Nombre d'exercices max qu'une seule "portion anatomique" peut faire monter
# le compte d'un muscle à couvrir de portions différentes (cf.
# `_portions_disponibles` ci-dessous) — plafond pour ne pas déséquilibrer une
# séance juste parce qu'un muscle a beaucoup de portions cataloguées.
PLANCHER_PORTIONS_MAX = 4


def _repartition_positionnelle(nb_muscles):
    """Nombre d'exercices "de base" par muscle selon sa position de priorité
    dans la séance (0 = le plus prioritaire). Exemples donnés explicitement
    par Samy : 1 muscle -> [4] ; 2 muscles -> [4, 4] (les deux restent
    prioritaires, pas de raison de moins doser le second) ; 3 muscles ->
    [4, 3, 2]. Au-delà de 3, dégression continue jusqu'au plancher 2."""
    if nb_muscles <= 0:
        return []
    if nb_muscles == 1:
        return [4]
    if nb_muscles == 2:
        return [4, 4]
    return [max(2, 4 - i) for i in range(nb_muscles)]


def _portions_disponibles(muscle, available_exercises):
    """Ensemble des portions anatomiques distinctes (`Exercise.
    portion_anatomique`, ex: "Haut des pecs"/"Milieu des pecs"/"Bas des pecs")
    présentes au catalogue pour `muscle`. Approximation volontaire (ne tient
    pas compte des exclusions équipement/blessure, qui restent gérées en aval
    par `fallback.run_fallback_cascade`) : sert uniquement à DIMENSIONNER le
    volume souhaité, pas à garantir sa disponibilité réelle."""
    return {
        getattr(ex, "portion_anatomique", None)
        for ex in available_exercises
        if getattr(ex, "muscle_principal", None) == muscle and getattr(ex, "portion_anatomique", None)
    }


def calculer_repartition_seance(target_muscles, available_exercises):
    """Nombre d'exercices par muscle pour TOUTE la séance (>= 1h), en
    combinant la position de priorité (`_repartition_positionnelle` ;
    `target_muscles` est supposé DÉJÀ réordonné par priorité par l'appelant,
    cf. `workout_generator._muscles_ordonnes_par_priorite`) et le nombre de
    portions anatomiques distinctes à couvrir pour ce muscle précis (un
    muscle à plusieurs portions, ex: pecs Haut/Milieu/Bas, mérite au moins
    autant d'exercices que de portions à varier, dans la limite de
    `PLANCHER_PORTIONS_MAX` pour ne pas déséquilibrer la séance). Retourne
    {muscle: nombre}, jamais moins que la base positionnelle."""
    base = _repartition_positionnelle(len(target_muscles))
    resultat = {}
    for muscle, compte_base in zip(target_muscles, base):
        nb_portions = len(_portions_disponibles(muscle, available_exercises))
        if nb_portions:
            resultat[muscle] = max(compte_base, min(nb_portions, PLANCHER_PORTIONS_MAX))
        else:
            resultat[muscle] = compte_base
    return resultat
