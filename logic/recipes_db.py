# -*- coding: utf-8 -*-
"""
Base de recettes du programme Alimentation.

Retour Samy : « je veux énormément plus de contenu, le plus de repas possible,
le plus de recettes possible. Les repas doivent être gourmands, healthy,
diététiques et adaptés aux objectifs. »

Chaque recette est une fiche exploitable par le moteur, pas un texte figé :

  id            : identifiant stable
  nom           : nom affiché
  moment        : "petit_dejeuner" | "dejeuner" | "diner" | "collation"
  kcal          : calories pour UNE portion
  proteines     : grammes de protéines par portion
  glucides      : grammes de glucides par portion
  lipides       : grammes de lipides par portion
  minutes       : temps de préparation total
  budget        : "serre" | "confortable"
  ingredients   : liste (quantités pour une portion)
  preparation   : étapes, en une phrase chacune
  tags          : contraintes satisfaites — "vegetarien", "vegan",
                  "sans_lactose", "sans_gluten"
  aliments      : mots-clés des ingrédients principaux, utilisés pour écarter
                  une recette si l'utilisateur déclare ne pas les aimer, et
                  pour privilégier celles qui contiennent ses aliments préférés
  objectifs     : objectifs pour lesquels la recette est particulièrement
                  adaptée ("prise_de_masse", "perte_de_gras", "maintien")
  gourmand      : True si la recette joue sur le plaisir (sucré, gratiné,
                  crémeux) tout en restant compatible avec l'objectif — c'est
                  la demande explicite « gourmands ET diététiques »

Les macros sont des ordres de grandeur pour une portion standard, arrondis.
Elles servent à composer une journée cohérente avec l'objectif calorique
calculé par `calculations.build_nutrition_profile`, pas à faire de la
diététique au gramme près.
"""

# Régimes : une recette sans tag de régime est omnivore.
VEGE = "vegetarien"
VEGAN = "vegan"
SANS_LACTOSE = "sans_lactose"
SANS_GLUTEN = "sans_gluten"

PRISE = "prise_de_masse"
PERTE = "perte_de_gras"
MAINTIEN = "maintien"


def _r(id, nom, moment, kcal, p, g, l, minutes, budget, ingredients,
       preparation, tags=(), aliments=(), objectifs=(), gourmand=False):
    return {
        "id": id, "nom": nom, "moment": moment,
        "kcal": kcal, "proteines": p, "glucides": g, "lipides": l,
        "minutes": minutes, "budget": budget,
        "ingredients": list(ingredients), "preparation": list(preparation),
        "tags": set(tags), "aliments": set(aliments),
        "objectifs": set(objectifs) or {MAINTIEN, PRISE, PERTE},
        "gourmand": gourmand,
    }


RECETTES = [

    # ================= PETITS DÉJEUNERS =================
    _r("pdj_porridge_choco", "Porridge chocolat-banane", "petit_dejeuner",
       480, 28, 62, 12, 8, "serre",
       ["60 g de flocons d'avoine", "250 ml de lait (ou boisson végétale)",
        "1 banane", "20 g de whey chocolat ou 10 g de cacao non sucré",
        "10 g de beurre de cacahuète", "cannelle"],
       ["Fais chauffer le lait avec les flocons d'avoine 4 à 5 minutes en remuant.",
        "Hors du feu, incorpore la whey ou le cacao pour éviter les grumeaux.",
        "Ajoute la banane écrasée, le beurre de cacahuète et la cannelle."],
       tags=[VEGE], aliments=["avoine", "banane", "lait", "cacahuete", "chocolat"],
       objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("pdj_omelette_feta", "Omelette épinards-feta", "petit_dejeuner",
       380, 30, 6, 26, 10, "confortable",
       ["3 œufs", "60 g d'épinards frais", "30 g de feta", "1 c. à c. d'huile d'olive", "poivre"],
       ["Fais tomber les épinards 2 minutes à la poêle avec l'huile.",
        "Verse les œufs battus, laisse prendre à feu doux.",
        "Émiette la feta dessus, plie l'omelette en deux."],
       tags=[VEGE, SANS_GLUTEN], aliments=["oeufs", "epinards", "feta", "fromage"],
       objectifs=[PERTE, MAINTIEN]),

    _r("pdj_skyr_bowl", "Bowl skyr, fruits rouges et granola maison", "petit_dejeuner",
       390, 32, 42, 10, 5, "confortable",
       ["250 g de skyr", "100 g de fruits rouges", "30 g de flocons d'avoine grillés",
        "10 g d'amandes concassées", "1 c. à c. de miel"],
       ["Fais griller les flocons d'avoine 3 minutes à sec dans une poêle.",
        "Mélange-les aux amandes et au miel, laisse refroidir.",
        "Dispose sur le skyr avec les fruits rouges."],
       tags=[VEGE, SANS_GLUTEN], aliments=["skyr", "fruits rouges", "amandes", "avoine"],
       objectifs=[PERTE, MAINTIEN], gourmand=True),

    _r("pdj_pancakes_proteines", "Pancakes protéinés banane-avoine", "petit_dejeuner",
       450, 34, 55, 11, 15, "serre",
       ["50 g de flocons d'avoine mixés", "1 banane", "2 œufs", "20 g de whey",
        "1/2 sachet de levure", "1 c. à c. d'huile de coco"],
       ["Mixe tous les ingrédients jusqu'à obtenir une pâte lisse.",
        "Cuis de petites louches 2 minutes par face à feu moyen.",
        "Sers avec un peu de fromage blanc ou des fruits frais."],
       tags=[VEGE], aliments=["avoine", "banane", "oeufs"],
       objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("pdj_tartines_avocat", "Tartines complètes avocat et œuf poché", "petit_dejeuner",
       420, 20, 38, 22, 12, "confortable",
       ["2 tranches de pain complet", "1/2 avocat", "2 œufs", "jus de citron", "piment doux"],
       ["Poche les œufs 3 minutes dans une eau frémissante vinaigrée.",
        "Écrase l'avocat avec le citron, étale sur les tartines grillées.",
        "Pose les œufs dessus, poivre et saupoudre de piment."],
       tags=[VEGE], aliments=["pain", "avocat", "oeufs"],
       objectifs=[MAINTIEN, PRISE]),

    _r("pdj_pudding_chia", "Pudding de chia coco-mangue", "petit_dejeuner",
       340, 14, 32, 17, 5, "confortable",
       ["30 g de graines de chia", "200 ml de boisson coco ou amande",
        "100 g de mangue", "1 c. à c. de sirop d'agave"],
       ["Mélange chia et boisson végétale, laisse au frais une nuit.",
        "Le matin, ajoute la mangue en dés et le sirop d'agave."],
       tags=[VEGE, VEGAN, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["chia", "coco", "mangue"], objectifs=[PERTE, MAINTIEN], gourmand=True),

    _r("pdj_oeufs_brouilles_saumon", "Œufs brouillés au saumon fumé", "petit_dejeuner",
       410, 34, 4, 28, 10, "confortable",
       ["3 œufs", "60 g de saumon fumé", "1 c. à c. de crème épaisse", "ciboulette"],
       ["Bats les œufs avec la crème, cuis à feu très doux en remuant sans arrêt.",
        "Retire du feu encore crémeux, ajoute le saumon en lamelles et la ciboulette."],
       tags=[SANS_GLUTEN], aliments=["oeufs", "saumon", "poisson"],
       objectifs=[PERTE, MAINTIEN], gourmand=True),

    _r("pdj_smoothie_vert", "Smoothie vert protéiné", "petit_dejeuner",
       330, 28, 34, 8, 5, "serre",
       ["1 banane", "60 g d'épinards", "25 g de whey vanille ou protéine végétale",
        "200 ml de boisson d'amande", "10 g de beurre d'amande"],
       ["Mixe tous les ingrédients 1 minute.",
        "Allonge avec un peu d'eau si la texture est trop épaisse."],
       tags=[VEGE, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["banane", "epinards", "amande"], objectifs=[PERTE, MAINTIEN]),

    # ================= DÉJEUNERS / DÎNERS =================
    _r("plat_poulet_patate_douce", "Poulet rôti et patate douce au four", "dejeuner",
       620, 48, 58, 18, 35, "serre",
       ["180 g de blanc de poulet", "250 g de patate douce", "1 c. à s. d'huile d'olive",
        "paprika fumé", "ail en poudre", "brocolis vapeur"],
       ["Coupe la patate douce en cubes, enrobe d'huile et d'épices.",
        "Enfourne 25 minutes à 200 °C, ajoute le poulet à mi-cuisson.",
        "Sers avec les brocolis vapeur."],
       tags=[SANS_GLUTEN, SANS_LACTOSE],
       aliments=["poulet", "patate douce", "brocolis"], objectifs=[PRISE, MAINTIEN]),

    _r("plat_dinde_riz_curry", "Sauté de dinde au curry et riz basmati", "dejeuner",
       590, 45, 62, 14, 25, "serre",
       ["180 g d'escalope de dinde", "80 g de riz basmati (poids sec)",
        "100 ml de lait de coco allégé", "1 c. à c. de curry", "poivrons", "oignon"],
       ["Fais revenir l'oignon et les poivrons 5 minutes.",
        "Ajoute la dinde en lanières, saisis 5 minutes.",
        "Verse le lait de coco et le curry, laisse mijoter 8 minutes.",
        "Sers sur le riz basmati."],
       tags=[SANS_GLUTEN, SANS_LACTOSE],
       aliments=["dinde", "riz", "coco", "poivrons"], objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("plat_saumon_quinoa", "Saumon rôti, quinoa et asperges", "diner",
       610, 42, 45, 26, 25, "confortable",
       ["160 g de pavé de saumon", "70 g de quinoa (poids sec)", "150 g d'asperges",
        "citron", "aneth", "1 c. à c. d'huile d'olive"],
       ["Cuis le quinoa 12 minutes dans deux fois son volume d'eau.",
        "Rôtis le saumon 12 minutes à 190 °C avec citron et aneth.",
        "Poêle les asperges 5 minutes, sers l'ensemble."],
       tags=[SANS_GLUTEN, SANS_LACTOSE],
       aliments=["saumon", "poisson", "quinoa", "asperges"], objectifs=[MAINTIEN, PERTE]),

    _r("plat_boeuf_pates", "Bœuf haché 5 %, pâtes complètes et sauce tomate maison", "dejeuner",
       650, 46, 70, 18, 25, "serre",
       ["150 g de bœuf haché à 5 %", "90 g de pâtes complètes (poids sec)",
        "200 g de coulis de tomate", "oignon", "ail", "origan", "basilic"],
       ["Fais revenir oignon et ail, ajoute le bœuf et saisis-le.",
        "Verse le coulis et les herbes, laisse réduire 12 minutes.",
        "Mélange aux pâtes égouttées."],
       tags=[SANS_LACTOSE], aliments=["boeuf", "viande rouge", "pates", "tomate"],
       objectifs=[PRISE, MAINTIEN]),

    _r("plat_cabillaud_ecrase", "Cabillaud et écrasé de pommes de terre à l'huile d'olive", "diner",
       520, 44, 48, 16, 30, "confortable",
       ["180 g de dos de cabillaud", "250 g de pommes de terre", "1 c. à s. d'huile d'olive",
        "ciboulette", "épinards"],
       ["Cuis les pommes de terre 20 minutes à l'eau, écrase-les à l'huile d'olive.",
        "Cuis le cabillaud 8 minutes à la vapeur ou au four.",
        "Sers avec les épinards tombés à la poêle."],
       tags=[SANS_GLUTEN, SANS_LACTOSE],
       aliments=["cabillaud", "poisson", "pommes de terre", "epinards"],
       objectifs=[PERTE, MAINTIEN]),

    _r("plat_chili_vegetarien", "Chili végétarien haricots rouges et patate douce", "diner",
       540, 26, 76, 14, 35, "serre",
       ["150 g de haricots rouges cuits", "200 g de patate douce", "200 g de tomates concassées",
        "1 oignon", "cumin", "paprika", "50 g de riz complet (poids sec)"],
       ["Fais revenir l'oignon et les épices 3 minutes.",
        "Ajoute la patate douce en cubes et les tomates, laisse mijoter 20 minutes.",
        "Incorpore les haricots rouges, poursuis 5 minutes, sers avec le riz."],
       tags=[VEGE, VEGAN, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["haricots", "legumineuses", "patate douce", "tomate", "riz"],
       objectifs=[MAINTIEN, PERTE], gourmand=True),

    _r("plat_dahl_lentilles", "Dahl de lentilles corail au lait de coco", "diner",
       510, 24, 68, 15, 30, "serre",
       ["120 g de lentilles corail (poids sec)", "150 ml de lait de coco allégé",
        "1 oignon", "gingembre", "curcuma", "épinards", "coriandre"],
       ["Fais revenir oignon, gingembre et épices 3 minutes.",
        "Ajoute les lentilles et 400 ml d'eau, cuis 18 minutes.",
        "Verse le lait de coco et les épinards, laisse fondre 3 minutes."],
       tags=[VEGE, VEGAN, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["lentilles", "legumineuses", "coco", "epinards"],
       objectifs=[MAINTIEN, PERTE], gourmand=True),

    _r("plat_wok_tofu", "Wok de tofu fumé, nouilles de sarrasin et légumes croquants", "dejeuner",
       560, 30, 66, 18, 20, "confortable",
       ["150 g de tofu fumé", "80 g de nouilles de sarrasin (poids sec)",
        "brocolis", "carottes", "sauce soja allégée", "sésame", "gingembre"],
       ["Saisis le tofu en cubes 5 minutes jusqu'à ce qu'il dore.",
        "Ajoute les légumes et le gingembre, fais sauter 6 minutes à feu vif.",
        "Mélange aux nouilles cuites, assaisonne à la sauce soja et au sésame."],
       tags=[VEGE, VEGAN, SANS_LACTOSE],
       aliments=["tofu", "soja", "brocolis", "carottes"], objectifs=[MAINTIEN, PERTE]),

    _r("plat_poulet_wrap", "Wrap de poulet grillé, crudités et sauce yaourt-citron", "dejeuner",
       520, 42, 48, 16, 15, "serre",
       ["150 g de blanc de poulet", "1 grande tortilla complète", "salade", "tomate", "concombre",
        "80 g de yaourt nature", "jus de citron", "ail en poudre"],
       ["Grille le poulet en lanières 8 minutes.",
        "Mélange le yaourt, le citron et l'ail pour la sauce.",
        "Garnis la tortilla de crudités, poulet et sauce, roule serré."],
       tags=[], aliments=["poulet", "yaourt", "salade", "tomate"],
       objectifs=[PERTE, MAINTIEN], gourmand=True),

    _r("plat_oeufs_shakshuka", "Shakshuka aux poivrons et pois chiches", "diner",
       470, 26, 42, 22, 25, "serre",
       ["3 œufs", "150 g de pois chiches cuits", "400 g de tomates concassées",
        "1 poivron", "oignon", "cumin", "paprika"],
       ["Fais revenir oignon et poivron 6 minutes, ajoute épices et tomates.",
        "Laisse réduire 10 minutes, incorpore les pois chiches.",
        "Casse les œufs dans la sauce, couvre et cuis 6 minutes."],
       tags=[VEGE, SANS_GLUTEN, SANS_LACTOSE],
       aliments=["oeufs", "pois chiches", "legumineuses", "tomate", "poivrons"],
       objectifs=[MAINTIEN, PERTE], gourmand=True),

    _r("plat_poulet_gratine", "Gratin de poulet, courgettes et ricotta", "diner",
       560, 48, 26, 30, 35, "confertable".replace("fert", "fort"),
       ["180 g de blanc de poulet", "2 courgettes", "100 g de ricotta",
        "30 g de parmesan", "ail", "basilic"],
       ["Poêle les courgettes en rondelles 8 minutes.",
        "Mélange ricotta, ail et basilic, alterne en couches avec poulet et courgettes.",
        "Parsème de parmesan, enfourne 20 minutes à 190 °C."],
       tags=[SANS_GLUTEN], aliments=["poulet", "courgettes", "ricotta", "fromage"],
       objectifs=[PERTE, MAINTIEN], gourmand=True),

    _r("plat_riz_saute_crevettes", "Riz sauté aux crevettes et petits pois", "dejeuner",
       540, 38, 68, 12, 20, "confortable",
       ["150 g de crevettes décortiquées", "80 g de riz (poids sec)", "100 g de petits pois",
        "1 œuf", "sauce soja allégée", "ciboule"],
       ["Cuis le riz la veille et laisse-le refroidir, c'est ce qui évite qu'il colle.",
        "Saisis les crevettes 3 minutes, réserve.",
        "Fais sauter le riz avec l'œuf brouillé et les petits pois, remets les crevettes."],
       tags=[SANS_LACTOSE], aliments=["crevettes", "fruits de mer", "riz", "petits pois"],
       objectifs=[PERTE, MAINTIEN]),

    _r("plat_steak_haricots", "Steak, haricots verts et pommes de terre sautées", "diner",
       580, 46, 44, 22, 25, "confortable",
       ["160 g de steak maigre", "200 g de haricots verts", "200 g de pommes de terre",
        "1 c. à s. d'huile d'olive", "ail", "persil"],
       ["Cuis les pommes de terre 15 minutes, puis fais-les sauter avec l'ail.",
        "Cuis les haricots verts 8 minutes à la vapeur.",
        "Saisis le steak 2 à 3 minutes par face selon la cuisson voulue."],
       tags=[SANS_GLUTEN, SANS_LACTOSE],
       aliments=["boeuf", "viande rouge", "haricots verts", "pommes de terre"],
       objectifs=[PRISE, MAINTIEN]),

    _r("plat_buddha_bowl", "Buddha bowl quinoa, pois chiches rôtis et houmous", "dejeuner",
       590, 24, 72, 22, 30, "serre",
       ["70 g de quinoa (poids sec)", "150 g de pois chiches", "carotte râpée",
        "chou rouge", "40 g de houmous", "graines de courge", "citron"],
       ["Rôtis les pois chiches 20 minutes à 200 °C avec paprika et huile.",
        "Cuis le quinoa, dresse tous les éléments côte à côte dans un bol.",
        "Ajoute le houmous et un filet de citron."],
       tags=[VEGE, VEGAN, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["quinoa", "pois chiches", "legumineuses", "houmous", "carottes"],
       objectifs=[MAINTIEN, PERTE], gourmand=True),

    _r("plat_poulet_pesto_pates", "Pâtes complètes, poulet et pesto léger", "dejeuner",
       630, 48, 66, 20, 20, "confortable",
       ["170 g de blanc de poulet", "90 g de pâtes complètes (poids sec)",
        "2 c. à c. de pesto", "tomates cerises", "roquette", "parmesan"],
       ["Cuis les pâtes al dente.",
        "Saisis le poulet en morceaux 8 minutes.",
        "Mélange le tout avec le pesto, ajoute tomates cerises et roquette hors du feu."],
       tags=[], aliments=["poulet", "pates", "pesto", "tomate", "fromage"],
       objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("plat_soupe_lentilles", "Soupe épaisse lentilles-légumes", "diner",
       420, 24, 58, 8, 30, "serre",
       ["120 g de lentilles vertes (poids sec)", "carottes", "poireau", "céleri",
        "bouillon de légumes", "thym", "laurier"],
       ["Fais revenir les légumes en dés 5 minutes.",
        "Ajoute les lentilles, le bouillon et les herbes, cuis 25 minutes.",
        "Mixe à moitié pour une texture épaisse."],
       tags=[VEGE, VEGAN, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["lentilles", "legumineuses", "carottes", "poireau"],
       objectifs=[PERTE, MAINTIEN]),

    _r("plat_omelette_pdt", "Tortilla espagnole pommes de terre-oignon", "diner",
       500, 26, 44, 24, 30, "serre",
       ["4 œufs", "250 g de pommes de terre", "1 oignon", "2 c. à s. d'huile d'olive"],
       ["Cuis doucement pommes de terre et oignon en fines lamelles 15 minutes.",
        "Mélange aux œufs battus, verse dans la poêle.",
        "Cuis 6 minutes à feu doux, retourne à l'aide d'une assiette, poursuis 4 minutes."],
       tags=[VEGE, SANS_GLUTEN, SANS_LACTOSE],
       aliments=["oeufs", "pommes de terre", "oignon"], objectifs=[MAINTIEN, PRISE]),

    _r("plat_thon_salade_pates", "Salade de pâtes au thon et légumes croquants", "dejeuner",
       540, 38, 62, 16, 15, "serre",
       ["1 boîte de thon au naturel", "90 g de pâtes (poids sec)", "tomates", "concombre",
        "maïs", "olives", "vinaigrette huile d'olive-citron"],
       ["Cuis les pâtes et rafraîchis-les à l'eau froide.",
        "Mélange avec le thon égoutté, les légumes et le maïs.",
        "Assaisonne à la vinaigrette juste avant de servir."],
       tags=[SANS_LACTOSE], aliments=["thon", "poisson", "pates", "tomate", "mais"],
       objectifs=[PERTE, MAINTIEN]),

    _r("plat_curry_pois_chiches", "Curry de pois chiches et épinards", "diner",
       520, 22, 66, 18, 25, "serre",
       ["200 g de pois chiches cuits", "150 ml de lait de coco allégé", "150 g d'épinards",
        "1 oignon", "curry", "gingembre", "60 g de riz (poids sec)"],
       ["Fais revenir oignon, gingembre et curry 3 minutes.",
        "Ajoute pois chiches et lait de coco, laisse mijoter 12 minutes.",
        "Incorpore les épinards en fin de cuisson, sers avec le riz."],
       tags=[VEGE, VEGAN, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["pois chiches", "legumineuses", "coco", "epinards", "riz"],
       objectifs=[MAINTIEN, PERTE], gourmand=True),

    _r("plat_poulet_teriyaki", "Poulet teriyaki maison et riz vinaigré", "dejeuner",
       600, 46, 70, 12, 25, "serre",
       ["180 g de blanc de poulet", "80 g de riz (poids sec)", "sauce soja allégée",
        "1 c. à c. de miel", "gingembre", "ail", "graines de sésame", "brocolis"],
       ["Mélange soja, miel, gingembre et ail pour la marinade.",
        "Saisis le poulet 8 minutes, ajoute la marinade et laisse caraméliser 3 minutes.",
        "Sers sur le riz avec les brocolis vapeur et le sésame."],
       tags=[SANS_LACTOSE], aliments=["poulet", "riz", "soja", "brocolis"],
       objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("plat_gratin_courgettes_thon", "Gratin de courgettes au thon", "diner",
       480, 40, 20, 26, 35, "serre",
       ["2 boîtes de thon au naturel", "3 courgettes", "2 œufs", "80 g de fromage blanc",
        "30 g de gruyère râpé", "herbes de Provence"],
       ["Poêle les courgettes en rondelles 10 minutes pour évacuer l'eau.",
        "Mélange œufs, fromage blanc, thon et herbes.",
        "Verse sur les courgettes, parsème de gruyère, enfourne 25 minutes à 180 °C."],
       tags=[SANS_GLUTEN], aliments=["thon", "poisson", "courgettes", "fromage"],
       objectifs=[PERTE, MAINTIEN], gourmand=True),

    _r("plat_boulettes_dinde", "Boulettes de dinde, semoule et légumes rôtis", "dejeuner",
       590, 46, 62, 16, 35, "serre",
       ["180 g de dinde hachée", "80 g de semoule complète (poids sec)", "courgette",
        "poivron", "oignon", "cumin", "coriandre"],
       ["Mélange la dinde avec l'oignon râpé et les épices, forme des boulettes.",
        "Rôtis-les 20 minutes à 200 °C avec les légumes en dés.",
        "Sers sur la semoule gonflée à l'eau bouillante."],
       tags=[SANS_LACTOSE], aliments=["dinde", "semoule", "courgettes", "poivrons"],
       objectifs=[PRISE, MAINTIEN]),

    _r("plat_poisson_blanc_ratatouille", "Poisson blanc et ratatouille maison", "diner",
       440, 40, 30, 16, 40, "serre",
       ["180 g de colin ou lieu", "aubergine", "courgette", "poivron", "tomates",
        "oignon", "ail", "herbes de Provence", "1 c. à s. d'huile d'olive"],
       ["Fais revenir séparément chaque légume en dés, puis réunis-les.",
        "Laisse mijoter 25 minutes avec ail et herbes.",
        "Cuis le poisson 8 minutes à la vapeur et sers-le sur la ratatouille."],
       tags=[SANS_GLUTEN, SANS_LACTOSE],
       aliments=["poisson", "aubergine", "courgettes", "poivrons", "tomate"],
       objectifs=[PERTE, MAINTIEN]),

    # ================= COLLATIONS =================
    _r("col_fromage_blanc_noix", "Fromage blanc, miel et noix", "collation",
       260, 24, 20, 10, 3, "serre",
       ["250 g de fromage blanc à 3 %", "1 c. à c. de miel", "15 g de noix"],
       ["Mélange le fromage blanc et le miel, ajoute les noix concassées."],
       tags=[VEGE, SANS_GLUTEN], aliments=["fromage blanc", "noix", "miel"],
       objectifs=[PERTE, MAINTIEN], gourmand=True),

    _r("col_shake_banane", "Shake protéiné banane-cacahuète", "collation",
       340, 30, 34, 10, 3, "serre",
       ["25 g de whey", "1 banane", "250 ml de lait ou boisson végétale",
        "10 g de beurre de cacahuète"],
       ["Mixe le tout 30 secondes."],
       tags=[VEGE], aliments=["banane", "cacahuete", "lait"],
       objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("col_energy_balls", "Energy balls dattes-amandes-cacao", "collation",
       220, 6, 26, 11, 15, "confortable",
       ["60 g de dattes dénoyautées", "30 g d'amandes", "10 g de cacao non sucré",
        "10 g de flocons d'avoine"],
       ["Mixe les dattes et les amandes jusqu'à obtenir une pâte collante.",
        "Ajoute cacao et avoine, forme des boules, réserve au frais 30 minutes."],
       tags=[VEGE, VEGAN, SANS_LACTOSE], aliments=["dattes", "amandes", "chocolat", "avoine"],
       objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("col_skyr_fruits", "Skyr et fruits frais", "collation",
       200, 26, 20, 1, 2, "confortable",
       ["200 g de skyr", "150 g de fruits de saison"],
       ["Coupe les fruits et mélange-les au skyr."],
       tags=[VEGE, SANS_GLUTEN], aliments=["skyr", "fruits"],
       objectifs=[PERTE, MAINTIEN]),

    _r("col_houmous_crudites", "Houmous et bâtonnets de légumes", "collation",
       230, 9, 22, 12, 10, "serre",
       ["60 g de houmous", "carottes", "concombre", "poivron"],
       ["Coupe les légumes en bâtonnets et sers avec le houmous."],
       tags=[VEGE, VEGAN, SANS_LACTOSE, SANS_GLUTEN],
       aliments=["houmous", "pois chiches", "carottes", "concombre"],
       objectifs=[PERTE, MAINTIEN]),

    _r("col_omelette_froide", "Muffins aux œufs et légumes (à préparer d'avance)", "collation",
       190, 16, 6, 12, 25, "serre",
       ["3 œufs", "poivron", "épinards", "20 g de fromage râpé"],
       ["Bats les œufs avec les légumes émincés et le fromage.",
        "Répartis dans des moules à muffins, enfourne 18 minutes à 180 °C.",
        "Se conserve 3 jours au frais, parfait à emporter."],
       tags=[VEGE, SANS_GLUTEN], aliments=["oeufs", "poivrons", "epinards", "fromage"],
       objectifs=[PERTE, MAINTIEN]),

    _r("col_pain_complet_amande", "Tartines de pain complet au beurre d'amande et banane", "collation",
       310, 10, 42, 12, 3, "serre",
       ["2 tranches de pain complet", "20 g de beurre d'amande", "1 banane", "cannelle"],
       ["Étale le beurre d'amande, dispose les rondelles de banane et saupoudre de cannelle."],
       tags=[VEGE, VEGAN, SANS_LACTOSE], aliments=["pain", "amande", "banane"],
       objectifs=[PRISE, MAINTIEN], gourmand=True),

    _r("col_cottage_ananas", "Cottage cheese et ananas frais", "collation",
       210, 22, 18, 5, 3, "confortable",
       ["200 g de cottage cheese", "120 g d'ananas frais"],
       ["Mélange le cottage cheese et l'ananas coupé en dés."],
       tags=[VEGE, SANS_GLUTEN], aliments=["cottage", "fromage", "ananas"],
       objectifs=[PERTE, MAINTIEN]),
]


MOMENTS = ("petit_dejeuner", "dejeuner", "diner", "collation")

MOMENT_LABELS = {
    "petit_dejeuner": "Petit-déjeuner",
    "dejeuner": "Déjeuner",
    "diner": "Dîner",
    "collation": "Collation",
}

# Une recette de "déjeuner" convient parfaitement le soir et inversement : on
# les considère interchangeables pour ne pas appauvrir artificiellement le
# choix (sinon 12 plats de midi et 10 du soir, au lieu de 22 pour les deux).
MOMENTS_INTERCHANGEABLES = {"dejeuner", "diner"}


def recettes_par_moment(moment):
    if moment in MOMENTS_INTERCHANGEABLES:
        return [r for r in RECETTES if r["moment"] in MOMENTS_INTERCHANGEABLES]
    return [r for r in RECETTES if r["moment"] == moment]
