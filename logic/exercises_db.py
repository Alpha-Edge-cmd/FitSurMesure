# -*- coding: utf-8 -*-
"""
Base de données d'exercices.

Chaque exercice :
- name        : nom affiché
- pattern     : schéma de mouvement (ex: "developpe_plat"). Un seul exercice est
                choisi par pattern -> garantit de la variété (pas 3 variantes du
                même mouvement dans une séance).
- equip       : type de matériel nécessaire, un parmi :
                "barre"          -> barre + disques (souvent banc/rack : salle ou gros équipement maison)
                "haltere"        -> haltères (souvent disponible même avec peu de matériel à la maison)
                "poids_du_corps" -> aucun matériel, ou juste une barre de traction/un banc simple
                "elastique"      -> élastique de résistance (facile à avoir à la maison)
                "machine"        -> machine guidée, poulie/câble (nécessite une salle)
- kind        : "compose" ou "isolation"
- force       : True si l'exercice peut servir de mouvement "force" en ouverture
- avoid       : liste de tags d'exclusion. L'exercice est retiré si un de ces tags
                est présent dans les contraintes de l'utilisateur.
                Tags possibles : epaule, dos_lombaire, genou, talon, poignet,
                cant_do_pullups, cant_do_dips, squat_libre_non, deadlift_barre_non
- priority    : plus petit = choisi en premier (au sein d'un même pattern, et pour
                classer les patterns entre eux)
- morpho      : (optionnel) tags de morphologie pour lesquels cette variante est
                particulièrement adaptée (bras_longs, bras_courts, jambes_longues,
                jambes_courtes)
"""

EXERCISES = {

    "pecs": [
        {"name": "Développé couché barre", "pattern": "developpe_plat", "equip": "barre", "kind": "compose", "force": True, "avoid": [], "priority": 1, "morpho": ["bras_courts"]},
        {"name": "Développé couché haltères", "pattern": "developpe_plat", "equip": "haltere", "kind": "compose", "force": True, "avoid": [], "priority": 2, "morpho": ["bras_longs"]},
        {"name": "Développé couché machine", "pattern": "developpe_plat", "equip": "machine", "kind": "compose", "force": True, "avoid": [], "priority": 2},
        {"name": "Développé incliné haltères", "pattern": "developpe_incline", "equip": "haltere", "kind": "compose", "force": False, "avoid": [], "priority": 2, "morpho": ["bras_longs"]},
        {"name": "Développé incliné barre", "pattern": "developpe_incline", "equip": "barre", "kind": "compose", "force": False, "avoid": [], "priority": 2, "morpho": ["bras_courts"]},
        {"name": "Développé incliné machine", "pattern": "developpe_incline", "equip": "machine", "kind": "compose", "force": False, "avoid": [], "priority": 2},
        {"name": "Développé décliné barre", "pattern": "developpe_decline", "equip": "barre", "kind": "compose", "force": False, "avoid": [], "priority": 3},
        {"name": "Développé décliné machine", "pattern": "developpe_decline", "equip": "machine", "kind": "compose", "force": False, "avoid": [], "priority": 3},
        {"name": "Pec deck / Butterfly machine", "pattern": "fly", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Écarté poulie (fly)", "pattern": "fly", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Écarté haltères", "pattern": "fly", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 4},
        {"name": "Écarté poulie incliné (haut vers bas)", "pattern": "fly_incline", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
        {"name": "Dips buste penché en avant", "pattern": "dips_pecs", "equip": "poids_du_corps", "kind": "compose", "force": False, "avoid": ["cant_do_dips", "epaule", "poignet"], "priority": 4},
        {"name": "Pompes (variante lestée ou pieds surélevés)", "pattern": "pompes", "equip": "poids_du_corps", "kind": "compose", "force": False, "avoid": ["poignet"], "priority": 5},
        {"name": "Pull-over haltère (pecs/dorsaux)", "pattern": "pull_over_pecs", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 5},
    ],

    "epaules": [
        {"name": "Développé militaire barre", "pattern": "developpe_militaire", "equip": "barre", "kind": "compose", "force": True, "avoid": ["epaule"], "priority": 1},
        {"name": "Développé militaire haltères", "pattern": "developpe_militaire", "equip": "haltere", "kind": "compose", "force": True, "avoid": ["epaule"], "priority": 1},
        {"name": "Développé épaules machine", "pattern": "developpe_militaire", "equip": "machine", "kind": "compose", "force": True, "avoid": ["epaule"], "priority": 1},
        {"name": "Élévations latérales haltères", "pattern": "elevation_laterale", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Élévations latérales poulie", "pattern": "elevation_laterale", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Élévations latérales élastique", "pattern": "elevation_laterale", "equip": "elastique", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Élévations frontales haltères", "pattern": "elevation_frontale", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Oiseau / rear delt fly haltères", "pattern": "rear_delt", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Face pull poulie", "pattern": "rear_delt", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Développé Arnold haltères", "pattern": "developpe_arnold", "equip": "haltere", "kind": "compose", "force": True, "avoid": ["epaule"], "priority": 2},
        {"name": "Élévations latérales assis (strict)", "pattern": "elevation_laterale", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
        {"name": "Rowing menton barre EZ (upright row)", "pattern": "upright_row", "equip": "barre", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 4},
        {"name": "Rowing menton haltères (upright row)", "pattern": "upright_row", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 4},
        {"name": "Y-raises haltères (coiffe des rotateurs / trapèzes bas)", "pattern": "y_raises", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 4},
        {"name": "Cuban press haltères", "pattern": "cuban_press", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 4},
        {"name": "Développé militaire assis élastique", "pattern": "developpe_militaire", "equip": "elastique", "kind": "compose", "force": False, "avoid": ["epaule"], "priority": 3},
    ],

    "triceps": [
        {"name": "Dips buste droit", "pattern": "dips_triceps", "equip": "poids_du_corps", "kind": "compose", "force": True, "avoid": ["cant_do_dips", "poignet"], "priority": 1},
        {"name": "Développé prise serrée barre (triceps)", "pattern": "close_grip_press", "equip": "barre", "kind": "compose", "force": True, "avoid": ["poignet"], "priority": 1},
        {"name": "Extension triceps allongé haltères (skull crusher)", "pattern": "skull_crusher", "equip": "haltere", "kind": "compose", "force": True, "avoid": ["epaule"], "priority": 1},
        {"name": "Extension poulie corde", "pattern": "pushdown", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Extension poulie barre", "pattern": "pushdown", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Extension nuque haltère", "pattern": "overhead_extension", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 3},
        {"name": "Extension triceps élastique", "pattern": "pushdown", "equip": "elastique", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
        {"name": "Dips sur banc (bench dips)", "pattern": "dips_banc", "equip": "poids_du_corps", "kind": "compose", "force": False, "avoid": ["poignet"], "priority": 3},
        {"name": "Extension triceps unilatérale poulie", "pattern": "pushdown_unilateral", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
        {"name": "Kickback triceps haltère", "pattern": "kickback_triceps", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 5},
    ],

    "dos": [
        {"name": "Tractions", "pattern": "tirage_vertical", "equip": "poids_du_corps", "kind": "compose", "force": True, "avoid": ["cant_do_pullups", "epaule"], "priority": 1, "morpho": ["bras_courts"]},
        {"name": "Tirage vertical poulie (devant ou nuque)", "pattern": "tirage_vertical", "equip": "machine", "kind": "compose", "force": True, "avoid": [], "priority": 1, "morpho": ["bras_longs"]},
        {"name": "Tirage vertical élastique (bande fixée en hauteur)", "pattern": "tirage_vertical", "equip": "elastique", "kind": "compose", "force": False, "avoid": [], "priority": 3},
        {"name": "Rowing barre", "pattern": "rowing", "equip": "barre", "kind": "compose", "force": False, "avoid": ["dos_lombaire"], "priority": 2},
        {"name": "Rowing haltère", "pattern": "rowing", "equip": "haltere", "kind": "compose", "force": False, "avoid": [], "priority": 2},
        {"name": "Rowing machine", "pattern": "rowing", "equip": "machine", "kind": "compose", "force": False, "avoid": [], "priority": 2},
        {"name": "Rowing élastique", "pattern": "rowing", "equip": "elastique", "kind": "compose", "force": False, "avoid": [], "priority": 3},
        # NB : ces variantes partagent volontairement le pattern "rowing" avec les 4
        # exercices ci-dessus (Rowing barre/haltère/machine/élastique) — ce sont toutes
        # des tirages horizontaux (rowing), et n'en garder qu'un seul par séance évite
        # de se retrouver avec 2-3 "rowing" différents le même jour (ex : Rowing T-bar
        # + Rowing haltère). La variété du dos vient plutôt d'alterner tirage vertical /
        # rowing / pull-over / shrugs.
        {"name": "Rowing inversé poids du corps (sous une barre)", "pattern": "rowing", "equip": "poids_du_corps", "kind": "compose", "force": False, "avoid": [], "priority": 3},
        {"name": "Rowing T-bar", "pattern": "rowing", "equip": "barre", "kind": "compose", "force": True, "avoid": ["dos_lombaire"], "priority": 2},
        {"name": "Tirage horizontal poulie", "pattern": "rowing", "equip": "machine", "kind": "compose", "force": False, "avoid": [], "priority": 3},
        {"name": "Tirage horizontal prise serrée poulie", "pattern": "rowing", "equip": "machine", "kind": "compose", "force": False, "avoid": [], "priority": 3},
        {"name": "Pull-over haltère (dos)", "pattern": "pull_over", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 4},
        {"name": "Shrugs haltères (trapèzes)", "pattern": "shrugs", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 5},
        {"name": "Shrugs à la machine", "pattern": "shrugs", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 5},
    ],

    "biceps": [
        {"name": "Curl barre", "pattern": "curl_standard", "equip": "barre", "kind": "isolation", "force": True, "avoid": [], "priority": 1},
        {"name": "Curl haltères", "pattern": "curl_standard", "equip": "haltere", "kind": "isolation", "force": True, "avoid": [], "priority": 1},
        {"name": "Curl élastique", "pattern": "curl_standard", "equip": "elastique", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Curl marteau haltères", "pattern": "curl_marteau", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Curl pupitre (preacher)", "pattern": "curl_isolation", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Curl poulie", "pattern": "curl_isolation", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Curl concentré haltère", "pattern": "curl_concentre", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
        {"name": "Curl prise inversée barre EZ", "pattern": "curl_inverse", "equip": "barre", "kind": "isolation", "force": False, "avoid": ["poignet"], "priority": 4},
        {"name": "Curl prise inversée haltères", "pattern": "curl_inverse", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["poignet"], "priority": 4},
        {"name": "Curl araignée (spider curl) banc incliné haltères", "pattern": "curl_spider", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
        {"name": "Curl araignée machine", "pattern": "curl_spider", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
        {"name": "Curl 21s barre EZ", "pattern": "curl_21s", "equip": "barre", "kind": "isolation", "force": False, "avoid": [], "priority": 5},
        {"name": "Curl zottman haltères", "pattern": "curl_zottman", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["poignet"], "priority": 5},
    ],

    "quadriceps": [
        {"name": "Squat barre (back squat)", "pattern": "squat", "equip": "barre", "kind": "compose", "force": True, "avoid": ["genou", "squat_libre_non"], "priority": 1, "morpho": ["jambes_courtes"]},
        {"name": "Squat guidé (smith machine)", "pattern": "squat", "equip": "machine", "kind": "compose", "force": True, "avoid": ["genou"], "priority": 1},
        {"name": "Squat gobelet haltère", "pattern": "squat", "equip": "haltere", "kind": "compose", "force": True, "avoid": ["genou"], "priority": 1, "morpho": ["jambes_longues"]},
        {"name": "Front squat barre", "pattern": "front_squat", "equip": "barre", "kind": "compose", "force": True, "avoid": ["genou", "poignet"], "priority": 2, "morpho": ["jambes_longues"]},
        {"name": "Presse à cuisses", "pattern": "presse", "equip": "machine", "kind": "compose", "force": False, "avoid": [], "priority": 2},
        {"name": "Hack squat machine", "pattern": "presse", "equip": "machine", "kind": "compose", "force": False, "avoid": ["genou"], "priority": 2},
        {"name": "Fentes haltères", "pattern": "fentes", "equip": "haltere", "kind": "compose", "force": False, "avoid": ["genou"], "priority": 3},
        {"name": "Fentes marchées poids du corps", "pattern": "fentes", "equip": "poids_du_corps", "kind": "compose", "force": False, "avoid": ["genou"], "priority": 3},
        {"name": "Step-up banc haltères", "pattern": "step_up", "equip": "haltere", "kind": "compose", "force": False, "avoid": ["genou"], "priority": 4},
        {"name": "Leg extension", "pattern": "leg_extension", "equip": "machine", "kind": "isolation", "force": False, "avoid": ["genou"], "priority": 4},
    ],

    "ischio": [
        {"name": "Soulevé de terre roumain barre", "pattern": "rdl", "equip": "barre", "kind": "compose", "force": True, "avoid": ["dos_lombaire", "deadlift_barre_non"], "priority": 1, "morpho": ["jambes_courtes"]},
        {"name": "Soulevé de terre roumain haltères", "pattern": "rdl", "equip": "haltere", "kind": "compose", "force": True, "avoid": ["dos_lombaire"], "priority": 1},
        # Pattern "rdl" volontairement partagé avec le RDL ci-dessus : ce sont deux
        # variantes de soulevé de terre (même famille de mouvement), en garder une
        # seule par séance libère une place pour un mouvement vraiment différent
        # (leg curl, hyperextension...) plutôt que 2x "soulevé de terre".
        {"name": "Soulevé de terre sumo barre", "pattern": "rdl", "equip": "barre", "kind": "compose", "force": True, "avoid": ["dos_lombaire", "deadlift_barre_non"], "priority": 2, "morpho": ["jambes_longues"]},
        {"name": "Leg curl (allongé ou assis)", "pattern": "leg_curl", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Leg curl nordique assisté", "pattern": "leg_curl", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["genou"], "priority": 3},
        {"name": "Leg curl serviette au sol (slide curl)", "pattern": "leg_curl", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["genou"], "priority": 3},
        {"name": "Extension lombaire (banc à hyperextension)", "pattern": "hyperextension", "equip": "machine", "kind": "compose", "force": False, "avoid": ["dos_lombaire"], "priority": 3},
        {"name": "Fentes arrière déficit haltères (accent ischio)", "pattern": "fentes_ischio", "equip": "haltere", "kind": "compose", "force": False, "avoid": ["genou"], "priority": 3},
        {"name": "Extension de hanche jambe tendue élastique", "pattern": "hip_hinge_elastique", "equip": "elastique", "kind": "isolation", "force": False, "avoid": ["dos_lombaire"], "priority": 3},
    ],

    "fessiers": [
        {"name": "Hip thrust barre", "pattern": "hip_thrust", "equip": "barre", "kind": "compose", "force": True, "avoid": [], "priority": 1},
        {"name": "Hip thrust machine", "pattern": "hip_thrust", "equip": "machine", "kind": "compose", "force": True, "avoid": [], "priority": 1},
        {"name": "Pont fessier poids du corps", "pattern": "hip_thrust", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Fentes bulgares haltères", "pattern": "fentes_bulgares", "equip": "haltere", "kind": "compose", "force": False, "avoid": ["genou"], "priority": 2},
        {"name": "Squat sumo haltère (accent fessiers)", "pattern": "squat_sumo", "equip": "haltere", "kind": "compose", "force": False, "avoid": ["genou"], "priority": 2, "morpho": ["jambes_longues"]},
        {"name": "Abduction hanche machine", "pattern": "abduction", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Kickback fessier poulie", "pattern": "kickback_fessier", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 3},
        {"name": "Extension de hanche au sol (donkey kick)", "pattern": "donkey_kick", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["genou"], "priority": 4},
    ],

    "mollets": [
        {"name": "Mollets debout machine", "pattern": "mollets_droit", "equip": "machine", "kind": "isolation", "force": False, "avoid": ["talon"], "priority": 1},
        {"name": "Mollets à la presse à cuisses", "pattern": "mollets_droit", "equip": "machine", "kind": "isolation", "force": False, "avoid": ["talon"], "priority": 1},
        {"name": "Mollets debout poids du corps (marche surélevée)", "pattern": "mollets_droit", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["talon"], "priority": 2},
        {"name": "Mollets debout haltères (unilatéral)", "pattern": "mollets_droit", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["talon"], "priority": 2},
        {"name": "Mollets debout barre (sur les épaules)", "pattern": "mollets_droit", "equip": "barre", "kind": "isolation", "force": False, "avoid": ["talon"], "priority": 3},
        {"name": "Mollets assis machine", "pattern": "mollets_plie", "equip": "machine", "kind": "isolation", "force": False, "avoid": [], "priority": 1},
        {"name": "Mollets assis lestés (haltère sur les genoux)", "pattern": "mollets_plie", "equip": "haltere", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Donkey calf raise (buste penché) poids du corps", "pattern": "mollets_donkey", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["talon"], "priority": 3},
        {"name": "Sauts à la corde / multibonds (mollets en pliométrie)", "pattern": "mollets_pliometrie", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["talon", "genou"], "priority": 4},
    ],

    "abdos": [
        {"name": "Planche (gainage)", "pattern": "gainage_statique", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": [], "priority": 1},
        {"name": "Crunch poulie", "pattern": "crunch", "equip": "machine", "kind": "isolation", "force": False, "avoid": ["dos_lombaire"], "priority": 2},
        {"name": "Crunch poids du corps", "pattern": "crunch", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": [], "priority": 2},
        {"name": "Relevé de jambes suspendu", "pattern": "releve_jambes", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["epaule"], "priority": 3},
        {"name": "Roulette abdominale (ab wheel)", "pattern": "ab_wheel", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": ["dos_lombaire", "poignet"], "priority": 3},
        {"name": "Russian twist lesté", "pattern": "rotation_tronc", "equip": "haltere", "kind": "isolation", "force": False, "avoid": ["dos_lombaire"], "priority": 4},
        {"name": "Crunch inversé (relevé de bassin)", "pattern": "crunch_inverse", "equip": "poids_du_corps", "kind": "isolation", "force": False, "avoid": [], "priority": 4},
    ],
}

# Regroupement des muscles par jour selon le type de split
SPLITS = {
    "full_body": {
        "label": "Full Body",
        "jours": [
            {"nom": "Séance A", "muscles": ["quadriceps", "pecs", "dos", "epaules", "ischio", "abdos"]},
            {"nom": "Séance B", "muscles": ["ischio", "dos", "pecs", "epaules", "quadriceps", "abdos"]},
            {"nom": "Séance C", "muscles": ["quadriceps", "epaules", "dos", "pecs", "fessiers", "abdos"]},
        ],
        "exos_par_muscle_defaut": 1,
    },
    "upper_lower": {
        "label": "Upper / Lower",
        "jours": [
            {"nom": "Upper A", "muscles": ["pecs", "dos", "epaules", "biceps", "triceps"]},
            {"nom": "Lower A", "muscles": ["quadriceps", "ischio", "fessiers", "mollets", "abdos"]},
            {"nom": "Upper B", "muscles": ["dos", "pecs", "epaules", "triceps", "biceps"]},
            {"nom": "Lower B", "muscles": ["ischio", "quadriceps", "fessiers", "mollets", "abdos"]},
        ],
        "exos_par_muscle_defaut": 2,
    },
    "ppl": {
        "label": "Push / Pull / Legs",
        "jours": [
            {"nom": "Push", "muscles": ["pecs", "epaules", "triceps"]},
            {"nom": "Pull", "muscles": ["dos", "biceps"]},
            {"nom": "Legs", "muscles": ["quadriceps", "ischio", "fessiers", "mollets", "abdos"]},
        ],
        "exos_par_muscle_defaut": 3,
    },
    "arnold": {
        "label": "Arnold Split",
        "jours": [
            {"nom": "Torse / Dos", "muscles": ["pecs", "dos"]},
            {"nom": "Épaules / Bras", "muscles": ["epaules", "biceps", "triceps"]},
            {"nom": "Jambes", "muscles": ["quadriceps", "ischio", "fessiers", "mollets", "abdos"]},
        ],
        "exos_par_muscle_defaut": 3,
    },
}

MUSCLE_LABELS = {
    "pecs": "Pectoraux", "epaules": "Épaules", "triceps": "Triceps",
    "dos": "Dos", "biceps": "Biceps", "quadriceps": "Quadriceps",
    "ischio": "Ischio-jambiers", "fessiers": "Fessiers", "mollets": "Mollets",
    "abdos": "Abdominaux",
}

BLESSURE_TAGS = {
    "Épaule": "epaule",
    "Dos / lombaires": "dos_lombaire",
    "Genoux": "genou",
    "Chevilles / talons": "talon",
    "Poignets": "poignet",
}

EXO_INCAPABLE_TAGS = {
    "Tractions": "cant_do_pullups",
    "Dips": "cant_do_dips",
    "Squat barre libre": "squat_libre_non",
    "Soulevé de terre barre": "deadlift_barre_non",
}
