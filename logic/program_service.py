# -*- coding: utf-8 -*-
"""
Couche applicative entre les routes Flask et le moteur de recommandation
(phase 12/16) : `app.py` ne doit jamais appeler directement
`logic/user_identity.py`, `logic/profile_normalizer.py`,
`logic/recommendation/program_builder.py` ou `logic/program_repository.py` —
ce module orchestre ces briques (toutes construites dans les phases 3, 4,
11) et n'en redéfinit aucune règle.

Ne modifie ni Stripe, ni `logic/orders.py`, ni `logic/promo_codes.py`, ni
aucune règle métier de scoring/recommandation.

Phase 16/16 : le catalogue n'est plus lu directement (`Exercise.query.
filter_by(actif=True)`) mais via `recommendation.catalog_provider.
get_recommendation_catalog()` — catalogue V2 APPROUVÉ en priorité, repli
automatique sur le catalogue legacy si aucun exercice n'est encore approuvé
(cf. catalog_provider.py, phase 15). Un dernier contrôle de sécurité
(`program_validation.validate_generated_program`) s'intercale entre la
génération et la sauvegarde : un programme invalide n'est JAMAIS persisté,
mais cette étape reste toujours indépendante du paiement (cf. docstring de
`generate_user_program` et de `app._essayer_generer_programme_v2`, phase 12,
qui absorbe déjà toute exception venant d'ici sans jamais bloquer Stripe/
orders.py/promo_codes.py, tous inchangés)."""
from logic.models import Exercise, Program, ProfileSnapshot
from logic.profile_normalizer import create_profile_snapshot
from logic.program_repository import create_program_from_result, get_latest_program
from logic.program_validation import ProgramValidationError, validate_generated_program
from logic.recommendation import history
from logic.recommendation.catalog_provider import get_recommendation_catalog
from logic.recommendation.program_builder import build_program
from logic.user_identity import get_or_create_user, get_user_by_email


def generate_user_program(user_email, questionnaire_data, options=None):
    """Point d'entrée principal de cette phase : questionnaire brut + email
    -> Program persisté. Enchaîne exactement les étapes demandées :

    1. récupère/crée le User (`user_identity.get_or_create_user`).
    2. normalise + persiste le ProfileSnapshot en une seule étape
       (`profile_normalizer.create_profile_snapshot`, qui normalise déjà en
       interne — pas de double normalisation).
    3. charge le catalogue via `catalog_provider.get_recommendation_catalog()`
       (phase 16/16) : exercices V2 approuvés (`actif=True` ET
       `review_status="approved"`) si disponibles, sinon repli automatique
       sur le catalogue legacy reconstruit à la volée — jamais les exercices
       désactivés ni rejetés, jamais de suppression physique (cf. phases 2,
       14, 15, toutes inchangées).
    4. appelle `build_program()` (phase 11, moteur complet).
    5. valide le résultat AVANT toute écriture (`program_validation.
       validate_generated_program`, phase 16/16) : lève `ProgramValidationError`
       si invalide, sans jamais rien sauvegarder — l'appelant (route Flask ou
       hook post-paiement `app._essayer_generer_programme_v2`, qui absorbe déjà
       toute exception) décide s'il doit bloquer ou simplement journaliser.
    6. sauvegarde via `create_program_from_result()` (phase 11, déduplique
       déjà une régénération strictement identique).

    Retourne le `Program` créé (ou réutilisé si régénération identique).
    Peut lever `ValueError` si `user_email` est vide (remontée telle quelle
    par `user_identity.get_or_create_user`) ou si le questionnaire n'a pas
    les champs cœur minimum (remontée par `profile_normalizer`, inchangé), ou
    `ProgramValidationError` si le programme généré échoue la validation de
    sécurité — dans tous les cas, c'est à l'appelant de décider de la suite ;
    le paiement (Stripe/orders.py/promo_codes.py) reste toujours indépendant
    de cette validation."""
    user, _cree = get_or_create_user(user_email, prenom=(questionnaire_data or {}).get("prenom") or None)

    profile_snapshot = create_profile_snapshot(user.id, questionnaire_data or {})

    catalogue = get_recommendation_catalog()

    result = build_program(profile_snapshot, catalogue, options=options)

    rapport_validation = validate_generated_program(result, profile=profile_snapshot)
    if not rapport_validation["valid"]:
        raise ProgramValidationError(
            f"programme généré invalide pour user_id={user.id} : {rapport_validation['errors']}"
        )

    return create_program_from_result(user.id, profile_snapshot.id, result)


def get_user_current_program(user_email):
    """Retourne le dernier `Program` sauvegardé pour cet email, ou None si
    l'utilisateur n'existe pas encore ou n'a aucun programme. Lecture seule
    (ne crée jamais de User) — cohérent avec `get_user_by_email`."""
    user = get_user_by_email(user_email)
    if user is None:
        return None
    return get_latest_program(user.id)


def serialize_program(program):
    """Sérialise un `Program` SQLAlchemy dans le format JSON exact attendu
    par la route `GET /my-program` (section 3 de la consigne). Ne fait
    aucune supposition sur l'ordre déjà garanti par les relations `Program.
    sessions`/`ProgramSession.exercises` (déjà triées par `order_by` dans
    `logic/models.py`, phases 1/11) : pas de re-tri ici.

    `warnings` n'est pas encore persisté sur `Program` (limite documentée en
    fin de phase 12) : toujours [] pour l'instant, jamais une clé absente."""
    if program is None:
        return None

    sessions = []
    for session in program.sessions:
        exercises = []
        for pe in session.exercises:
            exercises.append({
                "name": getattr(pe.exercise, "name", None) if pe.exercise else None,
                "series": pe.series,
                "repetitions": pe.reps,
                "rest_time": pe.rest_time_seconds,
            })
        sessions.append({"name": session.nom_seance, "exercises": exercises})

    objective = None
    if program.profile_snapshot is not None:
        objective = program.profile_snapshot.objectif_principal

    return {
        "program_id": program.id,
        "objective": objective,
        "created_at": program.created_at.isoformat() if program.created_at else None,
        "sessions": sessions,
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# Phase 22/24 : authentification utilisateur / espace personnel.
#
# `app.py` ne doit toujours jamais appeler directement `logic/user_identity.py`
# (règle inchangée depuis la phase 12, cf. docstring en tête de fichier) :
# `get_or_create_user_for_email` est le point de passage unique pour le hook
# post-paiement (`app.payment_success`), qui a besoin de résoudre un User à
# partir de l'email retrouvé sur la commande pour lui émettre un jeton
# d'authentification (`logic/auth.py`, phase 22/24).
# ---------------------------------------------------------------------------

def get_or_create_user_for_email(email, prenom=None):
    """Délègue tel quel à `user_identity.get_or_create_user` (phase 3,
    inchangé) — ne redéfinit aucune règle de résolution/dédoublonnage
    d'utilisateur. Peut lever `ValueError` si `email` est vide, comme la
    fonction déléguée."""
    user, _cree = get_or_create_user(email, prenom=prenom)
    return user


def get_user_dashboard(user):
    """get_user_dashboard(user) -> {"programme_actuel", "historique_
    programmes", "feedback_exercices", "evolution_profil"}.

    Espace personnel (phase 22/24, consigne : "programme actuel / historique
    programmes / feedback exercices / évolution profil"). LECTURE SEULE
    stricte : ne fait que relire et assembler ce que les phases précédentes
    ont déjà persisté (`program_repository.py` phase 11, `history.py` phase
    10, `ProfileSnapshot` phase 1/4) — aucune nouvelle règle métier, aucune
    régénération de programme ici."""
    programme_actuel = serialize_program(get_latest_program(user.id))

    programmes = (
        Program.query.filter_by(user_id=user.id).order_by(Program.created_at.desc()).all()
    )
    historique_programmes = [
        {
            "program_id": p.id,
            "formule": p.formule,
            "split": p.split,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in programmes
    ]

    feedbacks = history.get_exercise_feedback(user.id)
    feedback_exercices = []
    cache_exercices = {}
    for fb in feedbacks:
        exercise_id = fb["exercise_id"]
        if exercise_id not in cache_exercices:
            cache_exercices[exercise_id] = Exercise.query.get(exercise_id)
        exercise = cache_exercices[exercise_id]
        feedback_exercices.append({
            "exercise_id": exercise_id,
            "exercise_name": getattr(exercise, "name", None) if exercise else None,
            "feedback_type": fb["feedback_type"],
            "comment": fb["comment"],
            "created_at": fb["created_at"].isoformat() if fb["created_at"] else None,
        })

    snapshots = (
        ProfileSnapshot.query.filter_by(user_id=user.id)
        .order_by(ProfileSnapshot.created_at.asc())
        .all()
    )
    evolution_profil = [
        {
            "snapshot_id": s.id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "poids": s.poids,
            "niveau_musculation": s.niveau_musculation,
            "objectif_principal": s.objectif_principal,
        }
        for s in snapshots
    ]

    return {
        "programme_actuel": programme_actuel,
        "historique_programmes": historique_programmes,
        "feedback_exercices": feedback_exercices,
        "evolution_profil": evolution_profil,
    }
