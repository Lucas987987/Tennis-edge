#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebug_12_09.py — Réintroduit VOLONTAIREMENT les quatre bugs du correctif
du 12/09/2026 dans une COPIE des scripts, pour que verifier.sh puisse
prouver que les tests échouent quand le bug est là.

Un test qui passe sur du code correct ne prouve rien s'il passe aussi sur du
code buggé. Ce script est l'autre moitié de la preuve.

Usage : python3 tests/rebug_12_09.py <repertoire_scripts_copie>
Refuse de tourner sur un répertoire nommé exactement 'scripts' à la racine
du dépôt — on ne re-bugue jamais la production.
"""
import os
import sys


def remplace(chemin, avant, apres, etiquette):
    with open(chemin, encoding='utf-8') as f:
        src = f.read()
    if avant not in src:
        print(f"  ⚠️ {etiquette} : motif introuvable dans {chemin}")
        return False
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write(src.replace(avant, apres, 1))
    print(f"  rebuggé : {etiquette}")
    return True


def main(rep):
    rep = os.path.abspath(rep)
    if os.path.basename(rep) == 'scripts' and os.path.exists(
            os.path.join(os.path.dirname(rep), '.github')):
        print("REFUS : cible = scripts/ du dépôt. Copier ailleurs d'abord.")
        return 2

    ok = True

    # R1 — move_audit.py : l'ampleur exportée redevient rétrospective
    ma = os.path.join(rep, 'move_audit.py')
    ok &= remplace(ma,
                   "            mag_cote_pct=round(mag_odds_det * 100, 1),\n"
                   "            mag_cote_pct_POSTHOC=round(mag_odds * 100, 1),\n",
                   "            mag_cote_pct=round(mag_odds * 100, 1),\n",
                   "R1 ampleur exportée = clôture")
    ok &= remplace(ma,
                   "'mag_cote_pct','mag_cote_pct_POSTHOC',\n            'mag_proba_pts',",
                   "'mag_cote_pct','mag_proba_pts',",
                   "R1 colonne _POSTHOC retirée du CSV")

    # R2 — les gardes de version sautent
    for f in ('pistes_common.py', 'validation_report.py'):
        ok &= remplace(
            os.path.join(rep, f),
            "'mag_cote_pct_POSTHOC' not in (lecteur.fieldnames or [])",
            "False",
            f"R2 garde de version retirée ({f})")

    # R3 — H14 revient au gel du 07/09 sur critère contaminé
    ok &= remplace(os.path.join(rep, 'validation_report.py'),
                   "FREEZE_DATE_AMPLI = '2026-09-12'",
                   "FREEZE_DATE_AMPLI = '2026-09-07'",
                   "R3 gel H14 remis au 07/09")

    # R4 — la note de fiabilité disparaît de la branche forward
    pj = os.path.join(rep, 'paper_journal.py')
    with open(pj, encoding='utf-8') as f:
        src = f.read()
    debut = src.find("        # NOTE DE FIABILITÉ — MODE OMBRE (P9). AJOUTÉE ICI LE 12/09/2026.")
    fin = src.find("        n_open += 1", debut)
    if debut > 0 and fin > debut:
        with open(pj, 'w', encoding='utf-8') as f:
            f.write(src[:debut] + src[fin:])
        print("  rebuggé : R4 note de fiabilité retirée de la branche forward")
    else:
        print("  ⚠️ R4 : bloc introuvable")
        ok = False

    # R4bis — le composant book_en_retard retrouve la formule fausse
    ok &= remplace(pj,
                   "                t['fiabilite_score'], t['fiabilite_detail'] = fs.explique(\n"
                   "                    mag_pct=sig['thr'] * 100, lead_min=lead_min,\n"
                   "                    book_en_retard=bool(sig.get('ev') is not None\n"
                   "                                        and sig['ev'] >= 0.03))",
                   "                edge_pct = (sig['odds'] * (sig.get('pct') or 0) - 1) * 100 \\\n"
                   "                    if sig.get('pct') else None\n"
                   "                t['fiabilite_score'], t['fiabilite_detail'] = fs.explique(\n"
                   "                    mag_pct=sig['thr'] * 100, lead_min=lead_min,\n"
                   "                    book_en_retard=bool(edge_pct and edge_pct >= 3))",
                   "R4bis formule book_en_retard fausse")

    return 0 if ok else 1


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
