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
# Retour Samy (prompt hors 24 phases, test en conditions réelles : "toute tes
# séances sont à 3 série, parfois tu peux mettre 4 et 5, renseigne toi bien
# quand et pourquoi les mettre, mais 3 c'est le minimum pas le plafond").
#
# Diagnostic du bug corrigé ici : depuis le relèvement du plancher d'exercices
# par muscle (#132 : min 3 exercices/muscle, 4 pour le muscle prioritaire),
# une séance complète contient désormais 10 à 16 exercices. L'ancienne version
# assignait bien 4-5 séries de base aux mouvements principaux/secondaires,
# MAIS comparait ensuite le coût total de la séance ENTIÈRE à
# `fatigue.calculate_fatigue_budget(profile)` (un budget calibré à l'époque où
# les séances comptaient beaucoup moins d'exercices) : ce total dépassait
# systématiquement ce budget, donc la réduction ramenait TOUT le monde à 3
# séries avant même d'envisager le bonus — y compris pour des profils bien
# reposés, sans aucune raison sport-science. Double-comptage : le nombre
# d'exercices de la séance est déjà correctement dimensionné en amont
# (workout_generator.py/volume.py, #132) ; ce n'est pas au budget de séries de
# re-limiter, en plus, le nombre de séries de chaque exercice déjà retenu
# selon ce même total déjà budgété une fois.
#
# Nouvelle règle (recherche : littérature volume/force-hypertrophie usuelle,
# type NSCA/Renaissance Periodization/travaux de Schoenfeld sur la relation
# dose-volume) : le nombre de séries dépend du PALIER du mouvement (le
# mouvement principal mérite plus de volume que les accessoires) et du niveau
# (un pratiquant avancé a la capacité de récupération pour absorber plus de
# volume sur son mouvement principal ; un débutant/intermédiaire progresse
# déjà très bien à 3-4 séries et n'a rien à gagner à en faire plus — juste
# plus de fatigue/risque technique) :
#   - mouvement PRINCIPAL (le plus structurant pour ce muscle) : 4 séries la
#     plupart des niveaux, 5 en Avancé (capacité de récupération plus élevée,
#     dernier levier de progression restant une fois la technique acquise) ;
#   - mouvement SECONDAIRE (second mouvement composé) : reste à 3 séries pour
#     Débutant/Quelques mois/Intermédiaire (volume déjà couvert par le
#     principal), 4 en Avancé (légèrement en dessous du principal, jamais à
#     égalité) ;
#   - isolation/finisseur : toujours 3 (le plancher) — l'isolation ne gagne
#     rien à un volume plus élevé par séance dans un cadre généraliste, et
#     multiplier ce bonus par les nombreux exercices d'isolation d'une séance
#     ferait exploser la fatigue totale sans bénéfice.
NIVEAU_SETS_PRINCIPAL = {
    "Débutant complet": 4,
    "Quelques mois d'expérience": 4,
    "Intermédiaire": 4,
    "Avancé": 5,
}
NIVEAU_SETS_PRINCIPAL_DEFAUT = NIVEAU_SETS_PRINCIPAL["Intermédiaire"]

NIVEAU_SETS_SECONDAIRE = {
    "Débutant complet": 3,
    "Quelques mois d'expérience": 3,
    "Intermédiaire": 3,
    "Avancé": 4,
}
NIVEAU_SETS_SECONDAIRE_DEFAUT = NIVEAU_SETS_SECONDAIRE["Intermédiaire"]

# Plancher absolu (Retour Samy : "3 c'est le minimum") : jamais en dessous,
# quel que soit le palier/niveau — en dessous, mieux vaut retirer l'exercice
# de la séance que le vider de son intérêt (cf. `_retirer_exercices_si_besoin`
# ci-dessous, toujours utilisé comme filet de sécurité pour le seul cas où la
# récupération réelle du profil est dégradée, cf. `_recuperation_degradee`).
MIN_SETS_FLOOR = 3

# Retour Samy (mêmes travaux) : la récupération réelle du profil (sommeil/
# stress déclarés) reste un frein légitime au volume, contrairement au nombre
# d'exercices de la séance (déjà pris en charge ailleurs, cf. ci-dessus) :
# sommeil très réduit et/ou stress élevé -> tout le monde reste au plancher
# (3 séries), quel que soit le palier/niveau, plutôt que d'ajouter du volume
# à un profil qui récupère déjà mal.
SOMMEIL_RECUPERATION_DEGRADEE = "Moins de 6h"
STRESS_RECUPERATION_DEGRADEE = "Élevé"


def _recuperation_degradee(profile):
    """True si le profil déclare une récupération dégradée (mauvais sommeil
    et/ou stress élevé) : dans ce cas, aucun bonus de séries au-delà du
    plancher (3), quel que soit le palier du mouvement/niveau — cohérent avec
    le principe sport-science "réduire le volume, pas l'intensité ni la
    fréquence, quand la récupération est mauvaise"."""
    return (
        getattr(profile, "sommeil", None) == SOMMEIL_RECUPERATION_DEGRADEE
        or getattr(profile, "stress", None) == STRESS_RECUPERATION_DEGRADEE
    )

# --- Répétitions (section 4) --------------------------------------------------
# Retour Samy : « les répétitions sont presque toujours entre 6 et 8, je n'aime
# pas du tout. On avait pourtant défini une logique précise. »
#
# Diagnostic de l'ancienne version : REP_RANGES ne contenait QU'UNE plage par
# objectif, et `determine_rep_range` ignorait explicitement le paramètre
# `exercise`. Conséquence : sur un objectif dominant "force", les 10 à 16
# exercices d'une séance sortaient TOUS en 6-8, du squat barre au curl poulie.
# Une plage unique par objectif ne pouvait pas produire autre chose.
#
# Nouvelle logique : la plage dépend du croisement objectif x PALIER du
# mouvement, parce que c'est le palier qui porte l'information utile. Un
# mouvement principal lourd et un exercice d'isolation ne se travaillent pas
# dans la même zone de répétitions, même pour un objectif identique — charger
# un curl en 3 répétitions n'a pas de sens, et faire du squat en 25 non plus.
#
# Les plages reprennent celles demandées :
#   Force               : 1-5 (force maximale), 3-6 / 4-6 (exercices lourds),
#                         6-8 uniquement quand c'est pertinent
#   Hypertrophie        : 8-10, 10-12, 12-15 — les plus fréquentes
#   Endurance musculaire: 15-20, 20-30
#
# Clé = (objectif_dominant, palier) -> (min, max)
REP_RANGES_PAR_PALIER = {
    # --- Force ---------------------------------------------------------------
    # Le mouvement principal porte le travail lourd. Les accessoires restent en
    # zone hypertrophie : c'est le volume qui soutient la force sur le long
    # terme, pas la répétition de séries très courtes sur chaque exercice.
    ("force", exercise_order.TIER_PRINCIPAL): (3, 6),
    ("force", exercise_order.TIER_SECONDAIRE): (5, 8),
    ("force", exercise_order.TIER_ISOLATION): (8, 12),
    ("force", exercise_order.TIER_FINISSEUR): (10, 15),

    # --- Hypertrophie --------------------------------------------------------
    # Le cœur du programme, et de loin le cas le plus fréquent. Les trois
    # plages demandées (8-10, 10-12, 12-15) se répartissent naturellement du
    # mouvement le plus lourd au plus léger.
    ("hypertrophie", exercise_order.TIER_PRINCIPAL): (6, 10),
    ("hypertrophie", exercise_order.TIER_SECONDAIRE): (8, 12),
    ("hypertrophie", exercise_order.TIER_ISOLATION): (10, 15),
    ("hypertrophie", exercise_order.TIER_FINISSEUR): (12, 20),

    # --- Endurance musculaire ------------------------------------------------
    ("endurance_musculaire", exercise_order.TIER_PRINCIPAL): (10, 15),
    ("endurance_musculaire", exercise_order.TIER_SECONDAIRE): (12, 20),
    ("endurance_musculaire", exercise_order.TIER_ISOLATION): (15, 20),
    ("endurance_musculaire", exercise_order.TIER_FINISSEUR): (20, 30),

    # --- Perte de gras -------------------------------------------------------
    # Objectif d'entretien de la masse musculaire en déficit : on garde de la
    # charge sur les mouvements principaux (c'est ce qui préserve le muscle) et
    # on monte les répétitions sur les accessoires pour la densité de séance.
    ("perte_de_gras", exercise_order.TIER_PRINCIPAL): (8, 12),
    ("perte_de_gras", exercise_order.TIER_SECONDAIRE): (10, 15),
    ("perte_de_gras", exercise_order.TIER_ISOLATION): (12, 20),
    ("perte_de_gras", exercise_order.TIER_FINISSEUR): (15, 25),

    # --- Explosivité ---------------------------------------------------------
    # Séries très courtes sur les mouvements principaux (qualité du geste,
    # vitesse maximale), accessoires en hypertrophie classique.
    ("explosivite", exercise_order.TIER_PRINCIPAL): (2, 5),
    ("explosivite", exercise_order.TIER_SECONDAIRE): (4, 6),
    ("explosivite", exercise_order.TIER_ISOLATION): (8, 12),
    ("explosivite", exercise_order.TIER_FINISSEUR): (10, 15),
}

# Plancher de répétitions par niveau. Les séries très courtes (1-5) supposent
# une technique solide et un échauffement sérieux : on ne les prescrit pas à
# quelqu'un qui débute, sans supervision. Un débutant "force" travaillera donc
# en 6-8 sur son mouvement principal — c'est ici, et seulement ici, que le 6-8
# reste légitime.
PLANCHER_REPS_PAR_NIVEAU = {
    "Débutant complet": 8,
    "Quelques mois d'expérience": 6,
    "Intermédiaire": 4,
    "Avancé": 1,
}
PLANCHER_REPS_DEFAUT = 6

REP_RANGE_DEFAUT = (8, 12)

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


# --- Effort cible / travail à l'échec -----------------------------------------
# Retour Samy : « travail à l'échec, lorsque c'est demandé : AMRAP, jusqu'à
# l'échec, RIR 0, RPE 10 ».
#
# Le questionnaire ne pose aucune question sur le travail à l'échec. Plutôt
# que d'en ajouter une, on le rattache au PALIER du mouvement, ce qui est à la
# fois plus sûr et plus juste : aller à l'échec sur un squat lourd ou un
# soulevé de terre est le meilleur moyen de se blesser et de compromettre les
# séances suivantes, alors que sur une extension à la poulie, c'est sans risque
# et c'est précisément là que ça rapporte.
#
# RIR = répétitions en réserve (nombre de répétitions qu'il te restait à la fin
# de la série). RIR 0 = échec. RPE 10 = échec également, sur l'échelle d'effort
# perçu.
EFFORT_PAR_PALIER = {
    exercise_order.TIER_PRINCIPAL: (
        "RIR 2-3 — arrête chaque série avec 2 à 3 répétitions encore en réserve. "
        "Sur un mouvement lourd, aller à l'échec dégrade la technique et la "
        "récupération sans rien apporter de plus."
    ),
    exercise_order.TIER_SECONDAIRE: (
        "RIR 1-2 — arrête avec 1 à 2 répétitions en réserve, sauf sur la dernière "
        "série où tu peux aller au contact de l'échec si la technique tient."
    ),
    exercise_order.TIER_ISOLATION: (
        "RIR 0-1 — les dernières répétitions doivent être difficiles. Sur la "
        "dernière série, va jusqu'à l'échec musculaire (RIR 0 / RPE 10)."
    ),
    exercise_order.TIER_FINISSEUR: (
        "AMRAP sur la dernière série — autant de répétitions que possible, "
        "jusqu'à l'échec (RIR 0 / RPE 10). C'est le rôle d'un finisseur."
    ),
}

# Un débutant n'a ni la technique ni la lecture de ses sensations pour aller à
# l'échec sans risque : on garde une marge partout, quel que soit le palier.
EFFORT_DEBUTANT = (
    "RIR 2-3 — garde toujours 2 à 3 répétitions en réserve. À ce stade, la "
    "régularité et la technique font progresser bien plus vite que la recherche "
    "de l'échec, qui augmente surtout le risque de blessure."
)

# Sur un objectif explosivité, la série s'arrête à la perte de vitesse, jamais
# à l'épuisement : c'est le principe même du travail de puissance.
EFFORT_EXPLOSIVITE = (
    "Arrête la série dès que la vitesse d'exécution chute nettement, sans "
    "jamais chercher l'échec : en explosivité, c'est la qualité du geste qui "
    "compte, pas le nombre de répétitions arrachées."
)


def _effort_cible(dominant, tier, profile):
    """Consigne d'effort (RIR / AMRAP / échec) pour un exercice donné."""
    if dominant == "explosivite" and tier in (exercise_order.TIER_PRINCIPAL,
                                              exercise_order.TIER_SECONDAIRE):
        return EFFORT_EXPLOSIVITE
    if getattr(profile, "niveau_musculation", None) == "Débutant complet":
        return EFFORT_DEBUTANT
    return EFFORT_PAR_PALIER.get(tier, EFFORT_PAR_PALIER[exercise_order.TIER_SECONDAIRE])


def _dominant_objective(profile):
    vector = objectives.get_objective_vector(profile)
    return max(vector, key=vector.get)


def determine_rep_range(profile, exercise, semaine=1):
    """determine_rep_range(profile, exercise, semaine=1) -> "min-max" (chaîne).

    Retour Samy : « le nombre de répétitions doit varier automatiquement selon
    l'objectif, le type d'exercice, le niveau et la période de progression. Je
    ne veux pas voir quasiment tous les exercices en 6-8 répétitions. »

    Les quatre facteurs demandés interviennent ici :

    1. OBJECTIF — dominante du vecteur d'objectifs (`objectives`).
    2. TYPE D'EXERCICE — via le palier du mouvement (`exercise_order`), qui
       distingue mouvement principal, secondaire, isolation et finisseur. C'est
       ce paramètre qui manquait entièrement : il était reçu puis ignoré.
    3. NIVEAU — plancher de répétitions (`PLANCHER_REPS_PAR_NIVEAU`) : les
       séries très courtes ne sont pas prescrites à un débutant.
    4. PÉRIODE DE PROGRESSION — la semaine dans le cycle décale légèrement la
       plage vers le lourd, façon progression en intensité.
    """
    dominant = _dominant_objective(profile)
    tier = exercise_order.classify_exercise(exercise)

    low, high = REP_RANGES_PAR_PALIER.get((dominant, tier), REP_RANGE_DEFAUT)

    # --- Modulation par exercice --------------------------------------------
    # Un mouvement unilatéral se fait par côté : on ne descend pas aussi bas en
    # répétitions que sur son équivalent bilatéral, la charge absolue étant
    # mécaniquement plus faible.
    if getattr(exercise, "unilateral", False):
        low, high = low + 2, high + 2

    # --- Progression sur le cycle -------------------------------------------
    # Semaine 1-2 : plage nominale. Semaine 3-4 : on resserre d'un cran vers le
    # bas de la fourchette (charges plus lourdes, mêmes séries). Semaine 5+ :
    # retour à la plage nominale, façon décharge/reprise de cycle.
    phase = ((int(semaine) - 1) % 4) + 1 if semaine else 1
    if phase in (3, 4) and high - low >= 3:
        high -= 1
        if dominant in ("force", "explosivite"):
            low = max(1, low - 1)

    # --- Plancher de sécurité par niveau ------------------------------------
    plancher = PLANCHER_REPS_PAR_NIVEAU.get(
        getattr(profile, "niveau_musculation", None), PLANCHER_REPS_DEFAUT
    )
    if low < plancher:
        ecart = high - low
        low = plancher
        high = max(plancher + max(2, ecart), high)

    return f"{low}-{high}"


def _sets_de_base(profile, exercise, dominant, recuperation_degradee=False):
    """Nombre de séries selon le PALIER du mouvement (principal > secondaire
    > isolation/finisseur) et le niveau (cf. `NIVEAU_SETS_PRINCIPAL`/
    `NIVEAU_SETS_SECONDAIRE` ci-dessus pour le raisonnement complet) — plus
    aucune comparaison à un budget de fatigue SESSION-WIDE ici (cf. diagnostic
    ci-dessus : ce total est structurellement dépassé dès qu'une séance
    respecte le plancher d'exercices par muscle #132, ce qui écrasait tout le
    monde à 3 séries sans distinction).

    Deux cas ramènent tout le monde au plancher (3), quel que soit le
    palier/niveau :
      - objectif dominant = explosivité (scénario de test "explosivité ->
        faible volume", section 8 : qualité du geste > quantité, cohérent
        avec le principe d'entraînement de la puissance) ;
      - récupération dégradée déclarée (`_recuperation_degradee`, sommeil
        très réduit et/ou stress élevé) : on réduit le volume, pas
        l'intensité ni la fréquence, quand la récupération est mauvaise."""
    tier = exercise_order.classify_exercise(exercise)

    if dominant == "explosivite" or recuperation_degradee:
        return MIN_SETS_FLOOR, tier

    niveau = getattr(profile, "niveau_musculation", None)
    if tier == exercise_order.TIER_PRINCIPAL:
        return NIVEAU_SETS_PRINCIPAL.get(niveau, NIVEAU_SETS_PRINCIPAL_DEFAUT), tier
    if tier == exercise_order.TIER_SECONDAIRE:
        return NIVEAU_SETS_SECONDAIRE.get(niveau, NIVEAU_SETS_SECONDAIRE_DEFAUT), tier
    return MIN_SETS_FLOOR, tier


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
    au plancher de séries, UNIQUEMENT quand la récupération du profil est
    dégradée (cf. `_recuperation_degradee`/`_retirer_exercices_si_besoin`) ;
    vide sinon, rétrocompatible avec tout appelant qui ignorait déjà cette
    clé."""
    lookup = {}
    if available_exercises:
        lookup = {getattr(ex, "exercise_id", None): ex for ex in available_exercises}

    dominant = _dominant_objective(profile)
    recuperation_degradee = _recuperation_degradee(profile)

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
            it["sets"], it["tier"] = MIN_SETS_FLOOR, exercise_order.TIER_ISOLATION
        else:
            it["sets"], it["tier"] = _sets_de_base(profile, it["exercise"], dominant, recuperation_degradee)

    items_reels = [it for it in items if it["exercise"] is not None]
    warnings = []
    # Additif (prompt hors 24 phases, retour Samy : plancher d'exercices par
    # muscle) : `workout["muscle_floors"]` expose le plancher retenu par
    # `workout_generator.generate_workout` (cf. sa docstring) -> jamais
    # retirer un exercice en dessous de ce plancher lors de l'ajustement du
    # budget de fatigue par les séries. Absent -> {} (plancher 1 par défaut
    # dans `_retirer_exercices_si_besoin`, comportement historique préservé).
    planchers = workout.get("muscle_floors") or {}
    # Le budget de fatigue de séance (`fatigue.calculate_fatigue_budget`) ne
    # sert plus qu'au SEUL cas où la récupération est dégradée (cf. diagnostic
    # détaillé au-dessus de `NIVEAU_SETS_PRINCIPAL`) : dans ce cas, tout le
    # monde est déjà au plancher (3) via `_sets_de_base` ci-dessus ; si même ce
    # plancher dépasse encore le budget (catalogue trop pauvre en alternatives
    # pour ce muscle), on retire des exercices entiers plutôt que de descendre
    # sous la dose minimale efficace (comportement inchangé de
    # `_retirer_exercices_si_besoin`). Hors récupération dégradée, le nombre
    # d'exercices de la séance est déjà budgété correctement en amont
    # (workout_generator.py/volume.py) : aucune re-vérification ici.
    if recuperation_degradee:
        budget = calculate_fatigue_budget(profile)
        total_au_plancher = sum(
            it["sets"] * _cout_fatigue_par_serie(it["exercise"]) for it in items_reels
        )
        if total_au_plancher > budget:
            _retirer_exercices_si_besoin(items_reels, budget, warnings, planchers=planchers)

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
            # Champ ADDITIF (retour Samy, travail à l'échec) : consigne d'effort
            # explicite en RIR/AMRAP, calée sur le palier du mouvement. Les
            # consommateurs existants du dict ignorent simplement cette clé.
            "effort": _effort_cible(dominant, tier, profile),
        })

    return {"exercises": resultats, "warnings": warnings}
