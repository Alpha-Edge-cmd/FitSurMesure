# -*- coding: utf-8 -*-
"""
Adaptation du programme de musculation à un sport pratiqué en parallèle
(prompt hors 24 phases, retour Samy : "demande si tu veux que le programme
soit adapté à ce sport et fais toi une petite mémoire des sports les plus
pratiqués en France").

Périmètre volontairement limité : une "petite mémoire" documentée des sports
les plus pratiqués en France (source : chiffres de licenciés fédérations
sportives françaises, ordre de grandeur connu — football, tennis, équitation,
judo/arts martiaux, basket... très majoritaires), associés aux groupes
musculaires que ce sport sollicite le plus et qui bénéficient donc d'être
priorisés dans le programme de musculation (même mécanisme que
"muscles_prioritaires" choisi manuellement au questionnaire, cf.
`logic.program_builder.MUSCLE_PRIORITY_MAP`/`_resolve_prioritaires`, réutilisé
en lecture seule par `workout_generator.py`). Aucune formule sportive
scientifique n'est prétendue ici : c'est une association raisonnable et
documentée, pas une périodisation spécifique au sport (hors périmètre d'un
générateur de programme de musculation généraliste).
"""

# Sports proposés au questionnaire (select), dans un ordre approximatif de
# popularité en France (licences FFF, FFT, judo, basket, athlétisme...),
# suivi des sports cités explicitement par Samy. "Autre" permet toujours de
# sortir de cette liste (texte libre, cf. static/script.js).
SPORTS_FRANCE = [
    "Football",
    "Tennis",
    "Basketball",
    "Sports de combat (boxe, MMA, kickboxing...)",
    "Arts martiaux (judo, karaté, taekwondo...)",
    "Athlétisme / course à pied",
    "Rugby",
    "Natation",
    "Cyclisme",
    "Handball",
    "Volleyball",
    "Danse",
    "Escalade",
    "Golf",
    "Autre",
]

# Muscles (clés moteur, cf. logic/exercises_db.MUSCLE_LABELS) sollicités en
# priorité par chaque sport -> reçoivent le même traitement que les muscles
# prioritaires choisis manuellement (plancher d'exercices plus élevé,
# cf. workout_generator._muscles_ordonnes_par_priorite).
SPORT_MUSCLES_PRIORITAIRES = {
    "Football": {"quadriceps", "ischio", "mollets", "fessiers", "abdos"},
    "Tennis": {"epaules", "dos", "abdos", "triceps"},
    "Basketball": {"quadriceps", "mollets", "fessiers", "abdos", "epaules"},
    "Sports de combat (boxe, MMA, kickboxing...)": {"dos", "epaules", "abdos", "triceps", "quadriceps"},
    "Arts martiaux (judo, karaté, taekwondo...)": {"dos", "abdos", "epaules", "quadriceps", "fessiers"},
    "Athlétisme / course à pied": {"quadriceps", "ischio", "mollets", "fessiers", "abdos"},
    "Rugby": {"quadriceps", "fessiers", "dos", "epaules", "abdos"},
    "Natation": {"dos", "epaules", "abdos", "triceps"},
    "Cyclisme": {"quadriceps", "ischio", "mollets", "fessiers", "abdos"},
    "Handball": {"epaules", "abdos", "quadriceps", "mollets"},
    "Volleyball": {"mollets", "quadriceps", "epaules", "abdos"},
    "Danse": {"abdos", "fessiers", "mollets", "dos"},
    "Escalade": {"dos", "biceps", "abdos"},
    "Golf": {"abdos", "dos", "epaules"},
}


def resolve_sport_muscles(profile):
    """Retourne l'ensemble des muscles (clés moteur) à prioriser du fait du
    sport pratiqué en parallèle, UNIQUEMENT si l'utilisateur a explicitement
    demandé cette adaptation (`autre_sport_adapter == "Oui"`, question
    conditionnelle affichée seulement si `autre_sport == "Oui"`, cf.
    static/script.js) — jamais une adaptation silencieuse/non demandée.
    Ensemble vide si le sport déclaré ("Autre" ou texte libre non reconnu)
    n'a pas de correspondance documentée ci-dessus : pas d'invention de
    règle, comportement inchangé dans ce cas (même principe que le reste du
    moteur, cf. fallback.py)."""
    variables = getattr(profile, "variables_json", None) or {}
    if variables.get("autre_sport") != "Oui":
        return set()
    if variables.get("autre_sport_adapter") != "Oui":
        return set()
    sport = variables.get("autre_sport_type")
    return set(SPORT_MUSCLES_PRIORITAIRES.get(sport, ()))
