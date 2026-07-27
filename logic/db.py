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
    créée (pas de migration automatique destructive).

    Synchronise aussi le catalogue d'exercices (data/exercise_enrichment.json
    -> table Exercise) à CHAQUE démarrage de l'application. Découverte
    critique (prompt hors 24 phases, retour utilisateur "le programme ne
    change pas d'un poil") : rien ne rejouait jamais `import_enriched_
    catalog()` en production — seuls les tests locaux le faisaient. Résultat,
    la table Exercise restait vide sur Render, et `get_recommendation_catalog()`
    retombait silencieusement sur l'ANCIEN catalogue legacy (111 exercices,
    logic/exercises_db.py) à chaque génération de programme, quel que soit le
    contenu réel de data/exercise_enrichment.json (486 exercices depuis ce
    même prompt). `import_enriched_catalog` est idempotent et n'écrase jamais
    une décision de revue humaine existante (cf. sa docstring) : l'appeler à
    chaque boot est donc sans danger, y compris en production. `auto_approve
    =True` ne s'applique qu'à la CRÉATION (jamais à une mise à jour) : au
    tout premier boot après ce correctif, le nouveau catalogue est directement
    exposé au moteur ; tout exercice approuvé/rejeté ensuite à la main garde
    son statut pour toujours, réimport après réimport."""
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    # Importés ici (et pas en haut du fichier) pour éviter tout import
    # circulaire entre logic/db.py et logic/models.py / logic/exercise_catalog_
    # import.py, qui ont besoin de `db` déjà défini.
    from logic import models  # noqa: F401

    with app.app_context():
        db.create_all()
        _ajouter_colonnes_additives_manquantes()

        try:
            from logic.exercise_catalog_import import import_enriched_catalog
            import_enriched_catalog(auto_approve=True)
        except Exception as exc:  # ne doit jamais empêcher l'application de démarrer
            import sys
            print(f"[init_db] synchronisation du catalogue d'exercices impossible au démarrage : {exc}", file=sys.stderr)


# Colonnes ajoutées à un modèle APRÈS la création initiale de sa table en
# production (ex: Exercise.portion_anatomique, catalogue v3, prompt final hors
# 24 phases) : `db.create_all()` ne les ajoute jamais à une table déjà
# existante (cf. docstring de `init_db` ci-dessus). Table -> [(colonne, type
# SQL portable SQLite/Postgres)] à vérifier/ajouter à chaque démarrage,
# idempotent (ne fait rien si la colonne existe déjà).
COLONNES_ADDITIVES = {
    "exercises": [("portion_anatomique", "VARCHAR(60)")],
    "program_exercises": [("conseil_execution", "TEXT")],
}


def _ajouter_colonnes_additives_manquantes():
    from sqlalchemy import inspect, text

    inspecteur = inspect(db.engine)
    for table, colonnes in COLONNES_ADDITIVES.items():
        if table not in inspecteur.get_table_names():
            continue  # table pas encore créée (ne devrait pas arriver juste après create_all())
        colonnes_existantes = {c["name"] for c in inspecteur.get_columns(table)}
        for nom_colonne, type_sql in colonnes:
            if nom_colonne in colonnes_existantes:
                continue
            with db.engine.begin() as connexion:
                connexion.execute(text(f"ALTER TABLE {table} ADD COLUMN {nom_colonne} {type_sql}"))
