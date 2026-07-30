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

# --- Séries par objectif x palier ---------------------------------------------
# Retour Samy (second problème identifié) : « les séries sont bloquées à 3 ».
#
# Diagnostic : `_sets_de_base` renvoyait `MIN_SETS_FLOOR` (3) pour TOUT ce qui
# n'était ni principal ni secondaire — donc pour toutes les isolations et tous
# les finisseurs, sans aucune exception ni condition. Comme une séance qui
# respecte le plancher d'exercices par muscle compte majoritairement des
# isolations, 74% des exercices d'un programme sortaient à 3 séries, et 100%
# des isolations. Le correctif précédent (#132) avait bien relevé les
# mouvements principaux à 4-5, mais n'avait jamais touché aux isolations.
#
# Même principe que pour les répétitions : le nombre de séries dépend du
# croisement objectif dominant x palier du mouvement. Le plancher de 3 reste
# un plancher — « 3 c'est le minimum, pas le plafond » — mais ce n'est plus
# une valeur par défaut appliquée faute de règle.
SETS_PAR_PALIER = {
    # Force : peu d'exercices, beaucoup de séries sur le mouvement lourd.
    ("force", exercise_order.TIER_PRINCIPAL): 5,
    ("force", exercise_order.TIER_SECONDAIRE): 4,
    ("force", exercise_order.TIER_ISOLATION): 3,
    ("force", exercise_order.TIER_FINISSEUR): 3,

    # Hypertrophie : le volume est le principal moteur de progression, il est
    # réparti sur l'ensemble de la séance et pas concentré sur un seul
    # mouvement. C'est ici que les isolations méritent 4 séries.
    ("hypertrophie", exercise_order.TIER_PRINCIPAL): 4,
    ("hypertrophie", exercise_order.TIER_SECONDAIRE): 4,
    # Isolation à 3 : c'est la dose utile, et surtout c'est ce qui crée un
    # ÉCART avec les mouvements composés (4-5). Les monter à 4 aussi revenait
    # simplement à déplacer le problème — tout à 4 au lieu de tout à 3.
    ("hypertrophie", exercise_order.TIER_ISOLATION): 3,
    ("hypertrophie", exercise_order.TIER_FINISSEUR): 3,

    # Endurance musculaire : séries longues, donc moins nombreuses.
    ("endurance_musculaire", exercise_order.TIER_PRINCIPAL): 4,
    ("endurance_musculaire", exercise_order.TIER_SECONDAIRE): 3,
    ("endurance_musculaire", exercise_order.TIER_ISOLATION): 3,
    ("endurance_musculaire", exercise_order.TIER_FINISSEUR): 3,

    # Perte de gras : maintien de la masse musculaire, volume soutenu sur les
    # mouvements structurants. En déficit calorique, c'est le maintien de
    # l'INTENSITÉ (charge) qui préserve le muscle, pas le volume — d'où des
    # plages proches de l'hypertrophie plutôt que des séries très longues.
    ("perte_de_gras", exercise_order.TIER_PRINCIPAL): 4,
    ("perte_de_gras", exercise_order.TIER_SECONDAIRE): 3,
    ("perte_de_gras", exercise_order.TIER_ISOLATION): 3,
    ("perte_de_gras", exercise_order.TIER_FINISSEUR): 3,

    # Explosivité : séries très courtes (2-5 répétitions), donc plus
    # nombreuses. L'ancienne version ramenait tout le monde à 3 sur cet
    # objectif, ce qui donnait un volume de travail dérisoire.
    ("explosivite", exercise_order.TIER_PRINCIPAL): 5,
    ("explosivite", exercise_order.TIER_SECONDAIRE): 4,
    ("explosivite", exercise_order.TIER_ISOLATION): 3,
    ("explosivite", exercise_order.TIER_FINISSEUR): 3,
}
SETS_DEFAUT = 3

# --- Couplage séries <-> répétitions ------------------------------------------
# Retour Samy, règle donnée explicitement :
#   « 3x c'est seulement pour les répétitions 12-15 (hypertrophie),
#     pour 10-12 c'est 4x, pour 8-10 c'est 4x, pour 6-8 et force c'est 5x »
#
# C'est la bonne façon de raisonner, et c'est ce qui manquait : le nombre de
# séries et la plage de répétitions étaient calculés INDÉPENDAMMENT l'un de
# l'autre, chacun depuis sa propre matrice. Rien ne garantissait leur
# cohérence — on pouvait obtenir 3 x 6-8, qui ne correspond à aucun schéma
# d'entraînement réel.
#
# Le volume total d'une série se conserve : moins on fait de répétitions, plus
# on fait de séries. Les séries découlent donc désormais de la plage de
# répétitions, qui reste calculée en premier (objectif x palier x niveau).
#
# Clé = borne BASSE de la plage de répétitions.
SETS_SELON_REPS = [
    # (rep_min_incluse, rep_max_incluse, séries)
    (1, 5, 5),     # force maximale
    (6, 7, 5),     # 6-8 -> 5x
    (8, 9, 4),     # 8-10 -> 4x
    (10, 11, 4),   # 10-12 -> 4x
    (12, 14, 3),   # 12-15 -> 3x
    (15, 19, 3),   # endurance musculaire
    (20, 99, 3),   # endurance longue
]


# Plages de répétitions autorisées, reprises telles quelles de la liste donnée
# par Samy (« exemples acceptés : 5-8, 8-10, 10-12, 12-15, 15-20 — pas de
# plages absurdes comme 8-20 »), complétées vers le bas pour la force et vers
# le haut pour l'endurance musculaire.
#
# Toute plage calculée est ramenée à la plus proche de cette liste. Sans ça,
# les modulations successives (unilatéral +2, plancher par niveau, progression
# sur le cycle) produisaient des écarts comme "14-22", qui ne correspondent à
# aucune intention d'entraînement lisible.
PLAGES_CANONIQUES = [
    (2, 5),    # force maximale
    (3, 6),
    (5, 8),
    (6, 8),
    (8, 10),
    (10, 12),
    (12, 15),
    (15, 20),
    (20, 25),
    (20, 30),  # endurance musculaire longue
]


def normaliser_plage(bas, haut):
    """Ramène une plage calculée à la plage canonique la plus proche.

    Critère : distance entre les deux bornes, la borne basse pesant double
    (c'est elle qui porte l'intention — travailler à 6 répétitions ou à 12
    n'est pas le même exercice)."""
    def distance(candidate):
        cb, ch = candidate
        return 2 * abs(cb - bas) + abs(ch - haut)

    return min(PLAGES_CANONIQUES, key=distance)


def sets_depuis_reps(reps, tier=None):
    """Nombre de séries déduit de la plage de répétitions (règle Samy).

    `reps` : chaîne "min-max", ou "min-max sec" pour un exercice tenu.
    `tier` : palier du mouvement, utilisé uniquement pour le plafond des
             isolations (une isolation ne dépasse jamais 4 séries).
    """
    texte = str(reps or "")
    est_duree = "sec" in texte

    try:
        bas = int(texte.split("-")[0].strip())
    except (ValueError, IndexError):
        return SETS_DEFAUT

    if est_duree:
        # Un maintien ne suit pas la même logique : 3 séries de gainage est la
        # dose de référence, 4 pour un maintien court et intense.
        return 4 if bas <= 20 else 3

    series = SETS_DEFAUT
    for borne_basse, borne_haute, valeur in SETS_SELON_REPS:
        if borne_basse <= bas <= borne_haute:
            series = valeur
            break

    # Une isolation reste plafonnée : 5 séries de curl n'apportent rien de plus
    # que 4, elles ajoutent seulement de la fatigue locale.
    if tier in (exercise_order.TIER_ISOLATION, exercise_order.TIER_FINISSEUR):
        series = min(series, 4)

    return series

# Bonus de séries pour les niveaux capables d'absorber plus de volume. Un
# pratiquant avancé récupère mieux et a besoin de plus de stimulus pour
# continuer à progresser ; un débutant progresse déjà pleinement à 3-4 séries
# et n'y gagnerait que de la fatigue.
BONUS_SETS_PAR_NIVEAU = {
    "Débutant complet": 0,
    "Quelques mois d'expérience": 0,
    "Intermédiaire": 0,
    "Avancé": 1,
}

# Plafond absolu par palier, pour que le bonus de niveau ne produise pas
# d'aberration (une isolation à 6 séries n'a aucun intérêt).
PLAFOND_SETS_PAR_PALIER = {
    exercise_order.TIER_PRINCIPAL: 6,
    exercise_order.TIER_SECONDAIRE: 5,
    exercise_order.TIER_ISOLATION: 4,
    exercise_order.TIER_FINISSEUR: 4,
}

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
    # Recalibré après question de Samy (« l'hypertrophie c'est pas plutôt 12 à
    # 15 reps ? »). Le réglage précédent envoyait tous les mouvements composés
    # en 6-8, ce qui est une zone de FORCE, pas d'hypertrophie — mal calibré
    # pour quelqu'un qui achète un programme de prise de muscle.
    #
    # État des connaissances sur lequel je m'appuie :
    #
    # - Schoenfeld, Grgic, Ogborn & Krieger (2017), méta-analyse comparant
    #   charges lourdes et légères : à volume égal et séries menées proche de
    #   l'échec, l'hypertrophie est comparable sur une large plage de charges.
    #   Autrement dit il n'existe pas UNE zone d'hypertrophie étroite : elle
    #   s'obtient d'environ 6 à 30 répétitions. En revanche les gains de FORCE
    #   maximale, eux, sont spécifiques à la charge et nettement supérieurs en
    #   charges lourdes — d'où la distinction maintenue entre les deux
    #   objectifs dans cette table.
    #
    # - Schoenfeld, Ogborn & Krieger (2017), relation dose-réponse : le volume
    #   hebdomadaire est le principal déterminant de l'hypertrophie. Or le
    #   volume se construit plus facilement en séries de 8 à 15 qu'en séries
    #   de 6 : à 6 répétitions, la fatigue nerveuse et articulaire limite le
    #   nombre de séries réellement exploitables.
    #
    # - Conséquence pratique, largement partagée par les praticiens qui
    #   s'appuient sur ces travaux (Helms, Israetel, Nippard) : centrer le
    #   travail d'hypertrophie autour de 6-12 sur les gros composés et de
    #   12-20 sur les isolations, où la charge absolue compte moins et où les
    #   répétitions plus hautes sont mieux tolérées par les articulations.
    #
    # Limite assumée : ces plages sont des repères de population, pas des
    # optima individuels. La progression de charge à répétitions constantes
    # reste le facteur qui décide, quelle que soit la fourchette retenue.
    ("hypertrophie", exercise_order.TIER_PRINCIPAL): (8, 12),
    ("hypertrophie", exercise_order.TIER_SECONDAIRE): (10, 12),
    ("hypertrophie", exercise_order.TIER_ISOLATION): (12, 15),
    ("hypertrophie", exercise_order.TIER_FINISSEUR): (15, 20),

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
    ("perte_de_gras", exercise_order.TIER_SECONDAIRE): (10, 12),
    ("perte_de_gras", exercise_order.TIER_ISOLATION): (12, 15),
    ("perte_de_gras", exercise_order.TIER_FINISSEUR): (15, 20),

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

# --- Exercices tenus en durée, pas en répétitions -----------------------------
# Retour Samy (séries/répétitions cohérentes avec le TYPE d'exercice, dont
# « isométrique ») : une planche prescrite en « 3 x 12-15 répétitions » n'a
# aucun sens — il n'y a pas de répétition dans un gainage, il y a un temps de
# maintien. Même chose pour les ports de charge (farmer's walk), qui se
# mesurent en durée ou en distance.
#
# `movement_type` est déjà présent sur chaque fiche du catalogue et déjà
# utilisé par `exercise_order` : on s'appuie dessus plutôt que d'ajouter un
# champ.
MOVEMENT_TYPES_EN_DUREE = ("isometrique", "carry")

# Durées de maintien en secondes, par objectif dominant. Repères usuels du
# travail isométrique : court et lourd pour la force, moyen pour
# l'hypertrophie/le gainage classique, long pour l'endurance.
DUREES_ISOMETRIQUES = {
    "force": (20, 30),
    "explosivite": (15, 25),
    "hypertrophie": (30, 45),
    "perte_de_gras": (40, 60),
    "endurance_musculaire": (45, 60),
}
DUREE_ISOMETRIQUE_DEFAUT = (30, 45)

# Un débutant ne tient pas une planche 45 secondes en gardant une position
# correcte : au-delà, c'est le bas du dos qui travaille, pas la sangle
# abdominale. On raccourcit donc, quitte à ajouter une série.
FACTEUR_DUREE_PAR_NIVEAU = {
    "Débutant complet": 0.7,
    "Quelques mois d'expérience": 0.85,
    "Intermédiaire": 1.0,
    "Avancé": 1.2,
}

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


# --- Format de travail par exercice -------------------------------------------
# Retour Samy : « les séries et les répétitions ne sont toujours pas cohérentes.
# Par exemple, tu proposes du 5x3-6 sur un exercice à la poulie, alors que ce
# n'est pas un exercice de force. »
#
# Il a raison, et c'est un angle mort de la version précédente : la plage était
# choisie par (objectif x PALIER). Or le palier dit seulement qu'un mouvement
# est structurant pour son muscle — pas qu'il se prête à des séries lourdes.
# Un tirage à la poulie peut parfaitement être le mouvement principal du dos
# d'une séance, il reste inadapté à du 3-6 : on ne fait pas de la force
# maximale sur une poulie, la charge n'est pas stable, il n'y a pas de
# contrainte axiale, et la marge de progression en charge est faible.
#
# On introduit donc un FORMAT DE TRAVAIL propre à l'exercice, indépendant de
# l'objectif de l'utilisateur, qui plafonne ce que l'exercice autorise :
#
#   "force"        : mouvements type SBD — barre libre, polyarticulaires,
#                    charge axiale, progression en charge illimitée.
#                    Seuls ceux-là descendent en dessous de 6 répétitions.
#   "hypertrophie" : composés aux haltères, machines convergentes, Smith.
#                    Zone 6-15, jamais de série lourde à 3 répétitions.
#   "isolation"    : poulies, isolations mono-articulaires. Zone 8-20.
#   "isometrique"  : maintiens, en secondes (traité en amont).
FORMAT_FORCE = "force"
FORMAT_HYPERTROPHIE = "hypertrophie"
FORMAT_ISOLATION = "isolation"
FORMAT_ISOMETRIQUE = "isometrique"

# Plancher de répétitions autorisé par format. C'est un GARDE-FOU : la plage
# calculée depuis l'objectif ne peut jamais descendre en dessous.
PLANCHER_REPS_PAR_FORMAT = {
    FORMAT_FORCE: 1,
    FORMAT_HYPERTROPHIE: 6,
    FORMAT_ISOLATION: 8,
    FORMAT_ISOMETRIQUE: 1,
}

# Mouvements de force au sens strict : les trois du powerlifting (squat, bench,
# deadlift) et leurs cousins directs à la barre libre.
MOTS_CLES_FORCE = (
    "squat", "développé couché", "developpe couche", "bench",
    "soulevé de terre", "souleve de terre", "deadlift",
    "développé militaire", "developpe militaire", "overhead press",
    "rowing barre", "pendlay", "front squat", "good morning",
    "hip thrust", "clean", "snatch", "épaulé", "epaule-jete",
)

# Un exercice à la poulie ou sur machine guidée n'est jamais un mouvement de
# force, quelle que soit la façon dont il est classé par ailleurs.
EQUIPEMENTS_NON_FORCE = ("machine", "poulie", "elastique", "poids_du_corps")


def format_de_travail(exercise):
    """Format de travail que l'exercice AUTORISE, indépendamment de l'objectif
    de l'utilisateur."""
    movement_type = getattr(exercise, "movement_type", None)
    if movement_type in MOVEMENT_TYPES_EN_DUREE:
        return FORMAT_ISOMETRIQUE

    nom = str(getattr(exercise, "name", "") or "").lower()
    equipement = [str(e).lower() for e in (getattr(exercise, "equipment", None) or [])]
    est_compose = movement_type in exercise_order.COMPOUND_MOVEMENT_TYPES

    sur_machine_ou_poulie = any(e in EQUIPEMENTS_NON_FORCE for e in equipement)
    a_la_barre = "barre" in equipement
    aux_halteres = "haltere" in equipement

    # Smith machine : guidée, donc jamais de la force maximale malgré la barre.
    if "smith" in nom or "guidé" in nom or "guide" in nom:
        return FORMAT_HYPERTROPHIE

    if sur_machine_ou_poulie:
        # Une machine convergente sur un mouvement composé reste un bon support
        # d'hypertrophie lourde ; une poulie d'isolation, non.
        return FORMAT_HYPERTROPHIE if est_compose else FORMAT_ISOLATION

    if a_la_barre and est_compose and any(k in nom for k in MOTS_CLES_FORCE):
        return FORMAT_FORCE

    if est_compose and (a_la_barre or aux_halteres):
        return FORMAT_HYPERTROPHIE

    return FORMAT_ISOLATION


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

    # --- Exercices tenus, pas répétés ---------------------------------------
    # Traité en premier : aucune des modulations ci-dessous (unilatéral,
    # progression, plancher par niveau) ne s'applique à une durée de maintien.
    if getattr(exercise, "movement_type", None) in MOVEMENT_TYPES_EN_DUREE:
        bas, haut = DUREES_ISOMETRIQUES.get(dominant, DUREE_ISOMETRIQUE_DEFAUT)
        facteur = FACTEUR_DUREE_PAR_NIVEAU.get(
            getattr(profile, "niveau_musculation", None), 1.0
        )
        # Arrondi à 5 secondes : un programme qui affiche « 31-47 sec » fait
        # faux, personne ne tient une planche à la seconde près.
        bas = max(10, int(round(bas * facteur / 5)) * 5)
        haut = max(bas + 10, int(round(haut * facteur / 5)) * 5)
        return f"{bas}-{haut} sec"

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

    # --- Garde-fou par format de travail ------------------------------------
    # Retour Samy : « tu proposes du 5x3-6 sur un exercice à la poulie, alors
    # que ce n'est pas un exercice de force ». Le plancher de l'exercice prime
    # sur celui de l'objectif : un profil "force" peut parfaitement recevoir
    # 3-6 sur son squat barre, jamais sur un tirage poulie.
    plancher_format = PLANCHER_REPS_PAR_FORMAT.get(
        format_de_travail(exercise), PLANCHER_REPS_PAR_FORMAT[FORMAT_ISOLATION]
    )
    if low < plancher_format:
        ecart = high - low
        low = plancher_format
        high = plancher_format + max(2, ecart)

    # Dernière étape : ramener à une plage canonique. Les modulations
    # ci-dessus (unilatéral, progression, plancher par niveau) s'accumulent et
    # produisaient sinon des écarts illisibles du type "14-22".
    low, high = normaliser_plage(low, high)

    return f"{low}-{high}"


def _sets_de_base(profile, exercise, dominant, recuperation_degradee=False):
    """Nombre de séries selon le PALIER du mouvement (principal > secondaire
    > isolation/finisseur) et le niveau (cf. `NIVEAU_SETS_PRINCIPAL`/
    `NIVEAU_SETS_SECONDAIRE` ci-dessus pour le raisonnement complet) — plus
    aucune comparaison à un budget de fatigue SESSION-WIDE ici (cf. diagnostic
    ci-dessus : ce total est structurellement dépassé dès qu'une séance
    respecte le plancher d'exercices par muscle #132, ce qui écrasait tout le
    monde à 3 séries sans distinction).

    Retour Samy (« les séries sont bloquées à 3 ») : cette fonction renvoyait
    `MIN_SETS_FLOOR` pour tout ce qui n'était ni principal ni secondaire, donc
    pour TOUTES les isolations et TOUS les finisseurs. Comme une séance en
    compte majoritairement, 74% du programme sortait à 3 séries. Le nombre de
    séries est désormais lu dans `SETS_PAR_PALIER` (objectif x palier), avec un
    bonus de niveau et un plafond par palier.

    Un seul cas ramène tout le monde au plancher : une récupération dégradée
    déclarée (`_recuperation_degradee`, sommeil très réduit et/ou stress
    élevé) — on réduit le volume, pas l'intensité ni la fréquence, quand la
    récupération est mauvaise.

    L'explosivité n'y est plus ramenée : ses séries sont très courtes (2 à 5
    répétitions), elles doivent donc être plus nombreuses, pas moins. Les
    ramener à 3 produisait un volume de travail dérisoire."""
    tier = exercise_order.classify_exercise(exercise)

    if recuperation_degradee:
        return MIN_SETS_FLOOR, tier

    niveau = getattr(profile, "niveau_musculation", None)
    sets = SETS_PAR_PALIER.get((dominant, tier), SETS_DEFAUT)
    sets += BONUS_SETS_PAR_NIVEAU.get(niveau, 0)

    # Plafond par palier, puis plancher global : "3 c'est le minimum, pas le
    # plafond" (retour Samy sur le volume).
    sets = min(sets, PLAFOND_SETS_PAR_PALIER.get(tier, 4))
    sets = max(sets, MIN_SETS_FLOOR)
    return sets, tier


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

        # Retour Samy : les séries découlent de la plage de répétitions
        # (12-15 -> 3x, 10-12 -> 4x, 8-10 -> 4x, 6-8 et force -> 5x), et non
        # d'un calcul indépendant qui pouvait produire des couples incohérents
        # comme "3 x 6-8". On calcule donc les répétitions d'abord, puis les
        # séries qui en découlent.
        #
        # `it["sets"]` (issu de `_sets_de_base`, puis éventuellement réduit par
        # le budget de fatigue) reste un PLAFOND : si la récupération du profil
        # est dégradée ou si la séance dépasse le budget, on ne remonte jamais
        # le volume au-dessus de ce qui a été arbitré en amont.
        reps_calculees = determine_rep_range(profile, exo_obj)
        sets_couples = sets_depuis_reps(reps_calculees, tier)
        sets_finaux = max(MIN_SETS_FLOOR, min(sets_couples, it["sets"])) \
            if it["sets"] < sets_couples else sets_couples

        resultats.append({
            "exercise_id": exo_obj.exercise_id,
            "name": entree.get("name") or getattr(exo_obj, "name", None),
            "sets": sets_finaux,
            "reps": reps_calculees,
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
