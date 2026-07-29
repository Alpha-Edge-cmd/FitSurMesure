# Mettre FitSurMesure en ligne (GitHub + Render)

Le code est déjà prêt côté technique : dépôt git initialisé avec un premier commit (dossier `data/` exclu volontairement, il ne doit jamais être versionné), `gunicorn` ajouté pour faire tourner le site en production, et le stockage (codes promo, commandes) rendu compatible avec un disque persistant. Il te reste les étapes qui nécessitent tes propres comptes — je ne peux pas les faire à ta place.

## 1. Créer un compte GitHub

Sur https://github.com/join (gratuit). Retiens bien ton nom d'utilisateur.

## 2. Créer un dépôt vide sur GitHub

Sur https://github.com/new :
- Nom du dépôt : `fitsurmesure` (ou ce que tu veux)
- Ne coche RIEN (pas de README, pas de .gitignore, pas de licence) — le dépôt doit rester vide, le code sera poussé depuis ton ordinateur.
- Clique sur "Create repository".

GitHub t'affiche une page avec des commandes : ignore-les, utilise celles ci-dessous à la place (ton code est déjà prêt localement).

## 3. Pousser le code depuis ton terminal

Dans le dossier `site` (celui où tu lances déjà `python3 app.py`) :

```bash
git remote add origin https://github.com/TON-PSEUDO/fitsurmesure.git
git push -u origin main
```

Remplace `TON-PSEUDO` par ton nom d'utilisateur GitHub. Au premier push, GitHub va te demander de t'authentifier :
- Le plus simple : installe **GitHub Desktop** (https://desktop.github.com), connecte-toi avec ton compte, et fais le push depuis son interface graphique plutôt qu'en ligne de commande.
- Ou en ligne de commande : GitHub ne demande plus ton mot de passe mais un **token d'accès personnel** (Settings → Developer settings → Personal access tokens → Generate new token, coche juste "repo"), à coller à la place du mot de passe quand `git push` te le demande.

## 4. Créer un compte Render

Sur https://render.com (le bouton "Sign up with GitHub" est pratique : ça connecte direct ton compte GitHub).

## 5. Créer le service web

Dans le dashboard Render : **New +** → **Web Service** → sélectionne ton dépôt `fitsurmesure`.

Renseigne :
- **Name** : `fitsurmesure`
- **Runtime** : Python 3
- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `gunicorn app:app`
- **Plan** : **Starter** (~7$/mois) — pas le plan gratuit, pour ne jamais perdre les codes promo ni les commandes payées, et éviter le délai de réveil du site après inactivité.

Clique sur "Create Web Service" (le premier déploiement va probablement échouer ou tourner sans les bonnes variables — normal, on les ajoute à l'étape suivante).

## 6. Ajouter le disque persistant

Une fois le service créé, onglet **Disks** → **Add Disk** :
- Name : `fitsurmesure-data`
- Mount Path : `/var/data`
- Size : 1 GB (largement suffisant)

## 7. Configurer les variables d'environnement

Onglet **Environment** → ajoute :

| Clé | Valeur |
|---|---|
| `DATA_DIR` | `/var/data` |
| `SECRET_KEY` | une longue chaîne aléatoire (Render propose un bouton "Generate") |
| `ADMIN_PASSWORD` | un vrai mot de passe que toi seul connais |
| `OWNER_ACCESS_CODE` | un code que toi seul connais (remplace `SAMY-ACCES-ILLIMITE`) |
| `STRIPE_SECRET_KEY` | ta clé secrète Stripe (`sk_test_...` pour commencer) |
| `STRIPE_WEBHOOK_SECRET` | laisse vide pour l'instant, voir étape 9 |
| `ANTHROPIC_API_KEY` | facultatif : ta clé API Anthropic (console.anthropic.com), pour activer l'assistant IA de support sur `/assistant`. Sans elle, la page reste accessible mais affiche un message invitant à utiliser le formulaire de contact à la place — rien n'est bloqué. |

Sauvegarde : Render relance automatiquement le déploiement.

## 8. Récupérer l'URL de ton site

Une fois déployé (quelques minutes), Render te donne une URL du type :

```
https://fitsurmesure.onrender.com
```

C'est cette URL que tu utilises pour :
- Le champ "site web" demandé par Stripe lors de l'activation de ton compte.
- Vérifier que tout marche : va sur `https://fitsurmesure.onrender.com`.

## 9. Configurer le webhook Stripe (avec la vraie URL)

Dans le Dashboard Stripe → **Développeurs** → **Webhooks** → **Add an endpoint** :
- URL : `https://fitsurmesure.onrender.com/stripe-webhook`
- Événement à écouter : `checkout.session.completed`

Stripe te donne un `whsec_...` : reviens sur Render, onglet Environment, colle-le dans `STRIPE_WEBHOOK_SECRET`, sauvegarde (nouveau redéploiement automatique).

## 10. Tester en conditions réelles

Sur `https://fitsurmesure.onrender.com/questionnaire` :
- Avec ton code `OWNER_ACCESS_CODE` : accès gratuit illimité, pour vérifier que tout fonctionne.
- Avec une carte de test Stripe (`4242 4242 4242 4242`, tant que tu es en clés `sk_test_...`) : vérifie le vrai parcours de paiement.

## Plus tard : nom de domaine personnalisé

Quand tu veux un vrai nom de domaine (ex: `fitsurmesure.fr`) à la place de `fitsurmesure.onrender.com` : achète-le chez un registrar (OVH, Google Domains, Namecheap...), puis dans Render, onglet **Settings** → **Custom Domains**, ajoute-le et suis les instructions DNS. Aucun changement de code nécessaire.

## Mettre à jour le site après une future modification

À chaque fois que le code change (par moi ou par toi) :

```bash
git add -A
git commit -m "description du changement"
git push
```

Render redéploie automatiquement à chaque push sur `main`.
