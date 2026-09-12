#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_correctif_12_09.py — Tests du correctif du 12/09/2026.

Deux familles de tests :

  STATIQUES  — lisent le SOURCE des scripts (AST / texte). Ce sont eux qui
               sont rejoués sur une copie volontairement re-buguée par
               verifier.sh : ils DOIVENT échouer dans ce mode.
  FONCTIONNELS — font tourner move_audit.py sur de vraies courbes de
               production (une partition parts/hist_book_*.jsonl.gz) et
               vérifient les colonnes produites ligne à ligne.

Variables d'environnement :
  SCRIPTS   répertoire des scripts à tester (défaut : ./scripts)
  CURVES_T  fichier de courbes pour le test fonctionnel (défaut : la
            partition hist_book la plus récente, décompressée par verifier.sh)
  STATIQUES_SEULEMENT=1  n'exécute que les tests statiques
"""
import ast
import csv
import io
import json
import os
import subprocess
import sys
import tempfile

SCRIPTS = os.environ.get('SCRIPTS', 'scripts')
RACINE = os.path.dirname(os.path.abspath(SCRIPTS.rstrip('/'))) or '.'

echecs = []
oks = []


def verifie(nom, condition, detail=''):
    if condition:
        oks.append(nom)
        print(f"  ✅ {nom}")
    else:
        echecs.append(nom)
        print(f"  ❌ {nom}" + (f" — {detail}" if detail else ''))


def source(fichier):
    with open(os.path.join(SCRIPTS, fichier), encoding='utf-8') as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────
# T1 (statique) — move_audit.py exporte une ampleur CAUSALE
# ─────────────────────────────────────────────────────────────────────────
def t1_statique():
    print("\nT1 — move_audit.py : ampleur exportée mesurée à la détection")
    src = source('move_audit.py')
    arbre = ast.parse(src)

    # la valeur exportée sous `mag_cote_pct=` doit venir de mag_odds_det
    valeurs = {}
    for n in ast.walk(arbre):
        if isinstance(n, ast.keyword) and n.arg in (
                'mag_cote_pct', 'mag_cote_pct_POSTHOC'):
            valeurs[n.arg] = ast.unparse(n.value)
    verifie("mag_cote_pct est calculée sur mag_odds_det",
            'mag_odds_det' in valeurs.get('mag_cote_pct', ''),
            f"trouvé : {valeurs.get('mag_cote_pct')!r}")
    verifie("mag_cote_pct_POSTHOC existe et porte la valeur rétrospective",
            'mag_odds' in valeurs.get('mag_cote_pct_POSTHOC', '')
            and 'mag_odds_det' not in valeurs.get('mag_cote_pct_POSTHOC', ''),
            f"trouvé : {valeurs.get('mag_cote_pct_POSTHOC')!r}")
    verifie("mag_cote_pct_POSTHOC est dans les colonnes du CSV",
            "'mag_cote_pct_POSTHOC'" in src)
    verifie("mag_odds_det est bien calculée à t_det",
            'o_det' in src and "_at(pin['h'] if steam == 'h' else pin['a'], t_det)" in src)


# ─────────────────────────────────────────────────────────────────────────
# T2 (statique) — les deux lecteurs refusent un CSV d'avant le correctif
# ─────────────────────────────────────────────────────────────────────────
def t2_statique():
    print("\nT2 — gardes de version chez les lecteurs")
    for f, fn in (('pistes_common.py', 'charge_moves'),
                  ('validation_report.py', 'roi_ampli_watch')):
        src = source(f)
        verifie(f"{f} : garde sur mag_cote_pct_POSTHOC",
                "'mag_cote_pct_POSTHOC' not in" in src,
                "aucune garde trouvée — un vieux CSV serait relu en silence")


# ─────────────────────────────────────────────────────────────────────────
# T3 (statique) — H14 regelée à une nouvelle date
# ─────────────────────────────────────────────────────────────────────────
def t3_statique():
    print("\nT3 — H14 regelée sur le critère causal")
    src = source('validation_report.py')
    arbre = ast.parse(src)
    const = {}
    for n in arbre.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            try:
                const[n.targets[0].id] = ast.literal_eval(n.value)
            except Exception:
                pass
    verifie("FREEZE_DATE_AMPLI = 2026-09-12",
            const.get('FREEZE_DATE_AMPLI') == '2026-09-12',
            f"trouvé : {const.get('FREEZE_DATE_AMPLI')!r}")
    verifie("l'ancien gel du 07/09 est conservé comme invalidé",
            const.get('FREEZE_DATE_AMPLI_V1') == '2026-09-07',
            f"trouvé : {const.get('FREEZE_DATE_AMPLI_V1')!r}")
    verifie("le seuil et la fenêtre n'ont PAS été réoptimisés",
            const.get('H14_MOVE_MIN_PCT') == 5.0
            and const.get('H14_LEAD_MIN') == 480.0
            and const.get('H14_LEAD_MAX') == 1440.0,
            "un paramètre a bougé — un regel n'est pas une occasion de "
            "réajuster")


# ─────────────────────────────────────────────────────────────────────────
# T4 (statique) — la note de fiabilité est écrite dans la branche FORWARD
# ─────────────────────────────────────────────────────────────────────────
def t4_statique():
    print("\nT4 — paper_journal.py : note de fiabilité en branche forward")
    src = source('paper_journal.py')
    arbre = ast.parse(src)

    main = next((n for n in arbre.body
                 if isinstance(n, ast.FunctionDef) and n.name == 'main'), None)
    verifie("main() trouvée", main is not None)
    if main is None:
        return

    # La branche BACKFILL se termine par un `return` ; tout ce qui suit est
    # la branche forward, la seule à persister le journal.
    branche_backfill = None
    for n in ast.walk(main):
        if isinstance(n, ast.If) and 'BACKFILL' in ast.unparse(n.test):
            branche_backfill = n
            break
    lignes_backfill = set()
    if branche_backfill is not None:
        lignes_backfill = set(range(branche_backfill.lineno,
                                    (branche_backfill.end_lineno or 0) + 1))

    # site de création forward : l'affectation trades[tid] = {...}
    creations = [n for n in ast.walk(main)
                 if isinstance(n, ast.Assign)
                 and ast.unparse(n.targets[0]) == 'trades[tid]'
                 and n.lineno not in lignes_backfill]
    verifie("la branche forward crée bien un trade",
            len(creations) == 1,
            f"{len(creations)} site(s) de création hors BACKFILL")

    ecritures = [n for n in ast.walk(main)
                 if isinstance(n, (ast.Assign, ast.Tuple))
                 and 'fiabilite_score' in ast.unparse(n)
                 and n.lineno not in lignes_backfill]
    verifie("fiabilite_score est écrit hors de la branche BACKFILL",
            len(ecritures) > 0,
            "le score n'existe que dans BACKFILL, qui ne persiste rien : "
            "la piste P9 n'atteindra jamais son n")

    if creations and ecritures:
        verifie("le score est écrit APRÈS la création du trade forward",
                min(e.lineno for e in ecritures) > creations[0].lineno)

    # bug du composant book_en_retard
    verifie("book_en_retard n'utilise plus sig['pct'] (pourcentage entier)",
            "sig['odds'] * (sig.get('pct')" not in src,
            "odds x pct - 1 vaut toujours >> 3 % : le composant était +1 "
            "pour tous les paris")
    verifie("book_en_retard utilise sig['ev']",
            src.count("sig['ev'] >= 0.03") >= 2,
            "les deux branches doivent utiliser la même définition")


# ─────────────────────────────────────────────────────────────────────────
# T5 (fonctionnel) — move_audit.py sur de VRAIES courbes de production
# ─────────────────────────────────────────────────────────────────────────
def t5_fonctionnel():
    print("\nT5 — move_audit.py sur données de production réelles")
    courbes = os.environ.get('CURVES_T')
    if not courbes or not os.path.exists(courbes):
        verifie("courbes de test disponibles", False,
                f"CURVES_T absent ou introuvable ({courbes!r})")
        return
    sortie = os.path.join(tempfile.mkdtemp(), 'moves_test.csv')
    env = dict(os.environ, CURVES=courbes, OUT=sortie)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'move_audit.py')],
                       env=env, capture_output=True, text=True, timeout=900)
    verifie("move_audit.py s'exécute sans erreur", r.returncode == 0,
            (r.stderr or '')[-300:])
    if r.returncode != 0 or not os.path.exists(sortie):
        return

    with open(sortie, encoding='utf-8') as f:
        lignes = list(csv.DictReader(f))
    verifie("le CSV contient des moves", len(lignes) > 0)
    if not lignes:
        return
    verifie("en-tête : mag_cote_pct ET mag_cote_pct_POSTHOC",
            'mag_cote_pct' in lignes[0] and 'mag_cote_pct_POSTHOC' in lignes[0])

    # La colonne POSTHOC DOIT être (pin_open - pin_close)/pin_open.
    # La colonne causale NE DOIT PAS l'être.
    exact_posthoc, exact_causale, n = 0, 0, 0
    for r_ in lignes:
        try:
            po, pc = float(r_['pin_open']), float(r_['pin_close'])
            att = (po - pc) / po * 100 if po else None
            mc, mp = float(r_['mag_cote_pct']), float(r_['mag_cote_pct_POSTHOC'])
        except (TypeError, ValueError, KeyError):
            continue
        if att is None:
            continue
        n += 1
        # tolérance 0,6 pt : pin_open/pin_close sont arrondis à 2 décimales
        # dans le CSV, la formule interne ne l'est pas.
        if abs(mp - att) <= 0.6:
            exact_posthoc += 1
        if abs(mc - att) <= 0.6:
            exact_causale += 1
    verifie("mag_cote_pct_POSTHOC = (pin_open - pin_close)/pin_open",
            n and exact_posthoc / n > 0.98,
            f"{exact_posthoc}/{n}")
    verifie("mag_cote_pct ne reproduit PAS la formule sur la clôture",
            n and exact_causale / n < 0.50,
            f"{exact_causale}/{n} lignes identiques à la valeur "
            f"rétrospective — la colonne causale n'en est pas une")


# ─────────────────────────────────────────────────────────────────────────
# T6 (fonctionnel) — les gardes refusent réellement un vieux CSV
# ─────────────────────────────────────────────────────────────────────────
def t6_fonctionnel():
    print("\nT6 — un CSV d'avant le correctif est refusé, pas relu")
    src_csv = os.path.join(RACINE, 'moves_detail_hist.csv')
    if not os.path.exists(src_csv):
        verifie("moves_detail_hist.csv présent", False, src_csv)
        return
    tmp = tempfile.mkdtemp()
    # on fabrique la version ANCIENNE : sans la colonne _POSTHOC
    with open(src_csv, encoding='utf-8') as f:
        lecteur = csv.DictReader(f)
        cols = [c for c in (lecteur.fieldnames or [])
                if c != 'mag_cote_pct_POSTHOC']
        with open(os.path.join(tmp, 'moves_detail_hist.csv'), 'w',
                  newline='', encoding='utf-8') as g:
            w = csv.DictWriter(g, fieldnames=cols)
            w.writeheader()
            for r_ in lecteur:
                w.writerow({c: r_.get(c, '') for c in cols})

    code = (
        "import os,sys;sys.path.insert(0,%r);"
        "os.chdir(%r);"
        "import pistes_common as pc, validation_report as vr;"
        "m=pc.charge_moves();"
        "v=vr.roi_ampli_watch();"
        "print('MOVES=%%d' %% len(m));"
        "print('AMPLI=%%s' %% (v is None))"
        % (os.path.abspath(SCRIPTS), tmp))
    r = subprocess.run([sys.executable, '-c', code],
                       capture_output=True, text=True, timeout=300)
    sortie = (r.stdout or '') + (r.stderr or '')
    verifie("pistes_common refuse le vieux CSV (0 move chargé)",
            'MOVES=0' in sortie, sortie[-300:])
    verifie("roi_ampli_watch refuse le vieux CSV (retourne None)",
            'AMPLI=True' in sortie, sortie[-300:])


# ─────────────────────────────────────────────────────────────────────────
# T7 (fonctionnel, données réelles) — preuve du bug `pct`
# ─────────────────────────────────────────────────────────────────────────
def t7_fonctionnel():
    print("\nT7 — preuve sur le journal réel que l'ancien composant était "
          "toujours +1")
    jrn = os.path.join(RACINE, 'paper_trades_match.jsonl')
    if not os.path.exists(jrn):
        print("  (journal absent — test sauté)")
        return
    trades = [json.loads(l) for l in open(jrn, encoding='utf-8') if l.strip()]
    # `pct` vaut 0 quand le book n'a pas de track record à ce palier : dans
    # ce cas l'ancienne formule renvoyait None (composant neutre). Le test
    # porte donc sur les paris où pct est renseigné — ceux où l'ancien
    # composant se déclenchait.
    avec = [t for t in trades
            if isinstance(t.get('entry_odds'), (int, float))
            and isinstance(t.get('entry_pct_hist'), (int, float))
            and t['entry_pct_hist']]
    if not avec:
        print("  (aucun trade exploitable — test sauté)")
        return
    toujours = sum(1 for t in avec
                   if (t['entry_odds'] * t['entry_pct_hist'] - 1) * 100 >= 3)
    verifie("ancienne formule : +1 sur 100 % des paris à pct renseigné "
            f"({toujours}/{len(avec)})",
            toujours == len(avec),
            "si ce n'est pas 100 %, revoir le diagnostic avant d'appliquer "
            "le correctif")


def main():
    print(f"Scripts testés : {os.path.abspath(SCRIPTS)}")
    t1_statique()
    t2_statique()
    t3_statique()
    t4_statique()
    if os.environ.get('STATIQUES_SEULEMENT') != '1':
        t5_fonctionnel()
        t6_fonctionnel()
        t7_fonctionnel()
    print(f"\n{len(oks)} test(s) OK · {len(echecs)} échec(s)")
    if echecs:
        for e in echecs:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
