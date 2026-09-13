#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""carto_fichiers.py — LECTURE SEULE. Qui écrit quoi, qui lit quoi.

Sur un dépôt de 127 scripts et 52 workflows, savoir quel producteur alimente
quel fichier, et lesquels ne sont lus par personne, a une valeur directe :
deux producteurs de mesures fausses ont été trouvés en deux jours, et dans
les deux cas le symptôme était visible dans un fichier que personne
n'inspectait.

MÉTHODE ET SES LIMITES
Analyse statique par recherche du nom de fichier dans `scripts/*.py` et
`.github/workflows/*.yml`. Les noms passés par variable d'environnement
(`os.environ.get('LEDGER', 'canal_clv_detail.csv')`) sont suivis en
remontant à la variable, puis en cherchant son usage en écriture. Un chemin
construit dynamiquement (f-string, concaténation) échappe à la détection :
ce rapport signale des CANDIDATS, il ne prouve pas qu'un fichier est mort.
Toute ligne "orphelin" doit être vérifiée à la main avant suppression.

Usage : python3 carto_fichiers.py [--tout]
        --tout : liste aussi les fichiers correctement rattachés
"""
import os
import re
import sys

RACINE = '.'
SCRIPTS = 'scripts'
WORKFLOWS = os.path.join('.github', 'workflows')
EXT_DATA = ('.json', '.jsonl', '.csv', '.md', '.txt', '.gz')
IGNORE = {'README.md', 'requirements.txt', '.gitignore', '.gitattributes'}

ECRITURE = (
    r"open\(\s*{v}[^)]*['\"][wa]",
    r"ecriture_atomique\(\s*{v}",
    r"to_csv\(\s*{v}",
    r"json\.dump\([^)]*{v}",
    r"{v}\s*\+\s*['\"]\.tmp",
    r"os\.replace\(\s*[^,]*,\s*{v}",
)


def lire(p):
    try:
        with open(p, encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ''


def variables_pour(src, nom):
    """Variables auxquelles ce nom de fichier est affecté."""
    out = set()
    for m in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=.*"
                         + re.escape(nom), src, re.M):
        out.add(m.group(1))
    return out


def ecrit(src, nom):
    cands = {re.escape(nom)} | {re.escape(v) for v in variables_pour(src, nom)}
    for v in cands:
        for pat in ECRITURE:
            if re.search(pat.format(v=v), src):
                return True
    # écriture via un chemin littéral entre guillemets
    if re.search(r"open\(\s*['\"]" + re.escape(nom) + r"['\"]\s*,\s*['\"][wa]", src):
        return True
    return False


def main():
    tout = '--tout' in sys.argv
    fichiers = sorted(f for f in os.listdir(RACINE)
                      if os.path.isfile(f) and f.endswith(EXT_DATA)
                      and f not in IGNORE and not f.startswith('.'))
    srcs = {}
    for d in (SCRIPTS, WORKFLOWS):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(('.py', '.yml', '.yaml', '.sh')):
                srcs[os.path.join(d, f)] = lire(os.path.join(d, f))

    orphelins, sans_lecteur, sans_producteur, ok = [], [], [], []
    for nom in fichiers:
        prod = [p for p, s in srcs.items() if nom in s and ecrit(s, nom)]
        ment = [p for p, s in srcs.items() if nom in s]
        lect = [p for p in ment if p not in prod]
        taille = os.path.getsize(nom)
        ligne = (nom, taille, prod, lect)
        if not ment:
            orphelins.append(ligne)
        elif not lect:
            sans_lecteur.append(ligne)
        elif not prod:
            sans_producteur.append(ligne)
        else:
            ok.append(ligne)

    def bloc(titre, items, note):
        print(f"\n{'=' * 66}\n{titre}  ({len(items)})\n{note}\n{'=' * 66}")
        for nom, taille, prod, lect in sorted(items, key=lambda x: -x[1]):
            print(f"  {taille/1024:9.0f} Ko  {nom}")
            if prod:
                print(f"               écrit par : {', '.join(os.path.basename(p) for p in prod[:4])}")
            if lect:
                print(f"               lu par    : {', '.join(os.path.basename(p) for p in lect[:6])}"
                      + (f" (+{len(lect)-6})" if len(lect) > 6 else ""))

    bloc("ORPHELINS — cités par aucun script ni workflow", orphelins,
         "Candidats à la suppression. À VÉRIFIER : un chemin construit "
         "dynamiquement échappe à la détection.")
    bloc("ÉCRITS MAIS JAMAIS LUS", sans_lecteur,
         "Un producteur tourne et personne n'exploite sa sortie. "
         "Soit un consommateur manque, soit le producteur est à arrêter.")
    bloc("LUS MAIS SANS PRODUCTEUR IDENTIFIÉ", sans_producteur,
         "Souvent un faux positif (écriture via variable non suivie), "
         "parfois un fichier alimenté à la main et jamais régénéré.")
    if tout:
        bloc("RATTACHÉS", ok, "Un producteur, au moins un lecteur.")
    else:
        print(f"\n{len(ok)} fichier(s) correctement rattaché(s) "
              f"(--tout pour les lister)")
    print("\nAUCUN FICHIER MODIFIÉ.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
