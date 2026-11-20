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

CORRECTIF 14/10/2026 : l'ancienne version se fiait à last_run_at (écrit au DÉBUT
d'un run, publié ~16 min plus tard) et relançait sans regarder les runs en
cours -> un run en file avec un SHA périmé, puis un conflit de merge et la
perte de 15 min de ticks, une fenêtre sur deux. Désormais : aucune relance si
un run est queued/in_progress/waiting, ni si un run a été créé il y a moins de
GRACE_MIN, ni si l'API GitHub est injoignable (fail-safe : mieux vaut ne rien
faire que doubler). L'âge est celui de la dernière FIN de run réussi (ou, si
plus récent, de stopped_at de l'état), jamais celui d'un run annulé.

Env : SEUIL_MIN (déf 20) minutes de retard tolérées avant relance ;
      GRACE_MIN (déf 5) fenêtre pendant laquelle un run récent bloque la relance ;
      DRY_RUN=1 pour tester sans déclencher.
"""
import datetime
import json
import os
import subprocess
import sys

SEUIL_MIN = float(os.environ.get('SEUIL_MIN', '20'))
GRACE_MIN = float(os.environ.get('GRACE_MIN', '5'))
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
CIBLES = {
    'kalshi_collector.yml': 'kalshi_collector_state.json',
    'polymarket_collector.yml': 'polymarket_collector_state.json',
}
ACTIFS = {'queued', 'in_progress', 'waiting', 'requested', 'pending'}


def _parse(ts):
    """ISO 8601 (avec ou sans Z/fuseau) -> datetime UTC, ou None."""
    if not ts:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(datetime.timezone.utc)


def age_etat_minutes(fichier_etat, maintenant):
    """Âge de la dernière publication visible dans l'état (stopped_at, écrit
    en FIN de run). last_run_at (début de run) n'est volontairement pas lu."""
    try:
        d = json.load(open(fichier_etat, encoding='utf-8'))
    except (OSError, ValueError):
        return float('inf')
    t = _parse(d.get('stopped_at'))
    if t is None:
        return float('inf')
    return (maintenant - t).total_seconds() / 60


def lister_runs(workflow):
    """Derniers runs du workflow, ou None si l'API est injoignable/illisible."""
    try:
        r = subprocess.run(
            ['gh', 'run', 'list', '--workflow', workflow, '--limit', '20',
             '--json', 'status,conclusion,event,createdAt,updatedAt'],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"  ⚠️ API GitHub : {r.stderr.strip()[:200]}")
            return None
        runs = json.loads(r.stdout)
        return runs if isinstance(runs, list) else None
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        print(f"  ⚠️ API GitHub injoignable : {e}")
        return None


def decider(runs, age_etat, maintenant, seuil=None, grace=None):
    """-> (relancer: bool, raison: str). Fonction pure, testée."""
    seuil = SEUIL_MIN if seuil is None else seuil
    grace = GRACE_MIN if grace is None else grace
    if runs is None:
        return False, "API GitHub inaccessible -> aucune relance (fail-safe)"
    actifs = [r for r in runs if r.get('status') in ACTIFS]
    if actifs:
        return False, (f"{len(actifs)} run(s) {actifs[0].get('status')} "
                       f"-> rien à relancer")
    crees = [t for t in (_parse(r.get('createdAt')) for r in runs) if t]
    if crees:
        recent = (maintenant - max(crees)).total_seconds() / 60
        if recent < grace:
            return False, (f"run créé il y a {recent:.1f} min "
                           f"(< {grace:.0f}) -> attente")
    fins = [_parse(r.get('updatedAt')) for r in runs
            if r.get('status') == 'completed'
            and r.get('conclusion') == 'success']
    fins = [t for t in fins if t]
    ages = [age_etat]
    if fins:
        ages.append((maintenant - max(fins)).total_seconds() / 60)
    age = min(ages)
    if age <= seuil:
        return False, f"dernière publication il y a {age:.0f} min -> OK"
    quand = 'inconnue' if age == float('inf') else f"il y a {age:.0f} min"
    return True, (f"aucun run actif/récent, dernière publication {quand} "
                  f"(seuil {seuil:.0f}) -> relance")


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


def maintenant_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def traiter(workflow, fichier, lister=lister_runs, lancer=relancer,
            horloge=maintenant_utc):
    """Retourne True si une relance a échoué. Le contrôle est refait juste
    avant l'envoi pour réduire la fenêtre de course entre deux watchdogs."""
    maintenant = horloge()
    age = age_etat_minutes(fichier, maintenant)
    ok, raison = decider(lister(workflow), age, maintenant)
    print(f"  {workflow:28} {raison}")
    if not ok:
        return False
    ok, raison = decider(lister(workflow), age, horloge())
    if not ok:
        print(f"  {workflow:28} revérification : {raison}")
        return False
    return not lancer(workflow)


def main():
    print(f"WATCHDOG COLLECTEURS — seuil {SEUIL_MIN:.0f} min, "
          f"grâce {GRACE_MIN:.0f} min" + (" [DRY RUN]" if DRY_RUN else ""))
    echecs = sum(1 for w, f in CIBLES.items() if traiter(w, f))
    # Non-bloquant pour capture_closing : un échec de relance ne doit jamais
    # faire échouer le job principal (celui qui vient de pousser des données
    # réelles). Le signal reste visible dans les logs, jamais avalé.
    if echecs:
        print(f"  {echecs} relance(s) en échec — non bloquant pour ce run.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
