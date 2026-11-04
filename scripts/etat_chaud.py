#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etat_chaud.py — les fichiers d'état réécrits à chaque capture passent par R2 ; git n'en garde qu'une photo toutes les
2 heures (04/11/2026, demande de Lucas : le dépôt atteint 6,5 Go et GitHub a refusé 4 fois de suite une publication).

POURQUOI
capture_closing tourne ~470 fois par jour et réécrit à chaque fois, EN ENTIER :
    closing_lines.json (1,4 Mo), matches_oddspapi.json, live_odds.json, odds_alerts_state.json, odds_logged_state.json
soit des centaines de Mo de nouvelles versions par jour dans l'historique git (rapport taille_depot).

TROIS MODES — variable de dépôt ETAT_CHAUD (env du même nom) :
  off     : rien ne change (git fait tout, comme avant).
  double  : (défaut) git fait foi et reçoit tout comme avant ; R2 reçoit EN PLUS une copie à chaque passage
            (préfixe « chaud/ » du coffre R2). Sert à vérifier le relais sans aucun risque.
  on      : R2 fait foi entre deux photos. Les écrivains (capture_closing, fetch_clv) RAPATRIENT l'état de R2 au
            début (pull) et le RENVOIENT à la fin (push). Seule la capture laisse git publier une photo de ces
            fichiers, toutes les CHAUD_INTERVALLE_MIN minutes (120 par défaut) (garde) ; fetch_clv et les lecteurs
            qui ont besoin de frais (alertes, canal public, pronostics) font pull au début et ne republient jamais
            ces fichiers (garde --lecteur).
SANS SECRETS R2 : pull / push ne font rien, garde ne retient rien (comportement d'avant) : rien ne casse.

CONCURRENCE : push est conditionnel (If-Match sur l'ETag lu au pull). Si un autre passage a écrit entre-temps, la
version de R2 est relue et FUSIONNÉE (merge_json_state.fusion : union par clé ou par identifiant, la nôtre gagne
en cas d'égalité — closing_lines est un accumulateur), puis réécrite.
FRAÎCHEUR : chaud/etat.json garde l'empreinte git des dernières versions envoyées. Au pull, une copie git qui porte
l'une d'elles est « connue » (R2 a plus récent) ; sinon elle vient d'un écrivain hors relais (réparation manuelle) :
accumulateur → union (la copie git gagne en cas d'égalité), photo → copie git gardée. Rien ne se perd.

Usage : python scripts/etat_chaud.py pull | push | garde [--lecteur] [fichier …]   (sans fichier : les cinq)
"""
import hashlib
import json
import os
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

FICHIERS = ('closing_lines.json', 'matches_oddspapi.json', 'live_odds.json', 'odds_alerts_state.json',
            'odds_logged_state.json')
# accumulateurs : en cas de conflit on FUSIONNE (union par clé) ; les autres sont des photos : la plus récente gagne
ACCUMULATEURS = ('closing_lines.json', 'odds_alerts_state.json', 'odds_logged_state.json')
PREFIXE = 'chaud/'
CLE_ETAT = PREFIXE + 'etat.json'
CONNUS_MAX = 600
INTERVALLE_MIN = float(os.environ.get('CHAUD_INTERVALLE_MIN', '120'))
ETAGS = os.path.join(os.environ.get('RUNNER_TEMP') or '/tmp', 'etat_chaud_etags.json')


def mode(environ=None):
    m = str((environ if environ is not None else os.environ).get('ETAT_CHAUD', 'double')).strip().lower()
    return m if m in ('off', 'double', 'on') else 'double'


def empreinte(data):
    """Empreinte git (blob) d'un contenu : identique à `git hash-object`, sans appeler git (marche en clone superficiel)."""
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def commit_git(chemin):
    """Instant (epoch) du dernier commit git qui touche ce fichier, 0 s'il n'y en a pas."""
    r = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', chemin], capture_output=True, text=True)
    try:
        return int(r.stdout.strip() or 0)
    except ValueError:
        return 0


def _lire_json(data):
    try:
        return json.loads(data.decode('utf-8') if isinstance(data, bytes) else data)
    except (ValueError, UnicodeDecodeError):
        return None


def _octets(chemin):
    try:
        with open(chemin, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _etat(r2):
    got = r2.get_with_etag(CLE_ETAT)
    return (_lire_json(got[0]) or {}, got[1]) if got else ({}, None)


def pull(r2, fichiers=FICHIERS, racine='.'):
    """Met la copie locale à l'état de R2.
    Copie git CONNUE (déjà passée par R2) : R2 est plus récent → on prend R2.
    Copie git INCONNUE (écrite hors relais, ex. une réparation manuelle) : accumulateur → union, la copie git gagne
    en cas d'égalité ; photo → on garde la copie git. Renvoie {fichier: 'r2' | 'fusion' | 'git'}."""
    import merge_json_state as MJ
    etat, _ = _etat(r2)
    etags, pris = {}, {}
    for f in fichiers:
        got = r2.get_with_etag(PREFIXE + f)
        if not got:
            continue
        etags[f] = got[1]
        distant = _lire_json(got[0])
        if distant is None:
            continue
        chemin = os.path.join(racine, f)
        local = _octets(chemin)
        connus = set((etat.get(f) or {}).get('connus') or [])
        if local is None or empreinte(local) in connus:
            data, quoi = got[0], 'r2'
        elif f in ACCUMULATEURS and _lire_json(local) is not None:
            fus = MJ.fusion(_lire_json(local), distant)
            data, quoi = (_dump(fus), 'fusion') if fus is not None else (local, 'git')
        else:
            data, quoi = local, 'git'
        if data != local:
            with open(chemin, 'wb') as fh:
                fh.write(data)
        pris[f] = quoi
    try:
        with open(ETAGS, 'w', encoding='utf-8') as fh:
            json.dump(etags, fh)
    except OSError:
        pass
    return pris


def push(r2, fichiers=FICHIERS, racine='.', essais=4, ecraser=False):
    """Envoie chaque fichier à R2. Conditionnel (If-Match sur l'ETag du pull) ; si un autre passage a écrit entre-temps :
    accumulateur → fusion avec la version de R2 (la nôtre gagne en cas d'égalité), photo → la nôtre (plus récente).
    ecraser=True (mode double : git fait foi) : écriture directe, sans condition. Renvoie la liste envoyée."""
    import r2_io
    import merge_json_state as MJ
    etags = _lire_json(_octets(ETAGS) or b'') or {}
    envoyes = {}
    for f in fichiers:
        chemin = os.path.join(racine, f)
        if not os.path.exists(chemin):
            continue
        data = _octets(chemin)
        if _lire_json(data) is None:
            print(f'⚠️ {f} : JSON illisible, pas envoyé')
            continue
        etag = etags.get(f)
        for _ in range(essais):
            try:
                if ecraser:
                    r2.put(PREFIXE + f, data, content_type='application/json')
                elif etag:
                    r2.put(PREFIXE + f, data, if_match=etag, content_type='application/json')
                else:
                    r2.put(PREFIXE + f, data, create_only=True, content_type='application/json')
                envoyes[f] = empreinte(data)
                break
            except r2_io.PreconditionFailed:
                got = r2.get_with_etag(PREFIXE + f)
                if not got:
                    etag = None
                    continue
                etag = got[1]
                autre = _lire_json(got[0])
                if f in ACCUMULATEURS and autre is not None:
                    fus = MJ.fusion(_lire_json(data), autre)
                    if fus is not None:
                        data = _dump(fus)
                        with open(chemin, 'wb') as fh:      # la copie locale (et la photo git) = la version fusionnée
                            fh.write(data)
    # empreintes envoyées : au prochain pull, une copie git qui porte l'une d'elles est « connue » (déjà dans R2)
    for _ in range(essais):
        etat, e_etag = _etat(r2)
        maintenant = time.time()
        for f, h in envoyes.items():
            e = etat.setdefault(f, {})
            e['t'] = maintenant
            e['connus'] = ([x for x in (e.get('connus') or []) if x != h] + [h])[-CONNUS_MAX:]
        try:
            if e_etag:
                r2.put(CLE_ETAT, _dump(etat), if_match=e_etag, content_type='application/json')
            else:
                r2.put(CLE_ETAT, _dump(etat), create_only=True, content_type='application/json')
            break
        except r2_io.PreconditionFailed:
            continue
    return sorted(envoyes)


def garde(fichiers=FICHIERS, racine='.', lecteur=False, maintenant=None, intervalle_min=INTERVALLE_MIN):
    """Retire du commit (et du disque : la copie git revient) les fichiers chauds qui ne sont pas « dus ».
    Écrivain : un fichier est dû si son dernier commit git date de plus d'intervalle_min. Lecteur : jamais dû."""
    maintenant = maintenant or time.time()
    retenus = []
    for f in fichiers:
        chemin = os.path.join(racine, f)
        du = (not lecteur) and (maintenant - commit_git(chemin)) >= 60 * intervalle_min
        if du:
            continue
        r = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', chemin])
        if r.returncode != 0:
            subprocess.run(['git', 'restore', '--staged', '--worktree', '--source=HEAD', '--', chemin],
                           capture_output=True)
            retenus.append(f)
    return retenus


def main(argv):
    action = argv[1] if len(argv) > 1 else ''
    noms = tuple(a for a in argv[2:] if not a.startswith('--')) or FICHIERS
    inconnus = [n for n in noms if n not in FICHIERS]
    if inconnus:
        print(f'État chaud : fichiers inconnus {inconnus}')
        return 2
    m = mode()
    if m == 'off':
        print(f'État chaud : mode off ({action} ignoré)')
        return 0
    import r2_io
    r2 = r2_io.client(quiet=True)
    if action == 'pull':
        if m != 'on' or r2 is None:
            print(f"État chaud : pull ignoré (mode {m}{'' if r2 else ', R2 absent'})")
            return 0
        print(f'État chaud : copies locales → {pull(r2, noms) or "R2 vide (copies git gardées)"}')
    elif action == 'push':
        if r2 is None:
            print('État chaud : R2 absent, push ignoré')
            return 0
        print(f"État chaud : envoyés à R2 → {push(r2, noms, ecraser=(m == 'double'))}")
    elif action == 'garde':
        if m != 'on' or r2 is None:
            print(f'État chaud : garde inactive (mode {m}) — git publie comme avant')
            return 0
        lecteur = '--lecteur' in argv
        print(f"État chaud : retenus hors du commit → {garde(noms, lecteur=lecteur) or 'aucun'}"
              f"{' (lecteur)' if lecteur else f' (photo git toutes les {int(INTERVALLE_MIN)} min)'}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
