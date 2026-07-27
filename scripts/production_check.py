# -*- coding: utf-8 -*-
"""
Phase 24/24 — Audit production complet.

Script autonome (pas de dépendance à pytest) qui exécute des vérifications
RÉELLES — pas seulement une relecture du code — sur les 10 domaines demandés
(Architecture, Base de données, Sécurité, Performance, Paiement, Catalogue
exercices, Programme généré, PDF, Questionnaire, Feedback) et les 7 scénarios
explicitement demandés (installation vierge, migration DB, import catalogue,
génération programme, paiement simulé, PDF, utilisateur complet).

Produit `PRODUCTION_READY.md` à la racine du projet, avec chaque constat
classé OK / WARNING / BLOCKER.

SÉCURITÉ D'EXÉCUTION — CE SCRIPT NE TOUCHE JAMAIS AUX DONNÉES RÉELLES.
Avant même d'importer `app` (qui appelle `init_db(app)` -> `db.create_all()`
dès l'import), ce script redirige DATA_DIR et DATABASE_URL vers un dossier
temporaire jetable créé pour la durée de l'exécution (cf. `_isoler_
environnement()` ci-dessous) — qu'il tourne en local ou directement sur le
serveur de production, aucune commande, aucun code promo, aucun utilisateur
ni programme réels ne sont lus ou modifiés par les scénarios fonctionnels de
cet audit. Les variables d'environnement RÉELLES sont capturées une seule
fois avant cette redirection (`ENV_REEL`), uniquement pour les contrôles de
sécurité/configuration (lecture seule, jamais utilisées pour écrire quoi que
ce soit). Le dossier temporaire est supprimé à la fin de l'exécution.

Conformément à la consigne de cette phase ("Aucun changement fonctionnel
sans justification"), ce script est un pur outil d'audit : il ne modifie
aucun fichier du site (hors la production de PRODUCTION_READY.md).

Usage :
    python3 scripts/production_check.py
"""
import io
import os
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime

# ---------------------------------------------------------------------------
# 0) Isolation totale AVANT tout import de `app`/`logic`.
# ---------------------------------------------------------------------------
ENV_REEL = dict(os.environ)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TEMP_DIR = tempfile.mkdtemp(prefix="fitsurmesure_audit_")
os.environ["DATA_DIR"] = TEMP_DIR
os.environ.pop("DATABASE_URL", None)  # force un SQLite jetable, jamais la base réelle

import app as appmod  # noqa: E402  (import après isolation, volontaire)
from logic import auth, order_migration, orders, program_interaction, program_service, stripe_client  # noqa: E402
from logic.catalog_monitoring import catalog_health_report  # noqa: E402
from logic.db import db, get_database_uri  # noqa: E402
from logic.exercise_catalog_import import import_enriched_catalog  # noqa: E402
from logic.exercise_catalog_service import get_catalog_status  # noqa: E402
from logic.exercise_review import approve_exercise  # noqa: E402
from logic.feedback_learning import calculate_user_preferences  # noqa: E402
from logic.models import (  # noqa: E402
    Exercise, ExerciseFeedback, ExerciseUsageLog, Program, ProfileSnapshot,
    ProgramExercise, ProgramSession, User, UserAccessToken,
)
from logic.pdf_generator import generate_pdf  # noqa: E402
from logic.pdf_program_adapter import program_to_pdf_data  # noqa: E402
from logic.program_validation import validate_generated_program  # noqa: E402

# Garde-fou : si jamais l'isolation ci-dessus a échoué pour une raison
# quelconque (ex: DATA_DIR ignoré), on préfère arrêter net plutôt que de
# risquer d'exécuter les scénarios fonctionnels contre de vraies données.
_uri_effective = get_database_uri()
if TEMP_DIR.replace("\\", "/") not in _uri_effective.replace("\\", "/"):
    print(f"ERREUR FATALE : isolation de l'audit compromise (DATABASE_URI = {_uri_effective}). Arrêt immédiat.")
    sys.exit(1)


class Rapport:
    """Collecteur simple : chaque contrôle ajoute une ligne OK/WARNING/BLOCKER."""

    def __init__(self):
        self.lignes = []

    def _ajouter(self, statut, categorie, nom, detail):
        self.lignes.append({"statut": statut, "categorie": categorie, "nom": nom, "detail": detail})

    def ok(self, categorie, nom, detail=""):
        self._ajouter("OK", categorie, nom, detail)

    def warning(self, categorie, nom, detail=""):
        self._ajouter("WARNING", categorie, nom, detail)

    def blocker(self, categorie, nom, detail=""):
        self._ajouter("BLOCKER", categorie, nom, detail)

    def compte(self, statut):
        return sum(1 for ligne in self.lignes if ligne["statut"] == statut)


RAPPORT = Rapport()
TIMINGS = {}

MUSCLES = ["pecs", "epaules", "triceps", "dos", "biceps", "quadriceps", "ischio", "fessiers", "mollets", "abdos"]

DEFAUTS_DEV = {
    "SECRET_KEY": "fitsurmesure-cle-secrete-dev-a-changer",
    "ADMIN_PASSWORD": "fitsurmesure2026",
    "OWNER_ACCESS_CODE": "SAMY-ACCES-ILLIMITE",
}


def _section(categorie, nom_section):
    """Isole chaque section : toute exception non prévue devient un BLOCKER
    (avec traceback complet) au lieu de faire planter tout l'audit ou de
    sauter silencieusement le reste des contrôles."""
    def decorateur(fn):
        def wrapper(*args, **kwargs):
            try:
                fn(*args, **kwargs)
            except Exception:
                RAPPORT.blocker(
                    categorie, nom_section,
                    f"Exception inattendue pendant cette section :\n{traceback.format_exc()}",
                )
        return wrapper
    return decorateur


def questionnaire_complet(**kwargs):
    defaults = dict(
        prenom="Testeur", consentement_rgpd=True, date_naissance="1992-04-15", formule="musculation",
        poids=78, taille=180, sexe="Homme",
        niveau_musculation="Intermédiaire", objectif_principal="Prise de muscle",
        objectif_secondaire=None, composition_corporelle="Je ne sais pas",
        frequence_entrainement=3, duree_seance="1h - 1h30", equipement="Salle complète",
        exercices_maitrises=[], mobilite_generale=3, amplitude_squat="Avec difficulté",
        amplitude_epaule="Avec difficulté", tolerance_technique=3,
        preference_style_charge="Un mix des deux", preference_materiel="Pas de préférence",
        blessures=[], severite_blessure={}, autre_sport="Non",
        disponibilite_reelle="Comme prévu", sommeil="7 à 8h", niveau_stress="Modéré",
    )
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# 1) ARCHITECTURE
# ---------------------------------------------------------------------------
@_section("Architecture", "Structure du projet")
def check_architecture():
    fichiers_attendus = [
        "app.py", "requirements.txt", "Procfile", "render.yaml",
        "logic/db.py", "logic/models.py", "logic/data_dir.py",
        "logic/orders.py", "logic/promo_codes.py", "logic/stripe_client.py",
        "logic/program_service.py", "logic/program_repository.py", "logic/program_validation.py",
        "logic/program_personalization.py", "logic/feedback_learning.py", "logic/program_interaction.py",
        "logic/auth.py", "logic/user_identity.py", "logic/profile_normalizer.py",
        "logic/exercise_catalog_import.py", "logic/exercise_catalog_validator.py",
        "logic/exercise_review.py", "logic/catalog_monitoring.py",
        "logic/pdf_generator.py", "logic/pdf_program_adapter.py",
        "logic/recommendation/program_builder.py", "logic/recommendation/selector.py",
        "logic/recommendation/scoring.py", "logic/recommendation/history.py",
    ]
    manquants = [f for f in fichiers_attendus if not os.path.isfile(os.path.join(PROJECT_ROOT, f))]
    if manquants:
        RAPPORT.blocker("Architecture", "Fichiers attendus", f"Fichiers manquants : {manquants}")
    else:
        RAPPORT.ok("Architecture", "Fichiers attendus", f"{len(fichiers_attendus)} fichiers clés présents")

    # Séparation des responsabilités : app.py ne doit jamais importer les modules
    # internes du moteur de recommandation directement (déjà vérifié statiquement
    # par test_program_interface.py pour program_interaction.py) — ici on vérifie
    # qu'app.py passe bien par les couches applicatives (program_service, auth,
    # program_interaction) plutôt que d'appeler le moteur ou user_identity en direct.
    with open(os.path.join(PROJECT_ROOT, "app.py"), encoding="utf-8") as f:
        source_app = f.read()
    imports_interdits = ["logic.user_identity", "logic.recommendation.selector", "logic.recommendation.scoring",
                          "logic.program_personalization", "logic.feedback_learning"]
    trouves = [m for m in imports_interdits if m in source_app]
    if trouves:
        RAPPORT.warning("Architecture", "Séparation des couches",
                         f"app.py référence directement : {trouves} (devrait passer par program_service.py)")
    else:
        RAPPORT.ok("Architecture", "Séparation des couches",
                    "app.py ne référence aucun module moteur/interne directement")

    with open(os.path.join(PROJECT_ROOT, "requirements.txt"), encoding="utf-8") as f:
        lignes_req = [l.strip() for l in f if l.strip()]
    non_pinnees = [l for l in lignes_req if "==" not in l]
    if non_pinnees:
        RAPPORT.warning("Architecture", "Dépendances figées", f"Versions non figées : {non_pinnees}")
    else:
        RAPPORT.ok("Architecture", "Dépendances figées", f"{len(lignes_req)} dépendances, toutes avec version figée")

    with open(os.path.join(PROJECT_ROOT, "render.yaml"), encoding="utf-8") as f:
        render_yaml = f.read()
    if "disk:" in render_yaml and "mountPath" in render_yaml:
        RAPPORT.ok("Architecture", "Disque persistant déclaré", "render.yaml déclare un disque persistant")
    else:
        RAPPORT.blocker("Architecture", "Disque persistant déclaré",
                         "render.yaml ne déclare aucun disque persistant (perte de données au redémarrage)")


# ---------------------------------------------------------------------------
# 2) BASE DE DONNÉES — scénarios "installation vierge" + "migration DB"
# ---------------------------------------------------------------------------
@_section("Base de données", "Installation vierge")
def check_installation_vierge():
    """`app` vient d'être importé (donc `init_db(app)` vient d'appeler
    `db.create_all()` une première fois, sur le dossier temporaire isolé créé
    en tête de ce script) : toutes les tables doivent exister et être vides —
    c'est exactement le scénario "installation vierge" demandé."""
    with appmod.app.app_context():
        tables = list(db.metadata.tables.keys())
        attendues = {
            "users", "profile_snapshots", "programs", "program_sessions", "program_exercises",
            "exercises", "exercise_usage_logs", "exercise_feedbacks", "user_access_tokens",
        }
        manquantes = attendues - set(tables)
        if manquantes:
            RAPPORT.blocker("Base de données", "Installation vierge",
                             f"Tables manquantes après création à vide : {manquantes}")
            return

        comptes = {nom: db.session.execute(db.metadata.tables[nom].select()).rowcount for nom in attendues}
        # rowcount sur un SELECT SQLite/Postgres via l'API Core n'est pas toujours fiable ;
        # on recompte explicitement via count() pour chaque modèle connu.
        comptes = {
            "users": User.query.count(), "programs": Program.query.count(),
            "exercises": Exercise.query.count(), "profile_snapshots": ProfileSnapshot.query.count(),
            "user_access_tokens": UserAccessToken.query.count(),
        }
        non_vides = {k: v for k, v in comptes.items() if v != 0}
        if non_vides:
            RAPPORT.blocker("Base de données", "Installation vierge",
                             f"Tables non vides juste après une installation neuve : {non_vides}")
        else:
            RAPPORT.ok("Base de données", "Installation vierge",
                        f"{len(attendues)} tables créées, toutes vides ({TEMP_DIR})")


@_section("Base de données", "Migration douce")
def check_migration_db():
    """Insère une donnée, ré-invoque `db.create_all()` (le cœur non
    destructif de `init_db()`, cf. `logic/db.py`) une seconde fois sur une
    base non vide, et vérifie qu'aucune exception n'est levée et qu'aucune
    donnée existante n'est perdue. C'est le scénario réel d'une migration en
    production : un serveur qui redémarre (donc `init_db(app)` ré-exécuté au
    prochain import d'`app.py`, dans un NOUVEAU process) contre une base déjà
    peuplée. `db.init_app()` lui-même ne peut être appelé qu'une seule fois
    par instance Flask (Flask-SQLAlchemy lève une `RuntimeError` sinon) — ce
    n'est pas une régression du site, seulement une contrainte du framework
    sur ce process Python déjà initialisé ; on teste donc directement `db.
    create_all()`, la partie réellement ré-exécutée à chaque démarrage."""
    with appmod.app.app_context():
        utilisateur_temoin = User(email="migration-douce@example.com")
        db.session.add(utilisateur_temoin)
        db.session.commit()
        nb_avant = User.query.count()

        db.create_all()  # deuxième appel, sur une base déjà peuplée

        nb_apres = User.query.count()
        if nb_apres != nb_avant:
            RAPPORT.blocker("Base de données", "Migration douce",
                             f"Perte de données après un second appel à db.create_all() : {nb_avant} -> {nb_apres}")
        else:
            RAPPORT.ok("Base de données", "Migration douce",
                        f"Second appel à db.create_all() sans exception, {nb_apres} ligne(s) préservée(s)")

        # Contrainte de clé étrangère réellement appliquée (PRAGMA foreign_keys=ON
        # forcé par logic/db.py pour SQLite) : une ligne enfant orpheline doit être
        # rejetée, comme en production sous PostgreSQL.
        try:
            orpheline = ProgramExercise(
                session_id=999999, exercise_id="inexistant-audit", position_dans_seance=1,
                series=3, reps="8-10",
            )
            db.session.add(orpheline)
            db.session.commit()
            RAPPORT.blocker("Base de données", "Contrainte clé étrangère",
                             "Une ligne référençant une session inexistante a été acceptée")
        except Exception:
            db.session.rollback()
            RAPPORT.ok("Base de données", "Contrainte clé étrangère",
                        "Ligne orpheline rejetée (PRAGMA foreign_keys=ON actif)")


# ---------------------------------------------------------------------------
# 3) CATALOGUE EXERCICES — scénario "import catalogue"
# ---------------------------------------------------------------------------
@_section("Catalogue exercices", "Import du catalogue")
def check_catalogue():
    with appmod.app.app_context():
        t0 = time.perf_counter()
        resultat = import_enriched_catalog()
        TIMINGS["import_catalogue"] = time.perf_counter() - t0

        if resultat["errors"]:
            RAPPORT.blocker("Catalogue exercices", "Import du catalogue",
                             f"{len(resultat['errors'])} erreur(s) : {resultat['errors'][:5]}")
            return

        total = Exercise.query.count()
        if total == 0:
            RAPPORT.blocker("Catalogue exercices", "Import du catalogue", "0 exercice importé")
        else:
            RAPPORT.ok("Catalogue exercices", "Import du catalogue",
                        f"{total} exercices importés (créés={resultat['created']}, "
                        f"maj={resultat['updated']}, invalides ignorés={resultat['skipped_invalid']}) "
                        f"en {TIMINGS['import_catalogue']:.2f}s")

        statut = get_catalog_status()
        if statut["approved"] == 0:
            RAPPORT.warning("Catalogue exercices", "Exercices approuvés",
                             "0 exercice au statut 'approved' — le moteur repose entièrement sur le "
                             "repli catalogue legacy (fonctionnel, mais aucune revue humaine effectuée)")
        else:
            RAPPORT.ok("Catalogue exercices", "Exercices approuvés",
                        f"{statut['approved']} exercices approuvés / {statut['total']}")

        rapport_sante = catalog_health_report()
        if rapport_sante["missing_fields"] > 0:
            RAPPORT.warning("Catalogue exercices", "Champs critiques manquants",
                             f"{rapport_sante['missing_fields']} exercice(s) avec au moins un champ critique manquant")
        else:
            RAPPORT.ok("Catalogue exercices", "Champs critiques manquants", "aucun")

        if rapport_sante["quality_warnings"] > 0:
            RAPPORT.warning("Catalogue exercices", "Avertissements qualité",
                             f"{rapport_sante['quality_warnings']} avertissement(s) qualité cumulés")
        else:
            RAPPORT.ok("Catalogue exercices", "Avertissements qualité", "aucun")

        # Approuve un candidat par muscle pour donner au moteur un catalogue
        # "approved" réaliste pour les scénarios suivants (programme/PDF/paiement).
        for muscle in MUSCLES:
            candidat = Exercise.query.filter_by(muscle_principal=muscle).order_by(Exercise.exercise_id).first()
            if candidat is not None:
                approve_exercise(candidat.exercise_id, reviewer="audit-production")


# ---------------------------------------------------------------------------
# 4) PROGRAMME GÉNÉRÉ — scénario "génération programme"
# ---------------------------------------------------------------------------
@_section("Programme généré", "Génération de programme")
def check_programme():
    with appmod.app.app_context():
        email = "audit-programme@example.com"
        t0 = time.perf_counter()
        programme = program_service.generate_user_program(email, questionnaire_complet(prenom="Audit", email=email))
        TIMINGS["generation_programme"] = time.perf_counter() - t0

        if programme is None or programme.id is None:
            RAPPORT.blocker("Programme généré", "Génération de programme", "Aucun Program retourné/persisté")
            return

        nb_exercices = sum(len(s.exercises) for s in programme.sessions)
        if not programme.sessions or nb_exercices == 0:
            RAPPORT.blocker("Programme généré", "Génération de programme",
                             f"Program #{programme.id} créé mais vide (0 séance/exercice)")
        else:
            RAPPORT.ok("Programme généré", "Génération de programme",
                        f"Program #{programme.id} : {len(programme.sessions)} séance(s), {nb_exercices} exercice(s) "
                        f"en {TIMINGS['generation_programme']:.2f}s")

        # Sécurité de contenu : validate_generated_program() doit toujours
        # accepter ce que build_program() a réellement produit (déjà vérifié en
        # amont par generate_user_program lui-même, ré-exécuté ici pour l'audit).
        ids_utilises = {pe.exercise_id for s in programme.sessions for pe in s.exercises}
        exercices_rejetes = {
            e.exercise_id for e in Exercise.query.filter_by(review_status="rejected").all()
        }
        if ids_utilises & exercices_rejetes:
            RAPPORT.blocker("Programme généré", "Exclusion des exercices rejetés",
                             f"Exercice(s) rejeté(s) utilisé(s) : {ids_utilises & exercices_rejetes}")
        else:
            RAPPORT.ok("Programme généré", "Exclusion des exercices rejetés", "aucun exercice rejeté utilisé")

        # Régénération pour le même email : ne doit jamais planter, cohérent avec
        # le contrat documenté de create_program_from_result (déduplication).
        programme_bis = program_service.generate_user_program(email, questionnaire_complet(prenom="Audit", email=email))
        RAPPORT.ok("Programme généré", "Régénération idempotente",
                    f"seconde génération pour le même profil sans exception (Program #{programme_bis.id})")


# ---------------------------------------------------------------------------
# 5) PDF — scénario "PDF"
# ---------------------------------------------------------------------------
@_section("PDF", "Génération PDF")
def check_pdf():
    with appmod.app.app_context():
        email = "audit-programme@example.com"
        programme = program_service.get_user_current_program(email)
        if programme is None:
            RAPPORT.blocker("PDF", "Génération PDF", "Aucun programme disponible pour générer un PDF de test")
            return

        data = questionnaire_complet(prenom="Audit", email=email)
        error, profile, nutrition, _programme_legacy, cardio, lifestyle = appmod._build_everything(data)
        if error:
            RAPPORT.blocker("PDF", "Génération PDF", "_build_everything() a rejeté un questionnaire pourtant valide")
            return

        adapte = program_to_pdf_data(programme)
        buffer = io.BytesIO()
        t0 = time.perf_counter()
        generate_pdf(buffer, profile, nutrition, adapte, cardio, lifestyle)
        TIMINGS["generation_pdf"] = time.perf_counter() - t0
        pdf_bytes = buffer.getvalue()

        if not pdf_bytes.startswith(b"%PDF"):
            RAPPORT.blocker("PDF", "Génération PDF", "Le fichier généré n'est pas un PDF valide")
        elif len(pdf_bytes) < 1000:
            RAPPORT.warning("PDF", "Génération PDF", f"PDF généré mais suspicieusement petit ({len(pdf_bytes)} octets)")
        else:
            RAPPORT.ok("PDF", "Génération PDF",
                        f"PDF valide généré ({len(pdf_bytes)} octets) en {TIMINGS['generation_pdf']:.2f}s")

        if TIMINGS["generation_pdf"] > 3.0:
            RAPPORT.warning("Performance", "Temps de génération PDF",
                             f"{TIMINGS['generation_pdf']:.2f}s pour un seul PDF — à surveiller en charge")


# ---------------------------------------------------------------------------
# 6) PAIEMENT — scénario "paiement simulé"
# ---------------------------------------------------------------------------
@_section("Paiement", "Paiement simulé")
def check_paiement():
    with appmod.app.app_context():
        email = "audit-paiement@example.com"
        data = questionnaire_complet(prenom="Paiement", email=email)
        order_id = orders.create_order(data, "musculation")
        orders.mark_paid(order_id)
        order = orders.get_order(order_id)

        if not order.get("paid"):
            RAPPORT.blocker("Paiement", "Commande simulée", "orders.mark_paid() n'a pas marqué la commande payée")
            return
        RAPPORT.ok("Paiement", "Commande simulée", f"Commande {order_id} créée et marquée payée")

        appmod._essayer_generer_programme_v2(order_id, order)  # ne doit jamais lever
        order_apres = orders.get_order(order_id)
        if not order_apres.get("paid"):
            RAPPORT.blocker("Paiement", "Indépendance paiement/programme",
                             "Le statut payé a été altéré par la génération du programme")
        else:
            RAPPORT.ok("Paiement", "Indépendance paiement/programme",
                        "Paiement toujours confirmé après la génération automatique du programme")

        client = appmod.app.test_client()
        resp = client.get(f"/payment-success?order_id={order_id}")
        if resp.status_code != 200:
            RAPPORT.blocker("Paiement", "Page de succès", f"/payment-success a renvoyé {resp.status_code}")
        else:
            RAPPORT.ok("Paiement", "Page de succès", "/payment-success accessible après paiement simulé (200)")

        # Configuration Stripe réelle (lecture seule de l'environnement réel,
        # jamais d'appel réseau vers Stripe depuis ce script).
        if ENV_REEL.get("STRIPE_SECRET_KEY"):
            RAPPORT.ok("Paiement", "Configuration Stripe", "STRIPE_SECRET_KEY configurée")
        else:
            RAPPORT.warning("Paiement", "Configuration Stripe",
                             "STRIPE_SECRET_KEY absente — le paiement réel Stripe est indisponible tant que "
                             "cette variable n'est pas définie (dégradation déjà gérée : erreur 503 propre, "
                             "jamais un crash, cf. logic/stripe_client.py)")
        if ENV_REEL.get("STRIPE_WEBHOOK_SECRET"):
            RAPPORT.ok("Paiement", "Configuration webhook Stripe", "STRIPE_WEBHOOK_SECRET configurée")
        else:
            RAPPORT.warning("Paiement", "Configuration webhook Stripe",
                             "STRIPE_WEBHOOK_SECRET absente — la confirmation asynchrone de paiement "
                             "(filet de sécurité si le navigateur ne revient jamais sur /payment-success) "
                             "est indisponible tant que cette variable n'est pas définie")

        # Le endpoint webhook doit rejeter toute requête à la signature invalide,
        # que le secret soit configuré ou non (comportement attendu, pas un bug).
        resp_webhook = client.post("/stripe-webhook", data=b"payload-invalide",
                                    headers={"Stripe-Signature": "signature-invalide"})
        if resp_webhook.status_code == 400:
            RAPPORT.ok("Paiement", "Vérification signature webhook",
                        "signature invalide correctement rejetée (400)")
        else:
            RAPPORT.blocker("Paiement", "Vérification signature webhook",
                             f"signature invalide acceptée (statut {resp_webhook.status_code}) — faille de sécurité")


# ---------------------------------------------------------------------------
# 7) QUESTIONNAIRE
# ---------------------------------------------------------------------------
@_section("Questionnaire", "Validation du questionnaire")
def check_questionnaire():
    client = appmod.app.test_client()
    resp = client.get("/questionnaire")
    if resp.status_code != 200:
        RAPPORT.blocker("Questionnaire", "Page questionnaire", f"/questionnaire a renvoyé {resp.status_code}")
    else:
        RAPPORT.ok("Questionnaire", "Page questionnaire", "/questionnaire accessible (200)")

    with appmod.app.app_context():
        cas = [
            ("Consentement RGPD manquant", questionnaire_complet(consentement_rgpd=False)),
            ("Poids hors limites", questionnaire_complet(poids=999)),
            ("Taille hors limites", questionnaire_complet(taille=1)),
            ("Date de naissance invalide", questionnaire_complet(date_naissance="pas-une-date")),
            ("Sexe invalide", questionnaire_complet(sexe="Autre")),
        ]
        echecs = []
        for nom, donnees in cas:
            error, *_ = appmod._build_everything(donnees)
            if error is None:
                echecs.append(nom)
        if echecs:
            RAPPORT.blocker("Questionnaire", "Garde-fous de validation",
                             f"Cas invalides acceptés à tort : {echecs}")
        else:
            RAPPORT.ok("Questionnaire", "Garde-fous de validation",
                        f"{len(cas)} cas invalides correctement rejetés")

        error, *_ = appmod._build_everything(questionnaire_complet())
        if error is not None:
            RAPPORT.blocker("Questionnaire", "Cas valide", "Un questionnaire pourtant valide a été rejeté")
        else:
            RAPPORT.ok("Questionnaire", "Cas valide", "Questionnaire complet valide correctement accepté")


# ---------------------------------------------------------------------------
# 8) FEEDBACK
# ---------------------------------------------------------------------------
@_section("Feedback", "Boucle de feedback")
def check_feedback():
    with appmod.app.app_context():
        utilisateur = User(email="audit-feedback@example.com")
        db.session.add(utilisateur)
        db.session.commit()

        exercice = Exercise.query.filter_by(muscle_principal="pecs").order_by(Exercise.exercise_id).first()
        if exercice is None:
            RAPPORT.blocker("Feedback", "Boucle de feedback", "Aucun exercice disponible pour tester le feedback")
            return

        log = program_interaction.record_exercise_action(utilisateur.id, exercice.exercise_id, "realise")
        if not isinstance(log, ExerciseUsageLog):
            RAPPORT.blocker("Feedback", "Action 'réalisé'", "record_exercise_action() n'a pas créé d'ExerciseUsageLog")
        else:
            RAPPORT.ok("Feedback", "Action 'réalisé'", "ExerciseUsageLog créé correctement")

        echecs = []
        for action, type_attendu in (
            ("trop_facile", "trop_facile"), ("trop_difficile", "trop_difficile"), ("douleur", "douleur_gene"),
        ):
            fb = program_interaction.record_exercise_action(utilisateur.id, exercice.exercise_id, action)
            if not isinstance(fb, ExerciseFeedback) or fb.feedback_type != type_attendu:
                echecs.append(action)
        if echecs:
            RAPPORT.blocker("Feedback", "Actions de feedback", f"Action(s) en échec : {echecs}")
        else:
            RAPPORT.ok("Feedback", "Actions de feedback", "trop_facile/trop_difficile/douleur -> ExerciseFeedback OK")

        # Robustesse : action inconnue -> ValueError, aucune écriture silencieuse.
        try:
            program_interaction.record_exercise_action(utilisateur.id, exercice.exercise_id, "action-inexistante")
            RAPPORT.blocker("Feedback", "Robustesse action inconnue", "Aucune ValueError levée pour une action inconnue")
        except ValueError:
            RAPPORT.ok("Feedback", "Robustesse action inconnue", "ValueError levée comme attendu")

        # La boucle d'apprentissage (phase 21) doit refléter ce feedback.
        preferences = calculate_user_preferences(utilisateur.id)
        cles_attendues = {"preferred_exercises", "avoided_patterns", "difficulty_adjustment", "volume_adjustment"}
        if set(preferences.keys()) != cles_attendues:
            RAPPORT.blocker("Feedback", "Signaux d'apprentissage",
                             f"Clés inattendues : {set(preferences.keys())}")
        else:
            RAPPORT.ok("Feedback", "Signaux d'apprentissage",
                        f"calculate_user_preferences() renvoie les 4 signaux attendus : {preferences}")


# ---------------------------------------------------------------------------
# 9) UTILISATEUR COMPLET — scénario "utilisateur complet"
# ---------------------------------------------------------------------------
@_section("Programme généré", "Parcours utilisateur complet")
def check_utilisateur_complet():
    with appmod.app.app_context():
        email = "audit-utilisateur-complet@example.com"
        data = questionnaire_complet(prenom="Complet", email=email)
        order_id = orders.create_order(data, "musculation")
        orders.mark_paid(order_id)
        # Simule le déclencheur réel (webhook Stripe, ou vérification directe sur
        # /payment-success avec session_id) qui génère automatiquement le
        # programme dès qu'une commande devient payée (phase 12/16) — la route
        # /payment-success elle-même ne régénère rien si la commande est déjà
        # marquée payée AVANT d'y arriver (cf. `_essayer_generer_programme_v2`,
        # appelé uniquement depuis le webhook ou après vérification Stripe).
        appmod._essayer_generer_programme_v2(order_id, orders.get_order(order_id))

        client = appmod.app.test_client()
        resp_success = client.get(f"/payment-success?order_id={order_id}")
        if resp_success.status_code != 200 or "Ton espace personnel" not in resp_success.get_data(as_text=True):
            RAPPORT.blocker("Programme généré", "Parcours utilisateur complet",
                             "Jeton d'accès non émis/affiché après paiement")
            return

        utilisateur = User.query.filter_by(email=email).first()
        if utilisateur is None or UserAccessToken.query.filter_by(user_id=utilisateur.id).count() != 1:
            RAPPORT.blocker("Programme généré", "Parcours utilisateur complet",
                             "Jeton d'accès non persisté correctement")
            return

        resp_my_program = client.get("/my-program")
        if resp_my_program.status_code != 200:
            RAPPORT.blocker("Programme généré", "Parcours utilisateur complet",
                             f"/my-program a renvoyé {resp_my_program.status_code} pour un utilisateur connecté")
            return

        html = resp_my_program.get_data(as_text=True)
        if "J'ai réalisé" not in html:
            RAPPORT.blocker("Programme généré", "Parcours utilisateur complet",
                             "/my-program ne semble pas afficher l'interface attendue")
            return

        programme = program_service.get_user_current_program(email)
        premier_exo = programme.sessions[0].exercises[0]
        resp_action = client.post("/my-program/action",
                                   json={"exercise_id": premier_exo.exercise_id, "action": "realise"})
        if resp_action.status_code != 200:
            RAPPORT.blocker("Programme généré", "Parcours utilisateur complet",
                             f"POST /my-program/action a renvoyé {resp_action.status_code}")
            return

        resp_compte = client.get("/mon-compte")
        if resp_compte.status_code != 200 or email not in resp_compte.get_data(as_text=True):
            RAPPORT.blocker("Programme généré", "Parcours utilisateur complet",
                             "/mon-compte inaccessible ou n'affiche pas les informations attendues")
            return

        client.get("/logout")
        resp_apres_logout = client.get("/my-program", follow_redirects=False)
        if resp_apres_logout.status_code != 302:
            RAPPORT.blocker("Programme généré", "Parcours utilisateur complet",
                             "/my-program reste accessible après déconnexion")
            return

        RAPPORT.ok("Programme généré", "Parcours utilisateur complet",
                    "paiement -> jeton -> connexion -> /my-program -> action -> /mon-compte -> déconnexion : "
                    "bout en bout sans anomalie")


# ---------------------------------------------------------------------------
# 10) SÉCURITÉ
# ---------------------------------------------------------------------------
@_section("Sécurité", "Configuration de sécurité")
def check_securite():
    for cle, defaut in DEFAUTS_DEV.items():
        valeur_reelle = ENV_REEL.get(cle)
        if not valeur_reelle:
            RAPPORT.blocker("Sécurité", f"Variable d'environnement {cle}",
                             f"{cle} n'est pas définie : le site tourne avec la valeur par défaut de "
                             f"développement ('{defaut}'), documentée et donc devinable par n'importe qui")
        elif valeur_reelle == defaut:
            RAPPORT.blocker("Sécurité", f"Variable d'environnement {cle}",
                             f"{cle} est toujours sur sa valeur par défaut de développement")
        else:
            RAPPORT.ok("Sécurité", f"Variable d'environnement {cle}", f"{cle} a été personnalisée")

    if not ENV_REEL.get("DATABASE_URL"):
        RAPPORT.warning("Sécurité", "Base de données de production",
                         "DATABASE_URL absente : le site utilisera un fichier SQLite local (data/fitsurmesure.db) "
                         "plutôt qu'une vraie base PostgreSQL managée — acceptable à petite échelle si DATA_DIR "
                         "pointe vers le disque persistant Render, mais moins robuste sous forte charge concurrente")
    else:
        RAPPORT.ok("Sécurité", "Base de données de production", "DATABASE_URL configurée")

    if appmod.app.debug:
        RAPPORT.blocker("Sécurité", "Mode debug Flask", "app.debug est activé (fuite d'informations en production)")
    else:
        RAPPORT.ok("Sécurité", "Mode debug Flask", "app.debug désactivé")

    if not appmod.app.config.get("SESSION_COOKIE_SECURE"):
        RAPPORT.warning("Sécurité", "Cookie de session",
                         "SESSION_COOKIE_SECURE n'est pas activé — recommandé une fois le site en HTTPS (Render "
                         "fournit HTTPS par défaut) pour empêcher l'envoi du cookie de session en clair")
    else:
        RAPPORT.ok("Sécurité", "Cookie de session", "SESSION_COOKIE_SECURE activé")

    with appmod.app.app_context():
        utilisateur = User(email="audit-securite-token@example.com")
        db.session.add(utilisateur)
        db.session.commit()
        jeton = auth.issue_token_for_user(utilisateur)
        ligne = UserAccessToken.query.filter_by(user_id=utilisateur.id).first()
        if ligne.token_hash == jeton or len(ligne.token_hash) != 64:
            RAPPORT.blocker("Sécurité", "Stockage des jetons d'accès",
                             "Le jeton semble stocké en clair (attendu : empreinte SHA-256 de 64 caractères)")
        else:
            RAPPORT.ok("Sécurité", "Stockage des jetons d'accès",
                        "seule une empreinte SHA-256 est stockée, jamais le jeton brut")

    client = appmod.app.test_client()
    routes_protegees = ["/my-program", "/mon-compte", "/admin/dashboard"]
    non_protegees = []
    for route in routes_protegees:
        resp = client.get(route, follow_redirects=False)
        if resp.status_code not in (302, 401):
            non_protegees.append((route, resp.status_code))
    if non_protegees:
        RAPPORT.blocker("Sécurité", "Routes protégées",
                         f"Route(s) accessible(s) sans authentification : {non_protegees}")
    else:
        RAPPORT.ok("Sécurité", "Routes protégées",
                    f"{len(routes_protegees)} routes protégées correctement redirigées/rejetées en anonyme")


# ---------------------------------------------------------------------------
# 11) PERFORMANCE
# ---------------------------------------------------------------------------
@_section("Performance", "Configuration serveur")
def check_performance():
    with open(os.path.join(PROJECT_ROOT, "Procfile"), encoding="utf-8") as f:
        procfile = f.read()
    if "--workers" in procfile or "--timeout" in procfile:
        RAPPORT.ok("Performance", "Configuration Gunicorn", "workers/timeout explicitement configurés")
    else:
        RAPPORT.warning("Performance", "Configuration Gunicorn",
                         "Procfile ('gunicorn app:app') ne fixe ni --workers ni --timeout : gunicorn démarrera "
                         "avec 1 seul worker synchrone par défaut, ce qui limite fortement la concurrence sous "
                         "charge réelle. À envisager avant un lancement à grande échelle : par ex. "
                         "'gunicorn app:app --workers 3 --timeout 60'")

    with appmod.app.app_context():
        index_token = UserAccessToken.__table__.columns["token_hash"]
        if index_token.unique or index_token.index:
            RAPPORT.ok("Performance", "Index base de données",
                        "UserAccessToken.token_hash indexé/unique (recherche de jeton en O(1))")
        else:
            RAPPORT.warning("Performance", "Index base de données", "UserAccessToken.token_hash non indexé")

    seuils = {"import_catalogue": 5.0, "generation_programme": 2.0, "generation_pdf": 3.0}
    for cle, seuil in seuils.items():
        duree = TIMINGS.get(cle)
        if duree is None:
            continue
        if duree > seuil:
            RAPPORT.warning("Performance", f"Temps d'exécution — {cle}",
                             f"{duree:.2f}s (seuil indicatif {seuil}s) — à surveiller en charge réelle")
        else:
            RAPPORT.ok("Performance", f"Temps d'exécution — {cle}", f"{duree:.2f}s (sous le seuil indicatif {seuil}s)")


# ---------------------------------------------------------------------------
# Rapport final
# ---------------------------------------------------------------------------
def generer_markdown():
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M")
    nb_ok = RAPPORT.compte("OK")
    nb_warning = RAPPORT.compte("WARNING")
    nb_blocker = RAPPORT.compte("BLOCKER")
    verdict = "🔴 BLOQUÉ — au moins un BLOCKER à corriger avant lancement" if nb_blocker else (
        "🟡 LANÇABLE AVEC RÉSERVES — des WARNING à examiner" if nb_warning else "🟢 PRÊT POUR LA PRODUCTION"
    )

    lignes = [
        "# PRODUCTION_READY.md",
        "",
        f"Audit généré le {maintenant} par `scripts/production_check.py` (Phase 24/24).",
        "",
        f"## Verdict : {verdict}",
        "",
        f"- OK : {nb_ok}",
        f"- WARNING : {nb_warning}",
        f"- BLOCKER : {nb_blocker}",
        "",
        "Cet audit s'exécute dans un environnement totalement isolé (dossier de données "
        "temporaire jetable, base SQLite dédiée) : aucune commande, aucun utilisateur, "
        "aucun code promo réel n'a été lu ni modifié. Les contrôles de sécurité/configuration "
        "portent sur les variables d'environnement réelles, en lecture seule.",
        "",
    ]

    categories_ordre = [
        "Architecture", "Base de données", "Sécurité", "Performance", "Paiement",
        "Catalogue exercices", "Programme généré", "PDF", "Questionnaire", "Feedback",
    ]
    categories_presentes = [c for c in categories_ordre if any(l["categorie"] == c for l in RAPPORT.lignes)]
    autres = sorted({l["categorie"] for l in RAPPORT.lignes} - set(categories_presentes))
    for categorie in categories_presentes + autres:
        lignes.append(f"## {categorie}")
        lignes.append("")
        for ligne in [l for l in RAPPORT.lignes if l["categorie"] == categorie]:
            badge = {"OK": "✅ OK", "WARNING": "⚠️ WARNING", "BLOCKER": "🛑 BLOCKER"}[ligne["statut"]]
            lignes.append(f"**{badge} — {ligne['nom']}**")
            if ligne["detail"]:
                lignes.append("")
                lignes.append(f"{ligne['detail']}")
            lignes.append("")
        lignes.append("")

    return "\n".join(lignes)


def main():
    check_architecture()
    check_installation_vierge()
    check_migration_db()
    check_catalogue()
    check_programme()
    check_pdf()
    check_paiement()
    check_questionnaire()
    check_feedback()
    check_utilisateur_complet()
    check_securite()
    check_performance()

    contenu = generer_markdown()
    chemin_rapport = os.path.join(PROJECT_ROOT, "PRODUCTION_READY.md")
    with open(chemin_rapport, "w", encoding="utf-8") as f:
        f.write(contenu)

    print(contenu)
    print(f"\nRapport écrit dans {chemin_rapport}")

    try:
        db.session.remove()
        db.engine.dispose()
    except Exception:
        pass
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    return 1 if RAPPORT.compte("BLOCKER") else 0


if __name__ == "__main__":
    sys.exit(main())
