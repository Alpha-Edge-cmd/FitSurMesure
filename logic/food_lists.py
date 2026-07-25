# -*- coding: utf-8 -*-
"""
Listes d'aliments concrètes par catégorie, adaptées à la restriction
alimentaire déclarée et aux préférences/aversions de l'utilisateur, plus une
liste d'aliments à limiter selon l'objectif.
"""

FECULENTS = ["riz (blanc ou complet)", "pâtes complètes", "pommes de terre", "patate douce", "avoine",
             "quinoa", "pain complet", "sarrasin", "boulgour", "semoule complète", "légumineuses en accompagnement (lentilles, pois chiches)",
             "flocons d'avoine", "riz basmati", "maïs"]
FECULENTS_SANS_GLUTEN = ["riz (blanc ou complet)", "pommes de terre", "patate douce", "quinoa", "sarrasin",
                         "pâtes sans gluten", "pain sans gluten", "polenta", "maïs", "flocons d'avoine sans gluten"]

PROTEINES_ANIMALES = ["poulet", "dinde", "bœuf maigre", "porc (filet, longe)", "poisson blanc (cabillaud, colin, lieu)",
                       "poisson gras (saumon, maquereau, sardines, thon)", "fruits de mer (crevettes, moules)",
                       "œufs", "fromage blanc / skyr", "jambon blanc dégraissé", "viande hachée à 5%"]
PROTEINES_VEGETALES = ["lentilles (vertes, corail)", "pois chiches", "haricots rouges", "haricots blancs",
                       "tofu", "tofu fumé", "tempeh", "seitan", "edamame", "protéine de soja texturée",
                       "levure maltée (topping riche en protéines)"]

LEGUMES = ["brocolis", "épinards", "courgettes", "poivrons", "carottes", "champignons", "oignons",
           "haricots verts", "chou-fleur", "tomates", "aubergines", "salade verte", "concombre",
           "chou kale", "asperges", "petits pois", "poireaux", "endives", "radis", "betterave"]

FRUITS = ["pommes", "bananes", "fruits rouges (fraises, myrtilles, framboises)", "agrumes (orange, pamplemousse, mandarine)",
          "kiwi", "poires", "ananas", "mangue", "raisin", "pêches / nectarines", "fruits secs (abricots, dattes) avec modération"]

BONNES_GRAISSES = ["huile d'olive", "huile de colza", "avocat", "amandes", "noix", "noix de cajou",
                   "graines de chia", "graines de lin moulues", "beurre de cacahuète (100% cacahuète)",
                   "beurre d'amande", "olives"]

PRODUITS_LAITIERS = ["lait", "yaourt nature", "yaourt grec", "fromage blanc", "skyr", "fromage (à raisonner en quantité)", "petit-suisse", "cottage cheese"]
ALTERNATIVES_SANS_LACTOSE = ["lait sans lactose", "fromage sans lactose", "boisson d'amande",
                             "boisson d'avoine", "boisson de soja", "yaourt de soja", "yaourt de coco", "fromage végétal"]

SAUCES_CONDIMENTS = ["moutarde", "vinaigre balsamique ou de cidre", "jus de citron", "herbes de Provence, thym, basilic",
                     "ail et oignon (frais ou en poudre)", "épices variées (paprika, cumin, curry, piment)",
                     "sauce soja allégée en sel", "yaourt nature + citron + herbes (façon tzatziki)",
                     "salsa maison tomate-oignon-coriandre", "houmous (en petite quantité, compte en apport calorique)",
                     "sauce piquante type sriracha (avec modération)", "vinaigrette maison huile d'olive + moutarde + vinaigre"]

A_LIMITER_BASE = ["ultra-transformé en excès (plats préparés, biscuits industriels)"]
A_LIMITER_OBJECTIF = {
    "Perte de gras": ["sodas et boissons sucrées", "fritures", "viennoiseries", "alcool", "fast-food fréquent"],
    "Prise de muscle": ["alcool (freine la synthèse protéique)", "sucres rapides en dehors de l'entraînement"],
    "Recomposition (sec + muscle)": ["sucres ajoutés en excès", "alcool", "fritures"],
    "Performance / explosivité": ["alcool (nuit à la récupération)", "sucres rapides hors fenêtre d'entraînement"],
    "Condition physique générale": ["ultra-transformé fréquent", "excès de sucres ajoutés"],
}


def _filter_out(items, aliments_non_apprecies):
    if not aliments_non_apprecies:
        return items
    dislikes = [d.strip().lower() for d in aliments_non_apprecies.replace(";", ",").split(",") if d.strip()]
    if not dislikes:
        return items
    filtered = []
    for item in items:
        item_lower = item.lower()
        if any(d in item_lower for d in dislikes):
            continue
        filtered.append(item)
    return filtered


def get_food_recommendations(restriction_alimentaire, aliments_non_apprecies, aliments_apprecies, objectif_principal):
    restriction_alimentaire = restriction_alimentaire or "Aucune"
    aliments_apprecies = aliments_apprecies or []

    feculents = FECULENTS_SANS_GLUTEN if restriction_alimentaire == "Sans gluten" else FECULENTS

    proteines = []
    if restriction_alimentaire == "Végan":
        proteines = list(PROTEINES_VEGETALES)
    elif restriction_alimentaire == "Végétarien":
        proteines = ["œufs", "fromage blanc / skyr"] + PROTEINES_VEGETALES
    else:
        proteines = list(PROTEINES_ANIMALES) + PROTEINES_VEGETALES

    # priorise les catégories appréciées si renseignées
    priority_map = {
        "Viande rouge": "bœuf maigre", "Volaille": "poulet", "Poisson": "poisson",
        "Œufs": "œufs", "Légumineuses": "lentilles", "Produits laitiers": "fromage",
        "Fruits à coque": "amandes",
    }
    preferred_keywords = [priority_map[c] for c in aliments_apprecies if c in priority_map]
    if preferred_keywords:
        def score(item):
            return 0 if any(k in item.lower() for k in preferred_keywords) else 1
        proteines = sorted(proteines, key=score)

    laitiers = ALTERNATIVES_SANS_LACTOSE if restriction_alimentaire in ("Sans lactose", "Végan") else PRODUITS_LAITIERS
    if restriction_alimentaire == "Végan" and laitiers is PRODUITS_LAITIERS:
        laitiers = ALTERNATIVES_SANS_LACTOSE

    categories = [
        ("Féculents", feculents),
        ("Sources de protéines", proteines),
        ("Légumes", LEGUMES),
        ("Fruits", FRUITS),
        ("Bonnes graisses", BONNES_GRAISSES),
        ("Produits laitiers / alternatives", laitiers),
        ("Sauces, condiments et épices (pour ne pas manger fade)", SAUCES_CONDIMENTS),
    ]

    categories = [(nom, _filter_out(items, aliments_non_apprecies)) for nom, items in categories]

    a_limiter = A_LIMITER_BASE + A_LIMITER_OBJECTIF.get(objectif_principal, [])

    return {
        "categories": [{"nom": nom, "aliments": items} for nom, items in categories if items],
        "a_limiter": a_limiter,
    }
