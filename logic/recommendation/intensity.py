# -*- coding: utf-8 -*-
"""
Intensité recommandée (phase 9/16, section 5) : "faible" / "modérée" /
"élevée". Une indication QUALITATIVE pour l'utilisateur — pas un calcul de
charge exacte ni de %1RM (hors périmètre de cette phase, cf.
architecture_v2_consolidation.md, étapes ultérieures : charge personnalisée,
progression, auto-régulation).

Aucun barème chiffré n'a été validé dans les documents de conception pour ce
point précis (contrairement aux 8 facteurs de scoring.py) : base par
objectif dominant (réutilise le vecteur déjà validé de `objectives.py`),
plus les 2 garde-fous et la modulation par tolérance explicitement demandés
dans cette phase — un premier jet documenté, à calibrer empiriquement.
"""
from logic.recommendation import objectives
from logic.recommendation.scoring import _mastered_patterns

NIVEAUX_INTENSITE = ["faible", "modérée", "élevée"]

# Interprétation documentée du lien objectif dominant -> intensité qualitative :
#   - force               : charges proches du maximum -> élevée.
#   - hypertrophie         : charges modérées -> modérée.
#   - endurance_musculaire : charges légères, répétitions hautes -> faible.
#   - perte_de_gras        : même logique que l'endurance (reps hautes,
#                            charges sous-maximales) -> faible.
#   - explosivite          : la consigne insiste sur "priorité vitesse" (pas
#                            sur la charge maximale : une charge trop lourde
#                            ralentit le mouvement) -> modérée, pas élevée.
#                            Choix documenté, pas une formule validée.
BASE_INTENSITE_PAR_OBJECTIF = {
    "force": "élevée",
    "hypertrophie": "modérée",
    "endurance_musculaire": "faible",
    "perte_de_gras": "faible",
    "explosivite": "modérée",
}
BASE_INTENSITE_DEFAUT = "modérée"


def _index(niveau_intensite):
    return NIVEAUX_INTENSITE.index(niveau_intensite)


def _plafonner(niveau_intensite, plafond):
    return niveau_intensite if _index(niveau_intensite) <= _index(plafond) else plafond


def _reduire(niveau_intensite, paliers=1):
    return NIVEAUX_INTENSITE[max(0, _index(niveau_intensite) - paliers)]


def calculate_intensity(profile, exercise):
    """calculate_intensity(profile, exercise) -> "faible"/"modérée"/"élevée".
    Base = objectif dominant du profil (vecteur `objectives.get_objective_vector`,
    déjà validé, dominante = valeur la plus élevée). Puis garde-fous section 5 :
    - Débutant : jamais "élevée" (plafond "modérée").
    - Avancé : "élevée" seulement si le PATTERN de l'exercice est un mouvement
      maîtrisé déclaré par l'utilisateur (même correspondance que
      scoring.EXERCICE_MAITRISE_TO_PATTERN) ; sinon plafond "modérée" comme
      les autres niveaux.
    - Tolérance technique faible (<=2) : réduit l'intensité d'un palier."""
    vector = objectives.get_objective_vector(profile)
    dominant = max(vector, key=vector.get)
    intensite = BASE_INTENSITE_PAR_OBJECTIF.get(dominant, BASE_INTENSITE_DEFAUT)

    niveau = getattr(profile, "niveau_musculation", None)
    if niveau == "Débutant complet":
        intensite = _plafonner(intensite, "modérée")
    elif niveau == "Avancé":
        pattern = getattr(exercise, "pattern", None)
        if pattern not in _mastered_patterns(profile):
            intensite = _plafonner(intensite, "modérée")

    tolerance = getattr(profile, "tolerance_technique", None)
    if tolerance is None:
        tolerance = 3  # valeur neutre (resolution_11_points_bloquants.md point 5)
    if tolerance <= 2:
        intensite = _reduire(intensite, 1)

    return intensite
