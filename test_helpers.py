# -*- coding: utf-8 -*-
"""Aide partagée pour les scripts de test de régression.

Le PDF n'est plus généré via un simple POST /generate : il faut passer par une
commande payée (/create-checkout-session puis /download/<order_id>). Les codes
promo, eux, n'offrent plus qu'UN SEUL usage gratuit par code (le reste donne une
réduction, pas un accès gratuit) — inutilisable tel quel pour générer des dizaines
de PDF de test avec le même code.

Ces scripts testent la qualité du programme généré (variété d'exercices, absence
de chevauchement de texte, etc.), pas la logique métier du paiement ou des codes
promo (qui ont leurs propres tests dans test_payment_and_promo.py). On génère donc
le PDF directement via les fonctions internes (les mêmes que celles utilisées par
/download/<order_id> une fois une commande payée), en contournant complètement le
flux HTTP de paiement."""
import io

from app import app as flask_app, _build_everything
from logic.pdf_generator import generate_pdf


def ensure_test_promo_code():
    """Conservé pour compatibilité avec les scripts existants ; n'est plus
    nécessaire depuis que generate_via_payment ne passe plus par un code promo."""
    pass


class _FakeResponse:
    """Émule l'interface minimale d'une réponse Flask (resp.status_code,
    resp.get_data(...), resp.get_json()) utilisée par les scripts de test."""

    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")

    def get_data(self, as_text=False):
        if as_text:
            return self._data.decode("utf-8", errors="replace")
        return self._data

    def get_json(self):
        import json
        return json.loads(self._data.decode("utf-8"))


def generate_via_payment(client, payload, code_promo=None):
    """Génère le PDF directement à partir des réponses du questionnaire (`payload`),
    en appelant les mêmes fonctions internes que /download/<order_id> une fois la
    commande payée. Le paramètre `client` n'est plus utilisé (conservé pour ne pas
    avoir à changer tous les appels existants) ; `code_promo` est ignoré (plus
    pertinent ici, voir le docstring du module)."""
    with flask_app.app_context():
        error, profile, nutrition, program, cardio, lifestyle = _build_everything(payload)
        if error:
            resp, code = error
            return _FakeResponse(code, resp.get_data())

        buffer = io.BytesIO()
        generate_pdf(buffer, profile, nutrition, program, cardio, lifestyle)
        buffer.seek(0)
        return _FakeResponse(200, buffer.getvalue())
