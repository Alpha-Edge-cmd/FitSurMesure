# PRODUCTION_READY.md

Audit généré le 2026-07-28 19:58 par `scripts/production_check.py` (Phase 24/24).

## Verdict : 🔴 BLOQUÉ — au moins un BLOCKER à corriger avant lancement

- OK : 34
- WARNING : 5
- BLOCKER : 3

Cet audit s'exécute dans un environnement totalement isolé (dossier de données temporaire jetable, base SQLite dédiée) : aucune commande, aucun utilisateur, aucun code promo réel n'a été lu ni modifié. Les contrôles de sécurité/configuration portent sur les variables d'environnement réelles, en lecture seule.

## Architecture

**✅ OK — Fichiers attendus**

29 fichiers clés présents

**✅ OK — Séparation des couches**

app.py ne référence aucun module moteur/interne directement

**✅ OK — Dépendances figées**

6 dépendances, toutes avec version figée

**✅ OK — Disque persistant déclaré**

render.yaml déclare un disque persistant


## Base de données

**✅ OK — Installation vierge**

9 tables créées ; données utilisateur toutes vides, catalogue d'exercices pré-chargé (365 exercices) — dossier isolé /sessions/epic-affectionate-shannon/tmp/fitsurmesure_audit_nm7nboio

**✅ OK — Migration douce**

Second appel à db.create_all() sans exception, 1 ligne(s) préservée(s)

**✅ OK — Contrainte clé étrangère**

Ligne orpheline rejetée (PRAGMA foreign_keys=ON actif)


## Sécurité

**🛑 BLOCKER — Variable d'environnement SECRET_KEY**

SECRET_KEY n'est pas définie : le site tourne avec la valeur par défaut de développement ('fitsurmesure-cle-secrete-dev-a-changer'), documentée et donc devinable par n'importe qui

**🛑 BLOCKER — Variable d'environnement ADMIN_PASSWORD**

ADMIN_PASSWORD n'est pas définie : le site tourne avec la valeur par défaut de développement ('fitsurmesure2026'), documentée et donc devinable par n'importe qui

**🛑 BLOCKER — Variable d'environnement OWNER_ACCESS_CODE**

OWNER_ACCESS_CODE n'est pas définie : le site tourne avec la valeur par défaut de développement ('SAMY-ACCES-ILLIMITE'), documentée et donc devinable par n'importe qui

**⚠️ WARNING — Base de données de production**

DATABASE_URL absente : le site utilisera un fichier SQLite local (data/fitsurmesure.db) plutôt qu'une vraie base PostgreSQL managée — acceptable à petite échelle si DATA_DIR pointe vers le disque persistant Render, mais moins robuste sous forte charge concurrente

**✅ OK — Mode debug Flask**

app.debug désactivé

**⚠️ WARNING — Cookie de session**

SESSION_COOKIE_SECURE n'est pas activé — recommandé une fois le site en HTTPS (Render fournit HTTPS par défaut) pour empêcher l'envoi du cookie de session en clair

**✅ OK — Stockage des jetons d'accès**

seule une empreinte SHA-256 est stockée, jamais le jeton brut

**✅ OK — Routes protégées**

3 routes protégées correctement redirigées/rejetées en anonyme


## Performance

**⚠️ WARNING — Configuration Gunicorn**

Procfile ('gunicorn app:app') ne fixe ni --workers ni --timeout : gunicorn démarrera avec 1 seul worker synchrone par défaut, ce qui limite fortement la concurrence sous charge réelle. À envisager avant un lancement à grande échelle : par ex. 'gunicorn app:app --workers 3 --timeout 60'

**✅ OK — Index base de données**

UserAccessToken.token_hash indexé/unique (recherche de jeton en O(1))

**✅ OK — Temps d'exécution — import_catalogue**

0.17s (sous le seuil indicatif 5.0s)

**✅ OK — Temps d'exécution — generation_programme**

0.09s (sous le seuil indicatif 2.0s)

**✅ OK — Temps d'exécution — generation_pdf**

0.09s (sous le seuil indicatif 3.0s)


## Paiement

**✅ OK — Commande simulée**

Commande 4f6ade9e08f54b93a5ff8ad120168fdc créée et marquée payée

**✅ OK — Indépendance paiement/programme**

Paiement toujours confirmé après la génération automatique du programme

**✅ OK — Page de succès**

/payment-success accessible après paiement simulé (200)

**⚠️ WARNING — Configuration Stripe**

STRIPE_SECRET_KEY absente — le paiement réel Stripe est indisponible tant que cette variable n'est pas définie (dégradation déjà gérée : erreur 503 propre, jamais un crash, cf. logic/stripe_client.py)

**⚠️ WARNING — Configuration webhook Stripe**

STRIPE_WEBHOOK_SECRET absente — la confirmation asynchrone de paiement (filet de sécurité si le navigateur ne revient jamais sur /payment-success) est indisponible tant que cette variable n'est pas définie

**✅ OK — Vérification signature webhook**

signature invalide correctement rejetée (400)


## Catalogue exercices

**✅ OK — Import du catalogue**

365 exercices importés (créés=0, maj=365, invalides ignorés=0) en 0.17s

**✅ OK — Exercices approuvés**

365 exercices approuvés / 365

**✅ OK — Champs critiques manquants**

aucun

**✅ OK — Avertissements qualité**

aucun


## Programme généré

**✅ OK — Génération de programme**

Program #1 : 3 séance(s), 30 exercice(s) en 0.09s

**✅ OK — Exclusion des exercices rejetés**

aucun exercice rejeté utilisé

**✅ OK — Régénération idempotente**

seconde génération pour le même profil sans exception (Program #2)

**✅ OK — Parcours utilisateur complet**

paiement -> jeton -> connexion -> /my-program -> action -> /mon-compte -> déconnexion : bout en bout sans anomalie


## PDF

**✅ OK — Génération PDF**

PDF valide généré (21435 octets) en 0.09s


## Questionnaire

**✅ OK — Page questionnaire**

/questionnaire accessible (200)

**✅ OK — Garde-fous de validation**

5 cas invalides correctement rejetés

**✅ OK — Cas valide**

Questionnaire complet valide correctement accepté


## Feedback

**✅ OK — Action 'réalisé'**

ExerciseUsageLog créé correctement

**✅ OK — Actions de feedback**

trop_facile/trop_difficile/douleur -> ExerciseFeedback OK

**✅ OK — Robustesse action inconnue**

ValueError levée comme attendu

**✅ OK — Signaux d'apprentissage**

calculate_user_preferences() renvoie les 4 signaux attendus : {'preferred_exercises': [], 'avoided_patterns': ['developpe'], 'difficulty_adjustment': 0, 'volume_adjustment': -1}

