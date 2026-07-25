# -*- coding: utf-8 -*-
"""
Moteur de recommandation de compléments alimentaires. Ne se limite plus à
créatine/whey : combine ce que l'utilisateur a coché avec des suggestions
déduites de son profil complet (blessures, sommeil, sexe, IMC, objectif,
niveau, restriction alimentaire).
"""

CATALOGUE = {
    "Créatine": {
        "dosage": "3 à 5 g par jour, tous les jours",
        "explication": "force, puissance et récupération musculaire — utile pour quasiment tous les objectifs.",
        "forme": "poudre (monohydrate), neutre en goût, à diluer dans de l'eau ou un shaker",
        "moment": "à n'importe quel moment de la journée, y compris les jours de repos — la régularité "
                  "compte plus que l'heure de prise",
    },
    "Whey": {
        "dosage": "20-30 g par prise, notamment après l'entraînement",
        "explication": "facilite l'atteinte de l'apport en protéines au quotidien.",
        "forme": "poudre à mélanger avec de l'eau ou du lait au shaker",
        "moment": "idéalement dans les 1 à 2h après l'entraînement, ou en complément d'un repas pauvre en "
                  "protéines",
    },
    "Oméga-3": {
        "dosage": "1 à 2 g d'EPA+DHA par jour",
        "explication": "anti-inflammatoire, soutien articulaire et cardiovasculaire.",
        "forme": "capsules (huile de poisson, ou huile d'algue pour les végans)",
        "moment": "au cours d'un repas contenant un peu de gras, pour une meilleure absorption",
    },
    "Vitamine D": {
        "dosage": "1000 à 2000 UI par jour (à confirmer par une prise de sang si possible)",
        "explication": "souvent carencée en cas de faible exposition au soleil ou d'activité surtout en intérieur.",
        "forme": "gouttes ou capsules",
        "moment": "au cours d'un repas (vitamine liposoluble, mieux absorbée avec des graisses), le matin ou le midi",
    },
    "Magnésium / ZMA": {
        "dosage": "300 à 400 mg de magnésium le soir",
        "explication": "peut améliorer la qualité du sommeil et la récupération musculaire.",
        "forme": "gélules ou comprimés",
        "moment": "le soir, environ 30 à 60 min avant le coucher, pour l'effet sur le sommeil",
    },
    "Béta-alanine": {
        "dosage": "3 à 5 g par jour, effet cumulatif sur plusieurs semaines",
        "explication": "retarde la fatigue musculaire sur les efforts de 1 à 4 minutes, utile en fin de série.",
        "forme": "poudre ou gélules",
        "moment": "répartie en plusieurs prises dans la journée (effet cumulatif) — pas besoin de la prendre "
                  "juste avant l'entraînement",
    },
    "Multivitamines": {
        "dosage": "1 prise par jour selon l'étiquette",
        "explication": "filet de sécurité si l'alimentation est restrictive ou peu variée.",
        "forme": "comprimé ou gélule",
        "moment": "le matin, au cours d'un repas",
    },
    "Fer": {
        "dosage": "à ne prendre qu'en cas de carence confirmée par une prise de sang",
        "explication": "carence plus fréquente chez les femmes et en cas d'alimentation végétarienne/végane — ne pas se supplémenter sans dosage sanguin.",
        "forme": "comprimé (sur prescription, selon le dosage sanguin)",
        "moment": "à jeun ou avec un peu de vitamine C pour l'absorption, à distance du café/thé qui la réduisent",
    },
    "Collagène": {
        "dosage": "10 à 15 g par jour, idéalement avec de la vitamine C",
        "explication": "soutien de la santé des articulations et des tendons.",
        "forme": "poudre neutre ou aromatisée",
        "moment": "à jeun le matin ou avant le coucher, avec une source de vitamine C pour favoriser la synthèse",
    },
    "BCAA/EAA": {
        "dosage": "selon l'étiquette, autour des séances",
        "explication": "peu utile si l'apport total en protéines du jour est déjà suffisant.",
        "forme": "poudre ou gélules",
        "moment": "autour de l'entraînement (avant ou pendant), surtout utile si pris à jeun",
    },
    "Caféine / pré-workout": {
        "dosage": "150 à 300 mg environ 30-45 min avant la séance",
        "explication": "améliore la force perçue et réduit la fatigue à l'entraînement.",
        "forme": "gélule, comprimé ou poudre à diluer",
        "moment": "30 à 45 min avant la séance — à éviter après 16h-17h pour ne pas perturber le sommeil",
    },
}


def recommend_supplements(data):
    """
    data attendu : complements (list), blessures (list), sommeil (str), sexe (str),
    imc (float), objectif_principal (str), niveau_musculation (str),
    restriction_alimentaire (str), niveau_activite_quotidien (str)
    Retourne { "choisis": [...], "suggestions": [...] } avec dosage + explication.
    """
    choisis = set(data.get("complements", []) or [])
    choisis.discard("Autre")

    suggestions = set()

    if data.get("blessures"):
        suggestions.update(["Collagène", "Oméga-3"])

    if data.get("sommeil") in ("Moins de 6h", "6 à 7h"):
        suggestions.add("Magnésium / ZMA")

    if data.get("sexe") == "Femme" and data.get("restriction_alimentaire") in ("Végétarien", "Végan"):
        suggestions.add("Fer")
        suggestions.add("Multivitamines")

    niveau = data.get("niveau_musculation", "")
    objectif = data.get("objectif_principal", "")
    if niveau in ("Intermédiaire", "Avancé") and objectif in (
        "Prise de muscle", "Recomposition (sec + muscle)", "Performance / explosivité"
    ):
        suggestions.add("Béta-alanine")

    if objectif == "Performance / explosivité":
        suggestions.add("Caféine / pré-workout")

    if data.get("niveau_activite_quotidien") == "sedentaire":
        suggestions.add("Vitamine D")

    if data.get("restriction_alimentaire") in ("Végétarien", "Végan"):
        suggestions.add("Oméga-3")  # moins d'apport via poisson gras

    # on ne suggère pas ce qui est déjà choisi
    suggestions -= choisis

    def build(names):
        out = []
        for n in names:
            info = CATALOGUE.get(n)
            if info:
                out.append({
                    "nom": n,
                    "dosage": info["dosage"],
                    "explication": info["explication"],
                    "forme": info["forme"],
                    "moment": info["moment"],
                })
        return out

    return {
        "choisis": build(sorted(choisis)),
        "suggestions": build(sorted(suggestions)),
    }
