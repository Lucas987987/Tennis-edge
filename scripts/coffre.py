#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coffre.py — le COFFRE PRIVÉ du projet (23/10/2026) : des fichiers qui ne doivent plus être lisibles dans le dépôt
public, rangés dans R2 (privé) sous le préfixe « prive/ ».

Pourquoi : le dépôt est public (les workflows y sont gratuits). Tout fichier commité se lit par n'importe qui.
Les canaux H18, H19 et H20 sont privés (« ne pas diffuser ») : leurs journaux et leurs états, les verdicts du Lab
qui en sortent et le pronostic complet du jour ne doivent plus être commités ni publiés sur GitHub Pages.

Fonctionnement, dans chaque workflow qui lit ou écrit ces fichiers :
  pull    : rapatrie depuis R2 la version du coffre (sinon garde la copie locale — premier passage) ;
  push    : renvoie au coffre les fichiers modifiés (écriture conditionnelle ; deux runs qui se croisent sur un
            journal .jsonl : les lignes des deux sont gardées) ;
  retirer : sort du suivi git les fichiers que le coffre détient À L'IDENTIQUE (git rm --cached) ; le .gitignore
            les empêche d'y revenir. Rien n'est retiré si R2 est indisponible : jamais de perte.
Le site public n'en reçoit rien ; Lucas les lit dans le Lab par le worker « algo » (/prive/…, clé privée).

Limite assumée : l'historique git (versions passées de ces fichiers) reste lisible — le réécrire demanderait un
push forcé, exclu sur ce dépôt.
Usage : python scripts/coffre.py pull|push|retirer [--groupe signaux|lab|pronostics|tous]
"""
import argparse
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2_io  # noqa: E402

PREFIXE = 'prive/'
GROUPES = {
    # écrits par courbes_alertes.yml (canaux privés)
    'signaux': ['h18_signal_log.jsonl', 'h18_signal_state.json', 'h19_signal_log.jsonl', 'h19_signal_state.json',
                'h20_signal_log.jsonl', 'h20_signal_state.json'],
    # écrits par lab_quotidien.yml (verdicts des canaux privés)
    'lab': ['Tennis_Edge_Lab/live/valeur.json', 'Tennis_Edge_Lab/live/h20.json'],
    # écrit par pronostics_quotidien.yml (pronostic complet du jour : réservé)
    'pronostics': ['Tennis_Edge_Lab/live/pronostics.json'],
}
# entrées du Lab quotidien : seul le journal H19 est relu (verdict de H19) ; le journal H18 n'est PAS rapatrié
# dans le Lab, sans quoi l'explorateur et data.json (publiés) le republieraient
GROUPES['lab_entrees'] = ['h19_signal_log.jsonl']
# 28/10/2026 : rapport ROI (règles R1/R2) — interne, jamais dans le dépôt public ; écrit par pronostic.yml
GROUPES['roi'] = ['simulateur/rapport_roi_algo.json', 'simulateur/rapport_desaccords.json']
GROUPES['tous'] = [f for k in ('signaux', 'lab', 'pronostics') for f in GROUPES[k]]
# servis au Lab par le worker « algo » (nom de fichier seul, sans dossier)
SERVIS = sorted({os.path.basename(f) for f in GROUPES['tous']})


def cle(chemin):
    return PREFIXE + os.path.basename(chemin)


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _lire(chemin):
    try:
        with open(chemin, 'rb') as f:
            return f.read()
    except OSError:
        return None


def union_jsonl(distant, local):
    """Lignes du coffre, puis celles du local qu'il n'a pas (ordre gardé)."""
    vues = set(distant.splitlines())
    ajout = [l for l in local.splitlines() if l.strip() and l not in vues]
    base = distant if distant.endswith(b'\n') or not distant else distant + b'\n'
    return base + b''.join(l + b'\n' for l in ajout)


def pull(fichiers, r2):
    for f in fichiers:
        got = r2.get_with_etag(cle(f))
        if got is None:
            print(f"  coffre : {f} absent — copie locale gardée{' (absente aussi)' if _lire(f) is None else ''}")
            continue
        if _lire(f) != got[0]:
            os.makedirs(os.path.dirname(f) or '.', exist_ok=True)
            r2_io._write_atomic(f, got[0])
        print(f"  coffre → {f} ({len(got[0])} octets)")


def push(fichiers, r2):
    echecs = 0
    for f in fichiers:
        data = _lire(f)
        if data is None:
            continue
        for _ in range(4):
            got = r2.get_with_etag(cle(f))
            if got is not None and got[0] == data:
                break
            cible = data
            if got is not None and f.endswith('.jsonl'):
                cible = union_jsonl(got[0], data)
                if cible == got[0]:
                    break
            try:
                r2.put(cle(f), cible, create_only=got is None, if_match=got[1] if got else None,
                       content_type='application/json')
                if cible != data:
                    r2_io._write_atomic(f, cible)
                print(f"  {f} → coffre ({len(cible)} octets)")
                break
            except r2_io.PreconditionFailed:
                continue
        else:
            echecs += 1
            print(f"::warning::{f} : envoi au coffre impossible (conflits répétés) — reste local")
    return echecs


def retirer(fichiers, r2, si_present=False):
    """git rm --cached des fichiers suivis que le coffre détient à l'identique.
    28/10/2026 — si_present : retire aussi un fichier suivi dont le coffre détient une AUTRE version (le coffre
    est la source à jour ; la copie git est une ancienne version figée). Jamais si le coffre n'en a aucune."""
    suivis = set(subprocess.run(['git', 'ls-files', '--', *fichiers], capture_output=True, text=True).stdout.split())
    for f in sorted(suivis):
        data, got = _lire(f), r2.get_with_etag(cle(f))
        if si_present and got is not None and got[0]:
            subprocess.run(['git', 'rm', '--cached', '--quiet', '--', f], check=False)
            print(f"  {f} : retiré du dépôt (le coffre en a une version, {len(got[0])} octets)")
            continue
        if data is None or got is None or _sha(got[0]) != _sha(data):
            print(f"  {f} : gardé dans git (le coffre n'en a pas une copie identique)")
            continue
        subprocess.run(['git', 'rm', '--cached', '--quiet', '--', f], check=False)
        print(f"  {f} : retiré du dépôt (gardé au coffre)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['pull', 'push', 'retirer'])
    ap.add_argument('--groupe', default='tous', choices=sorted(GROUPES))
    ap.add_argument('--si-present', action='store_true',
                    help="retirer : aussi quand le coffre a une autre version (copie git figée et périmée)")
    a = ap.parse_args(argv)
    r2 = r2_io.client()
    if r2 is None:
        print('coffre : R2 indisponible — rien à faire (les fichiers restent tels quels).')
        return 0
    fichiers = GROUPES[a.groupe]
    if a.action == 'pull':
        pull(fichiers, r2)
        return 0
    if a.action == 'push':
        return 1 if push(fichiers, r2) else 0
    retirer(fichiers, r2, si_present=a.si_present)
    return 0


if __name__ == '__main__':
    sys.exit(main())
