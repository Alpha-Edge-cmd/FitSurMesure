# -*- coding: utf-8 -*-
"""
Stockage des messages envoyés via le formulaire de contact du site.

Retour Samy (prompt hors 24 phases) : "je veux également qu'il puisse me
laisser un message directement sur le site afin que au moindre problème il
y'ai une réponse." Réponse validée par Samy pour ce périmètre : "Dans le
dashboard admin (Recommandé)" — les messages ne sont visibles que dans le
dashboard admin, aucun envoi d'email (aucune infrastructure d'envoi d'email
n'existe dans ce projet ; même principe déjà appliqué pour l'authentification
par jeton, cf. logic/auth.py, plutôt qu'un envoi d'email de connexion).

Stockage JSON simple (même principe que logic/orders.py et
logic/promo_codes.py) : le besoin validé est "Liste + marquer comme lu", pas
de recherche/filtre avancé, donc pas de justification pour une nouvelle table
relationnelle.
"""
import json
import os
import uuid
from datetime import datetime

from logic.data_dir import get_data_dir

DATA_DIR = get_data_dir()
DATA_FILE = os.path.join(DATA_DIR, "contact_messages.json")


def _now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"messages": {}}, f, ensure_ascii=False, indent=2)


def _load():
    _ensure_store()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(store):
    _ensure_store()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def create_message(nom, email, message):
    """Enregistre un nouveau message de contact. `nom`/`email` sont
    facultatifs (un visiteur peut laisser un message sans se identifier
    précisément) ; `message` est le seul champ réellement requis (vérifié
    côté route, jamais côté stockage — ce module ne fait qu'enregistrer)."""
    store = _load()
    message_id = uuid.uuid4().hex
    store["messages"][message_id] = {
        "nom": (nom or "").strip(),
        "email": (email or "").strip(),
        "message": (message or "").strip(),
        "created_at": _now(),
        "lu": False,
    }
    _save(store)
    return message_id


def list_messages():
    """Les plus récents en premier."""
    store = _load()
    rows = [dict(m, id=mid) for mid, m in store["messages"].items()]
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


def mark_read(message_id, lu=True):
    store = _load()
    entry = store["messages"].get(message_id)
    if not entry:
        return False
    entry["lu"] = bool(lu)
    _save(store)
    return True


def delete_message(message_id):
    store = _load()
    if message_id in store["messages"]:
        del store["messages"][message_id]
        _save(store)
        return True
    return False
