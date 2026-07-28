# -*- coding: utf-8 -*-
"""Test de régression complet après le dernier round de modifications :
multi-select questionnaire, composition corporelle, temps 1km, note validité
nutrition, variété des repas d'exemple, forme/moment des compléments, split
auto + variété A/B/C en full body."""
import io
import json
import random
import sys

import pdfplumber

sys.path.insert(0, ".")
from app import app, _include_nutrition
from test_helpers import ensure_test_promo_code, generate_via_payment

OBJECTIFS = [
    "Perte de gras", "Prise de muscle", "Recomposition (sec + muscle)",
    "Performance / explosivité", "Condition physique générale",
]
NIVEAUX = ["Débutant complet", "Intermédiaire", "Avancé"]
EQUIPEMENTS = ["Salle complète", "Matériel limité à domicile", "Poids du corps uniquement"]
FORMULES = ["musculation", "cardio", "les_deux", "abonnement"]
COMPOSITIONS = [
    "Plutôt sec / mince", "Plutôt en surpoids / du gras à perdre",
    "Musclé(e) avec du gras à perdre (recomposition)", "Je ne sais pas",
]

client = app.test_client()
ensure_test_promo_code()

errors = []
meal_texts_by_style = {"leger": set(), "genereux": set(), "equilibre": set()}
fullbody_ab_identical = 0
fullbody_ab_total = 0
split_choices = []

random.seed(42)

N = 60
for i in range(N):
    prenom = f"Test{i}"
    objectif = random.choice(OBJECTIFS)
    niveau = random.choice(NIVEAUX)
    equip = random.choice(EQUIPEMENTS)
    formule = random.choice(FORMULES)
    freq = random.choice([2, 3, 4, 5, 6])
    composition = random.choice(COMPOSITIONS)
    cardio_types = random.sample(["Course", "Vélo", "Natation", "Autre"], k=random.choice([1, 2]))

    payload = {
        "consentement_rgpd": True,
        "prenom": prenom,
        "date_naissance": f"19{random.randint(70,99)}-0{random.randint(1,9)}-15",
        "sexe": random.choice(["Homme", "Femme"]),
        "poids": random.randint(55, 110),
        "taille": random.randint(150, 200),
        "formule": formule,
        "frequence_entrainement": freq,
        "niveau_musculation": niveau,
        "objectif_principal": objectif,
        "equipement": equip,
        "duree_seance": "1h - 1h30",
        "split_preference": "auto",
        "composition_corporelle": composition,
        "muscles_prioritaires": random.sample(["Pectoraux", "Dos", "Jambes", "Épaules"], k=1),
        "cardio_types": cardio_types,
        "temps_1km": round(random.uniform(3.5, 8.0), 1) if "Course" in cardio_types else None,
        "cardio_frequence": f"{random.randint(1,3)}x / semaine",
        "objectif_cardio": random.choice([
            "Perdre du poids / sécher", "Améliorer mon endurance générale",
            "Me préparer à une course (5km, 10km, semi, marathon)",
            "Santé cardiovasculaire générale", "",
        ]),
        "pratique_cardio": "Oui",
        "complements": random.sample(list(["Créatine", "Whey", "Oméga-3", "Magnésium / ZMA"]), k=random.choice([0,1,2])),
        "restriction_alimentaire": random.choice(["Aucune", "Végétarien", "Végan"]),
        "niveau_activite_quotidien": random.choice(["sedentaire", "leger", "modere"]),
    }

    resp = generate_via_payment(client, payload)
    if resp.status_code != 200:
        errors.append((i, payload, resp.status_code, resp.get_data(as_text=True)[:300]))
        continue

    pdf_bytes = resp.get_data()
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        errors.append((i, payload, "pdf_parse_error", str(e)))
        continue

    # Retour Samy (prompt hors 24 phases, #148) : "dans le programme
    # musculation seul ne mets pas de programme alimentation et dans le
    # programme cardio pareil" -- les vérifs ci-dessous portent sur le
    # contenu de la partie Alimentation (note de validité, forme des
    # compléments, exemples de repas), donc uniquement pertinentes/attendues
    # quand cette partie est effectivement incluse dans le PDF (même règle
    # que `app._include_nutrition`, jamais pour "musculation"/"cardio" seuls).
    if _include_nutrition(formule):
        # -- Vérifs meal variety --
        style = "leger" if objectif == "Perte de gras" else ("genereux" if objectif == "Prise de muscle" else "equilibre")
        # extract the "Déjeuner" line roughly
        if "Déjeuner :" in text:
            idx = text.index("Déjeuner :")
            snippet = text[idx:idx+150]
            meal_texts_by_style[style].add(snippet)

        if "restent fiables tant que celui-ci reste entre" not in text:
            errors.append((i, payload, "missing_nutrition_validity_note", ""))

        if payload["complements"] and "Forme :" not in text:
            errors.append((i, payload, "missing_supplement_form", ""))

    # -- Split / full body A/B/C variety check --
    if formule in ("musculation", "les_deux", "abonnement") and freq == 3:
        if "Séance A" in text and "Séance B" in text:
            fullbody_ab_total += 1
            # crude: grab exercise block between "Séance A" and "Séance B", and B->C
            ia = text.index("Séance A")
            ib = text.index("Séance B")
            block_a = text[ia:ib]
            ic = text.index("Séance C") if "Séance C" in text else len(text)
            block_b = text[ib:ic]
            if block_a.strip() == block_b.strip():
                fullbody_ab_identical += 1
        split_choices.append((niveau, objectif, "PPL" if "Push" in text or "Pull" in text else ("FullBody" if "Séance A" in text else "?")))

print(f"Total profils testés : {N}")
print(f"Erreurs : {len(errors)}")
for e in errors[:10]:
    print(" -", e)

print("\nVariété des repas (nb de textes distincts par style) :")
for style, texts in meal_texts_by_style.items():
    print(f"  {style}: {len(texts)} variantes distinctes observées")

print(f"\nFull body A vs B identiques (sur {fullbody_ab_total} cas à 3x/semaine en full body) : {fullbody_ab_identical}")

from collections import Counter
print("\nRépartition split à 3x/semaine (niveau, objectif) -> split :")
c = Counter(split_choices)
for k, v in sorted(c.items(), key=lambda x: -x[1])[:15]:
    print(" ", k, v)

sys.exit(1 if errors else 0)
