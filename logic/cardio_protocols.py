# -*- coding: utf-8 -*-
"""
Protocoles concrets pour les types de séance ajoutés au moteur cardio
(retour Samy : « je t'ai fourni un document sur le cardio, base-toi dessus
afin d'intégrer beaucoup plus de variété »).

Les 4 types historiques (Endurance fondamentale, Fractionné, Sprints /
explosivité, Endurance légère) restent définis dans `cardio_builder.py`
(PROTOCOLS_VARIANTS) et ne sont pas modifiés ici : ce module ne fait
qu'AJOUTER les 12 nouveaux types, pour ne pas remettre en cause du contenu
déjà validé.

Chaque entrée est une fonction `niveau -> [variantes]`, même signature que
l'existant, de façon à ce que `_choisir_protocole` fonctionne à l'identique.
Plusieurs variantes par combinaison : deux profils différents (ou deux séances
de la même semaine) n'obtiennent pas le même texte.

Chaque protocole précise la zone d'intensité en % de FCmax, reprise du tableau
du document « Les bases du cardio » :
  Z1 50-60% · Z2 60-70% · Z3 70-80% · Z4 80-90% · Z5 90-100%
"""

# --- Récupération active — Zone 1 (50-60% FCmax) -------------------------------
_RECUP = {
    "Course": lambda n: [
        "20 à 30 min de footing très lent (50-60% FCmax, Zone 1) : tu dois pouvoir "
        "parler en phrases complètes sans essoufflement. Le but est d'activer la "
        "circulation pour évacuer la fatigue, surtout pas de progresser.",
        "25 à 35 min en alternant 5 min de trot très lent et 2 min de marche active. "
        "Format idéal au lendemain d'une séance dure ou d'une sortie longue.",
    ],
    "Vélo": lambda n: [
        "30 à 40 min sur le plat, petit braquet, cadence élevée (90-100 tr/min) et "
        "résistance minimale (50-60% FCmax, Zone 1). Les jambes tournent, elles ne poussent pas.",
        "30 min de home-trainer ou de vélo tranquille en Zone 1, sans jamais mettre "
        "de force dans les pédales : la séance doit être ennuyeuse, c'est le signe qu'elle est bien faite.",
    ],
    "Natation": lambda n: [
        "800 à 1200 m très souples, en alternant les nages et en intégrant des "
        "longueurs avec planche. Priorité à la sensation de glisse, jamais à la vitesse.",
        "20 à 30 min de nage lente et continue (50-60% FCmax), en te concentrant "
        "uniquement sur l'amplitude du mouvement et la respiration.",
    ],
    "Circuit training": lambda n: [
        "20 à 25 min de machine cardio au choix (vélo, elliptique, rameur) à "
        "intensité très basse, suivies de 10 min de mobilité articulaire (hanches, "
        "chevilles, épaules).",
        "25 min en Zone 1 sur elliptique ou vélo, résistance minimale, en profitant "
        "de la séance pour étirer et relâcher les zones sollicitées la veille.",
    ],
    "Autre": lambda n: [
        "20 à 30 min d'activité très légère (marche rapide, vélo doux, natation "
        "souple) en Zone 1, uniquement pour favoriser la récupération.",
    ],
}

# --- Sortie longue — Zone 2 (60-70% FCmax) ------------------------------------
_LONGUE = {
    "Course": lambda n: [
        {"Débutant": "45 à 60 min à allure d'endurance (60-70% FCmax), en t'autorisant "
                     "des portions de marche si besoin. Augmente d'environ 10% par semaine, pas plus.",
         "Intermédiaire": "1h15 à 1h30 à allure d'endurance (60-70% FCmax), sur un "
                          "parcours si possible vallonné. Augmente d'environ 10% par semaine.",
         "Confirmé": "1h30 à 2h à allure d'endurance (60-70% FCmax). Tu peux terminer "
                     "les 15 dernières minutes légèrement plus vite, sans jamais basculer en Zone 4."}.get(n,
            "1h à 1h30 à allure d'endurance (60-70% FCmax), en augmentant d'environ 10% par semaine."),
        "Sortie longue progressive : 2 x 6 km, le premier bloc en endurance franche "
        "(60-65% FCmax) et le second légèrement plus rapide (68-72% FCmax), séparés "
        "par 5 min de trot très lent. Apprend à finir plus vite qu'on ne commence.",
        "Sortie longue en 2 x 8 km, premier bloc en endurance pure, second bloc avec "
        "des relances de 1 min toutes les 8 min. Réservé aux semaines où tu te sens frais.",
    ],
    "Vélo": lambda n: [
        "1h30 à 2h30 à allure d'endurance (65-75% FCmax), cadence fluide (80-90 tr/min), "
        "sur terrain roulant. Mange et bois régulièrement dès la première heure.",
        "2h en endurance avec 3 x 10 min en légère résistance (bosses ou braquet plus "
        "gros à 70 tr/min) pour travailler la force spécifique sans monter en intensité.",
    ],
    "Natation": lambda n: [
        "1500 à 2500 m en continu ou en séries longues (ex : 5 x 400 m / 30 sec de "
        "repos) à allure régulière et confortable.",
        "45 à 60 min de nage continue à allure d'endurance, en changeant de nage "
        "toutes les 10 longueurs pour préserver les épaules.",
    ],
    "Circuit training": lambda n: [
        "50 à 70 min de machines cardio enchaînées (20 min tapis, 20 min rameur, "
        "20 min elliptique) à intensité modérée et constante (60-70% FCmax).",
        "60 min en rotation libre entre trois machines, en restant en Zone 2 sur "
        "l'ensemble de la séance, sans jamais chercher à accélérer.",
    ],
    "Autre": lambda n: [
        "60 à 90 min d'activité continue à intensité modérée (60-70% FCmax), en "
        "augmentant la durée d'environ 10% par semaine.",
    ],
}

# --- Fartlek — Zones 2 à 4, jeu d'allures libre --------------------------------
_FARTLEK = {
    "Course": lambda n: [
        "10 min d'échauffement, puis 30 min de jeu d'allures libre : tu accélères "
        "quand tu veux (entre 30 sec et 3 min) et tu récupères en trot jusqu'à te "
        "sentir prêt. Sans montre, uniquement aux sensations. Puis 10 min de retour au calme.",
        "10 min d'échauffement, puis 8 à 10 x (1 min vive / 1 min trot lent), puis "
        "8 à 10 x (30 sec vive / 30 sec trot). Retour au calme 10 min.",
        "Fartlek du terrain : 40 min en accélérant dans chaque montée rencontrée et "
        "en récupérant dans les descentes et les plats. Le parcours dicte la séance.",
    ],
    "Vélo": lambda n: [
        "15 min d'échauffement, puis 30 min de jeu d'allures : accélérations libres "
        "de 30 sec à 2 min selon le terrain et l'envie, récupération jusqu'au retour "
        "d'une respiration confortable. 10 min de retour au calme.",
        "Fartlek vallonné : 45 min en attaquant chaque bosse en danseuse et en "
        "récupérant sur le plat, sans structure imposée.",
    ],
    "Natation": lambda n: [
        "200 m d'échauffement, puis 20 x 50 m en alternant une longueur vive et une "
        "longueur souple sans repos, puis 200 m de retour au calme.",
        "300 m d'échauffement, puis 6 x (100 m dont les 25 premiers mètres vifs), "
        "20 sec de repos, puis 200 m de retour au calme.",
    ],
    "Circuit training": lambda n: [
        "10 min d'échauffement, puis 30 min sur une machine cardio en alternant "
        "librement 1 à 3 min à intensité soutenue et 1 à 2 min de récupération, au feeling.",
        "Fartlek machines : 5 min par machine en alternant une machine à intensité "
        "vive et une machine en récupération, sur 6 blocs.",
    ],
    "Autre": lambda n: [
        "10 min d'échauffement, puis 30 min en alternant librement des phases vives "
        "(30 sec à 3 min) et des phases de récupération, aux sensations. 10 min de retour au calme.",
    ],
}

# --- Tempo — Zone 3 (70-80% FCmax) --------------------------------------------
_TEMPO = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 20 à 30 min en continu à allure tempo "
        "(70-80% FCmax) : soutenu mais contrôlé, tu peux dire quelques mots mais pas "
        "tenir une conversation. Puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 2 x 15 min à allure tempo / 3 min de trot lent "
        "entre les blocs, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 3 x 10 min à allure tempo / 2 min de récupération "
        "trottinée. Format un peu plus accessible que le bloc continu, pour une charge équivalente.",
    ],
    "Vélo": lambda n: [
        "15 min d'échauffement, puis 2 x 20 min en « sweet spot » (75-85% FCmax, "
        "cadence 85-95 tr/min) / 5 min de récupération. Puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 40 min en continu à intensité tempo (70-80% "
        "FCmax), position aérodynamique tenue. 10 min de retour au calme.",
    ],
    "Natation": lambda n: [
        "300 m d'échauffement, puis 6 x 200 m à allure soutenue mais régulière / "
        "30 sec de repos, puis 200 m de retour au calme.",
        "300 m d'échauffement, puis 3 x 400 m à allure tempo / 45 sec de repos, "
        "puis 200 m de retour au calme.",
    ],
    "Circuit training": lambda n: [
        "10 min d'échauffement, puis 25 à 30 min sur une seule machine à intensité "
        "tempo constante (70-80% FCmax), sans jamais redescendre. Puis 10 min de retour au calme.",
        "10 min d'échauffement, puis 3 x 10 min sur trois machines différentes à "
        "intensité tempo / 2 min de transition, puis retour au calme.",
    ],
    "Autre": lambda n: [
        "15 min d'échauffement, puis 20 à 30 min à intensité soutenue mais contrôlée "
        "(70-80% FCmax), puis 10 min de retour au calme.",
    ],
}

# --- Seuil — Zone 4 (80-90% FCmax) --------------------------------------------
_SEUIL = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 2 x 15 min à allure seuil (85-90% FCmax, allure "
        "tenable environ 1h en course) / 3 min de trot lent, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 4 x 8 min à allure seuil / 2 min de récupération "
        "trottinée, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 5 x 1000 m à allure seuil / 90 sec de "
        "récupération, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 3 x (1000 m, 1200 m, 2000 m — distances "
        "croissantes) à allure seuil / 2 à 3 min de récupération, puis retour au calme.",
    ],
    "Vélo": lambda n: [
        "15 min d'échauffement, puis 3 x 10 min au seuil (85-90% FCmax) / 5 min de "
        "récupération active, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 2 x 20 min au seuil / 8 min de récupération, "
        "puis 10 min de retour au calme.",
    ],
    "Natation": lambda n: [
        "300 m d'échauffement, puis 10 x 100 m à allure soutenue / 20 sec de repos, "
        "puis 200 m de retour au calme.",
        "300 m d'échauffement, puis 5 x 200 m à allure seuil / 30 sec de repos, "
        "puis 200 m de retour au calme.",
    ],
    "Circuit training": lambda n: [
        "10 min d'échauffement, puis 5 x 4 min à intensité seuil (85-90% FCmax) sur "
        "machine cardio / 2 min de récupération, puis 10 min de retour au calme.",
        "10 min d'échauffement, puis 4 x 6 min au seuil en changeant de machine à "
        "chaque bloc / 2 min de transition, puis retour au calme.",
    ],
    "Autre": lambda n: [
        "15 min d'échauffement, puis 3 x 8 à 10 min à intensité seuil (85-90% FCmax) "
        "/ 2 à 3 min de récupération, puis 10 min de retour au calme.",
    ],
}

# --- VMA longue — Zone 5, intervalles de 2 à 5 min -----------------------------
_VMA_LONGUE = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 5 x 3 min à intensité très élevée (90-95% FCmax, "
        "proche de ton maximum tenable 6 min) / 3 min de trot lent, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 6 x 800 m à allure vive / 2 min 30 de "
        "récupération trottinée, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 4 x 4 min à 90-95% FCmax / 3 min de récupération, "
        "puis 10 min de retour au calme. Le format historique de développement de la VO₂max.",
        "15 min d'échauffement, puis 3 x 1000 m puis 2 x 1200 m à allure vive / "
        "2 à 3 min de récupération, puis retour au calme.",
    ],
    "Vélo": lambda n: [
        "20 min d'échauffement, puis 5 x 3 min à intensité VO₂max (90-95% FCmax, "
        "cadence 95-105 tr/min) / 3 min de récupération très facile, puis 10 min de retour au calme.",
        "20 min d'échauffement, puis 4 x 5 min à 90-95% FCmax / 5 min de récupération, "
        "puis retour au calme.",
    ],
    "Natation": lambda n: [
        "400 m d'échauffement, puis 8 x 100 m à allure très soutenue / 30 à 40 sec "
        "de repos, puis 200 m de retour au calme.",
        "400 m d'échauffement, puis 6 x 150 m à allure très soutenue / 45 sec de "
        "repos, puis 200 m de retour au calme.",
    ],
    "Circuit training": lambda n: [
        "10 min d'échauffement, puis 6 x 3 min à intensité très élevée sur machine "
        "cardio / 2 min de récupération, puis 10 min de retour au calme.",
        "10 min d'échauffement, puis 5 x 4 min à 90-95% FCmax en alternant rameur et "
        "vélo / 3 min de récupération, puis retour au calme.",
    ],
    "Autre": lambda n: [
        "15 min d'échauffement, puis 5 x 3 min à intensité très élevée (90-95% FCmax) "
        "/ 3 min de récupération, puis 10 min de retour au calme.",
    ],
}

# --- VMA courte — Zone 5, intervalles de 30 sec à 1 min 30 ---------------------
_VMA_COURTE = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 2 séries de 8 x (30 sec vive / 30 sec de trot "
        "lent), 3 min de récupération entre les séries, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 12 x 200 m à allure très vive / 45 sec de "
        "récupération, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 10 x 400 m à allure vive (légèrement plus rapide "
        "que ton allure 5 km) / 90 sec de récupération trottinée, puis retour au calme.",
        "15 min d'échauffement, puis 3 séries de 6 x (15 sec très vive / 15 sec de "
        "trot), 3 min entre les séries. Format court, très efficace et peu traumatisant.",
    ],
    "Vélo": lambda n: [
        "20 min d'échauffement, puis 2 séries de 10 x (30 sec fort / 30 sec facile), "
        "5 min entre les séries, puis 10 min de retour au calme.",
        "20 min d'échauffement, puis 12 x 1 min à intensité très élevée / 1 min de "
        "récupération, puis retour au calme.",
    ],
    "Natation": lambda n: [
        "300 m d'échauffement, puis 16 x 50 m à allure vive / 15 sec de repos, puis "
        "200 m de retour au calme.",
        "300 m d'échauffement, puis 2 séries de 8 x 25 m sprint / 20 sec de repos, "
        "2 min entre les séries, puis 200 m de retour au calme.",
    ],
    "Circuit training": lambda n: [
        "10 min d'échauffement, puis 8 rounds de Tabata (20 sec maximal / 10 sec de "
        "repos) sur rameur ou vélo, 3 min de récupération, puis un second bloc "
        "identique. Retour au calme 10 min.",
        "10 min d'échauffement, puis 15 x (40 sec intense / 20 sec de repos) en "
        "alternant deux machines, puis 10 min de retour au calme.",
    ],
    "Autre": lambda n: [
        "15 min d'échauffement, puis 2 séries de 8 x (30 sec intense / 30 sec de "
        "récupération), 3 min entre les séries, puis 10 min de retour au calme.",
    ],
}

# --- Côtes — Zones 4-5, force spécifique --------------------------------------
_COTES = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 8 à 10 x 30 sec en côte à intensité élevée "
        "(pente 5-8%), retour en trot lent jusqu'au pied de la côte, puis 10 min de "
        "retour au calme. Impact articulaire réduit par rapport au fractionné à plat.",
        "15 min d'échauffement, puis 6 x 1 min en côte à allure soutenue / descente "
        "en marchant ou en trottinant, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 3 séries de 5 x 15 sec en côte très vive "
        "(travail de puissance), 3 min entre les séries, puis retour au calme.",
        "15 min d'échauffement, puis 4 x 3 min en côte régulière à allure seuil "
        "(pente douce 3-5%), descente en récupération, puis retour au calme.",
    ],
    "Vélo": lambda n: [
        "20 min d'échauffement, puis 6 x 3 min en montée sur gros braquet à cadence "
        "basse (55-65 tr/min) / descente en récupération, puis 10 min de retour au calme.",
        "20 min d'échauffement, puis 5 x 5 min en montée à intensité seuil, en "
        "alternant assis et en danseuse toutes les minutes, puis retour au calme.",
    ],
    "Natation": lambda n: [
        "Équivalent « côtes » en natation (travail de force spécifique) : 300 m "
        "d'échauffement, puis 10 x 50 m avec plaquettes à allure soutenue / 30 sec "
        "de repos, puis 200 m de retour au calme.",
        "300 m d'échauffement, puis 8 x 50 m en pull-buoy et plaquettes à intensité "
        "élevée / 30 sec de repos, puis 200 m souples.",
    ],
    "Circuit training": lambda n: [
        "10 min d'échauffement, puis 8 x 1 min sur tapis en pente forte (8-12%) à "
        "intensité élevée / 1 min 30 de récupération à plat, puis 10 min de retour au calme.",
        "10 min d'échauffement, puis 6 x 2 min sur tapis incliné à 10% ou sur vélo à "
        "forte résistance / 2 min de récupération, puis retour au calme.",
    ],
    "Autre": lambda n: [
        "15 min d'échauffement, puis 8 x 30 sec à 1 min en montée (ou à forte "
        "résistance) à intensité élevée / récupération en descente, puis 10 min de retour au calme.",
    ],
}

# --- Allures spécifiques (course) ---------------------------------------------
# Sur les autres disciplines, on ramène à un équivalent d'intensité comparable
# plutôt que d'inventer une "allure marathon" en natation, qui n'aurait aucun sens.
_ALLURE_5K = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 5 x 1000 m à ton allure cible sur 5 km / 2 min "
        "de récupération trottinée, puis 10 min de retour au calme. L'objectif est "
        "d'ancrer le rythme, pas d'aller plus vite que l'allure visée.",
        "15 min d'échauffement, puis 3 x 1600 m à allure 5 km / 3 min de "
        "récupération, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 8 x 600 m à allure 5 km / 90 sec de "
        "récupération, puis retour au calme.",
    ],
    "Vélo": lambda n: _SEUIL["Vélo"](n),
    "Natation": lambda n: _SEUIL["Natation"](n),
    "Circuit training": lambda n: _SEUIL["Circuit training"](n),
    "Autre": lambda n: _SEUIL["Autre"](n),
}

_ALLURE_10K = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 4 x 2000 m à ton allure cible sur 10 km / 2 min "
        "30 de récupération, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 2 x 4 km à allure 10 km / 3 min de récupération, "
        "puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 6 x 1200 m à allure 10 km / 2 min de "
        "récupération, puis retour au calme.",
    ],
    "Vélo": lambda n: _SEUIL["Vélo"](n),
    "Natation": lambda n: _SEUIL["Natation"](n),
    "Circuit training": lambda n: _SEUIL["Circuit training"](n),
    "Autre": lambda n: _SEUIL["Autre"](n),
}

_ALLURE_SEMI = {
    "Course": lambda n: [
        "15 min d'échauffement, puis 2 x 5 km à ton allure cible sur semi-marathon / "
        "3 min de récupération trottinée, puis 10 min de retour au calme.",
        "15 min d'échauffement, puis 12 km en continu à allure semi, puis 10 min de "
        "retour au calme. Séance clé de la préparation : elle valide que l'allure est réaliste.",
        "15 min d'échauffement, puis 3 x 4 km à allure semi / 3 min de récupération, "
        "puis retour au calme.",
    ],
    "Vélo": lambda n: _TEMPO["Vélo"](n),
    "Natation": lambda n: _TEMPO["Natation"](n),
    "Circuit training": lambda n: _TEMPO["Circuit training"](n),
    "Autre": lambda n: _TEMPO["Autre"](n),
}

_ALLURE_MARATHON = {
    "Course": lambda n: [
        "Sortie longue avec allure spécifique : 1h à 1h15 en endurance, dont "
        "3 x 3 km à ton allure cible marathon insérés en cours de sortie, puis "
        "retour au calme. Habitue le corps à tenir l'allure sur fatigue.",
        "15 min d'échauffement, puis 2 x 8 km à allure marathon / 5 min de trot lent, "
        "puis 10 min de retour au calme.",
        "Sortie longue de 1h30 dont les 45 dernières minutes courues à allure "
        "marathon. La séance la plus proche des conditions réelles de course.",
    ],
    "Vélo": lambda n: _TEMPO["Vélo"](n),
    "Natation": lambda n: _TEMPO["Natation"](n),
    "Circuit training": lambda n: _TEMPO["Circuit training"](n),
    "Autre": lambda n: _TEMPO["Autre"](n),
}


# Table exposée à `cardio_builder.py`, fusionnée avec PROTOCOLS_VARIANTS.
PROTOCOLS_SUPPLEMENTAIRES = {
    "Récupération active": _RECUP,
    "Sortie longue": _LONGUE,
    "Fartlek": _FARTLEK,
    "Tempo": _TEMPO,
    "Seuil": _SEUIL,
    "VMA longue": _VMA_LONGUE,
    "VMA courte": _VMA_COURTE,
    "Côtes": _COTES,
    "Allure spécifique 5 km": _ALLURE_5K,
    "Allure spécifique 10 km": _ALLURE_10K,
    "Allure semi-marathon": _ALLURE_SEMI,
    "Allure marathon": _ALLURE_MARATHON,
}
