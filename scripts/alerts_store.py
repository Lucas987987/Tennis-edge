#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""alerts_store.py — odds_alerts_log.jsonl découpé par mois (16/10/2026).

odds_alerts_log.jsonl (1,5 Mo, journal « Mouvement de cote ») était réécrit
~27 fois par jour : ~42 Mo de nouvelles versions par jour pour quelques
lignes ajoutées. Désormais :

    odds_alerts_log/odds_alerts_log_AAAA-MM.jsonl   (ajout seul, 8 Mo max)

Lecteurs :  with alerts_store.open_text(ALERTS_LOG) as f: for line in f: …
            alerts_store.exists(ALERTS_LOG)
Écrivain :  open(alerts_store.append_path(), 'a')   (odds_movement.py)
Ordre des lignes identique à l'ancien fichier (mois du maximum courant de
`logged_at`). Voir scripts/jsonl_parts.py.

    python scripts/alerts_store.py migrer | verifier | supprimer_ancien | annuler
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jsonl_parts import Store  # noqa: E402

LEGACY = "odds_alerts_log.jsonl"
STORE = Store(LEGACY, "odds_alerts_log", "odds_alerts_log", "logged_at",
              "ALERTS_PART_MAX_MB", 8.0)

resolve = STORE.resolve
exists = STORE.exists
iter_lines = STORE.iter_lines
iter_records = STORE.iter_records
open_text = STORE.open_text
append_path = STORE.append_path
partitions = STORE.partitions
migrate = STORE.migrate
verify = STORE.verify
remove_legacy = STORE.remove_legacy
restore = STORE.restore

if __name__ == "__main__":
    sys.exit(STORE.main(sys.argv[1:]))
