# -*- coding: utf-8 -*-
"""
Couche de données FitSurMesure V2 (fondations, phase 1/16).

Remplace progressivement le stockage JSON à plat (logic/orders.py,
logic/promo_codes.py) par une vraie base de données, comme décidé dans
architecture_v2_consolidation.md. Cette phase ne fait QUE poser
l'infrastructure (connexion + création des tables) : elle ne migre pas les
données existantes et ne modifie aucune route/fonctionnalité actuelle.

Résolution de l'URL de connexion, sur le même principe que
logic/data_dir.py (DATA_DIR) :
  - en production (Render), la variable d'environnement DATABASE_URL pointe
    vers la base PostgreSQL managée ;
  - en local, à défaut de DATABASE_URL, on utilise un simple fichier SQLite
    stocké dans le même dossier que les fichiers JSON existants (data/), pour
    ne rien exiger de plus qu'aujourd'hui pour développer en local.
"""
import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

from logic.data_dir import get_data_dir

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite n'applique pas les contraintes de clé étrangère par défaut
    (contrairement à PostgreSQL, utilisé en production) — sans ce réglage,
    une ligne pourrait référencer un exercise_id inexistant en local sans
    erreur, alors qu'elle serait rejetée en production. On force le même
    comportement partout pour ne pas découvrir un bug de contrainte
    uniquement après déploiement."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_database_uri():
    """Retourne l'URI de connexion à utiliser pour SQLAlchemy."""
    url = os.environ.get("DATABASE_URL")
    if url:
        # Render (et d'autres hébergeurs) fournissent parfois une URL qui commence
        # par "postgres://" alors que SQLAlchemy 2.x exige "postgresql://".
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    sqlite_path = os.path.join(data_dir, "fitsurmesure.db")
    return f"sqlite:///{sqlite_path}"


def init_db(app):
    """À appeler une fois, juste après la création de l'app Flask. Crée les
    tables si elles n'existent pas encore — ne touche jamais une table déjà
    créée (pas de migration automatique destructive)."""
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    # Importé ici (et pas en haut du fichier) pour éviter tout import circulaire
    # entre logic/db.py et logic/models.py, qui a besoin de `db` déjà défini.
    from logic import models  # noqa: F401

    with app.app_context():
        db.create_all()
