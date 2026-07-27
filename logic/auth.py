# -*- coding: utf-8 -*-
"""
Authentification utilisateur (phase 22/24).

État des lieux fait avant d'écrire ce module (comme pour `logic/user_
identity.py`, phase 3, jamais modifié ici) : le site n'a jamais eu de
système de compte. `User` n'a aucun champ mot de passe ; aucune
infrastructure d'envoi d'email n'existe nulle part dans le code (recherché
avant cette phase : aucun `smtplib`/`flask_mail`/fournisseur transactionnel).
Construire un mot de passe classique ou un lien "magique" envoyé par email
sortirait donc du périmètre de cette phase (ajouter une dépendance email
n'est pas demandé par la consigne) et risquerait de retarder ou de casser le
paiement — contrainte explicite "ne jamais casser Stripe".

Solution retenue, cohérente avec ce qui existe déjà : un JETON D'ACCÈS
PERSONNEL opaque (`UserAccessToken`, phase 22/24, `logic/models.py`) —
même principe qu'une clé API. Il est émis et affiché UNE SEULE FOIS à
l'utilisateur, au moment où l'app peut prouver qu'elle lui parle
légitimement (juste après confirmation Stripe qu'IL vient de payer, cf.
`app.payment_success` — c'est exactement la même frontière de confiance déjà
utilisée aujourd'hui pour le téléchargement du PDF par order_id, pas une
nouvelle hypothèse de sécurité). L'utilisateur peut ensuite revenir sur le
site (autre appareil, session expirée) en collant ce jeton sur `/login` :
`verify_token` le retrouve, `login` établit une SESSION FLASK (cookie signé
par `app.secret_key`, déjà utilisé pour la session admin depuis la phase
"Dashboard admin") — aucune donnée sensible n'est stockée en clair côté
serveur ni côté client au-delà de l'identifiant utilisateur.

Limite documentée (comme toutes les limites précédentes du projet) : si
l'utilisateur perd son jeton sans avoir de session active, il n'existe pas
encore de moyen de lui en redonner un sans passer par un nouvel achat/webhook
Stripe (pas d'envoi d'email). Résoudre cela proprement nécessiterait
d'ajouter un fournisseur d'email, hors périmètre explicite de cette phase.

Ne modifie jamais `logic/stripe_client.py`, `logic/orders.py`,
`logic/promo_codes.py`, ni la logique de vérification de paiement elle-même
(`app.payment_success` n'est enrichie qu'APRÈS la confirmation `order.get(
"paid")`, jamais avant) : ce module est appelé de façon strictement
additive, par des routes ou hooks post-paiement qui absorbent déjà toute
exception (même garantie que `app._essayer_generer_programme_v2`, phase 12)."""
import hashlib
import secrets

from flask import session

from logic.db import db
from logic.models import User, UserAccessToken

# Durée de vie de la session Flask (cookie signé) : 90 jours, cohérent avec
# un "espace personnel" que l'on ne veut pas voir se déconnecter à chaque
# fermeture de navigateur — aucune donnée sensible n'y est stockée (seul
# l'identifiant utilisateur), le jeton d'accès reste la seule information à
# protéger. Premier jet documenté, à ajuster si besoin.
DUREE_SESSION_JOURS = 90


def _hash_token(raw_token):
    """SHA-256 : suffisant ici (contrairement à un mot de passe), le jeton
    est un secret opaque à haute entropie généré par `secrets.token_urlsafe`
    (jamais choisi par l'utilisateur) — pas de risque de force brute par
    dictionnaire, pas besoin d'un algorithme de hachage lent (bcrypt/scrypt)."""
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def generate_raw_token():
    """256 bits d'entropie, encodage URL-safe (facilite le copier-coller
    sur `/login`, cf. template)."""
    return secrets.token_urlsafe(32)


def issue_token_for_user(user):
    """issue_token_for_user(user) -> jeton BRUT (str), affiché une seule
    fois à l'appelant (jamais reconsultable ensuite : seule l'empreinte est
    conservée). Remplace tout jeton précédent pour cet utilisateur (au plus
    un jeton actif à la fois, cf. `UserAccessToken.user_id` unique) — émettre
    un nouveau jeton invalide donc automatiquement un ancien jeton perdu/
    compromis."""
    raw_token = generate_raw_token()
    token_hash = _hash_token(raw_token)

    existant = UserAccessToken.query.filter_by(user_id=user.id).first()
    if existant is not None:
        existant.token_hash = token_hash
        existant.last_used_at = None
    else:
        db.session.add(UserAccessToken(user_id=user.id, token_hash=token_hash))

    db.session.commit()
    return raw_token


def verify_token(raw_token):
    """verify_token(raw_token) -> User ou None. Ne révèle jamais si un email
    existe (pas de distinction de message d'erreur côté route) — protège
    contre l'énumération de comptes. Met à jour `last_used_at` (traçabilité,
    lecture seule pour le reste du moteur)."""
    raw_token = (raw_token or "").strip()
    if not raw_token:
        return None

    from datetime import datetime

    entree = UserAccessToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if entree is None:
        return None

    entree.last_used_at = datetime.utcnow()
    db.session.commit()
    return entree.user


def login(user):
    """Établit la session Flask pour cet utilisateur (cookie signé, comme la
    session admin déjà en place) — ne stocke QUE l'identifiant, jamais le
    jeton lui-même côté session."""
    from datetime import timedelta

    session["user_id"] = user.id
    session.permanent = True
    # `PERMANENT_SESSION_LIFETIME` est un réglage d'application (Flask),
    # positionné ici plutôt que dans app.py pour que la durée de vie de la
    # session reste un détail interne de ce module d'authentification.
    from flask import current_app
    current_app.permanent_session_lifetime = timedelta(days=DUREE_SESSION_JOURS)


def logout():
    session.pop("user_id", None)


def current_user():
    """current_user() -> User connecté (session Flask) ou None. Lecture
    seule, ne lève jamais d'exception (même garantie que le reste du moteur) —
    un `user_id` de session pointant vers un User supprimé retourne
    simplement None plutôt que de planter."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return User.query.get(user_id)
