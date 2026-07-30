# -*- coding: utf-8 -*-
import io
import os
import re
from datetime import date
from functools import wraps

from flask import Flask, request, render_template, send_file, jsonify, redirect, url_for, session

from logic.calculations import build_nutrition_profile
from logic.program_builder import build_program
from logic.cardio_builder import build_cardio_program
from logic.pdf_generator import generate_pdf
from logic import auth, promo_codes, orders, stripe_client, order_migration, program_service, program_interaction, contact_messages
from logic.db import init_db

# Prompt hors 24 phases (décision explicite de Samy, cf. discussion sur le
# constat "le PDF payant utilise encore l'ancien moteur à 111 exercices") :
# /generate-preview et /download basculent sur le moteur V2 (catalogue
# enrichi, objectifs composites, préférence matériel multi-choix, questions
# PR, conseils d'exécution, justification à 3 niveaux) — cf. `_build_
# program_v2` ci-dessous. L'ancien moteur (`build_program`, import ci-dessus,
# jamais modifié) reste utilisé comme FILET DE SÉCURITÉ si la génération V2
# lève une exception (catalogue vide, champ questionnaire imprévu...) : ne
# jamais bloquer un client payant à cause d'un problème côté V2.
from logic.models import ProfileSnapshot
from logic.profile_normalizer import normalize_questionnaire_data
from logic.recommendation.catalog_provider import get_recommendation_catalog
from logic.recommendation.program_builder import build_program as build_program_v2
from logic.pdf_program_adapter import raw_result_to_pdf_data

app = Flask(__name__)

# Fondations données FitSurMesure V2 (phase 1/16, cf. architecture_v2_consolidation.md).
# N'affecte aucune route existante : crée seulement les nouvelles tables
# (User/ProfileSnapshot/Program/ProgramSession/ProgramExercise) si elles
# n'existent pas encore. Le stockage JSON existant (orders.py, promo_codes.py)
# continue de fonctionner exactement comme avant, sans aucune modification.
init_db(app)

# Clé de session et mot de passe admin : à surcharger via variables d'environnement
# en production (SECRET_KEY / ADMIN_PASSWORD). Valeurs par défaut fournies pour que
# le site fonctionne tel quel en local.
app.secret_key = os.environ.get("SECRET_KEY", "fitsurmesure-cle-secrete-dev-a-changer")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "fitsurmesure2026")

# Code d'accès illimité réservé au propriétaire du site (Samy) : distinct des codes
# promo influenceurs/amis (logic.promo_codes) — ne consomme aucun "essai gratuit",
# ne déclenche jamais de réduction/commission, et n'apparaît jamais dans le dashboard
# admin. À changer via variable d'environnement avant de mettre le site en ligne,
# comme ADMIN_PASSWORD, pour que personne d'autre ne puisse le deviner.
OWNER_ACCESS_CODE = os.environ.get("OWNER_ACCESS_CODE", "SAMY-ACCES-ILLIMITE")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Offres et tarifs (affichage uniquement, pas de paiement réel intégré pour l'instant)
# Retour Samy (prompt hors 24 phases) : "créer un programme alimentation
# moins cher que le programme cardio" -- nutrition seule strictement en
# dessous du prix du cardio seul (12,99€), cohérent avec le fait qu'elle
# demande moins de travail de génération (pas de séances à construire).
PRICES = {
    "musculation": "14,99€",
    "cardio": "12,99€",
    "nutrition": "9,99€",
    "les_deux": "22,99€",
    "abonnement": "59€ / an",
}
PRIX_AFFICHE = PRICES["les_deux"]  # gardé pour compat, utilisé comme prix "à partir de"


def _error(msg, code=400):
    return jsonify({"error": msg}), code


def _parse_sessions(text):
    """Convertit un texte du type '2x / semaine' en entier."""
    if not text:
        return 0
    match = re.match(r"\s*(\d+)", str(text))
    return int(match.group(1)) if match else 1


def _parse_optional_float(raw):
    """Convertit une valeur de champ numérique facultatif (temps en minutes,
    record...) en float, ou None si absente/invalide -- jamais d'exception.
    Un champ laissé vide au questionnaire (`raw` vaut None ou "") donne
    explicitement None, interprété en aval comme "aucun record" (retour Samy :
    "laisse une possibilité aucun record")."""
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _cardio_sessions(data):
    if data.get("pratique_cardio") != "Oui":
        return 0
    return _parse_sessions(data.get("cardio_frequence", ""))


def _autre_sport_sessions(data):
    if data.get("autre_sport") != "Oui":
        return 0
    return _parse_sessions(data.get("autre_sport_frequence", ""))


def _autre_sport_type_affiche(data):
    """Nom du sport à afficher (PDF/conseils) : résout le cas "Autre" (liste
    déroulante des sports les plus pratiqués en France, cf. static/script.js)
    vers le texte libre saisi ensuite (`autre_sport_type_autre`), sinon la
    valeur choisie telle quelle. Prompt hors 24 phases (retour Samy : liste
    des sports + adaptation du programme)."""
    valeur = data.get("autre_sport_type", "")
    if valeur == "Autre":
        return data.get("autre_sport_type_autre") or "un autre sport"
    return valeur


def _normalize_formule(data):
    formule = data.get("formule", "les_deux")
    if formule not in ("musculation", "cardio", "nutrition", "les_deux", "abonnement"):
        formule = "les_deux"
    return formule


def _include_nutrition(formule):
    """Retour Samy (prompt hors 24 phases) : "dans le programme musculation
    seul ne mets pas de programme alimentation et dans le programme cardio
    pareil" -- la partie Alimentation du PDF (`pdf_generator.generate_pdf`,
    paramètre `include_nutrition`) n'est incluse que pour les formules qui
    l'ont explicitement vendue : "nutrition" (nouvelle offre dédiée),
    "les_deux" et "abonnement" (les 2/tout compris). Jamais pour
    "musculation" ou "cardio" seuls."""
    return formule not in ("musculation", "cardio")


def _preview_json(nutrition, program, cardio):
    """Construit le JSON d'aperçu (musculation + cardio) partagé par /generate-preview
    (avant paiement, à partir des données brutes du questionnaire) et /order-preview
    (après paiement, à partir d'une commande stockée), pour l'écran de révision
    \"je n'aime pas cet exercice / cette séance\"."""
    if nutrition.get("blocked"):
        return {"blocked": True, "messages": nutrition.get("messages", [])}

    preview = {"blocked": False}

    if program:
        preview["program"] = {
            "split_label": program["split_label"],
            "programme": [
                {
                    "nom": jour["nom"],
                    "muscles": [
                        {
                            "muscle": bloc["muscle"],
                            "exercices": [e["nom"] for e in bloc["exercices"]],
                        }
                        for bloc in jour["muscles"]
                    ],
                }
                for jour in program["programme"]
            ],
        }

    if cardio:
        preview["cardio"] = {
            "seances": [
                {"nom": s["nom"], "discipline": s["discipline"], "type": s["type"]}
                for s in cardio["seances"]
            ],
        }

    return preview


@app.route("/")
def landing():
    return render_template("landing.html", prix=PRIX_AFFICHE, prices=PRICES)


@app.route("/questionnaire")
def questionnaire():
    return render_template("index.html")


def _derive_objectif_principal(data):
    """Objectifs multiples (prompt final, hors 24 phases) : le questionnaire
    envoie maintenant `objectifs` (liste, checkboxes cochées simultanément) au
    lieu d'un unique `objectif_principal`. Cette fonction ne fait QUE combler
    `objectif_principal` pour le pipeline legacy (nutrition/cardio/programme
    V1, tous inchangés, qui lisent encore cette clé unique directement dans
    `data`) — le vrai calcul de pondération composite sur tous les objectifs
    cochés se fait uniquement côté moteur V2 (logic/recommendation/
    objectives.py), jamais ici. Retourne un NOUVEAU dict (ne mute jamais
    l'original, cohérent avec la même précaution prise dans
    logic/profile_normalizer.py)."""
    if data.get("objectif_principal"):
        return data
    objectifs = data.get("objectifs")
    if not isinstance(objectifs, list) or not objectifs:
        return data
    principaux_valides = {
        "Prise de muscle", "Perte de gras", "Recomposition (sec + muscle)",
        "Performance / explosivité", "Condition physique générale",
    }
    candidats = [o for o in objectifs if o in principaux_valides]
    if not candidats:
        return data
    data = dict(data)
    data["objectif_principal"] = candidats[0]
    return data


RAISON_DOULEUR_REVUE = "Douleur / gêne"


def _build_program_v2(data, frequence, duree_seance):
    """_build_program_v2(data, frequence, duree_seance) -> dict PDF-ready
    (même forme que l'ancien `build_program`) ou lève une exception (à
    l'appelant de retomber sur l'ancien moteur, cf. docstring de l'import
    ci-dessus).

    Construit un `ProfileSnapshot` ÉPHÉMÈRE (jamais ajouté à `db.session`,
    jamais committé) : `/generate-preview` tourne AVANT tout paiement, il ne
    doit donc jamais écrire de User/ProfileSnapshot en base juste pour un
    aperçu. `/download`, lui, réutilise cette même fonction par simplicité
    (même résultat déterministe pour les mêmes données de commande, cf.
    `logic.recommendation.program_builder` "déterminisme préservé") plutôt
    que de dépendre d'un `Program` déjà persisté (qui pourrait ne pas encore
    exister si `_essayer_generer_programme_v2` a échoué silencieusement)."""
    cleaned = normalize_questionnaire_data(data)
    profile_ephemere = ProfileSnapshot(**cleaned)

    catalogue = get_recommendation_catalog()

    # Retours "je n'aime pas cet exercice" d'un programme précédent (même
    # contrat que l'ancien moteur, `program_builder._rejected_sets`) : exclu
    # par nom exact, et par SCHÉMA DE MOUVEMENT (pattern) en plus si la raison
    # est une douleur/gêne (une autre variante du même mouvement risque de
    # poser le même problème).
    exercices_rejetes = data.get("exercices_rejetes") or []
    noms_exclus = set()
    patterns_exclus = set()
    for item in exercices_rejetes:
        if not isinstance(item, dict):
            continue
        nom = item.get("nom")
        if not nom:
            continue
        noms_exclus.add(nom)
        if item.get("raison") == RAISON_DOULEUR_REVUE:
            for ex in catalogue:
                if getattr(ex, "name", None) == nom:
                    patterns_exclus.add(getattr(ex, "pattern", None))

    if noms_exclus or patterns_exclus:
        catalogue = [
            ex for ex in catalogue
            if getattr(ex, "name", None) not in noms_exclus
            and getattr(ex, "pattern", None) not in patterns_exclus
        ]

    result = build_program_v2(profile_ephemere, catalogue, options={
        "frequence": frequence, "duree_seance": duree_seance,
    })
    return raw_result_to_pdf_data(
        result, catalogue, questionnaire_data=data, profile_snapshot=profile_ephemere,
    )


def _build_everything(data):
    """Valide le questionnaire et construit profile/nutrition/program/cardio/lifestyle.
    Retourne (error_response, profile, nutrition, program, cardio, lifestyle).
    error_response est None si tout est valide. Partagé entre /generate (PDF) et
    /generate-preview (JSON, pour l'écran de révision \"je n'aime pas cet exercice\")."""
    data = _derive_objectif_principal(data)

    # ---- Consentement RGPD : obligatoire, on ne traite rien sans ça ----
    if not data.get("consentement_rgpd"):
        return _error("Le consentement au traitement des données est obligatoire."), None, None, None, None, None

    # ---- Validation des champs obligatoires ----
    required = ["date_naissance", "sexe", "poids", "taille"]
    for field in required:
        if not data.get(field):
            return _error(f"Champ manquant : {field}"), None, None, None, None, None

    if not DATE_RE.match(str(data["date_naissance"])):
        return _error("Date de naissance invalide (format attendu AAAA-MM-JJ)."), None, None, None, None, None

    try:
        poids = float(data["poids"])
        taille = float(data["taille"])
    except (TypeError, ValueError):
        return _error("Poids ou taille invalide."), None, None, None, None, None

    if not (30 <= poids <= 300):
        return _error("Le poids doit être compris entre 30 et 300 kg."), None, None, None, None, None
    if not (100 <= taille <= 250):
        return _error("La taille doit être comprise entre 100 et 250 cm."), None, None, None, None, None

    try:
        y, m, d = [int(x) for x in data["date_naissance"].split("-")]
        date(y, m, d)
    except ValueError:
        return _error("Date de naissance invalide."), None, None, None, None, None

    if data["sexe"] not in ("Homme", "Femme"):
        return _error("Sexe invalide."), None, None, None, None, None

    formule = _normalize_formule(data)
    veut_musculation = formule in ("musculation", "les_deux", "abonnement")
    veut_cardio = formule in ("cardio", "les_deux", "abonnement")

    if veut_musculation:
        frequence = int(data.get("frequence_entrainement", 3))
        if not (1 <= frequence <= 7):
            return _error("Fréquence d'entraînement invalide."), None, None, None, None, None
    else:
        frequence = 0

    if veut_cardio:
        # Formule cardio : la fréquence de cardio vient directement du champ dédié,
        # pas besoin de passer par la question "pratiques-tu déjà du cardio ?".
        cardio_sessions = _parse_sessions(data.get("cardio_frequence", ""))
    else:
        cardio_sessions = _cardio_sessions(data)
    autre_sport_sessions = _autre_sport_sessions(data)

    # ---- Calcul nutrition (inclut les garde-fous de sécurité) ----
    nutrition_input = {
        "sexe": data["sexe"],
        "poids": poids,
        "taille": taille,
        "date_naissance": data["date_naissance"],
        "niveau_activite_quotidien": data.get("niveau_activite_quotidien", "sedentaire"),
        "frequence_entrainement": frequence,
        "cardio_sessions_semaine": cardio_sessions,
        "autre_sport_sessions": autre_sport_sessions,
        "objectif_principal": data.get("objectif_principal", "Condition physique générale"),
        "niveau_musculation": data.get("niveau_musculation", "Débutant complet"),
        "condition_medicale": data.get("condition_medicale", "Non"),
        "grossesse": data.get("grossesse", "Non"),
    }
    nutrition = build_nutrition_profile(nutrition_input)

    # Signature stable propre à la personne (prénom/date de naissance/poids/taille/sexe) :
    # sert à départager des choix à égalité de pertinence (exercices, repas d'exemple...)
    # pour éviter que deux profils similaires obtiennent toujours exactement les mêmes
    # suggestions.
    # `_nonce` : identifiant unique généré côté frontend à chaque nouvelle session
    # de questionnaire (voir static/script.js). Sans lui, deux soumissions avec les
    # mêmes informations de profil (nom, date de naissance, poids, taille, sexe)
    # produiraient toujours exactement le même programme — un problème réel pour
    # un client qui régénère son programme plus tard (ex: formule abonnement).
    signature = "|".join(str(x) for x in [
        data.get("prenom", ""), data.get("date_naissance", ""), poids, taille, data.get("sexe", ""),
        data.get("_nonce", ""),
    ])

    profile = {
        "prenom": data.get("prenom", ""),
        "sexe": data["sexe"],
        "poids": poids,
        "taille": taille,
        "niveau_musculation": data.get("niveau_musculation", "Débutant complet"),
        "objectif_principal": data.get("objectif_principal", "Condition physique générale"),
        "frequence_entrainement": frequence,
        "composition_corporelle": data.get("composition_corporelle", "Je ne sais pas"),
        "signature": signature,
    }

    lifestyle = {
        "restriction_alimentaire": data.get("restriction_alimentaire", "Aucune"),
        "aliments_non_apprecies": data.get("aliments_non_apprecies", ""),
        "aliments_apprecies": data.get("aliments_apprecies", []),
        "repas_par_jour": data.get("repas_par_jour", "3 à 4"),
        "sommeil": data.get("sommeil", "7 à 8h"),
        "tabac": data.get("tabac", "Non"),
        "cigarette_electronique": data.get("cigarette_electronique", "Non"),
        "cannabis": data.get("cannabis", "Non"),
        "alcool": data.get("alcool", "Jamais"),
        "complements": data.get("complements", []),
        "cardio_type": ", ".join(data.get("cardio_types", [])) or "Aucun" if (veut_cardio or data.get("pratique_cardio") == "Oui") else "Aucun",
        "cardio_frequence": data.get("cardio_frequence", "") if (veut_cardio or data.get("pratique_cardio") == "Oui") else "",
        "condition_medicale": data.get("condition_medicale", "Non"),
        "condition_medicale_details": data.get("condition_medicale_details", ""),
        "precisions": data.get("precisions", ""),
        "autre_sport": data.get("autre_sport", "Non"),
        "autre_sport_type": _autre_sport_type_affiche(data),
        "autre_sport_type_brut": data.get("autre_sport_type", ""),
        "autre_sport_adapter": data.get("autre_sport_adapter", "Non"),
        "autre_sport_sessions": autre_sport_sessions,
        "niveau_activite_quotidien": data.get("niveau_activite_quotidien", "sedentaire"),
        "blessures": data.get("blessures", []),
        "exercices_incapables": data.get("exercices_incapables", []),
        "allergie_details": data.get("allergie_details", ""),
        "temps_cuisine": data.get("temps_cuisine", ""),
        "budget_alimentaire": data.get("budget_alimentaire", ""),
        "niveau_stress": data.get("niveau_stress", ""),
        "objectif_cardio": data.get("objectif_cardio", ""),
        "niveau_cardio": data.get("niveau_cardio", ""),
    }

    program = None
    cardio = None
    if not nutrition["blocked"] and veut_musculation:
        try:
            program = _build_program_v2(data, frequence, data.get("duree_seance", "1h - 1h30"))
        except Exception:
            # Filet de sécurité (jamais bloquer un client payant à cause d'un
            # problème côté moteur V2, cf. docstring de _build_program_v2) :
            # repli sur l'ancien moteur, comportement identique à avant la
            # bascule V2 de cette phase.
            app.logger.exception(
                "génération V2 du programme musculation impossible, repli sur l'ancien moteur"
            )
            program_input = {
                "frequence_entrainement": frequence,
                "split_preference": data.get("split_preference", "auto"),
                "splits_exclus": data.get("splits_exclus", []),
                "equipement": data.get("equipement", "Salle complète"),
                "blessures": data.get("blessures", []),
                "exercices_incapables": data.get("exercices_incapables", []),
                "duree_seance": data.get("duree_seance", "1h - 1h30"),
                "exos_par_muscle_pref": data.get("exos_par_muscle_pref", "auto"),
                "niveau_musculation": data.get("niveau_musculation", "Débutant complet"),
                "objectif_principal": data.get("objectif_principal", "Condition physique générale"),
                "muscles_prioritaires": data.get("muscles_prioritaires", []),
                "longueur_bras": data.get("longueur_bras", "Je ne sais pas"),
                "longueur_jambes": data.get("longueur_jambes", "Je ne sais pas"),
                "signature": signature,
                # Retours "je n'aime pas cet exercice" sur un programme précédent :
                # [{ "nom": "...", "raison": "..." }, ...]
                "exercices_rejetes": data.get("exercices_rejetes", []),
            }
            program = build_program(program_input)

    if not nutrition["blocked"] and veut_cardio:
        temps_1km = _parse_optional_float(data.get("temps_1km"))
        cardio_input = {
            "pratique_cardio": "Oui",
            # Retour Samy (prompt hors 24 phases, #150 : "gamme diversifiée
            # de séances cardio") : transmis à build_cardio_program pour
            # choisir une variante de protocole stable par profil (même
            # principe que la signature déjà utilisée pour la musculation),
            # cf. logic/cardio_builder.py::_variante_jitter.
            "signature": signature,
            "cardio_types": data.get("cardio_types", []),
            "cardio_sessions": cardio_sessions,
            "objectif_principal": data.get("objectif_principal", "Condition physique générale"),
            "objectif_cardio": data.get("objectif_cardio", ""),
            "niveau_cardio": data.get("niveau_cardio", "Intermédiaire"),
            "temps_1km": temps_1km,
            "sexe": data.get("sexe", ""),
            "autre_sport": data.get("autre_sport", "Non"),
            "autre_sport_type": data.get("autre_sport_type", ""),
            "autre_sport_sessions": autre_sport_sessions,
            "blessures": data.get("blessures", []),
            # Retours "je n'aime pas cette séance" : [{ "seance_nom": "...", "raison": "..." }, ...]
            "cardio_rejets": data.get("cardio_rejets", []),
            # Prompt hors 24 phases (retour Samy : "questionnaire adapté par
            # discipline" + questions objectif/délai/allure/records par
            # discipline) : transmis tel quel à build_cardio_program, qui les
            # utilise pour personnaliser objectif/notes/records par discipline
            # (cf. logic/cardio_builder.py, additif -- aucune règle existante
            # modifiée). Un champ record laissé vide au questionnaire ->
            # None ici -> interprété comme "aucun record" en aval.
            "objectif_course": data.get("objectif_course", ""),
            "delai_objectif_course": data.get("delai_objectif_course", ""),
            "allure_cible_course": data.get("allure_cible_course", ""),
            # Retour Samy : distance visée ("5km" | "10km" | "semi" |
            # "marathon" | "trail_ultra" | ""). Pilote le placement des séances
            # à allure spécifique et le dosage de la sortie longue.
            "distance_objectif_course": data.get("distance_objectif_course", ""),
            "records_course": {
                "5km": _parse_optional_float(data.get("record_5km")),
                "10km": _parse_optional_float(data.get("record_10km")),
                "20km": _parse_optional_float(data.get("record_20km")),
                "40km": _parse_optional_float(data.get("record_40km")),
            },
            "objectif_natation": data.get("objectif_natation", ""),
            "delai_objectif_natation": data.get("delai_objectif_natation", ""),
            "records_natation": {
                "500m": _parse_optional_float(data.get("record_500m_natation")),
                "1km": _parse_optional_float(data.get("record_1km_natation")),
            },
            "objectif_velo": data.get("objectif_velo", ""),
            "delai_objectif_velo": data.get("delai_objectif_velo", ""),
            "records_velo": {
                "20km": _parse_optional_float(data.get("record_20km_velo")),
                "40km": _parse_optional_float(data.get("record_40km_velo")),
            },
            "objectif_circuit": data.get("objectif_circuit", ""),
            "type_circuit_prefere": data.get("type_circuit_prefere", []),
        }
        cardio = build_cardio_program(cardio_input)

    return None, profile, nutrition, program, cardio, lifestyle


@app.route("/generate-preview", methods=["POST"])
def generate_preview():
    """Retourne le programme (muscu + cardio) en JSON, sans PDF et sans paiement,
    pour l'écran de révision \"je n'aime pas cet exercice / cette séance\" côté
    frontend, AVANT de passer au paiement : la personne voit la liste réelle de ce
    qui a été choisi pour elle, coche ce qu'elle n'aime pas avec une raison, puis
    le questionnaire complet + ces retours sont envoyés à /create-checkout-session."""
    data = request.get_json(silent=True) or {}
    error, profile, nutrition, program, cardio, lifestyle = _build_everything(data)
    if error:
        return error

    return jsonify(_preview_json(nutrition, program, cardio))


# ---------------------------------------------------------------------------
# Paiement (Stripe) et livraison du PDF.
#
# Flux :
#   1. /create-checkout-session valide le questionnaire, crée une "commande"
#      (logic.orders) qui garde les réponses côté serveur, puis :
#        - si un code promo valide/actif est fourni : la commande est marquée
#          payée immédiatement (accès gratuit parrainage), pas de Stripe ;
#        - sinon : crée une session Stripe Checkout et renvoie son URL.
#   2. Stripe redirige vers /payment-success (ou /payment-cancel), qui vérifie
#      le paiement et affiche une page permettant de télécharger le PDF et de
#      signaler un exercice/une séance à modifier (sans repayer).
#   3. /stripe-webhook confirme aussi le paiement de façon asynchrone (utile en
#      production, notamment si l'utilisateur ferme l'onglet avant la redirection).
#   4. /download/<order_id> génère et renvoie le PDF (GET) ou le régénère avec des
#      exercices/séances remplacés (POST), uniquement si la commande est payée.
# ---------------------------------------------------------------------------

def _essayer_generer_programme_v2(order_id, order):
    """Phase 12/16 : tente de générer automatiquement un `Program` (nouveau
    moteur V2, phases 6-11) dès qu'une commande devient payée. Appelée aux
    3 points où une commande passe à "payée" : accès gratuit immédiat
    (`create_checkout_session`), vérification directe Stripe au retour sur
    `/payment-success`, et webhook Stripe asynchrone.

    Ne bloque et ne casse JAMAIS le flux de paiement existant : toute erreur
    est absorbée ici (journalisée), la commande reste valide et payée même
    si cette étape échoue — conformément à la consigne explicite de cette
    phase ("ne jamais remplacer la création de commande/validation
    paiement/stockage legacy"). Si aucun email n'est disponible pour cette
    commande, le programme n'est simplement pas généré maintenant : il
    pourra l'être plus tard via `program_service.generate_user_program()`
    dès qu'un email sera connu (jamais de blocage du paiement pour cette
    raison)."""
    try:
        email = order_migration._resolve_email(order)
        if not email:
            return
        program_service.generate_user_program(email, order.get("data") or {})
    except Exception:
        app.logger.exception(
            "Génération automatique du programme V2 (phase 12) : échec non "
            "bloquant pour order_id=%s", order_id,
        )


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.get_json(silent=True) or {}
    error, profile, nutrition, program, cardio, lifestyle = _build_everything(data)
    if error:
        return error

    formule = _normalize_formule(data)
    code_promo = (data.get("code_promo") or "").strip()
    code_promo_normalized = re.sub(r"\s+", "", code_promo).upper()

    is_free = False
    discount_pct = 0.0
    commission_pct = 0.0
    order_code_promo = code_promo

    if code_promo_normalized and code_promo_normalized == re.sub(r"\s+", "", OWNER_ACCESS_CODE).upper():
        # Accès illimité réservé au propriétaire du site : ne touche jamais aux
        # codes promo influenceurs/amis, pas de suivi de parrainage/commission.
        is_free = True
        order_code_promo = ""
    elif code_promo:
        # Règle du parrainage : le tout premier usage d'un code est gratuit (le
        # bénéficiaire teste son propre programme). Une fois cet essai consommé, le
        # même code donne une réduction (discount_pct) à la personne parrainée et
        # une commission (commission_pct) à son propriétaire. `claim_free_trial`
        # réserve l'essai gratuit de façon atomique pour éviter qu'un double-clic
        # ne le consomme deux fois.
        promo_entry = promo_codes.get_code(code_promo)
        if promo_entry and promo_entry.get("active", True):
            commission_pct = promo_entry.get("commission_pct", promo_codes.DEFAULT_COMMISSION_PCT)
            if not promo_entry.get("free_claimed", False) and promo_codes.claim_free_trial(code_promo):
                is_free = True
            else:
                discount_pct = promo_entry.get("discount_pct", promo_codes.DEFAULT_DISCOUNT_PCT)

    order_id = orders.create_order(data, formule, order_code_promo, free=is_free,
                                    discount_pct=discount_pct, commission_pct=commission_pct)

    if is_free:
        _essayer_generer_programme_v2(order_id, orders.get_order(order_id))
        return jsonify({
            "free": True,
            "order_id": order_id,
            "redirect_url": url_for("payment_success", order_id=order_id),
        })

    if not stripe_client.is_configured():
        return _error(
            "Le paiement en ligne n'est pas encore configuré sur ce site "
            "(clé Stripe manquante côté serveur). Contacte l'administrateur du site.",
            503,
        )

    success_url = url_for("payment_success", order_id=order_id, _external=True) + "&session_id={CHECKOUT_SESSION_ID}"
    cancel_url = url_for("payment_cancel", order_id=order_id, _external=True)

    try:
        checkout_session = stripe_client.create_checkout_session(
            order_id, formule, success_url, cancel_url, discount_pct=discount_pct
        )
    except stripe_client.StripeNotConfiguredError as e:
        return _error(str(e), 503)
    except Exception as e:
        return _error(f"Erreur lors de la création du paiement : {e}", 502)

    orders.set_stripe_session(order_id, checkout_session.id)

    return jsonify({
        "free": False, "order_id": order_id, "checkout_url": checkout_session.url,
        "discount_pct": discount_pct,
    })


@app.route("/payment-success")
def payment_success():
    order_id = request.args.get("order_id", "")
    session_id = request.args.get("session_id", "")
    order = orders.get_order(order_id)
    if not order:
        return render_template("payment_cancel.html", message="Commande introuvable."), 404

    if not order.get("paid") and session_id and stripe_client.is_configured():
        # Vérification directe auprès de Stripe : filet de sécurité si le webhook
        # n'est pas encore arrivé (ou pas configuré) au moment de la redirection.
        try:
            checkout_session = stripe_client.retrieve_session(session_id)
            paid_ok = checkout_session.get("payment_status") == "paid" or checkout_session.get("status") == "complete"
            same_order = checkout_session.get("client_reference_id") == order_id
            if paid_ok and same_order:
                orders.mark_paid(order_id, stripe_session_id=session_id,
                                  stripe_subscription_id=checkout_session.get("subscription"))
                order = orders.get_order(order_id)
                _essayer_generer_programme_v2(order_id, order)
        except Exception:
            pass

    if not order.get("paid"):
        return render_template(
            "payment_cancel.html",
            message="Paiement non confirmé pour le moment. Si tu viens de payer, réessaie "
                    "dans quelques secondes ou contacte le support.",
            order_id=order_id,
        ), 402

    # Phase 22/24 : émet un jeton d'accès personnel + connecte automatiquement
    # l'acheteur (session Flask) à l'instant précis où le paiement vient
    # d'être confirmé — même frontière de confiance que le téléchargement PDF
    # par order_id déjà en place, jamais une nouvelle hypothèse de sécurité.
    # Enveloppé pour ne JAMAIS bloquer l'affichage de cette page en cas
    # d'échec (même garantie que `_essayer_generer_programme_v2`, phase 12) :
    # le paiement/téléchargement reste indépendant de l'authentification.
    access_token = None
    try:
        email = order_migration._resolve_email(order)
        if email:
            # Filet de sécurité (retour Samy, prompt hors 24 phases : "je
            # veux que les clients puisse également retrouver leur
            # programme directement sur le site par précautions", #154) :
            # `_essayer_generer_programme_v2` n'est normalement déclenché
            # qu'au moment où une commande PASSE à "payée" (webhook Stripe,
            # accès gratuit immédiat, ou la vérification directe ci-dessus
            # dans CETTE route) — si l'e-mail n'était pas encore résolvable
            # à ce moment-là (webhook arrivé avant que Stripe ait confirmé
            # l'email, panne réseau ponctuelle...), le Program n'a jamais
            # été généré et resterait invisible sur /mon-compte et
            # /my-program malgré un paiement bien confirmé. On retente donc
            # ici, uniquement si aucun programme n'existe encore pour cet
            # email : sans risque de doublon si une tentative précédente a
            # en fait réussi entre-temps (`create_program_from_result`
            # déduplique déjà une régénération strictement identique, cf.
            # logic/program_repository.py, jamais modifié ici).
            if program_service.get_user_current_program(email) is None:
                _essayer_generer_programme_v2(order_id, order)
            user = program_service.get_or_create_user_for_email(email)
            access_token = auth.issue_token_for_user(user)
            auth.login(user)
    except Exception:
        app.logger.exception(
            "Émission du jeton d'accès personnel (phase 22) : échec non "
            "bloquant pour order_id=%s", order_id,
        )

    return render_template("payment_success.html", order_id=order_id, access_token=access_token)


@app.route("/payment-cancel")
def payment_cancel():
    order_id = request.args.get("order_id", "")
    return render_template("payment_cancel.html", message="Paiement annulé.", order_id=order_id)


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe_client.construct_webhook_event(payload, sig_header)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if event["type"] == "checkout.session.completed":
        checkout_session = event["data"]["object"]
        order_id = checkout_session.get("client_reference_id") or (checkout_session.get("metadata") or {}).get("order_id")
        if order_id:
            orders.mark_paid(
                order_id,
                stripe_session_id=checkout_session.get("id"),
                stripe_subscription_id=checkout_session.get("subscription"),
            )
            _essayer_generer_programme_v2(order_id, orders.get_order(order_id))

    return jsonify({"received": True})


def _record_commission_if_needed(order_id, order, data):
    """Enregistre l'utilisation du code promo dans le grand livre (logic.promo_codes)
    une fois le paiement confirmé — jamais avant, pour ne pas compter un paiement
    abandonné comme un parrainage. Utilise les conditions figées sur la commande
    (gratuit / réduction / commission) au moment de sa création, pas les réglages
    actuels du code, pour rester cohérent avec ce qui a réellement été payé."""
    code_promo = order.get("code_promo", "")
    if code_promo and not order.get("commission_recorded"):
        prix_plein = promo_codes.price_to_float(PRICES.get(order.get("formule", ""), ""))
        recorded = promo_codes.append_usage(
            code_promo,
            order.get("formule", ""),
            free=order.get("code_promo_free", False),
            prix_plein=prix_plein,
            discount_pct=order.get("code_promo_discount_pct", 0.0),
            commission_pct=order.get("code_promo_commission_pct", 0.0),
            prenom=data.get("prenom", ""),
        )
        if recorded:
            orders.mark_commission_recorded(order_id)


@app.route("/order-preview/<order_id>")
def order_preview(order_id):
    """Comme /generate-preview, mais à partir d'une commande déjà payée : permet de
    proposer l'écran de révision APRÈS paiement (sur la page de confirmation), pour
    ajuster le programme sans repasser par le questionnaire ni repayer."""
    order = orders.get_order(order_id)
    if not order or not order.get("paid"):
        return _error("Commande introuvable ou paiement non confirmé.", 404)

    error, profile, nutrition, program, cardio, lifestyle = _build_everything(order["data"])
    if error:
        return error

    return jsonify(_preview_json(nutrition, program, cardio))


@app.route("/download/<order_id>", methods=["GET", "POST"])
def download_order(order_id):
    """Génère (GET) ou régénère (POST, avec des exercices/séances remplacés suite à
    l'écran de révision) le PDF d'une commande payée. Ne redemande jamais de
    paiement : la commande une fois payée reste modifiable librement."""
    order = orders.get_order(order_id)
    if not order or not order.get("paid"):
        return _error("Commande introuvable ou paiement non confirmé.", 404)

    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        orders.update_order_data(
            order_id,
            exercices_rejetes=payload.get("exercices_rejetes"),
            cardio_rejets=payload.get("cardio_rejets"),
        )
        order = orders.get_order(order_id)

    data = order["data"]
    error, profile, nutrition, program, cardio, lifestyle = _build_everything(data)
    if error:
        return error

    _record_commission_if_needed(order_id, order, data)

    buffer = io.BytesIO()
    generate_pdf(
        buffer, profile, nutrition, program, cardio, lifestyle,
        include_nutrition=_include_nutrition(_normalize_formule(data)),
    )
    buffer.seek(0)

    filename = "programme_personnalise.pdf"
    return send_file(buffer, mimetype="application/pdf",
                      as_attachment=True, download_name=filename)


def _login_required(view):
    """Phase 22/24 : même mécanique que `_admin_required` (session Flask,
    déjà en place pour le dashboard admin) — jamais une nouvelle façon de
    gérer une session, la même, appliquée à l'espace personnel utilisateur."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        utilisateur = auth.current_user()
        if utilisateur is None:
            return redirect(url_for("login_page", next=request.path))
        return view(utilisateur, *args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Phase 22/24 : connexion par jeton d'accès personnel (cf. logic/auth.py
    pour l'explication du choix — pas de mot de passe, pas d'email envoyé,
    aucune infrastructure d'envoi d'email n'existant dans ce projet)."""
    if auth.current_user() is not None:
        return redirect(url_for("mon_compte"))

    error = None
    if request.method == "POST":
        token = request.form.get("token", "")
        utilisateur = auth.verify_token(token)
        if utilisateur is not None:
            auth.login(utilisateur)
            next_url = request.form.get("next") or url_for("mon_compte")
            return redirect(next_url)
        # Message volontairement générique : ne jamais révéler si un jeton
        # existe ou non (protection contre l'énumération/le brute force).
        error = "Jeton d'accès invalide ou expiré."

    return render_template("login.html", error=error, next=request.args.get("next", ""))


@app.route("/logout")
def logout_page():
    auth.logout()
    return redirect(url_for("landing"))


@app.route("/contact", methods=["GET", "POST"])
def contact_page():
    """Retour Samy (prompt hors 24 phases) : "je veux également qu'il puisse
    me laisser un message directement sur le site afin que au moindre
    problème il y'ai une réponse." Réponse validée : "Dans le dashboard admin
    (Recommandé)" — aucun envoi d'email, le message atterrit uniquement dans
    /admin/messages (cf. logic/contact_messages.py). Accessible sans
    connexion : un visiteur qui n'a pas encore acheté doit pouvoir écrire
    aussi bien qu'un client existant."""
    utilisateur = auth.current_user()
    message = None
    error = None

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip()
        texte = request.form.get("message", "").strip()
        if not texte:
            error = "Le message ne peut pas être vide."
        else:
            contact_messages.create_message(nom, email, texte)
            message = "Message envoyé. Il sera lu et traité au plus vite."

    return render_template(
        "contact.html", message=message, error=error,
        prenom_defaut=utilisateur.prenom if utilisateur else "",
        email_defaut=utilisateur.email if utilisateur else "",
    )


# Retour Samy : « supprime l'assistant IA, mets juste le formulaire pour que le
# client soit recontacté ». Les routes /assistant et /assistant/ask ont donc été
# retirées, ainsi que logic/support_agent.py et templates/assistant.html.
#
# /assistant reste déclarée ici en REDIRECTION permanente vers /contact : la
# page a été publiquement liée (pied de page, espace personnel, bulle de la
# page d'accueil) et peut avoir été mise en favori ou indexée. Renvoyer une 404
# à quelqu'un qui cherche à poser une question serait exactement l'inverse de
# l'objectif recherché.
@app.route("/assistant")
def assistant_page():
    return redirect(url_for("contact_page"), code=301)


@app.route("/mon-compte")
@_login_required
def mon_compte(utilisateur):
    """Phase 22/24 : espace personnel — programme actuel, historique des
    programmes, feedback exercices, évolution du profil (consigne). Lecture
    seule stricte (cf. `program_service.get_user_dashboard`)."""
    dashboard = program_service.get_user_dashboard(utilisateur)
    return render_template("mon_compte.html", utilisateur=utilisateur, dashboard=dashboard)


@app.route("/my-program")
@_login_required
def my_program(utilisateur):
    """Phase 12/16 (JSON par `?email=`) puis phase 22/24 (JSON par session)
    REMPLACÉE en phase 23/24 par une VRAIE INTERFACE HTML mobile-first
    (consigne : "Créer une interface : /my-program") — séances, exercices,
    séries, répétitions, repos, conseils, et les 4 boutons de feedback
    ("J'ai réalisé"/"Trop facile"/"Trop difficile"/"Douleur") qui appellent
    `/my-program/action` en AJAX (cf. static/my_program.js).

    Cette route ne fait QUE lire/afficher (`program_service.get_user_
    current_program`, phase 12, inchangé) : aucune écriture, aucune règle du
    moteur backend ici (cf. logic/program_interaction.py pour l'écriture,
    et sa docstring pour la liste exacte des fichiers moteur non touchés)."""
    program = program_service.get_user_current_program(utilisateur.email)
    return render_template("my_program.html", utilisateur=utilisateur, program=program)


@app.route("/my-program/action", methods=["POST"])
def my_program_action():
    """Phase 23/24 : enregistre un usage réalisé (`ExerciseUsageLog`) ou un
    feedback exercice (`ExerciseFeedback`) depuis l'interface `/my-program`
    (cf. logic/program_interaction.py, seul module qui écrit ces tables ici
    — aucune logique de recommandation dans cette route ni dans ce module).
    Route JSON (401 explicite si non connecté, pas de redirection HTML,
    inadapté à un appel `fetch()`)."""
    utilisateur = auth.current_user()
    if utilisateur is None:
        return _error("Non authentifié.", 401)

    payload = request.get_json(silent=True) or {}
    exercise_id = (payload.get("exercise_id") or "").strip()
    action = (payload.get("action") or "").strip()

    programme_actuel = program_service.get_user_current_program(utilisateur.email)
    program_id = programme_actuel.id if programme_actuel else None

    try:
        program_interaction.record_exercise_action(
            utilisateur.id, exercise_id, action, program_id=program_id
        )
    except ValueError as e:
        return _error(str(e), 400)

    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Dashboard admin : gestion des codes promo / parrainage.
# Accès protégé par mot de passe (session Flask). Permet de créer un code pour
# un ami / un influenceur, de voir combien de personnes il a ramenées et la
# commission indicative due (le versement reste manuel, le site n'ayant pas de
# paiement intégré).
# ---------------------------------------------------------------------------

def _admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            next_url = request.form.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        error = "Mot de passe incorrect."

    return render_template("admin_login.html", error=error, next=request.args.get("next", ""))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard", methods=["GET", "POST"])
@_admin_required
def admin_dashboard():
    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action", "create")

        if action == "create":
            owner_name = request.form.get("owner_name", "").strip()
            owner_email = request.form.get("owner_email", "").strip()
            code_wanted = request.form.get("code", "").strip()
            notes = request.form.get("notes", "").strip()
            try:
                commission_pct = float(request.form.get("commission_pct", promo_codes.DEFAULT_COMMISSION_PCT))
            except ValueError:
                commission_pct = promo_codes.DEFAULT_COMMISSION_PCT
            try:
                discount_pct = float(request.form.get("discount_pct", promo_codes.DEFAULT_DISCOUNT_PCT))
            except ValueError:
                discount_pct = promo_codes.DEFAULT_DISCOUNT_PCT

            code, err = promo_codes.create_code(
                owner_name, owner_email, code_wanted or None,
                commission_pct=commission_pct, discount_pct=discount_pct, notes=notes,
            )
            if err:
                error = err
            else:
                message = f"Code « {code} » créé pour {owner_name}. Le premier programme est gratuit ; ensuite -{discount_pct:g}% pour la personne parrainée et {commission_pct:g}% de commission."

        elif action == "toggle":
            code = request.form.get("code", "")
            entry = promo_codes.get_code(code)
            if entry:
                promo_codes.set_active(code, not entry.get("active", True))
                message = f"Statut du code « {code} » mis à jour."

        elif action == "reset_free":
            code = request.form.get("code", "")
            if promo_codes.reset_free_trial(code):
                message = f"Essai gratuit réinitialisé pour le code « {code} »."

        elif action == "delete":
            code = request.form.get("code", "")
            if promo_codes.delete_code(code):
                message = f"Code « {code} » supprimé."

    codes = promo_codes.list_codes_with_stats()
    totals = {
        "nb_codes": len(codes),
        "nb_uses": sum(c["nb_uses"] for c in codes),
        "nb_referrals": sum(c["nb_referrals"] for c in codes),
        "ca_total": round(sum(c["ca_total"] for c in codes), 2),
        "commission_due": round(sum(c["commission_due"] for c in codes), 2),
    }

    return render_template(
        "admin_dashboard.html",
        codes=codes,
        totals=totals,
        message=message,
        error=error,
        default_commission=promo_codes.DEFAULT_COMMISSION_PCT,
        default_discount=promo_codes.DEFAULT_DISCOUNT_PCT,
    )


# ---------------------------------------------------------------------------
# Dashboard admin : suivi des programmes générés/envoyés (retour Samy, prompt
# hors 24 phases : "je veux également pouvoir avoir un suivi de tout les
# programmes qui sont faits et à qui ils sont envoyé"). Réponse validée par
# Samy pour ce périmètre : "Liste + consultation/téléchargement du PDF" (pas
# de recherche/filtre avancé pour cette phase). Source de vérité : orders.json
# (logic/orders.py), déjà la seule trace fiable de "qui a reçu quoi" — la
# couche Program/User (base relationnelle) n'est peuplée que pour les
# commandes migrées (logic/order_migration.py), donc pas encore exhaustive.
# ---------------------------------------------------------------------------

def _admin_program_rows():
    """Construit la liste des commandes pour le dashboard admin, la plus
    récente en premier. Un email non résolvable (essai gratuit/accès
    propriétaire sans email connu, cf. docstring order_migration._resolve_email)
    n'est jamais une erreur bloquante : affiché comme "?" plutôt que de faire
    échouer toute la liste."""
    store = orders._load()
    rows = []
    for order_id, order in store["orders"].items():
        data = order.get("data") or {}
        try:
            email = order_migration._resolve_email(order)
        except Exception:
            email = None
        rows.append({
            "order_id": order_id,
            "created_at": order.get("created_at", ""),
            "prenom": data.get("prenom") or "?",
            "email": email or "?",
            "formule": order.get("formule", "?"),
            "paid": bool(order.get("paid")),
            "free": bool(order.get("free")),
            "code_promo": order.get("code_promo") or "",
        })
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


@app.route("/admin/programmes")
@_admin_required
def admin_programmes():
    return render_template("admin_programs.html", rows=_admin_program_rows())


@app.route("/admin/programmes/<order_id>/pdf")
@_admin_required
def admin_programme_pdf(order_id):
    """Consultation/téléchargement du PDF d'une commande depuis le dashboard
    admin (même génération que /download/<order_id>, jamais une logique
    dupliquée). Ouvert en ligne (as_attachment=False) plutôt qu'en
    téléchargement forcé : permet à la fois la consultation directe dans le
    navigateur ET le téléchargement via son propre bouton, cf. réponse Samy
    "Liste + consultation/téléchargement du PDF"."""
    order = orders.get_order(order_id)
    if not order or not (order.get("paid") or order.get("free")):
        return _error("Commande introuvable ou programme jamais livré.", 404)

    data = order["data"]
    error, profile, nutrition, program, cardio, lifestyle = _build_everything(data)
    if error:
        return error

    buffer = io.BytesIO()
    generate_pdf(
        buffer, profile, nutrition, program, cardio, lifestyle,
        include_nutrition=_include_nutrition(_normalize_formule(data)),
    )
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=False,
                      download_name="programme_personnalise.pdf")


# ---------------------------------------------------------------------------
# Dashboard admin : messages envoyés via /contact (retour Samy, prompt hors
# 24 phases : "je veux également qu'il puisse me laisser un message
# directement sur le site afin que au moindre problème il y'ai une réponse").
# Réponse validée par Samy : "Dans le dashboard admin (Recommandé)".
# ---------------------------------------------------------------------------

@app.route("/admin/messages", methods=["GET", "POST"])
@_admin_required
def admin_messages():
    if request.method == "POST":
        action = request.form.get("action", "")
        message_id = request.form.get("message_id", "")
        if action == "mark_read":
            contact_messages.mark_read(message_id, True)
        elif action == "mark_unread":
            contact_messages.mark_read(message_id, False)
        elif action == "delete":
            contact_messages.delete_message(message_id)

    rows = contact_messages.list_messages()
    return render_template("admin_messages.html", rows=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
