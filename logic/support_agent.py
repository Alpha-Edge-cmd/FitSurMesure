# -*- coding: utf-8 -*-
"""
Agent IA de support, accessible directement sur le site (retour Samy, prompt
hors 24 phases : "je voudrais également qu'il y'ai un agent IA ou un blog ou
les utilisateurs peuvent parler entre eux afin que leur question persistante
ne soit pas laissé au hasard"). Réponse validée par Samy pour ce choix : agent
IA plutôt que blog/forum, motivée par "le moins compliqué et le moins
susceptible d'avoir un problème" — un forum demande des comptes, une
modération, et un vrai risque de contenu inapproprié entre utilisateurs ;
un agent IA sans état côté serveur n'a aucun de ces problèmes.

Configuration requise (variable d'environnement) :
  - ANTHROPIC_API_KEY : clé API Anthropic (https://console.anthropic.com).

Tant que ANTHROPIC_API_KEY n'est pas configurée, le site fonctionne toujours :
la page /assistant reste accessible mais affiche un message clair invitant à
utiliser le formulaire /contact à la place (même principe de dégradation
propre que Stripe non configuré, cf. logic/stripe_client.py::is_configured).

Choix délibéré de conception, cohérents avec "le moins compliqué" :
  - AUCUN ÉTAT CÔTÉ SERVEUR. L'historique de la conversation vit uniquement
    dans la page (JavaScript), et est renvoyé par le client à chaque question
    pour donner le contexte des échanges précédents. Rien n'est stocké en
    session Flask (pas de risque de dépassement de la taille d'un cookie de
    session, qui grossirait vite avec un historique de conversation) ni en
    base de données (pas de nouvelle table, pas de RGPD à gérer pour des
    conversations qui n'ont pas vocation à être conservées).
  - Système de prompt strict : répond UNIQUEMENT sur le fonctionnement du
    site (formules, questionnaire, PDF, paiement, compte) et des questions
    générales de musculation/nutrition/cardio de niveau explicatif. Redirige
    explicitement vers /contact pour tout ce qui dépend d'un compte/d'une
    commande précis, que l'IA n'a de toute façon aucun moyen de consulter.
"""
import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Modèle rapide/économique : largement suffisant pour des réponses de type
# FAQ/support, pas besoin d'un modèle de raisonnement complexe ici.
MODEL = "claude-haiku-4-5-20251001"

# Nombre de TOURS (question + réponse) maximum conservés dans l'historique
# renvoyé par le client et pris en compte côté serveur — jamais illimité,
# pour borner le coût et la taille de chaque appel API.
MAX_HISTORIQUE = 10

SYSTEM_PROMPT = """Tu es l'assistant du site FitSurMesure, qui génère des programmes de \
musculation/nutrition/cardio personnalisés en PDF, contre paiement.

Ton rôle est strictement limité à :
1. Expliquer comment fonctionne le site (questionnaire, formules et prix, génération du \
PDF, paiement, compte/connexion, régénération de programme).
2. Répondre à des questions générales de musculation/nutrition/cardio de niveau \
explicatif (ex : "c'est quoi le TDEE", "pourquoi 3 séries minimum", "c'est quoi un split").

Formules et prix actuels : Programme Nutrition seul 9,99€, Programme Cardio seul \
12,99€, Programme Musculation seul 14,99€, Programme Complet (Musculation + Cardio, \
alimentation incluse) 22,99€, Abonnement annuel (programmes illimités) 59€.

Tu n'as accès à AUCUNE donnée de compte, de commande ou de paiement d'un utilisateur \
précis. Pour toute question qui en dépend (statut d'une commande, remboursement, bug \
précis sur UN programme déjà généré, problème de connexion), dis clairement que tu ne \
peux pas y accéder et invite à utiliser le formulaire de contact du site (page \
"Nous contacter"), lu directement par l'équipe.

Rappelle, si la question s'y prête, que ce site est un outil automatisé qui ne remplace \
pas un avis médical, un coach sportif diplômé ou un nutritionniste — recommande de \
consulter un professionnel de santé pour toute question médicale précise (douleur, \
blessure, grossesse, condition médicale).

Réponds en français, de façon concise (quelques phrases, jamais un essai)."""


class SupportAgentNotConfiguredError(Exception):
    """Levée quand on tente d'utiliser l'agent sans ANTHROPIC_API_KEY configurée."""
    pass


def is_configured():
    return bool(ANTHROPIC_API_KEY)


def ask(question, historique=None):
    """`historique` : liste de {"role": "user"|"assistant", "content": str},
    déjà validée/tronquée par l'appelant (cf. MAX_HISTORIQUE, jamais fait
    confiance tel quel côté route). Retourne le texte de la réponse.

    Lève SupportAgentNotConfiguredError si ANTHROPIC_API_KEY n'est pas
    définie : l'appelant doit alors afficher le message de repli vers
    /contact, jamais laisser remonter une exception brute à l'utilisateur."""
    if not is_configured():
        raise SupportAgentNotConfiguredError()

    # Import différé : la dépendance `anthropic` n'est nécessaire que si
    # l'agent est réellement configuré et utilisé (même logique que
    # `import stripe` fait en haut de stripe_client.py, mais ici différé car
    # anthropic n'est utile qu'à ce seul endroit du code).
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = list(historique or []) + [{"role": "user", "content": question}]
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return "".join(bloc.text for bloc in response.content if bloc.type == "text")
