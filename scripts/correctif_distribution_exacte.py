#!/usr/bin/env python3
"""Correctif minimal: saturation 0.5 % de l'ancrage exact aux extrêmes Monte-Carlo."""
from pathlib import Path
import ast
p = Path('simulateur/pronostics_du_jour.py')
s = p.read_text(encoding='utf-8')
old = '''    if not controle['ok'] or abs(victoire - p_home) > 1e-8:
        raise ValueError(f'Distribution exacte incohérente pour {h}–{a}: {controle}, victoire={victoire}')'''
new = '''    # L'ancrage de la distribution exacte sature à 0,5 % aux extrêmes.
    # Une simulation Monte-Carlo peut renvoyer exactement 0 % ou 100 %.
    # Ne tolérer CET écart connu que pour les cas limites, jamais ailleurs.
    ecart = abs(victoire - p_home)
    saturation_extreme = (p_home in (0, 0.0, 1, 1.0)
                          and ecart <= 0.00500001)
    if not controle['ok'] or (ecart > 1e-8 and not saturation_extreme):
        raise ValueError(f'Distribution exacte incohérente pour {h}–{a}: {controle}, victoire={victoire}, cible={p_home}')
    if saturation_extreme and ecart > 1e-8:
        print(f'::warning::Ancrage exact saturé à la borne pour {h}–{a}: simulation={p_home}, exact={victoire}')'''
if old not in s:
    if new in s:
        print('Correctif déjà présent')
        raise SystemExit(0)
    raise SystemExit('ERREUR: code attendu introuvable; aucun changement effectué')
s2=s.replace(old,new,1)
ast.parse(s2, filename=str(p))
p.write_text(s2, encoding='utf-8')
print('Correctif appliqué et syntaxe vérifiée')
