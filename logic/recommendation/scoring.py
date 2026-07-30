# -*- coding: utf-8 -*-
"""
Fonction principale du moteur de recommandation : score_exercise(profile, exercise).

Combine les 8 facteurs validés (conception_moteur_recommandation.md partie 3) :
  1. Objectif             -> objectives.score_objectif_exercise
  2. Niveau                -> _score_niveau (ce module)
  3. Morphologie           -> biomechanics.score_morphologie
  4. Historique             -> stub neutre (ExerciseUsageLog n'existe pas encore)
  5. Préférence             -> filters.blessure_soft_penalty (le seul signal de
                               "préférence" déjà disponible sans ExerciseFeedback ;
                               j'aime/j'aime pas restera à ajouter quand cette
                               table existera)
  6. Fatigue                -> stub neutre (fatigue_cost absent du catalogue,
                               budget de séance hors périmètre sans assemblage
                               de séance — cf. fatigue.py)
  7. Autres sports           -> stub neutre (aucune formule chiffrée validée à
                               ce stade, cf. "problèmes rencontrés")
  8. Compatibilité biomécanique individuelle -> biomechanics.score_biomecanique_individuelle

Les facteurs 4/6/7 sont des stubs EXPLICITES (toujours 0, jamais d'exception),
documentés comme tels — pas une omission silencieuse. Rien de tout cela ne
constitue une génération de programme : cette fonction évalue un exercice
isolé pour un profil donné, sans notion de séance/semaine.
"""
from logic.recommendation import biomechanics, filters, objectives

# Phase 19/24 : import différé (dans score_exercise, pas ici en haut de
# fichier) pour éviter tout cycle d'import — logic/profile_analysis.py ne
# dépend lui-même que de filters.py/objectives.py, jamais de scoring.py,
# mais un import au niveau module ici obligerait Python à résoudre les deux
# fichiers dans un ordre précis ; l'import différé lève cette contrainte.

# --- Facteur "Niveau" --------------------------------------------------------
# Aucune formule chiffrée n'a été validée pour l'écart niveau/difficulté lui-
# même (seule sa modulation par tolerance_technique l'a été, cf. biomechanics.
# apply_tolerance_modulation). Barème de départ simple et documenté, à
# recalibrer empiriquement — cohérent avec conception_moteur_recommandation.md
# qui acte explicitement que le calibrage réel se fera avec des cas de test.
NIVEAU_ORDINAL = {
    "Débutant complet": 0,
    "Quelques mois d'expérience": 1,
    "Intermédiaire": 2,
    "Avancé": 3,
}
DIFFICULTY_ORDINAL = {"debutant": 0, "intermediaire": 2, "avance": 3}
PENALITE_PAR_NIVEAU_ECART = 3

# Correspondance questionnaire (catégorie 4, "exercices maîtrisés") -> pattern
# du catalogue, décidée en phase 4 (resolution_11_points_bloquants.md point
# 1d : correspondance au niveau du pattern, pas de l'exercice exact ni de la
# famille). À tenir à jour si le catalogue change de convention de nommage.
EXERCICE_MAITRISE_TO_PATTERN = {
    "Squat barre": "squat",
    "Soulevé de terre": "rdl",
    "Développé couché barre": "developpe_plat",
    "Tractions": "tirage_vertical",
    "Développé militaire barre": "developpe_militaire",
}


def _mastered_patterns(profile):
    maitrises = getattr(profile, "exercices_maitrises", None) or []
    return {EXERCICE_MAITRISE_TO_PATTERN[m] for m in maitrises if m in EXERCICE_MAITRISE_TO_PATTERN}


def _score_niveau(profile, exercise):
    """Un mouvement maîtrisé (par pattern) annule la pénalité de complexité,
    quel que soit le niveau global déclaré (questionnaire_optimise.md,
    resolution_11_points_bloquants.md point 1)."""
    if getattr(exercise, "pattern", None) in _mastered_patterns(profile):
        return 0

    difficulty_ordinal = DIFFICULTY_ORDINAL.get(getattr(exercise, "difficulty_level", None))
    if difficulty_ordinal is None:
        return 0  # catalogue pas encore renseigné pour cet exercice -> neutre, jamais de supposition

    user_ordinal = NIVEAU_ORDINAL.get(getattr(profile, "niveau_musculation", None), 2)  # repli intermédiaire
    ecart = difficulty_ordinal - user_ordinal
    if ecart <= 0:
        return 0

    penalite_brute = ecart * PENALITE_PAR_NIVEAU_ECART
    penalite_effective = biomechanics.apply_tolerance_modulation(profile, penalite_brute)
    return -penalite_effective


# --- Facteurs stubs (tables/formules pas encore disponibles) ----------------

def _score_historique(profile, exercise):
    """Neutre : ExerciseUsageLog n'existe pas encore (historique/feedback,
    phase ultérieure du plan d'évolution). Toujours 0, jamais d'exception."""
    return 0


def _score_fatigue(profile, exercise):
    """Neutre : `fatigue_cost` absent du catalogue (phase 2 n'a retenu que le
    sous-ensemble critique) et le budget de séance (fatigue.py) ne s'applique
    qu'à l'assemblage d'une séance complète, hors périmètre de cette phase."""
    return 0


def _score_autres_sports(profile, exercise):
    """Neutre pour l'instant : aucune formule chiffrée n'a été validée dans
    resolution_11_points_bloquants.md pour ce facteur (contrairement aux 5
    autres, qui ont des formules/seuils précis) — seule une description
    qualitative existe ("pénalise le volume articulation déjà sollicitée").
    Inventer une formule non validée irait contre la consigne "aucune
    modification métier supplémentaire sans justification"."""
    return 0


# --- Pondération de combinaison (première passe, à calibrer empiriquement) -

BASE_SCORE = 50
# Retour Samy (« pas juste mettre des exercices pour mettre des exercices, mais
# vraiment choisir les exercices par rapport aux questions ») :
#
# Diagnostic mesuré — les 52 exercices de dos du catalogue obtenaient TOUS
# exactement 100. Le score ne discriminait donc rien du tout, et l'ordre final
# ne dépendait que de l'ordre de lecture du catalogue.
#
# Cause : le commentaire ci-dessous supposait un score "objectif" brut compris
# entre 0 et ~3, d'où un poids de 10 pour l'étaler sur ~30 points. En pratique
# `objectives.score_objectif_exercise` renvoie plutôt 6,5 à 8 — le produit
# atteignait donc ~70, et 50 + 70 = 120, écrêté à 100 pour tout le monde. Tous
# les autres critères (niveau, morphologie, biomécanique) devenaient invisibles
# puisqu'ils s'appliquaient au-delà du plafond.
#
# Poids ramené à 5 : la composante objectif occupe ~33 à 40 points, le total
# reste sous le plafond, et les critères de personnalisation redeviennent
# décisifs au lieu d'être absorbés par l'écrêtage.
WEIGHTS = {
    "objectif": 5,        # score brut ~6,5 a ~8 (vecteur x objectifs_adaptes) -> ~33 a 40 points
    "niveau": 1,          # deja exprime en points
    "morphologie": 1,     # deja exprime en points
    "historique": 1,
    "preference": 1,      # note : n'est PAS utilise ici, applique a part (pourcentage), voir plus bas
    "fatigue": 1,
    "autres_sports": 1,
    "biomecanique": 1,
}


def score_exercise(profile, exercise, feedback_repository=None):
    """Retourne {"score_final", "excluded", "exclusion_reason", "details",
    "profile_analysis"}. `score_final` est toujours dans [0, 100] quand
    l'exercice n'est pas exclu ; `None` s'il l'est (un exercice exclu n'a pas
    de score, il ne doit simplement jamais être proposé).

    "profile_analysis" (phase 19/24, clé ADDITIVE — ne change ni le calcul
    du score ni aucune des clés précédentes, cf. logic/profile_analysis.py) :
    résumé lisible du profil (niveau/objectif dominant/contraintes/forces/
    faiblesses/risques), utile à l'appelant pour expliquer une sélection ou
    prioriser une revue, jamais utilisé ici pour modifier `score_final`."""
    # Import différé : voir le commentaire en haut de fichier (cycle d'import).
    from logic.profile_analysis import analyze_profile

    profile_analysis_result = analyze_profile(profile)

    reason = filters.exclusion_reason(profile, exercise, feedback_repository=feedback_repository)
    if reason:
        return {
            "score_final": None,
            "excluded": True,
            "exclusion_reason": reason,
            "details": {k: 0 for k in WEIGHTS},
            "profile_analysis": profile_analysis_result,
        }

    details = {
        "objectif": objectives.score_objectif_exercise(profile, exercise),
        "niveau": _score_niveau(profile, exercise),
        "morphologie": biomechanics.score_morphologie(profile, exercise),
        "historique": _score_historique(profile, exercise),
        "preference": filters.blessure_soft_penalty(profile, exercise),  # en pourcentage, pas en points
        "fatigue": _score_fatigue(profile, exercise),
        "autres_sports": _score_autres_sports(profile, exercise),
        "biomecanique": biomechanics.score_biomecanique_individuelle(profile, exercise),
    }

    raw = BASE_SCORE + sum(
        details[k] * WEIGHTS[k] for k in WEIGHTS if k != "preference"
    )
    preference_pct = details["preference"]
    final = raw * (1 + preference_pct / 100)
    final = max(0, min(100, final))

    return {
        "score_final": round(final, 2),
        "excluded": False,
        "exclusion_reason": None,
        "details": details,
        "profile_analysis": profile_analysis_result,
    }


def evaluate_exercises(profile, exercises, feedback_repository=None):
    """Évalue une liste d'exercices pour un profil donné. Retourne la liste
    complète (y compris les exclus, avec `excluded=True`) — filtrer/trier
    reste au choix de l'appelant ; ce n'est toujours pas une génération de
    séance, seulement une évaluation exercice par exercice."""
    return [
        {"exercise_id": getattr(ex, "exercise_id", None), **score_exercise(profile, ex, feedback_repository=feedback_repository)}
        for ex in exercises
    ]
