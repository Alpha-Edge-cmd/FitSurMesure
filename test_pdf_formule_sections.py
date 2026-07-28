# -*- coding: utf-8 -*-
"""Vérifie la séparation musculation/cardio <-> alimentation par formule
(prompt hors 24 phases, retour Samy en conditions réelles) :

"Dans le programme musculation seul ne mets pas de programme alimentation
et dans le programme cardio pareil et créer un programme alimentation
moins cher que le programme cardio avec également un questionnaire adapté
ne fais pas la même erreur."

Avant ce correctif, `pdf_generator.generate_pdf` incluait TOUJOURS la partie
1 (Alimentation), quelle que soit la formule choisie -- ce test vérifie que
ce n'est désormais plus le cas pour "musculation" et "cardio" seuls, tout en
restant présent pour la nouvelle offre "nutrition" et pour "les_deux"."""
import io

import pdfplumber

import app as appmod
from app import PRICES
from test_helpers import ensure_test_promo_code, generate_via_payment

client = appmod.app.test_client()
ensure_test_promo_code()

MARQUEUR_ALIMENTATION = "PARTIE ALIMENTAIRE"
MARQUEUR_MUSCULATION = "PARTIE MUSCULAIRE"
MARQUEUR_CARDIO = "PARTIE CARDIO"


def payload_de_base(**kwargs):
    defaults = dict(
        consentement_rgpd=True, prenom="TestFormule", date_naissance="1992-05-10",
        sexe="Homme", poids=78, taille="178", niveau_musculation="Intermédiaire",
        objectif_principal="Prise de muscle", composition_corporelle="Je ne sais pas",
        restriction_alimentaire="Aucune", niveau_activite_quotidien="modere",
        equipement="Salle complète", duree_seance="1h - 1h30",
        frequence_entrainement=3, split_preference="auto",
        cardio_types=["Course"], cardio_frequence="2x / semaine",
        objectif_cardio="Améliorer mon endurance générale", niveau_cardio="Intermédiaire",
    )
    defaults.update(kwargs)
    return defaults


def texte_pdf(resp):
    with pdfplumber.open(io.BytesIO(resp.get_data())) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def run():
    # 1) Musculation seul : pas d'alimentation, musculation présente, pas de cardio.
    resp = generate_via_payment(client, payload_de_base(formule="musculation"))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    texte = texte_pdf(resp)
    assert MARQUEUR_ALIMENTATION not in texte, "Alimentation ne devrait pas apparaître pour la formule musculation seule"
    assert MARQUEUR_MUSCULATION in texte
    assert MARQUEUR_CARDIO not in texte
    print("OK 1 — formule musculation seule : pas de partie alimentation")

    # 2) Cardio seul : pas d'alimentation, cardio présent, pas de musculation.
    resp = generate_via_payment(client, payload_de_base(formule="cardio"))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    texte = texte_pdf(resp)
    assert MARQUEUR_ALIMENTATION not in texte, "Alimentation ne devrait pas apparaître pour la formule cardio seule"
    assert MARQUEUR_CARDIO in texte
    assert MARQUEUR_MUSCULATION not in texte
    print("OK 2 — formule cardio seule : pas de partie alimentation")

    # 3) Nutrition seul (nouvelle offre) : alimentation présente, ni musculation ni cardio.
    resp = generate_via_payment(client, payload_de_base(formule="nutrition"))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    texte = texte_pdf(resp)
    assert MARQUEUR_ALIMENTATION in texte, "Alimentation devrait apparaître pour la nouvelle formule nutrition"
    assert MARQUEUR_MUSCULATION not in texte
    assert MARQUEUR_CARDIO not in texte
    print("OK 3 — formule nutrition seule : alimentation présente, ni musculation ni cardio")

    # 4) Complet : les trois parties présentes (comportement historique préservé).
    resp = generate_via_payment(client, payload_de_base(formule="les_deux"))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    texte = texte_pdf(resp)
    assert MARQUEUR_ALIMENTATION in texte
    assert MARQUEUR_MUSCULATION in texte
    assert MARQUEUR_CARDIO in texte
    print("OK 4 — formule complète : alimentation + musculation + cardio, comportement inchangé")

    # 5) Tarif nutrition strictement moins cher que cardio (retour Samy explicite).
    def _to_float(prix_label):
        return float(prix_label.replace("€", "").replace(",", ".").split("/")[0].strip())

    assert _to_float(PRICES["nutrition"]) < _to_float(PRICES["cardio"]), PRICES
    print(f"OK 5 — tarif nutrition ({PRICES['nutrition']}) < tarif cardio ({PRICES['cardio']})")

    print("\nTOUS LES TESTS DE SÉPARATION ALIMENTATION/FORMULE SONT PASSÉS")


if __name__ == "__main__":
    run()
