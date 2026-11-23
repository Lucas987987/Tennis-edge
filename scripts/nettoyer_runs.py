#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nettoyer_runs.py — supprimer les anciens runs des workflows sensibles (23/11/2026, paquet 394, Lucas : « un workflow
qui supprimerait directement les runs passés des workflows les plus sensibles »).

Le dépôt est public : le journal et les artefacts de chaque run le sont aussi. Avant le paquet 393, beaucoup de journaux
contenaient des chiffres privés (CLV, ROI, cotes par bookmaker, comparaisons aux cotes de clôture). Supprimer un run
efface son journal ET ses artefacts, définitivement.

Ce que fait le script (API GitHub, jeton du workflow, droit « actions: write ») :
  • pour chaque workflow de la liste SENSIBLES : les runs TERMINÉS créés il y a plus de GARDER_JOURS jours ;
  • les runs en cours ou en attente ne sont jamais touchés ;
  • au plus MAX_SUPPRESSIONS par passage (limite de 1 000 requêtes par heure du jeton) : un gros arriéré se vide en
    quelques passages horaires ;
  • mode « simuler » : compte sans rien supprimer.
Journal : seulement des nombres de runs par workflow.
Usage : python scripts/nettoyer_runs.py [--simuler] [--garder-jours N] [--max N] [--tous]
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API = 'https://api.github.com'
GARDER_JOURS = 2
MAX_SUPPRESSIONS = 800
SENSIBLES = [
 "a_ou_b.yml",
 "book_index.yml",
 "book_lag.yml",
 "calibration_buckets.yml",
 "capture_closing.yml",
 "clean_clv_metrics.yml",
 "confidence_v2.yml",
 "controle_prive.yml",
 "courbes_alertes.yml",
 "diag_windows.yml",
 "drift_predictability.yml",
 "elo.yml",
 "elo_mov.yml",
 "etudes_move.yml",
 "fetch_book_curves.yml",
 "fetch_clv.yml",
 "fetch_results_settlement.yml",
 "freeze_thresholds.yml",
 "identify_set_markets.yml",
 "inplay_setone.yml",
 "inspect_curves.yml",
 "inspect_set2.yml",
 "kalshi_probe.yml",
 "lab_gel.yml",
 "lab_quotidien.yml",
 "list_books.yml",
 "move_vs_outcome.yml",
 "observateur_externe.yml",
 "opening_value.yml",
 "pages.yml",
 "player_profiles.yml",
 "polymarket_collector.yml",
 "probe_historical.yml",
 "probe_v5.yml",
 "pronostic.yml",
 "rattrapage_derives.yml",
 "rentabilite_marches.yml",
 "roi_algo.yml",
 "sauvegarde_depot.yml",
 "simulateur.yml",
 "simulateur_marches.yml",
 "sonde_courbes.yml",
 "sonde_marches.yml",
 "sonde_marches_v2.yml",
 "sonde_tennis_data.yml",
 "steam_diag.yml",
 "steam_pipeline.yml",
 "suivi_outsiders.yml",
 "test_oddspapi.yml",
 "update_results.yml",
 "value_journal.yml",
 "nettoyer_runs.yml"
]


def appel(methode, chemin, jeton, ouvrir=urllib.request.urlopen):
    req = urllib.request.Request(API + chemin, method=methode, headers={
        'Authorization': f'Bearer {jeton}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'tennis-edge-nettoyage'})
    try:
        with ouvrir(req, timeout=30) as r:
            corps = r.read()
            return r.status, (json.loads(corps) if corps else None)
    except urllib.error.HTTPError as e:
        return e.code, None


def anciens_runs(depot, workflow, avant, jeton, ouvrir=urllib.request.urlopen, limite=1000):
    """Identifiants des runs TERMINÉS du workflow, créés avant la date « avant » (AAAA-MM-JJ)."""
    ids, page = [], 1
    while len(ids) < limite:
        code, doc = appel('GET', f'/repos/{depot}/actions/workflows/{workflow}/runs?status=completed&created=%3C{avant}'
                                 f'&per_page=100&page={page}', jeton, ouvrir)
        if code != 200 or not doc:
            break
        runs = doc.get('workflow_runs') or []
        ids += [r['id'] for r in runs if r.get('status') == 'completed']
        if len(runs) < 100:
            break
        page += 1
    return ids[:limite]


def tous_les_workflows(depot, jeton, ouvrir=urllib.request.urlopen):
    code, doc = appel('GET', f'/repos/{depot}/actions/workflows?per_page=100', jeton, ouvrir)
    return [os.path.basename(w['path']) for w in (doc or {}).get('workflows') or []] if code == 200 else []


def nettoyer(depot, jeton, garder_jours=GARDER_JOURS, maxi=MAX_SUPPRESSIONS, simuler=False, workflows=None,
             ouvrir=urllib.request.urlopen, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    avant = (maintenant - dt.timedelta(days=garder_jours)).date().isoformat()
    bilan, reste = {}, maxi
    for wf in workflows or SENSIBLES:
        if reste <= 0:
            break
        ids = anciens_runs(depot, wf, avant, jeton, ouvrir, limite=reste)
        ok = 0
        for i in ids:
            if simuler:
                ok += 1
                continue
            code, _ = appel('DELETE', f'/repos/{depot}/actions/runs/{i}', jeton, ouvrir)
            ok += code == 204
        reste -= len(ids)
        if ids:
            bilan[wf] = ok
    return bilan, reste <= 0


def main(argv):
    jeton, depot = os.environ.get('GITHUB_TOKEN'), os.environ.get('GITHUB_REPOSITORY')
    if not jeton or not depot:
        print('::error::GITHUB_TOKEN ou GITHUB_REPOSITORY absent')
        return 1
    simuler = '--simuler' in argv
    garder = int(argv[argv.index('--garder-jours') + 1]) if '--garder-jours' in argv else GARDER_JOURS
    maxi = int(argv[argv.index('--max') + 1]) if '--max' in argv else MAX_SUPPRESSIONS
    wfs = tous_les_workflows(depot, jeton) if '--tous' in argv else None
    bilan, plafond = nettoyer(depot, jeton, garder, maxi, simuler, wfs)
    total = sum(bilan.values())
    print(f"{'À supprimer (simulation)' if simuler else 'Supprimés'} : {total} run(s) de plus de {garder} jour(s), "
          f"{len(bilan)} workflow(s)" + (" — plafond atteint, la suite au prochain passage" if plafond else ""))
    for wf, n in sorted(bilan.items(), key=lambda x: -x[1]):
        print(f"  {wf} : {n}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
