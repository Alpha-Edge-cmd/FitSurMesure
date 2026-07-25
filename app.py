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
from logic import promo_codes, orders, stripe_client

app = Flask(__name__)

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
PRICES = {
    "musculation": "14,99€",
    "cardio": "12,99€",
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


def _cardio_sessions(data):
    if data.get("pratique_cardio") != "Oui":
        return 0
    return _parse_sessions(data.get("cardio_frequence", ""))


def _autre_sport_sessions(data):
    if data.get("autre_sport") != "Oui":
        return 0
    return _parse_sessions(data.get("autre_sport_frequence", ""))


def _normalize_formule(data):
    formule = data.get("formule", "les_deux")
    if formule not in ("musculation", "cardio", "les_deux", "abonnement"):
        formule = "les_deux"
    return formule


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


def _build_everything(data):
    """Valide le questionnaire et construit profile/nutrition/program/cardio/lifestyle.
    Retourne (error_response, profile, nutrition, program, cardio, lifestyle).
    error_response est None si tout est valide. Partagé entre /generate (PDF) et
    /generate-preview (JSON, pour l'écran de révision \"je n'aime pas cet exercice\")."""
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
    signature = "|".join(str(x) for x in [
        data.get("prenom", ""), data.get("date_naissance", ""), poids, taille, data.get("sexe", ""),
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
        "autre_sport_type": data.get("autre_sport_type", ""),
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
        program_input = {
            "frequence_entrainement": frequence,
            "split_preference": data.get("split_preference", "auto"),
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
        temps_1km_raw = data.get("temps_1km")
        try:
            temps_1km = float(temps_1km_raw) if temps_1km_raw not in (None, "") else None
        except (TypeError, ValueError):
            temps_1km = None
        cardio_input = {
            "pratique_cardio": "Oui",
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
        except Exception:
            pass

    if not order.get("paid"):
        return render_template(
            "payment_cancel.html",
            message="Paiement non confirmé pour le moment. Si tu viens de payer, réessaie "
                    "dans quelques secondes ou contacte le support.",
            order_id=order_id,
        ), 402

    return render_template("payment_success.html", order_id=order_id)


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
    generate_pdf(buffer, profile, nutrition, program, cardio, lifestyle)
    buffer.seek(0)

    filename = "programme_personnalise.pdf"
    return send_file(buffer, mimetype="application/pdf",
                      as_attachment=True, download_name=filename)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
