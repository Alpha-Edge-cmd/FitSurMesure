# -*- coding: utf-8 -*-
"""
Stockage des commandes (une commande = une réponse au questionnaire en attente de
paiement, ou déjà payée). Permet de :
  - créer une commande avant de rediriger vers Stripe Checkout, en gardant les
    réponses du questionnaire côté serveur (pour ne pas les perdre pendant
    l'aller-retour vers Stripe) ;
  - marquer une commande comme payée une fois le paiement confirmé (redirection
    de succès et/ou webhook Stripe) ;
  - régénérer le PDF (avec des exercices/séances remplacés suite à l'écran de
    révision) sans redemander un paiement, tant que la commande est marquée payée.

Stockage en JSON simple (pas de vraie base de données pour l'instant), comme pour
les codes promo.
"""
import json
import os
import uuid
from datetime import datetime

from logic.data_dir import get_data_dir

DATA_DIR = get_data_dir()
DATA_FILE = os.path.join(DATA_DIR, "orders.json")


def _now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"orders": {}}, f, ensure_ascii=False, indent=2)


def _load():
    _ensure_store()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(store):
    _ensure_store()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def create_order(data, formule, code_promo="", free=False, discount_pct=0.0, commission_pct=0.0):
    """Crée une commande à partir des réponses du questionnaire (`data`, dict JSON-
    sérialisable). `free` = True si l'accès est gratuit (premier essai offert d'un
    code promo, aucun paiement Stripe requis). `discount_pct`/`commission_pct` sont
    les conditions du code promo au moment de la commande (figées ici pour que le
    calcul de commission à la livraison reste cohérent avec ce qui a été payé, même
    si les réglages du code changent entre-temps). Retourne l'order_id."""
    store = _load()
    order_id = uuid.uuid4().hex
    store["orders"][order_id] = {
        "data": data,
        "formule": formule,
        "code_promo": code_promo or "",
        "code_promo_free": bool(free),
        "code_promo_discount_pct": float(discount_pct),
        "code_promo_commission_pct": float(commission_pct),
        "created_at": _now(),
        "paid": bool(free),
        "free": bool(free),
        "stripe_session_id": None,
        "stripe_subscription_id": None,
        "commission_recorded": False,
    }
    _save(store)
    return order_id


def get_order(order_id):
    store = _load()
    return store["orders"].get(order_id)


def set_stripe_session(order_id, session_id):
    store = _load()
    order = store["orders"].get(order_id)
    if not order:
        return False
    order["stripe_session_id"] = session_id
    _save(store)
    return True


def mark_paid(order_id, stripe_session_id=None, stripe_subscription_id=None):
    store = _load()
    order = store["orders"].get(order_id)
    if not order:
        return False
    order["paid"] = True
    if stripe_session_id:
        order["stripe_session_id"] = stripe_session_id
    if stripe_subscription_id:
        order["stripe_subscription_id"] = stripe_subscription_id
    _save(store)
    return True


def mark_commission_recorded(order_id):
    store = _load()
    order = store["orders"].get(order_id)
    if not order:
        return False
    order["commission_recorded"] = True
    _save(store)
    return True


def update_order_data(order_id, exercices_rejetes=None, cardio_rejets=None):
    """Fusionne des retours de l'écran de révision (\"je n'aime pas cet exercice\")
    dans les données stockées de la commande, pour permettre une régénération du
    PDF sans nouveau paiement."""
    store = _load()
    order = store["orders"].get(order_id)
    if not order:
        return False
    if exercices_rejetes is not None:
        order["data"]["exercices_rejetes"] = exercices_rejetes
    if cardio_rejets is not None:
        order["data"]["cardio_rejets"] = cardio_rejets
    _save(store)
    return True


def find_order_by_session_id(session_id):
    store = _load()
    for order_id, order in store["orders"].items():
        if order.get("stripe_session_id") == session_id:
            return order_id, order
    return None, None
