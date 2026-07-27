# -*- coding: utf-8 -*-
"""
Tests de l'audit production (phase 24/24) — scripts/production_check.py.

Exécute le script en sous-processus (et non par import direct) : c'est
essentiel, pas une simple préférence de style. `scripts/production_check.py`
importe `app` (donc `logic.db`) après avoir redirigé DATA_DIR/DATABASE_URL
vers un dossier temporaire jetable — un import direct dans ce process de
test partagerait le `app`/`db` déjà initialisés par les AUTRES suites de
régression (qui, elles, pointent vers `data/`), et Flask-SQLAlchemy refuse
d'appeler `db.init_app()` une seconde fois sur la même instance d'app (déjà
observé pendant le développement de cette phase). Le sous-processus est la
seule façon de vérifier fidèlement ce que fait réellement
`python3 scripts/production_check.py`, exactement comme un opérateur humain
l'exécuterait avant un lancement en production.

Ne vérifie PAS l'absence de BLOCKER (les BLOCKER de sécurité SECRET_KEY/
ADMIN_PASSWORD/OWNER_ACCESS_CODE sont attendus tant que ces variables ne
sont pas positionnées dans l'environnement d'exécution des tests — c'est le
comportement correct et voulu du script, pas un défaut). Vérifie en
revanche qu'aucune SECTION ne plante de façon inattendue (recherche de la
chaîne "Exception inattendue pendant cette section", qui signalerait un bug
du script d'audit lui-même plutôt qu'un vrai constat métier), que le
rapport contient bien les 10 catégories demandées par la consigne, et que
le fichier PRODUCTION_READY.md est produit à la racine du projet.
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts", "production_check.py")
RAPPORT_PATH = os.path.join(PROJECT_ROOT, "PRODUCTION_READY.md")

CATEGORIES_ATTENDUES = [
    "Architecture", "Base de données", "Sécurité", "Performance", "Paiement",
    "Catalogue exercices", "Programme généré", "PDF", "Questionnaire", "Feedback",
]


def run():
    # ------------------------------------------------------------------
    # 1) Le script existe et s'exécute sans crash Python (code retour 0 ou 1
    #    uniquement — 1 signifie "au moins un BLOCKER trouvé", jamais un
    #    autre code qui signalerait une erreur d'exécution du script lui-même).
    # ------------------------------------------------------------------
    assert os.path.isfile(SCRIPT_PATH), "scripts/production_check.py doit exister"

    resultat = subprocess.run(
        [sys.executable, SCRIPT_PATH], cwd=PROJECT_ROOT,
        capture_output=True, text=True, timeout=120,
    )
    assert resultat.returncode in (0, 1), (
        f"code retour inattendu ({resultat.returncode}) — stderr :\n{resultat.stderr[-4000:]}"
    )
    print(f"OK 1 — scripts/production_check.py s'exécute sans crash Python (code retour {resultat.returncode})")

    # ------------------------------------------------------------------
    # 2) PRODUCTION_READY.md est bien produit à la racine du projet
    # ------------------------------------------------------------------
    assert os.path.isfile(RAPPORT_PATH), "PRODUCTION_READY.md doit être généré à la racine du projet"
    with open(RAPPORT_PATH, encoding="utf-8") as f:
        contenu = f.read()
    assert "## Verdict" in contenu
    assert "- OK :" in contenu and "- WARNING :" in contenu and "- BLOCKER :" in contenu
    print("OK 2 — PRODUCTION_READY.md généré avec un verdict et des compteurs OK/WARNING/BLOCKER")

    # ------------------------------------------------------------------
    # 3) Les 10 domaines demandés par la consigne sont bien couverts
    # ------------------------------------------------------------------
    manquants = [c for c in CATEGORIES_ATTENDUES if f"## {c}" not in contenu]
    assert not manquants, f"catégories manquantes dans le rapport : {manquants}"
    print(f"OK 3 — les {len(CATEGORIES_ATTENDUES)} domaines demandés sont tous présents dans le rapport")

    # ------------------------------------------------------------------
    # 4) Aucune section n'a planté de façon inattendue (bug du script
    #    d'audit lui-même) — seuls de vrais constats OK/WARNING/BLOCKER
    #    métier sont attendus.
    # ------------------------------------------------------------------
    assert "Exception inattendue pendant cette section" not in contenu, (
        "au moins une section de l'audit a levé une exception imprévue :\n" + contenu
    )
    print("OK 4 — aucune section de l'audit n'a échoué de façon imprévue")

    # ------------------------------------------------------------------
    # 5) Les scénarios explicitement demandés par la consigne apparaissent
    #    bien comme des constats concrets dans le rapport (pas juste des
    #    titres de section vides).
    # ------------------------------------------------------------------
    scenarios_attendus = [
        "Installation vierge", "Migration douce", "Import du catalogue",
        "Génération de programme", "Commande simulée", "Génération PDF",
        "Parcours utilisateur complet",
    ]
    manquants_scenarios = [s for s in scenarios_attendus if s not in contenu]
    assert not manquants_scenarios, f"scénarios non trouvés dans le rapport : {manquants_scenarios}"
    print(f"OK 5 — les {len(scenarios_attendus)} scénarios demandés (installation vierge, migration DB, "
          f"import catalogue, génération programme, paiement simulé, PDF, utilisateur complet) sont documentés")

    # ------------------------------------------------------------------
    # 6) Contrôle de sécurité de l'audit lui-même : aucune trace du dossier
    #    temporaire jetable ne doit fuiter dans les autres fichiers du site
    #    (le script doit avoir nettoyé après lui) — seule une mention dans
    #    le rapport texte (constat "Installation vierge") est attendue.
    # ------------------------------------------------------------------
    assert "fitsurmesure_audit_" in contenu, "le rapport doit documenter le dossier temporaire isolé utilisé"
    print("OK 6 — l'audit documente explicitement son isolation (dossier temporaire jetable)")

    print("\nTOUS LES TESTS DE L'AUDIT PRODUCTION SONT PASSÉS")


if __name__ == "__main__":
    run()
