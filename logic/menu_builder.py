# -*- coding: utf-8 -*-
"""
Construction du menu de la semaine à partir de la base de recettes.

Retour Samy : « les repas doivent être gourmands, healthy, diététiques et
adaptés aux objectifs », et « le plus de repas possible ».

Rôle de ce module : choisir, parmi les recettes disponibles, celles qui
correspondent réellement au profil, puis les répartir sur 7 jours sans
répétition excessive.

Filtres DURS (une recette écartée ne revient jamais) :
  - restriction alimentaire déclarée (végétarien, végan, sans lactose,
    sans gluten) ;
  - allergie déclarée et aliments explicitement non appréciés.

Critères de PRÉFÉRENCE (ils classent, ils n'excluent pas) :
  - objectif (prise de masse / perte de gras / maintien) ;
  - aliments appréciés cochés au questionnaire ;
  - temps disponible pour cuisiner ;
  - budget.

Ce module ne calcule pas les besoins caloriques : il consomme ceux déjà
calculés par `calculations.build_nutrition_profile` et cherche à s'en
approcher, en affichant l'écart plutôt qu'en le masquant.
"""
import hashlib
import unicodedata

from logic import recipes_db as db

# Correspondance entre la restriction déclarée au questionnaire et le tag que
# la recette doit obligatoirement porter pour être retenue.
RESTRICTION_TAG_REQUIS = {
    "Végétarien": db.VEGE,
    "Végan": db.VEGAN,
    "Sans lactose": db.SANS_LACTOSE,
    "Sans gluten": db.SANS_GLUTEN,
}

OBJECTIF_CIBLE = {
    "Prise de muscle": db.PRISE,
    "Perte de gras": db.PERTE,
    "Recomposition (sec + muscle)": db.MAINTIEN,
    "Performance / explosivité": db.MAINTIEN,
    "Condition physique générale": db.MAINTIEN,
}

# Catégories cochées au questionnaire -> mots-clés présents dans `aliments`.
CATEGORIE_VERS_ALIMENTS = {
    "Poulet": ["poulet"],
    "Dinde": ["dinde"],
    "Volaille (autre)": ["volaille", "poulet", "dinde"],
    "Viande rouge": ["boeuf", "viande rouge"],
    "Poisson": ["poisson", "saumon", "thon", "cabillaud", "crevettes"],
    "Œufs": ["oeufs"],
    "Légumineuses": ["legumineuses", "lentilles", "pois chiches", "haricots"],
    "Produits laitiers": ["fromage", "skyr", "yaourt", "fromage blanc", "cottage", "lait"],
    "Fruits à coque": ["amandes", "noix", "cacahuete"],
}

JOURS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")


def _sans_accent(texte):
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(texte).lower())
        if not unicodedata.combining(c)
    )


def _termes_exclus(aliments_non_apprecies, allergie_details):
    """Mots-clés à bannir, issus des deux champs de texte libre du
    questionnaire. Une allergie est traitée exactement comme une aversion :
    exclusion dure, sans exception."""
    termes = []
    for source in (aliments_non_apprecies, allergie_details):
        if not source:
            continue
        brut = str(source).replace(";", ",").replace(" et ", ",")
        termes.extend(t.strip() for t in brut.split(",") if len(t.strip()) >= 3)
    return [_sans_accent(t) for t in termes]


def _recette_exclue(recette, tag_requis, termes_exclus):
    if tag_requis and tag_requis not in recette["tags"]:
        return True

    if termes_exclus:
        # On cherche dans les mots-clés ET dans la liste d'ingrédients : quelqu'un
        # qui écrit "champignons" ne doit pas se retrouver avec une recette qui
        # en contient, même si ce n'est pas l'ingrédient principal.
        texte = _sans_accent(" ".join(recette["aliments"]) + " " + " ".join(recette["ingredients"]))
        for terme in termes_exclus:
            if terme in texte:
                return True
    return False


def _score_recette(recette, objectif_cible, aliments_preferes, temps_limite, budget_serre):
    """Score de préférence. Ne sert qu'à classer : aucune recette n'est écartée
    à cause d'un score faible, sinon un profil très contraint se retrouverait
    sans menu."""
    score = 0

    if objectif_cible in recette["objectifs"]:
        score += 10

    # Aliments explicitement appréciés : c'est le levier le plus direct entre
    # la réponse au questionnaire et le contenu de l'assiette.
    if aliments_preferes:
        communs = recette["aliments"] & aliments_preferes
        score += 6 * min(len(communs), 3)

    if temps_limite:
        if recette["minutes"] <= 15:
            score += 8
        elif recette["minutes"] <= 25:
            score += 3
        else:
            score -= 6

    if budget_serre:
        score += 5 if recette["budget"] == "serre" else -4

    # À qualité égale, on préfère une recette gourmande : c'est ce qui fait
    # tenir un plan alimentaire dans la durée, et c'était la demande explicite.
    if recette["gourmand"]:
        score += 3

    return score


def _graine(signature, cle):
    return int(hashlib.sha256(f"{signature}|{cle}".encode("utf-8")).hexdigest()[:8], 16)


def _selection_variee(candidats, nombre, signature, cle):
    """Prend `nombre` recettes parmi les mieux classées, sans jamais répéter
    tant qu'il reste des recettes différentes disponibles.

    Le décalage dérivé de la signature du profil évite que deux personnes aux
    réponses proches reçoivent exactement le même menu — même principe que la
    rotation des exercices (`selector._graine_rotation`)."""
    if not candidats:
        return []

    depart = _graine(signature, cle) % len(candidats)
    ordonnes = candidats[depart:] + candidats[:depart]

    choix = []
    while len(choix) < nombre:
        restants = [r for r in ordonnes if r not in choix]
        if not restants:
            # Moins de recettes disponibles que de repas à couvrir : on
            # recommence le cycle plutôt que de laisser des trous.
            choix.append(ordonnes[len(choix) % len(ordonnes)])
            continue
        choix.append(restants[0])
    return choix


def build_menu(data, kcal_objectif=None, jours=7):
    """Construit le menu de la semaine.

    `data` : dictionnaire du questionnaire (mêmes clés que celles reçues par
    app.py). `kcal_objectif` : objectif calorique déjà calculé.

    Retourne un dict :
      {"menu": [{"jour", "repas": [{"moment", "recette"}], "kcal_total"}],
       "recettes_utilisees": [...],
       "kcal_objectif": int|None,
       "avertissements": [...]}
    """
    avertissements = []

    restriction = data.get("restriction_alimentaire", "Aucune")
    tag_requis = RESTRICTION_TAG_REQUIS.get(restriction)
    termes_exclus = _termes_exclus(
        data.get("aliments_non_apprecies"), data.get("allergie_details")
    )

    objectif_cible = OBJECTIF_CIBLE.get(
        data.get("objectif_principal", "Condition physique générale"), db.MAINTIEN
    )

    aliments_preferes = set()
    for categorie in (data.get("aliments_apprecies") or []):
        aliments_preferes.update(CATEGORIE_VERS_ALIMENTS.get(categorie, []))

    temps_limite = data.get("temps_cuisine") == "Peu de temps (recettes rapides)"
    budget_serre = data.get("budget_alimentaire") == "Serré"
    signature = data.get("signature", "") or f"{restriction}|{objectif_cible}"

    # Nombre de repas par jour, depuis la réponse "repas par jour souhaités".
    repas_par_jour = str(data.get("repas_par_jour", "3 à 4"))
    moments = ["petit_dejeuner", "dejeuner", "diner"]
    if repas_par_jour.startswith("3 à 4"):
        moments.append("collation")
    elif repas_par_jour.startswith("4 à 5"):
        moments.extend(["collation", "collation"])

    menu = []
    utilisees = {}

    for index_jour in range(min(jours, len(JOURS))):
        repas_du_jour = []
        for position, moment in enumerate(moments):
            disponibles = [
                r for r in db.recettes_par_moment(moment)
                if not _recette_exclue(r, tag_requis, termes_exclus)
            ]

            if not disponibles:
                if moment not in [a.get("moment") for a in avertissements if isinstance(a, dict)]:
                    avertissements.append(
                        f"Aucune recette de {db.MOMENT_LABELS[moment].lower()} ne correspond à "
                        f"la fois à ta restriction alimentaire et aux aliments que tu ne veux "
                        f"pas. Les suggestions de ce repas sont donc absentes du menu — "
                        f"écris-nous et on t'en ajoutera."
                    )
                continue

            disponibles.sort(
                key=lambda r: (
                    -_score_recette(r, objectif_cible, aliments_preferes,
                                    temps_limite, budget_serre),
                    r["id"],
                )
            )

            choix = _selection_variee(
                disponibles, index_jour + 1, signature, f"{moment}-{position}"
            )[index_jour]

            repas_du_jour.append({"moment": moment, "recette": choix})
            utilisees[choix["id"]] = choix

        menu.append({
            "jour": JOURS[index_jour],
            "repas": repas_du_jour,
            "kcal_total": sum(r["recette"]["kcal"] for r in repas_du_jour),
            "proteines_total": sum(r["recette"]["proteines"] for r in repas_du_jour),
        })

    # --- Ajustement des portions ---------------------------------------------
    # Les recettes sont écrites pour une portion standard. Un même menu doit
    # pouvoir servir à quelqu'un qui vise 1 800 kcal comme à quelqu'un qui en
    # vise 3 200 : sans coefficient, tout le monde recevrait la même quantité
    # de nourriture, et le plan ne correspondrait à l'objectif de personne.
    #
    # On calcule donc un coefficient à appliquer aux quantités, plutôt que de
    # multiplier les recettes par niveau calorique. C'est aussi ce qu'un
    # diététicien fait en pratique : mêmes plats, portions ajustées.
    facteur = 1.0
    if kcal_objectif and menu:
        moyenne_brute = sum(j["kcal_total"] for j in menu) / len(menu)
        if moyenne_brute > 0:
            facteur = kcal_objectif / moyenne_brute
            # Bornes de bon sens : au-delà, ce n'est plus un ajustement de
            # portion mais un menu inadapté — mieux vaut le dire.
            facteur = max(0.7, min(1.8, facteur))

    for jour in menu:
        jour["facteur_portions"] = round(facteur, 2)
        jour["kcal_ajuste"] = round(jour["kcal_total"] * facteur)
        jour["proteines_ajuste"] = round(jour["proteines_total"] * facteur)

    if kcal_objectif and menu:
        moyenne_ajustee = sum(j["kcal_ajuste"] for j in menu) / len(menu)
        ecart = moyenne_ajustee - kcal_objectif

        if abs(facteur - 1.0) >= 0.08:
            sens = "augmente" if facteur > 1 else "réduis"
            pourcentage = abs(round((facteur - 1) * 100))
            avertissements.append(
                f"Portions : {sens} d'environ {pourcentage}% les quantités indiquées dans les "
                f"recettes pour atteindre ton objectif de {kcal_objectif} kcal par jour. "
                f"Fais-le d'abord sur les féculents et les matières grasses, en gardant les "
                f"portions de protéines telles quelles."
            )

        if abs(ecart) > 250:
            sens = "au-dessus" if ecart > 0 else "en dessous"
            avertissements.append(
                f"Même portions ajustées, ces menus restent environ {abs(round(ecart))} kcal "
                f"{sens} de ton objectif. Ajoute ou retire une collation selon le sens de "
                f"l'écart, plutôt que de déséquilibrer les repas principaux."
            )

    return {
        "menu": menu,
        "recettes_utilisees": sorted(utilisees.values(), key=lambda r: (r["moment"], r["nom"])),
        "kcal_objectif": kcal_objectif,
        "facteur_portions": round(facteur, 2),
        "avertissements": avertissements,
    }
