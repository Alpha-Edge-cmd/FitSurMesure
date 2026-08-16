# -*- coding: utf-8 -*-
"""
Informations légales de l'éditeur du site.

Retour Samy : le site encaissait sans mentions légales ni conditions générales
de vente. Les deux sont obligatoires pour vendre en ligne à des particuliers,
et l'absence de clause de renonciation au droit de rétractation exposait à des
demandes de remboursement pendant quatorze jours après téléchargement du PDF —
sur un produit numérique livré immédiatement, c'est-à-dire déjà consommé.

TOUT SE CONFIGURE ICI, en un seul endroit. Les valeurs sensibles sont lues
depuis les variables d'environnement pour ne pas figer une adresse personnelle
dans un dépôt public.

À renseigner sur Render dès réception du SIRET :
    LEGAL_NOM       = "Prénom Nom"
    LEGAL_ADRESSE   = "12 rue Exemple, 75000 Paris"
    LEGAL_EMAIL     = "contact@..."
    LEGAL_SIRET     = "123 456 789 00012"
    LEGAL_MEDIATEUR = "Nom du médiateur, adresse, site web"

Tant que LEGAL_SIRET est vide, les pages affichent un avertissement visible
indiquant qu'elles sont incomplètes : mieux vaut un manque signalé qu'un
manque silencieux.
"""
import os

# Durée de conservation des données annoncée aux utilisateurs. Doit rester
# cohérente avec ce que fait réellement le site — ne pas annoncer une durée
# plus courte que la réalité.
DUREE_CONSERVATION = "3 ans"


def editeur():
    """Informations d'identification de l'éditeur, telles qu'affichées."""
    return {
        "nom": os.environ.get("LEGAL_NOM", "[Prénom Nom à compléter]"),
        "adresse": os.environ.get("LEGAL_ADRESSE", "[adresse à compléter]"),
        "email": os.environ.get("LEGAL_EMAIL", "contact@fitsurmesure.fr"),
        "siret": os.environ.get("LEGAL_SIRET", ""),
        "mediateur": os.environ.get("LEGAL_MEDIATEUR", ""),
    }


def offres(prices):
    """Libellés des formules vendues, pour l'article 2 des CGV.

    Construits depuis `PRICES` (app.py) plutôt que recopiés : un changement de
    tarif ne doit jamais rendre les conditions générales fausses.
    L'abonnement annuel est volontairement absent tant qu'il n'est pas
    commercialisé.
    """
    libelles = [
        ("nutrition", "Programme Nutrition seul"),
        ("cardio", "Programme Cardio seul"),
        ("musculation", "Programme Musculation seul"),
        ("les_deux", "Programme Complet (Musculation + Cardio)"),
    ]
    return [f"{nom} — {prices[cle]}" for cle, nom in libelles if cle in prices]


def est_complet():
    """True si les informations obligatoires sont renseignées."""
    infos = editeur()
    return bool(infos["siret"]) and "compléter" not in infos["nom"]
