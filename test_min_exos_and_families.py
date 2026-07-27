# -*- coding: utf-8 -*-
"""Vérifie le plancher d'exercices par séance (9 pour 1h-1h30, 10 pour 1h30+)
et l'absence de 2 exercices de la même "famille" de mouvement pour un même muscle
tant que d'autres familles sont disponibles (ex: 2x développé couché sous des
angles différents)."""
import io
import json
import random
import re
import sys

import pdfplumber

sys.path.insert(0, ".")
from app import app
from logic.program_builder import FAMILY_MAP, NAME_TO_PATTERN, MIN_EXOS_PAR_SEANCE
from logic.exercises_db import MUSCLE_LABELS
from test_helpers import ensure_test_promo_code, generate_via_payment

MUSCLE_HEADERS = set(MUSCLE_LABELS.values())

client = app.test_client()
ensure_test_promo_code()

OBJECTIFS = ["Perte de gras", "Prise de muscle", "Recomposition (sec + muscle)",
             "Performance / explosivité", "Condition physique générale"]
NIVEAUX = ["Débutant complet", "Quelques mois d'expérience", "Intermédiaire", "Avancé"]
EQUIPEMENTS = ["Salle complète", "Surtout machines guidées", "Surtout poids libres",
               "Matériel limité à domicile"]
DUREES = ["1h - 1h30", "1h30+"]

random.seed(99)

errors = []
below_floor = []
family_dupes = []

SESSION_RE = re.compile(r"^(.+?)\s*\(.\s*\d+\s*min\)\s*$")

N = 40
for i in range(N):
    niveau = random.choice(NIVEAUX)
    objectif = random.choice(OBJECTIFS)
    equip = random.choice(EQUIPEMENTS)
    duree = random.choice(DUREES)
    freq = random.choice([3, 4, 5])
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
        "duree_seance": duree,
        "split_preference": "auto",
        "composition_corporelle": "Je ne sais pas",
        "muscles_prioritaires": random.sample(["Pectoraux", "Dos", "Jambes (quadriceps/ischio)"], k=random.choice([0, 1])),
        "restriction_alimentaire": "Aucune",
        "niveau_activite_quotidien": "modere",
    }
    resp = generate_via_payment(client, payload)
    if resp.status_code != 200:
        errors.append((i, payload, resp.status_code))
        continue

    with pdfplumber.open(io.BytesIO(resp.get_data())) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    min_required = MIN_EXOS_PAR_SEANCE.get(duree, 0)

    lines = text.split("\n")
    current_session = None
    current_muscle = None
    session_total = 0
    muscle_families = {}  # (session, muscle) -> {family: count}
    in_table = False

    def flush_session_check():
        if current_session is not None and min_required and session_total < min_required:
            below_floor.append((i, current_session, session_total, min_required, equip, duree))

    for line in lines:
        stripped = line.strip()
        m = SESSION_RE.match(stripped)
        if m and any(kw in stripped for kw in ["Push", "Pull", "Legs", "Upper", "Lower", "Séance", "Torse", "Épaules / Bras", "Jambes"]):
            flush_session_check()
            current_session = stripped
            session_total = 0
            current_muscle = None
            in_table = False
            continue
        if stripped in MUSCLE_HEADERS:
            current_muscle = stripped
            in_table = False
            continue
        if stripped == "Exercice Séries x Répétitions":
            in_table = True
            continue
        if in_table:
            em = re.match(r"^(.*?)\s+\d+\s*x\s*[\d\-]+$", stripped)
            if em:
                nom = em.group(1).strip()
                session_total += 1
                pattern = NAME_TO_PATTERN.get(nom)
                if pattern and current_session and current_muscle:
                    fam = FAMILY_MAP.get(pattern, pattern)
                    key = (current_session, current_muscle)
                    fams = muscle_families.setdefault(key, {})
                    fams[fam] = fams.get(fam, 0) + 1
            # Prompt hors 24 phases (conseils d'exécution) : chaque exercice
            # est désormais suivi d'une ligne de conseil (tempo/effort) qui ne
            # matche jamais le motif "nom N x M" ci-dessus. Avant, une seule
            # ligne ne matchant pas suffisait à sortir du tableau (`in_table
            # = False`) — ce qui coupait le comptage après le 1er exercice de
            # chaque bloc muscle. La sortie de tableau reste correctement
            # détectée plus haut (nouvel en-tête muscle/nouvelle séance) : une
            # ligne isolée non reconnue À L'INTÉRIEUR du tableau est donc
            # maintenant simplement ignorée plutôt que de couper le comptage.
    flush_session_check()

    for (session, muscle), fams in muscle_families.items():
        # Un doublon de famille n'est un problème que si TOUTES les familles n'ont
        # pas encore été utilisées au moins une fois pour ce muscle (sinon c'est un
        # 2e passage légitime faute d'autre famille disponible).
        total_patterns_for_muscle = None  # on ne connait pas le nb de familles dispo ici
        dupes = {f: c for f, c in fams.items() if c > 1}
        if dupes:
            # Ne remonter que si le muscle a un mapping FAMILY_MAP connu (sinon la
            # famille == pattern, et le dedup par pattern est déjà garanti ailleurs).
            known = any(f in FAMILY_MAP.values() for f in dupes)
            if known:
                family_dupes.append((i, session, muscle, dupes, equip, duree))

print(f"Profils testés : {N}")
print(f"Erreurs : {len(errors)}")
for e in errors[:10]:
    print(" -", e)

print(f"\nSéances sous le plancher minimum : {len(below_floor)}")
for b in below_floor[:15]:
    print(" -", b)

print(f"\nDoublons de FAMILLE de mouvement (ex: 2x développé couché) : {len(family_dupes)}")
for d in family_dupes[:15]:
    print(" -", d)

sys.exit(1 if (errors or below_floor or family_dupes) else 0)
