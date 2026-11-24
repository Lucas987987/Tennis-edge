#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pronostics_prives.py — les pronostics À VENIR ne sont plus lisibles dans le dépôt public (23/11/2026, paquet 378,
Lucas : « on passe le reste en privé », pour l'accès Plus payant).

Constat : le site ne sert plus les % réservés qu'aux comptes Plus (paquet 377), mais le dépôt GitHub (public) contenait
encore, en clair : algo/donnees.json (tout le site), simulateur/pronostics_log.jsonl (premier pronostic de chaque
match), simulateur/journal_pronostics/AAAA-MM-JJ.jsonl.gz (chaque passage) et simulateur/journal_pronostics/fiches/
(premier et dernier pronostic figés). N'importe qui pouvait y lire les % des matchs à venir.

Principe : PUBLICATION DIFFÉRÉE.
  • La version COMPLÈTE de ces fichiers vit au coffre R2 (prive/pronostics_complets/<chemin>), jamais dans git.
  • La copie git ne garde que les matchs DÉJÀ COMMENCÉS (début planifié passé) : une fois le match lancé, le pronostic
    n'a plus rien de réservé, il est déjà public dans les bilans. algo/donnees.json devient la version libre du site
    (le match du jour complet, les autres matchs à l'affiche seulement).
  • Les scripts qui ne regardent que le passé (études, après-match, résolution des résultats, fantômes) lisent la
    copie git sans rien changer. Ceux qui ont besoin des matchs à venir rapatrient la version complète (pull).

Actions :
  pull     rapatrie la version complète (écrase les copies git) et note ce qui a été rapatrié (.pronostics_prives) ;
  push     renvoie la version complète au coffre — SEULEMENT si ce run l'a rapatriée (ou si le coffre n'a encore rien) :
           une copie git filtrée n'écrase jamais le coffre ;
  public   réécrit les copies locales en version publique (à faire juste avant le commit) ;
  rendre   remet les copies git (workflow qui n'a fait que lire, avant ses opérations git).
Un seul rédacteur : pronostics_quotidien.yml (groupe de concurrence « pronostics »).
Usage : python scripts/pronostics_prives.py pull|push|public|rendre [racine]
"""
import datetime as dt
import glob
import hashlib
import gzip
import json
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

PREFIXE = 'prive/pronostics_complets/'
DONNEES = 'algo/donnees.json'
LOG = 'simulateur/pronostics_log.jsonl'
JOURNAL = 'simulateur/journal_pronostics'
FICHES = 'simulateur/journal_pronostics/fiches'
MARQUE = '.pronostics_prives'
# 24/11/2026 (paquet 414, Lucas : « stocker sur Cloudflare comme le reste ») : le coffre garde aussi les journaux figés
# des lignes et des statistiques prévues (simulateur/journal_pronostics/*_v1.jsonl : version complète au coffre, git
# n'a que les matchs commencés — ils contenaient en clair les prévisions des matchs à venir), les bilans après match
# (apres_match/*.json.gz) et les résultats jugés (pronostics_resultats.json, matchs passés seulement : identiques).
# Git n'en reçoit plus qu'une photo toutes les 2 h (pronostics_quotidien.yml) : R2 fait foi entre deux photos.
RESULTATS = 'Tennis_Edge_Lab/live/pronostics_resultats.json'
APRES = 'simulateur/journal_pronostics/apres_match'


def fichiers_locaux(racine):
    out = [DONNEES, LOG, RESULTATS]
    out += sorted(os.path.relpath(p, racine) for p in glob.glob(os.path.join(racine, JOURNAL, '20*.jsonl.gz')))
    out += sorted(os.path.relpath(p, racine) for p in glob.glob(os.path.join(racine, JOURNAL, '*_v1.jsonl')))
    out += sorted(os.path.relpath(p, racine) for p in glob.glob(os.path.join(racine, APRES, '20*.json.gz')))
    out += sorted(os.path.relpath(p, racine) for p in glob.glob(os.path.join(racine, FICHES, '20*.json.gz')))
    return [f for f in out if os.path.exists(os.path.join(racine, f))]


def _maintenant():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec='minutes')


def commence(debut, maintenant):
    """Début planifié (UTC, « AAAA-MM-JJTHH:MM ») passé : le pronostic n'est plus réservé."""
    return bool(debut) and str(debut)[:16] <= maintenant[:16]


# --------------------------------------------------------------------------------------------- versions publiques
def public_log(texte, maintenant):
    out = []
    for l in texte.splitlines():
        if not l.strip():
            continue
        try:
            r = json.loads(l)
            if commence(r.get('debut') or r.get('debut_utc'), maintenant):     # 414 : journaux figés (debut_utc)
                out.append(l)
        except ValueError:
            continue
    return ''.join(x + '\n' for x in out)


def public_fiches(doc, maintenant):
    return {u: v for u, v in (doc or {}).items() if isinstance(v, dict) and commence(v.get('debut'), maintenant)}


def public_donnees(doc, maintenant=None):
    sys.path.insert(0, ICI)
    import site_leger as SL
    t = dt.datetime.fromisoformat(str(maintenant or _maintenant())[:16]).replace(tzinfo=dt.timezone.utc)
    return SL.libre(doc, t)


def _lire_gz_lignes(p):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        return f.read()


def _ecrire_gz(p, texte):
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        f.write(texte)


def rendre_public(racine, maintenant=None):
    """Réécrit les copies locales en version publique ; renvoie {fichier: (lignes gardées, lignes au total)}."""
    maintenant = maintenant or _maintenant()
    bilan = {}
    p = os.path.join(racine, DONNEES)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            doc = json.load(f)
        pub = public_donnees(doc, maintenant)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(pub, f, ensure_ascii=False, separators=(',', ':'))
        bilan[DONNEES] = (sum(1 for m in pub.get('matchs') or [] if not m.get('verrou')), len(doc.get('matchs') or []))
    p = os.path.join(racine, LOG)
    if os.path.exists(p):
        t = open(p, encoding='utf-8').read()
        pub = public_log(t, maintenant)
        open(p, 'w', encoding='utf-8').write(pub)
        bilan[LOG] = (pub.count('\n'), sum(1 for l in t.splitlines() if l.strip()))
    for p in sorted(glob.glob(os.path.join(racine, JOURNAL, '20*.jsonl.gz'))):
        t = _lire_gz_lignes(p)
        pub = public_log(t, maintenant)
        if pub != t:
            _ecrire_gz(p, pub)
        bilan[os.path.relpath(p, racine)] = (pub.count('\n'), sum(1 for l in t.splitlines() if l.strip()))
    for p in sorted(glob.glob(os.path.join(racine, JOURNAL, '*_v1.jsonl'))):      # 414 : journaux figés
        t = open(p, encoding='utf-8').read()
        pub = public_log(t, maintenant)
        if pub != t:
            open(p, 'w', encoding='utf-8').write(pub)
        bilan[os.path.relpath(p, racine)] = (pub.count('\n'), sum(1 for l in t.splitlines() if l.strip()))
    for p in sorted(glob.glob(os.path.join(racine, FICHES, '20*.json.gz'))):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            doc = json.load(f)
        pub = public_fiches(doc, maintenant)
        if len(pub) != len(doc):
            with gzip.open(p, 'wt', encoding='utf-8') as f:
                json.dump(pub, f, ensure_ascii=False, separators=(',', ':'))
        bilan[os.path.relpath(p, racine)] = (len(pub), len(doc))
    return bilan


# --------------------------------------------------------------------------------------------- coffre
def pull(r2, racine, seulement=None):
    """Rapatrie les versions complètes du coffre (seulement : ce fichier ou ce dossier) ; renvoie le nombre.
    Sans « seulement », le run devient rédacteur : il pourra renvoyer au coffre (push)."""
    n, vus = 0, {}
    for cle, _ in r2.list(PREFIXE + (seulement or '')):
        rel = cle[len(PREFIXE):]
        if not rel or '..' in rel.split('/') or not (rel in (DONNEES, LOG, RESULTATS) or rel.startswith(JOURNAL + '/')):
            continue
        got = r2.get_with_etag(cle)
        if got is None:
            continue
        p = os.path.join(racine, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(got[0])
        n += 1
        vus[rel] = hashlib.sha256(got[0]).hexdigest()
    if not seulement:
        with open(os.path.join(racine, MARQUE), 'w', encoding='utf-8') as f:
            json.dump({'rapatries': vus, 'le': _maintenant()}, f)
    print(f"Pronostics complets : {n} fichier(s) rapatrié(s) du coffre")
    return n


def push(r2, racine):
    """Envoie la version complète ; refuse si ce run n'a pas rapatrié le coffre alors qu'il en a déjà une."""
    marque = os.path.join(racine, MARQUE)
    try:
        with open(marque, encoding='utf-8') as f:
            rapatries = json.load(f).get('rapatries') or {}
        lu = True
    except (OSError, ValueError):
        rapatries, lu = {}, False
    deja = any(True for _ in r2.list(PREFIXE))
    if deja and not lu:
        print("::warning::Pronostics complets : pas rapatriés dans ce run — rien n'est envoyé (le coffre est gardé)")
        return 1
    n = 0
    for rel in fichiers_locaux(racine):
        with open(os.path.join(racine, rel), 'rb') as f:
            data = f.read()
        if rapatries.get(rel) == hashlib.sha256(data).hexdigest():
            continue                                     # inchangé depuis le pull
        r2.put(PREFIXE + rel, data, content_type='application/octet-stream')
        n += 1
    print(f"Pronostics complets : {n} fichier(s) envoyé(s) au coffre")
    return 0


def rendre(racine):
    suivis = subprocess.run(['git', 'ls-files', '--', DONNEES, LOG, JOURNAL, RESULTATS], capture_output=True, text=True,
                            cwd=racine).stdout.split()
    if suivis:
        subprocess.run(['git', 'checkout', '--', *suivis], check=False, cwd=racine)
    try:
        os.remove(os.path.join(racine, MARQUE))
    except OSError:
        pass
    print(f"Pronostics : {len(suivis)} copie(s) git remise(s)")


def main(argv):
    seulement = None
    if '--seulement' in argv:
        i = argv.index('--seulement')
        seulement = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    action = argv[1] if len(argv) > 1 else ''
    racine = argv[2] if len(argv) > 2 else '.'
    if action == 'public':
        b = rendre_public(racine)
        tot = sum(v[1] for v in b.values())
        print(f"Version publique : {len(b)} fichier(s), {sum(v[0] for v in b.values())} lignes gardées sur {tot}")
        return 0
    if action == 'rendre':
        rendre(racine)
        return 0
    import r2_io
    r2 = r2_io.client()
    if r2 is None:
        print('Pronostics complets : R2 indisponible — rien à faire.')
        return 1 if action == 'pull' else 0
    if action == 'pull':
        pull(r2, racine, seulement)
        return 0
    if action == 'push':
        return push(r2, racine)
    print('Usage : pronostics_prives.py pull|push|public|rendre [racine]')
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
