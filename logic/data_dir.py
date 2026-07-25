# -*- coding: utf-8 -*-
"""Emplacement du dossier de stockage JSON (codes promo, commandes).

En local, c'est simplement le dossier `data/` à la racine du projet. En
production (Render ou autre hébergeur), ce dossier doit pointer vers un DISQUE
PERSISTANT (sinon les codes promo et les commandes payées sont perdus à chaque
redémarrage du serveur) : on définit alors la variable d'environnement DATA_DIR
pour la faire pointer vers le point de montage de ce disque (ex: /var/data)."""
import os


def get_data_dir():
    override = os.environ.get("DATA_DIR")
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
