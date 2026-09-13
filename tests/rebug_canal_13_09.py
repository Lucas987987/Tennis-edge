#!/usr/bin/env python3
"""Réintroduit les bugs du correctif canal du 13/09 dans une COPIE."""
import os, sys
rep = os.path.abspath(sys.argv[1])
def rep_(f, a, b, lab):
    p = os.path.join(rep, f); s = open(p, encoding='utf-8').read()
    if a not in s:
        print(f"  ⚠️ {lab} : motif introuvable"); return False
    open(p, 'w', encoding='utf-8').write(s.replace(a, b, 1)); print(f"  rebuggé : {lab}"); return True
ok = True
ok &= rep_('canal_clv.py', "if k not in closes or pts[-1][0] > closes[k][2]:",
           "if k not in closes:  # priorité à la 1re source", "R1 canal_clv : 1re source gagne")
ok &= rep_('canal_suivi.py', "if k not in closes or pts[-1][0] > closes[k][1]:",
           "if k not in closes:", "R2 canal_suivi : 1re source gagne")
ok &= rep_('canal_suivi.py', "                try:\n                    lignes = ov.open_curves(path, verbose=False)",
           "                try:\n                    lignes = open(path, encoding='utf-8')", "R3 canal_suivi : open() brut")
ok &= rep_('canal_suivi.py', "if commence and (now - commence).total_seconds() < MARGE_MIN * 60:",
           "if False:", "R4 garde de complétude retirée")
sys.exit(0 if ok else 1)
