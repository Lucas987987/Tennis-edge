#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
freeze_thresholds.py — Gèle la sélection ACTUELLE des seuils adaptatifs par
book (9e hypothèse de validation_report.py), sans toucher au système en
production (steam_alert.py continue de tourner et de se ré-optimiser en
continu, exactement comme avant).

CONTEXTE : une revue externe du projet (ChatGPT, 15/08/2026) a identifié un
risque réel de sur-ajustement dans best_threshold() (scripts/steam_alert.py) :
le seuil par book est choisi en cherchant, sur les 90 derniers jours, celui
qui maximise le %CLV+ observé -- puis ce même %CLV+ est affiché comme preuve
de performance. C'est un data snooping classique : une partie du score
affiché peut être mécaniquement due à la recherche du meilleur seuil, pas à
un vrai edge.

CE SCRIPT : importe DIRECTEMENT les fonctions réelles de steam_alert.py
(load_curves, compute_stats, best_threshold) -- pas une réimplémentation --
pour garantir une fidélité totale à ce qui tourne effectivement en
production. Il fige l'état AUJOURD'HUI (quel seuil best_threshold()
choisirait, et sur quelle stat in-sample il s'est basé), dans
frozen_thresholds.json. validation_report.py lira ensuite ce fichier pour
comparer, sur des données STRICTEMENT POSTÉRIEURES, si ce seuil gelé
continue de performer comme annoncé -- ou si la performance s'effondre
(confirmant le sur-ajustement).

USAGE : à lancer UNE FOIS (comme migrate_hist_partitions.py) -- ou
périodiquement si on veut ré-geler avec un cycle walk-forward (ex. chaque
trimestre), auquel cas garder l'historique des gels précédents plutôt que
de les écraser (voir --append).
"""
import os, sys, json, datetime, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import steam_alert as sa

OUT_FILE = 'frozen_thresholds.json'

MARKETS = {
    'match': {'curves': 'book_curves_live.jsonl', 'track': 'book_curves.jsonl'},
    'set1':  {'curves': 'set1_curves_live.jsonl', 'track': 'set1_curves.jsonl'},
    'set2':  {'curves': 'set2_curves_live.jsonl', 'track': 'set2_curves.jsonl'},
}


def freeze_market(market, cfg):
    """Reproduit EXACTEMENT la logique de steam_alert.main() pour ce marché,
    jusqu'à best_threshold() inclus -- sans envoyer d'alerte ni rien modifier."""
    track = sa.load_curves(cfg['track'])
    now = sa._now()
    win_start = now - sa.WINDOW_DAYS * 86400 if sa.WINDOW_DAYS > 0 else 0
    past = {u: bk for u, bk in track.items()
            if bk.get('_commence') and win_start <= bk['_commence'] < now}
    upcoming_curves = sa.load_curves(cfg['curves']) if os.path.exists(cfg['curves']) else {}
    softbooks = sorted({b for m in list(past.values()) + list(upcoming_curves.values())
                        for b in m if not b.startswith('_') and b != sa.SHARP})
    if not softbooks:
        print(f"  [{market}] aucun book mou -- rien à geler")
        return {}
    stats = sa.compute_stats(past, softbooks)
    frozen = {}
    for sb in softbooks:
        mv, sdat, confident = sa.best_threshold(stats, sb)
        if sdat:
            frozen[sb] = {'threshold': mv, 'in_sample_pct': sdat['pct'],
                          'in_sample_med': sdat['med'], 'in_sample_n': sdat['n'],
                          'confident': confident}
    print(f"  [{market}] {len(frozen)} books gelés sur {len(softbooks)} suivis "
          f"(track record {len(past)} matchs, fenêtre {sa.WINDOW_DAYS:.0f}j)")
    return frozen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--append', action='store_true',
                    help="conserve les gels précédents au lieu d'écraser (walk-forward)")
    args = ap.parse_args()

    print("=== Gel des seuils adaptatifs (9e hypothèse) ===\n")
    frozen_at = datetime.datetime.utcnow().isoformat()
    result = {'frozen_at': frozen_at, 'window_days': sa.WINDOW_DAYS, 'markets': {}}
    for market, cfg in MARKETS.items():
        result['markets'][market] = freeze_market(market, cfg)

    if args.append and os.path.exists(OUT_FILE):
        try:
            history = json.load(open(OUT_FILE, encoding='utf-8'))
            if not isinstance(history, list):
                history = [history]
        except Exception:
            history = []
        history.append(result)
        with open(OUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {OUT_FILE} : gel ajouté à l'historique ({len(history)} gel(s) au total)")
    else:
        with open(OUT_FILE, 'w', encoding='utf-8') as f:
            json.dump([result], f, ensure_ascii=False, indent=2)
        print(f"\n✅ {OUT_FILE} écrit (1 gel, {frozen_at})")


if __name__ == '__main__':
    main()
