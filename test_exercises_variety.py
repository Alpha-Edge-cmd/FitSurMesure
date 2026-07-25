# -*- coding: utf-8 -*-
"""Vérifications ciblées suite aux retours utilisateur :
- pas d'élastique quand l'équipement est "Salle complète" / machines / poids libres
- pas de doublon de mouvement (rowing, soulevé de terre) dans une même séance
- pas de chevauchement de texte détecté dans le PDF
"""
import io
import json
import random
import sys

import pdfplumber

sys.path.insert(0, ".")
from app import app
from logic.exercises_db import EXERCISES
from test_helpers import ensure_test_promo_code, generate_via_payment

# Construit un mapping nom d'exercice -> pattern pour détecter les doublons de mouvement
NAME_TO_PATTERN = {}
for muscle, exos in EXERCISES.items():
    for e in exos:
        NAME_TO_PATTERN[e["name"]] = e["pattern"]

client = app.test_client()
ensure_test_promo_code()

OBJECTIFS = ["Perte de gras", "Prise de muscle", "Recomposition (sec + muscle)",
             "Performance / explosivité", "Condition physique générale"]
NIVEAUX = ["Débutant complet", "Quelques mois d'expérience", "Intermédiaire", "Avancé"]
EQUIPEMENTS_GYM = ["Salle complète", "Surtout machines guidées", "Surtout poids libres"]

random.seed(123)

errors = []
elastique_in_gym = []
duplicate_pattern_cases = []
overlap_cases = []

N = 40
for i in range(N):
    niveau = random.choice(NIVEAUX)
    objectif = random.choice(OBJECTIFS)
    equip = random.choice(EQUIPEMENTS_GYM)
    freq = random.choice([3, 4, 5, 6])
    payload = {
        "consentement_rgpd": True,
        "prenom": f"T{i}",
        "date_naissance": f"19{random.randint(70,99)}-0{random.randint(1,9)}-1{random.randint(0,8)}",
        "sexe": random.choice(["Homme", "Femme"]),
        "poids": random.randint(55, 110),
        "taille": random.randint(150, 200),
        "formule": "musculation",
        "frequence_entrainement": freq,
        "niveau_musculation": niveau,
        "objectif_principal": objectif,
        "equipement": equip,
        "duree_seance": random.choice(["45 min", "1h", "1h - 1h30", "1h30+"]),
        "split_preference": "auto",
        "composition_corporelle": "Je ne sais pas",
        "muscles_prioritaires": random.sample(
            ["Pectoraux", "Dos", "Jambes (quadriceps/ischio)", "Épaules", "Fessiers"],
            k=random.choice([0, 1, 2])
        ),
        "blessures": random.sample(["Genoux", "Épaule", "Dos / lombaires", "Poignets"], k=random.choice([0, 1, 2])),
        "restriction_alimentaire": "Aucune",
        "niveau_activite_quotidien": "modere",
    }
    resp = generate_via_payment(client, payload)
    if resp.status_code != 200:
        errors.append((i, payload, resp.status_code, resp.get_data(as_text=True)[:300]))
        continue

    pdf_bytes = resp.get_data()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(pages_text)

        for pno, page in enumerate(pdf.pages):
            words = page.extract_words()
            for a_idx in range(len(words)):
                for b_idx in range(a_idx + 1, len(words)):
                    a, b = words[a_idx], words[b_idx]
                    if a['x0'] < b['x1'] and b['x0'] < a['x1'] and a['top'] < b['bottom'] and b['top'] < a['bottom']:
                        overlap_w = min(a['x1'], b['x1']) - max(a['x0'], b['x0'])
                        overlap_h = min(a['bottom'], b['bottom']) - max(a['top'], b['top'])
                        if overlap_w > 3 and overlap_h > 3 and a['text'] != b['text']:
                            overlap_cases.append((i, pno, a['text'], b['text']))

    if "élastique" in full_text or "Élastique" in full_text:
        elastique_in_gym.append((i, equip, niveau, objectif))

    # Détection de doublons de pattern par séance : on cherche les blocs
    # "Exercice Séries x Répétitions" suivis des lignes d'exercices jusqu'au prochain
    # titre de muscle ou fin.
    lines = full_text.split("\n")
    current_patterns = []
    in_table = False
    for ln in lines:
        if ln.strip() == "Exercice Séries x Répétitions":
            in_table = True
            current_patterns = []
            continue
        if in_table:
            # ligne d'exercice : "Nom xN reps" -> on retire la partie "N x reps"
            m = None
            import re
            m = re.match(r"^(.*?)\s+\d+\s*x\s*[\d\-]+$", ln.strip())
            if m:
                nom = m.group(1).strip()
                pattern = NAME_TO_PATTERN.get(nom)
                if pattern:
                    if pattern in current_patterns:
                        duplicate_pattern_cases.append((i, nom, pattern, payload["equipement"], payload["niveau_musculation"]))
                    current_patterns.append(pattern)
            else:
                in_table = False

print(f"Profils testés : {N}")
print(f"Erreurs HTTP/PDF : {len(errors)}")
for e in errors[:5]:
    print(" -", e)

print(f"\nÉlastique présent alors qu'équipement = salle/machines/poids libres : {len(elastique_in_gym)}")
for e in elastique_in_gym[:10]:
    print(" -", e)

print(f"\nDoublons de pattern (même mouvement 2x dans une séance) : {len(duplicate_pattern_cases)}")
for d in duplicate_pattern_cases[:10]:
    print(" -", d)

print(f"\nChevauchements de texte détectés : {len(overlap_cases)}")
for o in overlap_cases[:10]:
    print(" -", o)

sys.exit(1 if (errors or elastique_in_gym or duplicate_pattern_cases or overlap_cases) else 0)
