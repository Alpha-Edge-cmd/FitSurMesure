# -*- coding: utf-8 -*-
"""
Outils de transition entre le stockage JSON historique des commandes
(logic/orders.py, data/orders.json) et la nouvelle architecture relationnelle
(User / ProfileSnapshot / Program, phase 1-2/16).

Ce module ne migre RIEN automatiquement. Il expose :
  - `preview_migration()`      : rapport en lecture seule (rien n'est écrit),
                                  commande par commande, migrable ou non.
  - `migrate_order_to_program(order_id, email_override=None)` : migre UNE
                                  commande précise, à la demande.
  - `unmigrate_order(order_id)`: annule une migration précédente pour UNE
                                  commande précise (réversibilité).

orders.json reste la source de vérité commerciale : rien ici ne le modifie,
ne le supprime, ni ne le remplace. logic/orders.py n'est pas non plus
modifié (aucune contrainte de cette phase ne le demandait) ; ce module se
contente de le LIRE.

Point d'analyse important avant d'écrire ce module : le stockage actuel
(orders.json) ne contient aucun email. La seule source d'email possible pour
une commande déjà payée par carte est Stripe lui-même (Stripe Checkout
demande l'email à l'acheteur, mais cet email n'est jamais rapatrié ni stocké
côté FitSurMesure aujourd'hui). Pour une commande gratuite (essai promo ou
accès propriétaire), il n'existe tout simplement aucun email nulle part —
ces commandes ne sont pas migrables automatiquement sans qu'un humain
fournisse l'email manuellement (`email_override`).
"""
from logic import orders, stripe_client
from logic.db import db
from logic.models import Program, ProfileSnapshot
from logic.profile_normalizer import normalize_questionnaire_data
from logic.user_identity import get_or_create_user, normalize_email

# Distinct de "achat_initial"/"regeneration"/"renouvellement" (architecture_v2_
# consolidation.md) : une commande migrée après coup n'est aucun des trois —
# elle n'est pas un achat fait via le nouveau flux, ni une régénération, ni un
# renouvellement d'abonnement. Ajout mineur et additif (une valeur de chaîne
# de plus), pas une remise en cause du schéma déjà validé.
ORIGINE_MIGRATION = "migration_legacy"


def _resolve_email(order):
    """Tente de retrouver l'email associé à une commande legacy, sans jamais
    en inventer un. Retourne None si aucune source fiable n'est disponible."""
    data = order.get("data") or {}

    # Compatibilité avant : si une future version du questionnaire ajoute un
    # champ email (hors périmètre de cette phase), ce module saura déjà s'en
    # servir sans modification.
    if data.get("email"):
        return normalize_email(data["email"])

    session_id = order.get("stripe_session_id")
    if session_id and stripe_client.is_configured():
        try:
            checkout_session = stripe_client.retrieve_session(session_id)
        except Exception:
            return None
        details = checkout_session.get("customer_details") or {}
        email = details.get("email") or checkout_session.get("customer_email")
        return normalize_email(email) if email else None

    return None


def preview_migration():
    """Rapport en lecture seule sur l'ensemble des commandes de orders.json :
    déjà migrée / migrable (email résolu) / bloquée (email introuvable).
    N'écrit rien nulle part — sert uniquement à décider, commande par
    commande, si/quand déclencher une vraie migration plus tard."""
    store = orders._load()  # lecture seule ; on réutilise le même fichier que orders.py

    report = []
    for order_id, order in store["orders"].items():
        already = Program.query.filter_by(order_id=order_id).first()
        if already:
            report.append({"order_id": order_id, "status": "deja_migre"})
            continue

        email = _resolve_email(order)
        report.append({
            "order_id": order_id,
            "status": "migrable" if email else "email_introuvable",
            "email_resolu": email,
            "paid": order.get("paid", False),
            "formule": order.get("formule"),
        })
    return report


def migrate_order_to_program(order_id, email_override=None):
    """Migre UNE commande précise vers User + ProfileSnapshot minimal +
    Program minimal (sans séances ni exercices : contrainte explicite de
    cette phase, "ne pas générer encore de nouveaux programmes"). Idempotent
    : rappeler cette fonction sur une commande déjà migrée ne crée pas de
    doublon, elle retourne simplement le Program existant."""
    order = orders.get_order(order_id)
    if not order:
        return {"status": "order_introuvable", "order_id": order_id}

    existing_program = Program.query.filter_by(order_id=order_id).first()
    if existing_program:
        return {
            "status": "deja_migre",
            "order_id": order_id,
            "user": existing_program.user,
            "program": existing_program,
        }

    email = normalize_email(email_override) if email_override else _resolve_email(order)
    if not email:
        return {
            "status": "email_introuvable",
            "order_id": order_id,
            "message": (
                "Aucun email retrouvable pour cette commande (ni dans les données "
                "stockées, ni via Stripe). Fournir email_override pour migrer quand "
                "même, si l'email est connu par un autre moyen."
            ),
        }

    data = order.get("data") or {}
    # Depuis la phase 4, la normalisation questionnaire -> ProfileSnapshot est
    # centralisée dans logic/profile_normalizer.py (utilisée aussi bien pour
    # les nouvelles commandes que pour cette migration legacy, pour ne pas
    # avoir deux façons différentes de construire un ProfileSnapshot).
    try:
        cleaned = normalize_questionnaire_data(data)
    except ValueError as e:
        return {
            "status": "donnees_profil_incompletes",
            "order_id": order_id,
            "message": str(e),
        }

    user, user_cree = get_or_create_user(email, prenom=data.get("prenom") or None)

    snapshot = ProfileSnapshot(user_id=user.id, **cleaned)
    db.session.add(snapshot)
    db.session.flush()

    program = Program(
        user_id=user.id,
        profile_snapshot_id=snapshot.id,
        formule=order.get("formule", ""),
        origine=ORIGINE_MIGRATION,
        order_id=order_id,
    )
    db.session.add(program)
    db.session.commit()

    return {
        "status": "migre",
        "order_id": order_id,
        "user": user,
        "user_cree": user_cree,
        "profile_snapshot": snapshot,
        "program": program,
    }


def unmigrate_order(order_id):
    """Annule la migration d'une commande précise : supprime le Program et le
    ProfileSnapshot créés pour elle. Ne touche JAMAIS au User (un même
    utilisateur peut être légitimement rattaché à d'autres commandes/achats ;
    le supprimer serait la seule action réellement irréversible de ce
    module, donc explicitement évitée). orders.json n'est pas affecté :
    l'historique commercial reste intact quoi qu'il arrive ici."""
    program = Program.query.filter_by(order_id=order_id, origine=ORIGINE_MIGRATION).first()
    if not program:
        return {"status": "rien_a_annuler", "order_id": order_id}

    snapshot = program.profile_snapshot
    db.session.delete(program)
    if snapshot is not None:
        db.session.delete(snapshot)
    db.session.commit()

    return {"status": "annule", "order_id": order_id}
