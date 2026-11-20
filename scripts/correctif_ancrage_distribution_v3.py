#!/usr/bin/env python3
"""Correction ciblée et idempotente du contrôle de distribution exacte."""
from pathlib import Path
import ast
p = Path(__file__).resolve().parents[1] / 'simulateur' / 'pronostics_du_jour.py'
s = p.read_text(encoding='utf-8')
start = s.index('    controle = DE.controle(distribution)\n', s.index('def distribution_exacte_du_match('))
end = s.index('    rows = DE.scores_ordonnes(distribution)\n', start)
old = s[start:end]
if 'cible_exacte = min(max(p_home, 0.005), 0.995)' in old:
    print('Correctif V3 déjà présent.'); raise SystemExit(0)
if 'victoire = DE.victoire_depuis_distribution(distribution)' not in old or 'raise ValueError' not in old:
    raise RuntimeError('Structure du contrôle inattendue : aucune modification appliquée.')
new = '''    controle = DE.controle(distribution)
    victoire = DE.victoire_depuis_distribution(distribution)
    # match_simule.noeuds_de_forme borne explicitement p_victoire à [0.005, 0.995]
    # avant l'ancrage. Comparer à cette même cible, et non à la valeur brute.
    cible_exacte = min(max(p_home, 0.005), 0.995) if p_home is not None else None
    if not controle['ok'] or (cible_exacte is not None and abs(victoire - cible_exacte) > 1e-8):
        raise ValueError(f'Distribution exacte incohérente pour {h}–{a}: {controle}, victoire={victoire}, cible_exacte={cible_exacte}, cible_brute={p_home}')
    if cible_exacte is not None and cible_exacte != p_home:
        print(f'::warning::Ancrage exact borné pour {h}–{a}: simulation={p_home}, cible_exacte={cible_exacte}')
'''
s2=s[:start]+new+s[end:]
ast.parse(s2, filename=str(p))
p.write_text(s2,encoding='utf-8')
print('Correctif V3 appliqué et syntaxe validée:',p)
