# -*- coding: utf-8 -*-
"""
Moteur de génération du programme cardio, séparé du programme de musculation.
Détermine un mix de types de séance (endurance fondamentale / fractionné /
sprints) selon l'objectif, puis un protocole concret selon le type de cardio
pratiqué (course, vélo, natation, circuit training, autre).

Retour Samy (prompt hors 24 phases, #150) : "Pour le programme cardio propose
jusqu'à 5 séances doit y être intégré du sprint 8-12 x 400m, 4-6 x 800m, 3-5
1000-1200m-2000m, course allure objectif(8-10-12-15-20), 2x6km, 2x8km,
Endurance fondamentale selon objectif etc fais des recherches mais je veux
vraiment une gamme diversifiée de séance cardio... il en faut vraiment
beaucoup pour pouvoir personnaliser la séance."

Chaque combinaison (type de séance x discipline) dispose donc de PLUSIEURS
variantes concrètes (au lieu d'un protocole unique et toujours identique),
choisies parmi une bibliothèque construite à partir de principes
d'entraînement établis (sources consultées lors de ce round : la méthode des
5 allures de Jack Daniels -- E/M/T/I/R et la répartition ~80% aisé / ~20%
intense qui en découle --, le repère "sortie longue = 20-30% du volume
hebdomadaire, +10%/semaine max" pour la course à pied, les structures de
séances fractionnées natation (ex: 10x50m/15s repos, 5x100m/20-30s repos) et
les zones d'entraînement cyclisme (endurance/sweet-spot/seuil/VO2max/sprint),
adaptées ici en %FCmax et ressenti d'effort car le questionnaire ne collecte
pas de données de puissance (FTP/capteur)) :
- Course : sprints 400m/800m/1000-2000m, séance à allure objectif, sortie
  longue progressive (échelle "2x6km, 2x8km" calibrée par niveau), côtes,
  lignes droites.
- Vélo : sweet-spot, seuil, VO2max, sprints, sortie longue.
- Natation : séries 50m/100m/200m à repos croissant selon l'intensité visée.
- Circuit training : rotation de machines, format Tabata, circuit poids du
  corps/cardio mixte.
Une variante est choisie de façon stable par profil (même principe que
`program_builder.py::_signature_jitter` pour la diversité Séance A/B/C en
musculation) : un même profil obtient toujours la même variante pour une
séance donnée (déterminisme préservé), mais des séances différentes de la
même semaine -- et des profils différents -- ont des variantes différentes.
"""
import hashlib

from logic import cardio_protocols, cardio_zones

# Libellé exact de l'option "préparer une course" dans le questionnaire
# (static/script.js, champ `objectif_cardio`). Centralisé ici pour éviter de
# le recopier dans chaque test d'égalité.
COURSE_OBJECTIF = "Me préparer à une course (5km, 10km, semi, marathon)"


def _variante_jitter(signature, cle):
    """Nombre stable dérivé de la signature du profil + d'une clé (nom de
    séance/discipline). Même principe que `_signature_jitter` dans
    `program_builder.py` : garantit qu'un même profil régénère toujours la
    même variante de séance cardio (déterminisme), tout en variant réellement
    d'une séance à l'autre dans la semaine (clé différente) et d'un profil à
    l'autre (signature différente)."""
    if not signature:
        return 0
    digest = hashlib.md5(f"{signature}::{cle}".encode("utf-8")).hexdigest()
    return int(digest[:4], 16)


def _sortie_longue_course(niveau_cardio):
    """Retour Samy : "2x6km, 2x8km" -- interprété comme une sortie longue
    progressive par paliers plutôt qu'une distance fixe et unique pour tout le
    monde, calibrée par niveau (principe reconnu : la sortie longue représente
    environ 20-30% du volume hebdomadaire, progression +10%/semaine max pour
    limiter le risque de blessure)."""
    if niveau_cardio == "Débutant":
        return (
            "Sortie longue à allure conversationnelle : 4 à 5 km, en augmentant "
            "d'environ 500 m à 1 km toutes les 1 à 2 semaines si la séance reste "
            "confortable (règle des +10%/semaine pour limiter le risque de blessure)."
        )
    if niveau_cardio == "Confirmé":
        return (
            "Sortie longue à allure conversationnelle : 8 à 12 km. Progresse par "
            "paliers (ex : 2 sorties à 8 km, puis 2 sorties à 10 km, puis 2 à "
            "12 km) plutôt que d'augmenter la distance à chaque séance."
        )
    return (
        "Sortie longue à allure conversationnelle : 6 à 8 km. Progresse par "
        "paliers (ex : 2 sorties à 6 km, puis 2 sorties à 8 km) plutôt que "
        "d'augmenter la distance à chaque séance, pour laisser le corps s'adapter."
    )


# Retour Samy (prompt hors 24 phases : "adapte le questionnaire pour le
# cardio (course à pied, natation, vélo, circuit training cardio en salle)") :
# "Circuit training" est désormais une discipline à part entière (auparavant
# fondue dans "Autre", jamais distinguée dans les protocoles ci-dessous).
#
# Chaque valeur est une fonction (niveau_cardio) -> list[str] : la liste des
# variantes concrètes disponibles pour cette combinaison type x discipline.
PROTOCOLS_VARIANTS = {
    "Endurance fondamentale": {
        "Course": lambda niveau: [
            "30 à 45 min à allure conversationnelle (60-70% FCmax), en continu.",
            _sortie_longue_course(niveau),
            "35 à 40 min à allure conversationnelle, avec 4 à 6 accélérations "
            "(« lignes droites ») de 15 à 20 sec à allure vive toutes les 5 à "
            "8 min, retour au calme progressif après chacune.",
        ],
        "Vélo": lambda niveau: [
            "40 à 50 min à intensité modérée (60-70% FCmax), cadence régulière.",
            "Sortie longue : 60 à 90 min à allure d'endurance (65-75% FCmax), "
            "cadence fluide (80-90 tr/min), en augmentant la durée progressivement.",
        ],
        "Natation": lambda niveau: [
            "30 à 40 min à allure régulière, technique fluide, sans forcer.",
            "200 m d'échauffement facile, puis 6 à 8 x 100 m à allure régulière "
            "/ 20 sec de repos, puis 200 m de retour au calme.",
        ],
        "Circuit training": lambda niveau: [
            "30 à 40 min de machines cardio enchaînées (tapis, elliptique, "
            "rameur) à intensité modérée (60-70% FCmax), en continu ou en "
            "rotation entre machines.",
        ],
        "Autre": lambda niveau: [
            "30 à 45 min d'activité continue à intensité modérée (60-70% FCmax).",
        ],
    },
    "Fractionné": {
        "Course": lambda niveau: [
            "10 à 15 min d'échauffement, puis 8 à 12 x 400 m à allure vive (un "
            "peu plus rapide que ton allure 5 km) / 90 sec récupération "
            "trottinée ou marchée, puis 10 min de retour au calme.",
            "10 à 15 min d'échauffement, puis 4 à 6 x 800 m à allure soutenue "
            "(proche de ton allure 10 km) / 2 à 3 min récupération trottinée, "
            "puis retour au calme.",
            "10 à 15 min d'échauffement, puis 3 à 5 x (1000 m, 1200 m, 1500 m, "
            "2000 m -- distances croissantes) à allure seuil (un peu plus lente "
            "que ton allure 10 km, tenable environ 1h) / 2 à 3 min récupération, "
            "puis retour au calme.",
            "10 min d'échauffement, puis une portion à allure objectif (ex : 3 "
            "à 6 km selon ta distance visée -- 8, 10, 12, 15 ou 20 km) courue à "
            "l'allure que tu vises pour ton objectif, pour habituer ton corps "
            "au rythme de course visé, puis retour au calme.",
        ],
        "Vélo": lambda niveau: [
            "10 min d'échauffement, puis 8 à 10 x 1 min effort intense (85-90% "
            "FCmax) / 2 min récupération légère, puis 10 min de retour au calme.",
            "10 min d'échauffement, puis 3 à 4 x 8 à 10 min à intensité "
            "« confortablement dure » (80-85% FCmax) / 4 à 5 min récupération "
            "facile, puis retour au calme.",
            "10 min d'échauffement, puis 2 x 15 à 20 min à allure seuil (85-90% "
            "FCmax, tenable environ 1h) / 5 min récupération facile, puis "
            "retour au calme.",
        ],
        "Natation": lambda niveau: [
            "10 x 50 m à allure vive / 15 sec repos, technique soignée sur "
            "chaque longueur.",
            "5 x 100 m à allure soutenue / 20 à 30 sec repos entre chaque.",
            "4 x 200 m à allure seuil (tenable environ 15-20 min) / 30 à 40 sec "
            "repos.",
        ],
        "Circuit training": lambda niveau: [
            "10 min d'échauffement, puis circuit de 5 à 6 machines/exercices "
            "cardio (tapis, rameur, vélo, corde à sauter...) 45 sec effort "
            "intense / 15 sec transition, 3 à 4 tours, puis retour au calme.",
            "10 min d'échauffement, puis circuit de 6 à 8 exercices "
            "cardio/poids du corps enchaînés (30 sec effort / 15 sec "
            "transition), 3 tours, avec 2 min de repos entre chaque tour.",
        ],
        "Autre": lambda niveau: [
            "10 min d'échauffement, puis 8 à 10 x 30-45 sec effort intense / "
            "1 à 2 min récupération, puis retour au calme.",
        ],
    },
    "Sprints / explosivité": {
        "Course": lambda niveau: [
            "10 à 15 min d'échauffement complet, puis 6 à 10 x 15-20 sec "
            "sprint maximal / 2 à 3 min récupération complète (marche), puis "
            "retour au calme.",
            "10 à 15 min d'échauffement, puis 8 à 10 x 100 m lancés "
            "(accélération progressive puis vitesse maximale) / 2 min "
            "récupération marchée.",
            "10 à 15 min d'échauffement, puis 8 à 10 x 20-30 sec en côte à "
            "intensité maximale (pente 4-8%) / descente en trottinant comme "
            "récupération.",
        ],
        "Vélo": lambda niveau: [
            "10 à 15 min d'échauffement, puis 6 à 8 x 15-20 sec sprint à fond "
            "/ 3 min récupération, puis retour au calme.",
            "10 à 15 min d'échauffement, puis 5 à 6 x 3 min à intensité très "
            "élevée (90-95% FCmax) / 3 min récupération facile, puis retour "
            "au calme.",
        ],
        "Natation": lambda niveau: [
            "10 à 15 min d'échauffement, puis 6 à 8 x 25 m sprint maximal / "
            "2 min récupération complète.",
            "10 à 15 min d'échauffement, puis 8 x 25 m départ dans l'eau à "
            "vitesse maximale / retour nagé tranquille comme récupération.",
        ],
        "Circuit training": lambda niveau: [
            "10 à 15 min d'échauffement, puis 6 à 8 x 20 sec effort maximal "
            "sur machine cardio (tapis rapide, vélo, rameur) / 2 à 3 min "
            "récupération complète.",
            "10 à 15 min d'échauffement, puis format Tabata : 8 x 20 sec "
            "effort maximal / 10 sec repos (un bloc de 4 min), répété 2 à 3 "
            "fois avec 2 min de récupération entre les blocs, sur la machine "
            "de ton choix.",
        ],
        "Autre": lambda niveau: [
            "10 à 15 min d'échauffement, puis 6 à 10 x 15-20 sec effort "
            "maximal / 2 à 3 min récupération complète.",
        ],
    },
    "Endurance légère": {
        "Course": lambda niveau: [
            "20 à 25 min à intensité légère, juste pour la santé cardiovasculaire.",
        ],
        "Vélo": lambda niveau: [
            "20 à 25 min à intensité légère, cadence tranquille.",
        ],
        "Natation": lambda niveau: [
            "20 à 25 min à allure détente.",
        ],
        "Circuit training": lambda niveau: [
            "20 à 25 min de machine(s) cardio au choix à intensité légère, "
            "cadence tranquille.",
        ],
        "Autre": lambda niveau: [
            "20 à 25 min d'activité à intensité légère.",
        ],
    },
}


# Les 12 types de séance ajoutés (Tempo, Seuil, VMA courte/longue, Côtes,
# Fartlek, Sortie longue, Récupération active, allures spécifiques) vivent dans
# `cardio_protocols.py` et sont fusionnés ici. Les 4 types historiques définis
# ci-dessus ne sont pas modifiés : en cas de collision de clé, c'est la
# définition historique qui gagne.
for _type, _table in cardio_protocols.PROTOCOLS_SUPPLEMENTAIRES.items():
    PROTOCOLS_VARIANTS.setdefault(_type, _table)


def _choisir_protocole(type_seance, discipline, niveau_cardio, signature, cle_variete):
    """Choisit une variante concrète parmi celles disponibles pour ce type de
    séance x discipline, de façon stable par profil (cf. `_variante_jitter`).

    Robustesse : l'ancienne version indexait directement
    `PROTOCOLS_VARIANTS[type][discipline]` et levait une KeyError si l'un des
    deux manquait. Avec 16 types de séance et 5 disciplines, une combinaison
    oubliée ferait planter la génération complète du programme pour un simple
    trou de catalogue. On replie donc proprement : discipline inconnue ->
    "Autre" ; type inconnu -> endurance fondamentale (la séance la plus sûre
    quel que soit le profil).
    """
    table = PROTOCOLS_VARIANTS.get(type_seance) or PROTOCOLS_VARIANTS["Endurance fondamentale"]
    fabrique = table.get(discipline) or table.get("Autre")
    if fabrique is None:
        fabrique = PROTOCOLS_VARIANTS["Endurance fondamentale"]["Autre"]

    variantes = fabrique(niveau_cardio) or []
    if not variantes:
        return PROTOCOLS_VARIANTS["Endurance fondamentale"]["Autre"](niveau_cardio)[0]
    if len(variantes) == 1:
        return variantes[0]
    idx = _variante_jitter(signature, cle_variete) % len(variantes)
    return variantes[idx]


OBJECTIF_CARDIO_NOTES = {
    "Perdre du poids / sécher": (
        "Vu ton objectif de perte de poids, le fractionné est privilégié : il maximise la dépense "
        "calorique et la consommation d'oxygène post-effort (afterburn), en plus des séances "
        "d'endurance fondamentale qui brûlent des graisses à intensité modérée sur la durée."
    ),
    "Améliorer mon endurance générale": (
        "Vu ton objectif d'endurance, l'accent est mis sur l'endurance fondamentale : c'est elle qui "
        "développe ta capacité aérobie (le cœur, les capillaires, la VO2max) sur le long terme."
    ),
    "Me préparer à une course (5km, 10km, semi, marathon)": (
        "Vu ta préparation à une course, augmente progressivement la durée de tes séances d'endurance "
        "fondamentale d'environ 10% par semaine, et garde le fractionné pour travailler ta vitesse de "
        "course sans t'épuiser."
    ),
    "Santé cardiovasculaire générale": (
        "Vu ton objectif de santé cardiovasculaire, la priorité est la régularité à intensité légère à "
        "modérée plutôt que la performance : mieux vaut 3 séances tranquilles par semaine qu'une seule "
        "séance épuisante."
    ),
}

NIVEAU_CARDIO_NOTES = {
    "Débutant": (
        "Niveau débutant en cardio : commence par le bas des fourchettes de durée et d'intensité "
        "indiquées ci-dessous, quitte à marcher un peu pendant les phases d'endurance fondamentale les "
        "premières semaines. La régularité compte plus que l'intensité au départ."
    ),
    "Intermédiaire": (
        "Niveau intermédiaire : vise le milieu des fourchettes indiquées, et augmente progressivement "
        "au fil des semaines si les séances te semblent confortables."
    ),
    "Confirmé": (
        "Niveau confirmé : tu peux viser le haut des fourchettes indiquées, voire les dépasser "
        "progressivement si tu récupères bien entre les séances."
    ),
}


def _priorites_par_objectif(objectif_cardio, objectif_principal, distance):
    """Ordre de priorité des séances INTENSES à placer dans la semaine, selon
    l'objectif. La première de la liste est posée en premier, la deuxième
    ensuite, etc. — donc à 1 seule séance dure par semaine, c'est la plus
    utile pour l'objectif qui est retenue.

    Retour Samy : « les séances doivent varier intelligemment selon
    l'objectif ». C'est ici que se joue cette intelligence : ce n'est plus une
    alternance mécanique entre deux étiquettes, mais un ordre de priorité
    argumenté par objectif.
    """
    # Préparation d'une course : l'allure spécifique de la distance visée passe
    # avant tout le reste — c'est le geste exact à automatiser. Vient ensuite le
    # seuil (tenir l'allure plus longtemps), puis la VMA (élever le plafond).
    if objectif_cardio == COURSE_OBJECTIF or distance:
        specifique = cardio_zones.ALLURE_SPECIFIQUE_PAR_DISTANCE.get(distance)
        if distance in ("5km", "10km"):
            # Courtes distances : le plafond aérobie (VMA) pèse lourd, le seuil
            # aussi. La sortie longue reste utile mais moins déterminante.
            ordre = ["Seuil", "VMA longue", "VMA courte", "Côtes", "Fartlek", "Tempo"]
        elif distance in ("semi", "marathon", "trail_ultra"):
            # Longues distances : tempo et seuil priment, la VMA n'intervient
            # qu'en complément une fois le socle installé.
            ordre = ["Tempo", "Seuil", "Côtes", "VMA longue", "Fartlek"]
        else:
            ordre = ["Seuil", "Tempo", "VMA longue", "Fartlek", "Côtes"]
        return ([specifique] if specifique else []) + ordre

    if objectif_cardio == "Perdre du poids / sécher":
        # La dépense se joue surtout sur le volume facile (déjà majoritaire dans
        # la répartition). Les séances dures servent à maintenir la masse
        # musculaire et l'appétence à l'effort, sans épuiser la récupération :
        # on privilégie des formats courts et variés plutôt que du seuil long.
        return ["Fractionné", "VMA courte", "Côtes", "Fartlek", "Tempo", "Seuil"]

    if objectif_cardio == "Améliorer mon endurance générale":
        return ["Tempo", "Seuil", "Fartlek", "VMA longue", "Côtes"]

    if objectif_cardio == "Santé cardiovasculaire générale":
        # Public le plus fragile : on reste sur des formats doux et ludiques,
        # jamais de VMA ni de sprints.
        return ["Fartlek", "Tempo"]

    # Pas d'objectif cardio renseigné (ex : formule Musculation avec un peu de
    # cardio en complément) : on retombe sur l'objectif musculation général.
    if objectif_principal == "Prise de muscle":
        # Interférence cardio/musculation : on limite volontairement l'intensité
        # pour ne pas concurrencer la récupération des séances de musculation.
        return ["Fartlek"]
    if objectif_principal == "Performance / explosivité":
        return ["Sprints / explosivité", "VMA courte", "Côtes", "VMA longue"]
    if objectif_principal in ("Perte de gras", "Recomposition (sec + muscle)"):
        return ["Fractionné", "VMA courte", "Fartlek", "Tempo"]
    return ["Fartlek", "Tempo", "Fractionné", "VMA longue"]


def _nb_seances_intenses(nb_sessions, niveau_cardio, objectif_cardio):
    """Nombre de séances dures dans la semaine.

    Principe de la répartition polarisée (le plus constant de la littérature
    endurance, et cohérent avec les zones du document « Les bases du cardio ») :
    l'essentiel du volume se fait facile (Z1-Z2), et seule une minorité
    assumée se fait dur (Z3-Z5). Empiler les séances intenses ne fait pas
    progresser plus vite, ça dégrade la récupération.

    On plafonne donc à environ un tiers de séances dures, avec un maximum
    absolu de 3 par semaine, et on tient compte du niveau : un débutant
    encaisse une seule séance dure, un confirmé jusqu'à trois.
    """
    if nb_sessions <= 0:
        return 0
    if objectif_cardio == "Santé cardiovasculaire générale":
        # Public santé : au maximum une séance un peu soutenue, et seulement
        # à partir de 3 séances hebdomadaires.
        return 1 if nb_sessions >= 3 else 0

    plafond_niveau = {"Débutant": 1, "Intermédiaire": 2, "Confirmé": 3}.get(niveau_cardio, 2)

    if nb_sessions == 1:
        # Séance unique : elle doit d'abord construire le socle aérobie.
        # Exception faite ci-dessous pour les objectifs où la seule séance de la
        # semaine n'aurait aucun sens en facile (perte de poids, explosivité).
        base = 0
    elif nb_sessions == 2:
        base = 1
    else:
        base = max(1, round(nb_sessions / 3))

    return max(0, min(base, plafond_niveau, 3))


def _session_mix(objectif_cardio, objectif_principal, nb_sessions,
                 niveau_cardio="Intermédiaire", distance="", signature=""):
    """Retourne la liste ordonnée des types de séance de la semaine.

    Réécriture complète (retour Samy : « sur 5 séances proposées, il y en a 4
    en endurance fondamentale, ce n'est absolument pas assez varié »).

    Diagnostic de l'ancienne version : elle ne connaissait que 4 étiquettes de
    séance (Endurance fondamentale, Fractionné, Endurance légère, Sprints) et
    construisait le mix par simple remplissage — typiquement
    `["Endurance fondamentale"] * (n-1) + ["Fractionné"]`. D'où 4 endurances
    sur 5 séances, quel que soit le profil.

    Nouvelle logique, en trois temps :
      1. on calcule combien de séances doivent être dures (`_nb_seances_intenses`,
         répartition polarisée) ;
      2. on choisit LESQUELLES via l'ordre de priorité propre à l'objectif et à
         la distance visée (`_priorites_par_objectif`), sans jamais répéter un
         type tant qu'il reste des types non utilisés ;
      3. on remplit le reste en volume facile, en alternant endurance
         fondamentale, sortie longue et récupération active plutôt qu'en
         empilant trois fois la même séance.

    Enfin on entrelace dur/facile pour ne jamais enchaîner deux séances dures
    consécutives.
    """
    if nb_sessions <= 0:
        return []

    priorites = _priorites_par_objectif(objectif_cardio, objectif_principal, distance)
    nb_intenses = _nb_seances_intenses(nb_sessions, niveau_cardio, objectif_cardio)

    # Cas particulier : une seule séance dans la semaine et un objectif pour
    # lequel une séance facile isolée n'apporterait quasiment rien.
    if nb_sessions == 1 and objectif_cardio in ("Perdre du poids / sécher",) :
        nb_intenses = 1
    if nb_sessions == 1 and not objectif_cardio and objectif_principal == "Performance / explosivité":
        nb_intenses = 1

    intenses = []
    if priorites and nb_intenses:
        # La première priorité de la liste est TOUJOURS retenue : c'est la
        # séance la plus utile à l'objectif (l'allure spécifique quand une
        # distance est visée, par exemple). Les suivantes sont prises en
        # tournant dans le reste de la liste, à partir d'un décalage dérivé de
        # la signature du profil. Sans ce décalage, seuls les 2-3 premiers
        # types de chaque liste sortaient jamais : côtes, VMA longue et sprints
        # n'apparaissaient dans aucun programme, alors qu'ils y figurent bien.
        intenses.append(priorites[0])
        reste = priorites[1:]
        if reste:
            depart = _variante_jitter(signature, "mix-intenses") % len(reste)
            for i in range(nb_intenses - 1):
                intenses.append(reste[(depart + i) % len(reste)])
        else:
            intenses.extend([priorites[0]] * (nb_intenses - 1))

    nb_faciles = nb_sessions - len(intenses)

    # --- Volume facile : varié lui aussi ------------------------------------
    # Une sortie longue dès 3 séances par semaine (repère classique : elle
    # représente 20-30% du volume hebdomadaire), et de la récupération active
    # dès qu'il reste assez de séances faciles pour se le permettre. Sans ça,
    # tout le volume facile retombait sur "Endurance fondamentale" répétée
    # trois ou quatre fois — le reproche initial.
    faciles = []
    sortie_longue_placee = False
    recup_placee = False
    for i in range(nb_faciles):
        reste_apres = nb_faciles - i - 1
        if (not sortie_longue_placee and nb_sessions >= 3
                and _sortie_longue_pertinente(objectif_cardio, distance)):
            faciles.append("Sortie longue")
            sortie_longue_placee = True
        elif not recup_placee and nb_faciles >= 3 and reste_apres == 0:
            # Dernière séance facile de la semaine et il y en a au moins trois :
            # une récupération active vaut mieux qu'une troisième endurance.
            # Pertinent pour tous les publics, y compris santé : c'est la séance
            # la plus douce du catalogue (Zone 1).
            faciles.append("Récupération active")
            recup_placee = True
        else:
            faciles.append("Endurance fondamentale")

    # --- Entrelacement dur / facile -----------------------------------------
    # On alterne pour ne jamais enchaîner deux séances dures d'affilée, ce qui
    # laisse au moins une journée de récupération relative entre deux gros
    # efforts quand les séances sont réparties sur la semaine.
    mix = []
    while intenses or faciles:
        if faciles:
            mix.append(faciles.pop(0))
        if intenses:
            mix.append(intenses.pop(0))

    # Si la semaine ne contient QUE des séances dures (cas limite : 1 séance,
    # objectif perte de poids), on la laisse telle quelle.
    return mix[:nb_sessions]


def _sortie_longue_pertinente(objectif_cardio, distance):
    """La sortie longue n'a de sens que si l'on cherche à durer.

    Elle a sa place dès 3 séances par semaine quel que soit l'objectif — y
    compris la perte de poids, où la séance longue en Zone 2 est justement le
    format qui maximise la part de graisses utilisées comme carburant (cf.
    tableau des zones du document), et y compris sur un objectif santé, où une
    sortie longue reste une sortie FACILE : elle allonge la durée, pas
    l'intensité. C'est le plafond de séances dures (`_nb_seances_intenses`) qui
    protège ce public, pas l'interdiction de varier le volume facile."""
    return True


def _estimate_niveau_from_1km(temps_1km, sexe):
    """Affine le niveau cardio déclaré à partir d'un temps réel sur 1 km, bien plus
    fiable qu'une simple auto-évaluation. Seuils légèrement différenciés
    homme/femme (écart physiologique moyen reconnu sur les performances de course)."""
    if not temps_1km:
        return None
    seuils = (
        {"Confirmé": 4.0, "Intermédiaire": 5.5} if sexe == "Homme"
        else {"Confirmé": 4.5, "Intermédiaire": 6.0}
    )
    if temps_1km <= seuils["Confirmé"]:
        return "Confirmé"
    if temps_1km <= seuils["Intermédiaire"]:
        return "Intermédiaire"
    return "Débutant"


# Pour la fonctionnalité "je n'aime pas cette séance" : à quel type plus doux
# retomber quand la raison est "trop difficile/intense". "Endurance légère" est le
# palier le plus bas, donc n'a nulle part où descendre plus.
# Allègement d'une séance jugée « trop difficile/intense » par l'utilisateur.
# Chaque type descend d'un cran vers une zone plus basse, jusqu'au plancher
# ("Récupération active"), plutôt que de retomber brutalement en endurance.
# Étendu aux 12 nouveaux types (retour Samy) : sans cela, une séance de Seuil
# ou de VMA signalée comme trop dure serait restée identique d'une semaine sur
# l'autre, faute d'entrée dans cette table.
TYPE_DOWNGRADE = {
    # Zone 5 -> Zone 4
    "Sprints / explosivité": "Côtes",
    "VMA courte": "VMA longue",
    "VMA longue": "Seuil",
    # Zone 4 -> Zone 3
    "Côtes": "Tempo",
    "Seuil": "Tempo",
    "Fractionné": "Fartlek",
    "Allure spécifique 5 km": "Allure spécifique 10 km",
    "Allure spécifique 10 km": "Tempo",
    # Zone 3 -> Zone 2
    "Tempo": "Endurance fondamentale",
    "Fartlek": "Endurance fondamentale",
    "Allure semi-marathon": "Endurance fondamentale",
    "Allure marathon": "Endurance fondamentale",
    # Zone 2 -> Zone 1
    "Sortie longue": "Endurance fondamentale",
    "Endurance fondamentale": "Endurance légère",
    "Endurance légère": "Récupération active",
    # Plancher : on ne descend pas plus bas.
    "Récupération active": "Récupération active",
}

RAISON_TROP_DUR = "Trop difficile / intense"
RAISON_SPORT = "Je n'aime pas ce sport"


def build_cardio_program(data):
    """
    data attendu :
      pratique_cardio ("Oui"/"Non"), cardio_types (list[str]), cardio_sessions (int),
      objectif_principal (str), objectif_cardio (str, optionnel), niveau_cardio (str, optionnel),
      temps_1km (float minutes, optionnel), sexe (str, optionnel),
      autre_sport ("Oui"/"Non"), autre_sport_type (str), autre_sport_sessions (int),
      blessures (list[str], optionnel), cardio_rejets (list[dict], optionnel) :
      [{ "seance_nom": "Séance cardio 2", "raison": "Trop difficile / intense" |
         "Je n'aime pas ce sport" | "Autre" }] — retours sur un programme précédent.
    """
    if data.get("pratique_cardio") != "Oui" or int(data.get("cardio_sessions", 0)) <= 0:
        return None

    cardio_types_raw = data.get("cardio_types") or ([data["cardio_type"]] if data.get("cardio_type") else [])
    cardio_types = []
    for t in cardio_types_raw:
        # "Circuit training (cardio en salle)" (libellé complet du
        # questionnaire, static/script.js) -> "Circuit training" (clé interne
        # courte, cohérente avec "Course"/"Vélo"/"Natation" ci-dessous et avec
        # les clés de PROTOCOLS ci-dessus).
        if t == "Circuit training (cardio en salle)":
            t = "Circuit training"
        elif t not in ("Course", "Vélo", "Natation", "Circuit training"):
            t = "Autre"
        if t not in cardio_types:
            cardio_types.append(t)
    if not cardio_types:
        cardio_types = ["Autre"]

    nb_sessions = int(data.get("cardio_sessions", 1))
    objectif = data.get("objectif_principal", "Condition physique générale")
    objectif_cardio = data.get("objectif_cardio") or ""
    niveau_cardio = data.get("niveau_cardio") or "Intermédiaire"
    blessures = data.get("blessures") or []

    niveau_calcule = None
    if "Course" in cardio_types and data.get("temps_1km"):
        niveau_calcule = _estimate_niveau_from_1km(data["temps_1km"], data.get("sexe"))
        if niveau_calcule:
            niveau_cardio = niveau_calcule

    # Distance visée en course ("5km" | "10km" | "semi" | "marathon" |
    # "trail_ultra" | ""), question ajoutée sous "Allure cible visée" (retour
    # Samy). Elle ne s'applique qu'à la course à pied : sur un profil qui ne
    # court pas, on l'ignore pour ne pas placer d'allure spécifique absurde
    # (une "allure marathon" en natation n'a aucun sens).
    distance = data.get("distance_objectif_course", "") or ""
    if "Course" not in cardio_types:
        distance = ""

    mix = _session_mix(objectif_cardio, objectif, nb_sessions,
                       niveau_cardio=niveau_cardio, distance=distance,
                       signature=data.get("signature", ""))

    warnings = []

    # ---- Retours "je n'aime pas cette séance" sur un programme précédent ----
    cardio_rejets = data.get("cardio_rejets") or []
    rejets_par_seance = {}
    for item in cardio_rejets:
        nom = item.get("seance_nom") if isinstance(item, dict) else None
        if nom:
            rejets_par_seance[nom] = item.get("raison", "")

    if rejets_par_seance:
        # "Je n'aime pas ce sport" sur une des disciplines choisies : on la retire
        # de la rotation (si ce n'est pas la seule), et les séances sont
        # réattribuées entre les disciplines restantes.
        disciplines_a_retirer = set()
        for i, type_seance in enumerate(mix):
            seance_nom = f"Séance cardio {i + 1}"
            if rejets_par_seance.get(seance_nom) == RAISON_SPORT:
                discipline_visee = cardio_types[i % len(cardio_types)]
                disciplines_a_retirer.add(discipline_visee)
        if disciplines_a_retirer:
            restantes = [t for t in cardio_types if t not in disciplines_a_retirer]
            if restantes:
                warnings.append(
                    f"Suite à ton retour, {', '.join(sorted(disciplines_a_retirer))} a/ont été "
                    f"retiré(s) de la rotation de tes séances de cardio."
                )
                cardio_types = restantes
            else:
                warnings.append(
                    "Tu as indiqué ne pas aimer ta seule discipline de cardio choisie : impossible "
                    "de la retirer sans te laisser sans séance. Réponds à nouveau au questionnaire "
                    "en choisissant un autre type de cardio pour en changer."
                )

    seances = []
    for i, type_seance in enumerate(mix):
        seance_nom = f"Séance cardio {i + 1}"
        raison = rejets_par_seance.get(seance_nom, "")
        discipline = cardio_types[i % len(cardio_types)]

        if raison == RAISON_TROP_DUR:
            type_allege = TYPE_DOWNGRADE.get(type_seance, type_seance)
            if type_allege != type_seance:
                warnings.append(
                    f"{seance_nom} allégée ({type_seance} → {type_allege}) suite à ton retour "
                    f"« trop difficile/intense »."
                )
                type_seance = type_allege
            else:
                warnings.append(
                    f"{seance_nom} est déjà à l'intensité la plus douce proposée : si elle reste "
                    f"trop difficile, envisage de réduire ta fréquence de cardio plutôt que "
                    f"l'intensité de cette séance."
                )
        elif raison == "Autre":
            warnings.append(
                f"Retour noté sur {seance_nom} : n'hésite pas à en discuter plus précisément pour "
                f"un ajustement sur mesure."
            )

        protocole = _choisir_protocole(
            type_seance, discipline, niveau_cardio,
            data.get("signature", ""), f"{seance_nom}::{discipline}",
        )
        seances.append({
            "nom": seance_nom,
            "type": type_seance,
            "discipline": discipline,
            "protocole": protocole,
            # Champs ADDITIFS (retour Samy, document « Les bases du cardio ») :
            # chaque séance affiche désormais sa zone d'intensité et l'effet
            # physiologique recherché, pour qu'on comprenne POURQUOI elle est là
            # et pas seulement quoi faire. Les consommateurs existants du dict
            # (PDF, page /my-program) ignorent simplement ces clés s'ils ne les
            # utilisent pas encore.
            "zone": cardio_zones.libelle_zone(type_seance),
            "description": cardio_zones.description_de(type_seance),
            "intensite": cardio_zones.intensite_de(type_seance),
        })

    if data.get("autre_sport") == "Oui" and int(data.get("autre_sport_sessions", 0)) >= 2:
        warnings.append(
            f"Tu pratiques déjà {data.get('autre_sport_type', 'un autre sport')} "
            f"{data.get('autre_sport_sessions')}x/semaine, ce qui sollicite déjà ton système "
            f"cardiovasculaire : si tu sens une fatigue excessive, tu peux réduire le nombre de "
            f"séances de cardio dédiées ci-dessous plutôt que d'ajouter du volume en plus."
        )

    if "Course" in cardio_types and ("Genoux" in blessures or "Chevilles / talons" in blessures):
        warnings.append(
            "Tu as signalé des douleurs aux genoux ou aux chevilles/talons : la course reste "
            "possible en respectant tes sensations, mais le vélo ou la natation sont des "
            "alternatives à impact réduit si la douleur persiste ou s'aggrave."
        )

    if niveau_calcule:
        warnings.append(
            f"Ton niveau cardio a été affiné à « {niveau_calcule} » à partir de ton temps "
            f"déclaré sur 1 km (plus fiable qu'une simple auto-évaluation)."
        )

    return {
        "cardio_type": ", ".join(cardio_types),
        "cardio_types": cardio_types,
        "nb_sessions": nb_sessions,
        "seances": seances,
        "warnings": warnings,
        "objectif_cardio": objectif_cardio,
        "objectif_cardio_note": OBJECTIF_CARDIO_NOTES.get(objectif_cardio),
        "niveau_cardio": niveau_cardio,
        "niveau_cardio_note": NIVEAU_CARDIO_NOTES.get(niveau_cardio),
        # Prompt hors 24 phases (retour Samy : "questionnaire adapté par
        # discipline course/natation/vélo/circuit training") : une phrase
        # personnalisée par discipline choisie, résumant l'objectif propre à
        # cette discipline (délai, allure, records déclarés) -- additif,
        # n'affecte ni le mix de séances ni les protocoles ci-dessus (repris
        # tel quel de `_session_mix`/`PROTOCOLS`).
        "notes_par_discipline": _notes_par_discipline(data, cardio_types),
    }


DELAI_LABELS = {
    "Pas de délai précis": "sans délai précis",
    "1 mois": "d'ici 1 mois",
    "2 à 3 mois": "d'ici 2 à 3 mois",
    "6 mois": "d'ici 6 mois",
    "1 an ou plus": "d'ici 1 an ou plus",
}


def _format_record_minutes(valeur_minutes):
    """Convertit un temps en minutes (float, ex: 25.5) en texte lisible
    "25 min 30 s" (ou "25 min" si rond). Utilisé pour afficher les records
    déclarés au questionnaire (5/10/20/40km course, distances natation/vélo)."""
    minutes = int(valeur_minutes)
    secondes = round((valeur_minutes - minutes) * 60)
    if secondes >= 60:
        minutes += 1
        secondes = 0
    return f"{minutes} min {secondes} s" if secondes else f"{minutes} min"


def _phrase_records(records, labels_distances):
    """records : dict {clé_distance: minutes_ou_None}. Ne mentionne QUE les
    distances pour lesquelles un record a été déclaré (retour Samy : "laisse
    une possibilité aucun record" -- un champ vide/absent n'est jamais
    mentionné, jamais affiché comme "0" ou "aucun record" intrusif)."""
    parties = []
    for cle, valeur in records.items():
        if valeur is not None and valeur > 0:
            parties.append(f"{labels_distances.get(cle, cle)} en {_format_record_minutes(valeur)}")
    if not parties:
        return ""
    return " Record(s) déclaré(s) : " + ", ".join(parties) + "."


def _notes_par_discipline(data, cardio_types):
    """Construit une phrase personnalisée par discipline PRÉSENTE dans
    `cardio_types`, à partir des questions spécifiques du questionnaire
    (objectif/délai/allure/records par discipline, cf. static/script.js) --
    absente/vide pour une discipline sans objectif renseigné (rétrocompatible
    avec les anciens questionnaires qui n'avaient pas ces champs)."""
    notes = {}

    if "Course" in cardio_types and data.get("objectif_course"):
        delai = DELAI_LABELS.get(data.get("delai_objectif_course"), "")
        phrase = f"Course à pied — objectif : {data['objectif_course']}"
        if delai:
            phrase += f", {delai}"
        phrase += "."
        if data.get("allure_cible_course"):
            phrase += f" Allure/précision visée : {data['allure_cible_course']}."
        phrase += _phrase_records(
            data.get("records_course") or {},
            {"5km": "5 km", "10km": "10 km", "20km": "20 km", "40km": "40 km (marathon)"},
        )
        notes["Course"] = phrase

    if "Natation" in cardio_types and data.get("objectif_natation"):
        delai = DELAI_LABELS.get(data.get("delai_objectif_natation"), "")
        phrase = f"Natation — objectif : {data['objectif_natation']}"
        if delai:
            phrase += f", {delai}"
        phrase += "."
        phrase += _phrase_records(
            data.get("records_natation") or {}, {"500m": "500 m", "1km": "1 km"},
        )
        notes["Natation"] = phrase

    if "Vélo" in cardio_types and data.get("objectif_velo"):
        delai = DELAI_LABELS.get(data.get("delai_objectif_velo"), "")
        phrase = f"Vélo — objectif : {data['objectif_velo']}"
        if delai:
            phrase += f", {delai}"
        phrase += "."
        phrase += _phrase_records(
            data.get("records_velo") or {}, {"20km": "20 km", "40km": "40 km"},
        )
        notes["Vélo"] = phrase

    if "Circuit training" in cardio_types and data.get("objectif_circuit"):
        phrase = f"Circuit training (cardio en salle) — objectif : {data['objectif_circuit']}."
        machines = data.get("type_circuit_prefere") or []
        if machines:
            phrase += f" Machines/formats préférés : {', '.join(machines)}."
        notes["Circuit training"] = phrase

    return notes
