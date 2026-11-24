#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cotes_privees.py — COTES EN PRIVÉ, ÉTAPE 3 (22/11/2026, paquet 346, Lucas : « basculer un maximum de choses en
privé ») : les fichiers de cotes quittent le dépôt public.

  chauds   closing_lines.json, matches_oddspapi.json, live_odds.json — déjà relayés par R2 (etat_chaud.py, préfixe
           « chaud/ », fusion par clé des accumulateurs) ;
  froids   closing_lines/closing_lines_AAAA-MM.jsonl — archives mensuelles (ajout seul), au coffre (coffre.py,
           préfixe « prive/closing_lines/ »).

INTERRUPTEUR : la variable de dépôt ETAT_CHAUD (déjà utilisée par etat_chaud.py).
  off / double / on : rien ne change pour les lecteurs (ils lisent le dépôt). Les écrivains envoient en plus les
                      archives au coffre à chaque passage, pour que le coffre soit complet le jour de la bascule.
  prive             : R2 fait foi, git ne reçoit plus AUCUNE copie. Chaque workflow qui lit ces fichiers les rapatrie
                      au début (pull) ; la capture les sort du suivi git (retirer) une fois que R2 en a une copie.
RETOUR ARRIÈRE : remettre ETAT_CHAUD à « on » ; au passage suivant, la capture rapatrie de R2 ce qui manque dans le
dépôt (pull, même hors « prive ») et le republie — rien n'est perdu.

22/11/2026 (paquet 351, Lucas : « Cotes privées, étape 3b ») — fichiers ENTIERS, même interrupteur, même retour arrière :
  mouvements           moves_detail.csv, moves_detail_hist.csv, moves_detail_live.csv (cotes d'ouverture et de
                       clôture, books, CLV, P&L par mouvement), suivi_direct/resultats.json (clôture, CLV et P&L des
                       alertes en direct, journaux privés compris) — rédacteur : steam_pipeline ;
  resultats_reglement  resultats_oddspapi.json (résultats du règlement de la source de cotes) — rédacteur :
                       fetch_results_settlement.
  Au coffre (coffre.py, groupes du même nom). Le rédacteur envoie à chaque passage (push --groupe …), quel que soit
  le mode ; en « prive », il les sort du dépôt (retirer --groupe …). Hors « prive », un lecteur ne rapatrie que ce
  qui n'est NI sur le disque NI suivi par git (retour arrière) : jamais une copie par-dessus celle du dépôt.
  age FICHIER : âge en heures de la copie du coffre (observateur externe, quand le fichier n'est plus dans git).
22/11/2026 (paquet 352, Lucas : « Étape 4 : le reste en privé ») — mêmes règles, un groupe par rédacteur :
  kalshi (polymarket_studies), courbes_absences (fetch_book_curves), value (value_journal), book_lag (book_lag),
  calibration (calibration_buckets), direct (courbes_alertes : early_open_log.jsonl, direct_matchs.json) et figes
  (fichiers sans rédacteur — games_markets, economic_v64, selection_v64_frozen, rapports d'écart à la clôture —
  envoyés tels quels et retirés par lab_quotidien). Les registres de gels du Lab restent publics : leur date dans git
  prouve qu'ils ont été écrits avant les résultats.
  pull --entiers G1,G2 | aucun : les workflows fréquents ne rapatrient que ce qu'ils lisent (défaut : tout).
  site : courbes_alertes envoie direct_matchs.json, live_odds.json et matches_oddspapi_meta.json au site privé du Lab
         (prive/site/Tennis_Edge_Lab/direct/), que l'onglet Direct lit avant GitHub.

Sans secrets R2 : tout est ignoré, rien ne casse. Jamais de nom de fichier ni de cote dans les journaux d'Actions :
des nombres seulement.

Usage : python scripts/cotes_privees.py pull [--entiers G,…|aucun] | push [--groupe G] | retirer [--groupe G]
                                       | age FICHIER | site
  pull     lecteurs et écrivains, au début : en « prive », tout ; sinon, seulement ce qui MANQUE dans le dépôt
           (retour arrière). En « prive », les fichiers sont aussi exclus de git sur ce runner (.git/info/exclude),
           pour qu'un « git add -A » ne les republie jamais.
  push     écrivains, à la fin : archives froides vers le coffre (les fichiers chauds passent par etat_chaud.py push).
  retirer  la capture seulement, en « prive » : git rm --cached des fichiers que R2 détient.
"""
import glob
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

CHAUDS = ('closing_lines.json', 'matches_oddspapi.json', 'live_odds.json')
DOSSIER = 'closing_lines'
GROUPES_ENTIERS = ('mouvements', 'resultats_reglement',      # 351 : groupes de coffre.py
                   'kalshi', 'courbes_absences', 'value', 'book_lag', 'calibration', 'direct', 'figes')   # 352
SITE_DIRECT = ('direct_matchs.json', 'live_odds.json', 'matches_oddspapi_meta.json')
PREFIXE_SITE_DIRECT = 'prive/site/Tennis_Edge_Lab/direct/'
# 24/11/2026 (paquet 416, contrôle des fuites) : la probabilité tirée des cotes pour les matchs à venir (ligne « Cote
# Pinnacle » du Lab) n'est plus commitée dans le dépôt public : elle part seulement au site privé du Lab.
SITE_LAB = (('Tennis_Edge_Lab/live/pronostics_marche.json', 'prive/site/Tennis_Edge_Lab/live/pronostics_marche.json'),)
EXCLUSIONS = ['/closing_lines.json', '/matches_oddspapi.json', '/live_odds.json', '/closing_lines/',
              '/moves_detail.csv', '/moves_detail_hist.csv', '/moves_detail_live.csv', '/suivi_direct/resultats.json',
              '/resultats_oddspapi.json']


def mode(environ=None):
    m = str((environ if environ is not None else os.environ).get('ETAT_CHAUD', 'double')).strip().lower()
    return m if m in ('off', 'double', 'on', 'prive') else 'double'


def suivis(chemins):
    r = subprocess.run(['git', 'ls-files', '--', *chemins], capture_output=True, text=True)
    return set(r.stdout.split()) if r.returncode == 0 else set()


def exclusions():
    """Motifs exclus de git en mode « prive » : chauds, archives et tous les fichiers entiers des groupes."""
    out = list(EXCLUSIONS)
    for f in entiers():
        if '/' + f not in out:
            out.append('/' + f)
    return out


def exclure(racine='.'):
    """Ajoute les fichiers de cotes à .git/info/exclude (propre à ce runner, jamais publié)."""
    p = os.path.join(racine, '.git', 'info', 'exclude')
    if not os.path.isdir(os.path.dirname(p)):
        return False
    try:
        deja = open(p, encoding='utf-8').read().splitlines()
    except OSError:
        deja = []
    manque = [e for e in exclusions() if e not in deja]
    if manque:
        with open(p, 'a', encoding='utf-8') as f:
            f.write('\n# cotes au coffre privé (scripts/cotes_privees.py)\n' + '\n'.join(manque) + '\n')
    return True


def _coffre():
    import coffre as C
    return C


def entiers(groupe=None, groupes=None):
    C = _coffre()
    gs = (groupe,) if groupe else (tuple(groupes) if groupes is not None else GROUPES_ENTIERS)
    return [f for g in gs for f in C.GROUPES[g]]


def _muet(fn, *a):
    """Les journaux d'Actions sont publics : des nombres seulement (coffre.py affiche les noms)."""
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


def pull_entiers(r2, m, racine='.', groupes=None):
    """Nombre de fichiers entiers rapatriés. « prive » : tous ; sinon ceux ni sur le disque ni suivis par git.
    groupes : seulement ceux-là (None : tous)."""
    C = _coffre()
    fichiers = entiers(groupes=groupes)
    if m != 'prive':
        dans_git = suivis(fichiers)
        fichiers = [f for f in fichiers if f not in dans_git and not os.path.exists(os.path.join(racine, f))]
    n = 0
    for f in fichiers:
        avant = os.path.exists(os.path.join(racine, f))
        _muet(C.pull, [f], r2)
        n += int(os.path.exists(os.path.join(racine, f)) and (m == 'prive' or not avant))
    return n


def pull(r2, m, racine='.'):
    """(chauds rapatriés, archives rapatriées). En « prive » : tout ; sinon seulement ce qui manque en local."""
    import etat_chaud as EC
    C = _coffre()
    if m == 'prive':
        noms = CHAUDS
    else:
        noms = tuple(f for f in CHAUDS if not os.path.exists(os.path.join(racine, f)))
    pris = EC.pull(r2, noms, racine) if noms else {}
    archives = C.developper([DOSSIER + '/*'], r2)
    if m != 'prive':
        archives = [f for f in archives if not os.path.exists(os.path.join(racine, f))]
    if archives:
        C.pull(archives, r2)
    if m == 'prive':
        exclure(racine)
    return len(pris), len(archives)


def push_entiers(r2, groupe):
    """(fichiers présents, échecs) — le rédacteur du groupe seulement."""
    C = _coffre()
    fichiers = [f for f in entiers(groupe) if os.path.exists(f)]
    return len(fichiers), (_muet(C.push, fichiers, r2) if fichiers else 0)


def retirer_entiers(r2, groupe):
    """git rm --cached des fichiers du groupe encore suivis dont le coffre a une copie."""
    C = _coffre()
    fichiers = sorted(suivis(entiers(groupe)))
    if not fichiers:
        return 0
    _muet(C.retirer, fichiers, r2, True)
    return len(fichiers) - len(suivis(fichiers))


def site_direct(r2, racine='.'):
    """(envoyés, inchangés) — copies de l'onglet Direct du Lab dans le site privé (servi après connexion)."""
    envoyes = inchanges = 0
    for n, cle in [(n, PREFIXE_SITE_DIRECT + n) for n in SITE_DIRECT] + list(SITE_LAB):
        p = os.path.join(racine, n)
        if not os.path.exists(p):
            continue
        data = open(p, 'rb').read()
        if not data:
            continue
        got = r2.get_with_etag(cle)
        if got is not None and got[0] == data:
            inchanges += 1
            continue
        try:
            r2.put(cle, data, content_type='application/json; charset=utf-8')
            envoyes += 1
        except Exception:  # noqa: BLE001
            pass
    return envoyes, inchanges


def _groupes_arg(argv):
    """--entiers G1,G2 | aucun → tuple (None si absent). Valeur inconnue : ValueError."""
    if '--entiers' not in argv[:-1]:
        return None
    v = argv[argv.index('--entiers') + 1].strip()
    if v == 'aucun':
        return ()
    gs = tuple(g for g in v.split(',') if g)
    if not gs or any(g not in GROUPES_ENTIERS for g in gs):
        raise ValueError(v)
    return gs


def age_h(r2, f):
    """Âge en heures de la copie du coffre, ou None."""
    import datetime as dt
    C = _coffre()
    try:
        h = r2.client.head_object(Bucket=r2.bucket, Key=C.cle(f))
    except Exception:  # noqa: BLE001
        return None
    t = h.get('LastModified')
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def push(r2):
    C = _coffre()
    fichiers = sorted(glob.glob(os.path.join(DOSSIER, 'closing_lines_*.jsonl')))
    return C.push(fichiers, r2) if fichiers else 0, len(fichiers)


def retirer(r2):
    """git rm --cached : chauds dont R2 a une copie, archives que le coffre détient (même autre version : union)."""
    import etat_chaud as EC
    C = _coffre()
    out = 0
    for f in sorted(suivis(CHAUDS)):
        if r2.get_with_etag(EC.PREFIXE + f):
            subprocess.run(['git', 'rm', '--cached', '--quiet', '--', f], check=False)
            out += 1
    arch = sorted(suivis([DOSSIER]))
    if arch:
        avant = len(suivis([DOSSIER]))
        C.retirer(arch, r2, si_present=True)
        out += avant - len(suivis([DOSSIER]))
    return out


def main(argv):
    action = argv[1] if len(argv) > 1 else ''
    groupe = argv[argv.index('--groupe') + 1] if '--groupe' in argv[:-1] else None
    try:
        groupes = _groupes_arg(argv)
    except ValueError:
        print(__doc__)
        return 2
    if action not in ('pull', 'push', 'retirer', 'age', 'site') or (groupe is not None and groupe not in GROUPES_ENTIERS) \
            or (action == 'age' and len(argv) < 3):
        print(__doc__)
        return 2
    if action == 'age':
        import r2_io
        r2 = r2_io.client(quiet=True)
        a = age_h(r2, argv[2]) if r2 is not None else None
        print('' if a is None else int(a))
        return 0 if a is not None else 1
    m = mode()
    if m == 'off':
        print(f'Cotes privées : mode off ({action} ignoré)')
        return 0
    import r2_io
    r2 = r2_io.client(quiet=True)
    if r2 is None:
        print(f'Cotes privées : R2 absent ({action} ignoré)')
        return 0
    if action == 'pull':
        n_c, n_a = pull(r2, m)
        n_e = pull_entiers(r2, m, groupes=groupes)
        print(f'Cotes privées (mode {m}) : {n_c} fichier(s) chaud(s), {n_a} archive(s), {n_e} fichier(s) entier(s) rapatriés')
    elif action == 'site':
        n, i = site_direct(r2)
        print(f'Cotes privées : {n} fichier(s) envoyés au site privé du Lab ({i} inchangé(s))')
    elif action == 'push' and groupe:
        n, echecs = push_entiers(r2, groupe)
        print(f'Cotes privées : {n} fichier(s) envoyés au coffre ({echecs} échec(s))')
    elif action == 'push':
        echecs, n = push(r2)
        print(f'Cotes privées : {n} archive(s) envoyées au coffre ({echecs} échec(s))')
    else:
        if m != 'prive':
            print(f'Cotes privées : retirer ignoré (mode {m})')
            return 0
        n = retirer_entiers(r2, groupe) if groupe else retirer(r2)
        print(f'Cotes privées : {n} fichier(s) sortis du dépôt public')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
