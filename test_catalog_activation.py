# -*- coding: utf-8 -*-
"""
Tests de l'activation contrôlée du catalogue (phase 15/16) —
logic/exercise_catalog_service.py, logic/exercise_catalog_import.py
(auto_approve), logic/recommendation/catalog_provider.py.

Prompt final (hors 24 phases) : data/exercise_enrichment.json contient
désormais le nouveau catalogue professionnel (486 exercices) — les
exercise_id de référence et les comptes ci-dessous sont mis à jour en
conséquence. Le repli legacy (`get_recommendation_catalog()` sans aucun
exercice approuvé) reste, lui, inchangé à 111 : il reconstruit à la volée
l'ANCIEN catalogue depuis logic/exercises_db.py, indépendamment de ce
fichier JSON (cf. logic/recommendation/catalog_provider.py, jamais modifié)."""
import app as appmod
from logic.exercise_catalog_import import import_enriched_catalog
from logic.exercise_catalog_service import (
    get_active_exercises,
    get_catalog_status,
    get_exercise_by_id,
)
from logic.exercise_review import approve_exercise, reject_exercise
from logic.models import Exercise
from logic.recommendation.catalog_provider import get_recommendation_catalog


def run():
    with appmod.app.app_context():
        # Import par défaut : tout le catalogue en "pending" (comportement
        # historique de la phase 13, inchangé par défaut).
        resultat_import = import_enriched_catalog()
        assert resultat_import["errors"] == []
        assert Exercise.query.count() == 486

        # --------------------------------------------------------------
        # 1) exercice pending -> absent du catalogue moteur
        # --------------------------------------------------------------
        cible_pending = "curl_barre_droite_biceps"
        assert Exercise.query.get(cible_pending).review_status == "pending"
        assert cible_pending not in {e.exercise_id for e in get_active_exercises(include_pending=False)}
        # visible seulement si on demande explicitement les "pending"
        assert cible_pending in {e.exercise_id for e in get_active_exercises(include_pending=True)}
        print(f"OK 1 — exercice pending ('{cible_pending}') absent du catalogue par défaut, visible avec include_pending=True")

        # --------------------------------------------------------------
        # 2) exercice approved -> présent dans le catalogue moteur
        # --------------------------------------------------------------
        cible_approuvee = "developpe_couche_barre_pecs"
        approve_exercise(cible_approuvee, reviewer="samy")
        actifs_defaut = {e.exercise_id for e in get_active_exercises(include_pending=False)}
        assert cible_approuvee in actifs_defaut
        catalogue_moteur = get_recommendation_catalog()
        assert cible_approuvee in {getattr(e, "exercise_id") for e in catalogue_moteur}
        print(f"OK 2 — exercice approved ('{cible_approuvee}') présent dans get_active_exercises et get_recommendation_catalog")

        # --------------------------------------------------------------
        # 3) exercice rejected -> absent même si actif=True
        # --------------------------------------------------------------
        cible_rejetee = "squat_arriere_barre_back_squat_quadriceps"
        rejete = reject_exercise(cible_rejetee, reason="difficulty_level à revoir", reviewer="samy")
        assert rejete.actif is True  # jamais désactivé automatiquement
        assert cible_rejetee not in {e.exercise_id for e in get_active_exercises(include_pending=False)}
        assert cible_rejetee not in {e.exercise_id for e in get_active_exercises(include_pending=True)}
        assert cible_rejetee not in {getattr(e, "exercise_id") for e in get_recommendation_catalog()}
        # toujours consultable directement (revue), juste jamais exposé au moteur
        assert get_exercise_by_id(cible_rejetee) is not None
        print(f"OK 3 — exercice rejected ('{cible_rejetee}') absent partout du catalogue moteur, mais toujours consultable via get_exercise_by_id")

        # --------------------------------------------------------------
        # 4) ancien catalogue vide -> fallback legacy fonctionnel
        # --------------------------------------------------------------
        # Simule un catalogue V2 entièrement vidé de tout exercice approuvé
        # (aucune suppression ici : uniquement un update ciblé sur les seules
        # lignes "approved" -> "pending", cohérent avec "ne jamais supprimer
        # automatiquement un exercice" ; la ligne "rejected" du scénario 3
        # n'est volontairement pas touchée par ce filtre).
        from logic.db import db
        Exercise.query.filter_by(review_status="approved").update(
            {"review_status": "pending"}, synchronize_session=False
        )
        db.session.commit()
        assert get_active_exercises(include_pending=False) == []

        catalogue_fallback = get_recommendation_catalog()
        assert len(catalogue_fallback) > 0, "le repli legacy doit toujours fournir des exercices"
        premier = catalogue_fallback[0]
        assert hasattr(premier, "muscle_principal") and hasattr(premier, "joint_stress")
        print(f"OK 4 — aucun exercice approuvé : repli legacy actif, {len(catalogue_fallback)} exercices legacy fournis au moteur")

        # --------------------------------------------------------------
        # 5) réimport JSON après validation humaine -> aucune perte du statut approved
        # --------------------------------------------------------------
        approve_exercise(cible_approuvee, reviewer="samy")
        avant_reimport = Exercise.query.get(cible_approuvee)
        assert avant_reimport.review_status == "approved"

        resultat_reimport = import_enriched_catalog()  # auto_approve=False par défaut
        assert resultat_reimport["created"] == 0
        assert resultat_reimport["updated"] == 486

        apres_reimport = Exercise.query.get(cible_approuvee)
        assert apres_reimport.review_status == "approved", "le réimport ne doit jamais écraser une approbation humaine"
        assert apres_reimport.validated_by == "samy"
        # le rejet précédent doit également survivre au réimport
        assert Exercise.query.get(cible_rejetee).review_status == "rejected"
        print(f"OK 5 — réimport JSON : statut 'approved' de '{cible_approuvee}' et 'rejected' de '{cible_rejetee}' tous deux conservés")

        # --------------------------------------------------------------
        # 6) catalogue complet : status correct, aucun crash, provider filtré
        # --------------------------------------------------------------
        statut = get_catalog_status()
        assert statut["total"] == 486
        assert statut["approved"] == Exercise.query.filter_by(review_status="approved").count() == 1
        assert statut["rejected"] == Exercise.query.filter_by(review_status="rejected").count() == 1
        assert statut["pending"] == 486 - statut["approved"] - statut["rejected"]
        assert statut["needs_review"] == Exercise.query.filter_by(needs_review=True).count()

        catalogue_final = get_recommendation_catalog()
        exercise_ids_final = {getattr(e, "exercise_id") for e in catalogue_final}
        assert exercise_ids_final == {cible_approuvee}, "seul l'unique exercice approuvé doit être exposé au moteur"
        print(f"OK 6 — get_catalog_status() cohérent ({statut}), aucun crash, provider renvoie exactement {exercise_ids_final}")

    print("\nTOUS LES TESTS D'ACTIVATION DU CATALOGUE SONT PASSÉS")


if __name__ == "__main__":
    run()
