# -*- coding: utf-8 -*-
"""
Aide à la validation humaine du catalogue (phase 18/24) : ce module ne
DÉCIDE jamais rien à la place d'un humain — il ne fait qu'agréger des
signaux déjà établis (`logic/exercise_quality.py`, phase 14) et quelques
vérifications de cohérence supplémentaires, pour que la revue (`logic/
exercise_review.py`, phase 14, inchangé : `approve_exercise`/`reject_
exercise`/`update_exercise_review`) aille plus vite. Ne modifie jamais un
`Exercise`, n'écrit jamais en base.

Ne redéfinit AUCUNE règle du moteur de recommandation (scoring.py, filters.py,
selector.py, fallback.py — tous inchangés, jamais importés ici).
"""
from logic.exercise_quality import _valeur, validate_exercise_quality
from logic.recommendation.exercise_order import COMPOUND_MOVEMENT_TYPES

# Plage de `technical_complexity` jugée cohérente avec chaque `difficulty_
# level` déclaré — mapping documenté (pas une mesure scientifique), sert
# uniquement à repérer une incohérence évidente (ex: difficulty_level=
# "debutant" avec technical_complexity=5) à faire vérifier par un humain,
# jamais à rejeter automatiquement quoi que ce soit.
PLAGE_TECHNICAL_COMPLEXITY_PAR_DIFFICULTE = {
    "debutant": (1, 2),
    "intermediaire": (2, 4),
    "avance": (3, 5),
}

# Seuil au-delà duquel un objectif "force" élevé sur un mouvement NON composé
# (cf. COMPOUND_MOVEMENT_TYPES, exercise_order.py, phase 8, réutilisé en
# lecture seule) mérite d'être vérifié — un exercice d'isolation peut
# légitimement contribuer à la force, mais rarement au niveau maximal.
SEUIL_FORCE_ELEVEE_SUR_ISOLATION = 8

# Seuil au-delà duquel un objectif "explosivite" élevé sur un exercice dont
# le SEUL équipement déclaré est une machine guidée mérite d'être vérifié
# (le travail explosif/pliométrique réel se fait rarement en machine guidée).
SEUIL_EXPLOSIVITE_ELEVEE_SUR_MACHINE = 7

DECISIONS_POSSIBLES = ("approve", "reject", "needs_changes")


def _categoriser_messages_qualite(messages):
    """Répartit les messages bruts de `exercise_quality.validate_exercise_
    quality` dans les catégories qui nous intéressent ici (les textes exacts
    sont ceux écrits en phase 14, pas dupliqués — seulement reconnus)."""
    muscle_pattern = [m for m in messages if m.startswith("muscle_principal=")]
    equipement = [m for m in messages if m.startswith("equipment")]
    scores = [m for m in messages if m.startswith("potentiel_hypertrophique=")]
    return muscle_pattern, equipement, scores


def _difficulte_incoherente(exercise):
    difficulty_level = _valeur(exercise, "difficulty_level")
    technical_complexity = _valeur(exercise, "technical_complexity")
    if difficulty_level is None or technical_complexity is None:
        return []

    plage = PLAGE_TECHNICAL_COMPLEXITY_PAR_DIFFICULTE.get(difficulty_level)
    if plage is None:
        return [f"difficulty_level='{difficulty_level}' non reconnu (attendu : debutant/intermediaire/avance)"]

    borne_min, borne_max = plage
    if not (borne_min <= technical_complexity <= borne_max):
        return [
            f"difficulty_level='{difficulty_level}' incohérent avec technical_complexity="
            f"{technical_complexity} (plage attendue : [{borne_min}, {borne_max}])"
        ]
    return []


def _objectifs_incompatibles(exercise):
    conflits = []
    movement_type = _valeur(exercise, "movement_type")
    equipment = _valeur(exercise, "equipment") or []
    objectifs = _valeur(exercise, "objectifs_adaptes") or {}

    force = objectifs.get("force")
    if (
        force is not None
        and force >= SEUIL_FORCE_ELEVEE_SUR_ISOLATION
        and movement_type is not None
        and movement_type not in COMPOUND_MOVEMENT_TYPES
    ):
        conflits.append(
            f"objectifs_adaptes['force']={force} très élevé pour un mouvement non composé "
            f"(movement_type='{movement_type}')"
        )

    explosivite = objectifs.get("explosivite")
    if explosivite is not None and explosivite >= SEUIL_EXPLOSIVITE_ELEVEE_SUR_MACHINE and equipment == ["machine"]:
        conflits.append(
            f"objectifs_adaptes['explosivite']={explosivite} élevé alors que l'équipement est "
            f"uniquement une machine guidée"
        )

    return conflits


def detect_conflicting_metadata(exercise):
    """detect_conflicting_metadata(exercise) -> {"muscle_pattern",
    "equipement", "difficulte", "objectifs", "scores_hypertrophiques"} :
    5 listes de chaînes (vides si aucun conflit dans la catégorie). Accepte
    une instance `Exercise` ou un dict fiche (même contrat que `exercise_
    quality.validate_exercise_quality`, réutilisé pour 3 des 5 catégories)."""
    rapport_qualite = validate_exercise_quality(exercise)
    muscle_pattern, equipement, scores = _categoriser_messages_qualite(
        rapport_qualite["errors"] + rapport_qualite["warnings"]
    )

    # Vérification d'équipement supplémentaire, spécifique à ce module : une
    # valeur d'équipement inconnue de EQUIPEMENTS_CONNUS mais déjà signalée
    # par le quality checker n'est pas dupliquée ici (cf. `equipement`
    # ci-dessus, qui couvre déjà ce cas via le message "equipment contient...").

    return {
        "muscle_pattern": muscle_pattern,
        "equipement": equipement,
        "difficulte": _difficulte_incoherente(exercise),
        "objectifs": _objectifs_incompatibles(exercise),
        "scores_hypertrophiques": scores,
    }


def suggest_review_decision(exercise):
    """suggest_review_decision(exercise) -> {"decision", "reasons",
    "confidence"}. `decision` est UNE SUGGESTION parmi DECISIONS_POSSIBLES,
    jamais appliquée automatiquement (aucun appel à `approve_exercise`/
    `reject_exercise` ici) :

      - "reject"       : au moins une erreur BLOQUANTE du quality checker
                         (ex: muscle_principal incompatible avec le pattern,
                         exercice actif mais totalement incomplet) — un
                         humain devrait très probablement rejeter ou corriger
                         avant d'approuver.
      - "needs_changes": aucune erreur bloquante, mais au moins un
                         avertissement qualité ou un conflit détecté ici
                         (difficulté/objectifs) — approuvable après
                         correction, pas en l'état.
      - "approve"      : aucune erreur, aucun avertissement, aucun conflit —
                         rien à signaler."""
    rapport_qualite = validate_exercise_quality(exercise)
    conflits = detect_conflicting_metadata(exercise)
    conflits_non_vides = [c for categorie in conflits.values() for c in categorie]

    if rapport_qualite["errors"]:
        decision = "reject"
        confidence = "haute"
    elif rapport_qualite["warnings"] or conflits_non_vides:
        decision = "needs_changes"
        confidence = "moyenne"
    else:
        decision = "approve"
        confidence = "haute"

    return {
        "decision": decision,
        "reasons": rapport_qualite["errors"] + rapport_qualite["warnings"],
        "confidence": confidence,
    }


def generate_review_summary(exercise):
    """generate_review_summary(exercise) -> dict structuré + un rendu texte
    ("resume_texte") prêt à être affiché tel quel dans un script/rapport —
    identité, classification, qualité, conflits, suggestion. N'écrit jamais
    rien, ne modifie jamais `exercise`."""
    exercise_id = _valeur(exercise, "exercise_id")
    name = _valeur(exercise, "name")
    rapport_qualite = validate_exercise_quality(exercise)
    conflits = detect_conflicting_metadata(exercise)
    suggestion = suggest_review_decision(exercise)

    identite = {
        "exercise_id": exercise_id,
        "name": name,
        "family": _valeur(exercise, "family"),
        "pattern": _valeur(exercise, "pattern"),
        "muscle_principal": _valeur(exercise, "muscle_principal"),
        "review_status": _valeur(exercise, "review_status"),
        "needs_review": _valeur(exercise, "needs_review"),
    }

    lignes_texte = [
        f"{exercise_id} — {name}",
        f"  famille={identite['family']} pattern={identite['pattern']} muscle={identite['muscle_principal']}",
        f"  statut revue actuel : {identite['review_status']} (needs_review={identite['needs_review']})",
        f"  suggestion : {suggestion['decision']} (confiance {suggestion['confidence']})",
    ]
    if rapport_qualite["errors"]:
        lignes_texte.append(f"  erreurs qualité : {rapport_qualite['errors']}")
    if rapport_qualite["warnings"]:
        lignes_texte.append(f"  avertissements qualité : {rapport_qualite['warnings']}")
    for categorie, messages in conflits.items():
        if messages:
            lignes_texte.append(f"  conflit [{categorie}] : {messages}")

    return {
        "identite": identite,
        "qualite": rapport_qualite,
        "conflits": conflits,
        "suggestion": suggestion,
        "resume_texte": "\n".join(lignes_texte),
    }
