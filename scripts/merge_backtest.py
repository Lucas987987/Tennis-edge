#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_backtest.py — fusionne l'export de l'outil dans le backtest du repo, SANS
jamais perdre de ligne ni régresser un résultat.

Règles :
  - Union des lignes par `uid` (clé de repli : date_match|joueurA|joueurB).
  - Lignes de SIGNAL (proba, EV, score_confiance, elo…) : on garde celles du
    REPO si la ligne existe déjà (signal forward FIGÉ au moment du pari ; on ne
    le laisse pas muter). Les lignes nouvelles de l'outil sont ajoutées telles quelles.
  - Colonnes RÉSULTAT (`resultat`, `anomalie`, `src_resultat`) : on préfère toute
    valeur NON VIDE ; si le repo a déjà un résultat, il est PROTÉGÉ (jamais
    écrasé par du vide ni par une valeur divergente de l'outil — l'Action/Sackmann
    fait foi). Si le repo est vide et l'outil a la valeur, on la prend.

Format : point-virgule, sans guillemets (compatible fetch_results_fast).

USAGE :
    python scripts/merge_backtest.py tool_export.csv backtest_tennis.csv
    (1er = entrant/outil, 2e = canonique/repo ; défauts ci-dessous)
"""
import sys, os

INCOMING  = sys.argv[1] if len(sys.argv) > 1 else 'tool_export.csv'
CANONICAL = sys.argv[2] if len(sys.argv) > 2 else 'backtest_tennis.csv'
RESULT_COLS = ['resultat', 'anomalie', 'src_resultat']


def load(path):
    if not os.path.exists(path):
        return [], []
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = [l.rstrip('\n') for l in f if l.strip()]
    if not lines:
        return [], []
    header = lines[0].split(';')
    rows = []
    for l in lines[1:]:
        vals = l.split(';')
        while len(vals) < len(header):
            vals.append('')
        rows.append(dict(zip(header, vals)))
    return header, rows


def key(r):
    u = (r.get('uid') or '').strip()
    if u:
        return u
    return '|'.join((r.get('date_match', ''), r.get('joueurA', ''), r.get('joueurB', '')))


def filled(v):
    return str(v or '').strip().lower() not in ('', 'nan', 'none')


def main():
    h_base, base = load(CANONICAL)
    h_inc, inc = load(INCOMING)
    if not inc:
        sys.exit(f"Entrant vide ou introuvable : {INCOMING}")
    header = h_base or h_inc

    bykey, order = {}, []
    for r in base:
        k = key(r); bykey[k] = r; order.append(k)

    added = gained = conflicts = protected = 0
    for r in inc:
        k = key(r)
        if k not in bykey:
            bykey[k] = r; order.append(k); added += 1
            continue
        b = bykey[k]                                   # ligne déjà au repo : signal figé
        for col in RESULT_COLS:
            if col not in header:
                continue
            bv, iv = b.get(col, ''), r.get(col, '')
            if filled(bv):
                if col == 'resultat':
                    if filled(iv) and str(bv).strip() != str(iv).strip():
                        conflicts += 1                 # divergence -> on garde le repo
                    else:
                        protected += 1
                # repo conservé (protégé), rien à faire
            elif filled(iv):
                b[col] = iv
                if col == 'resultat':
                    gained += 1

    with open(CANONICAL, 'w', encoding='utf-8') as f:
        f.write(';'.join(header) + '\n')
        for k in order:
            r = bykey[k]
            f.write(';'.join(str(r.get(col, '')) for col in header) + '\n')

    print("=" * 60)
    print("MERGE backtest")
    print("=" * 60)
    print(f"repo avant      : {len(base)} lignes")
    print(f"outil (entrant) : {len(inc)} lignes")
    print(f"repo après      : {len(order)} lignes")
    print(f"  + lignes ajoutées (nouveaux matchs)   : {added}")
    print(f"  + résultats récupérés (repo était vide): {gained}")
    print(f"  résultats protégés (repo déjà rempli) : {protected}")
    if conflicts:
        print(f"  ⚠️ divergences resultat (repo conservé) : {conflicts}  <-- à vérifier")
    print("\n-> backtest_tennis.csv réécrit, aucun résultat existant écrasé.")


if __name__ == '__main__':
    main()
