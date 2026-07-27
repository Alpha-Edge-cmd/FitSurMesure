# -*- coding: utf-8 -*-
"""
Modèles de données FitSurMesure V2.

Phase 1/16 (fondations) a créé : User -> ProfileSnapshot -> Program ->
ProgramSession -> ProgramExercise.

Phase 2/16 (ce fichier, mis à jour) ajoute : Exercise — le catalogue
d'exercices en base, conforme à architecture_base_exercices.md et au
sous-ensemble de champs "critique" retenu pour cette phase (cf. explication
donnée à l'utilisateur, qui reprend la recommandation de l'audit de ne pas
tout remplir d'un coup — audit_final_coherence_v2.md, point 4a).
`ProgramExercise.exercise_id` devient une vraie ForeignKey vers
`Exercise.exercise_id`, comme anticipé dès la phase 1.

Volontairement absents de cette phase (phases suivantes) :
  - ExerciseUsageLog / ExerciseFeedback : phase 5 (historique/feedback).
  - CardioUsageLog / CardioFeedback : idem, côté cardio.
  - Le remplissage réel des ~110 exercices existants : migration séparée,
    non exécutée ici (voir logic/exercise_migration.py).
"""
from datetime import datetime

from logic.db import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    prenom = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    profile_snapshots = db.relationship(
        "ProfileSnapshot", back_populates="user", cascade="all, delete-orphan"
    )
    programs = db.relationship(
        "Program", back_populates="user", cascade="all, delete-orphan"
    )
    # Phase 10/16 : historique d'utilisation + feedback exercice, jusqu'ici
    # de simples interfaces stub côté moteur (selector.py, phase 7).
    exercise_usage_logs = db.relationship(
        "ExerciseUsageLog", back_populates="user", cascade="all, delete-orphan"
    )
    exercise_feedbacks = db.relationship(
        "ExerciseFeedback", back_populates="user", cascade="all, delete-orphan"
    )
    # Phase 22/24 : authentification (cf. logic/auth.py) — au plus une ligne
    # par utilisateur (uselist=False), jamais consultée directement ailleurs
    # que dans logic/auth.py (encapsulation volontaire, cf. docstring de ce
    # module).
    access_token = db.relationship(
        "UserAccessToken", back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self):
        return f"<User id={self.id} email={self.email!r}>"


class ProfileSnapshot(db.Model):
    """Une ligne par génération de programme, jamais écrasée (cf. audit :
    l'ancien système traite chaque commande comme isolée, ce qui empêche
    toute évolution de profil dans le temps)."""

    __tablename__ = "profile_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Champs "cœur", assez stables pour justifier une vraie colonne (utiles pour
    # filtrer/interroger directement en base sans désérialiser le JSON).
    poids = db.Column(db.Float, nullable=False)
    taille = db.Column(db.Float, nullable=False)
    sexe = db.Column(db.String(20), nullable=False)
    niveau_musculation = db.Column(db.String(50), nullable=False)
    objectif_principal = db.Column(db.String(80), nullable=False)
    objectif_secondaire = db.Column(db.String(80), nullable=True)
    composition_corporelle = db.Column(db.String(50), nullable=True)

    # --- Variables moteur (phase 4/16) ---------------------------------------
    # Décision validée (questionnaire_optimise.md / resolution_11_points_
    # bloquants.md) : les variables nommées et déjà dotées d'une règle stable
    # (formules de scoring, seuils, valeurs neutres) deviennent des colonnes
    # dédiées — lues en boucle serrée par le futur moteur, leur forme est
    # figée. Tout le reste (questions non encore formalisées, champs
    # nutrition annexes, etc.) continue de vivre dans `variables_json`.
    exercices_maitrises = db.Column(db.JSON, nullable=False, default=list)
    mobilite_generale = db.Column(db.Integer, nullable=True)  # 1-5
    amplitude_squat = db.Column(db.String(30), nullable=True)
    amplitude_epaule = db.Column(db.String(30), nullable=True)
    tolerance_technique = db.Column(db.Integer, nullable=True)  # 1-5
    preference_style_charge = db.Column(db.String(50), nullable=True)
    preference_materiel = db.Column(db.String(30), nullable=True)
    # Regroupe longueur_bras/longueur_jambes (existants) + longueur_buste/
    # largeur_epaules (futurs, questionnaire_optimise.md catégorie 2) : ces
    # 4 traits sont toujours lus ensemble par le facteur morphologie, une
    # seule colonne JSON dédiée plutôt que 4 colonnes séparées.
    morphologie_declaree = db.Column(db.JSON, nullable=False, default=dict)
    # {zone: sévérité} — zone présente seulement si déclarée par l'utilisateur
    # (cf. resolution_11_points_bloquants.md #6, aucun effet si absente).
    blessures = db.Column(db.JSON, nullable=False, default=dict)
    # {pratique: bool, type: str|None, frequence: str|None}
    autres_sports = db.Column(db.JSON, nullable=False, default=dict)
    disponibilite_reelle = db.Column(db.String(30), nullable=True)
    sommeil = db.Column(db.String(30), nullable=True)
    stress = db.Column(db.String(30), nullable=True)

    # Toutes les autres variables du questionnaire (actuel ET futures questions
    # non encore nommées explicitement ci-dessus) sont stockées ici, plutôt
    # qu'en colonnes dédiées une par une. Choix délibéré : le questionnaire va
    # continuer à évoluer sur plusieurs phases, et une colonne par variable
    # obligerait à une migration de schéma à chaque ajout de question.
    variables_json = db.Column(db.JSON, nullable=False, default=dict)

    user = db.relationship("User", back_populates="profile_snapshots")
    programs = db.relationship("Program", back_populates="profile_snapshot")

    def __repr__(self):
        return f"<ProfileSnapshot id={self.id} user_id={self.user_id}>"


class Program(db.Model):
    __tablename__ = "programs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    profile_snapshot_id = db.Column(
        db.Integer, db.ForeignKey("profile_snapshots.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    formule = db.Column(db.String(50), nullable=False)
    split = db.Column(db.String(50), nullable=True)
    # 'achat_initial' | 'regeneration' | 'renouvellement' (cf. architecture_v2_consolidation.md)
    origine = db.Column(db.String(30), nullable=False, default="achat_initial")

    # Lien optionnel vers la commande legacy (logic/orders.py, stockage JSON),
    # à conserver tant que la transition vers cette nouvelle couche n'est pas
    # terminée (cf. risque "compatibilité avec les anciens achats", déjà
    # identifié et tranché dans resolution_11_points_bloquants.md).
    order_id = db.Column(db.String(64), nullable=True, index=True)

    # Phase 11/16 : identifiant de génération (hash de contenu, cf.
    # logic/program_repository.py._compute_generation_id — pas un UUID
    # aléatoire, précisément pour qu'une régénération strictement identique
    # produise le même identifiant et soit détectée comme un doublon plutôt
    # que créée une seconde fois). Nullable : les Program créés avant cette
    # phase (migration legacy, phase 3) n'en ont pas et restent valides ;
    # `unique=True` autorise plusieurs valeurs NULL (SQLite/PostgreSQL) sans
    # bloquer ces anciennes lignes.
    generation_id = db.Column(db.String(64), nullable=True, unique=True, index=True)

    user = db.relationship("User", back_populates="programs")
    profile_snapshot = db.relationship("ProfileSnapshot", back_populates="programs")
    sessions = db.relationship(
        "ProgramSession",
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="ProgramSession.ordre_dans_semaine",
    )
    # Phase 10/16 : un Program supprimé emporte son historique d'utilisation
    # associé (cohérent avec le reste des cascades de ce modèle).
    exercise_usage_logs = db.relationship(
        "ExerciseUsageLog", back_populates="program", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Program id={self.id} formule={self.formule!r}>"


class ProgramSession(db.Model):
    __tablename__ = "program_sessions"

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("programs.id"), nullable=False, index=True)

    nom_seance = db.Column(db.String(80), nullable=False)
    # Liste de muscles (ex: ["pectoraux", "triceps"]) — JSON plutôt qu'une table
    # à part, ce sous-ensemble ne justifie pas encore sa propre entité.
    muscles_concernes = db.Column(db.JSON, nullable=False, default=list)
    ordre_dans_semaine = db.Column(db.Integer, nullable=True)
    # Phase 12/16 : durée estimée (minutes), calculée par workout_generator.py
    # (phase 8) mais jusqu'ici jamais persistée par program_repository.py
    # (phase 11) — nécessaire pour que l'adaptateur PDF (pdf_program_adapter.py)
    # puisse fournir `duree_estimee_min`, lu directement par pdf_generator.py.
    # Nullable : les Program créés avant cette phase n'en ont pas.
    duree_estimee_minutes = db.Column(db.Integer, nullable=True)

    program = db.relationship("Program", back_populates="sessions")
    exercises = db.relationship(
        "ProgramExercise",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ProgramExercise.position_dans_seance",
    )

    def __repr__(self):
        return f"<ProgramSession id={self.id} nom={self.nom_seance!r}>"


class ProgramExercise(db.Model):
    __tablename__ = "program_exercises"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("program_sessions.id"), nullable=False, index=True
    )

    # Depuis la phase 2, `Exercise` existe : `exercise_id` est désormais une
    # vraie clé étrangère (c'était un simple champ texte en phase 1, en
    # attendant que la table existe — cf. historique dans le commit de la
    # phase 1). Type inchangé (String(64)) pour ne rien casser.
    exercise_id = db.Column(
        db.String(64), db.ForeignKey("exercises.exercise_id"), nullable=False, index=True
    )

    position_dans_seance = db.Column(db.Integer, nullable=False)
    series = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.String(20), nullable=False)
    # Facultatif tant que la prescription de charge (phase 7) n'est pas active.
    charge_prescrite = db.Column(db.Float, nullable=True)
    # Phase 12/16 : la prescription (phase 9, generate_prescription) produit déjà
    # rest_seconds/intensity/notes par exercice, mais program_repository.py
    # (phase 11) ne les persistait pas encore. Nécessaires pour le contrat JSON
    # de GET /my-program (rest_time) et pour compléter la prescription en base.
    # Tous nullable : les ProgramExercise créés avant cette phase n'en ont pas.
    rest_time_seconds = db.Column(db.Integer, nullable=True)
    intensity = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    session = db.relationship("ProgramSession", back_populates="exercises")
    exercise = db.relationship("Exercise", back_populates="program_exercises")

    def __repr__(self):
        return f"<ProgramExercise id={self.id} exercise_id={self.exercise_id!r}>"


class Exercise(db.Model):
    """Catalogue d'exercices (phase 2/16). Référentiel autonome : ne connaît
    aucun utilisateur, ne contient aucune règle personnelle (cf. architecture_
    v2_consolidation.md partie 2, responsabilités du composant "Base
    exercices").

    Sous-ensemble de champs volontairement limité au "critique" pour cette
    phase (identité, classification, biomécanique de base, objectifs, 2 des 7
    scores hypertrophiques) — conforme à la recommandation de l'audit de ne
    pas exiger le remplissage des 35+ champs du schéma complet de
    architecture_base_exercices.md avant un premier moteur fonctionnel. Les
    champs restants de ce schéma complet (profil_resistance, zone_etirement_
    max, zone_contraction_max, chain_type, plane_of_motion, type_articulaire,
    articulations_impliquees, progression_metric/step, tags_libres, version,
    et les 4 scores hypertrophiques restants) seront ajoutés lors d'une
    phase d'enrichissement ultérieure, sans remise en cause de cette table
    (ce sont des colonnes en plus, pas une restructuration).
    """

    __tablename__ = "exercises"

    # --- Identité ---------------------------------------------------------
    # Identifiant stable et indépendant du nom affiché (cf. audit : l'ancien
    # NAME_TO_PATTERN utilise le nom affiché comme clé, ce qui casse tout
    # renommage futur). Sert directement de clé primaire : c'est déjà un
    # identifiant unique et stable par construction, inutile d'en ajouter un
    # second (id auto-incrémenté) à côté.
    exercise_id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    family = db.Column(db.String(80), nullable=False, index=True)
    pattern = db.Column(db.String(80), nullable=False, index=True)
    movement_type = db.Column(db.String(30), nullable=True)  # push/pull/squat/hinge/lunge/carry/rotation/isometrique
    equipment = db.Column(db.JSON, nullable=False, default=list)  # liste, ex: ["barre", "banc"]

    # --- Classification -----------------------------------------------------
    muscle_principal = db.Column(db.String(50), nullable=False, index=True)
    muscles_secondaires = db.Column(db.JSON, nullable=False, default=list)
    unilateral = db.Column(db.Boolean, nullable=False, default=False)
    difficulty_level = db.Column(db.String(20), nullable=True)  # debutant/intermediaire/avance

    # --- Biomécanique ------------------------------------------------------
    joint_stress = db.Column(db.JSON, nullable=False, default=dict)  # {epaule: 0-3, genou: 0-3, ...}
    technical_complexity = db.Column(db.Integer, nullable=True)  # 1-5
    stability_demand = db.Column(db.String(20), nullable=True)  # faible/modere/eleve
    morphologie_adaptee = db.Column(db.JSON, nullable=False, default=dict)  # 9 clés, cf. resolution_11_points_bloquants.md #3

    # --- Objectifs -----------------------------------------------------------
    objectifs_adaptes = db.Column(db.JSON, nullable=False, default=dict)  # {force, hypertrophie, endurance_musculaire, perte_de_gras, explosivite}

    # --- Hypertrophie (sous-ensemble : 2 des 7 scores + le composite) ------
    score_tension_mecanique = db.Column(db.Integer, nullable=True)  # 1-10
    score_contraction_max = db.Column(db.Integer, nullable=True)  # 1-10
    # Note : la formule complète de architecture_base_exercices.md partie 3
    # combine 5 sous-scores (dont étirement_charge/surcharge_progressive/
    # stimulus_fatigue, absents de cette phase). Tant que ces 3 sous-scores
    # ne sont pas ajoutés, potentiel_hypertrophique doit être saisi à la main
    # plutôt que calculé automatiquement — voir "problèmes rencontrés".
    potentiel_hypertrophique = db.Column(db.Integer, nullable=True)  # 1-10

    # --- Autres --------------------------------------------------------------
    substitutes = db.Column(db.JSON, nullable=False, default=list)  # liste ordonnée d'exercise_id
    contre_indications = db.Column(db.JSON, nullable=False, default=list)  # cas médicaux non réductibles à joint_stress
    actif = db.Column(db.Boolean, nullable=False, default=True)  # jamais de suppression physique, seulement désactivation

    # --- Revue humaine (phase 14/16) -----------------------------------------
    # `needs_review` existait déjà comme clé éditoriale dans data/exercise_
    # enrichment.json (phase 13) mais n'était jusqu'ici PAS une colonne de ce
    # modèle (exercise_catalog_import.py ne le reportait pas en base). Ajouté
    # ici comme colonne réelle — "conserver needs_review pour compatibilité
    # avec les fichiers existants" (consigne phase 14) : même nom, même sens
    # booléen, désormais aussi persisté. Nullable=False avec default=True
    # (cohérent avec la valeur éditoriale par défaut du premier enrichissement,
    # phase 13, où toutes les fiches portent needs_review=true).
    needs_review = db.Column(db.Boolean, nullable=False, default=True)
    # pending / approved / rejected (pas de contrainte CHECK SQL, même choix
    # que ExerciseFeedback.feedback_type — validé côté application, cf.
    # logic/exercise_review.py).
    review_status = db.Column(db.String(20), nullable=False, default="pending")
    # Sert à la fois pour une note de revue libre et pour la raison d'un rejet
    # (reject_exercise) : la consigne de la phase 14 mentionne "review_reason"
    # dans la description du workflow mais "review_notes" dans la liste des
    # colonnes à ajouter — un seul champ texte couvre les deux, pas de colonne
    # dupliquée (cf. commentaire dans exercise_review.py).
    review_notes = db.Column(db.Text, nullable=True)
    validated_at = db.Column(db.DateTime, nullable=True)
    validated_by = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relation avec ProgramExercise (existe dès cette phase). Les relations
    # avec les futurs logs (ExerciseUsageLog, ExerciseFeedback — phase 5) ne
    # sont pas créées ici puisque ces tables n'existent pas encore, mais
    # `exercise_id` (clé primaire stable) est précisément ce sur quoi elles
    # s'appuieront le moment venu, sans changement sur cette table.
    program_exercises = db.relationship("ProgramExercise", back_populates="exercise")

    def __repr__(self):
        return f"<Exercise exercise_id={self.exercise_id!r} name={self.name!r}>"


class ExerciseUsageLog(db.Model):
    """Historique d'utilisation d'un exercice par un utilisateur (phase
    10/16). Alimente `logic/recommendation/history.py`, branché sur
    `selector.get_recent_exercises` pour la pénalité de récence déjà prévue
    depuis la phase 7 (jusqu'ici un stub retournant toujours []).

    Pas de relation ORM déclarée côté `Exercise` (simple FK) : cette table
    n'a besoin que du sens de lecture "un utilisateur -> ses usages", jamais
    l'inverse dans le moteur actuel — cohérent avec le principe de ne pas
    alourdir un modèle déjà testé sans besoin fonctionnel identifié."""

    __tablename__ = "exercise_usage_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    exercise_id = db.Column(db.String(64), db.ForeignKey("exercises.exercise_id"), nullable=False, index=True)
    # Nullable : un usage peut être enregistré sans Program SQLAlchemy associé
    # (ex. génération encore basée sur orders.py/JSON, non touchée par cette
    # phase — cf. Program.order_id, même logique de transition progressive).
    program_id = db.Column(db.Integer, db.ForeignKey("programs.id"), nullable=True, index=True)
    used_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User", back_populates="exercise_usage_logs")
    program = db.relationship("Program", back_populates="exercise_usage_logs")
    exercise = db.relationship("Exercise")

    def __repr__(self):
        return f"<ExerciseUsageLog user_id={self.user_id} exercise_id={self.exercise_id!r} used_at={self.used_at}>"


class ExerciseFeedback(db.Model):
    """Retour utilisateur sur un exercice précis (phase 10/16). Alimente
    `logic/recommendation/history.py` puis `logic/recommendation/feedback.py`,
    qui traduit ces signaux en ajustements moteur — jamais en contournement
    de sécurité (cf. filters.py, invariant inchangé depuis la phase 6)."""

    __tablename__ = "exercise_feedbacks"

    # Valeurs possibles de `feedback_type` (cf. consigne phase 10). Pas de
    # contrainte CHECK au niveau SQL (portabilité SQLite/PostgreSQL) :
    # validée côté application par `logic/recommendation/feedback.py`.
    FEEDBACK_TYPES = ("aime", "deteste", "douleur_gene", "trop_difficile", "trop_facile")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    exercise_id = db.Column(db.String(64), db.ForeignKey("exercises.exercise_id"), nullable=False, index=True)
    feedback_type = db.Column(db.String(20), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User", back_populates="exercise_feedbacks")
    exercise = db.relationship("Exercise")

    def __repr__(self):
        return f"<ExerciseFeedback user_id={self.user_id} exercise_id={self.exercise_id!r} type={self.feedback_type!r}>"


class UserAccessToken(db.Model):
    """Authentification utilisateur (phase 22/24) : jeton d'accès personnel,
    sans mot de passe (aucun système de mot de passe n'existait avant cette
    phase — vérifié en amont : `User` n'a jamais eu de champ credential, et
    Stripe Checkout est aujourd'hui le seul endroit qui collecte un email,
    jamais vérifié par nos soins). Table ENTIÈREMENT NOUVELLE plutôt qu'une
    colonne ajoutée à `users` : cohérent avec la "migration douce" déjà
    pratiquée aux phases 1/10 (ExerciseUsageLog/ExerciseFeedback) —
    `db.create_all()` (logic/db.py) crée les tables manquantes sans jamais
    toucher une table déjà déployée en production, contrairement à l'ajout
    d'une colonne sur une table existante qui exigerait une vraie migration
    de schéma (ALTER TABLE), hors périmètre ici.

    Ne stocke JAMAIS le jeton en clair (`token_hash`, empreinte SHA-256) :
    même en cas de fuite de la base, aucun jeton exploitable n'est exposé —
    cf. logic/auth.py, seul module autorisé à lire/écrire cette table."""

    __tablename__ = "user_access_tokens"

    id = db.Column(db.Integer, primary_key=True)
    # unique=True : au plus un jeton actif par utilisateur (en émettre un
    # nouveau remplace l'ancien, cf. logic/auth.issue_token_for_user — un
    # seul jeton compromis ne peut donc jamais coexister avec un jeton valide
    # oublié).
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="access_token")

    def __repr__(self):
        return f"<UserAccessToken user_id={self.user_id}>"
