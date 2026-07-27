# -*- coding: utf-8 -*-
"""
Liaison email -> User (phase 3/16).

Constat fait avant d'écrire ce module (cf. explication donnée à l'utilisateur,
point "analyse") : le système actuel n'identifie JAMAIS un acheteur par email.
`logic/orders.py` ne stocke aucun champ email ; le questionnaire ne le demande
pas ; `logic/stripe_client.create_checkout_session` accepte un `customer_email`
optionnel mais aucune route de `app.py` ne le renseigne aujourd'hui — Stripe
Checkout demande donc lui-même l'email à l'acheteur au moment de payer, et cet
email n'existe que côté Stripe (accessible via l'API a posteriori), jamais
dans nos propres données.

Ce module ne dépend d'aucune route existante et n'est appelé par aucune
d'elles pour l'instant : c'est un outil, prêt à être branché plus tard,
sans effet sur le flux de paiement actuel (contrainte explicite de cette
phase : "Ne pas modifier le paiement Stripe").
"""
from logic.db import db
from logic.models import User


def normalize_email(email):
    """Normalisation minimale mais suffisante pour éviter les doublons
    évidents (casse, espaces superflus). Ne fait pas de validation de
    format ici (une adresse mal formée sera de toute façon rejetée plus tôt,
    par Stripe ou par un futur formulaire)."""
    return (email or "").strip().lower()


def get_user_by_email(email):
    """Lecture seule, ne crée rien."""
    email_norm = normalize_email(email)
    if not email_norm:
        return None
    return User.query.filter_by(email=email_norm).first()


def get_or_create_user(email, prenom=None):
    """Retrouve un User existant par email, ou en crée un nouveau. Ne crée
    JAMAIS de doublon pour un même email (email normalisé + colonne unique
    en base, qui fait office de garde-fou de dernier recours si deux requêtes
    concurrentes tentaient de créer le même email en même temps).

    Règle de conservation du prénom : si l'utilisateur existe déjà sans
    prénom enregistré et qu'un prénom est fourni maintenant, on le complète
    (sans jamais écraser un prénom déjà renseigné par une valeur différente
    — on ne veut pas qu'une commande ultérieure avec un prénom mal saisi
    corrompe la donnée déjà correcte).

    Retourne (user, created) où `created` est True si l'utilisateur vient
    d'être créé, False s'il existait déjà.
    """
    email_norm = normalize_email(email)
    if not email_norm:
        raise ValueError("Impossible de créer/retrouver un utilisateur sans email.")

    user = User.query.filter_by(email=email_norm).first()
    if user:
        if prenom and not user.prenom:
            user.prenom = prenom
            db.session.commit()
        return user, False

    user = User(email=email_norm, prenom=prenom or None)
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        # Filet de sécurité en cas de course entre deux créations concurrentes
        # sur le même email (contrainte unique en base) : on retombe sur la
        # ligne créée par l'autre requête plutôt que de planter.
        db.session.rollback()
        user = User.query.filter_by(email=email_norm).first()
        if not user:
            raise
        return user, False

    return user, True
