# -*- coding: utf-8 -*-
"""
Moteur de calcul nutritionnel : BMR (Mifflin-St Jeor), TDEE, ajustement
calorique selon l'objectif, répartition des macros, et garde-fous de
sécurité (mineurs, grossesse, condition médicale).
"""
from datetime import date


def calculate_age(birthdate_iso, today=None):
    """birthdate_iso: 'YYYY-MM-DD'"""
    today = today or date.today()
    y, m, d = [int(x) for x in birthdate_iso.split("-")]
    born = date(y, m, d)
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age


def bmr_mifflin(sexe, poids_kg, taille_cm, age):
    base = 10 * poids_kg + 6.25 * taille_cm - 5 * age
    return base + 5 if sexe == "Homme" else base - 161


def activity_factor(niveau_quotidien, frequence_entrainement, cardio_sessions_semaine=0,
                     autre_sport_sessions=0):
    """
    niveau_quotidien : 'sedentaire' | 'modere' | 'actif'
    frequence_entrainement : int (nb séances muscu / semaine)
    cardio_sessions_semaine : int (nb séances cardio / semaine, en plus)
    autre_sport_sessions : int (nb séances d'un autre sport pratiqué en parallèle)
    """
    base = {"sedentaire": 1.2, "modere": 1.35, "actif": 1.5}.get(niveau_quotidien, 1.2)
    total_sessions = frequence_entrainement + cardio_sessions_semaine + autre_sport_sessions
    if total_sessions <= 2:
        increment = 0.05
    elif total_sessions <= 3:
        increment = 0.10
    elif total_sessions <= 4:
        increment = 0.15
    elif total_sessions <= 5:
        increment = 0.20
    elif total_sessions <= 7:
        increment = 0.25
    else:
        increment = 0.30
    return round(base + increment, 3)


def imc(poids_kg, taille_cm):
    taille_m = taille_cm / 100
    return round(poids_kg / (taille_m ** 2), 1)


def imc_category(imc_val):
    if imc_val < 18.5:
        return "sous-poids"
    if imc_val < 25:
        return "poids normal"
    if imc_val < 30:
        return "surpoids"
    return "obésité"


def kcal_adjustment(objectif, imc_val, niveau_musculation, age):
    """Retourne (ajustement_kcal, warnings[])"""
    warnings = []
    objectif = objectif.strip()

    if objectif == "Prise de muscle":
        adj = 250 if niveau_musculation == "Débutant complet" else 300
    elif objectif == "Perte de gras":
        if imc_val >= 30:
            adj = -500
        elif imc_val >= 25:
            adj = -400
        else:
            adj = -300
    elif objectif == "Recomposition (sec + muscle)":
        adj = -300 if imc_val >= 25 else -150
    else:  # Performance / explosivité, Condition physique générale
        adj = 0

    if age < 18 and abs(adj) > 300:
        warnings.append(
            "Ajustement calorique plafonné à 300 kcal (max/min) car l'utilisateur est mineur, "
            "pour ne pas interférer avec la croissance."
        )
        adj = max(min(adj, 300), -300)

    return adj, warnings


def macros(objectif, poids_kg, kcal_objectif, niveau_musculation):
    warnings = []

    if objectif == "Prise de muscle":
        proteine_par_kg = 2.0 if niveau_musculation == "Débutant complet" else 1.8
    elif objectif == "Perte de gras":
        proteine_par_kg = 2.0
    elif objectif == "Recomposition (sec + muscle)":
        proteine_par_kg = 1.9
    else:
        proteine_par_kg = 1.6

    proteines_g = round(proteine_par_kg * poids_kg)
    proteines_kcal = proteines_g * 4

    lipides_g = round(0.9 * poids_kg)
    lipides_kcal = lipides_g * 9

    # Bornes de sécurité sur les lipides : entre 20% et 35% des calories totales
    if lipides_kcal > 0.35 * kcal_objectif:
        lipides_kcal = 0.35 * kcal_objectif
        lipides_g = round(lipides_kcal / 9)
    elif lipides_kcal < 0.20 * kcal_objectif:
        lipides_kcal = 0.20 * kcal_objectif
        lipides_g = round(lipides_kcal / 9)

    glucides_kcal = kcal_objectif - proteines_kcal - lipides_kcal
    if glucides_kcal < 0:
        warnings.append(
            "Apport calorique très bas par rapport aux besoins en protéines/lipides : "
            "les glucides ont été ramenés à un minimum de sécurité."
        )
        glucides_kcal = max(glucides_kcal, 50 * 4)  # plancher 50g

    glucides_g = round(glucides_kcal / 4)

    return {
        "proteines_g": proteines_g,
        "lipides_g": lipides_g,
        "glucides_g": glucides_g,
    }, warnings


def build_nutrition_profile(data):
    """
    data attendu (dict) :
      sexe, poids, taille, date_naissance, niveau_activite_quotidien,
      frequence_entrainement, cardio_sessions_semaine, autre_sport_sessions,
      objectif_principal, niveau_musculation, grossesse (bool, optionnel),
      condition_medicale (bool), condition_medicale_details (str)
    """
    result = {"blocked": False, "warnings": [], "messages": []}

    age = calculate_age(data["date_naissance"])
    result["age"] = age

    if age < 13:
        result["blocked"] = True
        result["messages"].append(
            "Cet outil n'est pas conçu pour les moins de 13 ans. Merci de consulter un "
            "pédiatre ou un professionnel de santé pour toute question de nutrition ou "
            "d'activité physique à cet âge."
        )
        return result

    if data.get("sexe") == "Femme" and data.get("grossesse") == "Oui":
        result["blocked"] = True
        result["messages"].append(
            "En cas de grossesse en cours, un déficit calorique ou un programme "
            "d'entraînement intensif n'est pas recommandé sans encadrement médical. "
            "Merci de consulter ton médecin ou ta sage-femme pour un suivi alimentaire "
            "et sportif adapté à ta grossesse."
        )
        return result

    poids = float(data["poids"])
    taille = float(data["taille"])
    sexe = data["sexe"]
    niveau_musculation = data.get("niveau_musculation", "Débutant complet")
    objectif = data.get("objectif_principal", "Condition physique générale")
    frequence = int(data.get("frequence_entrainement", 3))
    cardio_sessions = int(data.get("cardio_sessions_semaine", 0))
    autre_sport_sessions = int(data.get("autre_sport_sessions", 0))
    niveau_quotidien = data.get("niveau_activite_quotidien", "sedentaire")

    if not (30 <= poids <= 300):
        result["blocked"] = True
        result["messages"].append("Le poids renseigné semble hors de la plage réaliste (30-300 kg).")
        return result
    if not (100 <= taille <= 250):
        result["blocked"] = True
        result["messages"].append("La taille renseignée semble hors de la plage réaliste (100-250 cm).")
        return result

    bmr = bmr_mifflin(sexe, poids, taille, age)
    facteur = activity_factor(niveau_quotidien, frequence, cardio_sessions, autre_sport_sessions)
    tdee = bmr * facteur
    imc_val = imc(poids, taille)

    adj, adj_warnings = kcal_adjustment(objectif, imc_val, niveau_musculation, age)
    result["warnings"].extend(adj_warnings)

    kcal_objectif = tdee + adj

    # Plancher de sécurité : jamais en dessous de 1.2 x BMR
    plancher = bmr * 1.2
    if kcal_objectif < plancher:
        result["warnings"].append(
            "L'objectif calorique a été remonté automatiquement pour rester au-dessus "
            "d'un plancher de sécurité (1,2 x métabolisme de base)."
        )
        kcal_objectif = plancher
        adj = round(kcal_objectif - tdee)

    macro_vals, macro_warnings = macros(objectif, poids, kcal_objectif, niveau_musculation)
    result["warnings"].extend(macro_warnings)

    if data.get("condition_medicale") == "Oui":
        result["warnings"].append(
            "Condition médicale déclarée par l'utilisateur : ce plan doit être validé par "
            "un médecin ou un professionnel de santé avant d'être suivi."
        )

    if age < 18:
        result["warnings"].append(
            "Utilisateur mineur : il est recommandé qu'un médecin ou nutritionniste valide "
            "ce plan, notamment pour s'assurer qu'il n'interfère pas avec la croissance."
        )

    total_sessions_semaine = frequence + cardio_sessions + autre_sport_sessions
    if total_sessions_semaine >= 8:
        result["warnings"].append(
            f"Volume total d'activité élevé ({total_sessions_semaine} séances/semaine tous "
            f"types confondus) : veille à bien respecter les jours de repos pour éviter le "
            f"surentraînement."
        )

    result.update({
        "bmr": round(bmr),
        "facteur_activite": facteur,
        "tdee": round(tdee),
        "imc": imc_val,
        "imc_categorie": imc_category(imc_val),
        "ajustement_kcal": round(adj),
        "kcal_objectif": round(kcal_objectif),
        **macro_vals,
    })
    return result
