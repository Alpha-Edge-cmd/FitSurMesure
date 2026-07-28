# -*- coding: utf-8 -*-
"""Vérifie le plancher d'exercices PAR MUSCLE ET PAR POSITION DE PRIORITÉ
(4 pour le muscle principal/prioritaire, 3 puis 2 pour les suivants — cf.
`logic.recommendation.volume._repartition_positionnelle`/
`calculer_repartition_seance`) et l'absence de 2 exercices de la même
"famille" de mouvement pour un même muscle tant que d'autres familles sont
disponibles (ex: 2x développé couché sous des angles différents).

Prompt hors 24 phases (retour Samy, test en conditions réelles : "ça ne va
pas du tout une séance fait 4 exercices, minimum 3 exercice par muscle et 4
pour le muscle principal ou le muscle priorisé choisi par la personne") :
REMPLACE l'ancien plancher de VOLUME TOTAL par séance (SESSION_MIN_EXOS,
9/10 selon durée, `logic.program_builder.MIN_EXOS_PAR_SEANCE`) — retiré du
moteur V2 (`workout_generator._muscles_ordonnes_par_priorite`/
`volume.calculer_repartition_seance`) au profit d'une répartition explicite
PAR MUSCLE ET PAR POSITION : 1 muscle -> [4] ; 2 muscles -> [4, 4] ; 3+
muscles -> [4, 3, 2, ...] (dégression jusqu'à un plancher de 2), le tout
appliqué uniquement à partir d'1h de séance (les 2 durées testées ici, "1h -
1h30" et "1h30+", sont toutes deux au-dessus du seuil).

Le catalogue réel peut malgré tout dimensionner en dessous de ce plancher
pour un muscle si le PDF l'explique : soit par manque de candidats
disponibles compte tenu des contraintes (équipement/blessures/exclusions,
`workout_generator.MESSAGE_VOLUME_CIBLE_INATTEIGNABLE`), soit parce que même
au plancher de séries (`prescription.MIN_SETS_FLOOR`) le budget de fatigue
est dépassé et qu'aucun retrait d'exercice n'est plus possible sans descendre
sous le plancher retenu (`workout_generator.MESSAGE_BUDGET_PLANCHER`) ou
qu'un retrait a quand même eu lieu ailleurs dans la séance
(`prescription.MESSAGE_EXERCICE_RETIRE_BUDGET`). Une séance sous le plancher
n'est donc un problème QUE si le PDF n'explique pas pourquoi."""
import io
import random
import re
import sys

import pdfplumber

sys.path.insert(0, ".")
from app import app
from logic.program_builder import FAMILY_MAP, NAME_TO_PATTERN
from logic.exercises_db import MUSCLE_LABELS
from logic.recommendation.prescription import MESSAGE_EXERCICE_RETIRE_BUDGET
from logic.recommendation.workout_generator import MESSAGE_BUDGET_PLANCHER
from logic.recommendation.volume import _repartition_positionnelle, SEUIL_NOUVELLE_REPARTITION_MINUTES, _duree_minutes
from test_helpers import ensure_test_promo_code, generate_via_payment

MUSCLE_HEADERS = set(MUSCLE_LABELS.values())
MUSCLE_LABEL_TO_KEY = {v: k for k, v in MUSCLE_LABELS.items()}

client = app.test_client()
ensure_test_promo_code()

OBJECTIFS = ["Perte de gras", "Prise de muscle", "Recomposition (sec + muscle)",
             "Performance / explosivité", "Condition physique générale"]
NIVEAUX = ["Débutant complet", "Quelques mois d'expérience", "Intermédiaire", "Avancé"]
EQUIPEMENTS = ["Salle complète", "Surtout machines guidées", "Surtout poids libres",
               "Matériel limité à domicile"]
DUREES = ["1h - 1h30", "1h30+"]
assert all(_duree_minutes(d) >= SEUIL_NOUVELLE_REPARTITION_MINUTES for d in DUREES)

random.seed(99)

errors = []
below_floor = []
family_dupes = []

SESSION_RE = re.compile(r"^(.+?)\s*\(.\s*\d+\s*min\)\s*$")

# Suffixe stable (sans les placeholders numériques/nom de muscle) du message
# "cible non atteinte faute de candidats" -> matchable indépendamment des
# valeurs formatées pour chaque muscle concerné.
SUFFIXE_VOLUME_CIBLE_INATTEIGNABLE = "compte tenu de tes contraintes actuelles (équipement/blessures/exclusions)."
MESSAGE_BUDGET_PLANCHER_APLATI = re.sub(r"\s+", " ", MESSAGE_BUDGET_PLANCHER).strip()
MESSAGE_EXERCICE_RETIRE_BUDGET_APLATI = re.sub(r"\s+", " ", MESSAGE_EXERCICE_RETIRE_BUDGET).strip()

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

    # Prompt hors 24 phases (retrait budgétaire d'exercices / cible non
    # atteinte, cf. docstring en tête de fichier) : une séance sous le
    # plancher reste acceptable si le PDF explique pourquoi. Les messages
    # concernés sont de longs paragraphes reportlab qui RETOURNENT À LA LIGNE
    # dans le PDF (largeur de page) : pdfplumber extrait alors ce texte
    # réparti sur plusieurs lignes, cassant une recherche de sous-chaîne
    # littérale -> on aplatit tous les espaces/retours à la ligne du texte
    # extrait en un seul espace avant de chercher.
    texte_aplati = re.sub(r"\s+", " ", text)
    a_une_explication = (
        SUFFIXE_VOLUME_CIBLE_INATTEIGNABLE in texte_aplati
        or MESSAGE_BUDGET_PLANCHER_APLATI in texte_aplati
        or MESSAGE_EXERCICE_RETIRE_BUDGET_APLATI in texte_aplati
    )

    lines = text.split("\n")
    current_session = None
    current_muscle = None
    muscles_ordre = []  # ordre de première apparition dans la séance courante
    muscle_counts = {}  # muscle -> nombre d'exercices dans la séance courante
    muscle_families = {}  # (session, muscle) -> {family: count}
    in_table = False

    def flush_session_check():
        if current_session is None or not muscles_ordre:
            return
        base = _repartition_positionnelle(len(muscles_ordre))
        for idx, muscle in enumerate(muscles_ordre):
            plancher = base[idx]
            obtenu = muscle_counts.get(muscle, 0)
            if obtenu < plancher and not a_une_explication:
                below_floor.append((i, current_session, muscle, obtenu, plancher, equip, duree))

    for line in lines:
        stripped = line.strip()
        m = SESSION_RE.match(stripped)
        if m and any(kw in stripped for kw in ["Push", "Pull", "Legs", "Upper", "Lower", "Séance", "Torse", "Épaules / Bras", "Jambes"]):
            flush_session_check()
            current_session = stripped
            current_muscle = None
            muscles_ordre = []
            muscle_counts = {}
            in_table = False
            continue
        if stripped in MUSCLE_HEADERS:
            current_muscle = stripped
            if current_muscle not in muscle_counts:
                muscles_ordre.append(current_muscle)
                muscle_counts[current_muscle] = 0
            in_table = False
            continue
        if stripped == "Exercice Séries x Répétitions":
            in_table = True
            continue
        if in_table:
            em = re.match(r"^(.*?)\s+\d+\s*x\s*[\d\-]+$", stripped)
            if em:
                nom = em.group(1).strip()
                if current_muscle is not None:
                    muscle_counts[current_muscle] = muscle_counts.get(current_muscle, 0) + 1
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

print(f"\nMuscles sous le plancher positionnel (par séance) : {len(below_floor)}")
for b in below_floor[:15]:
    print(" -", b)

print(f"\nDoublons de FAMILLE de mouvement (ex: 2x développé couché) : {len(family_dupes)}")
for d in family_dupes[:15]:
    print(" -", d)

sys.exit(1 if (errors or below_floor or family_dupes) else 0)
