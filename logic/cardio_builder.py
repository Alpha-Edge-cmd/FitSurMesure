# -*- coding: utf-8 -*-
"""
Moteur de génération du programme cardio, séparé du programme de musculation.
Détermine un mix de types de séance (endurance fondamentale / fractionné /
sprints) selon l'objectif, puis un protocole concret selon le type de cardio
pratiqué (course, vélo, natation, autre).
"""

PROTOCOLS = {
    "Endurance fondamentale": {
        "Course": "30 à 45 min à allure conversationnelle (60-70% FCmax), en continu.",
        "Vélo": "40 à 50 min à intensité modérée (60-70% FCmax), cadence régulière.",
        "Natation": "30 à 40 min à allure régulière, technique fluide, sans forcer.",
        "Autre": "30 à 45 min d'activité continue à intensité modérée (60-70% FCmax).",
    },
    "Fractionné": {
        "Course": "10 min d'échauffement, puis 8 à 12 x 400m rapide (80-90% FCmax) / 90 sec "
                  "récupération trottinée, puis 10 min de retour au calme.",
        "Vélo": "10 min d'échauffement, puis 8 à 10 x 1 min effort intense (85-90% FCmax) / 2 min "
                "récupération légère, puis 10 min de retour au calme.",
        "Natation": "10 min d'échauffement, puis 8 x 50m rapide / 30 sec de repos, puis retour au calme.",
        "Autre": "10 min d'échauffement, puis 8 à 10 x 30-45 sec effort intense / 1-2 min "
                 "récupération, puis retour au calme.",
    },
    "Sprints / explosivité": {
        "Course": "10-15 min d'échauffement complet, puis 6 à 10 x 15-20 sec sprint maximal / "
                  "2-3 min récupération complète (marche), puis retour au calme.",
        "Vélo": "10-15 min d'échauffement, puis 6 à 8 x 15-20 sec sprint à fond / 3 min "
                "récupération, puis retour au calme.",
        "Natation": "10-15 min d'échauffement, puis 6 à 8 x 25m sprint maximal / 2 min "
                    "récupération complète.",
        "Autre": "10-15 min d'échauffement, puis 6 à 10 x 15-20 sec effort maximal / 2-3 min "
                 "récupération complète.",
    },
    "Endurance légère": {
        "Course": "20 à 25 min à intensité légère, juste pour la santé cardiovasculaire.",
        "Vélo": "20 à 25 min à intensité légère, cadence tranquille.",
        "Natation": "20 à 25 min à allure détente.",
        "Autre": "20 à 25 min d'activité à intensité légère.",
    },
}


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


def _session_mix(objectif_cardio, objectif_principal, nb_sessions):
    """Retourne une liste de types de séance, dans l'ordre, pour la semaine.
    Priorité à l'objectif cardio spécifique s'il est renseigné, sinon on retombe
    sur l'objectif musculation général (rétro-compatibilité)."""
    if nb_sessions <= 0:
        return []

    if objectif_cardio == "Perdre du poids / sécher":
        if nb_sessions == 1:
            return ["Fractionné"]
        mix = ["Fractionné"] + ["Endurance fondamentale"] * (nb_sessions - 1)
        return mix

    if objectif_cardio == "Améliorer mon endurance générale":
        if nb_sessions == 1:
            return ["Endurance fondamentale"]
        base = ["Endurance fondamentale", "Endurance fondamentale", "Fractionné"]
        return [base[i % 3] for i in range(nb_sessions)]

    if objectif_cardio == "Me préparer à une course (5km, 10km, semi, marathon)":
        if nb_sessions == 1:
            return ["Endurance fondamentale"]
        mix = ["Endurance fondamentale"] * (nb_sessions - 1) + ["Fractionné"]
        return mix

    if objectif_cardio == "Santé cardiovasculaire générale":
        return ["Endurance légère"] * nb_sessions

    # Pas d'objectif cardio spécifique renseigné : on retombe sur l'ancienne logique
    # basée sur l'objectif musculation général (ex: formule musculation + un peu de cardio).
    objectif = objectif_principal
    if objectif == "Prise de muscle":
        return ["Endurance légère"] * nb_sessions

    if objectif == "Perte de gras":
        if nb_sessions == 1:
            return ["Endurance fondamentale"]
        mix = ["Fractionné"] + ["Endurance fondamentale"] * (nb_sessions - 1)
        return mix

    if objectif == "Recomposition (sec + muscle)":
        if nb_sessions == 1:
            return ["Endurance fondamentale"]
        mix = ["Fractionné"] + ["Endurance fondamentale"] * (nb_sessions - 1)
        return mix

    if objectif == "Performance / explosivité":
        if nb_sessions == 1:
            return ["Fractionné"]
        mix = ["Sprints / explosivité", "Fractionné"] + ["Endurance fondamentale"] * max(0, nb_sessions - 2)
        return mix[:nb_sessions]

    # Condition physique générale : mix équilibré
    base = ["Endurance fondamentale", "Fractionné"]
    return [base[i % 2] for i in range(nb_sessions)]


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
TYPE_DOWNGRADE = {
    "Sprints / explosivité": "Fractionné",
    "Fractionné": "Endurance fondamentale",
    "Endurance fondamentale": "Endurance légère",
    "Endurance légère": "Endurance légère",
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
        t = t if t in ("Course", "Vélo", "Natation") else "Autre"
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

    mix = _session_mix(objectif_cardio, objectif, nb_sessions)

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

        protocole = PROTOCOLS[type_seance][discipline]
        seances.append({
            "nom": seance_nom,
            "type": type_seance,
            "discipline": discipline,
            "protocole": protocole,
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
    }
