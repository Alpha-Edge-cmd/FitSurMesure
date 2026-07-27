# -*- coding: utf-8 -*-
"""
Personnalisation avancée du programme généré (phase 20/24).

Ce module ne redéfinit AUCUNE règle déjà validée de scoring/sélection/volume/
ordre/repos/intensité (`logic/recommendation/scoring.py`, `selector.py`,
`workout_generator.py`, `volume.py`, `exercise_order.py`, `prescription.py`,
`intensity.py`, `rest_time.py`, `history.py`, `feedback.py`) : il se contente
de lire ce que ces modules ont déjà calculé, et d'AJOUTER une couche de
personnalisation additive sur deux axes jusqu'ici inexploités par le moteur
(confirmé par recherche exhaustive avant cette phase : zéro référence dans
`logic/recommendation/`) :

  - l'âge (dérivé de `ProfileSnapshot.variables_json["date_naissance"]`,
    aucune colonne dédiée n'existe) ;
  - le matériel préféré (`ProfileSnapshot.preference_materiel`) ;
  - la disponibilité réelle déclarée (`ProfileSnapshot.disponibilite_reelle`).

Les autres axes demandés par la consigne (niveau, objectif, blessures,
historique/feedback) sont DÉJÀ pleinement personnalisés par le pipeline
existant (scoring.py/selector.py pour niveau+objectif+blessures+historique/
feedback, cf. phases 6 à 10 ; `logic/profile_analysis.py`, phase 19, pour un
résumé lisible niveau/objectif/contraintes/forces/faiblesses/risques) : ce
module les RÉUTILISE (jamais ne les recalcule) pour construire le contexte de
personnalisation et les explications demandées, plutôt que d'inventer une
seconde logique parallèle et incohérente avec l'existant.

Intégré dans `logic/recommendation/program_builder.py` (`build_program`),
uniquement de façon ADDITIVE :
  - fréquence : `adjust_frequency_for_availability` peut réduire (jamais
    augmenter) la fréquence effective si la disponibilité réelle déclarée
    est incompatible, avec un avertissement explicite (jamais une
    substitution silencieuse) ;
  - ordre : `reorder_session_by_equipment_preference` ne fait que
    départager, À L'INTÉRIEUR d'un même palier `exercise_order` déjà décidé
    (principal/secondaire/isolation/finisseur, phase 8, jamais reclassé
    ici), les exercices dont l'équipement correspond au matériel préféré —
    ne franchit jamais une frontière de palier ;
  - repos/intensité : `adjust_rest_for_age`/`adjust_intensity_for_age`
    n'ajustent (légèrement, jamais radicalement) le résultat déjà calculé
    par `rest_time.py`/`intensity.py` qu'à partir d'un seuil d'âge prudent,
    documenté et conservateur ;
  - notes coaching : `build_coaching_note` enrichit (concatène, ne remplace
    jamais) le texte déjà produit par `prescription._note_automatique` ;
  - exercices/volume : aucune resélection ni recalcul de volume ici (déjà
    personnalisés par selector.py/volume.py/scoring.py) — seulement expliqués
    via `generate_program_explanation`.

Ne touche jamais : `logic/program_repository.py`, `logic/pdf_program_adapter.py`,
`logic/pdf_generator.py`, `logic/orders.py`, `logic/promo_codes.py`, ni aucune
route de paiement Stripe. N'ajoute que des clés supplémentaires à des dicts
déjà consommés par clé explicite (jamais de renommage/suppression d'une clé
existante), cf. vérification faite en amont de cette phase sur
`program_repository.create_program_from_result` et
`program_validation.validate_generated_program` (les deux ne lisent que des
clés précises, une clé additive ne peut donc jamais les casser)."""
import datetime

from logic.recommendation import exercise_order
from logic.recommendation.intensity import NIVEAUX_INTENSITE, _reduire

# --- Axe "âge" (nouveau — aucune colonne dédiée, dérivé de variables_json) --

# Seuil documenté, conservateur : au-delà, on privilégie prudemment un peu
# plus de récupération et une intensité légèrement réduite plutôt que de
# prétendre à une formule médicale validée (aucun barème chiffré fourni par
# la consigne pour cet axe, contrairement aux facteurs de scoring.py).
AGE_SEUIL_PRUDENCE = 50
BONUS_REPOS_AGE_SECONDES = 15


def compute_age(profile_snapshot, aujourdhui=None):
    """compute_age(profile_snapshot, aujourdhui=None) -> int ou None.

    Dérive l'âge à partir de `variables_json["date_naissance"]` (format
    "AAAA-MM-JJ", cf. `static/script.js`/`app.py`) : aucune colonne dédiée
    n'existe sur `ProfileSnapshot` (vérifié en amont de cette phase). Ne
    lève jamais d'exception sur une valeur absente/mal formée (None dans ce
    cas, jamais une supposition), même garantie que le reste du moteur."""
    variables = getattr(profile_snapshot, "variables_json", None) or {}
    date_naissance = variables.get("date_naissance")
    if not date_naissance:
        return None
    try:
        annee, mois, jour = [int(x) for x in str(date_naissance).split("-")]
        naissance = datetime.date(annee, mois, jour)
    except (ValueError, TypeError):
        return None

    reference = aujourdhui or datetime.date.today()
    age = reference.year - naissance.year
    if (reference.month, reference.day) < (naissance.month, naissance.day):
        age -= 1
    return age if 0 <= age <= 120 else None


def adjust_rest_for_age(rest_time_secondes, age):
    """Allonge (jamais ne réduit) légèrement le repos déjà calculé par
    `rest_time.calculate_rest_time` (phase 9, inchangé) au-delà du seuil de
    prudence. `None` en entrée (repos non résolu, cf. prescription.py cas
    exercice introuvable) reste `None` en sortie — jamais de supposition."""
    if rest_time_secondes is None or age is None or age < AGE_SEUIL_PRUDENCE:
        return rest_time_secondes
    return rest_time_secondes + BONUS_REPOS_AGE_SECONDES


def adjust_intensity_for_age(intensite, age):
    """Réduit d'UN palier (jamais plus) l'intensité qualitative déjà
    calculée par `intensity.calculate_intensity` (phase 9, inchangé) au-delà
    du seuil de prudence — réutilise `intensity._reduire`, ne redéfinit pas
    l'échelle `NIVEAUX_INTENSITE`. `None` reste `None`."""
    if intensite is None or age is None or age < AGE_SEUIL_PRUDENCE:
        return intensite
    if intensite not in NIVEAUX_INTENSITE:
        return intensite
    return _reduire(intensite, 1)


# --- Axe "matériel" (nouveau — preference_materiel jusqu'ici inexploité) ---

# Correspondance texte questionnaire (`profile_normalizer.MATERIELS_PREFERES`)
# -> mots-clés `Exercise.equipment` du catalogue. Toute valeur absente de
# cette table (dont "Pas de préférence", None, ou une valeur libre non
# reconnue comme "Élastiques uniquement") -> aucune préférence, aucun
# réordonnancement (jamais de supposition sur un mot-clé d'équipement non
# documenté ici).
EQUIPEMENT_PAR_PREFERENCE = {
    "Barres libres": {"barre"},
    "Haltères": {"haltere"},
    "Machines guidées": {"machine"},
}


def equipements_preferes(profile_snapshot):
    """-> set() de mots-clés d'équipement correspondant à
    `preference_materiel`, ou set() vide si aucune préférence reconnue
    (comportement neutre par défaut, jamais d'exclusion)."""
    preference = getattr(profile_snapshot, "preference_materiel", None)
    return set(EQUIPEMENT_PAR_PREFERENCE.get(preference, set()))


def reorder_session_by_equipment_preference(items_avec_exercice, preferences):
    """reorder_session_by_equipment_preference(items, preferences) -> liste.

    `items_avec_exercice` : liste de dicts contenant au moins la clé
    "exercise" (objet `Exercise`) — même forme que les items internes de
    `workout_generator`/`selector`. Ne fait JAMAIS d'exclusion (aucun
    exercice retiré) et ne franchit JAMAIS une frontière de palier
    `exercise_order.classify_exercise` déjà décidée (phase 8) : trie
    seulement, à l'intérieur d'un même palier, en priorisant les exercices
    dont l'équipement correspond au matériel préféré. Tri stable : l'ordre
    relatif préexistant est conservé pour tout ce qui ne diffère pas selon
    ce critère (donc aucun effet si `preferences` est vide)."""
    if not preferences:
        return items_avec_exercice

    def cle(item):
        tier_rang = exercise_order.TIER_ORDER[exercise_order.classify_exercise(item["exercise"])]
        equipement = set(getattr(item["exercise"], "equipment", None) or [])
        materiel_rang = 0 if equipement & preferences else 1
        return (tier_rang, materiel_rang)

    return sorted(items_avec_exercice, key=cle)


# --- Axe "disponibilité" (nouveau — disponibilite_reelle jusqu'ici inexploité) --

# `disponibilite_reelle` est un champ texte LIBRE côté normalisation
# (`profile_normalizer._clean_str`, aucune liste fermée contrairement à
# `preference_materiel`) : seules les 4 valeurs du questionnaire actuel
# (`static/script.js`) sont reconnues ici. Toute autre valeur (absente,
# ou texte libre non standard) -> aucun ajustement, jamais de supposition.
FREQUENCE_MAX_PAR_DISPONIBILITE = {
    "Moins de 2h": 2,
    "2 à 4h": 3,
    "4 à 6h": 4,
    # "Plus de 6h" : aucun plafond particulier -> absent de cette table.
}

MESSAGE_FREQUENCE_REDUITE = (
    "Fréquence ramenée à {plafond}x/semaine (au lieu de {demandee}x demandé) : "
    "ta disponibilité réelle déclarée ('{disponibilite}') ne permet pas de tenir "
    "un tel rythme dans la durée sans compromettre la récupération."
)


def adjust_frequency_for_availability(profile_snapshot, frequence_demandee):
    """adjust_frequency_for_availability(profile_snapshot, frequence_demandee)
    -> (frequence_effective, avertissement_ou_None).

    Ne réduit la fréquence QUE si `disponibilite_reelle` correspond à une des
    4 valeurs reconnues du questionnaire ET que la fréquence demandée
    dépasse le plafond associé ; sinon retourne la fréquence demandée
    inchangée, sans avertissement (comportement neutre par défaut — aucune
    supposition sur un texte libre non standard ou une disponibilité
    confortable)."""
    disponibilite = getattr(profile_snapshot, "disponibilite_reelle", None)
    plafond = FREQUENCE_MAX_PAR_DISPONIBILITE.get(disponibilite)

    if plafond is None or frequence_demandee <= plafond:
        return frequence_demandee, None

    avertissement = MESSAGE_FREQUENCE_REDUITE.format(
        plafond=plafond, demandee=frequence_demandee, disponibilite=disponibilite
    )
    return plafond, avertissement


# --- Contexte de personnalisation : regroupe les 7 axes de la consigne ----

def compute_personalization_context(profile_snapshot):
    """compute_personalization_context(profile_snapshot) -> dict rassemblant
    en UNE lecture les 7 axes demandés par la consigne (âge/niveau/objectif/
    disponibilité/matériel/blessures/historique) :

      - "age" : calculé ici (nouveau, cf. `compute_age`) ;
      - "niveau"/"objectif_dominant"/"contraintes"/"forces"/"faiblesses"/
        "risques" : réutilisés tels quels depuis `profile_analysis.analyze_
        profile` (phase 19, inchangé — couvre déjà niveau/objectif/blessures) ;
      - "materiel_prefere"/"disponibilite_reelle" : colonnes `ProfileSnapshot`
        déjà validées (phase 4), lues ici pour la première fois par le
        moteur (cf. recherche préalable de cette phase) ;
      - "historique_feedback_deja_integre" : True, pour signaler explicitement
        que cet axe est déjà pleinement pris en compte par `selector.py` +
        `history.py`/`feedback.py` (phase 10) — pas recalculé ici, pour ne
        jamais dupliquer une règle métier déjà tranchée."""
    # Import différé : évite tout cycle d'import, même précaution que
    # `logic/recommendation/scoring.py` (phase 19/24) vis-à-vis de
    # `profile_analysis.py`.
    from logic.profile_analysis import analyze_profile

    analyse = analyze_profile(profile_snapshot)

    return {
        "age": compute_age(profile_snapshot),
        "niveau": analyse["niveau"],
        "objectif_dominant": analyse["objectif_dominant"],
        "contraintes": analyse["contraintes"],
        "forces": analyse["forces"],
        "faiblesses": analyse["faiblesses"],
        "risques": analyse["risques"],
        "materiel_prefere": getattr(profile_snapshot, "preference_materiel", None),
        "disponibilite_reelle": getattr(profile_snapshot, "disponibilite_reelle", None),
        "historique_feedback_deja_integre": True,
    }


# --- Notes coaching enrichies ----------------------------------------------

def build_coaching_note(note_base, exercise, contexte, materiel_correspond):
    """build_coaching_note(note_base, exercise, contexte, materiel_correspond)
    -> str.

    Enrichit (concatène) la note déjà produite par
    `prescription._note_automatique` (phase 9, jamais remplacée) avec les
    axes nouvellement exploités par cette phase (âge, matériel), pour rendre
    explicite au coaché POURQUOI ce choix, sans jamais redéfinir la note de
    base elle-même."""
    ajouts = []

    if contexte.get("age") is not None and contexte["age"] >= AGE_SEUIL_PRUDENCE:
        ajouts.append(
            f"Repos légèrement allongé et intensité prudente compte tenu de l'âge déclaré "
            f"({contexte['age']} ans)."
        )

    if materiel_correspond and contexte.get("materiel_prefere"):
        ajouts.append(f"Choisi en priorité : matériel préféré ('{contexte['materiel_prefere']}').")

    if not ajouts:
        return note_base
    return (note_base or "").rstrip() + " " + " ".join(ajouts)


# --- Explication du programme (section demandée : generate_program_explanation) --

_LABEL_TRAIT_MORPHOLOGIE = {
    "bras_longs": "ta morphologie (bras plutôt longs)", "bras_courts": "ta morphologie (bras plutôt courts)",
    "jambes_longues": "ta morphologie (jambes plutôt longues)", "jambes_courtes": "ta morphologie (jambes plutôt courtes)",
    "buste_long": "ta morphologie (buste plutôt long)", "buste_court": "ta morphologie (buste plutôt court)",
    "epaules_larges": "ta morphologie (épaules plutôt larges)", "epaules_etroites": "ta morphologie (épaules plutôt étroites)",
    "mobilite_faible": "ta mobilité réduite",
}

_LABEL_OBJECTIF = {
    "force": "ton objectif force", "hypertrophie": "ton objectif hypertrophie",
    "endurance_musculaire": "ton objectif endurance musculaire", "perte_de_gras": "ton objectif perte de gras",
    "explosivite": "ton objectif explosivité",
}


def _complement_morphologie_objectif(profile_snapshot, exercise, contexte):
    """Prompt final (hors 24 phases) : construit la phrase "Choisi car adapté
    à [...]" en croisant les traits morphologiques RÉELLEMENT activés pour ce
    profil (même fonction que le moteur de scoring, `biomechanics.
    _activated_morphologie_keys` — jamais une règle dupliquée) avec les clés
    RÉELLEMENT présentes sur `exercise.morphologie_adaptee` (donc seulement
    si get_recommendation_catalog() catalogue). Ajoute l'objectif dominant si
    l'exercice y est particulièrement adapté (score >= 6/10). Retourne une
    chaîne vide si rien de notable (jamais de texte creux/inventé)."""
    if exercise is None:
        return ""
    # Import différé : évite tout cycle (même précaution que scoring.py vis-à-vis
    # de profile_analysis.py, déjà établie phase 19/24).
    from logic.recommendation.biomechanics import _activated_morphologie_keys

    traits_actifs = set(_activated_morphologie_keys(profile_snapshot))
    morpho_exercice = getattr(exercise, "morphologie_adaptee", None) or {}
    traits_correspondants = [t for t in traits_actifs if morpho_exercice.get(t, 0) > 0]

    objectifs_adaptes = getattr(exercise, "objectifs_adaptes", None) or {}
    objectif_dominant = contexte.get("objectif_dominant") if contexte else None
    objectif_notable = (
        objectif_dominant if objectif_dominant and objectifs_adaptes.get(objectif_dominant, 0) >= 6 else None
    )

    if not traits_correspondants and not objectif_notable:
        return ""

    elements = [_LABEL_TRAIT_MORPHOLOGIE[t] for t in traits_correspondants if t in _LABEL_TRAIT_MORPHOLOGIE]
    if objectif_notable:
        elements.append(_LABEL_OBJECTIF.get(objectif_notable, f"ton objectif {objectif_notable}"))

    if not elements:
        return ""
    if len(elements) == 1:
        texte_elements = elements[0]
    else:
        texte_elements = ", ".join(elements[:-1]) + " et " + elements[-1]
    return f"Choisi car adapté à {texte_elements}."


def generate_program_explanation(profile_snapshot, seances_detail, contexte=None):
    """generate_program_explanation(profile_snapshot, seances_detail, contexte=None)
    -> {"resume_profil", "seances": [{"nom", "exercices": [{"exercise_id",
    "pourquoi_exercice", "pourquoi_volume", "pourquoi_intensite"}]}]}.

    `seances_detail` : liste de dicts (un par séance, MÊME ORDRE que
    `result["sessions"]`) de la forme
    {"nom": str, "exercices": [{"exercise_id", "raison_selection", "tier",
    "sets", "intensity"}, ...]} — ces informations sont déjà calculées par
    `workout_generator.generate_workout` (raison_selection) et
    `prescription.generate_prescription`/`_sets_de_base` (tier/sets) plus
    haut dans `build_program` ; cette fonction ne fait QUE les reformuler en
    phrases lisibles, jamais ne les recalcule.

    Ne lève jamais d'exception sur une entrée incomplète (texte neutre à la
    place, même garantie que le reste du moteur)."""
    contexte = contexte or compute_personalization_context(profile_snapshot)

    resume_profil = (
        f"Niveau '{contexte.get('niveau')}', objectif dominant '{contexte.get('objectif_dominant')}'"
        + (f", âge déclaré {contexte['age']} ans" if contexte.get("age") is not None else "")
        + (f", matériel préféré '{contexte['materiel_prefere']}'" if contexte.get("materiel_prefere") else "")
        + "."
    )

    seances_explication = []
    for seance in seances_detail or []:
        exercices_explication = []
        for exo in seance.get("exercices", []):
            tier = exo.get("tier")
            sets = exo.get("sets")
            intensite = exo.get("intensity")

            pourquoi_exercice = exo.get("raison_selection") or (
                "Sélectionné par le moteur de recommandation selon ton profil."
            )
            # Prompt final (hors 24 phases) : "le programme final doit être
            # capable de répondre 'pourquoi cet exercice a été choisi ?' avec
            # une justification" citant explicitement morphologie/mobilité/
            # objectif. `exo.get("exercise")` est l'objet Exercise déjà résolu
            # par program_builder.py (ajout additif, aucune règle recalculée
            # ici) — absent si non fourni (rétrocompatible, aucune exception).
            complement_morpho_objectif = _complement_morphologie_objectif(
                profile_snapshot, exo.get("exercise"), contexte
            )
            if complement_morpho_objectif:
                pourquoi_exercice = f"{pourquoi_exercice} {complement_morpho_objectif}"

            pourquoi_volume = (
                f"{sets} série(s) : palier '{tier}' pour ce mouvement, niveau '{contexte.get('niveau')}', "
                f"objectif dominant '{contexte.get('objectif_dominant')}'."
                if sets is not None
                else "Volume déterminé par ton niveau et l'objectif dominant du programme."
            )

            pourquoi_intensite = (
                f"Intensité '{intensite}' : basée sur l'objectif dominant '{contexte.get('objectif_dominant')}', "
                f"plafonnée selon le niveau '{contexte.get('niveau')}'"
                + (f", réduite compte tenu de l'âge déclaré ({contexte['age']} ans)"
                   if contexte.get("age") is not None and contexte["age"] >= AGE_SEUIL_PRUDENCE else "")
                + "."
                if intensite is not None
                else "Intensité neutre (donnée insuffisante pour cet exercice)."
            )

            exercices_explication.append({
                "exercise_id": exo.get("exercise_id"),
                "pourquoi_exercice": pourquoi_exercice,
                "pourquoi_volume": pourquoi_volume,
                "pourquoi_intensite": pourquoi_intensite,
            })

        seances_explication.append({"nom": seance.get("nom"), "exercices": exercices_explication})

    return {"resume_profil": resume_profil, "seances": seances_explication}
