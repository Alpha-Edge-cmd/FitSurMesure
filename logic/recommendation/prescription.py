# -*- coding: utf-8 -*-
"""
Prescription d'entraînement (phase 9/16) : transforme une séance structurée
(sortie de `workout_generator.generate_workout`, phase 8) en prescription
exploitable — séries, répétitions, repos, intensité, consignes générales.
Ne gère PAS : progression semaine après semaine, auto-régulation selon
historique, charges exactes personnalisées, génération PDF finale (hors
périmètre, cf. architecture_v2_consolidation.md, étapes ultérieures).

Réutilise strictement `exercise_order` (paliers de mouvement, phase 8),
`objectives` (vecteur objectif, phases 6+), `fatigue.calculate_fatigue_budget`
(phase 6) et `workout_generator.estimate_exercise_fatigue_cost` (phase 8) —
aucune de ces règles n'est redéfinie ici.

Limite de conception assumée et documentée : le format de séance produit en
phase 8 (`generate_workout`) ne conserve, par exercice, que
{exercise_id, name, family, muscle_principal, score, raison_selection}
(schéma figé par cette phase précédente, volontairement non modifié ici pour
ne pas remettre en cause un livrable déjà validé/testé). Cette phase a
pourtant besoin d'attributs supplémentaires de l'exercice (pattern,
movement_type, technical_complexity, stability_demand, unilateral) pour
calculer séries/repos/intensité. `generate_prescription` accepte donc un
troisième paramètre optionnel `available_exercises` (même catalogue que celui
déjà utilisé pour générer la séance) pour résoudre ces attributs sans toucher
au DB ; à défaut, un repli sur `Exercise.query.get(...)` est tenté (utile une
fois le catalogue réellement peuplé en base). La signature à 2 arguments
demandée par la consigne (`generate_prescription(profile, workout)`) reste
pleinement valide : le 3e paramètre est optionnel.
"""
from logic.models import Exercise
from logic.recommendation import exercise_order, objectives, workout_generator
from logic.recommendation.fatigue import calculate_fatigue_budget
from logic.recommendation.intensity import calculate_intensity
from logic.recommendation.rest_time import calculate_rest_time
from logic.recommendation.scoring import _mastered_patterns  # noqa: F401 (réutilisé indirectement via intensity.py)

# --- Séries (section 3) -------------------------------------------------------
# Bornes fournies par la consigne pour Débutant/Intermédiaire/Avancé.
# "Quelques mois d'expérience" n'est pas listé explicitement (questionnaire
# réel à 4 paliers, cf. scoring.NIVEAU_ORDINAL) : interpolé entre les deux
# paliers voisins, comme dans volume.py (phase 8) — non validé, à calibrer.
NIVEAU_SETS_RANGE = {
    "Débutant complet": (2, 3),
    "Quelques mois d'expérience": (2, 4),
    "Intermédiaire": (3, 4),
    "Avancé": (3, 5),
}
NIVEAU_SETS_RANGE_DEFAUT = NIVEAU_SETS_RANGE["Intermédiaire"]

# --- Répétitions (section 4) --------------------------------------------------
REP_RANGES = {
    "force": (3, 6),
    "hypertrophie": (6, 12),
    "endurance_musculaire": (12, 20),
    "perte_de_gras": (8, 15),
    "explosivite": (3, 8),
}
REP_RANGE_DEFAUT = REP_RANGES["hypertrophie"]

# --- Notes automatiques (section 7) ------------------------------------------
NOTE_PRINCIPALE = "Priorité à la technique et à la progression de charge."
NOTE_ISOLATION = "Contrôle du mouvement, amplitude complète."
NOTE_EXPLOSIVITE = "Recherche de vitesse maximale, arrêter si perte de qualité."


def _dominant_objective(profile):
    vector = objectives.get_objective_vector(profile)
    return max(vector, key=vector.get)


def determine_rep_range(profile, exercise):
    """determine_rep_range(profile, exercise) -> "min-max" (chaîne).
    Selon l'objectif dominant du profil (vecteur déjà validé de
    `objectives.get_objective_vector`, dominante = valeur la plus élevée,
    cf. consigne "objectif composite -> utiliser le vecteur, choisir la
    dominante la plus élevée"). Le paramètre `exercise` n'intervient pas
    dans la formule demandée (purement objectif-dépendante) : conservé pour
    respecter la signature requise et une éventuelle évolution future
    (aucune modulation par exercice individuel n'a été validée à ce stade)."""
    dominant = _dominant_objective(profile)
    low, high = REP_RANGES.get(dominant, REP_RANGE_DEFAUT)
    return f"{low}-{high}"


def _sets_de_base(profile, exercise, dominant):
    """Bornes de niveau (section 3) + modulation par type d'exercice :
    mouvement composé (principal/secondaire) -> borne haute (le "+1 série
    possible" est un bonus conditionnel, appliqué séparément si le budget de
    fatigue le permet, cf. `_ajuster_series_selon_budget`) ; isolation/
    finisseur -> borne basse.

    Règle additionnelle (dérivée du scénario de test "explosivité -> faible
    volume", section 8) : quand l'objectif dominant est l'explosivité, le
    volume reste sciemment bas (qualité du geste > quantité, cohérent avec le
    principe d'entraînement de la puissance) -> borne basse quel que soit le
    palier, et pas de bonus "+1 série" pour ce cas (cf. generate_prescription)."""
    niveau = getattr(profile, "niveau_musculation", None)
    borne_min, borne_max = NIVEAU_SETS_RANGE.get(niveau, NIVEAU_SETS_RANGE_DEFAUT)
    tier = exercise_order.classify_exercise(exercise)

    if dominant == "explosivite":
        return borne_min, tier

    if tier in (exercise_order.TIER_PRINCIPAL, exercise_order.TIER_SECONDAIRE):
        return borne_max, tier
    return borne_min, tier


def _cout_fatigue_par_serie(exercise):
    """Proxy documenté (même limitation que `workout_generator`/
    `exercise_order` : `fatigue_cost` par exercice absent du catalogue) :
    ramène le coût de fatigue "par séance" de
    `workout_generator.estimate_exercise_fatigue_cost` à un coût "par série"
    (forfait de 3 séries de référence), pour pouvoir arbitrer un nombre de
    séries plutôt qu'un nombre d'exercices."""
    return workout_generator.estimate_exercise_fatigue_cost(exercise) / 3.0


def _ajuster_series_selon_budget(items, budget, autoriser_bonus):
    """"Ne jamais dépasser le budget fatigue de séance" (section 3). Réduit
    d'abord les paliers les moins prioritaires (finisseur puis isolation puis
    secondaire puis, en dernier recours, principal) jusqu'à 1 série avant de
    descendre plus loin ; accorde ensuite le "+1 série possible" aux
    mouvements composés (un seul palier de bonus, jamais cumulatif) si de la
    marge reste, principal d'abord."""

    def total():
        return sum(it["sets"] * _cout_fatigue_par_serie(it["exercise"]) for it in items)

    ordre_reduction = [
        exercise_order.TIER_FINISSEUR,
        exercise_order.TIER_ISOLATION,
        exercise_order.TIER_SECONDAIRE,
        exercise_order.TIER_PRINCIPAL,
    ]
    for tier_a_reduire in ordre_reduction:
        while total() > budget:
            candidats = [it for it in items if it["tier"] == tier_a_reduire and it["sets"] > 1]
            if not candidats:
                break
            candidats[0]["sets"] -= 1
        if total() <= budget:
            break

    if autoriser_bonus:
        for it in items:
            if it["tier"] in (exercise_order.TIER_PRINCIPAL, exercise_order.TIER_SECONDAIRE):
                if total() + _cout_fatigue_par_serie(it["exercise"]) <= budget:
                    it["sets"] += 1

    return items


def _note_automatique(dominant, tier):
    if dominant == "explosivite" and tier in (exercise_order.TIER_PRINCIPAL, exercise_order.TIER_SECONDAIRE):
        return NOTE_EXPLOSIVITE
    if tier in (exercise_order.TIER_PRINCIPAL, exercise_order.TIER_SECONDAIRE):
        return NOTE_PRINCIPALE
    return NOTE_ISOLATION


def generate_prescription(profile, workout, available_exercises=None):
    """Point d'entrée principal de cette phase.

    profile             : ProfileSnapshot.
    workout             : sortie de `workout_generator.generate_workout`
                          (dict avec au moins une clé "exercises").
    available_exercises : catalogue optionnel d'objets Exercise (même liste
                          que celle utilisée pour générer `workout`) — permet
                          de résoudre les attributs biomécaniques nécessaires
                          sans dépendre du DB (cf. docstring du module).

    Retourne {"exercises": [{"exercise_id", "name", "sets", "reps",
    "rest_seconds", "intensity", "notes"}]}."""
    lookup = {}
    if available_exercises:
        lookup = {getattr(ex, "exercise_id", None): ex for ex in available_exercises}

    budget = calculate_fatigue_budget(profile)
    dominant = _dominant_objective(profile)

    items = []
    for entree in workout.get("exercises", []):
        exercise_id = entree.get("exercise_id")
        exo_obj = lookup.get(exercise_id)
        if exo_obj is None:
            exo_obj = Exercise.query.get(exercise_id)  # repli DB, cf. docstring du module
        items.append({"entree": entree, "exercise": exo_obj})

    for it in items:
        if it["exercise"] is None:
            # Catalogue introuvable pour cet exercice (ni fourni, ni en base) :
            # prescription minimale neutre plutôt qu'un plantage (même
            # principe "jamais d'exception silencieuse" que tout le moteur).
            it["sets"], it["tier"] = NIVEAU_SETS_RANGE_DEFAUT[0], exercise_order.TIER_ISOLATION
        else:
            it["sets"], it["tier"] = _sets_de_base(profile, it["exercise"], dominant)

    items_reels = [it for it in items if it["exercise"] is not None]
    _ajuster_series_selon_budget(items_reels, budget, autoriser_bonus=(dominant != "explosivite"))

    resultats = []
    for it in items:
        entree, exo_obj, tier = it["entree"], it["exercise"], it["tier"]
        if exo_obj is None:
            resultats.append({
                "exercise_id": entree.get("exercise_id"),
                "name": entree.get("name"),
                "sets": it["sets"],
                "reps": f"{REP_RANGE_DEFAUT[0]}-{REP_RANGE_DEFAUT[1]}",
                "rest_seconds": None,
                "intensity": None,
                "notes": NOTE_ISOLATION,
            })
            continue

        resultats.append({
            "exercise_id": exo_obj.exercise_id,
            "name": entree.get("name") or getattr(exo_obj, "name", None),
            "sets": it["sets"],
            "reps": determine_rep_range(profile, exo_obj),
            "rest_seconds": calculate_rest_time(exo_obj, profile),
            "intensity": calculate_intensity(profile, exo_obj),
            "notes": _note_automatique(dominant, tier),
        })

    return {"exercises": resultats}
