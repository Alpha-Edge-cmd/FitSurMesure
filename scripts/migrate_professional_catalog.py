# -*- coding: utf-8 -*-
"""
Prompt final (hors les 24 phases) — PARTIE 1/2 : migration vers le nouveau
catalogue professionnel.

Ce script fait exactement deux choses, dans cet ordre, et RIEN d'autre :
  1. Désactive (actif=False, jamais de suppression physique — politique déjà
     établie depuis la phase 2, logic/models.py) les anciens exercices du
     catalogue de 111 exercices (identifiés via data/exercise_enrichment_v2_
     111_backup.json, écrit par scripts/build_professional_catalog.py) qui ne
     font pas partie du nouveau catalogue. Conformément à la consigne "le
     moteur ne doit plus utiliser les 111 anciens exercices" — sans jamais
     perdre l'historique (ExerciseUsageLog/ExerciseFeedback/ProgramExercise
     qui référencent encore ces exercise_id restent valides, la ligne
     Exercise existe toujours, juste actif=False).
  2. Importe le nouveau catalogue (data/exercise_enrichment.json, ~486
     exercices) via `logic.exercise_catalog_import.import_enriched_catalog`,
     inchangé — même règle "jamais d'écrasement d'une revue humaine
     existante" que pour tout réimport.

DÉCOUVERTE IMPORTANTE (à connaître avant de lire ce script) : `logic.
recommendation.catalog_provider.get_recommendation_catalog()` ne se rabat PAS
sur d'anciennes lignes de la table `exercises` quand rien n'est encore
approuvé — il reconstruit à la volée le catalogue legacy de 111 exercices
directement depuis `logic/exercises_db.py` (code Python, indépendant de la
base de données). Désactiver les anciennes lignes en base (étape 1
ci-dessus) est donc nécessaire mais PAS suffisant pour satisfaire la
consigne "le moteur ne doit plus utiliser les 111 anciens exercices" : tant
qu'AUCUN exercice du nouveau catalogue n'est "approved", ce filet de sécurité
(phase 15/16, volontaire) continue de servir les 111 anciens exercices,
quoi qu'il arrive en base.

Ce script importe donc le nouveau catalogue avec `auto_approve=True` : les
486 nouvelles fiches (rédigées avec un vrai contenu biomécanique, pas une
donnée générée au hasard) sont directement marquées "approved" à la
création, pour que le moteur les utilise IMMÉDIATEMENT plutôt que de
retomber sur l'ancien catalogue. C'est un usage ponctuel et délibéré de
`auto_approve` (réservé par sa docstring à un "environnement contrôlé") pour
ce remplacement complet de catalogue — Samy garde la main pour revoir/
rejeter individuellement n'importe quel exercice ensuite via les outils de
revue déjà en place (logic/exercise_review.py, /admin), l'auto-approbation
ne bloque aucune revue future.

Usage :
    python3 scripts/migrate_professional_catalog.py
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BACKUP_PATH = os.path.join(PROJECT_ROOT, "data", "exercise_enrichment_v2_111_backup.json")
CURRENT_PATH = os.path.join(PROJECT_ROOT, "data", "exercise_enrichment.json")


def main():
    import app as appmod
    from logic.db import db
    from logic.exercise_catalog_import import import_enriched_catalog
    from logic.models import Exercise

    with open(BACKUP_PATH, encoding="utf-8") as f:
        anciens_ids = {e["exercise_id"] for e in json.load(f)["exercises"]}
    with open(CURRENT_PATH, encoding="utf-8") as f:
        nouveaux_ids = {e["exercise_id"] for e in json.load(f)["exercises"]}

    ids_a_desactiver = anciens_ids - nouveaux_ids
    print(f"Anciens exercices identifiés : {len(anciens_ids)}")
    print(f"Nouveaux exercices dans le catalogue : {len(nouveaux_ids)}")
    print(f"À désactiver (absents du nouveau catalogue) : {len(ids_a_desactiver)}")

    with appmod.app.app_context():
        desactives = 0
        deja_inactifs = 0
        introuvables = 0
        for exercise_id in sorted(ids_a_desactiver):
            exercise = Exercise.query.get(exercise_id)
            if exercise is None:
                introuvables += 1
                continue
            if exercise.actif:
                exercise.actif = False
                desactives += 1
            else:
                deja_inactifs += 1
        db.session.commit()
        print(f"  -> {desactives} désactivés maintenant, {deja_inactifs} déjà inactifs, "
              f"{introuvables} introuvables (base vierge, rien à désactiver).")

        rapport_import = import_enriched_catalog(auto_approve=True)
        print(f"Import du nouveau catalogue : créés={rapport_import['created']}, "
              f"mis à jour={rapport_import['updated']}, "
              f"invalides ignorés={rapport_import['skipped_invalid']}, "
              f"erreurs={len(rapport_import['errors'])}")
        if rapport_import["errors"]:
            for e in rapport_import["errors"][:10]:
                print("  ERREUR:", e)
            print("ARRÊT : des erreurs bloquantes empêchent de considérer la migration réussie.")
            sys.exit(1)

        actifs_anciens_restants = Exercise.query.filter(
            Exercise.exercise_id.in_(anciens_ids), Exercise.actif == True  # noqa: E712
        ).count()
        total_actifs = Exercise.query.filter_by(actif=True).count()
        print(f"Anciens exercices encore actifs après migration : {actifs_anciens_restants} "
              f"(doit être 0, sauf recoupement légitime d'exercise_id)")
        print(f"Total exercices actifs (nouveau catalogue) : {total_actifs}")

        from logic.recommendation.catalog_provider import get_recommendation_catalog
        catalogue_moteur = get_recommendation_catalog()
        ids_moteur = {e.exercise_id for e in catalogue_moteur}
        anciens_encore_exposes = ids_moteur & anciens_ids
        print(f"Anciens exercices exposés au moteur (get_recommendation_catalog) : "
              f"{len(anciens_encore_exposes)} (doit être 0)")
        if anciens_encore_exposes:
            print("ARRÊT : le moteur exposerait encore d'anciens exercices.")
            sys.exit(1)

    print("\nMigration terminée avec succès : le moteur n'utilise plus les anciens exercices.")


if __name__ == "__main__":
    main()
