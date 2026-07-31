# -*- coding: utf-8 -*-
"""
Gestion des codes promo / parrainage.

Règle métier : un ami ou un influenceur reçoit un code qui lui donne UN programme
gratuit (pour tester lui-même). Une fois ce premier programme gratuit consommé, le
même code devient un code de parrainage classique : les personnes qu'il ramène
obtiennent une réduction (par défaut 10%) sur leur achat, et lui touche une
commission (par défaut 10%) sur le montant réellement payé par chaque personne.

Stockage en JSON simple (pas de vraie base de données pour l'instant). Le site
ayant maintenant un vrai paiement (Stripe), la réduction est appliquée directement
sur le prix envoyé à Stripe ; la commission reste indicative, à reverser
manuellement par l'administrateur du site.
"""
import json
import os
import re
import string
import secrets
from datetime import datetime

from logic.data_dir import get_data_dir

DATA_DIR = get_data_dir()
DATA_FILE = os.path.join(DATA_DIR, "promo_codes.json")

DEFAULT_COMMISSION_PCT = 10
DEFAULT_DISCOUNT_PCT = 10


def _now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"codes": {}}, f, ensure_ascii=False, indent=2)


def _load():
    _ensure_store()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(store):
    _ensure_store()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def _normalize(code):
    return re.sub(r"\s+", "", (code or "")).upper()


def price_to_float(prix_label):
    """Convertit '22,99€' ou '59€ / an' en 22.99 / 59.0. Retourne 0.0 si non reconnu."""
    if not prix_label:
        return 0.0
    m = re.search(r"(\d+(?:[.,]\d+)?)", prix_label)
    if not m:
        return 0.0
    return float(m.group(1).replace(",", "."))


# Alias interne conservé pour compatibilité.
_price_to_float = price_to_float


def generate_code(base=""):
    """Génère un code lisible : préfixe basé sur le nom si fourni + suffixe aléatoire,
    ex: ALEX-7F3B. Garantit l'unicité par rapport aux codes déjà stockés."""
    store = _load()
    prefix = re.sub(r"[^A-Z0-9]", "", (base or "").upper())[:10] or "AMI"
    while True:
        suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        code = f"{prefix}-{suffix}"
        if code not in store["codes"]:
            return code


def create_code(owner_name, owner_email="", code=None, commission_pct=DEFAULT_COMMISSION_PCT,
                 discount_pct=DEFAULT_DISCOUNT_PCT, notes=""):
    """Crée un nouveau code promo. Si `code` n'est pas fourni, en génère un à partir
    du nom du bénéficiaire. Retourne (code, error) — error est None si tout va bien."""
    store = _load()
    if not owner_name or not owner_name.strip():
        return None, "Le nom du bénéficiaire est obligatoire."

    if code:
        code = _normalize(code)
        if not code:
            return None, "Code invalide."
        if code in store["codes"]:
            return None, f"Le code « {code} » existe déjà."
    else:
        code = generate_code(owner_name)

    store["codes"][code] = {
        "owner_name": owner_name.strip(),
        "owner_email": (owner_email or "").strip(),
        "commission_pct": float(commission_pct),
        "discount_pct": float(discount_pct),
        "free_claimed": False,
        "notes": notes or "",
        "active": True,
        "created_at": _now(),
        "uses": [],
    }
    _save(store)
    return code, None


def get_code(code):
    store = _load()
    return store["codes"].get(_normalize(code))


def set_active(code, active):
    store = _load()
    entry = store["codes"].get(_normalize(code))
    if not entry:
        return False
    entry["active"] = bool(active)
    _save(store)
    return True


def reset_free_trial(code):
    """Réinitialise l'essai gratuit d'un code (permet au bénéficiaire de reprendre
    un programme gratuit, ex: en cas de souci technique lors de la première tentative)."""
    store = _load()
    entry = store["codes"].get(_normalize(code))
    if not entry:
        return False
    entry["free_claimed"] = False
    _save(store)
    return True


def delete_code(code):
    store = _load()
    code = _normalize(code)
    if code in store["codes"]:
        del store["codes"][code]
        _save(store)
        return True
    return False


def get_redemption_terms(code):
    """Indique, SANS rien modifier, ce que donnerait l'utilisation de ce code
    maintenant : gratuit (si le programme gratuit n'a pas encore été consommé) ou
    réduction de parrainage. Retourne None si le code est invalide/inactif."""
    entry = get_code(code)
    if not entry or not entry.get("active", True):
        return None
    free = not entry.get("free_claimed", False)
    return {
        "free": free,
        "discount_pct": 0.0 if free else entry.get("discount_pct", DEFAULT_DISCOUNT_PCT),
        "commission_pct": entry.get("commission_pct", DEFAULT_COMMISSION_PCT),
    }


def claim_free_trial(code):
    """Tente de réserver le programme gratuit unique de ce code. Retourne True si
    réservé avec succès (le code n'avait pas encore été utilisé gratuitement),
    False sinon (déjà consommé, ou code invalide — dans ce cas il faut retomber sur
    le parcours payant avec réduction)."""
    store = _load()
    entry = store["codes"].get(_normalize(code))
    if not entry or not entry.get("active", True) or entry.get("free_claimed", False):
        return False
    entry["free_claimed"] = True
    _save(store)
    return True


def append_usage(code, formule, free, prix_plein, discount_pct, commission_pct, prenom=""):
    """Enregistre définitivement l'utilisation d'un code (appelé une fois le
    paiement confirmé, jamais avant, pour ne pas compter des paiements abandonnés
    comme des parrainages). Calcule le montant réellement payé et la commission à
    partir des conditions déjà décidées au moment de la création de la commande
    (`free` et `discount_pct`), pas des réglages actuels du code, pour rester
    cohérent avec ce qui a vraiment été facturé. Retourne True si enregistré."""
    store = _load()
    entry = store["codes"].get(_normalize(code))
    if not entry:
        return False

    montant_paye = 0.0 if free else round(prix_plein * (1 - discount_pct / 100), 2)
    commission = 0.0 if free else round(montant_paye * commission_pct / 100, 2)

    entry["uses"].append({
        "date": _now(),
        "formule": formule or "",
        "free": bool(free),
        "prix_plein": round(prix_plein, 2),
        "discount_pct": discount_pct,
        "montant_paye": montant_paye,
        "commission_pct": commission_pct,
        "commission": commission,
        "prenom": prenom or "",
    })
    _save(store)
    return True


def list_codes_with_stats():
    """Retourne la liste des codes avec, pour chacun : nombre d'utilisations
    (gratuites + parrainages payants), chiffre d'affaires généré (indicatif, basé
    sur les montants réellement payés après réduction) et commission due."""
    store = _load()
    result = []
    for code, entry in sorted(store["codes"].items()):
        uses = entry.get("uses", [])
        nb_uses = len(uses)
        nb_referrals = sum(1 for u in uses if not u.get("free"))
        ca_total = sum(u.get("montant_paye", 0.0) for u in uses)
        commission = sum(u.get("commission", 0.0) for u in uses)
        result.append({
            "code": code,
            "owner_name": entry.get("owner_name", ""),
            "owner_email": entry.get("owner_email", ""),
            "commission_pct": entry.get("commission_pct", DEFAULT_COMMISSION_PCT),
            "discount_pct": entry.get("discount_pct", DEFAULT_DISCOUNT_PCT),
            "free_claimed": entry.get("free_claimed", False),
            "active": entry.get("active", True),
            "created_at": entry.get("created_at", ""),
            "notes": entry.get("notes", ""),
            "nb_uses": nb_uses,
            "nb_referrals": nb_referrals,
            "ca_total": round(ca_total, 2),
            "commission_due": round(commission, 2),
            "uses": list(reversed(uses)),  # plus récent en premier
        })
    return result
