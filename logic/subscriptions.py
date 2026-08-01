# -*- coding: utf-8 -*-
"""
Droits liés à l'abonnement annuel.

Retour Samy : « vérifie que l'abonnement annuel fonctionne correctement,
étant donné que je ne peux pas le tester ».

Audit qui a motivé ce module — trois trous constatés :

  1. La landing promet « régénérer un nouveau programme aussi souvent que
     nécessaire », mais aucun code ne donnait ce droit. Un abonné à 59 € avait
     exactement les mêmes possibilités qu'un acheteur à 22,99 €.
  2. Le webhook ne traitait que `checkout.session.completed`. Stripe prélevait
     bien la deuxième année, mais le site n'en savait rien.
  3. Une résiliation n'était nulle part enregistrée : le client gardait son
     accès indéfiniment.

Ce module centralise la réponse à une seule question : « cet email a-t-il un
abonnement actif aujourd'hui ? » — et la stocke de façon simple, dans le même
fichier JSON que les commandes (aucune nouvelle table, aucune migration).

Choix de conception : on ne fait JAMAIS confiance à la seule existence d'une
commande "abonnement" payée. Un abonnement a une date de fin, qui recule à
chaque renouvellement facturé par Stripe et qui se fige en cas de résiliation.
C'est cette date qui fait foi.
"""
import json
import os
from datetime import datetime, timedelta

from logic.orders import _load, _save, _now  # même magasin JSON, même verrou

# Durée de validité accordée à chaque paiement d'abonnement. Volontairement un
# peu plus longue qu'un an : si le prélèvement de renouvellement traîne de
# quelques jours côté Stripe, le client ne perd pas son accès entre-temps.
DUREE_ABONNEMENT_JOURS = 372  # 1 an + 7 jours de tolérance

FORMULE_ABONNEMENT = "abonnement"


def _normaliser(email):
    return (email or "").strip().lower()


def _store_abonnements(store):
    return store.setdefault("abonnements", {})


def activer(email, stripe_subscription_id=None, duree_jours=DUREE_ABONNEMENT_JOURS):
    """Active (ou prolonge) l'abonnement d'un email.

    Appelé au premier paiement ET à chaque renouvellement facturé par Stripe.
    Prolonger plutôt que réécrire évite de raccourcir un abonnement si un
    événement arrive en double ou dans le désordre — Stripe ne garantit ni
    l'unicité ni l'ordre de livraison des webhooks.
    """
    email = _normaliser(email)
    if not email:
        return None

    store = _load()
    abonnements = _store_abonnements(store)
    existant = abonnements.get(email) or {}

    depart = datetime.utcnow()
    fin_actuelle = existant.get("valide_jusqu_au")
    if fin_actuelle:
        try:
            fin_dt = datetime.fromisoformat(fin_actuelle)
            if fin_dt > depart:
                depart = fin_dt  # on prolonge, on ne remet pas à zéro
        except ValueError:
            pass

    abonnements[email] = {
        "email": email,
        "stripe_subscription_id": stripe_subscription_id or existant.get("stripe_subscription_id"),
        "valide_jusqu_au": (depart + timedelta(days=duree_jours)).isoformat(),
        "resilie": False,
        "mis_a_jour_le": _now(),
    }
    _save(store)
    return abonnements[email]


def resilier(stripe_subscription_id=None, email=None):
    """Marque un abonnement comme résilié.

    On NE supprime PAS l'accès immédiatement : le client a payé jusqu'à la fin
    de sa période, il doit en profiter. On coupe simplement le renouvellement,
    et `est_actif` cessera de répondre vrai à l'échéance.
    """
    store = _load()
    abonnements = _store_abonnements(store)

    cible = None
    if email:
        cible = abonnements.get(_normaliser(email))
    if cible is None and stripe_subscription_id:
        for abo in abonnements.values():
            if abo.get("stripe_subscription_id") == stripe_subscription_id:
                cible = abo
                break

    if cible is None:
        return False

    cible["resilie"] = True
    cible["mis_a_jour_le"] = _now()
    _save(store)
    return True


def est_actif(email):
    """True si cet email dispose aujourd'hui d'un abonnement valide.

    Un abonnement résilié reste actif jusqu'à son échéance — c'est du temps
    déjà payé.
    """
    email = _normaliser(email)
    if not email:
        return False

    abo = _store_abonnements(_load()).get(email)
    if not abo:
        return False

    try:
        return datetime.fromisoformat(abo["valide_jusqu_au"]) > datetime.utcnow()
    except (KeyError, ValueError):
        return False


def details(email):
    """Détails de l'abonnement pour affichage dans l'espace personnel, ou None."""
    email = _normaliser(email)
    abo = _store_abonnements(_load()).get(email) if email else None
    if not abo:
        return None
    return {
        "actif": est_actif(email),
        "resilie": bool(abo.get("resilie")),
        "valide_jusqu_au": abo.get("valide_jusqu_au"),
    }


def peut_regenerer(email, order=None):
    """Droit de régénérer un programme complet.

    Réservé aux abonnés : c'est précisément ce que vend l'abonnement annuel
    par rapport à un achat unique. Un acheteur ponctuel garde évidemment le
    droit d'ajuster le programme qu'il a payé (retirer un exercice qu'il
    n'aime pas) — c'est un mécanisme distinct, inchangé.
    """
    if est_actif(email):
        return True
    # Filet : une commande d'abonnement payée dont le webhook n'aurait pas
    # encore été traité ne doit pas priver le client de ce qu'il vient
    # d'acheter.
    if order and order.get("formule") == FORMULE_ABONNEMENT and order.get("paid"):
        return True
    return False
