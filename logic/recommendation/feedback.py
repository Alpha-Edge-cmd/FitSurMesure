# -*- coding: utf-8 -*-
"""
Traduction des feedbacks utilisateur (`ExerciseFeedback`, phase 10/16) en
signaux exploitables par le moteur. Ne redéfinit AUCUNE règle de sécurité ni
de scoring déjà validée : passe 1 (sécurité) reste exclusivement gouvernée
par `filters.py` (inchangé depuis la phase 6, y compris son hook
`feedback_repository` déjà prévu à l'époque pour cette exacte connexion) ;
les ajustements de score sont appliqués EN AVAL de `scoring.score_exercise`
(dans `selector.py`, même mécanique que la pénalité de récence de la phase
7) — `scoring.py` lui-même n'est pas modifié.

Règles (consigne phase 10 + resolution_points_bloquants_v2.md point 9) :
  - "deteste"         : exclusion douce (passe 2, `disliked_provider` de
                        selector.py), jamais sécurité, réintégrable dès
                        l'étape 2 de la cascade de fallback (mécanisme
                        inchangé depuis la phase 7).
  - "douleur_gene"     : passe 1 (sécurité), portée dépendant de l'exercice :
                        - articulation dominante clairement identifiable
                          dans `joint_stress` -> `blessures[zone]` élevée à
                          "Gêne modérée régulière" au minimum pour cette
                          zone (exclusion GÉNÉRALISÉE à tous les exercices
                          sollicitant cette articulation, pas seulement
                          celui rejeté).
                        - plusieurs articulations sans dominante claire ->
                          exclusion CIBLÉE, permanente, de cet exercice
                          précis (par id), via le hook `feedback_repository`
                          déjà prévu par filters.py.
  - "trop_difficile"  : pénalité de score (passe 2), même mécanique que la
                        pénalité de récence.
  - "trop_facile"      : petit bonus de score pour des exercices plus
                        complexes, si compatibles avec le niveau déclaré
                        (passe 2, même mécanique).

Aucun de ces ajustements ne peut jamais réintroduire un exercice exclu par
`joint_stress` critique ou `contre_indications` (invariant absolu, inchangé
depuis la phase 6/7) : ce module ne touche jamais à `filters.exclusion_reason`
lui-même, il ne fait qu'alimenter ses entrées (via une vue de profil dérivée
et le hook `feedback_repository` déjà existant).
"""
from logic.models import Exercise, ExerciseFeedback
from logic.recommendation import filters
from logic.recommendation.scoring import DIFFICULTY_ORDINAL, NIVEAU_ORDINAL

# Seuil documenté pour "articulation dominante clairement identifiable"
# (resolution_points_bloquants_v2.md point 9 : "une valeur nettement
# supérieure aux autres"). Aucun seuil chiffré n'a été validé : on retient
# qu'une zone est dominante si sa valeur est la plus haute ET dépasse d'au
# moins ce nombre de points la deuxième valeur la plus haute présente
# (`joint_stress` va de 0 à 3) — premier jet documenté, à calibrer.
ECART_DOMINANCE_MINIMUM = 1

PENALITE_TROP_DIFFICILE = 15  # points, même ordre de grandeur que selector.PENALITE_RECENCE
BONUS_TROP_FACILE = 5  # points, même ordre de grandeur que diversity.BONUS_NOUVELLE_FAMILLE

_JOINT_STRESS_KEY_TO_ZONE_LABEL = {v: k for k, v in filters.ZONE_LABEL_TO_JOINT_STRESS_KEY.items()}


class EffectiveProfileView:
    """Vue dérivée d'un `ProfileSnapshot` avec certains attributs redéfinis
    (ici : `blessures`), SANS jamais modifier ni persister la ligne en base
    (`ProfileSnapshot` est immuable par design depuis la phase 1). Tout
    attribut non redéfini est délégué au profil d'origine — transparent
    pour le reste du moteur (`biomechanics.py`, `scoring.py`, etc. n'ont pas
    besoin de savoir qu'ils manipulent une vue dérivée plutôt que l'objet
    ProfileSnapshot lui-même)."""

    def __init__(self, profil_source, **overrides):
        self._profil_source = profil_source
        self._overrides = overrides

    def __getattr__(self, nom):
        if nom in self._overrides:
            return self._overrides[nom]
        return getattr(self._profil_source, nom)


def load_feedback(user_id):
    """Charge une seule fois tous les `ExerciseFeedback` d'un utilisateur —
    évite une requête par exercice dans les boucles de `selector.py`.
    Retourne toujours [] si `user_id` est None."""
    if user_id is None:
        return []
    return ExerciseFeedback.query.filter_by(user_id=user_id).all()


def _resoudre_exercice(exercise_id, available_exercises=None):
    if available_exercises:
        for ex in available_exercises:
            if getattr(ex, "exercise_id", None) == exercise_id:
                return ex
    return Exercise.query.get(exercise_id)


def _zone_dominante(joint_stress):
    """Retourne la clé de la zone dominante de `joint_stress` (dict
    {zone_courte: 0-3}), ou None si aucune zone ne se détache clairement
    (valeurs toutes nulles, ou écart insuffisant avec la 2e plus haute)."""
    if not joint_stress:
        return None
    valeurs = sorted(joint_stress.items(), key=lambda kv: kv[1], reverse=True)
    if not valeurs or valeurs[0][1] <= 0:
        return None
    if len(valeurs) == 1:
        return valeurs[0][0]
    if valeurs[0][1] - valeurs[1][1] >= ECART_DOMINANCE_MINIMUM:
        return valeurs[0][0]
    return None


def compute_effective_blessures(profile, feedbacks, available_exercises=None):
    """Point 9, cas "articulation dominante claire" : dérive une nouvelle
    version de `profile.blessures` intégrant les élévations de sévérité
    issues des feedbacks "douleur_gene". Ne modifie jamais le
    `ProfileSnapshot` en base : retourne un nouveau dict, à consommer via
    `EffectiveProfileView` le temps d'un calcul de recommandation."""
    blessures = dict(getattr(profile, "blessures", None) or {})

    for fb in feedbacks:
        if fb.feedback_type != "douleur_gene":
            continue
        exercise = _resoudre_exercice(fb.exercise_id, available_exercises)
        if exercise is None:
            continue
        zone = _zone_dominante(getattr(exercise, "joint_stress", None) or {})
        if zone is None:
            continue  # pas de dominante claire : cf. get_targeted_pain_exclusions
        label = _JOINT_STRESS_KEY_TO_ZONE_LABEL.get(zone)
        if label is None:
            continue
        rang_actuel = filters.SEVERITE_RANG.get(blessures.get(label), 0)
        if rang_actuel < filters.SEVERITE_RANG["Gêne modérée régulière"]:
            blessures[label] = "Gêne modérée régulière"

    return blessures


def get_targeted_pain_exclusions(feedbacks, available_exercises=None):
    """Point 9, cas "plusieurs articulations sans dominante claire" :
    exercise_ids à exclure de façon ciblée et permanente pour cet
    utilisateur — jamais réintégrés par le fallback (invariant du point 8 :
    les exclusions "douleur" ne sont jamais relâchées, à aucune étape)."""
    exclusions = set()
    for fb in feedbacks:
        if fb.feedback_type != "douleur_gene":
            continue
        exercise = _resoudre_exercice(fb.exercise_id, available_exercises)
        if exercise is None:
            continue
        if _zone_dominante(getattr(exercise, "joint_stress", None) or {}) is None:
            exclusions.add(fb.exercise_id)
    return exclusions


def build_feedback_repository(feedbacks, available_exercises=None):
    """Construit le callable `feedback_repository(user_id, exercise_id) ->
    raison|None` déjà prévu par `filters._feedback_douleur_exclusion_reason`
    depuis la phase 6 (jamais modifié ici). Ne couvre que le cas "exclusion
    ciblée" : le cas "dominante claire" passe par `compute_effective_blessures`
    + `EffectiveProfileView`, en amont du filtrage standard, pas par ce hook."""
    exclusions = get_targeted_pain_exclusions(feedbacks, available_exercises)

    def _repository(user_id, exercise_id):
        return "douleur_gene" if exercise_id in exclusions else None

    return _repository


def get_disliked_exercise_ids(user_id, feedbacks=None):
    """"deteste" (passe 2, exclusion douce, jamais sécurité) — branché sur
    `selector.get_disliked_exercises`, remplace le stub `[]` de la phase 7."""
    feedbacks = load_feedback(user_id) if feedbacks is None else feedbacks
    return [fb.exercise_id for fb in feedbacks if fb.feedback_type == "deteste"]


def apply_score_adjustments(profile, exercise, score, feedbacks):
    """Ajustements de score post-scoring (passe 2), même mécanique que la
    pénalité de récence de `selector.py` (appliquée en aval de
    `scoring.score_exercise`, sans modifier `scoring.py`) :
      - "trop_difficile" déclaré sur CET exercice -> pénalité fixe.
      - "trop_facile" déclaré sur un AUTRE exercice moins complexe du même
        registre -> petit bonus pour CET exercice, s'il reste "compatible
        avec le niveau" (pas plus d'un cran de difficulté au-dessus du
        niveau déclaré, réutilise `scoring.DIFFICULTY_ORDINAL`/
        `NIVEAU_ORDINAL`, sans les redéfinir)."""
    if not feedbacks:
        return score

    exercise_id = getattr(exercise, "exercise_id", None)

    for fb in feedbacks:
        if fb.exercise_id == exercise_id and fb.feedback_type == "trop_difficile":
            score = max(0, score - PENALITE_TROP_DIFFICILE)

    exercise_ordinal = DIFFICULTY_ORDINAL.get(getattr(exercise, "difficulty_level", None))
    if exercise_ordinal is not None:
        niveau_ordinal = NIVEAU_ORDINAL.get(getattr(profile, "niveau_musculation", None), 2)
        if exercise_ordinal <= niveau_ordinal + 1:
            for fb in feedbacks:
                if fb.feedback_type != "trop_facile" or fb.exercise_id == exercise_id:
                    continue
                autre = Exercise.query.get(fb.exercise_id)
                if autre is None:
                    continue
                autre_ordinal = DIFFICULTY_ORDINAL.get(getattr(autre, "difficulty_level", None))
                if autre_ordinal is not None and exercise_ordinal > autre_ordinal:
                    score = min(100, score + BONUS_TROP_FACILE)
                    break

    return score
