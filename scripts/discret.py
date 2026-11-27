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
--pouls MINUTES (paquet 500, Steam pipeline coupé deux fois pendant validation_report.py sans rien laisser au journal) :
  toutes les MINUTES, une ligne technique dans le journal public — durée, mémoire du script, mémoire libre de la machine,
  dernier repère « ::progres:: » écrit par le script (numéro de bloc seulement). Les lignes « ::progres:: » ne sont
  jamais affichées autrement ; aucun chiffre privé n'y figure.
Le code de sortie est celui de la commande.
Usage : python scripts/discret.py [--copie F | --ajout F] [--pouls MIN] -- python scripts/etude.py arg1 arg2
"""
import datetime as dt
import os
import re
import subprocess
import sys
import threading
import time

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


def _ko(cle, chemin):
    """Valeur en Ko d'une ligne « Cle: 123 kB » de /proc (None si illisible : hors Linux, processus fini)."""
    try:
        with open(chemin, encoding='ascii', errors='replace') as f:
            for l in f:
                if l.startswith(cle + ':'):
                    return int(l.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _go(ko):
    if ko is None:
        return '?'
    return f"{ko // 1024} Mo" if ko < 1048576 else f"{ko / 1048576:.1f} Go".replace('.', ',')


def pouls_ligne(nom, debut, pid, repere):
    return (f"discret · {nom} · {int((time.monotonic() - debut) // 60)} min · mémoire du script "
            f"{_go(_ko('VmRSS', f'/proc/{pid}/status'))} (pic {_go(_ko('VmHWM', f'/proc/{pid}/status'))}) · "
            f"mémoire libre {_go(_ko('MemAvailable', '/proc/meminfo'))}" + (f" · {repere}" if repere else ''))


def executer(args, pouls=None, ecrire=print):
    """(code, sortie). Sortie lue au fil de l'eau ; avec pouls (minutes), une ligne technique à intervalle régulier."""
    env = dict(os.environ, PYTHONUNBUFFERED='1') if pouls else None
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    morceaux, etat, fini = [], {'repere': ''}, threading.Event()
    nom, debut = nom_script(args), time.monotonic()

    def battre():
        while not fini.wait(pouls * 60):
            ecrire(pouls_ligne(nom, debut, p.pid, etat['repere']))
            sys.stdout.flush()
    t = threading.Thread(target=battre, daemon=True) if pouls else None
    if t:
        t.start()
    for b in iter(p.stdout.readline, b''):
        morceaux.append(b)
        if b.startswith(b'::progres::'):
            etat['repere'] = b[len(b'::progres::'):].decode('utf-8', 'replace').strip()[:40]
    code = p.wait()
    fini.set()
    if t:
        try:
            import resource
            pic = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss      # Ko sous Linux
        except (ImportError, OSError):
            pic = None
        ecrire(f"discret · {nom} · {int((time.monotonic() - debut) // 60)} min · fin (code {code}) · pic de mémoire "
               f"{_go(pic)} · mémoire libre {_go(_ko('MemAvailable', '/proc/meminfo'))}"
               + (f" · {etat['repere']}" if etat['repere'] else ''))
    return code, b''.join(morceaux).decode('utf-8', errors='replace')


def main(argv):
    args = argv[1:]
    copie, mode, pouls = None, 'w', None
    while args and args[0] in ('--copie', '--ajout', '--pouls'):
        if args[0] == '--pouls':
            pouls, args = float(args[1]), args[2:]
            continue
        mode = 'a' if args[0] == '--ajout' else 'w'
        copie, args = args[1], args[2:]
    if args and args[0] == '--':
        args = args[1:]
    if not args:
        print('usage : discret.py [--copie F | --ajout F] -- commande …')
        return 2
    code, sortie = executer(args, pouls)
    if copie:
        with open(copie, mode, encoding='utf-8') as f:
            f.write(sortie)
    nom = nom_script(args)
    publics, n = resume(sortie)
    jour = dt.datetime.now(dt.timezone.utc).date().isoformat()
    wf = re.sub(r'[^A-Za-z0-9_.-]+', '_', os.environ.get('GITHUB_WORKFLOW', 'local'))[:60]
    cle = f"prive/site/Tennis_Edge_Lab/journaux/{jour}/{wf}-{os.environ.get('GITHUB_RUN_ID', '0')}-{nom}.log"
    garde = vers_coffre(cle, sortie)
    if code:
        vers_telegram(f"❌ {wf} · {nom} (code {code})", sortie)
    for l in publics:
        print(l)
    ou = f" · journal complet : /lab/{cle[len('prive/site/Tennis_Edge_Lab/'):]}" if garde else ''
    print(f"{nom} : {'terminé' if code == 0 else 'ÉCHEC (code %d)' % code} · {n} lignes écrites, "
          f"non affichées (journal public){ou}")
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv))
