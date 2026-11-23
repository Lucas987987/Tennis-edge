#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""discret.py — lancer un script SANS que son détail arrive dans le journal GitHub (23/11/2026, paquet 393, Lucas :
« fais un audit complet des journaux de tous les workflows »).

Le dépôt est public : le journal de chaque run GitHub Actions l'est aussi. Beaucoup de scripts d'étude et de collecte
y écrivaient des chiffres privés (cotes, CLV, ROI, bookmakers, comparaisons aux cotes de clôture). Ce lanceur exécute
la commande en capturant tout ce qu'elle écrit et ne montre dans le journal que :
  • une ligne de bilan : nom du script, code de sortie, nombre de lignes écrites ;
  • les annotations GitHub « ::error:: » et « ::warning:: » (messages techniques, sans chiffres privés) ;
  • en cas d'échec, la trace Python (à partir de « Traceback ») : le code, pas les données.
Le journal COMPLET part, si les secrets sont là :
  • au coffre R2 privé (prive/site/Tennis_Edge_Lab/journaux/<jour>/<workflow>-<run>-<script>.log), lisible dans le Lab
    (/lab/journaux/…, avec la clé) ;
  • sur le Telegram privé, en cas d'échec seulement (les 3 500 derniers caractères).
--copie FICHIER (ou --ajout FICHIER) : écrit aussi la sortie complète dans ce fichier (comme « | tee » / « | tee -a »).
Le code de sortie est celui de la commande.
Usage : python scripts/discret.py [--copie F | --ajout F] -- python scripts/etude.py arg1 arg2
"""
import datetime as dt
import os
import re
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
GARDE = re.compile(r'^::(error|warning)(\s[^:]*)?::')


def resume(sortie):
    """Ce qui peut aller dans le journal public."""
    lignes = sortie.splitlines()
    out = [l for l in lignes if GARDE.match(l)]
    for i, l in enumerate(lignes):
        if l.startswith('Traceback (most recent call last):'):
            out.append('\n'.join(lignes[i:]))
            break
    return out, len(lignes)


def nom_script(cmd):
    for x in cmd:
        if x.endswith(('.py', '.mjs', '.js', '.sh')):
            return os.path.basename(x)
    return os.path.basename(cmd[0]) if cmd else 'commande'


def vers_coffre(cle, texte):
    if not (os.environ.get('R2_ACCESS_KEY_ID') and os.environ.get('R2_SECRET_ACCESS_KEY') and os.environ.get('R2_ENDPOINT')):
        return False
    try:
        sys.path.insert(0, ICI)
        import r2_io
        c = r2_io.client(quiet=True)
        if not c:
            return False
        c.put(cle, texte.encode('utf-8'))
        return True
    except Exception:  # noqa: BLE001 — jamais bloquant
        return False


def vers_telegram(titre, texte):
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not (tok and chat):
        return False
    try:
        sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
        import telegram_envoi as TE
        return bool(TE.envoyer(f"{titre}\n{texte[-3500:]}", html=False, tok=tok, chat=chat))
    except Exception:  # noqa: BLE001
        return False


def main(argv):
    args = argv[1:]
    copie, mode = None, 'w'
    while args and args[0] in ('--copie', '--ajout'):
        mode = 'a' if args[0] == '--ajout' else 'w'
        copie, args = args[1], args[2:]
    if args and args[0] == '--':
        args = args[1:]
    if not args:
        print('usage : discret.py [--copie F | --ajout F] -- commande …')
        return 2
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sortie = p.stdout.decode('utf-8', errors='replace')
    if copie:
        with open(copie, mode, encoding='utf-8') as f:
            f.write(sortie)
    nom = nom_script(args)
    publics, n = resume(sortie)
    jour = dt.datetime.now(dt.timezone.utc).date().isoformat()
    wf = re.sub(r'[^A-Za-z0-9_.-]+', '_', os.environ.get('GITHUB_WORKFLOW', 'local'))[:60]
    cle = f"prive/site/Tennis_Edge_Lab/journaux/{jour}/{wf}-{os.environ.get('GITHUB_RUN_ID', '0')}-{nom}.log"
    garde = vers_coffre(cle, sortie)
    if p.returncode:
        vers_telegram(f"❌ {wf} · {nom} (code {p.returncode})", sortie)
    for l in publics:
        print(l)
    ou = f" · journal complet : /lab/{cle[len('prive/site/Tennis_Edge_Lab/'):]}" if garde else ''
    print(f"{nom} : {'terminé' if p.returncode == 0 else 'ÉCHEC (code %d)' % p.returncode} · {n} lignes écrites, "
          f"non affichées (journal public){ou}")
    return p.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv))
