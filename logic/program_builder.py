# -*- coding: utf-8 -*-
"""
Moteur de génération du programme d'entraînement : choix du split,
sélection des exercices selon équipement/contre-indications, gestion
du volume (nb d'exercices par muscle, séries) et de la durée de séance.
"""
import hashlib

from .exercises_db import EXERCISES, SPLITS, MUSCLE_LABELS, BLESSURE_TAGS, EXO_INCAPABLE_TAGS

DUREE_MINUTES = {
    "45 min": 45,
    "1h": 60,
    "1h - 1h30": 90,
    "1h30+": 105,
}

SET_TIME_SEC = 130  # temps moyen par série (exécution + repos)
WARMUP_MIN = 10

# Nombre total d'exercices minimum par séance selon la durée choisie (au-delà
# du volume "par muscle" habituel) : une séance de plus d'1h doit avoir de quoi
# remplir le temps, pas juste 5-6 exercices. Pas de plancher pour les séances
# courtes (45 min / 1h), où moins d'exercices avec plus de repos/séries est
# plus logique.
MIN_EXOS_PAR_SEANCE = {
    "1h - 1h30": 9,
    "1h30+": 10,
}
MAX_PAR_MUSCLE = 6  # on ne stack jamais plus de 6 exercices sur un seul muscle

# Certains schémas de mouvement ("pattern") sont bien assez différents pour la
# base de données (angle, appui...) mais restent "le même exercice" pour la
# plupart des gens (ex : développé couché plat/incliné/décliné = 3 variantes du
# développé couché). On les regroupe en "famille" pour garantir qu'une séance
# pioche d'abord dans des familles différentes (presse / écarté / dips / tirage...)
# avant de proposer 2 exercices de la même famille — un pattern non listé ici
# forme sa propre famille à lui seul.
FAMILY_MAP = {
    "developpe_plat": "presse_pecs",
    "developpe_incline": "presse_pecs",
    "developpe_decline": "presse_pecs",
    "fly": "ecarte_pecs",
    "fly_incline": "ecarte_pecs",
    "dips_pecs": "dips_pompes_pecs",
    "pompes": "dips_pompes_pecs",
    "developpe_militaire": "presse_epaules",
    "developpe_arnold": "presse_epaules",
    "squat": "squat_family",
    "front_squat": "squat_family",
}

# Nom d'exercice -> pattern (schéma de mouvement), utilisé pour la fonctionnalité
# "je n'aime pas cet exercice" : quand la raison invoquée est une douleur/gêne, on
# exclut tout le schéma de mouvement plutôt que ce seul exercice (une autre variante
# du même mouvement risque de poser le même problème).
NAME_TO_PATTERN = {}
for _muscle, _exos in EXERCISES.items():
    for _e in _exos:
        NAME_TO_PATTERN[_e["name"]] = _e["pattern"]

# Raisons proposées côté questionnaire de révision ("je n'aime pas mon programme").
RAISON_DOULEUR = "Douleur / gêne"


def _rejected_sets(exercices_rejetes):
    """Construit (excluded_names, excluded_patterns) à partir des retours de
    l'utilisateur sur son programme précédent. `exercices_rejetes` : liste de
    { "nom": <nom exact de l'exercice>, "raison": <str> }."""
    excluded_names = set()
    excluded_patterns = set()
    for item in exercices_rejetes or []:
        if isinstance(item, dict):
            nom = item.get("nom", "")
            raison = item.get("raison", "")
        else:
            nom, raison = str(item), ""
        if not nom:
            continue
        excluded_names.add(nom)
        if raison == RAISON_DOULEUR and nom in NAME_TO_PATTERN:
            excluded_patterns.add(NAME_TO_PATTERN[nom])
    return excluded_names, excluded_patterns


def _split_key_auto(frequence, objectif=None, niveau=None):
    if frequence <= 2:
        return "full_body"
    if frequence == 3:
        # À 3 séances/semaine, le Full Body reste la référence pour la plupart des
        # profils (chaque muscle travaillé 3x/semaine). Mais pour un pratiquant
        # intermédiaire/avancé cherchant du volume (prise de muscle/recomposition),
        # un Push/Pull/Legs propose plus d'exercices par muscle par séance : c'est
        # une alternative tout aussi valable que beaucoup préfèrent à ce niveau.
        if niveau in ("Intermédiaire", "Avancé") and objectif in (
            "Prise de muscle", "Recomposition (sec + muscle)"
        ):
            return "ppl"
        return "full_body"
    if frequence == 4:
        return "upper_lower"
    if frequence == 5:
        return "ppl"
    return "arnold"


def _avoid_tags(blessures, exos_incapables):
    tags = set()
    for b in blessures or []:
        if b in BLESSURE_TAGS:
            tags.add(BLESSURE_TAGS[b])
    for e in exos_incapables or []:
        if e in EXO_INCAPABLE_TAGS:
            tags.add(EXO_INCAPABLE_TAGS[e])
    return tags


ALL_EQUIP = {"barre", "haltere", "poids_du_corps", "elastique", "machine"}

# Profils "salle" : barre/haltères/machines réels sont disponibles, donc l'élastique
# (solution de dépannage sans matériel) ne doit jamais être privilégié par rapport à
# eux — seulement utilisé en dernier recours si aucun autre pattern ne convient.
GYM_EQUIPEMENTS = {"Salle complète", "Surtout machines guidées", "Surtout poids libres"}


def _equip_allowed(equipement):
    """
    Retourne (allowed_set, equip_priorite) où equip_priorite est un set d'équipements
    à privilégier dans le tri (ou None). Distingue bien la barre (nécessite un
    rack/banc, en pratique une salle ou un gros équipement maison) des haltères,
    du poids du corps et de l'élastique (réalisables avec peu de matériel à la
    maison), pour que "Matériel limité à domicile" ne renvoie plus d'exercices à
    la barre ou en machine.

    Pour les profils "salle" (GYM_EQUIPEMENTS), le poids du corps est exclu du
    programme principal : quand on a barre/haltères/machines à disposition, les
    tractions/dips/pompes ne sont plus mélangés aux exercices avec charge dans le
    tableau principal — ils sont proposés à part, dans une petite section
    "bonus poids du corps (facultatif)" (voir _select_bodyweight_bonus).
    """
    if equipement == "Salle complète":
        return set(ALL_EQUIP) - {"poids_du_corps"}, None
    if equipement == "Surtout machines guidées":
        return set(ALL_EQUIP) - {"poids_du_corps"}, {"machine"}
    if equipement == "Surtout poids libres":
        return set(ALL_EQUIP) - {"poids_du_corps"}, {"barre", "haltere"}
    if equipement == "Matériel limité à domicile":
        return {"haltere", "poids_du_corps", "elastique"}, {"poids_du_corps", "haltere"}
    return set(ALL_EQUIP), None


BONUS_POIDS_DU_CORPS_MAX = 3  # "petite partie" : on ne déborde pas sur une vraie séance


def _select_bodyweight_bonus(muscles, avoid_tags, signature, max_total=BONUS_POIDS_DU_CORPS_MAX):
    """Construit une petite liste FACULTATIVE d'exercices poids du corps en lien
    avec les muscles réellement travaillés dans la séance (uniquement pour les
    profils salle, où le poids du corps a été retiré du programme principal).
    Un seul exercice par pattern (variété), un seul par muscle pour rester une
    "petite partie" et pas une deuxième séance."""
    bonus = []
    used_patterns = set()
    for muscle in muscles:
        if len(bonus) >= max_total:
            break
        variants = [e for e in EXERCISES.get(muscle, []) if e["equip"] == "poids_du_corps"]
        candidates = [v for v in variants
                      if not (set(v["avoid"]) & avoid_tags) and v["pattern"] not in used_patterns]
        if not candidates:
            continue
        candidates.sort(key=lambda e: (e["priority"], _signature_jitter(signature, e["name"])))
        chosen = candidates[0]
        reps = "8-12" if chosen["force"] else "12-15"
        bonus.append({
            "nom": chosen["name"],
            "muscle": MUSCLE_LABELS.get(muscle, muscle),
            "series": 3,
            "reps": reps,
        })
        used_patterns.add(chosen["pattern"])
    return bonus


def _signature_jitter(signature, name):
    """Petit nombre stable (0-6) dérivé du nom de l'exercice + d'une signature propre
    à la personne (prénom/date de naissance/poids/taille). Sert uniquement à
    départager des exercices à égalité de pertinence, pour éviter que deux profils
    avec le même équipement/blessures/niveau obtiennent systématiquement exactement
    les mêmes exercices."""
    if not signature:
        return 0
    digest = hashlib.md5(f"{signature}::{name}".encode("utf-8")).hexdigest()
    return int(digest[:4], 16) % 7


def _select_pool(muscle, avoid_tags, equip_set, equip_priorite, niveau=None, morpho=None, signature="",
                  used_names=None, equipement=None, excluded_names=None, excluded_patterns=None):
    """
    Regroupe les exercices du muscle par schéma de mouvement ("pattern") et ne
    retient qu'UN SEUL exercice par pattern (le mieux adapté à l'équipement
    disponible, au niveau et à la morphologie de la personne), afin de garantir
    de la variété plutôt que plusieurs variantes du même mouvement (ex :
    développé couché barre + haltères + machine).
    `used_names` : exercices déjà choisis pour ce muscle plus tôt dans la semaine
    (autres séances) — pénalisés pour éviter des séances quasi-identiques quand
    un même muscle revient plusieurs fois (ex : Full Body A/B/C).
    `excluded_names`/`excluded_patterns` : retours "je n'aime pas cet exercice" de
    l'utilisateur sur un programme précédent — jamais reproposés.
    Retourne une liste de (exercice, fallback_used) triée par priorité.
    """
    morpho = morpho or set()
    used_names = used_names or set()
    excluded_names = excluded_names or set()
    excluded_patterns = excluded_patterns or set()
    by_pattern = {}
    for e in EXERCISES[muscle]:
        by_pattern.setdefault(e["pattern"], []).append(e)

    def _niveau_bonus(e):
        if niveau == "Débutant complet":
            return -2 if e["equip"] == "machine" else 0
        if niveau == "Avancé":
            return -2 if (e["equip"] in ("barre", "haltere") and e["kind"] == "compose") else 0
        return 0

    def _morpho_bonus(e):
        return -3 if set(e.get("morpho", [])) & morpho else 0

    def _repeat_bonus(e):
        # Déjà utilisé cette semaine pour ce muscle : on pénalise pour favoriser
        # une autre variante si une existe, plutôt que de répéter le même
        # exercice d'une séance à l'autre (ex : Full Body A/B/C).
        return 6 if e["name"] in used_names else 0

    def _priority_tier(p):
        # Regroupe les priorités 1 et 2 dans le même palier : la variante "phare"
        # d'un mouvement (souvent la barre, priorité 1) et sa meilleure alternative
        # (souvent l'haltère, priorité 2) sont considérées équivalentes et
        # départagées par la signature de la personne, plutôt que la priorité 1
        # qui gagnerait sinon systématiquement pour tout le monde.
        return 1 if p <= 2 else p

    def _elastique_penalty(e):
        # L'élastique est une solution de dépannage (pas de salle/matériel limité),
        # pas un choix à égalité avec la barre/l'haltère/la machine. Sans ce
        # correctif, un élastique en priorité 2 (ex : "Curl élastique") se
        # retrouvait dans le même palier que la barre/l'haltère (priorité 1) via
        # _priority_tier, et pouvait donc être choisi pour quelqu'un en salle
        # complète juste par tirage au sort (signature). On ne le pénalise pas
        # si c'est la seule option disponible (équipement limité à domicile).
        if e["equip"] == "elastique" and equipement in GYM_EQUIPEMENTS:
            return 8
        return 0

    def sort_key(e):
        equip_bonus = -10 if (equip_priorite and e["equip"] in equip_priorite) else 0
        return (equip_bonus + _niveau_bonus(e) + _morpho_bonus(e) + _repeat_bonus(e) + _elastique_penalty(e),
                _priority_tier(e["priority"]), _signature_jitter(signature, e["name"]))

    choices = []
    for pattern, variants in by_pattern.items():
        if pattern in excluded_patterns:
            # L'utilisateur a signalé une douleur/gêne sur un exercice de ce schéma
            # de mouvement : on évite tout le pattern, pas juste l'exercice précis
            # (une autre variante du même mouvement risque de poser le même souci).
            continue
        equip_variants = [v for v in variants if v["equip"] in equip_set and v["name"] not in excluded_names]
        if not equip_variants:
            # Ce schéma de mouvement n'existe tout simplement pas avec l'équipement
            # déclaré (ex : squat barre pour quelqu'un qui n'a que des haltères à
            # la maison), ou bien toutes ses variantes compatibles ont été
            # explicitement rejetées par l'utilisateur : on saute ce pattern.
            continue
        candidates = [v for v in equip_variants if not (set(v["avoid"]) & avoid_tags)]
        fallback_used = False
        if not candidates:
            # Toutes les variantes compatibles avec l'équipement sont exclues pour
            # des raisons de sécurité (blessure) : on garde une variante sûre même
            # si elle demande un autre équipement, plutôt qu'un mouvement à risque.
            candidates = [v for v in variants
                          if not (set(v["avoid"]) & avoid_tags) and v["name"] not in excluded_names]
            fallback_used = True
        if not candidates:
            continue  # aucune variante sûre (et non rejetée) pour ce muscle/pattern
        candidates.sort(key=sort_key)
        choices.append((candidates[0], fallback_used))

    def choice_sort_key(item):
        e, fallback_used = item
        # Un pattern qui n'a nécessité un secours "hors équipement" (fallback_used)
        # passe en dernier : on préfère toujours garder les patterns réellement
        # compatibles avec l'équipement déclaré quand on doit couper au nombre
        # d'exercices demandé.
        fallback_bonus = 10 if fallback_used else 0
        force_bonus = -5 if e["force"] else 0
        # Même logique que _elastique_penalty mais au niveau du choix ENTRE patterns :
        # un pattern qui n'existe qu'en élastique (ex : "hip_hinge_elastique") ne doit
        # être retenu qu'en dernier recours si l'équipement disponible permet mieux
        # (salle complète, machines, poids libres), pas être pioché avant un pattern
        # sur machine/haltère/barre juste par jitter de signature.
        elastique_choice_penalty = 3 if (e["equip"] == "elastique" and equipement in GYM_EQUIPEMENTS) else 0
        return (fallback_bonus + force_bonus + elastique_choice_penalty, e["priority"],
                _signature_jitter(signature, e["pattern"]))

    choices.sort(key=choice_sort_key)

    # Diversité par FAMILLE de mouvement, pas juste par pattern : certains patterns
    # bien distincts en base (développé plat/incliné/décliné) restent "le même
    # exercice" aux yeux de la personne (développé couché sous 3 angles). On
    # réordonne donc pour piocher d'abord le meilleur choix de CHAQUE famille
    # différente, et ne proposer un 2e exercice d'une famille déjà utilisée que
    # si toutes les familles disponibles ont déjà été prises une fois (ex :
    # séance longue avec beaucoup d'exercices demandés sur peu de familles).
    ordered = []
    remaining = choices
    used_families = set()
    while remaining:
        round_pick = []
        leftover = []
        for item in remaining:
            e, _fb = item
            fam = FAMILY_MAP.get(e["pattern"], e["pattern"])
            if fam not in used_families:
                round_pick.append(item)
                used_families.add(fam)
            else:
                leftover.append(item)
        if not round_pick:
            # Ne devrait pas arriver (used_families ne peut que grandir), filet de
            # sécurité pour éviter une boucle infinie.
            ordered.extend(leftover)
            break
        ordered.extend(round_pick)
        remaining = leftover

    return ordered


def _reps_for(index, exo):
    if index == 0 and exo["force"]:
        return 4, "6-8"
    if exo["kind"] == "compose":
        return 3, "8-12"
    return 3, "12-15"


def _build_day_exercises(muscles, exos_par_muscle, avoid_tags, equip_set, equip_priorite,
                          niveau=None, morpho=None, signature="", used_by_muscle=None, equipement=None,
                          excluded_names=None, excluded_patterns=None):
    """Retourne { muscle: [ {nom, series, reps}, ... ] }, warnings[].
    `used_by_muscle` : dict {muscle: set(noms déjà utilisés cette semaine)}, mutable,
    mis à jour au fil des séances pour éviter qu'un muscle qui revient plusieurs
    fois dans la semaine (ex : Full Body) obtienne exactement les mêmes exercices
    à chaque séance."""
    warnings = []
    used_by_muscle = used_by_muscle if used_by_muscle is not None else {}
    day = {}
    for i, muscle in enumerate(muscles):
        count = exos_par_muscle[i] if i < len(exos_par_muscle) else exos_par_muscle[-1]
        used_names = used_by_muscle.setdefault(muscle, set())
        choices = _select_pool(muscle, avoid_tags, equip_set, equip_priorite, niveau, morpho,
                                signature, used_names, equipement, excluded_names, excluded_patterns)
        chosen = choices[:max(1, count)]
        if any(fallback for _, fallback in chosen):
            warnings.append(
                f"Choix d'exercices limité pour {MUSCLE_LABELS[muscle]} : l'équipement "
                f"sélectionné ne suffisait pas, une variante a été gardée malgré tout "
                f"pour respecter tes contraintes de sécurité."
            )
        exos = []
        for idx, (exo, _fallback) in enumerate(chosen):
            sets, reps = _reps_for(idx, exo)
            exos.append({"nom": exo["name"], "series": sets, "reps": reps})
            used_names.add(exo["name"])
        day[muscle] = exos
    return day, warnings


def _estimate_duration(day):
    total_sets = sum(e["series"] for exos in day.values() for e in exos)
    minutes = WARMUP_MIN + (total_sets * SET_TIME_SEC) / 60
    return round(minutes)


def _trim_to_duration(day, duree_max, prioritaires=None, min_total=0):
    """Retire les exercices d'isolation les moins prioritaires (dans les muscles
    ayant le plus d'exercices) jusqu'à rentrer dans la durée demandée. Les muscles
    marqués comme prioritaires par l'utilisateur sont protégés en dernier recours.
    `min_total` : nombre total d'exercices en dessous duquel on ne descend jamais,
    même si la durée estimée dépasse encore `duree_max` (le plancher "9-10 exercices
    minimum selon la durée" prime sur l'estimation de durée, qui reste approximative)."""
    prioritaires = prioritaires or set()
    warnings = []
    trimmed = False
    while _estimate_duration(day) > duree_max:
        total = sum(len(exos) for exos in day.values())
        if total <= min_total:
            break
        # muscle avec le plus d'exercices, et au moins 2 (on ne descend jamais à 0)
        candidats = [m for m, exos in day.items() if len(exos) > 1]
        if not candidats:
            break
        non_prio = [m for m in candidats if m not in prioritaires]
        pool = non_prio if non_prio else candidats
        muscle_cible = max(pool, key=lambda m: len(day[m]))
        day[muscle_cible].pop()  # retire le dernier (le moins prioritaire)
        trimmed = True
    if trimmed:
        warnings.append(
            "Le nombre d'exercices a été réduit automatiquement pour respecter la "
            "durée de séance souhaitée, en gardant les mouvements prioritaires."
        )
    return day, warnings


def _apply_min_exos_par_seance(counts, muscles, prioritaires, min_total, max_dispo=None):
    """Augmente les counts par muscle (round-robin, plafonné à la fois par
    MAX_PAR_MUSCLE et par le nombre réel d'exercices disponibles pour ce muscle
    avec l'équipement/les contraintes actuelles) jusqu'à ce que le total de la
    séance atteigne `min_total`. `max_dispo` : dict {muscle: nb d'exercices
    réellement disponibles} — sans ça, un muscle à faible variété (ex : dos avec
    seulement 4 familles de mouvement) se voyait demander plus d'exercices que ce
    qu'il pouvait fournir, gaspillant le "budget" du plancher au lieu de le
    reporter sur un autre muscle qui, lui, a de la marge (ex : biceps).
    Retourne (counts, reste_manquant) : reste_manquant > 0 si même en poussant
    tous les muscles à leur maximum réel, le plancher demandé n'est pas atteignable."""
    if min_total <= 0:
        return counts, 0
    counts = list(counts)
    max_dispo = max_dispo or {}
    ceilings = [min(MAX_PAR_MUSCLE, max_dispo.get(m, MAX_PAR_MUSCLE)) for m in muscles]
    total = sum(counts)
    if total >= min_total:
        return counts, 0
    i = 0
    n = len(counts)
    # Sécurité anti-boucle infinie : si tous les muscles sont au plafond, on arrête.
    max_iterations = min_total * 4 + 10
    iterations = 0
    while total < min_total and iterations < max_iterations:
        idx = i % n
        if counts[idx] < ceilings[idx]:
            counts[idx] += 1
            total += 1
        i += 1
        iterations += 1
        if all(c >= ceil for c, ceil in zip(counts, ceilings)):
            break  # tous les muscles sont à leur maximum réel, inutile de continuer
    return counts, max(0, min_total - total)


def _priority_counts(nb_muscles, base_count):
    """Construit un dégradé de priorité, ex: base=4 -> [4,3,2,2,...] borné à 2 minimum."""
    counts = []
    for i in range(nb_muscles):
        c = max(2, base_count - i)
        counts.append(c)
    return counts


MUSCLE_PRIORITY_MAP = {
    "Pectoraux": ["pecs"],
    "Dos": ["dos"],
    "Épaules": ["epaules"],
    "Bras (biceps/triceps)": ["biceps", "triceps"],
    "Jambes (quadriceps/ischio)": ["quadriceps", "ischio"],
    "Fessiers": ["fessiers"],
    "Abdominaux": ["abdos"],
}


def _resolve_prioritaires(labels):
    prioritaires = set()
    for label in labels or []:
        prioritaires.update(MUSCLE_PRIORITY_MAP.get(label, []))
    return prioritaires


def _reorder_by_priority(muscles, prioritaires):
    """Place les muscles prioritaires en tête (ordre relatif conservé), le reste ensuite."""
    prio = [m for m in muscles if m in prioritaires]
    rest = [m for m in muscles if m not in prioritaires]
    return prio + rest


OBJECTIF_NOTES = {
    "Perte de gras": (
        "Vu ton objectif de perte de gras, réduis les temps de repos entre les séries "
        "(60-90 sec, y compris sur les exercices « force ») pour augmenter la dépense "
        "calorique de la séance."
    ),
    "Prise de muscle": (
        "Vu ton objectif de prise de muscle, respecte des repos plus longs sur les "
        "mouvements lourds (2-3 min) pour maximiser la charge soulevée, moteur principal "
        "de la prise de muscle."
    ),
    "Recomposition (sec + muscle)": (
        "Vu ton objectif de recomposition, garde des repos modérés (90 sec à 2 min) : "
        "assez pour progresser en charge, assez courts pour garder un peu d'intensité "
        "métabolique."
    ),
    "Performance / explosivité": (
        "Vu ton objectif de performance, exécute la phase concentrique (la poussée/tirée) "
        "le plus explosivement possible sur les exercices « force », même à charge modérée."
    ),
    "Condition physique générale": (
        "Objectif condition physique générale : garde des repos confortables (90 sec) et "
        "priorise la régularité sur la performance pure."
    ),
}

NIVEAU_NOTES = {
    "Débutant complet": (
        "En tant que débutant complet, priorise l'apprentissage du mouvement avant "
        "d'augmenter les charges : les 4-6 premières semaines servent surtout à graver "
        "la technique."
    ),
    "Quelques mois d'expérience": (
        "Avec quelques mois d'expérience, tu peux commencer à augmenter les charges dès "
        "que la technique est maîtrisée, sans attendre la perfection totale."
    ),
    "Intermédiaire": (
        "À ton niveau, la progression linéaire ralentit : varie les rep ranges d'un bloc "
        "à l'autre (quelques semaines en 8-12, puis quelques semaines en 4-6) pour continuer "
        "à progresser."
    ),
    "Avancé": (
        "À ton niveau, envisage des techniques d'intensification ponctuelles (séries "
        "dégressives, rest-pause) sur le dernier exercice de chaque muscle pour continuer "
        "à progresser."
    ),
}


def build_program(data):
    """
    data attendu :
      frequence_entrainement (int), split_preference ("auto"|"full_body"|"upper_lower"|"ppl"|"arnold"),
      equipement (str), blessures (list[str]), exercices_incapables (list[str]),
      duree_seance (str), exos_par_muscle_pref ("auto"|"2"|"3"|"4"), niveau_musculation (str)
    """
    warnings = []
    frequence = int(data.get("frequence_entrainement", 3))
    split_pref = data.get("split_preference", "auto")
    objectif_pour_split = data.get("objectif_principal", "Condition physique générale")
    niveau_pour_split = data.get("niveau_musculation", "Débutant complet")

    split_key = (
        _split_key_auto(frequence, objectif_pour_split, niveau_pour_split)
        if split_pref == "auto" else split_pref
    )
    split = SPLITS[split_key]

    if split_key == "arnold" and frequence < 5:
        warnings.append(
            "Arnold Split choisi avec moins de 5 séances/semaine : chaque muscle sera "
            "travaillé moins souvent que ce que ce split permet idéalement (5-6x/semaine). "
            "Un Push/Pull/Legs serait plus efficace à cette fréquence, mais le programme "
            "ci-dessous respecte ton choix."
        )

    avoid_tags = _avoid_tags(data.get("blessures"), data.get("exercices_incapables"))
    equip_set, equip_priorite = _equip_allowed(data.get("equipement", "Salle complète"))
    duree_max = DUREE_MINUTES.get(data.get("duree_seance", "1h - 1h30"), 90)

    exos_pref = data.get("exos_par_muscle_pref", "auto")
    base_count = split["exos_par_muscle_defaut"] if exos_pref == "auto" else int(exos_pref)

    prioritaires = _resolve_prioritaires(data.get("muscles_prioritaires"))
    if prioritaires:
        labels = ", ".join(sorted(set(data.get("muscles_prioritaires"))))
        warnings.append(f"Priorité donnée à : {labels} (plus de volume sur ces groupes).")

    niveau_musculation = data.get("niveau_musculation", "Débutant complet")
    morpho = set()
    if data.get("longueur_bras") == "Plutôt longs":
        morpho.add("bras_longs")
    elif data.get("longueur_bras") == "Plutôt courts":
        morpho.add("bras_courts")
    if data.get("longueur_jambes") == "Plutôt longues":
        morpho.add("jambes_longues")
    elif data.get("longueur_jambes") == "Plutôt courtes":
        morpho.add("jambes_courtes")
    signature = data.get("signature", "")
    # Un même muscle peut revenir plusieurs fois dans la semaine (Full Body, ou
    # Upper/Lower A+B) : on garde en mémoire ce qui a déjà été choisi pour éviter
    # des séances quasi-identiques d'un jour à l'autre.
    used_by_muscle = {}

    # Retours "je n'aime pas cet exercice" d'un programme précédent : jamais
    # reproposés (tout le pattern si la raison est une douleur/gêne).
    excluded_names, excluded_patterns = _rejected_sets(data.get("exercices_rejetes"))
    if excluded_names:
        warnings.append(
            f"Suite à tes retours, {len(excluded_names)} exercice(s) que tu n'appréciais "
            f"pas ou plus ont été remplacés par une autre variante."
        )

    min_total_seance = MIN_EXOS_PAR_SEANCE.get(data.get("duree_seance", "1h - 1h30"), 0)
    if min_total_seance:
        warnings.append(
            f"Chaque séance de cette durée comporte un minimum de {min_total_seance} exercices "
            f"au total, pour bien remplir le temps disponible."
        )

    programme = []
    for jour in split["jours"]:
        muscles = _reorder_by_priority(jour["muscles"], prioritaires)
        if split_key == "full_body":
            counts = [base_count for _ in muscles]
        else:
            counts = _priority_counts(len(muscles), base_count)
        # Boost explicite : un muscle prioritaire gagne toujours +1 exercice (borné à 5),
        # qu'il soit déjà en tête de liste par défaut ou non.
        counts = [min(5, c + 1) if m in prioritaires else c for c, m in zip(counts, muscles)]
        day_signature = f"{signature}::{jour['nom']}"
        # Plancher "9-10 exercices minimum par séance" selon la durée choisie : on
        # ajoute des exercices (round-robin) si le total actuel n'atteint pas encore
        # ce plancher. On calcule d'abord combien d'exercices chaque muscle peut
        # réellement fournir (équipement/blessures/exclusions) pour ne pas gaspiller
        # le "budget" sur un muscle à faible variété (ex : dos) au lieu de le
        # reporter sur un muscle qui a de la marge (ex : biceps).
        if min_total_seance:
            # Important : on compte les FAMILLES distinctes disponibles, pas juste les
            # patterns. Sinon un muscle avec beaucoup de patterns mais peu de familles
            # réellement différentes (ex : pecs = 6 patterns mais seulement 3 familles
            # presse/écarté/pull-over) se voit quand même demander plus d'exercices que
            # sa diversité réelle ne le permet, forçant un doublon de famille (ex :
            # 2x développé couché) au lieu de reporter l'exercice en trop sur un autre
            # muscle de la séance qui a plus de marge.
            def _familles_dispo(m):
                choices = _select_pool(m, avoid_tags, equip_set, equip_priorite, niveau_musculation, morpho,
                                        day_signature, used_by_muscle.get(m, set()),
                                        data.get("equipement", "Salle complète"), excluded_names, excluded_patterns)
                return len({FAMILY_MAP.get(e["pattern"], e["pattern"]) for e, _fb in choices})

            max_dispo = {m: _familles_dispo(m) for m in muscles}
            counts, manque = _apply_min_exos_par_seance(counts, muscles, prioritaires, min_total_seance, max_dispo)
            if manque:
                warnings.append(
                    f"{jour['nom']} : impossible d'atteindre {min_total_seance} exercices avec tes "
                    f"contraintes actuelles (équipement/blessures/exclusions) — {sum(counts)} exercices "
                    f"proposés, c'est le maximum réellement disponible pour cette séance."
                )
        day, day_warnings = _build_day_exercises(muscles, counts, avoid_tags, equip_set, equip_priorite,
                                                  niveau_musculation, morpho, day_signature, used_by_muscle,
                                                  data.get("equipement", "Salle complète"),
                                                  excluded_names, excluded_patterns)
        warnings.extend(day_warnings)
        # Le premier muscle de la séance (tel que défini par le split, avant réordre
        # par priorité utilisateur) est le muscle principal de la séance — celui qui
        # reçoit le plus d'exercices. On le protège aussi en cas de réduction pour
        # tenir la durée, pour ne pas annuler cet effet "muscle principal".
        muscle_principal = {jour["muscles"][0]} if jour["muscles"] else set()
        day, trim_warnings = _trim_to_duration(day, duree_max, prioritaires | muscle_principal, min_total_seance)
        warnings.extend(trim_warnings)
        duree_estimee = _estimate_duration(day)

        # Petite section poids du corps FACULTATIVE, en lien avec les muscles de
        # cette séance : uniquement pour les profils salle, où le poids du corps a
        # été retiré du programme principal (voir _equip_allowed).
        bonus_poids_du_corps = []
        if data.get("equipement", "Salle complète") in GYM_EQUIPEMENTS:
            bonus_poids_du_corps = _select_bodyweight_bonus(muscles, avoid_tags, day_signature)

        programme.append({
            "nom": jour["nom"],
            "muscles": [
                {"muscle": MUSCLE_LABELS[m], "exercices": day[m]} for m in muscles if day[m]
            ],
            "duree_estimee_min": duree_estimee,
            "bonus_poids_du_corps": bonus_poids_du_corps,
        })

    # dédoublonne les warnings en gardant l'ordre
    seen = set()
    warnings_uniques = []
    for w in warnings:
        if w not in seen:
            warnings_uniques.append(w)
            seen.add(w)

    objectif = data.get("objectif_principal", "Condition physique générale")
    niveau = data.get("niveau_musculation", "Débutant complet")

    return {
        "split_label": split["label"],
        "split_key": split_key,
        "programme": programme,
        "warnings": warnings_uniques,
        "objectif_note": OBJECTIF_NOTES.get(objectif),
        "niveau_note": NIVEAU_NOTES.get(niveau),
        "equipement": data.get("equipement", "Salle complète"),
        "prioritaires_labels": sorted(set(data.get("muscles_prioritaires") or [])),
        "morpho_labels": sorted(morpho),
    }
