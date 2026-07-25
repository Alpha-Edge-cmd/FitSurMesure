# -*- coding: utf-8 -*-
"""
Intégration Stripe : création de sessions Stripe Checkout (paiement unique pour
les formules Cardio / Musculation / Complet, abonnement récurrent annuel pour la
formule Abonnement) et vérification des webhooks.

Configuration requise (variables d'environnement) :
  - STRIPE_SECRET_KEY   : clé secrète Stripe (test : sk_test_..., prod : sk_live_...)
  - STRIPE_WEBHOOK_SECRET : signature du endpoint webhook (whsec_...), fournie par
    Stripe une fois le webhook configuré dans le dashboard (ou via `stripe listen`
    en local pour tester).

Tant que STRIPE_SECRET_KEY n'est pas configurée, le site fonctionne toujours (le
questionnaire et l'aperçu restent utilisables) mais la création d'une session de
paiement échoue proprement avec StripeNotConfiguredError, affichée à l'utilisateur
comme "le paiement n'est pas encore configuré".
"""
import os

import stripe

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

stripe.api_key = STRIPE_SECRET_KEY

# Prix en centimes, alignés sur PRICES dans app.py (affichage).
PRICES_CENTS = {
    "musculation": 1499,
    "cardio": 1299,
    "les_deux": 2299,
    "abonnement": 5900,
}

PRODUCT_NAMES = {
    "musculation": "FitSurMesure — Programme Musculation",
    "cardio": "FitSurMesure — Programme Cardio",
    "les_deux": "FitSurMesure — Programme Complet (Musculation + Cardio)",
    "abonnement": "FitSurMesure — Abonnement annuel",
}


class StripeNotConfiguredError(Exception):
    """Levée quand on tente de créer un paiement sans clé Stripe configurée."""
    pass


def is_configured():
    return bool(STRIPE_SECRET_KEY)


def create_checkout_session(order_id, formule, success_url, cancel_url, customer_email=None, discount_pct=0.0):
    """Crée une session Stripe Checkout pour la formule donnée. `success_url` doit
    contenir le littéral '{CHECKOUT_SESSION_ID}', remplacé par Stripe à la volée.
    Les prix sont définis à la volée (price_data) : pas besoin de créer les
    produits/prix à l'avance dans le dashboard Stripe. `discount_pct` applique une
    réduction de parrainage directement sur le prix envoyé à Stripe (ex: 10 pour
    -10%)."""
    if not is_configured():
        raise StripeNotConfiguredError(
            "Le paiement en ligne n'est pas encore configuré (clé Stripe manquante)."
        )

    base_amount = PRICES_CENTS.get(formule)
    if base_amount is None:
        raise ValueError(f"Formule inconnue : {formule}")

    unit_amount = round(base_amount * (1 - (discount_pct or 0) / 100))
    unit_amount = max(unit_amount, 0)

    mode = "subscription" if formule == "abonnement" else "payment"
    product_name = PRODUCT_NAMES.get(formule, "FitSurMesure")
    if discount_pct:
        product_name += f" (code promo -{discount_pct:g}%)"
    price_data = {
        "currency": "eur",
        "unit_amount": unit_amount,
        "product_data": {"name": product_name},
    }
    if mode == "subscription":
        price_data["recurring"] = {"interval": "year"}

    session_kwargs = dict(
        mode=mode,
        line_items=[{"price_data": price_data, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=order_id,
        metadata={"order_id": order_id, "formule": formule},
    )
    if customer_email:
        session_kwargs["customer_email"] = customer_email

    return stripe.checkout.Session.create(**session_kwargs)


def retrieve_session(session_id):
    return stripe.checkout.Session.retrieve(session_id)


def construct_webhook_event(payload, sig_header):
    """Vérifie la signature du webhook et retourne l'événement Stripe. Lève
    stripe.error.SignatureVerificationError si la signature est invalide."""
    return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
