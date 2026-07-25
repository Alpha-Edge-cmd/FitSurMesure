# Configurer le paiement Stripe sur FitSurMesure

Le site est maintenant câblé pour un vrai paiement (Stripe Checkout) sur les 4 formules : Cardio, Musculation et Complet en paiement unique, Abonnement en récurrent annuel. Tant que les clés ci-dessous ne sont pas renseignées, le site fonctionne toujours (questionnaire, aperçu, dashboard promo), mais la création d'un paiement renvoie une erreur claire ("paiement non configuré").

## 1. Créer un compte Stripe

Sur https://dashboard.stripe.com/register. Le compte démarre en **mode test** par défaut : tu peux tout tester sans vraie carte bancaire, avant d'activer le mode production.

## 2. Récupérer les clés de test

Dans le Dashboard Stripe → *Développeurs* → *Clés API* (mode test activé, bascule en haut à droite) :
- **Clé secrète** : `sk_test_...`

## 3. Configurer les variables d'environnement

Avant de lancer le site (`python3 app.py`), exporte :

```bash
export STRIPE_SECRET_KEY="sk_test_..."
export SECRET_KEY="une-chaine-aleatoire-longue"       # sécurise les sessions (dashboard admin)
export ADMIN_PASSWORD="choisis-un-vrai-mot-de-passe"  # remplace la valeur par défaut
```

Sans `STRIPE_SECRET_KEY`, tout le reste marche mais le paiement est bloqué proprement.

## 4. Tester les paiements en local (webhook)

Stripe a besoin de confirmer les paiements par un "webhook". Pour tester ça en local, installe la Stripe CLI (https://docs.stripe.com/stripe-cli) puis :

```bash
stripe login
stripe listen --forward-to localhost:5050/stripe-webhook
```

Cette commande affiche une clé `whsec_...` à mettre dans :

```bash
export STRIPE_WEBHOOK_SECRET="whsec_..."
```

Note : même sans webhook configuré, le paiement fonctionne quand même grâce à une vérification de secours faite directement à la page de confirmation (`/payment-success`). Le webhook est surtout utile en production, pour ne rien perdre si l'utilisateur ferme l'onglet juste après avoir payé.

## 5. Cartes de test Stripe

En mode test, utilise par exemple `4242 4242 4242 4242`, n'importe quelle date future, n'importe quel CVC. Liste complète : https://docs.stripe.com/testing.

## 6. Passer en production (quand le site sera en ligne)

Une fois que tu as un nom de domaine et un hébergeur :
1. Active le mode production dans Stripe (vérifications d'identité/entreprise demandées par Stripe).
2. Récupère les clés **live** (`sk_live_...`) et remplace `STRIPE_SECRET_KEY`.
3. Dans le Dashboard Stripe → *Développeurs* → *Webhooks*, crée un endpoint pointant vers `https://ton-domaine.fr/stripe-webhook`, récupère son `whsec_...` et mets-le à jour.
4. Vérifie que ton hébergeur sert le site en HTTPS (obligatoire pour Stripe Checkout en production).
5. Change `ADMIN_PASSWORD` et `SECRET_KEY` pour de vraies valeurs secrètes (pas celles utilisées en test).

## Ton accès personnel illimité

Un code séparé des codes promo influenceurs te donne un accès gratuit et illimité, sans jamais apparaître dans le dashboard admin ni fausser les statistiques de parrainage. Entre-le dans le champ "Code promo / parrainage" du questionnaire :

```
SAMY-ACCES-ILLIMITE
```

Insensible à la casse et aux espaces. Change-le avant la mise en ligne via la variable d'environnement `OWNER_ACCESS_CODE` (comme `ADMIN_PASSWORD`), pour que personne d'autre ne puisse le deviner :

```bash
export OWNER_ACCESS_CODE="un-code-que-toi-seul-connais"
```

## Ce qui a été construit côté code

- `logic/stripe_client.py` : crée les sessions Stripe Checkout (paiement unique ou abonnement annuel selon la formule), sans besoin de créer les produits à l'avance dans le dashboard Stripe (prix envoyés à la volée).
- `logic/orders.py` : garde les réponses du questionnaire côté serveur pendant l'aller-retour vers Stripe, marque une commande "payée", permet de régénérer le PDF (exercices/séances remplacés) sans redemander de paiement.
- Routes : `/create-checkout-session`, `/payment-success`, `/payment-cancel`, `/stripe-webhook`, `/download/<order_id>`, `/order-preview/<order_id>`.
- Un code promo actif rend l'accès gratuit sans passer par Stripe (comportement voulu pour le parrainage).
