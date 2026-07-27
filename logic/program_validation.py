# -*- coding: utf-8 -*-
"""
Dernier contrôle de sécurité AVANT persistance d'un programme généré (phase
16/16) : `validate_generated_program` s'intercale entre `build_program()`
(moteur, phases 6-11, inchangé) et `program_repository.create_program_from_
result()` (persistance, phase 11, inchangé). Ne modifie jamais le résultat
qu'il inspecte — un dict en entrée reste identique en sortie, ce module ne
fait qu'observer et rapporter, exactement comme `logic/exercise_quality.py`
(phase 14) dont il réutilise la logique de repli sans la redéfinir.

Pourquoi ce contrôle est nécessaire précisément à cette phase : depuis le
branchement de `catalog_provider.get_recommendation_catalog()` dans
`program_service.py` (section 1 de cette phase), un programme peut, dans de
très rares cas de déploiement (catalogue V2 jamais importé du tout, avant le
tout premier `import_enriched_catalog()`), référencer un `exercise_id` issu
du repli legacy qui ne correspond encore à AUCUNE ligne réelle de la table
`exercises` — ce qui violerait la contrainte de clé étrangère `ProgramExercise.
exercise_id -> Exercise.exercise_id` (contrainte FK active, cf. logic/db.py)
au moment de la sauvegarde. Ce module détecte ce cas (et les autres,
ci-dessous) AVANT toute écriture, pour échouer proprement plutôt que de
laisser une IntegrityError brute remonter depuis `program_repository.py`.

Écart de signature documenté : la consigne décrit `validate_generated_
program(program_result)` à un seul argument, mais le contrôle "aucun
exercice incompatible avec les exclusions blessures" a besoin de connaître
le profil (blessures déclarées) pour avoir un sens — sans profil, il n'y a
rien à comparer. `profile` est donc ajouté en second paramètre OPTIONNEL
(`profile=None`) : un appel à un seul argument reste valide (ce contrôle
précis est alors simplement ignoré, avec un avertissement explicite plutôt
qu'une supposition silencieuse), ce qui respecte "ne pas changer les
signatures publiques existantes sauf nécessité" tout en rendant le contrôle
réellement utilisable par `program_service.py`, qui dispose du profil."""
from logic.exercise_catalog_service import get_exercise_by_id
from logic.recommendation import filters

# Une séance sans aucun exercice est le signe d'un problème en amont (budget
# de fatigue à zéro, catalogue vide pour tous les muscles ciblés, etc.) — pas
# une simple préférence de volume (cf. logic/recommendation/volume.py, qui
# gère déjà les cas de volume réduit légitimes en amont, avec avertissement).
# Ce seuil est un dernier filet de sécurité générique, pas une redéfinition
# des règles de volume déjà validées (phase 8).
MINIMUM_EXERCICES_PAR_SEANCE = 1


class ProgramValidationError(RuntimeError):
    """Levée par `program_service.generate_user_program` quand `validate_
    generated_program` détecte un programme invalide — jamais persisté."""


def _valider_un_exercice(exercise_id, profile, erreurs, cache):
    """Vérifie un seul `exercise_id` référencé par le programme. `cache`
    évite de requêter deux fois le même exercice au sein d'un même appel de
    `validate_generated_program` (un exercice peut apparaître dans plusieurs
    séances)."""
    if exercise_id in cache:
        exercise = cache[exercise_id]
    else:
        exercise = get_exercise_by_id(exercise_id)
        cache[exercise_id] = exercise

    if exercise is None:
        erreurs.append(f"exercice inexistant en base : '{exercise_id}'")
        return

    if not exercise.actif:
        erreurs.append(f"exercice non actif utilisé : '{exercise_id}'")

    if exercise.review_status == "rejected":
        erreurs.append(f"exercice rejeté (review_status='rejected') utilisé : '{exercise_id}'")

    if profile is not None:
        # Réutilise la RÈGLE DE SÉCURITÉ existante (passe 1 du moteur,
        # phase 6, inchangée) plutôt que d'en écrire une seconde ici : si le
        # filtrage dur aurait dû exclure cet exercice pour ce profil, sa
        # présence dans un programme déjà généré est une incohérence à
        # signaler, pas une nouvelle règle métier.
        raison = filters.exclusion_reason(profile, exercise)
        if raison:
            erreurs.append(
                f"exercice incompatible avec les exclusions blessures du profil : "
                f"'{exercise_id}' ({raison})"
            )


def validate_generated_program(program_result, profile=None):
    """validate_generated_program(program_result, profile=None) ->
    {"valid", "errors", "warnings"}.

    Contrôles (consigne section 2) :
      - aucun exercice `rejected` ;
      - aucun exercice non actif ;
      - aucun exercice inexistant (protège la contrainte FK avant écriture) ;
      - aucun exercice incompatible avec les exclusions blessures du profil
        (si `profile` fourni — sinon avertissement, jamais une supposition) ;
      - nombre minimal d'exercices respecté par séance.

    Ne modifie jamais `program_result`. `valid` est `True` si et seulement si
    `errors` est vide (les avertissements n'empêchent jamais la sauvegarde)."""
    erreurs = []
    avertissements = []
    cache = {}

    sessions = (program_result or {}).get("sessions") or []
    if not sessions:
        erreurs.append("aucune séance générée")

    if profile is None:
        avertissements.append(
            "profil non fourni : le contrôle 'exercice incompatible avec les "
            "exclusions blessures' n'a pas pu être effectué"
        )

    for session in sessions:
        nom_seance = session.get("name") or "(sans nom)"
        exercices = session.get("exercises") or []

        if len(exercices) < MINIMUM_EXERCICES_PAR_SEANCE:
            erreurs.append(
                f"séance '{nom_seance}' : {len(exercices)} exercice(s), "
                f"minimum requis {MINIMUM_EXERCICES_PAR_SEANCE}"
            )

        for exo_data in exercices:
            exercise_id = exo_data.get("exercise_id")
            if not exercise_id:
                erreurs.append(f"séance '{nom_seance}' : exercice sans exercise_id")
                continue
            _valider_un_exercice(exercise_id, profile, erreurs, cache)

    return {
        "valid": not erreurs,
        "errors": erreurs,
        "warnings": avertissements,
    }
