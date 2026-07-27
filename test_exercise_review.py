# -*- coding: utf-8 -*-
"""
Tests du workflow de revue humaine (phase 14/16) —
logic/exercise_review.py et logic/exercise_quality.py.

Prompt final (hors 24 phases) : catalogue professionnel (486 exercices) —
exercise_id et comptes mis à jour en conséquence."""
import copy

import app as appmod
from logic.exercise_catalog_import import import_enriched_catalog
from logic.exercise_quality import validate_exercise_quality
from logic.exercise_review import (
    ExerciseReviewError,
    approve_exercise,
    get_pending_reviews,
    reject_exercise,
    update_exercise_review,
)
from logic.models import Exercise


def run():
    with appmod.app.app_context():
        resultat_import = import_enriched_catalog()
        assert resultat_import["errors"] == []
        total = Exercise.query.count()

        # --------------------------------------------------------------
        # 1) exercice pending -> approve -> statut correct
        # --------------------------------------------------------------
        cible1 = "developpe_couche_barre_pecs"
        avant = Exercise.query.get(cible1)
        assert avant.needs_review is True
        assert avant.review_status == "pending"

        approuve = approve_exercise(cible1, reviewer="samy")
        assert approuve.needs_review is False
        assert approuve.review_status == "approved"
        assert approuve.validated_at is not None
        assert approuve.validated_by == "samy"
        assert cible1 not in {e.exercise_id for e in get_pending_reviews()}
        print(f"OK 1 — approve_exercise('{cible1}') : needs_review=False, review_status='approved', validated_by='samy'")

        # --------------------------------------------------------------
        # 2) exercice pending -> reject -> raison conservée
        # --------------------------------------------------------------
        cible2 = "squat_arriere_barre_back_squat_quadriceps"
        rejete = reject_exercise(cible2, reason="Difficulty_level à revérifier avec un coach", reviewer="samy")
        assert rejete.review_status == "rejected"
        assert rejete.review_notes == "Difficulty_level à revérifier avec un coach"
        assert rejete.validated_by == "samy"
        assert rejete.validated_at is not None
        # needs_review n'est volontairement PAS modifié par un rejet (cf.
        # docstring exercise_review.py) : l'exercice reste "à revoir".
        assert rejete.needs_review is True
        assert cible2 in {e.exercise_id for e in get_pending_reviews()}

        try:
            reject_exercise("un_id_qui_nexiste_pas", reason="peu importe")
            raise AssertionError("reject_exercise aurait dû lever ExerciseReviewError pour un id inconnu")
        except ExerciseReviewError:
            pass
        print(f"OK 2 — reject_exercise('{cible2}') : raison conservée dans review_notes, needs_review inchangé (True)")

        # --------------------------------------------------------------
        # 3) modification manuelle d'un champ -> validation correcte
        # --------------------------------------------------------------
        cible3 = "curl_barre_droite_biceps"
        avant3 = Exercise.query.get(cible3)
        assert avant3.technical_complexity != 5

        corrige = update_exercise_review(cible3, {"technical_complexity": 5, "stability_demand": "eleve"})
        assert corrige.technical_complexity == 5
        assert corrige.stability_demand == "eleve"
        # une correction n'est pas une décision de revue : needs_review/review_status inchangés
        assert corrige.needs_review is True
        assert corrige.review_status == "pending"

        # correction invalide : rejetée intégralement (aucun champ modifié)
        avant_invalide = Exercise.query.get(cible3).technical_complexity
        try:
            update_exercise_review(cible3, {"technical_complexity": 99})
            raise AssertionError("technical_complexity=99 aurait dû être rejeté")
        except ExerciseReviewError:
            pass
        assert Exercise.query.get(cible3).technical_complexity == avant_invalide

        # champ non corrigeable via cette fonction
        try:
            update_exercise_review(cible3, {"name": "Nouveau nom"})
            raise AssertionError("le champ 'name' n'est pas dans CHAMPS_CORRIGEABLES, devait être refusé")
        except ExerciseReviewError:
            pass
        print(f"OK 3 — update_exercise_review('{cible3}') : correction valide appliquée, correction invalide rejetée intégralement")

        # --------------------------------------------------------------
        # 4) exercice incohérent détecté par le quality checker
        # --------------------------------------------------------------
        fiche_incoherente = {
            "exercise_id": "test_incoherent",
            "pattern": "squat",  # historiquement associé à "quadriceps" dans le catalogue legacy
            "muscle_principal": "pecs",  # incompatible
            "movement_type": "squat",
            "equipment": ["objet_inconnu"],
            "difficulty_level": "avance",
            "technical_complexity": 4,
            "stability_demand": "eleve",
            "joint_stress": {"genou": 3},
            "objectifs_adaptes": {},  # vide
            "score_tension_mecanique": 8,
            "score_contraction_max": 2,
            "potentiel_hypertrophique": 10,  # loin de la moyenne (8+2)/2=5
            "contre_indications": [],
            "substitutes": [],
            "actif": True,
        }
        rapport4 = validate_exercise_quality(fiche_incoherente)
        assert rapport4["valid"] is False
        assert rapport4["errors"], "muscle_principal incompatible avec le pattern doit être bloquant"
        assert any("objectifs_adaptes" in w for w in rapport4["warnings"])
        assert any("joint_stress maximal" in w for w in rapport4["warnings"])
        assert any("potentiel_hypertrophique" in w for w in rapport4["warnings"])
        assert any("equipment" in w for w in rapport4["warnings"])
        print(f"OK 4 — fiche incohérente détectée : {len(rapport4['errors'])} erreur(s), {len(rapport4['warnings'])} avertissement(s)")

        # --------------------------------------------------------------
        # 5) exercice valide accepté sans warning bloquant
        # --------------------------------------------------------------
        exercice_valide = Exercise.query.get("developpe_couche_barre_pecs")
        rapport5 = validate_exercise_quality(exercice_valide)
        assert rapport5["valid"] is True
        assert rapport5["errors"] == []
        print(f"OK 5 — exercice valide ('developpe_couche_barre_pecs') : valid=True, 0 erreur, {len(rapport5['warnings'])} avertissement(s)")

        # --------------------------------------------------------------
        # 6) catalogue complet : validation globale, aucun crash
        # --------------------------------------------------------------
        tous = Exercise.query.all()
        assert len(tous) == total == 486
        nb_erreurs_total = 0
        nb_avertissements_total = 0
        for ex in tous:
            rapport = validate_exercise_quality(ex)
            nb_erreurs_total += len(rapport["errors"])
            nb_avertissements_total += len(rapport["warnings"])
        print(f"OK 6 — catalogue complet ({len(tous)} exercices) : aucun crash, "
              f"{nb_erreurs_total} erreur(s) totale(s), {nb_avertissements_total} avertissement(s) au total")

    print("\nTOUS LES TESTS DU WORKFLOW DE REVUE SONT PASSÉS")


if __name__ == "__main__":
    run()
