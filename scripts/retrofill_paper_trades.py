#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retrofill_paper_trades.py — Rétro-remplit won/pnl sur les trades existants
(un seul usage, créé le 27/08/2026 suite à l'audit §1.1).

Les paris marqués SETTLED sans jamais avoir reçu de pnl (le bug corrigé dans
settle_trade()) sont ici corrigés hors ligne : pour chaque paire (uid, marché),
on cherche le résultat dans set_results.json et on calcule won/pnl comme le
ferait settle_trade(). Si aucun résultat n'existe encore, le statut redescend
à CLOSED_NO_RESULT pour que la prochaine exécution de paper_journal.py le
retraite normalement (au lieu de rester bloqué en SETTLED-sans-résultat).

Usage : python scripts/retrofill_paper_trades.py [--write]
Sans --write : affiche ce qui serait fait, ne touche à rien.
"""
import json
import os
import sys

FICHIERS = {
    'match': 'paper_trades_match.jsonl',
    'set1': 'paper_trades_set1.jsonl',
    'set2': 'paper_trades_set2.jsonl',
}


def charge(fichier):
    if not os.path.exists(fichier):
        return []
    return [json.loads(l) for l in open(fichier, encoding='utf-8') if l.strip()]


def ecrit(fichier, trades):
    with open(fichier, 'w', encoding='utf-8') as f:
        for t in trades:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')


def main():
    ecrire = '--write' in sys.argv
    resultats = json.load(open('set_results.json', encoding='utf-8'))
    n_maj, n_reste, n_deja_ok = 0, 0, 0
    for marche, fichier in FICHIERS.items():
        trades = charge(fichier)
        if not trades:
            continue
        touches = 0
        for t in trades:
            if 'pnl' in t:
                n_deja_ok += 1
                continue
            r = resultats.get(t['uid'], {})
            w = r.get(marche)
            if w in ('home', 'away'):
                won = (t['side'] == w)
                t['won'] = bool(won)
                t['pnl'] = round((t['entry_odds'] - 1) if won else -1.0, 3)
                t['status'] = 'SETTLED'
                n_maj += 1
                touches += 1
            else:
                # Pas encore de résultat : redescendu à CLOSED_NO_RESULT pour
                # que paper_journal.py le retraite au prochain cycle — au
                # lieu de rester bloqué en SETTLED sans jamais être revisité.
                if t.get('status') != 'CLOSED_NO_RESULT':
                    t['status'] = 'CLOSED_NO_RESULT'
                n_reste += 1
        print(f"{fichier} : {len(trades)} trades | {touches} rétro-remplis")
        if ecrire:
            ecrit(fichier, trades)
    print(f"\nTotal : {n_maj} rétro-remplis (won+pnl), {n_reste} encore sans "
          f"résultat -> CLOSED_NO_RESULT, {n_deja_ok} déjà corrects.")
    if not ecrire:
        print("(mode lecture seule — relancer avec --write pour appliquer)")


if __name__ == '__main__':
    main()
