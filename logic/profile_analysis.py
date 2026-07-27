# -*- coding: utf-8 -*-
"""
Analyse agrégée d'un profil (phase 19/24) : `analyze_profile(snapshot)`
rassemble en UNE lecture ce que le moteur calcule déjà, dispersé dans
plusieurs modules (`objectives.py` pour le vecteur d'objectif, `filters.py`
pour le rang de sévérité des blessures, les colonnes brutes du
`ProfileSnapshot` lui-même pour mobilité/amplitude/tolérance technique) — ne
redéfinit AUCUNE règle de ces modules, ne fait que les relire et les
résumer de façon lisible par un humain (ou par un autre module du moteur,
cf. section "branchement").

Fonction pure et sans effet de bord : ne modifie jamais `snapshot`, n'écrit
jamais en base, ne lève jamais d'exception sur un profil incomplet (mêmes
garanties que `scoring.py`/`biomechanics.py`, valeurs neutres plutôt que
suppositions).

Branchement (section 2 de la consigne) : `logic/recommendation/scoring.py`,
`selector.py` et `workout_generator.py` importent ce module et attachent son
résultat comme métadonnée ADDITIVE à leurs sorties existantes (une clé en
plus dans un dict déjà retourné) — aucune signature publique changée, aucune
valeur déjà calculée modifiée. Voir le commentaire "phase 19/24" dans chacun
de ces trois fichiers pour le point d'intégration exact.
"""
from logic.recommendation import filters, objectives

# Rang de sévérité à partir duquel une blessure est considérée comme une
# vraie "contrainte" à mentionner (pas seulement un risque théorique) —
# réutilise filters.SEVERITE_RANG (phase 6, inchangé) plutôt que d'inventer
# une nouvelle échelle : rang 2 = "Gêne modérée régulière", rang 3 =
# "Douleur invalidante".
RANG_CONTRAINTE_MINIMUM = 2


def _vecteur_et_objectif_dominant(profile):
    vecteur = objectives.get_objective_vector(profile)
    dominant = max(objectives.OBJECTIVE_KEYS, key=lambda k: vecteur.get(k, 0))
    return vecteur, dominant


def _analyser_blessures(profile):
    """-> (risques, contraintes) à partir de `profile.blessures` (phase 5,
    inchangé) et du barème de sévérité déjà validé (filters.SEVERITE_RANG,
    phase 6, réutilisé en lecture seule)."""
    blessures = getattr(profile, "blessures", None) or {}
    risques = []
    contraintes = []

    for zone, severite in blessures.items():
        rang = filters.SEVERITE_RANG.get(severite)
        risques.append({"zone": zone, "severite": severite, "rang": rang})
        if rang is not None and rang >= RANG_CONTRAINTE_MINIMUM:
            contraintes.append(
                f"Blessure déclarée sur '{zone}' ({severite}) : exercices à risque sur cette zone "
                f"exclus ou pénalisés"
            )

    return risques, contraintes


def _analyser_amplitude(profile, contraintes):
    """Ajoute à `contraintes` (en place) les limitations d'amplitude déjà
    gérées par biomechanics.amplitude_hard_exclusion_reason (phase 6,
    inchangé) — ce module ne fait que les décrire en français, pas les
    recalculer."""
    amplitude_squat = getattr(profile, "amplitude_squat", None)
    if amplitude_squat == "Non, pas du tout":
        contraintes.append("Amplitude squat très limitée : squat profond libre exclu")
    elif amplitude_squat == "Avec difficulté":
        contraintes.append("Amplitude squat réduite : squat profond libre pénalisé (pas exclu)")

    amplitude_epaule = getattr(profile, "amplitude_epaule", None)
    if amplitude_epaule == "Non, pas du tout":
        contraintes.append("Amplitude épaule très limitée : développé militaire strict exclu")
    elif amplitude_epaule == "Avec difficulté":
        contraintes.append("Amplitude épaule réduite : développé militaire strict pénalisé (pas exclu)")


def _analyser_mobilite(profile, forces, faiblesses):
    mobilite = getattr(profile, "mobilite_generale", None)
    if mobilite is None:
        return
    if mobilite <= 2:
        faiblesses.append("Mobilité générale faible : exercices exigeants en stabilité pénalisés")
    elif mobilite >= 4:
        forces.append("Bonne mobilité générale : exercices exigeants en stabilité mieux tolérés")


def _analyser_experience_technique(profile, forces, faiblesses):
    exercices_maitrises = getattr(profile, "exercices_maitrises", None) or []
    aucun_maitrise = len(exercices_maitrises) == 0 or exercices_maitrises == ["Aucun de ces mouvements"]

    if aucun_maitrise:
        faiblesses.append("Aucun mouvement technique maîtrisé déclaré")
    else:
        forces.append(f"Mouvements déjà maîtrisés : {list(exercices_maitrises)}")

    tolerance = getattr(profile, "tolerance_technique", None)
    if tolerance is not None and tolerance >= 4 and not aucun_maitrise:
        forces.append("Tolérance technique élevée avec expérience réelle : prudence de complexité réduite")

    return aucun_maitrise


def _analyser_niveau(profile, forces, faiblesses):
    niveau = getattr(profile, "niveau_musculation", None)
    if niveau == "Débutant complet":
        faiblesses.append("Niveau débutant complet : exercices techniques/avancés fortement pénalisés")
    elif niveau == "Avancé":
        forces.append("Niveau avancé : pénalité de complexité réduite voire annulée sur mouvements maîtrisés")
    return niveau


def analyze_profile(snapshot):
    """analyze_profile(snapshot) -> {"niveau", "objectif_dominant",
    "contraintes", "forces", "faiblesses", "risques", "priorites_moteur"}.

    `snapshot` : un `ProfileSnapshot` (ou tout objet exposant les mêmes
    attributs, cf. tests) — jamais modifié, jamais requêté en base ici."""
    vecteur, objectif_dominant = _vecteur_et_objectif_dominant(snapshot)

    forces = []
    faiblesses = []
    risques, contraintes = _analyser_blessures(snapshot)
    _analyser_amplitude(snapshot, contraintes)
    _analyser_mobilite(snapshot, forces, faiblesses)
    aucun_maitrise = _analyser_experience_technique(snapshot, forces, faiblesses)
    niveau = _analyser_niveau(snapshot, forces, faiblesses)

    priorites_moteur = {
        "objectif_dominant": objectif_dominant,
        "vecteur_objectif": vecteur,
        "niveau": niveau,
        "aucun_mouvement_maitrise": aucun_maitrise,
        "nombre_contraintes": len(contraintes),
        "nombre_risques_declares": len([r for r in risques if r["rang"] is not None]),
    }

    return {
        "niveau": niveau,
        "objectif_dominant": objectif_dominant,
        "contraintes": contraintes,
        "forces": forces,
        "faiblesses": faiblesses,
        "risques": risques,
        "priorites_moteur": priorites_moteur,
    }
