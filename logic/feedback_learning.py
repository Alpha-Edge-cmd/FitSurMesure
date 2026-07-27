# -*- coding: utf-8 -*-
"""
Boucle d'amélioration utilisateur (phase 21/24) : transforme l'historique
`ExerciseFeedback` (phase 10/16, `logic/models.py`) en signaux agrégés,
utilisateur par utilisateur — PAS un ajustement par exercice pris isolément
(ça, c'est déjà le rôle de `logic/recommendation/feedback.py`, phase 10,
inchangé), mais une lecture d'ENSEMBLE de "qui est cet utilisateur ?" :
qu'aime-t-il, qu'évite-t-il, trouve-t-il les choses trop faciles ou trop
difficiles dans l'ensemble, progresse-t-il ?

Quatre signaux dérivés de `ExerciseFeedback.feedback_type`
(`FEEDBACK_TYPES = ("aime", "deteste", "douleur_gene", "trop_difficile",
"trop_facile")`, cf. logic/models.py) :

  - préférence utilisateur  -> "aime" (jusqu'ici jamais exploité par le
                               moteur : `logic/recommendation/feedback.py`
                               ne traite que "deteste"/"douleur_gene"/
                               "trop_difficile"/"trop_facile", jamais "aime" ;
                               confirmé par lecture de ce module en amont de
                               cette phase) -> `preferred_exercises`.
  - douleur                 -> "douleur_gene" (déjà géré au niveau SÉCURITÉ
                               par filters.py/feedback.py, inchangés :
                               exclusion dure, jamais relâchée) + "deteste"
                               (aversion déclarée) -> généralisés ici au
                               niveau du PATTERN de mouvement (pas seulement
                               l'exercice précis) -> `avoided_patterns`,
                               signal de préférence SOUPLE, jamais une
                               nouvelle exclusion de sécurité.
  - difficulté réelle        -> "trop_difficile"/"trop_facile", agrégés sur
                               l'ensemble de l'historique (pas exercice par
                               exercice, contrairement à
                               `feedback.apply_score_adjustments`) ->
                               `difficulty_adjustment`.
  - progression              -> même agrégat "trop_facile"/"trop_difficile",
                               interprété cette fois comme un RYTHME de
                               progression, tempéré par la prudence sécurité
                               (une douleur signalée fait toujours primer la
                               prudence sur tout signe de progression) ->
                               `volume_adjustment`.

Fonction principale : `calculate_user_preferences(user_id)` ->
{"preferred_exercises", "avoided_patterns", "difficulty_adjustment",
"volume_adjustment"}.

Branchement (consigne : "brancher UNIQUEMENT dans selector.py via une
couche EXTERNE, ne jamais modifier le scoring de base") : ce module ne
touche ni `logic/recommendation/scoring.py`, ni `logic/recommendation/
filters.py`. `apply_user_preferences_to_score` est appelée depuis
`logic/recommendation/selector.py`, EN AVAL de `scoring.score_exercise`
(exactement la même mécanique déjà établie que la pénalité de récence de la
phase 7 et les ajustements `feedback.apply_score_adjustments` de la phase
10) : un simple ajustement de score déjà calculé, jamais une redéfinition de
la formule de `scoring.py`. Ne peut jamais réintroduire un exercice exclu en
passe 1 (sécurité) : n'agit qu'sur des candidats déjà survivants du
filtrage dur, comme tous les ajustements de passe 2 précédents.

Ne modifie jamais `ExerciseFeedback`/`ExerciseUsageLog` ni aucune autre
table : lecture seule, comme `logic/recommendation/history.py`."""
from logic.models import Exercise
from logic.recommendation import history
from logic.recommendation.scoring import DIFFICULTY_ORDINAL, NIVEAU_ORDINAL

# Seuil documenté (premier jet, à calibrer empiriquement — même statut que
# les seuils déjà en place dans feedback.py/intensity.py/rest_time.py) :
# un écart net d'au moins 2 entre "trop_facile" et "trop_difficile" (ou
# l'inverse) est considéré comme un signal suffisamment clair pour agir ;
# en dessous, on reste neutre plutôt que de sur-réagir à un feedback isolé.
SEUIL_SIGNAL_DIFFICULTE = 2

BONUS_EXERCICE_PREFERE = 10
MALUS_PATTERN_EVITE = 10
BONUS_MALUS_DIFFICULTE = 5


def _feedbacks_bruts(user_id):
    """Charge les feedbacks de l'utilisateur via `history.get_exercise_
    feedback` (phase 10, inchangé, lecture seule) plutôt que de requêter la
    table `ExerciseFeedback` une seconde fois avec une logique différente."""
    return history.get_exercise_feedback(user_id)


def _resoudre_pattern(exercise_id, exercises_by_id=None):
    if exercises_by_id is not None:
        exercise = exercises_by_id.get(exercise_id)
    else:
        exercise = Exercise.query.get(exercise_id)
    return getattr(exercise, "pattern", None) if exercise is not None else None


def compute_preference_signal(feedbacks):
    """"aime" -> `preferred_exercises` : liste (dédupliquée, ordre de
    première apparition) des exercise_id "aimés". Un exercise_id à la fois
    "aimé" et "détesté" (signal contradictoire dans l'historique) est
    EXCLU de la liste plutôt que de trancher arbitrairement — choix
    conservateur documenté, jamais une supposition."""
    aimes, detestes = [], set()
    for fb in feedbacks:
        if fb["feedback_type"] == "deteste":
            detestes.add(fb["exercise_id"])

    vus = set()
    for fb in feedbacks:
        if fb["feedback_type"] == "aime" and fb["exercise_id"] not in vus:
            vus.add(fb["exercise_id"])
            if fb["exercise_id"] not in detestes:
                aimes.append(fb["exercise_id"])
    return aimes


def compute_avoidance_signal(feedbacks, exercises_by_id=None):
    """"douleur_gene" + "deteste" -> `avoided_patterns` : généralise
    l'aversion déclarée sur des exercices précis au PATTERN de mouvement
    (`Exercise.pattern`), pour capter "cet utilisateur évite les mouvements
    de type X" au-delà du seul exercice signalé. Signal SOUPLE de
    préférence (utilisé en bonus/malus de score, cf.
    `apply_user_preferences_to_score`) — ne remplace ni ne relâche jamais
    l'exclusion de SÉCURITÉ déjà gérée par `filters.py`/`feedback.py`
    (invariant inchangé depuis les phases 6/10)."""
    patterns = []
    for fb in feedbacks:
        if fb["feedback_type"] not in ("douleur_gene", "deteste"):
            continue
        pattern = _resoudre_pattern(fb["exercise_id"], exercises_by_id)
        if pattern and pattern not in patterns:
            patterns.append(pattern)
    return patterns


def _ecart_difficulte(feedbacks):
    """Compte net "trop_facile" moins "trop_difficile" sur tout
    l'historique (exercices distincts, un même exercice signalé plusieurs
    fois ne compte qu'une fois pour éviter qu'un doublon de clic ne fausse
    le signal)."""
    trop_facile = {fb["exercise_id"] for fb in feedbacks if fb["feedback_type"] == "trop_facile"}
    trop_difficile = {fb["exercise_id"] for fb in feedbacks if fb["feedback_type"] == "trop_difficile"}
    return len(trop_facile) - len(trop_difficile)


def compute_difficulty_signal(feedbacks):
    """"trop_difficile"/"trop_facile" agrégés -> `difficulty_adjustment`
    (-1/0/+1) : +1 si l'utilisateur trouve significativement plus souvent
    les exercices trop faciles que trop difficiles (au-delà de
    `SEUIL_SIGNAL_DIFFICULTE`), -1 dans le cas inverse, 0 sinon (signal
    insuffisant, comportement neutre par défaut)."""
    ecart = _ecart_difficulte(feedbacks)
    if ecart >= SEUIL_SIGNAL_DIFFICULTE:
        return 1
    if ecart <= -SEUIL_SIGNAL_DIFFICULTE:
        return -1
    return 0


def compute_volume_signal(feedbacks):
    """Signal de "progression" -> `volume_adjustment` (-1/0/+1) : réutilise
    le même écart "trop_facile"/"trop_difficile" que `compute_difficulty_
    signal` (la progression se lit, ici, dans le même agrégat de
    difficulté réelle déclarée), MAIS la prudence sécurité prime toujours :
    toute "douleur_gene" déclarée force `volume_adjustment` à -1, quel que
    soit le signe du signal de progression (jamais l'inverse — un signe de
    progression ne peut jamais compenser une douleur signalée)."""
    if any(fb["feedback_type"] == "douleur_gene" for fb in feedbacks):
        return -1
    ecart = _ecart_difficulte(feedbacks)
    if ecart >= SEUIL_SIGNAL_DIFFICULTE:
        return 1
    if ecart <= -SEUIL_SIGNAL_DIFFICULTE:
        return -1
    return 0


def calculate_user_preferences(user_id):
    """calculate_user_preferences(user_id) -> {"preferred_exercises",
    "avoided_patterns", "difficulty_adjustment", "volume_adjustment"}.

    Point d'entrée principal de cette phase. Retourne des valeurs neutres
    (listes vides, ajustements à 0) si `user_id` est None ou en l'absence
    de tout feedback — jamais d'exception, même garantie que le reste du
    moteur."""
    if user_id is None:
        return {
            "preferred_exercises": [],
            "avoided_patterns": [],
            "difficulty_adjustment": 0,
            "volume_adjustment": 0,
        }

    feedbacks = _feedbacks_bruts(user_id)
    return {
        "preferred_exercises": compute_preference_signal(feedbacks),
        "avoided_patterns": compute_avoidance_signal(feedbacks),
        "difficulty_adjustment": compute_difficulty_signal(feedbacks),
        "volume_adjustment": compute_volume_signal(feedbacks),
    }


def apply_user_preferences_to_score(profile, exercise, score, preferences):
    """apply_user_preferences_to_score(profile, exercise, score, preferences)
    -> score ajusté.

    COUCHE EXTERNE appelée depuis `logic/recommendation/selector.py`
    UNIQUEMENT (consigne), en aval de `scoring.score_exercise` — ne modifie
    jamais `logic/recommendation/scoring.py` lui-même, exactement comme la
    pénalité de récence (phase 7) et `feedback.apply_score_adjustments`
    (phase 10) déjà en place dans `selector.py`. `score` reste toujours
    dans [0, 100]. Retourne `score` inchangé si `preferences` est vide/None
    (comportement neutre par défaut, aucune régression pour un appel sans
    `user_id`)."""
    if not preferences:
        return score

    exercise_id = getattr(exercise, "exercise_id", None)
    pattern = getattr(exercise, "pattern", None)

    if exercise_id in preferences.get("preferred_exercises", []):
        score = min(100, score + BONUS_EXERCICE_PREFERE)

    if pattern and pattern in preferences.get("avoided_patterns", []):
        score = max(0, score - MALUS_PATTERN_EVITE)

    ajustement = preferences.get("difficulty_adjustment", 0)
    if ajustement:
        niveau_ordinal = NIVEAU_ORDINAL.get(getattr(profile, "niveau_musculation", None), 2)
        exercise_ordinal = DIFFICULTY_ORDINAL.get(getattr(exercise, "difficulty_level", None))
        if exercise_ordinal is not None:
            ecart_niveau = exercise_ordinal - niveau_ordinal
            plus_difficile_que_niveau = ecart_niveau >= 1
            if ajustement > 0:
                # Progression constatée : privilégie un cran au-dessus du niveau.
                score = (
                    min(100, score + BONUS_MALUS_DIFFICULTE) if plus_difficile_que_niveau
                    else max(0, score - BONUS_MALUS_DIFFICULTE)
                )
            else:
                # Signal inverse : privilégie le niveau déclaré ou plus bas.
                score = (
                    max(0, score - BONUS_MALUS_DIFFICULTE) if plus_difficile_que_niveau
                    else min(100, score + BONUS_MALUS_DIFFICULTE)
                )

    return score
