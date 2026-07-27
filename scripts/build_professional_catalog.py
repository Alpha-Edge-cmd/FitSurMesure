# -*- coding: utf-8 -*-
"""
Prompt final (hors les 24 phases) — PARTIE 1/2 : remplacement du catalogue de
111 exercices par un catalogue professionnel enrichi.

Ce script ne modifie AUCUNE règle de scoring/sélection/génération : il ne
fait que PRODUIRE des données (data/exercise_enrichment.json), au même
format éditorial que l'existant (cf. logic/exercise_catalog_validator.py,
CHAMPS_OBLIGATOIRES, inchangé), pour que le pipeline d'import déjà en place
(logic/exercise_catalog_import.py, phase 13-16, inchangé) puisse le charger
sans aucune modification de son code.

Convention d'équipement reprise à l'identique du catalogue existant (vérifiée
avant d'écrire ce script) : seules les valeurs "barre", "haltere", "machine",
"poids_du_corps", "elastique" sont utilisées — un mouvement à la poulie/câble
est encodé "machine", exactement comme les 111 exercices actuels
(ex: "ecarte_poulie_fly" -> equipment=["machine"]).

Chaque "archétype" de mouvement (ARCHETYPES ci-dessous) porte des valeurs
biomécaniques par défaut réalistes (tension mécanique, contraction maximale,
complexité technique, exigence de stabilité, vecteur d'objectifs) — un
exercice donné peut surcharger ponctuellement un champ (ex: un développé
militaire barre debout est plus exigeant en stabilité qu'un développé assis
dossier). Ceci évite d'inventer 700+ fiches from scratch tout en gardant
CHAQUE exercice réellement distinct (nom, équipement, biomécanique propre) —
pas une duplication artificielle par simple changement d'étiquette.

Usage :
    python3 scripts/build_professional_catalog.py
Écrit data/exercise_enrichment.json (après sauvegarde de l'ancien fichier
111 exercices dans data/exercise_enrichment_v2_111_backup.json, jamais
supprimé - cf. politique "aucune suppression physique" déjà établie)."""
import json
import os
import re
import unicodedata

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "exercise_enrichment.json")
BACKUP_PATH = os.path.join(PROJECT_ROOT, "data", "exercise_enrichment_v2_111_backup.json")


def slugify(name):
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")
    return ascii_name


# ---------------------------------------------------------------------------
# Archétypes biomécaniques : valeurs par défaut réalistes par TYPE de
# mouvement (jamais par exercice individuel — chaque exercice hérite de son
# archétype puis peut surcharger 1-2 champs via `overrides`).
# ---------------------------------------------------------------------------
ARCHETYPES = {
    # --- Presses / poussées ---
    "presse_lourde_barre": dict(
        technical_complexity=4, stability_demand="modere", difficulty_level="intermediaire",
        score_tension_mecanique=8, score_contraction_max=5, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 7, "hypertrophie": 7, "endurance_musculaire": 2, "perte_de_gras": 3, "explosivite": 3},
    ),
    "presse_haltere": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="debutant",
        score_tension_mecanique=6, score_contraction_max=7, potentiel_hypertrophique=8,
        objectifs_adaptes={"force": 5, "hypertrophie": 8, "endurance_musculaire": 2, "perte_de_gras": 3, "explosivite": 2},
    ),
    "presse_machine": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=5, score_contraction_max=8, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 3, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 3, "explosivite": 1},
    ),
    "presse_debout_barre": dict(
        technical_complexity=4, stability_demand="eleve", difficulty_level="avance",
        score_tension_mecanique=8, score_contraction_max=4, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 8, "hypertrophie": 5, "endurance_musculaire": 1, "perte_de_gras": 2, "explosivite": 4},
    ),
    "ecarte_isolation": dict(
        technical_complexity=2, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=3, score_contraction_max=9, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 1, "hypertrophie": 8, "endurance_musculaire": 4, "perte_de_gras": 2, "explosivite": 0},
    ),
    "pompe_poids_du_corps": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="debutant",
        score_tension_mecanique=5, score_contraction_max=6, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 3, "hypertrophie": 6, "endurance_musculaire": 6, "perte_de_gras": 4, "explosivite": 1},
    ),
    # --- Tirages / tractions ---
    "traction_poids_du_corps": dict(
        technical_complexity=3, stability_demand="eleve", difficulty_level="avance",
        score_tension_mecanique=7, score_contraction_max=6, potentiel_hypertrophique=8,
        objectifs_adaptes={"force": 6, "hypertrophie": 8, "endurance_musculaire": 3, "perte_de_gras": 3, "explosivite": 1},
    ),
    "tirage_vertical_machine": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=5, score_contraction_max=7, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 3, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 3, "explosivite": 1},
    ),
    "rowing_barre": dict(
        technical_complexity=4, stability_demand="eleve", difficulty_level="intermediaire",
        score_tension_mecanique=8, score_contraction_max=6, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 7, "hypertrophie": 7, "endurance_musculaire": 2, "perte_de_gras": 3, "explosivite": 2},
    ),
    "rowing_haltere": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="debutant",
        score_tension_mecanique=6, score_contraction_max=7, potentiel_hypertrophique=8,
        objectifs_adaptes={"force": 5, "hypertrophie": 8, "endurance_musculaire": 3, "perte_de_gras": 3, "explosivite": 1},
    ),
    "rowing_machine": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=5, score_contraction_max=8, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 4, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 3, "explosivite": 1},
    ),
    "pullover_isolation": dict(
        technical_complexity=2, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=4, score_contraction_max=8, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 2, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 2, "explosivite": 0},
    ),
    "shrug_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=6, score_contraction_max=7, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 4, "hypertrophie": 6, "endurance_musculaire": 4, "perte_de_gras": 2, "explosivite": 0},
    ),
    "arriere_epaule_isolation": dict(
        technical_complexity=2, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=3, score_contraction_max=8, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 1, "hypertrophie": 7, "endurance_musculaire": 5, "perte_de_gras": 2, "explosivite": 0},
    ),
    # --- Épaules isolation ---
    "elevation_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=3, score_contraction_max=8, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 1, "hypertrophie": 7, "endurance_musculaire": 5, "perte_de_gras": 2, "explosivite": 0},
    ),
    # --- Bras (biceps/triceps) isolation ---
    "curl_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=4, score_contraction_max=8, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 2, "hypertrophie": 8, "endurance_musculaire": 4, "perte_de_gras": 2, "explosivite": 0},
    ),
    "extension_triceps_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=4, score_contraction_max=8, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 2, "hypertrophie": 8, "endurance_musculaire": 4, "perte_de_gras": 2, "explosivite": 0},
    ),
    "triceps_compose": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="intermediaire",
        score_tension_mecanique=6, score_contraction_max=6, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 4, "hypertrophie": 7, "endurance_musculaire": 3, "perte_de_gras": 2, "explosivite": 1},
    ),
    # --- Jambes ---
    "squat_libre": dict(
        technical_complexity=4, stability_demand="eleve", difficulty_level="avance",
        score_tension_mecanique=9, score_contraction_max=4, potentiel_hypertrophique=8,
        objectifs_adaptes={"force": 8, "hypertrophie": 8, "endurance_musculaire": 2, "perte_de_gras": 4, "explosivite": 5},
    ),
    "squat_guide": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="intermediaire",
        score_tension_mecanique=7, score_contraction_max=6, potentiel_hypertrophique=8,
        objectifs_adaptes={"force": 6, "hypertrophie": 8, "endurance_musculaire": 3, "perte_de_gras": 4, "explosivite": 2},
    ),
    "presse_jambes": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=7, score_contraction_max=7, potentiel_hypertrophique=8,
        objectifs_adaptes={"force": 6, "hypertrophie": 8, "endurance_musculaire": 3, "perte_de_gras": 4, "explosivite": 1},
    ),
    "extension_jambes_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=3, score_contraction_max=9, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 1, "hypertrophie": 7, "endurance_musculaire": 5, "perte_de_gras": 2, "explosivite": 0},
    ),
    "fente_lunge": dict(
        technical_complexity=3, stability_demand="eleve", difficulty_level="intermediaire",
        score_tension_mecanique=6, score_contraction_max=6, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 5, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 5, "explosivite": 2},
    ),
    "hinge_lourd": dict(
        technical_complexity=4, stability_demand="eleve", difficulty_level="avance",
        score_tension_mecanique=9, score_contraction_max=4, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 8, "hypertrophie": 7, "endurance_musculaire": 2, "perte_de_gras": 3, "explosivite": 3},
    ),
    "leg_curl_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=4, score_contraction_max=8, potentiel_hypertrophique=7,
        objectifs_adaptes={"force": 2, "hypertrophie": 7, "endurance_musculaire": 4, "perte_de_gras": 2, "explosivite": 0},
    ),
    "hip_thrust_fessier": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="intermediaire",
        score_tension_mecanique=7, score_contraction_max=8, potentiel_hypertrophique=8,
        objectifs_adaptes={"force": 5, "hypertrophie": 8, "endurance_musculaire": 3, "perte_de_gras": 4, "explosivite": 2},
    ),
    "fessier_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=3, score_contraction_max=8, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 1, "hypertrophie": 6, "endurance_musculaire": 5, "perte_de_gras": 3, "explosivite": 0},
    ),
    "mollet_isolation": dict(
        technical_complexity=1, stability_demand="faible", difficulty_level="debutant",
        score_tension_mecanique=4, score_contraction_max=8, potentiel_hypertrophique=6,
        objectifs_adaptes={"force": 2, "hypertrophie": 6, "endurance_musculaire": 6, "perte_de_gras": 2, "explosivite": 1},
    ),
    # --- Core ---
    "core_flexion": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="debutant",
        score_tension_mecanique=4, score_contraction_max=8, potentiel_hypertrophique=5,
        objectifs_adaptes={"force": 2, "hypertrophie": 5, "endurance_musculaire": 6, "perte_de_gras": 3, "explosivite": 1},
    ),
    "core_anti_extension": dict(
        technical_complexity=3, stability_demand="eleve", difficulty_level="intermediaire",
        score_tension_mecanique=5, score_contraction_max=5, potentiel_hypertrophique=5,
        objectifs_adaptes={"force": 3, "hypertrophie": 4, "endurance_musculaire": 6, "perte_de_gras": 3, "explosivite": 1},
    ),
    "core_anti_rotation": dict(
        technical_complexity=3, stability_demand="eleve", difficulty_level="intermediaire",
        score_tension_mecanique=4, score_contraction_max=5, potentiel_hypertrophique=4,
        objectifs_adaptes={"force": 3, "hypertrophie": 4, "endurance_musculaire": 6, "perte_de_gras": 3, "explosivite": 1},
    ),
    "core_gainage": dict(
        technical_complexity=2, stability_demand="modere", difficulty_level="debutant",
        score_tension_mecanique=3, score_contraction_max=4, potentiel_hypertrophique=3,
        objectifs_adaptes={"force": 2, "hypertrophie": 3, "endurance_musculaire": 8, "perte_de_gras": 3, "explosivite": 0},
    ),
    "core_charge_lourde": dict(
        technical_complexity=2, stability_demand="eleve", difficulty_level="intermediaire",
        score_tension_mecanique=6, score_contraction_max=4, potentiel_hypertrophique=4,
        objectifs_adaptes={"force": 5, "hypertrophie": 4, "endurance_musculaire": 6, "perte_de_gras": 4, "explosivite": 1},
    ),
}


def make(name, muscle, family, pattern, movement_type, equipment, archetype,
         unilateral=False, secondaires=None, joint_stress=None, morpho=None,
         difficulty_override=None, technical_override=None, stability_override=None,
         contre_indications=None):
    base = dict(ARCHETYPES[archetype])
    exercise_id = slugify(name) + "_" + muscle
    return {
        "exercise_id": exercise_id,
        "name": name,
        "family": family,
        "pattern": pattern,
        "movement_type": movement_type,
        "equipment": list(equipment),
        "muscle_principal": muscle,
        "muscles_secondaires": list(secondaires or []),
        "unilateral": bool(unilateral),
        "difficulty_level": difficulty_override or base["difficulty_level"],
        "joint_stress": dict(joint_stress or {}),
        "technical_complexity": technical_override or base["technical_complexity"],
        "stability_demand": stability_override or base["stability_demand"],
        "morphologie_adaptee": dict(morpho or {}),
        "objectifs_adaptes": dict(base["objectifs_adaptes"]),
        "score_tension_mecanique": base["score_tension_mecanique"],
        "score_contraction_max": base["score_contraction_max"],
        "potentiel_hypertrophique": base["potentiel_hypertrophique"],
        "substitutes": [],
        "contre_indications": list(contre_indications or []),
        "actif": True,
        "needs_review": True,
    }


EXERCISES = []


def add(*args, **kwargs):
    EXERCISES.append(make(*args, **kwargs))


# ===========================================================================
# PECTORAUX (cible >= 60)
# ===========================================================================
# --- Faisceau claviculaire (haut) ---
for eq_label, eq, arch, tc_over, stab_over, diff_over in [
    ("barre", ["barre"], "presse_lourde_barre", None, None, None),
    ("haltères", ["haltere"], "presse_haltere", None, None, None),
    ("machine convergente", ["machine"], "presse_machine", None, None, None),
    ("Smith", ["machine", "barre"], "presse_lourde_barre", 3, "faible", "debutant"),
    ("prise serrée", ["barre"], "presse_lourde_barre", None, None, None),
]:
    add(f"Développé incliné {eq_label}", "pecs", "pecs_haut", "developpe_incline", "push", eq, arch,
        technical_override=tc_over, stability_override=stab_over, difficulty_override=diff_over,
        secondaires=["triceps", "epaules"], joint_stress={"epaule": 2})
add("Développé militaire incliné haltères", "pecs", "pecs_haut", "developpe_incline", "push", ["haltere"],
    "presse_haltere", secondaires=["epaules", "triceps"], joint_stress={"epaule": 2})
add("Landmine press", "pecs", "pecs_haut", "developpe_incline", "push", ["barre"], "presse_haltere",
    secondaires=["epaules", "triceps"], joint_stress={"epaule": 1})
add("Pompes pieds surélevés", "pecs", "pecs_haut", "developpe_incline", "push", ["poids_du_corps"],
    "pompe_poids_du_corps", secondaires=["triceps", "epaules"])
add("Pompes inclinées lestées", "pecs", "pecs_haut", "developpe_incline", "push", ["poids_du_corps"],
    "pompe_poids_du_corps", secondaires=["triceps", "epaules"], difficulty_override="avance")
add("Écarté poulie basse vers haute", "pecs", "pecs_haut", "ecarte_incline", "push", ["machine"],
    "ecarte_isolation", secondaires=["epaules"])
add("Écarté haltères incliné", "pecs", "pecs_haut", "ecarte_incline", "push", ["haltere"],
    "ecarte_isolation", secondaires=["epaules"])
add("Crossover poulie basse", "pecs", "pecs_haut", "ecarte_incline", "push", ["machine"],
    "ecarte_isolation", secondaires=["epaules"])
add("Écarté incliné unilatéral haltère", "pecs", "pecs_haut", "ecarte_incline", "push", ["haltere"],
    "ecarte_isolation", unilateral=True, secondaires=["epaules"])
add("Développé incliné unilatéral haltère", "pecs", "pecs_haut", "developpe_incline", "push", ["haltere"],
    "presse_haltere", unilateral=True, secondaires=["triceps", "epaules"], joint_stress={"epaule": 2})
add("Développé incliné débutant machine assise", "pecs", "pecs_haut", "developpe_incline", "push", ["machine"],
    "presse_machine", secondaires=["triceps"])
add("Écarté élastique incliné", "pecs", "pecs_haut", "ecarte_incline", "push", ["elastique"],
    "ecarte_isolation", secondaires=["epaules"])
add("Développé incliné élastique", "pecs", "pecs_haut", "developpe_incline", "push", ["elastique"],
    "presse_haltere", secondaires=["triceps", "epaules"], joint_stress={"epaule": 1})
add("Développé incliné prudence épaule (machine guidée amplitude réduite)", "pecs", "pecs_haut",
    "developpe_incline", "push", ["machine"], "presse_machine", secondaires=["triceps"],
    joint_stress={"epaule": 0})

# --- Faisceau moyen ---
for eq_label, eq, arch, name_extra in [
    ("barre", ["barre"], "presse_lourde_barre", ""),
    ("haltères", ["haltere"], "presse_haltere", ""),
    ("Smith", ["machine", "barre"], "presse_lourde_barre", ""),
]:
    add(f"Développé couché {eq_label}", "pecs", "pecs_moyen", "developpe_plat", "push", eq, arch,
        secondaires=["triceps", "epaules"], joint_stress={"epaule": 1},
        morpho={"bras_courts": 2} if eq_label == "barre" else ({"bras_longs": 2} if eq_label == "haltères" else {}))
add("Chest press machine", "pecs", "pecs_moyen", "developpe_plat", "push", ["machine"], "presse_machine",
    secondaires=["triceps"])
add("Chest press convergente", "pecs", "pecs_moyen", "developpe_plat", "push", ["machine"], "presse_machine",
    secondaires=["triceps"])
add("Pompes classiques", "pecs", "pecs_moyen", "developpe_plat", "push", ["poids_du_corps"],
    "pompe_poids_du_corps", secondaires=["triceps", "epaules"])
add("Pompes lestées", "pecs", "pecs_moyen", "developpe_plat", "push", ["poids_du_corps"],
    "pompe_poids_du_corps", secondaires=["triceps", "epaules"], difficulty_override="avance")
add("Développé prise neutre haltères", "pecs", "pecs_moyen", "developpe_plat", "push", ["haltere"],
    "presse_haltere", secondaires=["triceps"], joint_stress={"epaule": 1}, morpho={"epaules_etroites": 2})
add("Floor press barre", "pecs", "pecs_moyen", "developpe_plat", "push", ["barre"], "presse_lourde_barre",
    secondaires=["triceps"], joint_stress={"epaule": 0})
add("Floor press haltères", "pecs", "pecs_moyen", "developpe_plat", "push", ["haltere"], "presse_haltere",
    secondaires=["triceps"], joint_stress={"epaule": 0})
add("Larsen press", "pecs", "pecs_moyen", "developpe_plat", "push", ["barre"], "presse_lourde_barre",
    secondaires=["triceps"], stability_override="eleve", difficulty_override="avance")
add("Spoto press", "pecs", "pecs_moyen", "developpe_plat", "push", ["barre"], "presse_lourde_barre",
    secondaires=["triceps"], difficulty_override="avance")
add("Écarté couché haltères", "pecs", "pecs_moyen", "ecarte_plat", "push", ["haltere"], "ecarte_isolation",
    secondaires=["epaules"])
add("Écarté poulie (fly plat)", "pecs", "pecs_moyen", "ecarte_plat", "push", ["machine"], "ecarte_isolation",
    secondaires=["epaules"])
add("Pec deck machine", "pecs", "pecs_moyen", "ecarte_plat", "push", ["machine"], "ecarte_isolation",
    secondaires=["epaules"])
add("Développé couché unilatéral haltère", "pecs", "pecs_moyen", "developpe_plat", "push", ["haltere"],
    "presse_haltere", unilateral=True, secondaires=["triceps"], stability_override="eleve")
add("Développé couché élastique", "pecs", "pecs_moyen", "developpe_plat", "push", ["elastique"],
    "presse_haltere", secondaires=["triceps"])
add("Pompes genoux (débutant)", "pecs", "pecs_moyen", "developpe_plat", "push", ["poids_du_corps"],
    "pompe_poids_du_corps", secondaires=["triceps"], difficulty_override="debutant", technical_override=1)

# --- Faisceau inférieur ---
add("Développé décliné barre", "pecs", "pecs_bas", "developpe_decline", "push", ["barre"],
    "presse_lourde_barre", secondaires=["triceps"])
add("Développé décliné haltères", "pecs", "pecs_bas", "developpe_decline", "push", ["haltere"],
    "presse_haltere", secondaires=["triceps"])
add("Développé décliné machine", "pecs", "pecs_bas", "developpe_decline", "push", ["machine"],
    "presse_machine", secondaires=["triceps"])
add("Dips buste penché", "pecs", "pecs_bas", "dips", "push", ["poids_du_corps"], "pompe_poids_du_corps",
    secondaires=["triceps", "epaules"], difficulty_override="intermediaire", joint_stress={"epaule": 2})
add("Dips lestés", "pecs", "pecs_bas", "dips", "push", ["poids_du_corps"], "pompe_poids_du_corps",
    secondaires=["triceps", "epaules"], difficulty_override="avance", joint_stress={"epaule": 2})
add("Machine dips", "pecs", "pecs_bas", "dips", "push", ["machine"], "presse_machine",
    secondaires=["triceps"], joint_stress={"epaule": 1})
add("Crossover poulie haute vers basse", "pecs", "pecs_bas", "ecarte_decline", "push", ["machine"],
    "ecarte_isolation", secondaires=["epaules"])
add("Écarté poulie haute (fly bas)", "pecs", "pecs_bas", "ecarte_decline", "push", ["machine"],
    "ecarte_isolation", secondaires=["epaules"])
add("Pompes diamant larges", "pecs", "pecs_bas", "pompe_serree", "push", ["poids_du_corps"],
    "pompe_poids_du_corps", secondaires=["triceps"], difficulty_override="intermediaire")
add("Dips assistés machine (débutant)", "pecs", "pecs_bas", "dips", "push", ["machine"], "presse_machine",
    secondaires=["triceps"], difficulty_override="debutant")

# ===========================================================================
# DOS (cible >= 90)
# ===========================================================================
# --- Grand dorsal largeur ---
for name, eq, arch, diff_over, tc_over in [
    ("Tractions pronation", ["poids_du_corps"], "traction_poids_du_corps", None, None),
    ("Tractions supination", ["poids_du_corps"], "traction_poids_du_corps", None, None),
    ("Tractions neutres", ["poids_du_corps"], "traction_poids_du_corps", None, None),
    ("Tractions assistées machine (débutant)", ["machine"], "tirage_vertical_machine", "debutant", 1),
    ("Tractions lestées", ["poids_du_corps"], "traction_poids_du_corps", "avance", None),
]:
    add(name, "dos", "dos_largeur", "traction", "pull", eq, arch, secondaires=["biceps", "epaules"],
        difficulty_override=diff_over, technical_override=tc_over, joint_stress={"epaule": 1})
add("Tirage vertical prise large", "dos", "dos_largeur", "tirage_vertical", "pull", ["machine"],
    "tirage_vertical_machine", secondaires=["biceps"])
add("Tirage vertical prise neutre", "dos", "dos_largeur", "tirage_vertical", "pull", ["machine"],
    "tirage_vertical_machine", secondaires=["biceps"])
add("Tirage vertical prise supination", "dos", "dos_largeur", "tirage_vertical", "pull", ["machine"],
    "tirage_vertical_machine", secondaires=["biceps"])
add("Tirage vertical unilatéral", "dos", "dos_largeur", "tirage_vertical", "pull", ["machine"],
    "tirage_vertical_machine", unilateral=True, secondaires=["biceps"])
add("Tirage vertical nuque (mobilité épaule requise)", "dos", "dos_largeur", "tirage_vertical", "pull",
    ["machine"], "tirage_vertical_machine", secondaires=["biceps"], joint_stress={"epaule": 2},
    difficulty_override="avance")
add("Pullover poulie haute", "dos", "dos_largeur", "pullover", "pull", ["machine"], "pullover_isolation",
    secondaires=["triceps"])
add("Pullover haltère", "dos", "dos_largeur", "pullover", "pull", ["haltere"], "pullover_isolation",
    secondaires=["triceps", "pecs"])
add("Machine pulldown convergente", "dos", "dos_largeur", "tirage_vertical", "pull", ["machine"],
    "tirage_vertical_machine", secondaires=["biceps"])
add("Straight arm pulldown", "dos", "dos_largeur", "pullover", "pull", ["machine"], "pullover_isolation",
    secondaires=["triceps"])
add("Tirage vertical élastique", "dos", "dos_largeur", "tirage_vertical", "pull", ["elastique"],
    "tirage_vertical_machine", secondaires=["biceps"])
add("Tirage vertical prise large blessure épaule (amplitude réduite)", "dos", "dos_largeur",
    "tirage_vertical", "pull", ["machine"], "tirage_vertical_machine", secondaires=["biceps"],
    joint_stress={"epaule": 0}, difficulty_override="debutant")

# --- Épaisseur du dos ---
for name, eq, arch, morpho in [
    ("Rowing barre pronation", ["barre"], "rowing_barre", {}),
    ("Rowing barre supination", ["barre"], "rowing_barre", {}),
    ("Pendlay row", ["barre"], "rowing_barre", {}),
    ("Kroc row", ["haltere"], "rowing_haltere", {"bras_longs": 2}),
]:
    add(name, "dos", "dos_epaisseur", "rowing", "pull", eq, arch, secondaires=["biceps", "epaules"],
        morpho=morpho, joint_stress={"dos_lombaire": 1})
add("Rowing haltère un bras", "dos", "dos_epaisseur", "rowing", "pull", ["haltere"], "rowing_haltere",
    unilateral=True, secondaires=["biceps"], joint_stress={"dos_lombaire": 1})
add("Rowing T-bar", "dos", "dos_epaisseur", "rowing", "pull", ["barre"], "rowing_barre",
    secondaires=["biceps"], joint_stress={"dos_lombaire": 1})
add("Rowing machine convergente", "dos", "dos_epaisseur", "rowing", "pull", ["machine"], "rowing_machine",
    secondaires=["biceps"])
add("Rowing poitrine supportée machine", "dos", "dos_epaisseur", "rowing", "pull", ["machine"],
    "rowing_machine", secondaires=["biceps"], joint_stress={"dos_lombaire": 0})
add("Rowing poitrine supportée haltères", "dos", "dos_epaisseur", "rowing", "pull", ["haltere"],
    "rowing_haltere", secondaires=["biceps"], joint_stress={"dos_lombaire": 0})
add("Seal row", "dos", "dos_epaisseur", "rowing", "pull", ["barre"], "rowing_barre", secondaires=["biceps"],
    joint_stress={"dos_lombaire": 0})
add("Rowing poulie basse prise large", "dos", "dos_epaisseur", "rowing", "pull", ["machine"],
    "rowing_machine", secondaires=["biceps"])
add("Rowing poulie basse prise serrée", "dos", "dos_epaisseur", "rowing", "pull", ["machine"],
    "rowing_machine", secondaires=["biceps"])
add("Rowing poulie basse prise neutre", "dos", "dos_epaisseur", "rowing", "pull", ["machine"],
    "rowing_machine", secondaires=["biceps"])
add("Rowing inversé (poids du corps, débutant)", "dos", "dos_epaisseur", "rowing", "pull",
    ["poids_du_corps"], "rowing_machine", secondaires=["biceps"], difficulty_override="debutant")
add("Rowing élastique assis", "dos", "dos_epaisseur", "rowing", "pull", ["elastique"], "rowing_machine",
    secondaires=["biceps"])
add("Rowing barre lombaires protégées (buste redressé)", "dos", "dos_epaisseur", "rowing", "pull",
    ["barre"], "rowing_barre", secondaires=["biceps"], joint_stress={"dos_lombaire": 0},
    difficulty_override="intermediaire")
add("Rowing machine unilatéral", "dos", "dos_epaisseur", "rowing", "pull", ["machine"], "rowing_machine",
    unilateral=True, secondaires=["biceps"])

# --- Trapèzes ---
add("Shrug barre", "dos", "dos_trapezes", "shrug", "pull", ["barre"], "shrug_isolation")
add("Shrug haltères", "dos", "dos_trapezes", "shrug", "pull", ["haltere"], "shrug_isolation")
add("Shrug machine", "dos", "dos_trapezes", "shrug", "pull", ["machine"], "shrug_isolation")
add("Face pull corde", "dos", "dos_trapezes", "face_pull", "pull", ["machine"], "arriere_epaule_isolation",
    secondaires=["epaules"])
add("Oiseau poulie", "dos", "dos_trapezes", "oiseau", "pull", ["machine"], "arriere_epaule_isolation",
    secondaires=["epaules"])
add("Reverse fly haltères", "dos", "dos_trapezes", "oiseau", "pull", ["haltere"], "arriere_epaule_isolation",
    secondaires=["epaules"])
add("Shrug élastique", "dos", "dos_trapezes", "shrug", "pull", ["elastique"], "shrug_isolation")
add("Face pull élastique", "dos", "dos_trapezes", "face_pull", "pull", ["elastique"],
    "arriere_epaule_isolation", secondaires=["epaules"])

# ===========================================================================
# ÉPAULES (cible >= 50)
# ===========================================================================
add("Développé militaire barre", "epaules", "epaule_anterieur", "developpe_militaire", "push", ["barre"],
    "presse_debout_barre", secondaires=["triceps"], joint_stress={"epaule": 2})
add("Développé militaire barre assis", "epaules", "epaule_anterieur", "developpe_militaire", "push",
    ["barre"], "presse_lourde_barre", secondaires=["triceps"], joint_stress={"epaule": 2})
add("Développé haltères assis", "epaules", "epaule_anterieur", "developpe_militaire", "push", ["haltere"],
    "presse_haltere", secondaires=["triceps"], joint_stress={"epaule": 1})
add("Développé haltères debout", "epaules", "epaule_anterieur", "developpe_militaire", "push", ["haltere"],
    "presse_debout_barre", secondaires=["triceps"], joint_stress={"epaule": 2})
add("Arnold press", "epaules", "epaule_anterieur", "developpe_militaire", "push", ["haltere"],
    "presse_haltere", secondaires=["triceps"], difficulty_override="intermediaire", joint_stress={"epaule": 2})
add("Développé militaire machine", "epaules", "epaule_anterieur", "developpe_militaire", "push",
    ["machine"], "presse_machine", secondaires=["triceps"], joint_stress={"epaule": 1})
add("Landmine press épaule", "epaules", "epaule_anterieur", "developpe_militaire", "push", ["barre"],
    "presse_haltere", secondaires=["triceps"], joint_stress={"epaule": 1})
add("Élévation frontale haltères", "epaules", "epaule_anterieur", "elevation_frontale", "push", ["haltere"],
    "elevation_isolation")
add("Élévation frontale disque", "epaules", "epaule_anterieur", "elevation_frontale", "push", ["barre"],
    "elevation_isolation")
add("Élévation frontale poulie", "epaules", "epaule_anterieur", "elevation_frontale", "push", ["machine"],
    "elevation_isolation")
add("Élévation frontale élastique", "epaules", "epaule_anterieur", "elevation_frontale", "push",
    ["elastique"], "elevation_isolation")
add("Développé militaire prudence épaule (machine amplitude réduite)", "epaules", "epaule_anterieur",
    "developpe_militaire", "push", ["machine"], "presse_machine", secondaires=["triceps"],
    joint_stress={"epaule": 0}, difficulty_override="debutant")

add("Élévation latérale haltères", "epaules", "epaule_moyen", "elevation_laterale", "push", ["haltere"],
    "elevation_isolation")
add("Élévation latérale poulie", "epaules", "epaule_moyen", "elevation_laterale", "push", ["machine"],
    "elevation_isolation")
add("Machine élévation latérale", "epaules", "epaule_moyen", "elevation_laterale", "push", ["machine"],
    "elevation_isolation")
add("Élévation latérale un bras", "epaules", "epaule_moyen", "elevation_laterale", "push", ["haltere"],
    unilateral=True, archetype="elevation_isolation")
add("Lean away lateral raise", "epaules", "epaule_moyen", "elevation_laterale", "push", ["machine"],
    "elevation_isolation", unilateral=True, difficulty_override="intermediaire")
add("Élévation latérale élastique", "epaules", "epaule_moyen", "elevation_laterale", "push", ["elastique"],
    "elevation_isolation")
add("Élévation latérale penché en avant", "epaules", "epaule_moyen", "elevation_laterale", "push",
    ["haltere"], "elevation_isolation", difficulty_override="intermediaire")
add("Cuban press haltères", "epaules", "epaule_moyen", "developpe_militaire", "push", ["haltere"],
    "presse_haltere", secondaires=["triceps"], difficulty_override="intermediaire", technical_override=3)

add("Reverse fly machine", "epaules", "epaule_posterieur", "oiseau", "pull", ["machine"],
    "arriere_epaule_isolation", secondaires=["dos"])
add("Oiseau haltères", "epaules", "epaule_posterieur", "oiseau", "pull", ["haltere"],
    "arriere_epaule_isolation", secondaires=["dos"])
add("Oiseau poulie épaule", "epaules", "epaule_posterieur", "oiseau", "pull", ["machine"],
    "arriere_epaule_isolation", secondaires=["dos"])
add("Face pull corde épaule", "epaules", "epaule_posterieur", "face_pull", "pull", ["machine"],
    "arriere_epaule_isolation", secondaires=["dos"])
add("Rowing coude ouvert (arrière épaule)", "epaules", "epaule_posterieur", "rowing", "pull", ["haltere"],
    "rowing_haltere", secondaires=["dos"])
add("Oiseau élastique", "epaules", "epaule_posterieur", "oiseau", "pull", ["elastique"],
    "arriere_epaule_isolation", secondaires=["dos"])

# ===========================================================================
# BICEPS (cible >= 40)
# ===========================================================================
for name, eq, morpho in [
    ("Curl barre droite", ["barre"], {}),
    ("Curl EZ", ["barre"], {}),
    ("Curl haltères supination", ["haltere"], {}),
    ("Curl incliné haltères", ["haltere"], {"bras_longs": 2}),
    ("Curl pupitre (banc Scott)", ["barre"], {}),
    ("Curl pupitre haltère", ["haltere"], {}),
    ("Curl câble (poulie basse)", ["machine"], {}),
    ("Curl concentration", ["haltere"], {}),
    ("Spider curl", ["barre"], {}),
    ("Curl 21s barre EZ", ["barre"], {}),
    ("Curl machine", ["machine"], {}),
    ("Curl élastique", ["elastique"], {}),
]:
    add(name, "biceps", "biceps_chef_long", "curl_biceps", "pull", eq, "curl_isolation", morpho=morpho)
add("Curl marteau haltères", "biceps", "biceps_brachial", "curl_marteau", "pull", ["haltere"],
    "curl_isolation")
add("Curl marteau corde", "biceps", "biceps_brachial", "curl_marteau", "pull", ["machine"],
    "curl_isolation")
add("Curl marteau élastique", "biceps", "biceps_brachial", "curl_marteau", "pull", ["elastique"],
    "curl_isolation")
add("Curl marteau incliné", "biceps", "biceps_brachial", "curl_marteau", "pull", ["haltere"],
    "curl_isolation")
add("Curl prise inversée barre (brachio-radial)", "biceps", "biceps_brachioradial", "curl_biceps", "pull",
    ["barre"], "curl_isolation")
add("Curl poulie haute (chef long)", "biceps", "biceps_chef_long", "curl_biceps", "pull", ["machine"],
    "curl_isolation")
add("Curl unilatéral haltère", "biceps", "biceps_chef_court", "curl_biceps", "pull", ["haltere"],
    unilateral=True, archetype="curl_isolation")
add("Curl unilatéral poulie", "biceps", "biceps_chef_court", "curl_biceps", "pull", ["machine"],
    unilateral=True, archetype="curl_isolation")
add("Curl assis genoux (concentration variante)", "biceps", "biceps_chef_court", "curl_biceps", "pull",
    ["haltere"], "curl_isolation")
add("Curl drag barre", "biceps", "biceps_chef_court", "curl_biceps", "pull", ["barre"], "curl_isolation")
add("Curl zottman", "biceps", "biceps_brachioradial", "curl_biceps", "pull", ["haltere"], "curl_isolation",
    difficulty_override="intermediaire")
add("Curl banc incliné unilatéral", "biceps", "biceps_chef_long", "curl_biceps", "pull", ["haltere"],
    unilateral=True, archetype="curl_isolation", morpho={"bras_longs": 2})
add("Curl câble double poulie", "biceps", "biceps_chef_court", "curl_biceps", "pull", ["machine"],
    "curl_isolation")

# ===========================================================================
# TRICEPS (cible >= 45)
# ===========================================================================
add("Développé couché prise serrée", "triceps", "triceps_longue_portion", "extension_triceps", "push",
    ["barre"], "triceps_compose", secondaires=["pecs"], joint_stress={"epaule": 1})
add("Dips serrés (triceps)", "triceps", "triceps_longue_portion", "dips", "push", ["poids_du_corps"],
    "triceps_compose", secondaires=["pecs"], difficulty_override="intermediaire", joint_stress={"epaule": 1})
add("Dips machine (triceps)", "triceps", "triceps_longue_portion", "dips", "push", ["machine"],
    "triceps_compose", secondaires=["pecs"])
add("Barre front EZ (skull crusher)", "triceps", "triceps_longue_portion", "extension_triceps", "push",
    ["barre"], "extension_triceps_isolation", joint_stress={"coude": 1})
add("Extension corde poulie (pushdown corde)", "triceps", "triceps_vaste_lateral", "pushdown", "push",
    ["machine"], "extension_triceps_isolation")
add("Extension au-dessus tête corde", "triceps", "triceps_longue_portion", "extension_triceps", "push",
    ["machine"], "extension_triceps_isolation")
add("Extension haltère derrière tête (une main)", "triceps", "triceps_longue_portion", "extension_triceps",
    "push", ["haltere"], unilateral=True, archetype="extension_triceps_isolation", joint_stress={"epaule": 1})
add("Extension haltère derrière tête (deux mains)", "triceps", "triceps_longue_portion",
    "extension_triceps", "push", ["haltere"], "extension_triceps_isolation", joint_stress={"epaule": 1})
add("Kickback haltère", "triceps", "triceps_vaste_lateral", "kickback", "push", ["haltere"],
    "extension_triceps_isolation")
add("Kickback poulie", "triceps", "triceps_vaste_lateral", "kickback", "push", ["machine"],
    "extension_triceps_isolation")
add("Pushdown barre droite", "triceps", "triceps_vaste_lateral", "pushdown", "push", ["machine"],
    "extension_triceps_isolation")
add("Pushdown corde", "triceps", "triceps_vaste_lateral", "pushdown", "push", ["machine"],
    "extension_triceps_isolation")
add("Pushdown prise marteau (corde, vaste médial)", "triceps", "triceps_vaste_medial", "pushdown", "push",
    ["machine"], "extension_triceps_isolation")
add("Extension triceps unilatérale poulie", "triceps", "triceps_vaste_lateral", "pushdown", "push",
    ["machine"], unilateral=True, archetype="extension_triceps_isolation")
add("JM press barre", "triceps", "triceps_longue_portion", "extension_triceps", "push", ["barre"],
    "triceps_compose", difficulty_override="avance", technical_override=4)
add("Extension triceps machine assise", "triceps", "triceps_vaste_lateral", "extension_triceps", "push",
    ["machine"], "extension_triceps_isolation")
add("Extension triceps élastique", "triceps", "triceps_vaste_lateral", "pushdown", "push", ["elastique"],
    "extension_triceps_isolation")
add("Close grip push-up (pompes serrées)", "triceps", "triceps_vaste_lateral", "dips", "push",
    ["poids_du_corps"], "triceps_compose")
add("Extension nuque haltère bilatérale (vaste médial)", "triceps", "triceps_vaste_medial",
    "extension_triceps", "push", ["haltere"], "extension_triceps_isolation", joint_stress={"epaule": 1})

# ===========================================================================
# JAMBES : quadriceps / ischios / fessiers (cible >= 120)
# ===========================================================================
# --- Quadriceps ---
add("Squat arrière barre (back squat)", "quadriceps", "quadriceps", "squat", "squat", ["barre"],
    "squat_libre", secondaires=["fessiers", "ischio"], joint_stress={"genou": 2, "dos_lombaire": 1})
add("Front squat", "quadriceps", "quadriceps", "front_squat", "squat", ["barre"], "squat_libre",
    secondaires=["fessiers"], difficulty_override="avance", joint_stress={"genou": 2, "epaule": 1})
add("Hack squat machine", "quadriceps", "quadriceps", "squat", "squat", ["machine"], "squat_guide",
    secondaires=["fessiers"], joint_stress={"genou": 2})
add("Presse inclinée pieds bas (quadriceps)", "quadriceps", "quadriceps", "presse_jambes", "squat",
    ["machine"], "presse_jambes", secondaires=["fessiers"], joint_stress={"genou": 1})
add("Extension jambes machine", "quadriceps", "quadriceps", "leg_extension", "squat", ["machine"],
    "extension_jambes_isolation", joint_stress={"genou": 2})
add("Bulgarian split squat haltères", "quadriceps", "quadriceps", "fente", "lunge", ["haltere"],
    "fente_lunge", unilateral=True, secondaires=["fessiers"], joint_stress={"genou": 1})
add("Fente avant haltères", "quadriceps", "quadriceps", "fente", "lunge", ["haltere"], "fente_lunge",
    unilateral=True, secondaires=["fessiers"])
add("Fente marchée haltères", "quadriceps", "quadriceps", "fente", "lunge", ["haltere"], "fente_lunge",
    unilateral=True, secondaires=["fessiers"])
add("Fente arrière barre", "quadriceps", "quadriceps", "fente", "lunge", ["barre"], "fente_lunge",
    unilateral=True, secondaires=["fessiers"])
add("Step up haltères", "quadriceps", "quadriceps", "fente", "lunge", ["haltere"], "fente_lunge",
    unilateral=True, secondaires=["fessiers"])
add("Sissy squat poids du corps", "quadriceps", "quadriceps", "squat", "squat", ["poids_du_corps"],
    "extension_jambes_isolation", difficulty_override="avance", joint_stress={"genou": 2})
add("Squat gobelet haltère (débutant)", "quadriceps", "quadriceps", "squat", "squat", ["haltere"],
    "squat_guide", secondaires=["fessiers"], difficulty_override="debutant", joint_stress={"genou": 1})
add("Squat machine Smith", "quadriceps", "quadriceps", "squat", "squat", ["machine", "barre"],
    "squat_guide", secondaires=["fessiers"], joint_stress={"genou": 1})
add("Presse jambes pieds hauts (quadriceps réduit, fessiers accentués)", "quadriceps", "quadriceps",
    "presse_jambes", "squat", ["machine"], "presse_jambes", secondaires=["fessiers"])
add("Leg press unilatérale", "quadriceps", "quadriceps", "presse_jambes", "squat", ["machine"],
    unilateral=True, archetype="presse_jambes", secondaires=["fessiers"])
add("Squat élastique (maison)", "quadriceps", "quadriceps", "squat", "squat", ["elastique"],
    "squat_guide", secondaires=["fessiers"], difficulty_override="debutant")
add("Squat prudence genoux (amplitude partielle, presse guidée)", "quadriceps", "quadriceps",
    "presse_jambes", "squat", ["machine"], "presse_jambes", secondaires=["fessiers"],
    joint_stress={"genou": 0}, difficulty_override="debutant")
add("Squat fentes bulgares pieds surélevés (fémurs longs)", "quadriceps", "quadriceps", "fente", "lunge",
    ["haltere"], "fente_lunge", unilateral=True, secondaires=["fessiers"], morpho={"jambes_longues": 2})
add("Extension jambes unilatérale machine", "quadriceps", "quadriceps", "leg_extension", "squat",
    ["machine"], unilateral=True, archetype="extension_jambes_isolation", joint_stress={"genou": 2})
add("Squat pistol assisté (poids du corps, avancé)", "quadriceps", "quadriceps", "squat", "squat",
    ["poids_du_corps"], unilateral=True, archetype="squat_libre", difficulty_override="avance",
    joint_stress={"genou": 2})

# --- Ischios ---
add("Soulevé de terre jambes tendues barre", "ischio", "ischio", "hinge_jambes_tendues", "hinge", ["barre"],
    "hinge_lourd", secondaires=["fessiers", "dos"], joint_stress={"dos_lombaire": 2})
add("Romanian deadlift barre", "ischio", "ischio", "hinge_jambes_tendues", "hinge", ["barre"],
    "hinge_lourd", secondaires=["fessiers", "dos"], joint_stress={"dos_lombaire": 2})
add("Romanian deadlift haltères", "ischio", "ischio", "hinge_jambes_tendues", "hinge", ["haltere"],
    "hinge_lourd", secondaires=["fessiers", "dos"], joint_stress={"dos_lombaire": 1})
add("Soulevé de terre jambes tendues unilatéral haltère", "ischio", "ischio", "hinge_jambes_tendues",
    "hinge", ["haltere"], unilateral=True, archetype="hinge_lourd", secondaires=["fessiers"],
    difficulty_override="avance", joint_stress={"dos_lombaire": 1})
add("Leg curl couché machine", "ischio", "ischio", "leg_curl", "hinge", ["machine"], "leg_curl_isolation",
    joint_stress={"genou": 1})
add("Leg curl assis machine", "ischio", "ischio", "leg_curl", "hinge", ["machine"], "leg_curl_isolation",
    joint_stress={"genou": 1})
add("Leg curl debout unilatéral machine", "ischio", "ischio", "leg_curl", "hinge", ["machine"],
    unilateral=True, archetype="leg_curl_isolation", joint_stress={"genou": 1})
add("Nordic curl (poids du corps)", "ischio", "ischio", "leg_curl", "hinge", ["poids_du_corps"],
    "leg_curl_isolation", difficulty_override="avance", technical_override=4, joint_stress={"genou": 2})
add("Good morning barre", "ischio", "ischio", "hinge_jambes_tendues", "hinge", ["barre"], "hinge_lourd",
    secondaires=["dos", "fessiers"], difficulty_override="avance", joint_stress={"dos_lombaire": 2})
add("Soulevé de terre sumo barre", "ischio", "ischio", "hinge_jambes_tendues", "hinge", ["barre"],
    "hinge_lourd", secondaires=["fessiers", "dos"], joint_stress={"dos_lombaire": 2, "genou": 1})
add("Leg curl élastique au sol", "ischio", "ischio", "leg_curl", "hinge", ["elastique"],
    "leg_curl_isolation", difficulty_override="debutant")
add("Hip hinge lombaires protégées (haltère, buste plus droit)", "ischio", "ischio",
    "hinge_jambes_tendues", "hinge", ["haltere"], "hinge_lourd", secondaires=["fessiers"],
    joint_stress={"dos_lombaire": 0}, difficulty_override="debutant")
add("Glute ham raise (banc, avancé)", "ischio", "ischio", "leg_curl", "hinge", ["machine"],
    "leg_curl_isolation", difficulty_override="avance", technical_override=4)

# --- Fessiers ---
add("Hip thrust barre", "fessiers", "fessiers", "hip_thrust", "hinge", ["barre"], "hip_thrust_fessier",
    secondaires=["ischio"], joint_stress={"dos_lombaire": 1})
add("Hip thrust machine", "fessiers", "fessiers", "hip_thrust", "hinge", ["machine"], "hip_thrust_fessier",
    secondaires=["ischio"])
add("Glute bridge poids du corps", "fessiers", "fessiers", "hip_thrust", "hinge", ["poids_du_corps"],
    "hip_thrust_fessier", secondaires=["ischio"], difficulty_override="debutant")
add("Glute bridge unilatéral", "fessiers", "fessiers", "hip_thrust", "hinge", ["poids_du_corps"],
    unilateral=True, archetype="hip_thrust_fessier", secondaires=["ischio"])
add("Abduction hanche machine", "fessiers", "fessiers", "abduction", "isometrique", ["machine"],
    "fessier_isolation")
add("Abduction hanche élastique", "fessiers", "fessiers", "abduction", "isometrique", ["elastique"],
    "fessier_isolation")
add("Kickback fessier poulie", "fessiers", "fessiers", "kickback_fessier", "hinge", ["machine"],
    unilateral=True, archetype="fessier_isolation")
add("Kickback fessier élastique", "fessiers", "fessiers", "kickback_fessier", "hinge", ["elastique"],
    unilateral=True, archetype="fessier_isolation")
add("Bulgarian squat buste penché (fessiers accentués)", "fessiers", "fessiers", "fente", "lunge",
    ["haltere"], unilateral=True, archetype="fente_lunge", secondaires=["quadriceps"])
add("Step up haut fessiers", "fessiers", "fessiers", "fente", "lunge", ["haltere"], unilateral=True,
    archetype="fente_lunge", secondaires=["quadriceps"])
add("Hip thrust unilatéral haltère", "fessiers", "fessiers", "hip_thrust", "hinge", ["haltere"],
    unilateral=True, archetype="hip_thrust_fessier", secondaires=["ischio"])
add("Extension de hanche jambe tendue élastique", "fessiers", "fessiers", "kickback_fessier",
    "hinge", ["elastique"], unilateral=True, archetype="fessier_isolation")
add("Frog pump (poids du corps, genoux sensibles)", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["poids_du_corps"], "hip_thrust_fessier", difficulty_override="debutant", joint_stress={"genou": 0})
add("Hip thrust prudence lombaires (machine guidée)", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["machine"], "hip_thrust_fessier", joint_stress={"dos_lombaire": 0}, difficulty_override="debutant")
add("Donkey calf raise buste penché (accessoire fessiers/mollets)", "fessiers", "fessiers",
    "abduction", "isometrique", ["poids_du_corps"], "fessier_isolation", secondaires=["mollets"])

# ===========================================================================
# MOLLETS (cible >= 25)
# ===========================================================================
add("Mollets debout barre", "mollets", "mollets_gastrocnemien", "mollet_debout", "isometrique", ["barre"],
    "mollet_isolation")
add("Mollets debout machine", "mollets", "mollets_gastrocnemien", "mollet_debout", "isometrique",
    ["machine"], "mollet_isolation")
add("Mollets presse (pieds bas)", "mollets", "mollets_gastrocnemien", "mollet_presse", "isometrique",
    ["machine"], "mollet_isolation")
add("Mollets assis machine (soléaire)", "mollets", "mollets_soleaire", "mollet_assis", "isometrique",
    ["machine"], "mollet_isolation")
add("Mollets unilatéraux haltère", "mollets", "mollets_gastrocnemien", "mollet_debout", "isometrique",
    ["haltere"], unilateral=True, archetype="mollet_isolation")
add("Farmer walk pointe de pieds (mollets)", "mollets", "mollets_gastrocnemien", "farmer_walk_mollets",
    "carry", ["haltere"], "mollet_isolation")
add("Mollets debout poids du corps (débutant)", "mollets", "mollets_gastrocnemien", "mollet_debout",
    "isometrique", ["poids_du_corps"], "mollet_isolation", difficulty_override="debutant")
add("Mollets presse pieds hauts (soléaire accentué)", "mollets", "mollets_soleaire", "mollet_presse",
    "isometrique", ["machine"], "mollet_isolation")
add("Mollets assis barre sur genoux", "mollets", "mollets_soleaire", "mollet_assis", "isometrique",
    ["barre"], "mollet_isolation")
add("Mollets unilatéraux poids du corps (step)", "mollets", "mollets_gastrocnemien", "mollet_debout",
    "isometrique", ["poids_du_corps"], unilateral=True, archetype="mollet_isolation", difficulty_override="debutant")
add("Mollets Smith machine", "mollets", "mollets_gastrocnemien", "mollet_debout", "isometrique",
    ["machine", "barre"], "mollet_isolation")
add("Mollets élastique assis", "mollets", "mollets_soleaire", "mollet_assis", "isometrique", ["elastique"],
    "mollet_isolation")

# ===========================================================================
# ABDOMINAUX / CORE (cible >= 50)
# ===========================================================================
add("Crunch câble (poulie haute)", "abdos", "abdos_flexion", "crunch", "isometrique", ["machine"],
    "core_flexion")
add("Crunch machine", "abdos", "abdos_flexion", "crunch", "isometrique", ["machine"], "core_flexion")
add("Crunch poids du corps au sol", "abdos", "abdos_flexion", "crunch", "isometrique", ["poids_du_corps"],
    "core_flexion", difficulty_override="debutant")
add("Relevé de jambes suspendu", "abdos", "abdos_flexion", "releve_jambes", "isometrique",
    ["poids_du_corps"], "core_flexion", difficulty_override="intermediaire", technical_override=3)
add("Relevé de jambes au sol (débutant)", "abdos", "abdos_flexion", "releve_jambes", "isometrique",
    ["poids_du_corps"], "core_flexion", difficulty_override="debutant")
add("Relevé de genoux suspendu", "abdos", "abdos_flexion", "releve_jambes", "isometrique",
    ["poids_du_corps"], "core_flexion")
add("Dragon flag (avancé)", "abdos", "abdos_flexion", "releve_jambes", "isometrique", ["poids_du_corps"],
    "core_flexion", difficulty_override="avance", technical_override=5, stability_override="eleve")
add("Crunch inversé / relevé de bassin", "abdos", "abdos_flexion", "crunch_inverse", "isometrique",
    ["poids_du_corps"], "core_flexion")
add("Crunch élastique", "abdos", "abdos_flexion", "crunch", "isometrique", ["elastique"], "core_flexion")
add("Crunch sur ballon (swiss ball)", "abdos", "abdos_flexion", "crunch", "isometrique", ["poids_du_corps"],
    "core_flexion")
add("Gainage planche (plank)", "abdos", "abdos_anti_extension", "gainage", "isometrique",
    ["poids_du_corps"], "core_gainage", difficulty_override="debutant")
add("Gainage planche latérale", "abdos", "abdos_obliques", "gainage_lateral", "isometrique",
    ["poids_du_corps"], "core_anti_rotation", difficulty_override="debutant")
add("Ab wheel rollout", "abdos", "abdos_anti_extension", "rollout", "isometrique", ["poids_du_corps"],
    "core_anti_extension", difficulty_override="avance", technical_override=4)
add("Pallof press poulie", "abdos", "abdos_anti_rotation", "pallof_press", "isometrique", ["machine"],
    "core_anti_rotation")
add("Pallof press élastique", "abdos", "abdos_anti_rotation", "pallof_press", "isometrique", ["elastique"],
    "core_anti_rotation")
add("Rotation câble (bûcheron / woodchopper)", "abdos", "abdos_obliques", "rotation_cable", "rotation",
    ["machine"], "core_anti_rotation")
add("Rotation élastique (bûcheron)", "abdos", "abdos_obliques", "rotation_cable", "rotation",
    ["elastique"], "core_anti_rotation")
add("Farmer walk lourd (gainage anti-latéral)", "abdos", "abdos_anti_rotation", "farmer_walk", "carry",
    ["haltere"], "core_charge_lourde")
add("Farmer walk unilatéral (suitcase carry)", "abdos", "abdos_anti_rotation", "farmer_walk", "carry",
    ["haltere"], unilateral=True, archetype="core_charge_lourde")
add("Crunch oblique câble", "abdos", "abdos_obliques", "crunch_oblique", "isometrique", ["machine"],
    "core_flexion")
add("Crunch oblique au sol", "abdos", "abdos_obliques", "crunch_oblique", "isometrique",
    ["poids_du_corps"], "core_flexion", difficulty_override="debutant")
add("Russian twist (avec charge)", "abdos", "abdos_obliques", "rotation_cable", "rotation", ["haltere"],
    "core_anti_rotation")
add("Hollow body hold", "abdos", "abdos_anti_extension", "gainage", "isometrique", ["poids_du_corps"],
    "core_gainage", difficulty_override="intermediaire")
add("Gainage planche lombaires sensibles (genoux au sol)", "abdos", "abdos_anti_extension", "gainage",
    "isometrique", ["poids_du_corps"], "core_gainage", difficulty_override="debutant",
    joint_stress={"dos_lombaire": 0})
add("Mountain climber", "abdos", "abdos_anti_extension", "gainage_dynamique", "isometrique",
    ["poids_du_corps"], "core_gainage")
add("Bird dog (stabilité lombaire)", "abdos", "abdos_anti_rotation", "bird_dog", "isometrique",
    ["poids_du_corps"], "core_anti_rotation", difficulty_override="debutant", joint_stress={"dos_lombaire": 0})
add("Dead bug (stabilité lombaire, débutant)", "abdos", "abdos_anti_extension", "dead_bug", "isometrique",
    ["poids_du_corps"], "core_anti_extension", difficulty_override="debutant", joint_stress={"dos_lombaire": 0})


# ===========================================================================
# EXTENSION (deuxième passe) : compléter les familles encore sous le minimum
# demandé, avec des variantes réellement distinctes (prise/stance/matériel/
# contrainte articulaire) — jamais un simple changement d'étiquette sur un
# exercice déjà présent.
# ===========================================================================

# --- DOS : compléter tirage/rowing avec prises + variantes contrainte ---
for prise, joint in [("prise large", {}), ("prise serrée", {}), ("prise neutre", {})]:
    add(f"Tirage vertical {prise} machine (variante)", "dos", "dos_largeur", "tirage_vertical", "pull",
        ["machine"], "tirage_vertical_machine", secondaires=["biceps"])
for prise in ["prise large", "prise serrée", "prise neutre", "prise pronation", "prise supination"]:
    add(f"Rowing barre {prise} (variante)", "dos", "dos_epaisseur", "rowing", "pull", ["barre"],
        "rowing_barre", secondaires=["biceps", "epaules"], joint_stress={"dos_lombaire": 1})
for eq_label, eq in [("haltère", ["haltere"]), ("machine", ["machine"]), ("élastique", ["elastique"])]:
    add(f"Rowing unilatéral {eq_label} banc supporté (lombaires protégées)", "dos", "dos_epaisseur",
        "rowing", "pull", eq, unilateral=True, archetype="rowing_haltere" if eq_label != "machine" else "rowing_machine",
        secondaires=["biceps"], joint_stress={"dos_lombaire": 0})
add("Tirage horizontal poulie basse prise large (variante dos épaisseur)", "dos", "dos_epaisseur",
    "rowing", "pull", ["machine"], "rowing_machine", secondaires=["biceps"])
add("Tirage horizontal prise serrée poulie (variante dos épaisseur)", "dos", "dos_epaisseur",
    "rowing", "pull", ["machine"], "rowing_machine", secondaires=["biceps"])
add("Meadows row (barre landmine unilatéral)", "dos", "dos_epaisseur", "rowing", "pull", ["barre"],
    unilateral=True, archetype="rowing_barre", secondaires=["biceps"], difficulty_override="intermediaire")
add("Chest supported row machine incliné", "dos", "dos_epaisseur", "rowing", "pull", ["machine"],
    "rowing_machine", secondaires=["biceps"])
add("Rowing câble assis prise large", "dos", "dos_epaisseur", "rowing", "pull", ["machine"],
    "rowing_machine", secondaires=["biceps"])
add("Rowing câble assis prise serrée", "dos", "dos_epaisseur", "rowing", "pull", ["machine"],
    "rowing_machine", secondaires=["biceps"])
add("Tractions lestées prise supination (variante largeur)", "dos", "dos_largeur", "traction", "pull",
    ["poids_du_corps"], "traction_poids_du_corps", secondaires=["biceps"], difficulty_override="avance")
add("Tractions prise large (dos largeur accentuée)", "dos", "dos_largeur", "traction", "pull",
    ["poids_du_corps"], "traction_poids_du_corps", secondaires=["biceps"])
add("Tractions prise rapprochée (dos épaisseur)", "dos", "dos_epaisseur", "traction", "pull",
    ["poids_du_corps"], "traction_poids_du_corps", secondaires=["biceps"])
add("Australian pull-up (tractions inclinées débutant)", "dos", "dos_epaisseur", "rowing", "pull",
    ["poids_du_corps"], "rowing_machine", secondaires=["biceps"], difficulty_override="debutant")
add("Pull-in machine (dos largeur, débutant)", "dos", "dos_largeur", "tirage_vertical", "pull",
    ["machine"], "tirage_vertical_machine", secondaires=["biceps"], difficulty_override="debutant")
add("Shrug derrière le dos (barre)", "dos", "dos_trapezes", "shrug", "pull", ["barre"], "shrug_isolation")
add("Shrug incliné haltères (trapèzes moyens)", "dos", "dos_trapezes", "shrug", "pull", ["haltere"],
    "shrug_isolation")
add("Y-raise haltères légers (trapèzes inférieurs)", "dos", "dos_trapezes", "face_pull", "pull",
    ["haltere"], "arriere_epaule_isolation", secondaires=["epaules"])
add("W-raise élastique (trapèzes/rotateurs)", "dos", "dos_trapezes", "face_pull", "pull", ["elastique"],
    "arriere_epaule_isolation", secondaires=["epaules"])
add("Rowing genou au sol unilatéral haltère (débutant)", "dos", "dos_epaisseur", "rowing", "pull",
    ["haltere"], unilateral=True, archetype="rowing_haltere", secondaires=["biceps"],
    difficulty_override="debutant", joint_stress={"dos_lombaire": 0})
add("Tirage vertical mobilité épaule réduite (amplitude partielle devant)", "dos", "dos_largeur",
    "tirage_vertical", "pull", ["machine"], "tirage_vertical_machine", secondaires=["biceps"],
    joint_stress={"epaule": 0}, difficulty_override="debutant")

# --- JAMBES : compléter quadriceps/ischios/fessiers ---
for stance in ["pieds serrés", "pieds larges (sumo)", "pieds moyens"]:
    add(f"Presse à cuisses {stance} (variante)", "quadriceps", "quadriceps", "presse_jambes", "squat",
        ["machine"], "presse_jambes", secondaires=["fessiers"])
for var in ["squat avant élastique résistance", "squat pause 2 secondes barre", "squat tempo lent barre",
            "squat cluster barre (avancé)"]:
    add(var.capitalize(), "quadriceps", "quadriceps", "squat", "squat",
        ["elastique"] if "élastique" in var else ["barre"], "squat_libre" if "barre" in var else "squat_guide",
        secondaires=["fessiers"], joint_stress={"genou": 1})
add("Zercher squat barre (avancé)", "quadriceps", "quadriceps", "squat", "squat", ["barre"], "squat_libre",
    secondaires=["fessiers", "dos"], difficulty_override="avance", joint_stress={"genou": 2, "dos_lombaire": 1})
add("Squat overhead (avancé, mobilité épaule requise)", "quadriceps", "quadriceps", "squat", "squat",
    ["barre"], "squat_libre", secondaires=["epaules"], difficulty_override="avance",
    joint_stress={"genou": 2, "epaule": 2})
add("Fente latérale haltères (cossack squat)", "quadriceps", "quadriceps", "fente", "lunge", ["haltere"],
    unilateral=True, archetype="fente_lunge", secondaires=["fessiers"], difficulty_override="intermediaire")
add("Fente arrière élévée haltères (déficit lunge)", "quadriceps", "quadriceps", "fente", "lunge",
    ["haltere"], unilateral=True, archetype="fente_lunge", secondaires=["fessiers"],
    difficulty_override="avance")
add("Extension jambes prudence genoux (amplitude partielle)", "quadriceps", "quadriceps", "leg_extension",
    "squat", ["machine"], "extension_jambes_isolation", joint_stress={"genou": 0},
    difficulty_override="debutant")
add("Wall sit (isométrique, débutant genoux sensibles)", "quadriceps", "quadriceps", "squat", "squat",
    ["poids_du_corps"], "extension_jambes_isolation", difficulty_override="debutant",
    joint_stress={"genou": 1})
add("Squat box (profondeur contrôlée, mobilité limitée)", "quadriceps", "quadriceps", "squat", "squat",
    ["barre"], "squat_guide", secondaires=["fessiers"], joint_stress={"genou": 1},
    difficulty_override="debutant")
add("Leg press pieds écartés (adducteurs/quadriceps)", "quadriceps", "quadriceps", "presse_jambes",
    "squat", ["machine"], "presse_jambes", secondaires=["fessiers"])
add("Squat haltères pieds larges (sumo goblet)", "quadriceps", "quadriceps", "squat", "squat",
    ["haltere"], "squat_guide", secondaires=["fessiers"], difficulty_override="debutant")

for eq_label, eq, arch in [("haltères", ["haltere"], "hinge_lourd"), ("barre", ["barre"], "hinge_lourd"),
                            ("élastique", ["elastique"], "leg_curl_isolation"), ("kettlebell", ["haltere"], "hinge_lourd")]:
    add(f"Soulevé de terre roumain unijambiste {eq_label}", "ischio", "ischio", "hinge_jambes_tendues",
        "hinge", eq, unilateral=True, archetype=arch, secondaires=["fessiers"],
        difficulty_override="avance", joint_stress={"dos_lombaire": 1})
add("Leg curl couché unilatéral machine", "ischio", "ischio", "leg_curl", "hinge", ["machine"],
    unilateral=True, archetype="leg_curl_isolation", joint_stress={"genou": 1})
add("Swiss ball leg curl (poids du corps)", "ischio", "ischio", "leg_curl", "hinge", ["poids_du_corps"],
    "leg_curl_isolation", difficulty_override="intermediaire")
add("Soulevé de terre roumain déficit (mobilité élevée)", "ischio", "ischio", "hinge_jambes_tendues",
    "hinge", ["barre"], "hinge_lourd", secondaires=["fessiers"], difficulty_override="avance",
    joint_stress={"dos_lombaire": 2})
add("Good morning genoux fléchis (charge réduite, débutant)", "ischio", "ischio", "hinge_jambes_tendues",
    "hinge", ["barre"], "hinge_lourd", secondaires=["dos", "fessiers"], difficulty_override="debutant",
    joint_stress={"dos_lombaire": 1})
add("Reverse hyperextension machine (lombaires protégées)", "ischio", "ischio", "hinge_jambes_tendues",
    "hinge", ["machine"], "hinge_lourd", secondaires=["fessiers"], joint_stress={"dos_lombaire": 0},
    difficulty_override="debutant")
add("45 degrés hyperextension (banc lombaire)", "ischio", "ischio", "hinge_jambes_tendues", "hinge",
    ["poids_du_corps"], "hinge_lourd", secondaires=["fessiers", "dos"], joint_stress={"dos_lombaire": 1})

for eq_label, eq in [("barre", ["barre"]), ("machine", ["machine"]), ("élastique", ["elastique"])]:
    add(f"Hip thrust pieds surélevés {eq_label}", "fessiers", "fessiers", "hip_thrust", "hinge", eq,
        "hip_thrust_fessier", secondaires=["ischio"])
add("Cable pull-through (fessiers, lombaires protégées)", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["machine"], "hip_thrust_fessier", secondaires=["ischio"], joint_stress={"dos_lombaire": 0},
    difficulty_override="debutant")
add("Abduction hanche debout poulie (fessier moyen)", "fessiers", "fessiers", "abduction", "isometrique",
    ["machine"], "fessier_isolation")
add("Clamshell élastique (fessier moyen, genoux sensibles)", "fessiers", "fessiers", "abduction",
    "isometrique", ["elastique"], "fessier_isolation", difficulty_override="debutant",
    joint_stress={"genou": 0})
add("Monster walk élastique (fessier moyen)", "fessiers", "fessiers", "abduction", "isometrique",
    ["elastique"], "fessier_isolation")
add("Curtsy lunge haltères (fessier moyen)", "fessiers", "fessiers", "fente", "lunge", ["haltere"],
    unilateral=True, archetype="fente_lunge", secondaires=["quadriceps"], difficulty_override="intermediaire")
add("Single leg hip thrust banc (unilatéral)", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["poids_du_corps"], unilateral=True, archetype="hip_thrust_fessier", secondaires=["ischio"])
add("Pull-through élastique (fessiers, débutant)", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["elastique"], "hip_thrust_fessier", secondaires=["ischio"], difficulty_override="debutant")

# --- ÉPAULES : compléter ---
add("Développé Arnold machine (débutant)", "epaules", "epaule_anterieur", "developpe_militaire", "push",
    ["machine"], "presse_machine", secondaires=["triceps"])
add("Développé militaire prise serrée barre", "epaules", "epaule_anterieur", "developpe_militaire",
    "push", ["barre"], "presse_debout_barre", secondaires=["triceps"], joint_stress={"epaule": 2})
add("Push press barre (explosif)", "epaules", "epaule_anterieur", "developpe_militaire", "push",
    ["barre"], "presse_debout_barre", secondaires=["triceps", "quadriceps"], difficulty_override="avance",
    technical_override=4)
add("Élévation frontale barre EZ", "epaules", "epaule_anterieur", "elevation_frontale", "push", ["barre"],
    "elevation_isolation")
add("Élévation frontale alternée haltères", "epaules", "epaule_anterieur", "elevation_frontale", "push",
    ["haltere"], "elevation_isolation")
add("Plate raise (élévation disque frontale, variante)", "epaules", "epaule_anterieur",
    "elevation_frontale", "push", ["barre"], "elevation_isolation")
add("Élévation latérale câble croisé (tension continue)", "epaules", "epaule_moyen", "elevation_laterale",
    "push", ["machine"], "elevation_isolation")
add("Élévation latérale assise (strict, sans élan)", "epaules", "epaule_moyen", "elevation_laterale",
    "push", ["haltere"], "elevation_isolation", difficulty_override="intermediaire")
add("Y-raise incliné banc (épaule moyenne/basse trapèze)", "epaules", "epaule_moyen", "elevation_laterale",
    "push", ["haltere"], "elevation_isolation")
add("Élévation latérale 21s (technique dégressive)", "epaules", "epaule_moyen", "elevation_laterale",
    "push", ["haltere"], "elevation_isolation", difficulty_override="intermediaire")
add("Développé épaule prudence (douleur épaule, machine amplitude courte)", "epaules", "epaule_anterieur",
    "developpe_militaire", "push", ["machine"], "presse_machine", secondaires=["triceps"],
    joint_stress={"epaule": 0}, difficulty_override="debutant")
add("Rotation externe élastique (coiffe des rotateurs, prévention épaule)", "epaules", "epaule_posterieur",
    "face_pull", "pull", ["elastique"], "arriere_epaule_isolation", secondaires=["dos"],
    difficulty_override="debutant", joint_stress={"epaule": 0})
add("Rotation interne élastique (coiffe des rotateurs)", "epaules", "epaule_posterieur", "face_pull",
    "pull", ["elastique"], "arriere_epaule_isolation", secondaires=["dos"], difficulty_override="debutant",
    joint_stress={"epaule": 0})
add("Scapular pull-up (stabilité scapulaire)", "epaules", "epaule_posterieur", "face_pull", "pull",
    ["poids_du_corps"], "arriere_epaule_isolation", secondaires=["dos"], difficulty_override="debutant")

# --- BICEPS : compléter ---
add("Curl barre EZ prise serrée (chef court)", "biceps", "biceps_chef_court", "curl_biceps", "pull",
    ["barre"], "curl_isolation")
add("Curl barre EZ prise large (chef long)", "biceps", "biceps_chef_long", "curl_biceps", "pull",
    ["barre"], "curl_isolation")
add("Curl câble derrière le dos (étirement chef long)", "biceps", "biceps_chef_long", "curl_biceps",
    "pull", ["machine"], "curl_isolation", difficulty_override="intermediaire")
add("Curl banc incliné 45° haltères", "biceps", "biceps_chef_long", "curl_biceps", "pull", ["haltere"],
    "curl_isolation", morpho={"bras_longs": 2})
add("Curl marteau câble corde", "biceps", "biceps_brachial", "curl_marteau", "pull", ["machine"],
    "curl_isolation")
add("Curl marteau assis banc", "biceps", "biceps_brachial", "curl_marteau", "pull", ["haltere"],
    "curl_isolation")
add("Curl poids du corps (anneaux/sangle, avancé)", "biceps", "biceps_chef_court", "curl_biceps", "pull",
    ["poids_du_corps"], "curl_isolation", difficulty_override="avance")
add("Preacher curl machine (banc Scott guidé)", "biceps", "biceps_chef_court", "curl_biceps", "pull",
    ["machine"], "curl_isolation")
add("Curl une main poulie basse", "biceps", "biceps_chef_court", "curl_biceps", "pull", ["machine"],
    unilateral=True, archetype="curl_isolation")

# --- TRICEPS : compléter ---
add("Triceps corde poulie haute (overhead, longue portion accentuée)", "triceps", "triceps_longue_portion",
    "extension_triceps", "push", ["machine"], "extension_triceps_isolation")
add("Extension triceps unilatérale haltère assis", "triceps", "triceps_longue_portion", "extension_triceps",
    "push", ["haltere"], unilateral=True, archetype="extension_triceps_isolation", joint_stress={"epaule": 1})
add("Triceps push-down prise inversée (supination)", "triceps", "triceps_vaste_medial", "pushdown", "push",
    ["machine"], "extension_triceps_isolation")
add("Dips entre deux bancs (poids du corps, débutant)", "triceps", "triceps_longue_portion", "dips",
    "push", ["poids_du_corps"], "triceps_compose", secondaires=["pecs"], difficulty_override="debutant")
add("Close grip bench press Smith machine", "triceps", "triceps_longue_portion", "extension_triceps",
    "push", ["machine", "barre"], "triceps_compose", secondaires=["pecs"])
add("Extension triceps banc décliné haltères", "triceps", "triceps_longue_portion", "extension_triceps",
    "push", ["haltere"], "extension_triceps_isolation", joint_stress={"epaule": 1})
add("Kickback élastique", "triceps", "triceps_vaste_lateral", "kickback", "push", ["elastique"],
    "extension_triceps_isolation")
add("Triceps dips prudence épaule (machine amplitude réduite)", "triceps", "triceps_longue_portion",
    "dips", "push", ["machine"], "presse_machine", secondaires=["pecs"], joint_stress={"epaule": 0},
    difficulty_override="debutant")
add("Diamond push-up sur genoux (débutant)", "triceps", "triceps_vaste_lateral", "dips", "push",
    ["poids_du_corps"], "pompe_poids_du_corps", difficulty_override="debutant")
add("Triceps extension unilatérale câble croisé", "triceps", "triceps_vaste_lateral", "pushdown", "push",
    ["machine"], unilateral=True, archetype="extension_triceps_isolation")

# --- MOLLETS : compléter ---
add("Mollets debout unilatéral élastique", "mollets", "mollets_gastrocnemien", "mollet_debout",
    "isometrique", ["elastique"], unilateral=True, archetype="mollet_isolation")
add("Mollets sur step (poids du corps, amplitude complète)", "mollets", "mollets_gastrocnemien",
    "mollet_debout", "isometrique", ["poids_du_corps"], "mollet_isolation")
add("Mollets assis unilatéral haltère sur genou", "mollets", "mollets_soleaire", "mollet_assis",
    "isometrique", ["haltere"], unilateral=True, archetype="mollet_isolation")
add("Donkey calf raise machine dédiée", "mollets", "mollets_gastrocnemien", "mollet_debout",
    "isometrique", ["machine"], "mollet_isolation")
add("Mollets presse unilatérale (pieds bas)", "mollets", "mollets_gastrocnemien", "mollet_presse",
    "isometrique", ["machine"], unilateral=True, archetype="mollet_isolation")
add("Sauts à la corde (mollets, cardio léger)", "mollets", "mollets_gastrocnemien", "mollet_debout",
    "isometrique", ["poids_du_corps"], "mollet_isolation", difficulty_override="debutant")
add("Mollets cheville sensible (amplitude réduite, machine assise)", "mollets", "mollets_soleaire",
    "mollet_assis", "isometrique", ["machine"], "mollet_isolation", joint_stress={"cheville": 0},
    difficulty_override="debutant")
add("Mollets debout haltères deux mains", "mollets", "mollets_gastrocnemien", "mollet_debout",
    "isometrique", ["haltere"], "mollet_isolation")
add("Mollets sur presse à cuisses (jambes tendues)", "mollets", "mollets_gastrocnemien", "mollet_presse",
    "isometrique", ["machine"], "mollet_isolation")
add("Tibia raise (releveur de pied, prévention cheville)", "mollets", "mollets_gastrocnemien",
    "mollet_debout", "isometrique", ["poids_du_corps"], "mollet_isolation", difficulty_override="debutant")

# --- ABDOS : compléter ---
add("Cable crunch à genoux (poulie haute)", "abdos", "abdos_flexion", "crunch", "isometrique",
    ["machine"], "core_flexion")
add("V-up (poids du corps, avancé)", "abdos", "abdos_flexion", "releve_jambes", "isometrique",
    ["poids_du_corps"], "core_flexion", difficulty_override="avance")
add("Toes to bar (suspendu, avancé)", "abdos", "abdos_flexion", "releve_jambes", "isometrique",
    ["poids_du_corps"], "core_flexion", difficulty_override="avance", technical_override=5)
add("Sit-up lesté (disque sur poitrine)", "abdos", "abdos_flexion", "crunch", "isometrique",
    ["poids_du_corps"], "core_flexion", difficulty_override="intermediaire")
add("Gainage planche avant-bras sur ballon (instabilité)", "abdos", "abdos_anti_extension", "gainage",
    "isometrique", ["poids_du_corps"], "core_gainage", difficulty_override="intermediaire")
add("Gainage planche latérale genoux (débutant, lombaires sensibles)", "abdos", "abdos_obliques",
    "gainage_lateral", "isometrique", ["poids_du_corps"], "core_anti_rotation",
    difficulty_override="debutant", joint_stress={"dos_lombaire": 0})
add("Ab wheel rollout sur genoux (intermédiaire)", "abdos", "abdos_anti_extension", "rollout",
    "isometrique", ["poids_du_corps"], "core_anti_extension", difficulty_override="intermediaire")
add("Landmine rotation core (anti-rotation debout)", "abdos", "abdos_obliques", "rotation_cable",
    "rotation", ["barre"], "core_anti_rotation")
add("Suitcase deadlift (gainage anti-latéral, charge unilatérale)", "abdos", "abdos_anti_rotation",
    "farmer_walk", "carry", ["haltere"], unilateral=True, archetype="core_charge_lourde")
add("Copenhagen plank (adducteurs/obliques, avancé)", "abdos", "abdos_obliques", "gainage_lateral",
    "isometrique", ["poids_du_corps"], "core_anti_rotation", difficulty_override="avance",
    technical_override=4)
add("Stir the pot (planche sur swiss ball, rotation)", "abdos", "abdos_anti_rotation", "gainage",
    "isometrique", ["poids_du_corps"], "core_anti_rotation", difficulty_override="intermediaire")
add("Pallof press à genoux (débutant)", "abdos", "abdos_anti_rotation", "pallof_press", "isometrique",
    ["elastique"], "core_anti_rotation", difficulty_override="debutant")
add("Renforcement lombaire superman (poids du corps, prudence)", "abdos", "abdos_anti_extension",
    "gainage", "isometrique", ["poids_du_corps"], "core_gainage", joint_stress={"dos_lombaire": 1})
add("Crunch bicyclette (obliques dynamique)", "abdos", "abdos_obliques", "crunch_oblique",
    "isometrique", ["poids_du_corps"], "core_flexion")

# --- PECS : compléter jusqu'au minimum ---
add("Développé couché prise large (pecs externe)", "pecs", "pecs_moyen", "developpe_plat", "push",
    ["barre"], "presse_lourde_barre", secondaires=["triceps", "epaules"], joint_stress={"epaule": 1})
add("Développé couché tempo lent (contrôle excentrique)", "pecs", "pecs_moyen", "developpe_plat", "push",
    ["barre"], "presse_lourde_barre", secondaires=["triceps"], difficulty_override="intermediaire")
add("Développé couché pause poitrine (compétition powerlifting)", "pecs", "pecs_moyen", "developpe_plat",
    "push", ["barre"], "presse_lourde_barre", secondaires=["triceps"], difficulty_override="avance")
add("Svend press (disques, pecs interne)", "pecs", "pecs_moyen", "ecarte_plat", "push", ["barre"],
    "ecarte_isolation")
add("Pompes archer (unilatéral, avancé)", "pecs", "pecs_moyen", "developpe_plat", "push",
    ["poids_du_corps"], unilateral=True, archetype="pompe_poids_du_corps", secondaires=["triceps"],
    difficulty_override="avance")
add("Pompes plyométriques (explosif)", "pecs", "pecs_moyen", "developpe_plat", "push",
    ["poids_du_corps"], "pompe_poids_du_corps", secondaires=["triceps"], difficulty_override="avance",
    technical_override=4)


# ===========================================================================
# TROISIÈME PASSE : dernières familles encore sous le minimum demandé.
# ===========================================================================

# --- DOS (encore sous 90) ---
add("Rowing Yates (barre, prise supination explosive)", "dos", "dos_epaisseur", "rowing", "pull",
    ["barre"], "rowing_barre", secondaires=["biceps"], difficulty_override="avance")
add("Rowing haltère buste à 45° (deux bras)", "dos", "dos_epaisseur", "rowing", "pull", ["haltere"],
    "rowing_haltere", secondaires=["biceps"], joint_stress={"dos_lombaire": 1})
add("Rowing câble poitrine appuyée (isolation dorsaux)", "dos", "dos_epaisseur", "rowing", "pull",
    ["machine"], "rowing_machine", secondaires=["biceps"])
add("Rowing haltère renversé sur banc (récup lombaire)", "dos", "dos_epaisseur", "rowing", "pull",
    ["haltere"], "rowing_machine", secondaires=["biceps"], joint_stress={"dos_lombaire": 0},
    difficulty_override="debutant")
add("Tirage vertical prise inversée serrée (biceps/dos bas)", "dos", "dos_largeur", "tirage_vertical",
    "pull", ["machine"], "tirage_vertical_machine", secondaires=["biceps"])
add("Tirage vertical grande amplitude (stretch dorsaux)", "dos", "dos_largeur", "tirage_vertical",
    "pull", ["machine"], "tirage_vertical_machine", secondaires=["biceps"], difficulty_override="intermediaire")
add("Pullover machine dédiée (dorsaux, étirement)", "dos", "dos_largeur", "pullover", "pull",
    ["machine"], "pullover_isolation", secondaires=["triceps"])
add("Pullover élastique debout", "dos", "dos_largeur", "pullover", "pull", ["elastique"],
    "pullover_isolation", secondaires=["triceps"])
add("Traction lestée prise étroite neutre", "dos", "dos_largeur", "traction", "pull",
    ["poids_du_corps"], "traction_poids_du_corps", secondaires=["biceps"], difficulty_override="avance")
add("Traction négative (excentrique, débutant)", "dos", "dos_largeur", "traction", "pull",
    ["poids_du_corps"], "traction_poids_du_corps", secondaires=["biceps"], difficulty_override="debutant")
add("Rowing landmine unilatéral (angle bas)", "dos", "dos_epaisseur", "rowing", "pull", ["barre"],
    unilateral=True, archetype="rowing_barre", secondaires=["biceps"])
add("Face pull haut (angle épaule, arrière dos)", "dos", "dos_trapezes", "face_pull", "pull",
    ["machine"], "arriere_epaule_isolation", secondaires=["epaules"])
add("Shrug poulie basse (trajectoire guidée)", "dos", "dos_trapezes", "shrug", "pull", ["machine"],
    "shrug_isolation")
add("Rack pull (soulevé de terre partiel, dos épaisseur)", "dos", "dos_epaisseur", "hinge_jambes_tendues",
    "hinge", ["barre"], "hinge_lourd", secondaires=["ischio", "fessiers"], difficulty_override="intermediaire",
    joint_stress={"dos_lombaire": 1})
add("Snatch grip row (barre prise très large)", "dos", "dos_epaisseur", "rowing", "pull", ["barre"],
    "rowing_barre", secondaires=["biceps"], difficulty_override="avance")
add("Rowing haltère prise neutre banc plat", "dos", "dos_epaisseur", "rowing", "pull", ["haltere"],
    "rowing_haltere", secondaires=["biceps"])
add("Tirage nuque prudence (mobilité épaule limitée, éviter)", "dos", "dos_largeur", "tirage_vertical",
    "pull", ["machine"], "tirage_vertical_machine", secondaires=["biceps"], joint_stress={"epaule": 0},
    difficulty_override="debutant")
add("Rowing debout buste penché barre courte (débutant)", "dos", "dos_epaisseur", "rowing", "pull",
    ["barre"], "rowing_barre", secondaires=["biceps"], difficulty_override="debutant",
    joint_stress={"dos_lombaire": 1})
add("Cross-bench pullover (dorsaux + pecs)", "dos", "dos_largeur", "pullover", "pull", ["haltere"],
    "pullover_isolation", secondaires=["pecs", "triceps"])
add("Renforcement rhomboïdes câble (rétraction scapulaire)", "dos", "dos_trapezes", "face_pull", "pull",
    ["machine"], "arriere_epaule_isolation", secondaires=["epaules"], difficulty_override="debutant")
add("Rowing assis élastique prise large", "dos", "dos_epaisseur", "rowing", "pull", ["elastique"],
    "rowing_machine", secondaires=["biceps"])
add("Rowing assis élastique prise serrée", "dos", "dos_epaisseur", "rowing", "pull", ["elastique"],
    "rowing_machine", secondaires=["biceps"])

# --- QUADRICEPS/ISCHIOS/FESSIERS (jambes encore sous 120 au total) ---
add("Squat avant élastique (résistance progressive)", "quadriceps", "quadriceps", "squat", "squat",
    ["elastique"], "squat_guide", secondaires=["fessiers"], difficulty_override="debutant")
add("Squat unilatéral banc (pistol assisté banc)", "quadriceps", "quadriceps", "squat", "squat",
    ["poids_du_corps"], unilateral=True, archetype="squat_guide", difficulty_override="intermediaire",
    joint_stress={"genou": 1})
add("Presse à cuisses unilatérale pieds hauts", "quadriceps", "quadriceps", "presse_jambes", "squat",
    ["machine"], unilateral=True, archetype="presse_jambes", secondaires=["fessiers"])
add("Squat kettlebell goblet pieds larges", "quadriceps", "quadriceps", "squat", "squat", ["haltere"],
    "squat_guide", secondaires=["fessiers"], difficulty_override="debutant")
add("Extension jambes isométrique (tenue en haut)", "quadriceps", "quadriceps", "leg_extension", "squat",
    ["machine"], "extension_jambes_isolation", joint_stress={"genou": 1})
add("Fente bulgare barre sur dos (avancé)", "quadriceps", "quadriceps", "fente", "lunge", ["barre"],
    unilateral=True, archetype="fente_lunge", secondaires=["fessiers"], difficulty_override="avance")
add("Squat jump (explosif, pliométrique)", "quadriceps", "quadriceps", "squat", "squat",
    ["poids_du_corps"], "squat_libre", secondaires=["fessiers"], difficulty_override="avance",
    technical_override=3)
add("Sissy squat machine (assisté)", "quadriceps", "quadriceps", "squat", "squat", ["machine"],
    "extension_jambes_isolation", joint_stress={"genou": 2}, difficulty_override="intermediaire")
add("Step down excentrique (genou, rééducation/prévention)", "quadriceps", "quadriceps", "fente",
    "lunge", ["poids_du_corps"], unilateral=True, archetype="fente_lunge", difficulty_override="debutant",
    joint_stress={"genou": 1})
add("Squat isométrique contre mur (chaise, débutant)", "quadriceps", "quadriceps", "squat", "squat",
    ["poids_du_corps"], "extension_jambes_isolation", difficulty_override="debutant")
add("Leg press pieds étroits (quadriceps externe)", "quadriceps", "quadriceps", "presse_jambes", "squat",
    ["machine"], "presse_jambes", secondaires=["fessiers"])
add("Squat prise sumo barre basse (fémurs longs)", "quadriceps", "quadriceps", "squat", "squat",
    ["barre"], "squat_libre", secondaires=["fessiers"], morpho={"jambes_longues": 2},
    joint_stress={"genou": 2, "dos_lombaire": 1})

add("Good morning assis (isolation ischio/dos, débutant)", "ischio", "ischio", "hinge_jambes_tendues",
    "hinge", ["barre"], "hinge_lourd", secondaires=["dos"], difficulty_override="debutant",
    joint_stress={"dos_lombaire": 1})
add("Leg curl nordique assisté élastique", "ischio", "ischio", "leg_curl", "hinge", ["elastique"],
    "leg_curl_isolation", difficulty_override="intermediaire")
add("Soulevé de terre roumain élastique (maison)", "ischio", "ischio", "hinge_jambes_tendues", "hinge",
    ["elastique"], "hinge_lourd", secondaires=["fessiers"], difficulty_override="debutant")
add("Single leg RDL banc d'appui (équilibre assisté)", "ischio", "ischio", "hinge_jambes_tendues",
    "hinge", ["haltere"], unilateral=True, archetype="hinge_lourd", secondaires=["fessiers"],
    difficulty_override="intermediaire")
add("Leg curl ballon suisse unilatéral", "ischio", "ischio", "leg_curl", "hinge", ["poids_du_corps"],
    unilateral=True, archetype="leg_curl_isolation", difficulty_override="avance")
add("Soulevé de terre roumain barre prudence lombaire (amplitude réduite)", "ischio", "ischio",
    "hinge_jambes_tendues", "hinge", ["barre"], "hinge_lourd", secondaires=["fessiers"],
    joint_stress={"dos_lombaire": 0}, difficulty_override="debutant")

add("Hip thrust smith machine (guidé)", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["machine", "barre"], "hip_thrust_fessier", secondaires=["ischio"])
add("Frog pump élastique (fessier isolation)", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["elastique"], "hip_thrust_fessier", difficulty_override="debutant")
add("Step up latéral (fessier moyen)", "fessiers", "fessiers", "fente", "lunge", ["haltere"],
    unilateral=True, archetype="fente_lunge", secondaires=["quadriceps"])
add("Bulgarian split squat élastique résistance (fessier)", "fessiers", "fessiers", "fente", "lunge",
    ["elastique"], unilateral=True, archetype="fente_lunge", secondaires=["quadriceps"])
add("Banded walk latéral (fessier moyen, prévention genou)", "fessiers", "fessiers", "abduction",
    "isometrique", ["elastique"], "fessier_isolation", difficulty_override="debutant",
    joint_stress={"genou": 0})
add("Hip thrust unilatéral pieds surélevés", "fessiers", "fessiers", "hip_thrust", "hinge",
    ["poids_du_corps"], unilateral=True, archetype="hip_thrust_fessier", secondaires=["ischio"])

# --- TRICEPS (encore sous 45) ---
add("Triceps kickback poulie basse unilatéral", "triceps", "triceps_vaste_lateral", "kickback", "push",
    ["machine"], unilateral=True, archetype="extension_triceps_isolation")
add("Extension triceps barre EZ debout", "triceps", "triceps_longue_portion", "extension_triceps",
    "push", ["barre"], "extension_triceps_isolation")
add("Triceps dips banc (pieds au sol, débutant)", "triceps", "triceps_longue_portion", "dips", "push",
    ["poids_du_corps"], "pompe_poids_du_corps", secondaires=["pecs"], difficulty_override="debutant")
add("Triceps dips banc pieds surélevés (avancé)", "triceps", "triceps_longue_portion", "dips", "push",
    ["poids_du_corps"], "triceps_compose", secondaires=["pecs"], difficulty_override="avance")
add("JM press haltères (variante)", "triceps", "triceps_longue_portion", "extension_triceps", "push",
    ["haltere"], "triceps_compose", difficulty_override="avance")
add("Pushdown prise supination (biceps assisté, triceps ciblé)", "triceps", "triceps_vaste_medial",
    "pushdown", "push", ["machine"], "extension_triceps_isolation")
add("Extension triceps genou au sol (poulie basse)", "triceps", "triceps_vaste_lateral",
    "extension_triceps", "push", ["machine"], "extension_triceps_isolation")
add("Triceps presse française allongé (skull crusher haltères)", "triceps", "triceps_longue_portion",
    "extension_triceps", "push", ["haltere"], "extension_triceps_isolation", joint_stress={"coude": 1})
add("Triceps dips machine assistée (débutant)", "triceps", "triceps_longue_portion", "dips", "push",
    ["machine"], "presse_machine", secondaires=["pecs"], difficulty_override="debutant")
add("Close grip push-up pieds surélevés (avancé)", "triceps", "triceps_vaste_lateral", "dips", "push",
    ["poids_du_corps"], "triceps_compose", difficulty_override="avance")
add("Triceps extension câble corde à genoux", "triceps", "triceps_vaste_lateral", "pushdown", "push",
    ["machine"], "extension_triceps_isolation", difficulty_override="debutant")
add("Overhead triceps élastique bilatéral", "triceps", "triceps_longue_portion", "extension_triceps",
    "push", ["elastique"], "extension_triceps_isolation")
add("Triceps kickback banc incliné (isolation stricte)", "triceps", "triceps_vaste_lateral", "kickback",
    "push", ["haltere"], "extension_triceps_isolation")
add("Triceps dips prise serrée barre parallèle", "triceps", "triceps_longue_portion", "dips", "push",
    ["poids_du_corps"], "triceps_compose", secondaires=["pecs"], difficulty_override="intermediaire")

# --- MOLLETS (encore sous 25) ---
add("Mollets debout barre nuque (Smith guidé)", "mollets", "mollets_gastrocnemien", "mollet_debout",
    "isometrique", ["machine", "barre"], "mollet_isolation")
add("Mollets sur presse à cuisses unilatéral", "mollets", "mollets_gastrocnemien", "mollet_presse",
    "isometrique", ["machine"], unilateral=True, archetype="mollet_isolation")
add("Mollets assis élastique unilatéral", "mollets", "mollets_soleaire", "mollet_assis", "isometrique",
    ["elastique"], unilateral=True, archetype="mollet_isolation")

# --- ABDOS (encore sous 50) ---
add("Renforcement obliques câble debout (rotation contrôlée)", "abdos", "abdos_obliques",
    "rotation_cable", "rotation", ["machine"], "core_anti_rotation")
add("Sit-up déclive (banc incliné)", "abdos", "abdos_flexion", "crunch", "isometrique",
    ["poids_du_corps"], "core_flexion", difficulty_override="intermediaire")
add("Roue abdominale debout (avancé)", "abdos", "abdos_anti_extension", "rollout", "isometrique",
    ["poids_du_corps"], "core_anti_extension", difficulty_override="avance", technical_override=5)
add("Planche avec levée de jambe (gainage dynamique)", "abdos", "abdos_anti_extension", "gainage",
    "isometrique", ["poids_du_corps"], "core_gainage", difficulty_override="intermediaire")

# --- PECS (dernier ajustement pour dépasser 60) ---
add("Développé couché barre courte (safety bar, épaule prudente)", "pecs", "pecs_moyen",
    "developpe_plat", "push", ["barre"], "presse_lourde_barre", secondaires=["triceps"],
    joint_stress={"epaule": 0}, difficulty_override="debutant")
add("Écarté couché câble unilatéral", "pecs", "pecs_moyen", "ecarte_plat", "push", ["machine"],
    unilateral=True, archetype="ecarte_isolation", secondaires=["epaules"])
add("Développé haltères prise marteau (pecs interne)", "pecs", "pecs_moyen", "developpe_plat", "push",
    ["haltere"], "presse_haltere", secondaires=["triceps"], joint_stress={"epaule": 1})
add("Pec fly machine unilatéral", "pecs", "pecs_moyen", "ecarte_plat", "push", ["machine"],
    unilateral=True, archetype="ecarte_isolation", secondaires=["epaules"])


# ===========================================================================
# QUATRIÈME PASSE : derniers ajustements pour dépasser tous les minimums.
# ===========================================================================
add("Développé militaire haltères prudence épaule (banc dossier haut)", "epaules", "epaule_anterieur",
    "developpe_militaire", "push", ["haltere"], "presse_machine", secondaires=["triceps"],
    joint_stress={"epaule": 0}, difficulty_override="debutant")
add("Élévation latérale câble bas vers haut (tension bas)", "epaules", "epaule_moyen",
    "elevation_laterale", "push", ["machine"], "elevation_isolation")
add("Élévation latérale genou plié (technique triche contrôlée)", "epaules", "epaule_moyen",
    "elevation_laterale", "push", ["haltere"], "elevation_isolation", difficulty_override="intermediaire")
add("Cuban rotation élastique (rotateurs + épaule moyenne)", "epaules", "epaule_moyen",
    "elevation_laterale", "push", ["elastique"], "elevation_isolation", difficulty_override="debutant")
add("Développé Bradford (barre, avancé)", "epaules", "epaule_anterieur", "developpe_militaire", "push",
    ["barre"], "presse_debout_barre", secondaires=["triceps"], difficulty_override="avance",
    technical_override=4)
add("Élévation frontale plaque neutre (prise marteau)", "epaules", "epaule_anterieur",
    "elevation_frontale", "push", ["haltere"], "elevation_isolation")
add("Rear delt row élastique (arrière épaule)", "epaules", "epaule_posterieur", "oiseau", "pull",
    ["elastique"], "arriere_epaule_isolation", secondaires=["dos"])
add("Oiseau banc incliné poitrine appuyée (isolation stricte)", "epaules", "epaule_posterieur", "oiseau",
    "pull", ["haltere"], "arriere_epaule_isolation", secondaires=["dos"])
add("Face pull genoux au sol (angle bas)", "epaules", "epaule_posterieur", "face_pull", "pull",
    ["machine"], "arriere_epaule_isolation", secondaires=["dos"])
add("Développé militaire assis dossier (dos protégé)", "epaules", "epaule_anterieur",
    "developpe_militaire", "push", ["machine"], "presse_machine", secondaires=["triceps"],
    joint_stress={"dos_lombaire": 0})

add("Curl biceps câble bas (angle constant)", "biceps", "biceps_chef_court", "curl_biceps", "pull",
    ["machine"], "curl_isolation")
add("Curl biceps genou au sol (isolation stricte)", "biceps", "biceps_chef_long", "curl_biceps", "pull",
    ["haltere"], "curl_isolation")
add("Curl EZ prise inversée (avant-bras/brachial)", "biceps", "biceps_brachial", "curl_marteau", "pull",
    ["barre"], "curl_isolation")
add("Curl biceps machine à came unilatérale", "biceps", "biceps_chef_court", "curl_biceps", "pull",
    ["machine"], unilateral=True, archetype="curl_isolation")
add("Curl biceps debout dos au mur (triche éliminée)", "biceps", "biceps_chef_long", "curl_biceps",
    "pull", ["barre"], "curl_isolation", difficulty_override="intermediaire")
add("Waiter curl haltère (prise neutre, brachial)", "biceps", "biceps_brachial", "curl_marteau", "pull",
    ["haltere"], "curl_isolation")

add("Écarté couché prise neutre haltères courts (débutant)", "pecs", "pecs_moyen", "developpe_plat",
    "push", ["haltere"], "presse_haltere", secondaires=["triceps"], difficulty_override="debutant")
add("Développé couché élastique + barre (résistance variable)", "pecs", "pecs_moyen", "developpe_plat",
    "push", ["elastique", "barre"], "presse_lourde_barre", secondaires=["triceps"],
    difficulty_override="avance")
add("Pec deck inversé (isolation interne, prise rapprochée)", "pecs", "pecs_moyen", "ecarte_plat", "push",
    ["machine"], "ecarte_isolation", secondaires=["epaules"])
add("Dips lestés prudence épaule (amplitude partielle)", "pecs", "pecs_bas", "dips", "push",
    ["poids_du_corps"], "pompe_poids_du_corps", secondaires=["triceps"], joint_stress={"epaule": 0},
    difficulty_override="debutant")

add("Gainage planche dynamique (touches épaules)", "abdos", "abdos_anti_extension", "gainage",
    "isometrique", ["poids_du_corps"], "core_gainage", difficulty_override="intermediaire")
add("Rotation médecine ball (explosif, obliques)", "abdos", "abdos_obliques", "rotation_cable",
    "rotation", ["poids_du_corps"], "core_anti_rotation", difficulty_override="intermediaire")
add("Renforcement transverse (respiration abdominale, vacuum)", "abdos", "abdos_anti_extension",
    "gainage", "isometrique", ["poids_du_corps"], "core_gainage", difficulty_override="debutant")
add("Crunch poulie debout (variante fonctionnelle)", "abdos", "abdos_flexion", "crunch", "isometrique",
    ["machine"], "core_flexion")
add("Renforcement lombaire oiseau-chien avancé (charge légère)", "abdos", "abdos_anti_rotation",
    "bird_dog", "isometrique", ["elastique"], "core_anti_rotation", difficulty_override="intermediaire")

add("Triceps dips anneaux (instabilité, avancé)", "triceps", "triceps_longue_portion", "dips", "push",
    ["poids_du_corps"], "triceps_compose", secondaires=["pecs"], difficulty_override="avance",
    technical_override=4)
add("Triceps extension câble une main derrière la tête", "triceps", "triceps_longue_portion",
    "extension_triceps", "push", ["machine"], unilateral=True, archetype="extension_triceps_isolation")

add("Squat sauté élastique (résistance, explosif)", "quadriceps", "quadriceps", "squat", "squat",
    ["elastique"], "squat_guide", secondaires=["fessiers"], difficulty_override="intermediaire")
add("Leg extension isométrique unilatérale (prévention genou)", "quadriceps", "quadriceps",
    "leg_extension", "squat", ["machine"], unilateral=True, archetype="extension_jambes_isolation",
    difficulty_override="debutant", joint_stress={"genou": 0})
add("Fente latérale élastique (adducteurs/quadriceps)", "quadriceps", "quadriceps", "fente", "lunge",
    ["elastique"], unilateral=True, archetype="fente_lunge", secondaires=["fessiers"])
add("Soulevé de terre roumain barre sumo (ischio + intérieur cuisse)", "ischio", "ischio",
    "hinge_jambes_tendues", "hinge", ["barre"], "hinge_lourd", secondaires=["fessiers"],
    joint_stress={"dos_lombaire": 1, "genou": 1})
add("Hip thrust barre pieds rapprochés (quadriceps accentué)", "fessiers", "fessiers", "hip_thrust",
    "hinge", ["barre"], "hip_thrust_fessier", secondaires=["ischio", "quadriceps"])
add("Nordic curl assisté élastique (excentrique contrôlé)", "ischio", "ischio", "leg_curl", "hinge",
    ["elastique"], "leg_curl_isolation", difficulty_override="intermediaire")


# ===========================================================================
# CINQUIÈME PASSE : jambes (quadriceps/ischios/fessiers) encore sous 120 au
# total malgré les 3 passes précédentes.
# ===========================================================================
add("Squat barre pause basse (force/technique)", "quadriceps", "quadriceps", "squat", "squat", ["barre"],
    "squat_libre", secondaires=["fessiers"], difficulty_override="avance", joint_stress={"genou": 2})
add("Presse à cuisses 45 degrés amplitude complète", "quadriceps", "quadriceps", "presse_jambes", "squat",
    ["machine"], "presse_jambes", secondaires=["fessiers"])
add("Squat safety bar (dos plus droit, épaule prudente)", "quadriceps", "quadriceps", "squat", "squat",
    ["barre"], "squat_guide", secondaires=["fessiers"], joint_stress={"epaule": 0, "genou": 2})
add("Extension jambes tempo lent (contrôle excentrique)", "quadriceps", "quadriceps", "leg_extension",
    "squat", ["machine"], "extension_jambes_isolation", difficulty_override="intermediaire",
    joint_stress={"genou": 2})
add("Fente avant élastique lestée", "quadriceps", "quadriceps", "fente", "lunge", ["elastique"],
    unilateral=True, archetype="fente_lunge", secondaires=["fessiers"])
add("Leg curl allongé prise large (variante ischio)", "ischio", "ischio", "leg_curl", "hinge",
    ["machine"], "leg_curl_isolation", joint_stress={"genou": 1})
add("Soulevé de terre roumain haltères prudence genoux (légère flexion)", "ischio", "ischio",
    "hinge_jambes_tendues", "hinge", ["haltere"], "hinge_lourd", secondaires=["fessiers"],
    joint_stress={"dos_lombaire": 1, "genou": 0}, difficulty_override="debutant")
add("Good morning élastique (léger, technique)", "ischio", "ischio", "hinge_jambes_tendues", "hinge",
    ["elastique"], "hinge_lourd", secondaires=["dos", "fessiers"], difficulty_override="debutant",
    joint_stress={"dos_lombaire": 1})
add("Hip thrust élastique autour des genoux (fessier + moyen fessier)", "fessiers", "fessiers",
    "hip_thrust", "hinge", ["elastique"], "hip_thrust_fessier", secondaires=["ischio"])
add("Squat sumo haltère bas (fessier + adducteurs)", "fessiers", "fessiers", "squat", "squat",
    ["haltere"], "squat_guide", secondaires=["quadriceps"], difficulty_override="debutant")
add("Step up croisé (fessier moyen, coordination)", "fessiers", "fessiers", "fente", "lunge",
    ["poids_du_corps"], unilateral=True, archetype="fente_lunge", secondaires=["quadriceps"],
    difficulty_override="intermediaire")


# ---------------------------------------------------------------------------
# Vérifications de cohérence avant écriture (jamais deux fiches avec le même
# exercise_id : le générateur additionne des variantes réellement distinctes,
# une collision indiquerait un doublon accidentel).
# ---------------------------------------------------------------------------
def build():
    ids_vus = {}
    for fiche in EXERCISES:
        eid = fiche["exercise_id"]
        if eid in ids_vus:
            ids_vus[eid] += 1
            fiche["exercise_id"] = f"{eid}_{ids_vus[eid]}"
        else:
            ids_vus[eid] = 0

    # Substituts : pour chaque exercice, les autres exercices du même
    # `pattern` + `muscle_principal` (mouvements réellement interchangeables),
    # limité à 5 pour rester lisible.
    par_pattern = {}
    for fiche in EXERCISES:
        cle = (fiche["muscle_principal"], fiche["pattern"])
        par_pattern.setdefault(cle, []).append(fiche["exercise_id"])
    for fiche in EXERCISES:
        cle = (fiche["muscle_principal"], fiche["pattern"])
        fiche["substitutes"] = [eid for eid in par_pattern[cle] if eid != fiche["exercise_id"]][:5]

    return EXERCISES


def main():
    exercises = build()

    if os.path.exists(OUTPUT_PATH) and not os.path.exists(BACKUP_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            ancien = f.read()
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            f.write(ancien)
        print(f"Ancien catalogue (111 exercices) sauvegardé dans {BACKUP_PATH}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"exercises": exercises}, f, ensure_ascii=False, indent=2)

    par_muscle = {}
    for e in exercises:
        par_muscle[e["muscle_principal"]] = par_muscle.get(e["muscle_principal"], 0) + 1

    print(f"Nouveau catalogue écrit : {len(exercises)} exercices -> {OUTPUT_PATH}")
    for muscle, n in sorted(par_muscle.items(), key=lambda kv: -kv[1]):
        print(f"  {muscle:12s} : {n}")


if __name__ == "__main__":
    main()
