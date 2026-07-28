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
    "Débutant complet": (3, 4),
    "Quelques mois d'expérience": (3, 4),
    "Intermédiaire": (3, 4),
    "Avancé": (3, 5),
}
NIVEAU_SETS_RANGE_DEFAUT = NIVEAU_SETS_RANGE["Intermédiaire"]

# Retour Samy (prompt hors 24 phases, test en conditions réelles : "minimum 3
# série de 6 à 15 répétition selon si c'est de la force, de l'hypertrophie, à
# l'échec etc") : plancher relevé de 2 à 3 séries, quel que soit le niveau
# (bornes basses de `NIVEAU_SETS_RANGE` ci-dessus alignées en conséquence) —
# en dessous, mieux vaut retirer l'exercice de la séance que le vider de son
# intérêt (cf. `_retirer_exercices_si_besoin` ci-dessous, appelé quand 3
# séries partout dépasse encore le budget).
MIN_SETS_FLOOR = 3

# --- Répétitions (section 4) --------------------------------------------------
# Retour Samy (prompt hors 24 phases) : fourchettes resserrées entre 6 et 15
# répétitions (jamais en dessous de 6, jugé trop technique/risqué sans
# supervision réelle sur une appli non encadrée ; jamais au-dessus de 15,
# hors du champ hypertrophie/force qu'un programme généraliste doit couvrir),
# tout en gardant des paliers distincts selon l'objectif dominant (force <
# hypertrophie < perte de gras/endurance).
REP_RANGES = {
    "force": (6, 8),
    "hypertrophie": (8, 12),
    "endurance_musculaire": (12, 15),
    "perte_de_gras": (10, 15),
    "explosivite": (6, 8),
}
REP_RANGE_DEFAUT = REP_RANGES["hypertrophie"]

# --- Notes automatiques (section 7) ------------------------------------------
NOTE_PRINCIPALE = "Priorité à la technique et à la progression de charge."
NOTE_ISOLATION = "Contrôle du mouvement, amplitude complète."
NOTE_EXPLOSIVITE = "Recherche de vitesse maximale, arrêter si perte de qualité."

MESSAGE_EXERCICE_RETIRE_BUDGET = (
    "Un ou plusieurs exercices ont été retirés de cette séance : même réduits à 3 séries "
    "chacun (dose minimale pour rester utile), le total dépassait encore le budget de fatigue "
    "estimé pour ton profil. Mieux vaut une séance un peu plus courte mais correctement dosée "
    "qu'un volume dilué."
)

# --- Conseils d'exécution (prompt hors 24 phases, retour Samy : "j'aimerai
# que tu ajoutes des trucs du style contrôler la descente et pousser fort ou
# inversement, aller jusqu'à l'échec") -----------------------------------------
# Champ ADDITIF ("conseil_execution"), distinct de "notes" (déjà testé/figé,
# cf. test_prescription.py) : ne modifie ni ne remplace la logique de "notes"
# existante, s'ajoute simplement à côté dans le dict retourné par exercice.
CONSEIL_PAR_MOVEMENT_TYPE = {
    "push": "Contrôle la descente (2-3 secondes), puis pousse fort et de façon explosive en phase de remontée.",
    "pull": "Résiste à la descente/au retour de la charge, puis tire fort et de façon explosive.",
    "squat": "Descends de façon contrôlée jusqu'à ta profondeur maîtrisée, puis pousse fort dans le sol pour remonter.",
    "hinge": "Contrôle la descente de la charge le long des jambes, puis pousse fort dans le sol pour te redresser.",
    "lunge": "Descends de façon contrôlée, puis pousse fort pour remonter, sans à-coup.",
    "carry": "Garde le gainage serré et une marche contrôlée, sans précipitation.",
    "rotation": "Mouvement contrôlé sur toute l'amplitude, sans à-coup ni élan.",
    "isometrique": "Maintiens la position de façon stable, respiration régulière, jusqu'au temps ou à la fatigue ciblée.",
}
CONSEIL_DEFAUT = "Contrôle le mouvement sur toute l'amplitude, sans à-coup."
CONSEIL_ECHEC_FINISSEUR = "Sur la dernière série, cherche à aller proche de l'échec musculaire (1-2 répétitions en réserve max)."
CONSEIL_EXPLOSIVITE = "Vitesse maximale en phase concentrique ; arrête la série dès que la vitesse d'exécution chute nettement."

# Mapping exact vers les 4 mouvements sur lesquels le questionnaire demande un
# 1RM testé ou non (cf. profile.variables_json["pr_..."], questions ajoutées
# côté questionnaire) -> permet un conseil de calibrage de charge adapté.
PR_EXERCISE_IDS = {
    "developpe_couche_a_la_barre_libre_pecs": "pr_developpe_couche_barre",
    "developpe_couche_aux_halteres_pecs": "pr_developpe_couche_haltere",
    "squat_arriere_a_la_barre_back_squat_quadriceps": "pr_squat_barre",
    "souleve_de_terre_traditionnel_deadlift_a_la_barre_dos": "pr_souleve_de_terre",
}
CONSEIL_PR_CONNU = " Tu as déjà un repère de charge max sur ce mouvement : cale tes charges de travail sur un pourcentage connu de ce record plutôt que d'estimer à l'aveugle."
CONSEIL_PR_INCONNU = " Tu n'as pas encore de 1RM testé sur ce mouvement : monte progressivement sur tes 2-3 premières séries d'approche avant d'atteindre ton poids de travail, plutôt que d'estimer directement une charge."


def _conseil_execution(exercise, dominant, tier, profile):
    """Conseil d'exécution ADDITIF (tempo/intensité d'effort), distinct de
    `_note_automatique` (inchangée). Basé sur `movement_type` (déjà validé,
    cf. exercise_order.py) + objectif dominant + palier (isolation/finisseur
    -> recherche de l'échec sur la dernière série) + repère PR déclaré au
    questionnaire pour les 4 mouvements de référence, s'il y en a un."""
    if dominant == "explosivite" and tier in (exercise_order.TIER_PRINCIPAL, exercise_order.TIER_SECONDAIRE):
        conseil = CONSEIL_EXPLOSIVITE
    else:
        movement_type = getattr(exercise, "movement_type", None)
        conseil = CONSEIL_PAR_MOVEMENT_TYPE.get(movement_type, CONSEIL_DEFAUT)
        if tier in (exercise_order.TIER_ISOLATION, exercise_order.TIER_FINISSEUR):
            conseil = f"{conseil} {CONSEIL_ECHEC_FINISSEUR}"

    exercise_id = getattr(exercise, "exercise_id", None)
    champ_pr = PR_EXERCISE_IDS.get(exercise_id)
    if champ_pr is not None:
        variables_json = getattr(profile, "variables_json", None) or {}
        valeur = variables_json.get(champ_pr)
        if valeur == "Oui":
            conseil += CONSEIL_PR_CONNU
        elif valeur == "Non":
            conseil += CONSEIL_PR_INCONNU

    return conseil


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


def _retirer_exercices_si_besoin(items, budget, warnings, planchers=None):
    """Appelé quand, même en réduisant toutes les séries jusqu'au plancher
    réaliste (`MIN_SETS_FLOOR` = 2), le total de fatigue estimé dépasse
    encore le budget du profil. Plutôt que de continuer à dégrader les
    séries en dessous de leur dose minimale efficace (ce que faisait
    l'ancienne version -> "1 x 3-6", cf. retour Samy), retire des EXERCICES
    ENTIERS de la séance, dans le même ordre de priorité que la réduction de
    séries (finisseur, puis isolation, puis secondaire, puis en tout dernier
    recours principal) et JAMAIS en dessous du plancher retenu pour ce muscle
    (`planchers[muscle]`, cf. `workout_generator._muscles_ordonnes_par_
    priorite`/`volume.calculer_repartition_seance` — 1 par défaut si absent,
    même garantie minimale qu'avant). Marque les éléments retirés
    (`it["retire"] = True`) plutôt que de les supprimer de `items`, pour que
    l'appelant puisse les exclure du résultat final sans perdre la
    correspondance avec `workout["exercises"]` (cf.
    `program_builder.build_program`)."""
    planchers = planchers or {}

    def total():
        return sum(
            it["sets"] * _cout_fatigue_par_serie(it["exercise"])
            for it in items if not it.get("retire")
        )

    def muscle_de(it):
        return getattr(it["exercise"], "muscle_principal", None)

    ordre_retrait = [
        exercise_order.TIER_FINISSEUR,
        exercise_order.TIER_ISOLATION,
        exercise_order.TIER_SECONDAIRE,
        exercise_order.TIER_PRINCIPAL,
    ]
    retrait_applique = False
    for tier_a_retirer in ordre_retrait:
        while total() > budget:
            restants = [it for it in items if not it.get("retire")]
            comptes_par_muscle = {}
            for it in restants:
                comptes_par_muscle[muscle_de(it)] = comptes_par_muscle.get(muscle_de(it), 0) + 1
            candidats = [
                it for it in restants
                if it["tier"] == tier_a_retirer
                and comptes_par_muscle.get(muscle_de(it), 0) > planchers.get(muscle_de(it), 1)
            ]
            if not candidats:
                break
            candidats[0]["retire"] = True
            retrait_applique = True
        if total() <= budget:
            break

    if retrait_applique:
        warnings.append(MESSAGE_EXERCICE_RETIRE_BUDGET)

    return items


def _ajuster_series_selon_budget(items, budget, autoriser_bonus, warnings, planchers=None):
    """"Ne jamais dépasser le budget fatigue de séance" (section 3). Réduit
    d'abord les paliers les moins prioritaires (finisseur puis isolation puis
    secondaire puis, en dernier recours, principal) jusqu'au plancher
    réaliste `MIN_SETS_FLOOR` (3 séries, cf. retour Samy : "1x3-6 c'est
    complètement incohérent" puis "minimum 3 série" — en dessous, une
    prescription n'a plus de valeur d'entraînement documentée). Si le budget
    est encore dépassé à ce plancher, retire des exercices entiers
    (`_retirer_exercices_si_besoin`, jamais en dessous du plancher par muscle
    `planchers`) plutôt que de continuer à dégrader les séries. Accorde
    ensuite le "+1 série possible" aux mouvements composés (un seul palier de
    bonus, jamais cumulatif) si de la marge reste, principal d'abord."""

    def total():
        return sum(
            it["sets"] * _cout_fatigue_par_serie(it["exercise"])
            for it in items if not it.get("retire")
        )

    ordre_reduction = [
        exercise_order.TIER_FINISSEUR,
        exercise_order.TIER_ISOLATION,
        exercise_order.TIER_SECONDAIRE,
        exercise_order.TIER_PRINCIPAL,
    ]
    for tier_a_reduire in ordre_reduction:
        while total() > budget:
            candidats = [it for it in items if it["tier"] == tier_a_reduire and it["sets"] > MIN_SETS_FLOOR]
            if not candidats:
                break
            candidats[0]["sets"] -= 1
        if total() <= budget:
            break

    if total() > budget:
        _retirer_exercices_si_besoin(items, budget, warnings, planchers=planchers)

    if autoriser_bonus:
        for it in items:
            if it.get("retire"):
                continue
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
    "rest_seconds", "intensity", "notes"}], "warnings": [...]} — "warnings"
    (clé ADDITIVE, prompt hors 24 phases) n'est renseignée que si des
    exercices ont dû être retirés faute de budget de fatigue suffisant même
    au plancher de séries (cf. `_retirer_exercices_si_besoin`) ; vide sinon,
    rétrocompatible avec tout appelant qui ignorait déjà cette clé."""
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
    warnings = []
    # Additif (prompt hors 24 phases, retour Samy : plancher d'exercices par
    # muscle) : `workout["muscle_floors"]` expose le plancher retenu par
    # `workout_generator.generate_workout` (cf. sa docstring) -> jamais
    # retirer un exercice en dessous de ce plancher lors de l'ajustement du
    # budget de fatigue par les séries. Absent -> {} (plancher 1 par défaut
    # dans `_retirer_exercices_si_besoin`, comportement historique préservé).
    planchers = workout.get("muscle_floors") or {}
    _ajuster_series_selon_budget(
        items_reels, budget, autoriser_bonus=(dominant != "explosivite"),
        warnings=warnings, planchers=planchers,
    )

    resultats = []
    for it in items:
        if it.get("retire"):
            # Retiré par `_retirer_exercices_si_besoin` (budget de fatigue
            # dépassé même au plancher de séries) : absent du résultat plutôt
            # que présent avec des séries vides (cf. correspondance attendue
            # par `program_builder.build_program`, qui doit alors ignorer cet
            # exercice au lieu de l'afficher sans dosage).
            continue
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
                "conseil_execution": CONSEIL_DEFAUT,
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
            "conseil_execution": _conseil_execution(exo_obj, dominant, tier, profile),
        })

    return {"exercises": resultats, "warnings": warnings}
