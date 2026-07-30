# -*- coding: utf-8 -*-
"""
Génère le PDF final (alimentation / musculation / cardio / conseils) à partir
des données calculées par calculations.py, program_builder.py et cardio_builder.py.
"""
import hashlib

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from . import cardio_zones
from .recipes_db import MOMENT_LABELS
from .supplements import recommend_supplements
from .food_lists import get_food_recommendations
from .exercises_db import MUSCLE_LABELS


# Trois "styles" de repas selon l'objectif : léger (perte de gras), généreux (prise de
# muscle), équilibré (le reste). Plusieurs variantes par repas pour éviter la répétition,
# la variante retenue pour chaque personne dépend de sa signature (stable pour elle,
# différente d'une personne à l'autre).
MEAL_TEMPLATES = {
    "leger": {
        "Petit-déjeuner": [
            "{laitier} nature avec {fruit} frais et une pointe de {graisse} concassées.",
            "Omelette légère aux {legumes} (2 œufs), un {fruit} à côté.",
            "Fromage blanc ou skyr, {fruit} coupé en morceaux, une pointe de cannelle.",
        ],
        "Déjeuner": [
            "{proteine} grillée, {legumes} rôtis au four, assaisonnés de {sauce}.",
            "Grande salade de {legumes} et {proteine}, {sauce} en vinaigrette maison, un peu de {feculent}.",
            "{proteine} poêlée sans matière grasse, poêlée de {legumes}, {sauce} pour relever.",
        ],
        "Dîner": [
            "{proteine} vapeur, {legumes} à volonté, {sauce} pour ne pas manger fade, féculent en toute "
            "petite quantité ce soir.",
            "Soupe maison de {legumes}, {proteine} froide ou grillée à côté.",
            "{proteine} et {legumes} sautés au wok, {sauce}, sans féculent ce soir.",
        ],
    },
    "genereux": {
        "Petit-déjeuner": [
            "{feculent} au lait, {fruit} coupé, un filet de miel.",
            "Pain complet grillé, {proteine} et {graisse} écrasées dessus, {fruit} en dessert.",
            "Porridge de {feculent}, {laitier}, {fruit}, une poignée de {graisse}.",
        ],
        "Déjeuner": [
            "{proteine} mijotée, {feculent} en portion généreuse, {legumes} sautés à {graisse}, {sauce}.",
            "{feculent} façon risotto ou pâtes avec {proteine} et {legumes}, un peu de {laitier} râpé.",
            "{proteine}, double portion de {feculent}, {legumes}, {sauce} maison.",
        ],
        "Dîner": [
            "{proteine}, {feculent}, {legumes}, {sauce}, {laitier} râpé en topping.",
            "{proteine} au four avec {feculent} rôti et {legumes}, filet de {graisse}.",
            "{feculent} type riz complet ou quinoa, {proteine}, {legumes}, {sauce}.",
        ],
    },
    "equilibre": {
        "Petit-déjeuner": [
            "{laitier} avec {feculent} façon granola maison et {fruit}.",
            "Œufs brouillés, tranche de pain complet, {fruit} frais.",
            "{feculent} (flocons d'avoine) au lait, {fruit}, {graisse} en topping.",
        ],
        "Déjeuner": [
            "{proteine} poêlée avec {sauce}, {feculent}, {legumes} vapeur, filet de {graisse}.",
            "Bowl composé : {feculent}, {proteine}, {legumes} croquants, {sauce}, {graisse}.",
            "{proteine}, {feculent}, {legumes} rôtis, {sauce} maison.",
        ],
        "Dîner": [
            "{proteine} au four avec {legumes} et {sauce}, {feculent} en quantité modérée.",
            "{proteine} grillée, {legumes} poêlés à {graisse}, un peu de {feculent}.",
            "{legumes} et {proteine} en wok, {sauce}, {feculent} léger.",
        ],
    },
}

MEAL_STYLE_NOTES = {
    "leger": ("Vu ton objectif de perte de gras, ces exemples restent riches en protéines et légumes, "
              "avec des féculents plus discrets — surtout au dîner."),
    "genereux": ("Vu ton objectif de prise de muscle, ces exemples sont plus généreux en féculents et "
                 "calories pour t'aider à manger en surplus sans forcer."),
    "equilibre": ("Ces exemples visent un équilibre standard entre protéines, féculents et légumes, "
                  "adapté à ton objectif actuel."),
}


def _meal_style(objectif_principal):
    if objectif_principal == "Perte de gras":
        return "leger"
    if objectif_principal == "Prise de muscle":
        return "genereux"
    return "equilibre"


def _cat(categories, nom):
    for c in categories:
        if c["nom"] == nom:
            return c["aliments"]
    return []


def _pick(items, seed, offset=0, fallback="", n=1):
    """Choisit un ou plusieurs éléments d'une liste à partir d'un seed déterministe,
    pour que la sélection varie d'une personne à l'autre sans être aléatoire."""
    if not items:
        return fallback
    idx = (seed + offset) % len(items)
    n = min(n, len(items))
    chosen = [items[(idx + k) % len(items)] for k in range(n)]
    return ", ".join(chosen)


def _meal_examples(food, objectif_principal="", signature=""):
    """Construit 3 exemples de repas concrets, variés et adaptés à l'objectif, à partir
    des catégories déjà filtrées (restriction alimentaire, aversions, préférences prises
    en compte en amont). La variante de recette et les aliments piochés dépendent de la
    signature de la personne, pour éviter que tout le monde ait exactement les mêmes
    suggestions."""
    categories = food["categories"]
    feculent = _cat(categories, "Féculents")
    proteine = _cat(categories, "Sources de protéines")
    legumes = _cat(categories, "Légumes")
    graisse = _cat(categories, "Bonnes graisses")
    fruit = _cat(categories, "Fruits")
    laitier = _cat(categories, "Produits laitiers / alternatives")
    sauce = _cat(categories, "Sauces, condiments et épices (pour ne pas manger fade)")

    style = _meal_style(objectif_principal)
    templates = MEAL_TEMPLATES[style]
    seed_base = int(hashlib.md5((signature or "defaut").encode("utf-8")).hexdigest(), 16)

    resultats = []
    for i, nom_repas in enumerate(["Petit-déjeuner", "Déjeuner", "Dîner"]):
        options = templates[nom_repas]
        seed = seed_base + i * 37
        tpl = options[seed % len(options)]
        contenu = tpl.format(
            feculent=_pick(feculent, seed, offset=1, fallback="un féculent au choix"),
            proteine=_pick(proteine, seed, offset=2, fallback="une source de protéines au choix"),
            legumes=_pick(legumes, seed, offset=3, fallback="des légumes de saison", n=2),
            graisse=_pick(graisse, seed, offset=4, fallback="une bonne graisse (huile d'olive, oléagineux...)"),
            fruit=_pick(fruit, seed, offset=5, fallback="un fruit de saison"),
            laitier=_pick(laitier, seed, offset=6, fallback="un produit laitier ou une alternative"),
            sauce=_pick(sauce, seed, offset=7, fallback="des épices ou une sauce légère au choix"),
        )
        if contenu:
            contenu = contenu[0].upper() + contenu[1:]
        resultats.append((nom_repas, contenu))
    return resultats, MEAL_STYLE_NOTES[style]

NAVY = colors.HexColor("#1b2a4a")
BLUE = colors.HexColor("#2e5aac")
LIGHT_BLUE = colors.HexColor("#eaf0fb")
GREY = colors.HexColor("#555555")
RED = colors.HexColor("#a32d2d")
LIGHT_RED = colors.HexColor("#fcebeb")
TEAL = colors.HexColor("#0f6e56")
LIGHT_TEAL = colors.HexColor("#e1f5ee")

_styles = getSampleStyleSheet()

title_style = ParagraphStyle("TitleCustom", parent=_styles["Title"], fontSize=24,
                              textColor=NAVY, spaceAfter=4, alignment=TA_CENTER)
subtitle_style = ParagraphStyle("SubtitleCustom", parent=_styles["Normal"], fontSize=12,
                                 textColor=GREY, alignment=TA_CENTER, spaceAfter=20)
section_style = ParagraphStyle("Section", parent=_styles["Heading1"], fontSize=17,
                                textColor=colors.white, backColor=NAVY,
                                spaceBefore=0, spaceAfter=14, leftIndent=8,
                                borderPadding=(8, 8, 8, 8))
h2_style = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=13,
                           textColor=BLUE, spaceBefore=14, spaceAfter=6)
h3_style = ParagraphStyle("H3", parent=_styles["Heading3"], fontSize=11,
                           textColor=NAVY, spaceBefore=8, spaceAfter=4,
                           fontName="Helvetica-Bold")
body_style = ParagraphStyle("Body", parent=_styles["Normal"], fontSize=10,
                             leading=14, spaceAfter=6, alignment=TA_LEFT)
bullet_style = ParagraphStyle("Bullet", parent=_styles["Normal"], fontSize=10,
                               leading=14, spaceAfter=4, leftIndent=12)
note_style = ParagraphStyle("Note", parent=_styles["Normal"], fontSize=9,
                             leading=12, textColor=GREY, spaceAfter=6,
                             fontName="Helvetica-Oblique")
warn_style = ParagraphStyle("Warn", parent=_styles["Normal"], fontSize=9.5,
                             leading=13, textColor=RED, spaceAfter=4)

# Styles dédiés aux cellules de tableau. IMPORTANT : toute cellule de Table doit
# passer par un Paragraph plutôt qu'une chaîne brute. Une chaîne brute dans une
# Table reportlab n'est pas fiablement renvoyée à la ligne selon la largeur de
# colonne — sur les textes longs (protocole cardio, valeurs du tableau de profil),
# ça peut déborder du tableau ou chevaucher la cellule voisine. Le Paragraph, lui,
# calcule un retour à la ligne correct et une hauteur de ligne cohérente.
cell_style = ParagraphStyle("Cell", parent=_styles["Normal"], fontSize=9.5,
                             leading=12, spaceAfter=0, alignment=TA_LEFT)
cell_style_bold = ParagraphStyle("CellBold", parent=cell_style, fontName="Helvetica-Bold",
                                  textColor=NAVY)
cardio_cell_style = ParagraphStyle("CardioCell", parent=_styles["Normal"], fontSize=9,
                                    leading=11.5, spaceAfter=0, alignment=TA_LEFT)


def _p(text, style=body_style):
    return Paragraph(text, style)


def _bullet(text):
    return Paragraph("• " + text, bullet_style)


def _cell(text, style=cell_style):
    return Paragraph(str(text), style)


CONSEIL_EXECUTION_STYLE = ParagraphStyle("ConseilExecution", parent=cell_style, fontSize=8,
                                          leading=10, textColor=colors.HexColor("#555555"))


def _nom_avec_conseil(nom, conseil, portion=None):
    """Cellule "Exercice" : nom + (optionnel) sous-ligne "Muscle ciblé : ..."
    explicitant la portion anatomique travaillée + (optionnel) conseil
    d'exécution en sous-ligne plus petite/grisée, dans le MÊME Paragraph que
    le nom (pas de colonne/ligne supplémentaire dans le tableau) — pour ne
    pas retoucher la structure de `_exo_table` (déjà corrigée pour des bugs
    de chevauchement de texte, cf. historique du projet). Additif (prompt
    hors 24 phases, conseils d'exécution puis portion musculaire, retour
    Samy) : absents -> comportement strictement inchangé."""
    if not conseil and not portion:
        return _cell(nom)
    from xml.sax.saxutils import escape
    texte = f"<b>{escape(str(nom))}</b>"
    if portion:
        # Retour Samy (prompt hors 24 phases, réitéré : "n'oublie pas de dire
        # quelle partie du muscle l'exercice travaille") : sous-ligne dédiée
        # et explicite ("Muscle ciblé : ...") plutôt qu'un simple ajout entre
        # parenthèses juste après le nom, facile à ne pas remarquer.
        texte += f"<br/><font size=8 color='#2e5aac'>Muscle ciblé : {escape(str(portion))}</font>"
    if conseil:
        texte += f"<br/><font size=8 color='#555555'><i>{escape(str(conseil))}</i></font>"
    return Paragraph(texte, cell_style)


def _exo_table(rows):
    data = [["Exercice", "Séries x Répétitions"]] + [
        [(cell_nom if isinstance(cell_nom, Paragraph) else _cell(cell_nom)), _cell(reps)]
        for cell_nom, reps in rows
    ]
    t = Table(data, colWidths=[10.5 * cm, 4.5 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _cardio_table(rows):
    data = [["Séance", "Discipline", "Type", "Protocole"]] + [
        [_cell(c, cardio_cell_style) for c in row] for row in rows
    ]
    t = Table(data, colWidths=[2.6 * cm, 2.4 * cm, 3 * cm, 7 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_TEAL]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _build_blocked_pdf(story, profile, nutrition):
    story.append(Spacer(1, 3 * cm))
    story.append(_p("PROGRAMME PERSONNALISÉ", title_style))
    story.append(Spacer(1, 1 * cm))
    for msg in nutrition["messages"]:
        story.append(Table([[Paragraph(msg, ParagraphStyle("msg", parent=body_style, textColor=RED, fontSize=11))]],
                            colWidths=[15.5 * cm],
                            style=TableStyle([
                                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_RED),
                                ("BOX", (0, 0), (-1, -1), 0.5, RED),
                                ("TOPPADDING", (0, 0), (-1, -1), 12),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                            ])))
        story.append(Spacer(1, 0.5 * cm))


def generate_pdf(output, profile, nutrition, program, cardio, lifestyle, include_nutrition=True,
                 menu_semaine=None):
    """
    output      : chemin fichier ou objet BytesIO
    profile     : dict prenom, sexe, poids, taille, age, niveau_musculation, objectif_principal
    nutrition   : résultat de calculations.build_nutrition_profile
    program     : résultat de program_builder.build_program (ou None si nutrition bloquée)
    cardio      : résultat de cardio_builder.build_cardio_program (ou None)
    lifestyle   : dict restriction_alimentaire, aliments_non_apprecies, repas_par_jour,
                  sommeil, tabac, cannabis, alcool, complements, blessures, exercices_incapables,
                  condition_medicale, cardio_type, cardio_frequence, precisions,
                  autre_sport, autre_sport_type, autre_sport_sessions
    include_nutrition : bool (par défaut True, rétrocompatible avec tout appelant
                  existant -- scripts/production_check.py notamment) -- retour
                  Samy (prompt hors 24 phases) : "dans le programme musculation
                  seul ne mets pas de programme alimentation et dans le
                  programme cardio pareil". `app.py` passe désormais False pour
                  les formules "musculation" et "cardio" (seules), True pour
                  "nutrition" (nouvelle offre), "les_deux" et "abonnement".
                  N'affecte QUE la partie 1 (Alimentation) ; le calcul
                  `nutrition` lui-même reste toujours fait en amont (BMR/TDEE
                  utilisés ailleurs -- âge affiché en page de garde, sécurité
                  grossesse/condition médicale -- même si cette partie n'est
                  pas imprimée).
    """
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        title="Programme personnalisé - Alimentation, Musculation, Cardio, Conseils",
    )
    story = []
    prenom = profile.get("prenom") or "toi"

    if nutrition.get("blocked"):
        _build_blocked_pdf(story, profile, nutrition)
        doc.build(story)
        return

    # ---------------- PAGE DE GARDE ----------------
    story.append(Spacer(1, 2.5 * cm))
    story.append(_p("PROGRAMME PERSONNALISÉ", title_style))
    sections_incluses = (["Alimentation"] if include_nutrition else []) + \
                        (["Musculation"] if program else []) + \
                        (["Cardio"] if cardio else []) + ["Conseils"]
    story.append(_p(" • ".join(sections_incluses), subtitle_style))
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE))
    story.append(Spacer(1, 0.5 * cm))

    profil_rows = [
        ["Prénom", prenom],
        ["Âge", f"{nutrition['age']} ans"],
        ["Poids", f"{profile['poids']} kg"],
        ["Taille", f"{profile['taille']} cm"],
        ["Sexe", profile["sexe"]],
        ["Niveau", profile["niveau_musculation"]],
    ]
    if program:
        profil_rows.append(["Fréquence musculation", f"{profile['frequence_entrainement']}x / semaine"])
    if cardio:
        profil_rows.append(["Fréquence cardio", f"{cardio['nb_sessions']}x / semaine"])
    profil_rows.append(["Objectif", profile["objectif_principal"]])
    profil_rows.append(["Programme musculation", program["split_label"] if program else "— (non inclus dans ta formule)"])
    profil_rows_wrapped = [[_cell(label, cell_style_bold), _cell(value)] for label, value in profil_rows]
    t = Table(profil_rows_wrapped, colWidths=[5 * cm, 10 * cm])
    t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#dddddd")),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
    ]))
    story.append(t)

    if include_nutrition and nutrition["warnings"]:
        story.append(Spacer(1, 0.5 * cm))
        for w in nutrition["warnings"]:
            story.append(_p("⚠ " + w, warn_style))

    story.append(PageBreak())

    if include_nutrition:
        # ================= 1. ALIMENTATION =================
        story.append(_p("1. PARTIE ALIMENTAIRE", section_style))

        story.append(_p("Calcul du métabolisme de base (formule de Mifflin-St Jeor)", h2_style))
        signe = "+" if profile["sexe"] == "Homme" else "-"
        story.append(_p(f"BMR = 10 × poids(kg) + 6,25 × taille(cm) − 5 × âge(ans) {signe} "
                         f"{'5' if profile['sexe']=='Homme' else '161'}"))
        story.append(_p(f"BMR = <b>{nutrition['bmr']} kcal</b>"))

        story.append(_p("Besoin énergétique journalier (TDEE)", h2_style))
        story.append(_p(f"TDEE = BMR × facteur d'activité ({nutrition['facteur_activite']}, combinant ton "
                         f"activité quotidienne, ta fréquence d'entraînement, ton cardio et un éventuel "
                         f"autre sport)"))
        story.append(_p(f"TDEE = <b>{nutrition['tdee']} kcal/jour</b> (maintien du poids actuel)"))
        story.append(_p(f"IMC actuel : <b>{nutrition['imc']}</b>"))

        story.append(_p("Objectif calorique", h2_style))
        ajustement = nutrition["ajustement_kcal"]
        sens = "déficit" if ajustement < 0 else ("surplus" if ajustement > 0 else "maintien")
        story.append(_p(f"Objectif « {profile['objectif_principal']} » → {sens} de {abs(ajustement)} kcal "
                         f"par rapport au TDEE."))
        story.append(_p(f"Ton IMC actuel ({nutrition['imc']}) te place dans la catégorie "
                         f"<b>{nutrition['imc_categorie']}</b> — ça a orienté le calcul ci-dessus."))

        # Retour Samy (prompt hors 24 phases : "ajoutes combien tu mets par poids
        # de corps exactement") : 3e colonne explicite en g/kg de poids de corps
        # (cf. logic/calculations.py, `macros()` -> `*_g_par_kg`), plutôt que de
        # laisser ce calcul invisible derrière le total en grammes.
        macro_data = [
            ["", "Quantité", "g / kg de poids de corps"],
            ["Objectif calorique", f"≈ {nutrition['kcal_objectif']} kcal / jour", "—"],
            ["Protéines", f"{nutrition['proteines_g']} g", f"{nutrition['proteines_g_par_kg']:.1f} g/kg"],
            ["Lipides", f"{nutrition['lipides_g']} g", f"{nutrition['lipides_g_par_kg']:.1f} g/kg"],
            ["Glucides", f"{nutrition['glucides_g']} g", f"{nutrition['glucides_g_par_kg']:.1f} g/kg"],
        ]
        macro_table = Table(macro_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
        macro_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (1, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (0, -1), NAVY),
            ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
            ("BACKGROUND", (1, 1), (-1, -1), LIGHT_BLUE),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
        ]))
        story.append(Spacer(1, 4))
        story.append(macro_table)
        story.append(Spacer(1, 4))

        poids_min_valide = round(profile["poids"] * 0.95)
        poids_max_valide = round(profile["poids"] * 1.05)
        story.append(_p(f"Ces valeurs sont calculées pour ton poids actuel ({profile['poids']} kg) et restent "
                         f"fiables tant que celui-ci reste entre <b>{poids_min_valide} et {poids_max_valide} kg</b> "
                         f"environ (± 5%), et pour les <b>6 à 8 prochaines semaines</b> à peu près — au-delà, ton "
                         f"métabolisme de base et tes besoins caloriques changent avec le poids, il faut "
                         f"recalculer un nouveau programme.", note_style))
        story.append(Spacer(1, 6))

        # Retour Samy (prompt hors 24 phases : "pourquoi tu as choisi ça") :
        # justification explicite du g/kg retenu pour CE profil précis (objectif/
        # niveau pour les protéines, bornes de sécurité pour les lipides,
        # enveloppe calorique restante pour les glucides) — cf. `_justification_*`
        # dans logic/calculations.py, jamais recalculées ici (une seule source de
        # vérité pour cette logique).
        story.append(_p("Pourquoi ces quantités précisément", h2_style))
        story.append(_bullet(f"<b>Protéines</b> : {nutrition['proteines_justification']}"))
        story.append(_bullet(f"<b>Lipides</b> : {nutrition['lipides_justification']}"))
        story.append(_bullet(f"<b>Glucides</b> : {nutrition['glucides_justification']}"))
        story.append(Spacer(1, 6))

        story.append(_p("À quoi servent tes macronutriments, et où les trouver", h2_style))
        story.append(_bullet("<b>Protéines</b> : réparent et construisent le muscle après l'entraînement, "
                              "et rassasient bien. On les trouve dans la viande, le poisson, les œufs, les "
                              "produits laitiers, ainsi que dans le tofu, les légumineuses (lentilles, pois "
                              "chiches) et le seitan côté végétal."))
        story.append(_bullet("<b>Glucides</b> : ta principale source d'énergie, en particulier pour "
                              "l'intensité en musculation et en cardio ; ils rechargent aussi les réserves "
                              "musculaires (glycogène). On les trouve dans le riz, les pâtes, le pain, "
                              "l'avoine, la patate douce, les légumineuses, mais aussi les fruits et légumes."))
        story.append(_bullet("<b>Lipides</b> : indispensables à la production hormonale (dont la "
                              "testostérone) et à l'absorption de certaines vitamines. On les trouve dans "
                              "l'huile d'olive, l'avocat, les oléagineux (amandes, noix), les poissons gras, "
                              "et en plus petite quantité dans les œufs et les produits laitiers."))
        story.append(_p("Ne cherche pas à supprimer une catégorie : les trois sont nécessaires, seules les "
                         "quantités changent selon ton objectif.", note_style))

        story.append(_p("Aliments recommandés, par catégorie", h2_style))
        food = get_food_recommendations(
            lifestyle.get("restriction_alimentaire"),
            lifestyle.get("aliments_non_apprecies"),
            lifestyle.get("aliments_apprecies"),
            profile["objectif_principal"],
        )
        if lifestyle.get("restriction_alimentaire") and lifestyle["restriction_alimentaire"] != "Aucune":
            story.append(_p(f"Adapté à ta restriction déclarée : <b>{lifestyle['restriction_alimentaire']}</b>.",
                             note_style))
        if lifestyle.get("restriction_alimentaire") == "Allergie" and lifestyle.get("allergie_details"):
            story.append(_p(f"⚠ Allergie déclarée : <b>{lifestyle['allergie_details']}</b> — vérifie "
                             f"systématiquement les étiquettes (y compris les mentions de traces éventuelles) "
                             f"avant de consommer un produit nouveau.", warn_style))
        for cat in food["categories"]:
            story.append(KeepTogether([
                _p(cat["nom"], h3_style),
                _p(", ".join(cat["aliments"]) + "."),
            ]))

        story.append(_p("Aliments à limiter", h3_style))
        story.append(_p(", ".join(food["a_limiter"]) + ".", body_style))

        story.append(_p("Structure des repas", h2_style))
        story.append(_bullet("Assiette type : un quart à un tiers de féculents, une portion de protéines, "
                              "des légumes à volonté, une source de bonnes graisses."))
        story.append(_bullet(f"{lifestyle.get('repas_par_jour', '3 à 4')} repas par jour, pour bien répartir "
                              f"les protéines."))
        story.append(_bullet("Une prise de protéines dans l'heure ou deux après l'entraînement."))
        story.append(_bullet("Base de l'alimentation sur des aliments à un seul ingrédient ; garde "
                              "l'ultra-transformé occasionnel plutôt que de le bannir totalement."))
        if lifestyle.get("temps_cuisine") == "Peu de temps (recettes rapides)":
            story.append(_bullet("Vu ton peu de temps pour cuisiner : privilégie la cuisson vapeur/poêle "
                                  "rapide, les œufs, les conserves de qualité (thon, légumineuses, maïs) et "
                                  "le batch cooking le week-end (cuire féculents et protéines en grande "
                                  "quantité pour plusieurs repas d'un coup)."))
        if lifestyle.get("budget_alimentaire") == "Serré":
            story.append(_bullet("Vu ton budget, mise sur les protéines les moins chères au gramme : œufs, "
                                  "poulet en cuisses/gros conditionnement, légumineuses en sec ou en boîte, "
                                  "thon en conserve, fromage blanc, et les légumes surgelés (aussi nutritifs "
                                  "que le frais, souvent moins chers)."))

        story.append(_p("Hydratation", h3_style))
        story.append(_bullet("2,5 à 3 L d'eau par jour, davantage les jours d'entraînement."))

        story.append(_p("Règle du 80/20", h3_style))
        story.append(_bullet("80% du temps une alimentation propre et structurée, 20% flexible. La constance "
                              "sur la durée compte plus que la perfection sur une semaine."))

        story.append(_p("Exemples de repas (à titre indicatif)", h2_style))
        story.append(_p("Ce ne sont que 2-3 exemples parmi de très nombreuses combinaisons possibles avec les "
                         "aliments recommandés ci-dessus — l'idée n'est pas de manger exactement ça tous les "
                         "jours, mais de piocher librement dans les catégories pour varier tes assiettes.",
                         note_style))
        exemples_repas, style_note = _meal_examples(
            food, profile.get("objectif_principal", ""), profile.get("signature", "")
        )
        story.append(_p(style_note, note_style))
        for nom_repas, contenu in exemples_repas:
            story.append(_bullet(f"<b>{nom_repas}</b> : {contenu}"))

        story.append(_p("Comment compter tes valeurs nutritionnelles", h3_style))
        story.append(_bullet("Utilise une application de suivi (Yazio, MyFitnessPal, FatSecret...) : elle "
                              "calcule kcal et macros automatiquement à partir du poids d'un aliment ou d'un "
                              "scan de code-barres."))
        story.append(_bullet("Pèse tes aliments crus (avant cuisson) les premières semaines, le temps de "
                              "connaître tes portions ; avec l'habitude tu pourras estimer à l'œil."))
        story.append(_bullet("Sur un emballage, repère la ligne « pour 100 g » du tableau des valeurs "
                              "nutritionnelles, puis ramène-la au poids réel de ta portion (règle de trois : "
                              "poids réel ÷ 100 × valeur pour 100 g)."))
        story.append(_bullet("Tu n'as pas besoin de peser à vie : quelques semaines de suivi rigoureux "
                              "suffisent en général pour bien connaître tes portions et pouvoir ensuite "
                              "estimer sans applications."))

        supplements = recommend_supplements({
            "complements": lifestyle.get("complements", []),
            "blessures": lifestyle.get("blessures", []),
            "sommeil": lifestyle.get("sommeil"),
            "sexe": profile["sexe"],
            "imc": nutrition["imc"],
            "objectif_principal": profile["objectif_principal"],
            "niveau_musculation": profile["niveau_musculation"],
            "restriction_alimentaire": lifestyle.get("restriction_alimentaire"),
            "niveau_activite_quotidien": lifestyle.get("niveau_activite_quotidien"),
        })
        if supplements["choisis"] or supplements["suggestions"]:
            story.append(_p("Compléments", h2_style))
        if supplements["choisis"]:
            story.append(_p("Ceux que tu as choisis", h3_style))
            for s in supplements["choisis"]:
                story.append(_bullet(f"<b>{s['nom']}</b> ({s['dosage']}) : {s['explication']}"))
                story.append(_bullet(f"&nbsp;&nbsp;→ Forme : {s['forme']}. Quand la prendre : {s['moment']}."))
        if supplements["suggestions"]:
            story.append(_p("Suggestions supplémentaires selon ton profil", h3_style))
            for s in supplements["suggestions"]:
                story.append(_bullet(f"<b>{s['nom']}</b> ({s['dosage']}) : {s['explication']}"))
                story.append(_bullet(f"&nbsp;&nbsp;→ Forme : {s['forme']}. Quand la prendre : {s['moment']}."))
            story.append(_p("Ces suggestions découlent de ton profil (blessures, sommeil, sexe, objectif, "
                             "restriction alimentaire...) ; elles restent facultatives.", note_style))

        # ---------- Menus de la semaine et recettes ----------
        # Retour Samy : « je veux énormément plus de contenu : le plus de repas
        # possible, le plus de recettes possible. Les repas doivent être
        # gourmands, healthy, diététiques et adaptés aux objectifs. »
        # Le PDF ne donnait jusqu'ici que des règles générales (règle de
        # l'assiette, hydratation, 80/20) sans un seul repas concret.
        if menu_semaine and menu_semaine.get("menu"):
            story.append(PageBreak())
            # Retour Samy : « supprime la partie "Tes menus de la semaine",
            # les recettes proposées suffisent largement ». Le tableau
            # jour-par-jour imposait un planning que personne ne suit à la
            # lettre, et il faisait doublon avec les recettes qui suivent.
            # Seule la consigne de portions est conservée : sans elle, les
            # quantités des recettes ne correspondraient à l'objectif calorique
            # de personne.
            story.append(_p("Tes recettes", h2_style))
            story.append(_p(
                "Ces recettes sont sélectionnées à partir de tes réponses : restriction "
                "alimentaire, aliments que tu n'aimes pas, aliments que tu apprécies, temps de "
                "préparation disponible et budget. Compose tes journées librement en piochant "
                "dedans.", body_style))

            for avertissement in menu_semaine.get("avertissements", []):
                story.append(_p("⚠ " + avertissement, warn_style))
            story.append(Spacer(1, 6))

            story.append(_p(
                "Quantités indiquées pour une portion.", note_style))

            for recette in menu_semaine.get("recettes_utilisees", []):
                bloc = [
                    _p(f"{recette['nom']} — {MOMENT_LABELS.get(recette['moment'], '')}", h3_style),
                    _p(f"<b>{recette['kcal']} kcal</b> · {recette['proteines']} g de protéines · "
                       f"{recette['glucides']} g de glucides · {recette['lipides']} g de lipides · "
                       f"{recette['minutes']} min de préparation", note_style),
                    _p("<b>Ingrédients :</b> " + ", ".join(recette["ingredients"]) + ".", body_style),
                ]
                for numero, etape in enumerate(recette["preparation"], start=1):
                    bloc.append(_bullet(f"{numero}. {etape}"))
                story.append(KeepTogether(bloc))
                story.append(Spacer(1, 6))

        story.append(PageBreak())

    # ================= 2. MUSCULATION =================
    if program:
        story.append(_p("2. PARTIE MUSCULAIRE — " + program["split_label"].upper(), section_style))

        story.append(_p(f"Programme en <b>{program['split_label']}</b>, {profile['frequence_entrainement']}x "
                         f"par semaine. Minimum 3 séries par exercice. Chaque séance associe un exercice "
                         f"« force » en ouverture et des exercices « hypertrophie » sous des angles variés.",
                         body_style))
        if program.get("objectif_note"):
            story.append(_p(program["objectif_note"], note_style))
        if program.get("niveau_note"):
            story.append(_p(program["niveau_note"], note_style))
        story.append(Spacer(1, 4))

        story.append(_p("Pourquoi ces exercices ont été choisis pour toi", h3_style))
        blessures = lifestyle.get("blessures") or []
        incapables = lifestyle.get("exercices_incapables") or []
        prioritaires_labels = program.get("prioritaires_labels") or []
        story.append(_bullet(f"Équipement : sélectionnés pour être réalisables avec ton équipement "
                              f"déclaré (<b>{program.get('equipement', 'Salle complète')}</b>)."))
        if blessures or incapables:
            exclus = ", ".join(blessures + incapables)
            story.append(_bullet(f"Sécurité : les mouvements à risque pour tes contraintes déclarées "
                                  f"({exclus}) ont été automatiquement exclus et remplacés par des "
                                  f"alternatives équivalentes."))
        story.append(_bullet("Niveau : le choix penche vers des mouvements guidés (machine) si tu es "
                              "débutant, ou vers des mouvements libres techniques si tu es avancé, "
                              "en fonction de ton niveau déclaré."))
        morpho_labels = program.get("morpho_labels") or []
        if morpho_labels:
            morpho_txt = {
                "bras_longs": "bras plutôt longs", "bras_courts": "bras plutôt courts",
                "jambes_longues": "jambes plutôt longues", "jambes_courtes": "jambes plutôt courtes",
                # Additif (prompt hors 24 phases, bascule PDF payant sur le
                # moteur V2) : le V2 suit aussi buste/épaules (cf.
                # logic/recommendation/biomechanics._activated_morphologie_keys),
                # jamais lus par l'ancien moteur -> absents jusqu'ici de cette table.
                "buste_long": "buste plutôt long", "buste_court": "buste plutôt court",
                "epaules_larges": "épaules plutôt larges", "epaules_etroites": "épaules plutôt étroites",
            }
            labels_fr = ", ".join(morpho_txt.get(m, m) for m in morpho_labels)
            story.append(_bullet(f"Morphologie : vu ta morphologie déclarée ({labels_fr}), certaines "
                                  f"variantes ont été privilégiées pour un meilleur confort articulaire "
                                  f"et une meilleure amplitude (ex : haltères plutôt que barre au "
                                  f"développé couché pour des bras longs, squat gobelet ou sumo plutôt "
                                  f"que back squat classique pour des jambes longues)."))
        story.append(_bullet("Structure : chaque muscle travaillé commence par un exercice « force » "
                              "(charges plus lourdes, moins de répétitions) puis enchaîne sur des "
                              "exercices « hypertrophie » sous des angles différents, pour solliciter "
                              "le muscle sous plusieurs axes."))
        story.append(_bullet("Variété : un seul exercice a été gardé par schéma de mouvement (ex : un "
                              "seul développé couché) plutôt que plusieurs variantes redondantes, pour "
                              "que chaque séance couvre des mouvements réellement différents."))
        if prioritaires_labels:
            story.append(_bullet(f"Priorité : {', '.join(prioritaires_labels)} reçoi(ven)t un exercice "
                                  f"supplémentaire par rapport aux autres groupes, pour accélérer leur "
                                  f"développement comme demandé."))

        # Additif (prompt hors 24 phases, "justification à 3 niveaux : exercice
        # / séance / programme") : "pourquoi_programme" (niveau programme,
        # cf. program_personalization.generate_program_explanation) — absent
        # si le programme vient de l'ancien moteur (rétrocompatible, ignoré).
        explanation = program.get("explanation") or {}
        if explanation.get("pourquoi_programme"):
            story.append(_p("Pourquoi CE programme, pour toi", h3_style))
            story.append(_p(explanation["pourquoi_programme"], note_style))
        pourquoi_seance_par_nom = {
            s.get("nom"): s.get("pourquoi_seance")
            for s in (explanation.get("seances") or [])
        }

        if program["warnings"]:
            for w in program["warnings"]:
                story.append(_p("⚠ " + w, warn_style))
            story.append(Spacer(1, 6))

        for i, jour in enumerate(program["programme"]):
            story.append(_p(jour["nom"] + f" (≈ {jour['duree_estimee_min']} min)", h2_style))
            # Additif (prompt hors 24 phases, justification niveau SÉANCE) :
            # absent si le programme vient de l'ancien moteur (rétrocompatible).
            pourquoi_seance = pourquoi_seance_par_nom.get(jour["nom"])
            if pourquoi_seance:
                story.append(_p(pourquoi_seance, note_style))
            for bloc in jour["muscles"]:
                rows = [
                    [_nom_avec_conseil(e["nom"], e.get("conseil_execution"), e.get("portion")), f"{e['series']} x {e['reps']}"]
                    for e in bloc["exercices"]
                ]
                story.append(KeepTogether([_p(bloc["muscle"], h3_style), _exo_table(rows)]))

            bonus = jour.get("bonus_poids_du_corps")
            if bonus:
                bonus_rows = [[f"{e['nom']} ({e['muscle']})", f"{e['series']} x {e['reps']}"] for e in bonus]
                # Retour Samy (prompt hors 24 phases : "une petite section où
                # c'est écrit poids de corps facultatif en début ou fin de
                # séance + X minutes") : estimation de temps affichée dans le
                # titre de la section (cf. `bonus_poids_du_corps_duree_min`,
                # logic/recommendation/program_builder.py), et rappel que ça
                # se fait en DÉBUT ou en FIN de séance, au choix.
                duree_bonus = jour.get("bonus_poids_du_corps_duree_min") or 0
                titre_bonus = "Bonus poids du corps — facultatif"
                if duree_bonus:
                    titre_bonus += f" (+ {duree_bonus} min)"
                story.append(KeepTogether([
                    _p(titre_bonus, h3_style),
                    _p("À ajouter en début OU en fin de séance, selon ce qui t'arrange — aucune "
                       "obligation, ton programme principal ci-dessus est déjà complet sans ça.",
                       note_style),
                    _exo_table(bonus_rows),
                ]))

            if i < len(program["programme"]) - 1:
                story.append(PageBreak())

        story.append(PageBreak())

    # ================= 3. CARDIO =================
    if cardio:
        story.append(_p("3. PARTIE CARDIO", section_style))
        objectif_cardio_affiche = cardio.get("objectif_cardio") or profile["objectif_principal"]
        story.append(_p(f"{cardio['nb_sessions']} séance(s) de {cardio['cardio_type'].lower()} par "
                         f"semaine, adaptées à ton objectif « {objectif_cardio_affiche} ».",
                         body_style))
        if cardio.get("objectif_cardio_note"):
            story.append(_p(cardio["objectif_cardio_note"], note_style))
        if cardio.get("niveau_cardio_note"):
            story.append(_p(cardio["niveau_cardio_note"], note_style))
        # Prompt hors 24 phases (retour Samy : "questionnaire adapté par
        # discipline") : une phrase par discipline choisie, dans le même
        # ordre que `cardio_types` (déjà dédupliqué/ordonné en amont).
        for discipline in cardio.get("cardio_types") or []:
            note_discipline = (cardio.get("notes_par_discipline") or {}).get(discipline)
            if note_discipline:
                story.append(_p(note_discipline, note_style))
        story.append(Spacer(1, 4))

        story.append(_p("Mini-cours : comprendre tes séances de cardio", h3_style))
        age = nutrition.get("age", 30)
        fcmax = 220 - age
        story.append(_bullet(f"Ta fréquence cardiaque maximale (FCmax) théorique, avec la formule "
                              f"« 220 − âge », est d'environ <b>{fcmax} battements/min</b>. Les zones "
                              f"d'intensité ci-dessous sont calculées à partir de cette valeur (une "
                              f"estimation, pas une mesure exacte)."))
        zone_explications = {
            "Endurance fondamentale": (f"<b>Endurance fondamentale</b> ({round(fcmax*0.6)}-{round(fcmax*0.7)} "
                                        f"batt/min) : la base du travail cardio. Développe ta capacité aérobie "
                                        f"et ta capacité à utiliser les graisses comme carburant, à effort "
                                        f"confortable et soutenable longtemps."),
            "Fractionné": (f"<b>Fractionné</b> ({round(fcmax*0.8)}-{round(fcmax*0.9)} batt/min sur les "
                            f"efforts) : alterne efforts intenses et récupération. Améliore ta VO2max "
                            f"(la quantité d'oxygène que ton corps peut utiliser) et ta vitesse de course "
                            f"tenable dans la durée."),
            "Sprints / explosivité": ("<b>Sprints / explosivité</b> (effort maximal) : travail de puissance "
                                       "et de vitesse pure, sur la filière anaérobie. Complémentaire de la "
                                       "musculation pour l'explosivité."),
            "Endurance légère": (f"<b>Endurance légère</b> ({round(fcmax*0.5)}-{round(fcmax*0.6)} "
                                  f"batt/min) : effort très confortable, presque une récupération active. "
                                  f"Entretient ta santé cardiovasculaire sans ajouter de fatigue."),
        }
        types_presents = list(dict.fromkeys(s["type"] for s in cardio["seances"]))
        for t in types_presents:
            if t in zone_explications:
                story.append(_bullet(zone_explications[t]))
                continue
            # Types ajoutés au catalogue cardio (Tempo, Seuil, VMA, Côtes,
            # Fartlek, allures spécifiques...) : l'explication est construite
            # automatiquement à partir du référentiel de zones, converti en
            # battements/min pour cet utilisateur. Sans ce repli, une séance de
            # Seuil ou de VMA apparaissait dans le tableau sans la moindre
            # explication de zone au-dessus.
            zone = cardio_zones.zone_de(t)
            if not zone:
                continue
            bpm_min = round(fcmax * zone["fc_min"] / 100)
            bpm_max = round(fcmax * zone["fc_max"] / 100)
            story.append(_bullet(
                f"<b>{t}</b> ({bpm_min}-{bpm_max} batt/min, soit "
                f"{zone['fc_min']}-{zone['fc_max']}% de ta FCmax) : "
                f"{cardio_zones.description_de(t)} "
                f"Filière {zone['filiere'].lower()}, carburant principal : "
                f"{zone['carburant'].lower()}."
            ))
        story.append(_p("Concrètement, tu peux estimer ta fréquence cardiaque pendant l'effort avec une "
                         "montre connectée, ou plus simplement au ressenti : en endurance fondamentale tu "
                         "dois pouvoir parler par phrases courtes, en fractionné tu es essoufflé mais tu "
                         "tiens l'effort, en sprint tu ne peux pas parler du tout.", note_style))

        if cardio["warnings"]:
            for w in cardio["warnings"]:
                story.append(_p("⚠ " + w, warn_style))
            story.append(Spacer(1, 6))

        rows = [[s["nom"], s.get("discipline", cardio["cardio_type"]), s["type"], s["protocole"]] for s in cardio["seances"]]
        story.append(_cardio_table(rows))
        story.append(Spacer(1, 8))
        story.append(_p("Idéalement, place les séances de cardio à distance des séances de musculation "
                         "les plus lourdes (jambes notamment), ou en fin de séance de musculation si tu "
                         "manques de jours dans la semaine.", note_style))

        story.append(PageBreak())

    # ================= 4. CONSEILS =================
    story.append(_p("4. CONSEILS GÉNÉRAUX", section_style))

    story.append(_p("Entraînement", h2_style))
    story.append(_bullet("Priorité à la technique avant la charge : mieux vaut exécuter un mouvement "
                          "correctement avec moins de poids que de charger lourd avec une mauvaise forme."))
    story.append(_bullet("Progression progressive : augmente le poids ou les répétitions dès que les "
                          "séries hautes de la fourchette deviennent faciles."))
    if lifestyle.get("precisions"):
        story.append(_bullet(f"Précision indiquée : {lifestyle['precisions']} — garde ce point en tête "
                              f"pendant les séances et adapte l'amplitude/la charge si besoin."))
    if lifestyle.get("autre_sport") == "Oui":
        story.append(_bullet(f"Tu pratiques aussi {lifestyle.get('autre_sport_type', 'un autre sport')} "
                              f"({lifestyle.get('autre_sport_sessions', '?')}x/semaine) : répartis bien "
                              f"tes jours de repos entre toutes tes activités pour éviter le cumul de "
                              f"fatigue sur les mêmes groupes musculaires."))
        # Additif (prompt hors 24 phases, retour Samy : "demande si tu veux
        # que le programme soit adapté à ce sport") : n'affiche cette 2e
        # phrase que si l'utilisateur a explicitement demandé l'adaptation
        # ET que le sport déclaré a une correspondance documentée (cf.
        # logic/recommendation/sport_profiles.py, réutilisé ici en lecture
        # seule pour le libellé des muscles, aucune règle recalculée).
        if lifestyle.get("autre_sport_adapter") == "Oui":
            from logic.recommendation.sport_profiles import SPORT_MUSCLES_PRIORITAIRES
            muscles_sport = SPORT_MUSCLES_PRIORITAIRES.get(lifestyle.get("autre_sport_type_brut", ""))
            if muscles_sport:
                labels_muscles = ", ".join(sorted(MUSCLE_LABELS.get(m, m) for m in muscles_sport))
                story.append(_bullet(f"Ton programme est adapté à {lifestyle.get('autre_sport_type', 'ce sport')} "
                                      f"comme demandé : {labels_muscles} reçoivent davantage de volume, ce "
                                      f"sont les groupes les plus sollicités par cette pratique."))
    story.append(_bullet("Quelques minutes d'étirements ou de mobilité en fin de séance pour la récupération."))

    story.append(_p("Récupération", h2_style))
    sommeil = lifestyle.get("sommeil", "7 à 8h")
    story.append(_bullet(f"Sommeil actuel déclaré : {sommeil} par nuit. Vise 7 à 9h : c'est pendant le "
                          f"sommeil que se fait l'essentiel de la récupération musculaire et de la "
                          f"production hormonale."))
    story.append(_bullet("Prévois au moins un jour de repos complet dans la semaine."))
    if lifestyle.get("niveau_stress") == "Élevé":
        story.append(_bullet("Stress actuel élevé : un stress chronique maintient le cortisol élevé, ce "
                              "qui peut perturber ton sommeil, ta récupération et parfois ton appétit. "
                              "Quelques minutes de respiration lente, de marche ou de coupure sans écran "
                              "avant de dormir peuvent faire une vraie différence sur ta progression."))
    elif lifestyle.get("niveau_stress") == "Modéré":
        story.append(_bullet("Stress modéré déclaré : reste attentif à ton sommeil et ta récupération, "
                              "des périodes de stress plus intenses peuvent nécessiter de réduire "
                              "temporairement le volume d'entraînement plutôt que de forcer."))

    if lifestyle.get("tabac") and lifestyle["tabac"] != "Non":
        story.append(_bullet("Tabac : réduit la capacité pulmonaire et l'endurance cardiovasculaire, "
                              "ce qui freine directement les progrès en cardio."))
    if lifestyle.get("cigarette_electronique") and lifestyle["cigarette_electronique"] != "Non":
        story.append(_bullet("Cigarette électronique : la nicotine a des effets similaires au tabac "
                              "classique sur le système cardiovasculaire et la récupération, même sans "
                              "combustion — à limiter, surtout avant les séances de cardio."))
    if lifestyle.get("cannabis") and lifestyle["cannabis"] != "Non":
        story.append(_bullet("Cannabis : peut stimuler l'appétit (risque pour le respect de l'objectif "
                              "calorique) et perturber la qualité du sommeil profond, donc la récupération. "
                              "Éviter d'en consommer avant de dormir les jours d'entraînement peut aider."))
    if lifestyle.get("alcool") and lifestyle["alcool"] not in ("Jamais", None):
        story.append(_bullet("Alcool : impacte négativement le sommeil, la récupération et l'équilibre "
                              "hormonal, en plus d'ajouter des calories vides."))

    story.append(_p("Suivi et ajustements", h2_style))
    imc_cat = nutrition.get("imc_categorie")
    if imc_cat == "sous-poids":
        story.append(_bullet("Ton IMC est en sous-poids : surveille que le surplus calorique se traduise "
                              "bien par une prise de poids progressive (250-500g/semaine) ; si le poids "
                              "stagne, augmente encore un peu les calories plutôt que le volume "
                              "d'entraînement."))
    elif imc_cat == "obésité":
        story.append(_bullet("Ton IMC est dans la catégorie obésité : privilégie la régularité et des "
                              "objectifs de perte de poids modérés (0,5 à 1% du poids corporel par "
                              "semaine) plutôt qu'un déficit agressif, pour préserver la masse musculaire "
                              "et la santé articulaire."))
    story.append(_bullet("Réévalue ton poids et tes mensurations toutes les 2 à 4 semaines pour ajuster "
                          "les calories si besoin."))
    story.append(_bullet("Ne te fie pas uniquement à la balance : prends aussi des photos et des mesures."))

    composition = profile.get("composition_corporelle")
    # Prompt hors 24 phases (retour Samy : options "sec"/"mince" distinctes,
    # ajout "athlétique") : les deux valeurs remplacent l'ancienne option
    # unique "Plutôt sec / mince" pour ce même avertissement décalage-IMC ;
    # rétrocompatible avec d'anciens profils enregistrés sous l'ancien libellé.
    valeurs_sec_ou_mince = (
        "Sec / bien défini, peu de gras visible",
        "Mince / plutôt menu(e), naturellement peu de masse",
        "Plutôt sec / mince",
    )
    if composition and composition != "Je ne sais pas":
        if composition in ("En surpoids / du gras à perdre", "Plutôt en surpoids / du gras à perdre") \
                and imc_cat in ("poids normal", "sous-poids"):
            story.append(_bullet("Tu te perçois plutôt en surpoids alors que ton IMC est dans la norme : "
                                  "l'IMC ne distingue pas masse grasse et masse musculaire, donc ce "
                                  "décalage est fréquent et ne remet pas en cause le calcul ci-dessus. "
                                  "Fie-toi surtout à l'évolution de tes mensurations et de tes photos."))
        elif composition in valeurs_sec_ou_mince and imc_cat in ("surpoids", "obésité"):
            story.append(_bullet("Tu te perçois plutôt sec/mince alors que ton IMC suggère un surpoids : "
                                  "si tu es très musclé, l'IMC peut surestimer ta masse grasse réelle. "
                                  "Le tour de taille et les photos donneront une image plus fidèle que "
                                  "l'IMC seul dans ton cas."))
        elif composition == "Musclé(e) avec du gras à perdre (recomposition)":
            story.append(_bullet("Vu ta description (musclé avec du gras à perdre), la recomposition "
                                  "corporelle (perdre du gras tout en maintenant le muscle) est réaliste "
                                  "avec un déficit calorique modéré et un apport protéique élevé — assure-toi "
                                  "de bien suivre les grammes de protéines indiqués plus haut."))

    story.append(_p("Mental et constance", h2_style))
    story.append(_bullet("La constance sur plusieurs mois compte plus que la perfection sur une semaine."))
    story.append(_bullet("Évite de te comparer à d'autres pratiquants : les résultats visibles prennent "
                          "plusieurs mois, surtout en début de parcours."))

    if nutrition["age"] < 18 or lifestyle.get("condition_medicale") == "Oui":
        story.append(_p("Suivi médical", h2_style))
        if nutrition["age"] < 18:
            story.append(_bullet(f"Tu as {nutrition['age']} ans : il est recommandé qu'un médecin ou "
                                  f"nutritionniste valide ce plan, pour s'assurer qu'il n'interfère pas "
                                  f"avec ta croissance."))
        if lifestyle.get("condition_medicale") == "Oui":
            detail = f" ({lifestyle['condition_medicale_details']})" if lifestyle.get("condition_medicale_details") else ""
            story.append(_bullet(f"Condition médicale déclarée{detail} : fais valider ce plan par un "
                                  f"professionnel de santé avant de le suivre."))

    doc.build(story)
