#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""watchdog_collecteurs.py — Kalshi/Polymarket relancés s'ils sont en retard.

CRÉÉ LE 26/08/2026 après une panne de déclenchement automatique : le Worker
Cloudflare (repository_dispatch) fonctionne, mais kalshi_collector et
polymarket_collector n'ont AUCUN filet de secours — contrairement à
capture_closing qui a en plus un cron GitHub natif. Résultat observé : les
deux collecteurs restent muets en automatique pendant que capture_closing
continue de tourner seul.

PAS DE CRON GITHUB EN PLUS (décision du 26/08 : peu réactif, redondant avec
le Worker). À la place : capture_closing, qui se déclenche de façon fiable
(dispatch + cron horaire), vérifie à CHAQUE passage si Kalshi/Polymarket ont
écrit récemment (champ last_run_at de leur état) et les relance lui-même via
l'API si le retard dépasse le seuil. Réaction à un signal réel, pas un
calendrier de plus.

Env : SEUIL_MIN (déf 20) minutes de retard tolérées avant relance ;
      DRY_RUN=1 pour tester sans déclencher.
"""
import datetime
import json
import os
import subprocess
import sys

SEUIL_MIN = float(os.environ.get('SEUIL_MIN', '20'))
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
CIBLES = {
    'kalshi_collector.yml': 'kalshi_collector_state.json',
    'polymarket_collector.yml': 'polymarket_collector_state.json',
}


def age_minutes(fichier_etat):
    try:
        d = json.load(open(fichier_etat, encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f"  ⚠️ {fichier_etat} illisible ({e}) — retard supposé maximal.")
        return float('inf')
    ts = d.get('last_run_at')
    if not ts:
        print(f"  ⚠️ {fichier_etat} sans last_run_at — retard supposé maximal.")
        return float('inf')
    try:
        t = datetime.datetime.fromisoformat(ts.replace('Z', ''))
        t = t.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return float('inf')
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    return (maintenant - t).total_seconds() / 60


def relancer(workflow):
    if DRY_RUN:
        print(f"  [dry] gh workflow run {workflow}")
        return True
    r = subprocess.run(['gh', 'workflow', 'run', workflow],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ⚠️ relance de {workflow} ÉCHOUÉE : {r.stderr.strip()[:200]}")
        return False
    print(f"  ✅ {workflow} relancé (déclenchement manuel via API).")
    return True


def main():
    print(f"WATCHDOG COLLECTEURS — seuil {SEUIL_MIN:.0f} min"
         + (" [DRY RUN]" if DRY_RUN else ""))
    echecs = 0
    for workflow, fichier in CIBLES.items():
        age = age_minutes(fichier)
        if age == float('inf'):
            print(f"  {workflow:28} état illisible ou incomplet -> relance")
            if not relancer(workflow):
                echecs += 1
        elif age > SEUIL_MIN:
            print(f"  {workflow:28} dernière écriture il y a {age:.0f} min "
                 f"(seuil {SEUIL_MIN:.0f}) -> relance")
            if not relancer(workflow):
                echecs += 1
        else:
            print(f"  {workflow:28} dernière écriture il y a {age:.0f} min "
                 f"-> OK, rien à faire")
    # Non-bloquant pour capture_closing : un échec de relance ne doit jamais
    # faire échouer le job principal (celui qui vient de pousser des données
    # réelles). Le signal reste visible dans les logs, jamais avalé.
    if echecs:
        print(f"  {echecs} relance(s) en échec — non bloquant pour ce run.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
