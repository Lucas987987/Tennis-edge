#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du correctif canal du 13/09/2026 (cascade de sources + complétude).

Le test fonctionnel rejoue le cas RÉEL du 11/09 : une source `live` tronquée
en tête de cascade, les partitions de ticks derrière. Le bon comportement est
de retenir le prix de clôture des partitions (2.32), pas celui de la source
tronquée (2.694) qui avait produit le « +0 % » publié.

Env : SCRIPTS · CURVES_LIVE · CURVES_FULL · STATIQUES_SEULEMENT=1
"""
import os, subprocess, sys

SCRIPTS = os.path.abspath(os.environ.get('SCRIPTS', 'scripts'))
RACINE = os.path.dirname(SCRIPTS) or '.'
echecs, oks = [], []


def verifie(nom, cond, detail=''):
    (oks if cond else echecs).append(nom)
    print(("  ✅ " if cond else "  ❌ ") + nom + (f" — {detail}" if not cond and detail else ""))


def src(f):
    return open(os.path.join(SCRIPTS, f), encoding='utf-8').read()


def t1():
    print("\nT1 — la cascade retient le point pré-match le PLUS TARDIF")
    c = src('canal_clv.py')
    verifie("canal_clv : comparaison d'horodatage entre sources",
            "pts[-1][0] > closes[k][2]" in c,
            "la 1re source gagne encore : une courbe live tronquée écrase hist")
    s = src('canal_suivi.py')
    verifie("canal_suivi : comparaison d'horodatage entre sources",
            "pts[-1][0] > closes[k][1]" in s)
    verifie("canal_suivi : ouvre les partitions via open_curves",
            "ov.open_curves" in s,
            "avec un open() brut, book_curves.jsonl (migré vers parts/) "
            "ne donne plus rien depuis la migration")


def t2():
    print("\nT2 — complétude : pas de mesure avant le coup d'envoi")
    for f, ref in (('canal_suivi.py', 'en_attente'), ('canal_clv.py', 'en_attente')):
        c = src(f)
        verifie(f"{f} : garde de complétude", "MARGE_MIN * 60" in c and ref in c)
        verifie(f"{f} : heure injectable (NOW_OVERRIDE)", "_maintenant()" in c)


def t3():
    print("\nT3 — cas réel du 11/09, source live tronquée en tête de cascade")
    live = os.environ.get('CURVES_LIVE', '')
    full = os.environ.get('CURVES_FULL', '')
    if not (live and full and os.path.exists(live) and os.path.exists(full)):
        verifie("courbes de test disponibles", False, f"{live!r} / {full!r}")
        return
    env = dict(os.environ, DRY_RUN='1', CURVES=f"{live},{full}",
               NOW_OVERRIDE='2026-09-12T07:00', DAYS='1', MIN_ROWS='1',
               PYTHONPATH=SCRIPTS)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'canal_suivi.py')],
                       cwd=RACINE, env=env, capture_output=True, text=True, timeout=600)
    out = r.stdout + r.stderr
    verifie("canal_suivi s'exécute", r.returncode == 0, out[-200:])
    verifie("la clôture retenue vient des partitions (2.32), pas de la source tronquée",
            "2.32" in out and "2.69 → 2.69" not in out,
            "mesure tronquée retenue — c'est le bug publié le 12/09")
    verifie("l'écart est compté comme refermé", "1 se sont refermés" in out, out[-300:])
    verifie("les extrêmes ne sont plus la même ligne",
            not ("Le plus net : bet365 3.25 → 3.25" in out
                 and "Le moins bon : bet365 3.25 → 3.25" in out))


def main():
    print(f"Scripts testés : {SCRIPTS}")
    t1(); t2()
    if os.environ.get('STATIQUES_SEULEMENT') != '1':
        t3()
    print(f"\n{len(oks)} test(s) OK · {len(echecs)} échec(s)")
    for e in echecs:
        print(f"  - {e}")
    return 1 if echecs else 0


if __name__ == '__main__':
    sys.exit(main())
