#!/usr/bin/env python3
"""Corrige la comparaison ancrage exact (borne 0,5 %) sans toucher au modèle."""
from pathlib import Path
import ast
p = Path('simulateur/pronostics_du_jour.py')
s = p.read_text(encoding='utf-8')
old = '''    saturation_extreme = (p_home in (0, 0.0, 1, 1.0)
                          and ecart <= 0.00500001)'''
new = '''    # L'ancrage exact borne la cible dans [0,005 ; 0,995].
    # Vérifier sa valeur bornée, sans accepter d'autres incohérences.
    cible_exacte = min(0.995, max(0.005, p_home))
    saturation_extreme = (p_home < 0.005 or p_home > 0.995) and abs(victoire - cible_exacte) <= 1e-8'''
if old not in s:
    if new in s:
        print('Correctif v2 déjà présent')
        raise SystemExit(0)
    raise SystemExit('ERREUR: version précédente non trouvée; aucun changement')
s2 = s.replace(old, new, 1)
ast.parse(s2, filename=str(p))
p.write_text(s2, encoding='utf-8')
print('Correctif v2 appliqué')
