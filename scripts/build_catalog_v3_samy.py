# -*- coding: utf-8 -*-
"""
Reconstruction du catalogue d'exercices (v3) à partir de la liste exacte
fournie par Samy (hors 24 phases, prompt de refonte finale) :
scripts/liste_exercices_samy.txt — organisée par muscle puis par portion
anatomique précise (ex : PECTORAUX > Haut/Milieu/Bas des pecs), 365 exercices
réels et distincts, aucune duplication artificielle.

Deux exclusions explicites de Samy, déjà appliquées directement dans le
fichier texte source (pas ici) :
  - tous les "développé décliné" (barre/haltères/Smith) retirés des pecs ;
  - "Développé militaire debout à la barre (OHP)" retiré des épaules (on ne
    garde que haltères/machine pour le développé épaules debout/assis).

Ce script REMPLACE le catalogue v2 (486 exercices, scripts/build_professional_
catalog.py) par ce nouveau catalogue v3 (365 exercices), à la demande de
Samy : "voici la liste de tous les exercices" — une liste qu'il a lui-même
entièrement écrite et priorisée, plus précise et plus rigoureusement
organisée par portion anatomique que la v2.

Nouveauté demandée : chaque fiche porte maintenant un champ
`portion_anatomique` (portion précise du muscle travaillée, ex: "Haut des
pecs") en plus des 13 champs de métadonnées déjà existants. La "qualité
travaillée" (force/hypertrophie/endurance/explosivité) demandée par Samy est
déjà portée par `objectifs_adaptes` (5 clés, 0-10) — calculée ici par
archétype plutôt que réinventée comme un nouveau champ séparé.
"""
import json
import os
import re
import unicodedata

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_TXT = os.path.join(PROJECT_ROOT, "scripts", "liste_exercices_samy.txt")
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "data", "exercise_enrichment.json")
BACKUP_V2_PATH = os.path.join(PROJECT_ROOT, "data", "exercise_enrichment_v2_486_backup.json")


def slugify(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    n = re.sub(r"[^a-zA-Z0-9]+", "_", n).strip("_").lower()
    return n


# --------------------------------------------------------------------------
# 1) Parsing du fichier texte source -> {muscle_header: {portion: [noms]}}
# --------------------------------------------------------------------------

def parse_source():
    with open(SOURCE_TXT, encoding="utf-8") as f:
        lines = [l.rstrip() for l in f if l.strip()]

    data = {}
    muscle = None
    portion = None
    for l in lines:
        m_muscle = re.match(r"^\d+\.\s+([A-ZÀ-Ü].*)$", l)
        if m_muscle and not re.match(r"^\d+\.\t", l):
            muscle = m_muscle.group(1).strip()
            data[muscle] = {}
            portion = None
            continue
        m_portion = re.match(r"^([A-Z])\.\s+(.*)$", l)
        if m_portion:
            portion = m_portion.group(2).strip().rstrip("—-").strip()
            data[muscle][portion] = []
            continue
        m_item = re.match(r"^\d+\.\t(.*)$", l)
        if m_item:
            data[muscle][portion].append(m_item.group(1).strip())
    return data


MUSCLE_HEADER_TO_PRINCIPAL = {
    "PECTORAUX": "pecs",
    "DOS": "dos",
    "EPAULES": "epaules",
    "TRICEPS": "triceps",
    "BICEPS": "biceps",
    "ABDOMINAUX": "abdos",
    "FESSIERS": "fessiers",
    "QUADRICEPS": "quadriceps",
    "ISCHIO-JAMBIERS": "ischio",
    "MOLLETS": "mollets",
}

# Portion anatomique -> libellé propre et court (affiché à l'utilisateur).
PORTION_LABELS = {
    "Haut des pecs (Faisceau claviculaire)": "Haut des pecs",
    "Milieu des pecs (Faisceau sterno-costal)": "Milieu des pecs",
    "Bas des pecs (Faisceau abdominal) — [EXCLU : développé décliné toutes variantes]": "Bas des pecs",
    "Grand Dorsal (Largeur du dos)": "Grand dorsal",
    "Trapèzes & Rhomboïdes (Épaisseur du dos)": "Trapèzes & rhomboïdes",
    "Lombaires & Érecteurs du rachis": "Lombaires & érecteurs du rachis",
    "Deltoide Anterieur (Avant) — [EXCLU : Développé militaire debout à la barre (OHP) — on ne garde que haltère/machine]": "Deltoïde antérieur",
    "Deltoide Lateral (Cote)": "Deltoïde latéral",
    "Deltoide Posterieur (Arriere)": "Deltoïde postérieur",
    "Chef Long (Partie interne/arriere)": "Chef long (triceps)",
    "Chefs Lateral et Medial (Partie externe et mediane)": "Chefs latéral & médial (triceps)",
    "Chef Court (Partie interne)": "Chef court (biceps)",
    "Chef Long (Partie externe, \"Bosse\")": "Chef long (biceps)",
    "Brachial et Avant-bras": "Brachial & avant-bras",
    "Grand Droit (Haut et Bas des abdos)": "Grand droit (abdos)",
    "Obliques": "Obliques",
    "Grand Fessier (Volume principal)": "Grand fessier",
    "Moyen et Petit Fessier (Hanches, Galbe superieur)": "Moyen & petit fessier",
    "Quadriceps": "Quadriceps",
    "Ischio-jambiers": "Ischio-jambiers",
    "Mollets et Adducteurs": "Mollets & adducteurs",
}


# --------------------------------------------------------------------------
# 2) Inférence équipement (mots-clés du nom -> vocabulaire fermé du moteur :
#    barre/haltere/machine/poids_du_corps/elastique — cf. logic/recommendation/
#    filters.py, jamais d'autre mot-clé, sous peine de casser le filtrage dur
#    par accès matériel qui vient d'être ajouté à cette même phase).
# --------------------------------------------------------------------------

# Corrections ciblées, vérifiées à la main après un premier passage de
# l'inférence générique (audit : toutes les fiches retombées sur le repli
# "haltere" sans mot-clé haltère/kettlebell/disque explicite dans le nom —
# certaines l'étaient à raison, par exemple "Curl marteau en travers du
# corps" qui n'a pas d'autre équipement possible ; d'autres non, corrigées
# ici explicitement plutôt que de complexifier encore l'heuristique
# générique au risque d'introduire de nouveaux angles morts).
EQUIPMENT_OVERRIDES = {
    "lat pulldown": {"machine"},
    "triangle v-bar": {"machine"},
    "barre double poignée": {"machine"},
    "deficit deadlift": {"barre"},
    "paused deadlift": {"barre"},
    "board press (développé couché amplitude réduite) prise serrée": {"barre"},
    "curl au banc larry scott prise serrée": {"barre"},
    "reverse spider curl": {"barre"},
    "captain's chair": {"machine", "poids_du_corps"},
    "relevé de bassin sur banc incliné avec lest aux chevilles": {"haltere", "poids_du_corps"},
    "crunch oblique lesté sur banc décliné": {"haltere", "poids_du_corps"},
    "soulevé de terre jambes tendues depuis un déficit": {"barre"},
    "extension des mollets à la presse horizontale": {"machine"},
    # Corrigé : le mot "leg curl" déclenchait à tort le mot-clé "machine",
    # alors que cette variante précise se fait au sol/sur banc avec un
    # haltère serré entre les pieds, sans aucune machine.
    "leg curl avec haltère serré entre les pieds": {"haltere"},
}


def infer_equipment(name):
    n = name.lower()

    for cle, forced in EQUIPMENT_OVERRIDES.items():
        if cle in n:
            return sorted(forced)

    equip = set()

    if "smith" in n:
        equip.update({"machine", "barre"})

    if any(k in n for k in (
        "poulie", "câble", "cable", "corde", "woodchopper", "pallof",
        "crossover", "cross-over", "cross over",
    )):
        equip.add("machine")

    if any(k in n for k in (
        "machine", "presse à cuisses", "leg press", "hack squat",
        "leg extension", "leg curl", "pec deck", "abducteurs", "adducteurs",
        "belt squat", "torso rotation", "extension lombaire guidée",
        "reverse hack squat", "pendulum squat", "don key calf raise",
        "guidée", "guidé",
    )):
        equip.add("machine")

    if "landmine" in n:
        equip.add("barre")

    if any(k in n for k in ("haltère", "haltères", "kettlebell", "disque")):
        equip.add("haltere")

    if any(k in n for k in (
        " barre", "barre ", "barre)", "barre,", " ez", "trap bar", "hex bar",
        "ssb", "safety bar", "olympique", "landmine",
    )):
        equip.add("barre")

    if any(k in n for k in ("élastique", "bande de résistance", "résistance")):
        equip.add("elastique")

    if any(k in n for k in (
        "poids du corps", "suspendu", "assisté", "sit-up", "gainage",
        "plank", "dragon flag", "nordic hamstring", "v-up", "jackknife",
        "farmer walk", "marche du fermier", "marche de la valise",
        "suitcase carry", "monster walk", "pinch grip",
    )):
        equip.add("poids_du_corps")

    if not equip:
        equip.add("haltere")

    return sorted(equip)


UNILATERAL_MOTS = (
    "unilatéral", "unilatérale", "unilateral", "single-leg", "single-arm",
    "single leg", "single arm", "un bras", "une jambe", "alterné", "alternée",
)


def is_unilateral(name):
    n = name.lower()
    return any(m in n for m in UNILATERAL_MOTS)


# --------------------------------------------------------------------------
# 3) Archétypes par (muscle, portion) : pattern/movement_type/joint_stress de
#    base/objectifs_adaptes ("qualité travaillée")/scores hypertrophiques,
#    affinés ensuite au cas par cas via des mots-clés du nom (isolation vs
#    composé, lourd vs léger, explosif...).
# --------------------------------------------------------------------------

# objectifs_adaptes : force / hypertrophie / endurance_musculaire /
# perte_de_gras / explosivite (5 clés valides, 0-10).

ARCHETYPE_COMPOSE_LOURD = dict(
    pattern="presse", movement_type="push", technical_complexity=3,
    stability_demand="modere", difficulty_level="intermediaire",
    objectifs_adaptes={"force": 8, "hypertrophie": 7, "endurance_musculaire": 2, "perte_de_gras": 4, "explosivite": 5},
    score_tension_mecanique=8, score_contraction_max=5, potentiel_hypertrophique=8,
)
ARCHETYPE_ISOLATION = dict(
    pattern="isolation", movement_type="rotation", technical_complexity=2,
    stability_demand="faible", difficulty_level="debutant",
    objectifs_adaptes={"force": 2, "hypertrophie": 8, "endurance_musculaire": 5, "perte_de_gras": 5, "explosivite": 1},
    score_tension_mecanique=4, score_contraction_max=8, potentiel_hypertrophique=8,
)
ARCHETYPE_TIRAGE = dict(
    pattern="tirage", movement_type="pull", technical_complexity=3,
    stability_demand="modere", difficulty_level="intermediaire",
    objectifs_adaptes={"force": 7, "hypertrophie": 8, "endurance_musculaire": 3, "perte_de_gras": 4, "explosivite": 3},
    score_tension_mecanique=7, score_contraction_max=6, potentiel_hypertrophique=8,
)
ARCHETYPE_HINGE_LOURD = dict(
    pattern="hinge", movement_type="hinge", technical_complexity=4,
    stability_demand="eleve", difficulty_level="avance",
    objectifs_adaptes={"force": 9, "hypertrophie": 6, "endurance_musculaire": 2, "perte_de_gras": 4, "explosivite": 4},
    score_tension_mecanique=9, score_contraction_max=4, potentiel_hypertrophique=7,
)
ARCHETYPE_SQUAT_LOURD = dict(
    pattern="squat", movement_type="squat", technical_complexity=4,
    stability_demand="eleve", difficulty_level="avance",
    objectifs_adaptes={"force": 9, "hypertrophie": 7, "endurance_musculaire": 2, "perte_de_gras": 4, "explosivite": 5},
    score_tension_mecanique=9, score_contraction_max=5, potentiel_hypertrophique=8,
)
ARCHETYPE_LUNGE = dict(
    pattern="fente", movement_type="lunge", technical_complexity=3,
    stability_demand="eleve", difficulty_level="intermediaire",
    objectifs_adaptes={"force": 6, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 5, "explosivite": 3},
    score_tension_mecanique=6, score_contraction_max=6, potentiel_hypertrophique=7,
)
ARCHETYPE_CARRY = dict(
    pattern="portage", movement_type="carry", technical_complexity=2,
    stability_demand="eleve", difficulty_level="intermediaire",
    objectifs_adaptes={"force": 6, "hypertrophie": 3, "endurance_musculaire": 8, "perte_de_gras": 6, "explosivite": 1},
    score_tension_mecanique=5, score_contraction_max=3, potentiel_hypertrophique=4,
)
ARCHETYPE_CORE_DYNAMIQUE = dict(
    pattern="flexion_tronc", movement_type="rotation", technical_complexity=2,
    stability_demand="modere", difficulty_level="debutant",
    objectifs_adaptes={"force": 3, "hypertrophie": 5, "endurance_musculaire": 7, "perte_de_gras": 6, "explosivite": 2},
    score_tension_mecanique=4, score_contraction_max=7, potentiel_hypertrophique=6,
)
ARCHETYPE_CORE_STATIQUE = dict(
    pattern="gainage", movement_type="isometrique", technical_complexity=2,
    stability_demand="eleve", difficulty_level="debutant",
    objectifs_adaptes={"force": 3, "hypertrophie": 2, "endurance_musculaire": 9, "perte_de_gras": 5, "explosivite": 0},
    score_tension_mecanique=3, score_contraction_max=6, potentiel_hypertrophique=3,
)
ARCHETYPE_MOLLET_ADDUCTEUR = dict(
    pattern="isolation", movement_type="rotation", technical_complexity=1,
    stability_demand="faible", difficulty_level="debutant",
    objectifs_adaptes={"force": 2, "hypertrophie": 7, "endurance_musculaire": 6, "perte_de_gras": 4, "explosivite": 1},
    score_tension_mecanique=4, score_contraction_max=7, potentiel_hypertrophique=7,
)
ARCHETYPE_SHRUG = dict(
    pattern="isolation", movement_type="rotation", technical_complexity=1,
    stability_demand="faible", difficulty_level="debutant",
    objectifs_adaptes={"force": 4, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 3, "explosivite": 1},
    score_tension_mecanique=5, score_contraction_max=7, potentiel_hypertrophique=6,
)
ARCHETYPE_ABDUCTION = dict(
    pattern="isolation", movement_type="rotation", technical_complexity=1,
    stability_demand="faible", difficulty_level="debutant",
    objectifs_adaptes={"force": 2, "hypertrophie": 7, "endurance_musculaire": 5, "perte_de_gras": 4, "explosivite": 1},
    score_tension_mecanique=3, score_contraction_max=7, potentiel_hypertrophique=6,
)

# (muscle_header, portion_texte_source) -> archétype de base.
ARCHETYPE_PAR_PORTION = {
    ("PECTORAUX", "Haut des pecs (Faisceau claviculaire)"): ARCHETYPE_COMPOSE_LOURD,
    ("PECTORAUX", "Milieu des pecs (Faisceau sterno-costal)"): ARCHETYPE_COMPOSE_LOURD,
    ("PECTORAUX", "Bas des pecs (Faisceau abdominal) — [EXCLU : développé décliné toutes variantes]"): ARCHETYPE_ISOLATION,
    ("DOS", "Grand Dorsal (Largeur du dos)"): ARCHETYPE_TIRAGE,
    ("DOS", "Trapèzes & Rhomboïdes (Épaisseur du dos)"): ARCHETYPE_TIRAGE,
    ("DOS", "Lombaires & Érecteurs du rachis"): ARCHETYPE_HINGE_LOURD,
    ("EPAULES", "Deltoide Anterieur (Avant) — [EXCLU : Développé militaire debout à la barre (OHP) — on ne garde que haltère/machine]"): ARCHETYPE_COMPOSE_LOURD,
    ("EPAULES", "Deltoide Lateral (Cote)"): ARCHETYPE_ISOLATION,
    ("EPAULES", "Deltoide Posterieur (Arriere)"): ARCHETYPE_ISOLATION,
    ("TRICEPS", "Chef Long (Partie interne/arriere)"): ARCHETYPE_ISOLATION,
    ("TRICEPS", "Chefs Lateral et Medial (Partie externe et mediane)"): ARCHETYPE_ISOLATION,
    ("BICEPS", "Chef Court (Partie interne)"): ARCHETYPE_ISOLATION,
    ("BICEPS", "Chef Long (Partie externe, \"Bosse\")"): ARCHETYPE_ISOLATION,
    ("BICEPS", "Brachial et Avant-bras"): ARCHETYPE_ISOLATION,
    ("ABDOMINAUX", "Grand Droit (Haut et Bas des abdos)"): ARCHETYPE_CORE_DYNAMIQUE,
    ("ABDOMINAUX", "Obliques"): ARCHETYPE_CORE_DYNAMIQUE,
    ("FESSIERS", "Grand Fessier (Volume principal)"): ARCHETYPE_HINGE_LOURD,
    ("FESSIERS", "Moyen et Petit Fessier (Hanches, Galbe superieur)"): ARCHETYPE_ABDUCTION,
    ("QUADRICEPS", "Quadriceps"): ARCHETYPE_SQUAT_LOURD,
    ("ISCHIO-JAMBIERS", "Ischio-jambiers"): ARCHETYPE_HINGE_LOURD,
    ("MOLLETS", "Mollets et Adducteurs"): ARCHETYPE_MOLLET_ADDUCTEUR,
}


def affiner_archetype(muscle_header, portion_texte, nom, base):
    """Ajustements ciblés par mots-clés du nom, au-dessus de l'archétype de
    portion : distingue isolation vs composé, lourd vs léger, fente/carry/
    gainage spécifiques, même à l'intérieur d'une portion majoritairement
    "presse" ou "tirage"."""
    n = nom.lower()
    arche = dict(base)
    arche["objectifs_adaptes"] = dict(base["objectifs_adaptes"])

    if any(k in n for k in ("écarté", "ecarte", "fly", "reverse fly", "pec deck", "pullover", "pull-over")):
        arche = dict(ARCHETYPE_ISOLATION)
        arche["objectifs_adaptes"] = dict(ARCHETYPE_ISOLATION["objectifs_adaptes"])
        arche["pattern"] = "isolation"

    if any(k in n for k in ("shrug", "haussement")):
        arche = dict(ARCHETYPE_SHRUG)
        arche["objectifs_adaptes"] = dict(ARCHETYPE_SHRUG["objectifs_adaptes"])

    if any(k in n for k in ("fente", "lunge", "step-up", "step up", "split squat", "bulgar")):
        arche = dict(ARCHETYPE_LUNGE)
        arche["objectifs_adaptes"] = dict(ARCHETYPE_LUNGE["objectifs_adaptes"])

    if any(k in n for k in ("farmer walk", "marche du fermier", "marche de la valise", "suitcase carry", "monster walk")):
        arche = dict(ARCHETYPE_CARRY)
        arche["objectifs_adaptes"] = dict(ARCHETYPE_CARRY["objectifs_adaptes"])

    if any(k in n for k in ("plank", "gainage", "pallof", "dragon flag", "hold", "maintien")):
        arche = dict(ARCHETYPE_CORE_STATIQUE)
        arche["objectifs_adaptes"] = dict(ARCHETYPE_CORE_STATIQUE["objectifs_adaptes"])

    if any(k in n for k in ("hip thrust", "kas glute bridge", "glute bridge")):
        arche["pattern"] = "hinge"
        arche["movement_type"] = "hinge"

    if any(k in n for k in ("soulevé de terre", "deadlift", "good morning", "rdl", "romanian")):
        arche["pattern"] = "hinge"
        arche["movement_type"] = "hinge"
        arche["objectifs_adaptes"]["force"] = max(arche["objectifs_adaptes"].get("force", 0), 8)

    if any(k in n for k in ("squat", "hack squat", "presse à cuisses", "leg press", "goblet")):
        if "leg press" not in n and "presse à cuisses" not in n:
            arche["pattern"] = "squat"
            arche["movement_type"] = "squat"

    if "extension" in n and ("mollet" in n or "leg extension" in n or "genou" in n):
        arche["pattern"] = "isolation"
        arche["movement_type"] = "rotation"

    if "leg curl" in n or "glute ham raise" in n or "nordic hamstring" in n:
        arche["pattern"] = "isolation"
        arche["movement_type"] = "rotation"

    if any(k in n for k in ("upright row", "rowing vertical")):
        arche["pattern"] = "tirage"
        arche["movement_type"] = "pull"

    if any(k in n for k in ("kickback", "curl", "extension triceps", "élévation", "elevation", "y-raise", "w-raise",
                             "face pull", "oiseau", "abduction", "adduction")):
        arche["pattern"] = "isolation"
        arche["movement_type"] = "rotation"
        arche["technical_complexity"] = min(arche.get("technical_complexity", 2), 2)
        arche["stability_demand"] = "faible"

    if any(k in n for k in ("développé couché prise serrée", "floor press prise serrée", "board press",
                             "close-grip", "développé décliné prise serrée")):
        # Volontairement PAS "prise serrée" seul : ce mot-clé apparaît aussi
        # sur des curls biceps ("Curl à la barre EZ prise serrée"), qui ne
        # sont pas des mouvements de développé — cf. audit qualité catalogue.
        arche["pattern"] = "presse"
        arche["movement_type"] = "push"

    if any(k in n for k in ("rotation du buste", "woodchopper", "russian twist", "windmill", "twist")):
        arche["pattern"] = "rotation"
        arche["movement_type"] = "rotation"

    if any(k in n for k in ("side bend", "flexion latérale", "side plank", "gainage latéral")):
        arche["pattern"] = "flexion_laterale"
        arche["movement_type"] = "isometrique" if "plank" in n or "gainage" in n else "rotation"

    if any(k in n for k in ("wrist", "poignet", "pinch grip", "wrist roller")):
        arche["pattern"] = "isolation"
        arche["movement_type"] = "rotation"
        arche["objectifs_adaptes"]["endurance_musculaire"] = max(arche["objectifs_adaptes"].get("endurance_musculaire", 0), 7)

    return arche


# --------------------------------------------------------------------------
# 4) Morphologie adaptée — heuristique simple par pattern (mêmes 9 clés
#    validées que la v2, cf. logic/exercise_catalog_enrichment.MORPHOLOGIE_
#    KEYS_VALIDES). Ne fait AUCUNE supposition hasardeuse : uniquement les
#    corrélations pattern/morphologie déjà documentées dans le moteur
#    (biomechanics.py, score_morphologie).
# --------------------------------------------------------------------------

def morphologie_pour(pattern, muscle_principal):
    m = {}
    if pattern in ("squat", "hinge"):
        m["jambes_longues"] = 6
        m["jambes_courtes"] = 3
    if pattern == "presse" and muscle_principal in ("pecs", "epaules", "triceps"):
        m["bras_longs"] = 3
        m["bras_courts"] = 6
    if pattern in ("tirage", "isolation") and muscle_principal in ("dos", "biceps"):
        m["bras_longs"] = 6
        m["bras_courts"] = 3
    if muscle_principal == "epaules":
        m["epaules_larges"] = 6
        m["epaules_etroites"] = 4
    return m


# --------------------------------------------------------------------------
# 5) Génération des fiches
# --------------------------------------------------------------------------

def joint_stress_pour(muscle_principal, pattern, nom, movement_type=None, equipment=None):
    """Stress articulaire estimé, par zone : 0 aucun, 1 modéré, 2 élevé,
    3 très élevé.

    C'EST LE SEUL CRITÈRE D'EXCLUSION EN CAS DE BLESSURE DÉCLARÉE
    (cf. logic/recommendation/filters.py::_blessure_exclusion_reason) : une
    zone absente de ce dict n'a JAMAIS d'effet, quelle que soit la gravité de
    la douleur déclarée par l'utilisateur.

    Retour Samy (vérification demandée après activation du catalogue) : la
    version précédente ne couvrait qu'une poignée de mots-clés et laissait 273
    fiches sur 365 entièrement vides. Mesure faite avant correction : un
    utilisateur déclarant une DOULEUR INVALIDANTE à l'épaule ne voyait que
    6 exercices exclus sur 365 — le développé militaire, les dips et les
    développés lourds lui étaient toujours prescrits. Le trou existait déjà
    dans le générateur, mais il était masqué tant que la production tournait
    sur l'ancien catalogue de 111 exercices, lui renseigné.

    Principe retenu : partir du schéma de mouvement (qui porte l'essentiel de
    l'information mécanique), puis affiner par le matériel et le nom. Une
    estimation par règles ne remplace pas une revue exercice par exercice,
    mais elle vaut infiniment mieux qu'un champ vide — et la sécurité doit
    pencher du côté prudent : en cas de doute, on déclare le stress plutôt que
    de l'ignorer.

    Les clés sont celles attendues par filters.ZONE_LABEL_TO_JOINT_STRESS_KEY :
    epaule, dos_lombaire, genou, cheville, poignet, coude.
    """
    n = nom.lower()
    equipment = equipment or []
    js = {}

    def poser(zone, valeur):
        js[zone] = max(js.get(zone, 0), valeur)

    libre = any(e in ("barre", "haltere") for e in equipment)
    guide = any(e in ("machine", "poulie", "smith") for e in equipment)

    # ---------- Épaule ----------
    # Tout ce qui pousse au-dessus de la tête, tire en arrière du plan du
    # corps, ou met l'épaule en rotation externe/extension forcée.
    if movement_type == "push" or pattern in ("developpe", "presse"):
        poser("epaule", 1)
    if any(k in n for k in ("militaire", "overhead", "au-dessus", "développé épaules",
                            "arnold", "nuque", "derrière la nuque", "push press",
                            "élévation", "elevation", "shoulder press", "landmine press")):
        poser("epaule", 2)
    if any(k in n for k in ("dips", "développé couché", "developpe couche", "bench",
                            "écarté", "ecarte", "fly", "pull-over", "pullover",
                            "papillon", "pec deck")):
        # Amplitude d'étirement importante à l'épaule, surtout en charge libre.
        poser("epaule", 2 if libre else 1)
    if any(k in n for k in ("traction", "pull-up", "chin-up", "tirage vertical",
                            "lat pulldown", "muscle-up")):
        poser("epaule", 2)
    if muscle_principal in ("pecs", "epaules") and libre:
        poser("epaule", 2)
    if muscle_principal in ("pecs", "epaules", "dos") and guide and "epaule" not in js:
        poser("epaule", 1)

    # ---------- Dos / lombaires ----------
    if movement_type == "hinge" or pattern in ("hinge", "rdl", "souleve_de_terre"):
        poser("dos_lombaire", 2)
    if any(k in n for k in ("soulevé de terre", "souleve de terre", "deadlift",
                            "good morning", "extension du buste", "hyperextension",
                            "banc 45", "lombaire", "rack pull", "snatch", "clean")):
        poser("dos_lombaire", 3 if libre else 2)
    if any(k in n for k in ("rowing", "row ", "meadow", "pendlay", "t-bar", "yates")):
        # Un rowing buste penché maintient les lombaires en isométrie sous
        # charge ; un rowing appuyé sur banc les décharge.
        buste_soutenu = any(k in n for k in ("appui", "supported", "banc", "chest"))
        poser("dos_lombaire", 1 if buste_soutenu else 2)
    if movement_type == "squat" or pattern == "squat":
        poser("dos_lombaire", 2 if libre else 1)
    if any(k in n for k in ("crunch", "sit-up", "relevé de jambes", "releve de jambes",
                            "dragon flag", "hollow")):
        poser("dos_lombaire", 1)
    if "smith" in n or "presse" in n or "hack squat" in n:
        poser("dos_lombaire", 1)

    # ---------- Genou ----------
    if movement_type in ("squat", "lunge") or pattern in ("squat", "fente", "presse"):
        poser("genou", 2)
    if any(k in n for k in ("squat", "fente", "lunge", "presse à cuisses", "leg press",
                            "hack squat", "step-up", "montée de banc", "bulgare",
                            "pistol", "sissy", "belt squat", "split squat")):
        poser("genou", 2)
    if any(k in n for k in ("sissy squat", "profond", "deep", "saut", "jump", "pliométrie",
                            "plyo", "box jump")):
        poser("genou", 3)
    if "leg extension" in n or "extension des jambes" in n or "leg curl" in n:
        # Cisaillement rotulien sur le leg extension, tension sur l'insertion
        # postérieure au leg curl : modéré, pas anodin.
        poser("genou", 2 if "extension" in n else 1)
    if muscle_principal in ("quadriceps", "fessiers") and "genou" not in js:
        poser("genou", 1)

    # ---------- Cheville ----------
    if muscle_principal == "mollets" or "mollet" in n or "calf" in n:
        poser("cheville", 2)
    if any(k in n for k in ("saut", "jump", "corde à sauter", "pliométrie", "plyo",
                            "fente", "lunge", "step-up")):
        poser("cheville", 2)
    if movement_type in ("squat", "lunge"):
        poser("cheville", 1)

    # ---------- Poignet ----------
    if any(k in n for k in ("wrist", "poignet", "curl inversé", "reverse curl",
                            "prise serrée", "close grip", "pompes", "push-up",
                            "front squat", "barre au front", "skull")):
        poser("poignet", 2)
    if any(k in n for k in ("barre ez", "barre z", "prise neutre", "corde")):
        # Matériel justement choisi pour ménager le poignet.
        poser("poignet", 1)
    elif "barre" in equipment:
        poser("poignet", 1)

    # ---------- Coude ----------
    if muscle_principal in ("biceps", "triceps"):
        poser("coude", 2)
    if any(k in n for k in ("skull", "barre au front", "extension nuque", "overhead extension",
                            "dips", "prise serrée", "close grip", "preacher", "pupitre")):
        poser("coude", 2)

    return js


def build_fiches():
    data = parse_source()
    fiches = []
    vus = {}

    for muscle_header, portions in data.items():
        muscle_principal = MUSCLE_HEADER_TO_PRINCIPAL[muscle_header]
        for portion_texte, noms in portions.items():
            portion_label = PORTION_LABELS.get(portion_texte, portion_texte)
            base_archetype = ARCHETYPE_PAR_PORTION[(muscle_header, portion_texte)]

            for nom in noms:
                arche = affiner_archetype(muscle_header, portion_texte, nom, base_archetype)
                equipment = infer_equipment(nom)
                unilateral = is_unilateral(nom)
                pattern = arche["pattern"]

                # "presse" collision : logic/exercise_quality.py (heuristique de
                # revue, phase 14) associe historiquement le pattern "presse"
                # UNIQUEMENT aux quadriceps (presse à cuisses, catalogue legacy,
                # logic/exercises_db.py) — un faux positif "muscle_principal
                # incompatible" apparaîtrait sinon pour tout développé pecs/
                # épaules/triceps prise serrée. Renommé vers un pattern propre
                # à chaque muscle, sans effet sur la validation/le scoring (le
                # champ "pattern" n'a aucune valeur imposée, cf. exercise_
                # catalog_validator.py) ni sur la diversité de séance (exercise_
                # order.py raisonne sur movement_type, jamais sur ce libellé).
                if pattern == "presse":
                    pattern = {
                        "pecs": "developpe",
                        "epaules": "developpe_militaire",
                        "triceps": "close_grip_press",
                    }.get(muscle_principal, pattern)

                # Même collision pour "squat" : réservé aux quadriceps dans le
                # catalogue legacy. Certains squats de la liste de Samy sont
                # volontairement classés sous fessiers/mollets (ex: squat
                # bulgare ciblé fessiers, Cossack squat ciblé adducteurs) —
                # pattern renommé pour éviter le même faux positif, sans
                # rien changer côté moteur (movement_type="squat" conservé).
                if pattern == "squat" and muscle_principal != "quadriceps":
                    pattern = f"squat_{muscle_principal}"
                exercise_id = f"{slugify(nom)}_{muscle_principal}"
                if exercise_id in vus:
                    vus[exercise_id] += 1
                    exercise_id = f"{exercise_id}_{vus[exercise_id]}"
                else:
                    vus[exercise_id] = 1

                fiche = {
                    "exercise_id": exercise_id,
                    "name": nom,
                    "family": muscle_principal,
                    "pattern": pattern,
                    "movement_type": arche["movement_type"],
                    "equipment": equipment,
                    "muscle_principal": muscle_principal,
                    "muscles_secondaires": [],
                    "unilateral": unilateral,
                    "difficulty_level": arche["difficulty_level"],
                    "joint_stress": joint_stress_pour(
                        muscle_principal, pattern, nom,
                        movement_type=arche.get("movement_type"),
                        equipment=equipment,
                    ),
                    "technical_complexity": arche["technical_complexity"],
                    "stability_demand": arche["stability_demand"],
                    "morphologie_adaptee": morphologie_pour(pattern, muscle_principal),
                    "objectifs_adaptes": arche["objectifs_adaptes"],
                    "score_tension_mecanique": arche["score_tension_mecanique"],
                    "score_contraction_max": arche["score_contraction_max"],
                    "potentiel_hypertrophique": arche["potentiel_hypertrophique"],
                    "substitutes": [],
                    "contre_indications": [],
                    "actif": True,
                    "needs_review": True,
                    # Nouveau champ demandé par Samy (prompt hors 24 phases) :
                    # portion anatomique précise du muscle travaillée.
                    "portion_anatomique": portion_label,
                }
                fiches.append(fiche)

    # Substituts : autres exercice_id du même muscle_principal + pattern
    # (même logique que scripts/build_professional_catalog.py, v2).
    par_cle = {}
    for f in fiches:
        par_cle.setdefault((f["muscle_principal"], f["pattern"]), []).append(f["exercise_id"])
    for f in fiches:
        autres = [eid for eid in par_cle[(f["muscle_principal"], f["pattern"])] if eid != f["exercise_id"]]
        f["substitutes"] = autres[:5]

    return fiches


def main():
    fiches = build_fiches()

    if os.path.exists(OUTPUT_JSON) and not os.path.exists(BACKUP_V2_PATH):
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            ancien = f.read()
        with open(BACKUP_V2_PATH, "w", encoding="utf-8") as f:
            f.write(ancien)
        print(f"Sauvegarde de l'ancien catalogue (v2) -> {BACKUP_V2_PATH}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"exercises": fiches}, f, ensure_ascii=False, indent=2)

    print(f"Nouveau catalogue v3 écrit -> {OUTPUT_JSON} ({len(fiches)} exercices)")
    par_muscle = {}
    for f in fiches:
        par_muscle[f["muscle_principal"]] = par_muscle.get(f["muscle_principal"], 0) + 1
    for muscle, n in sorted(par_muscle.items()):
        print(f"  {muscle:12s} : {n}")


if __name__ == "__main__":
    main()
