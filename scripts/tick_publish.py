#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tick_publish.py — publication des ticks par run, sans conflit (correction B+D).

PROTOTYPE, NON BRANCHÉ : aucun workflow ni collecteur ne l'appelle encore.

PRINCIPE
  * Les collecteurs ajoutent leurs ticks à la fin de parts/<p>_ticks_<jour>.jsonl.gz
    (membres gzip concaténés). Les octets ajoutés pendant UN run forment donc
    eux-mêmes un gzip valide : extract_run_ticks() les isole sans toucher au
    collecteur. Le fichier du jour est ensuite remis dans l'état du checkout.
  * Chaque run publie son segment sous un nom UNIQUE (run_id + tentative) :
    deux runs ne modifient jamais le même fichier, donc aucun conflit Git.
  * Le push se fait sur une branche dédiée (inbox), avec rebase + nouvelles
    tentatives ; un échec définitif écrit le segment dans un dossier destiné à
    un artifact (D), republiable sans doublon par recover().
  * consolidate() reconstitue le fichier du jour de façon déterministe
    (ordre run_id/tentative, dédup par tick_id V6.4, gzip mtime=0).
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from partitioned_store import stable_tick_record  # noqa: E402

PROVIDERS = {'kalshi': 'kx', 'polymarket': 'pm'}
NOM_RE = re.compile(r'^(?P<p>kalshi|polymarket)_(?P<d>\d{4}-\d{2}-\d{2})_'
                    r'(?P<run>\d+)-(?P<att>\d+)\.jsonl\.gz$')


class PublishError(RuntimeError):
    pass


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def segment_name(provider, day, run_id, attempt):
    if provider not in PROVIDERS:
        raise ValueError(f'fournisseur inconnu : {provider}')
    return f'{provider}_{day}_{int(run_id)}-{int(attempt)}.jsonl.gz'


def segment_dir(provider, day):
    return os.path.join('inbox', provider, day)


def _lignes(data):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        return [ln for ln in f.read().split(b'\n') if ln.strip()]


def extract_run_ticks(day_file, base_size):
    """Octets ajoutés après base_size (taille du fichier au checkout).
    Si le fichier a été remplacé/tourné (plus petit), tout le fichier est pris."""
    with open(day_file, 'rb') as f:
        data = f.read()
    seg = data[base_size:] if base_size <= len(data) else data
    if seg:
        _lignes(seg)  # lève si le segment n'est pas un gzip complet
    return seg


def build_manifest(provider, day, run_id, attempt, data):
    lignes = _lignes(data) if data else []
    tss = []
    for ln in lignes:
        try:
            ts = json.loads(ln).get('ts')
        except ValueError:
            continue
        if isinstance(ts, str):
            tss.append(ts)
    return {'schema': 1, 'provider': provider, 'day': day,
            'run_id': int(run_id), 'attempt': int(attempt),
            'name': segment_name(provider, day, run_id, attempt),
            'bytes': len(data), 'sha256': sha256_hex(data),
            'lines': len(lignes),
            'ts_min': min(tss) if tss else None,
            'ts_max': max(tss) if tss else None}


def _git(repo, *args, check=True):
    r = subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise PublishError(f"git {' '.join(args)} : {(r.stderr or r.stdout).strip()[:300]}")
    return r


def publish_segment(repo, branch, provider, day, run_id, attempt, data,
                    retries=10, base_wait=1.0, max_wait=20.0, jitter=0.5,
                    sleep=time.sleep, remote='origin'):
    """Publie un segment sur `branch`. Idempotent : un segment déjà présent avec
    le même SHA-256 n'est pas republié ; un nom identique avec un contenu
    différent est refusé (jamais d'écrasement). Retourne 'published' | 'exists'."""
    manifest = build_manifest(provider, day, run_id, attempt, data)
    rel = os.path.join(segment_dir(provider, day), manifest['name'])
    man_rel = rel[:-len('.jsonl.gz')] + '.manifest.json'
    attente = base_wait
    for essai in range(1, retries + 1):
        try:
            _git(repo, 'fetch', '-q', remote, branch)
            _git(repo, 'checkout', '-q', '-B', branch, f'{remote}/{branch}')
            dest = os.path.join(repo, rel)
            if os.path.exists(dest):
                with open(dest, 'rb') as f:
                    if sha256_hex(f.read()) == manifest['sha256']:
                        return 'exists'
                raise PublishError(f'{rel} existe avec un contenu différent')
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, 'wb') as f:
                f.write(data)
            with open(os.path.join(repo, man_rel), 'w', encoding='utf-8') as f:
                json.dump(manifest, f, sort_keys=True)
            _git(repo, 'add', '--', rel, man_rel)
            _git(repo, '-c', 'user.name=github-actions[bot]',
                 '-c', 'user.email=github-actions[bot]@users.noreply.github.com',
                 'commit', '-q', '-m',
                 f"ticks {provider} {day} run {run_id}-{attempt} ({manifest['lines']} lignes)")
            _git(repo, 'push', '-q', remote, f'HEAD:{branch}')
            return 'published'
        except PublishError as e:
            if 'contenu différent' in str(e) or essai == retries:
                raise
            sleep(attente * (1 + jitter * random.random()))
            attente = min(attente * 2, max_wait)
    raise PublishError('retries épuisés')


def publish_or_artifact(repo, branch, provider, day, run_id, attempt, data,
                        artifact_dir, **kw):
    """D : si la publication échoue, le segment + manifeste sont écrits dans
    artifact_dir (à téléverser par upload-artifact, if: always()). Retourne
    'published' | 'exists' | 'artifact'."""
    try:
        return publish_segment(repo, branch, provider, day, run_id, attempt,
                               data, **kw)
    except PublishError as e:
        os.makedirs(artifact_dir, exist_ok=True)
        name = segment_name(provider, day, run_id, attempt)
        with open(os.path.join(artifact_dir, name), 'wb') as f:
            f.write(data)
        with open(os.path.join(artifact_dir, name[:-len('.jsonl.gz')] + '.manifest.json'),
                  'w', encoding='utf-8') as f:
            json.dump({**build_manifest(provider, day, run_id, attempt, data),
                       'error': str(e)[:300]}, f, sort_keys=True)
        return 'artifact'


def recover(artifact_dir, repo, branch, **kw):
    """Republie les segments d'un artifact téléchargé. Vérifie le SHA-256 du
    manifeste avant publication ; idempotent (relancer ne crée aucun doublon)."""
    bilan = {'published': 0, 'exists': 0, 'rejected': 0}
    for nom in sorted(os.listdir(artifact_dir)):
        m = NOM_RE.match(nom)
        if not m:
            continue
        with open(os.path.join(artifact_dir, nom), 'rb') as f:
            data = f.read()
        man_path = os.path.join(artifact_dir, nom[:-len('.jsonl.gz')] + '.manifest.json')
        try:
            man = json.load(open(man_path, encoding='utf-8'))
            if man['sha256'] != sha256_hex(data):
                raise ValueError('sha256')
            _lignes(data)
        except (OSError, ValueError, KeyError, EOFError, gzip.BadGzipFile):
            bilan['rejected'] += 1
            continue
        bilan[publish_segment(repo, branch, m['p'], m['d'], m['run'], m['att'],
                              data, **kw)] += 1
    return bilan


def list_segments(inbox_root, provider, day):
    d = os.path.join(inbox_root, provider, day)
    if not os.path.isdir(d):
        return []
    sel = []
    for nom in os.listdir(d):
        m = NOM_RE.match(nom)
        if m and m['p'] == provider and m['d'] == day:
            sel.append((int(m['run']), int(m['att']), os.path.join(d, nom)))
    return [p for _, _, p in sorted(sel)]


def consolidate(inbox_root, provider, day, base_file=None):
    """Fichier du jour reconstitué : (base_file éventuel) puis segments triés
    par (run_id, tentative). Dédup par tick_id V6.4 ; lignes illisibles
    conservées (dédup sur la ligne brute). Sortie déterministe (gzip mtime=0).
    Retourne (octets_gz, rapport)."""
    vus, sortie, n_in = set(), [], 0
    sources = ([base_file] if base_file else []) + list_segments(inbox_root, provider, day)
    for chemin in sources:
        with open(chemin, 'rb') as f:
            for ln in _lignes(f.read()):
                n_in += 1
                try:
                    cle, _ = stable_tick_record(provider, json.loads(ln))
                except (ValueError, TypeError):
                    cle = 'raw:' + sha256_hex(ln)
                if cle in vus:
                    continue
                vus.add(cle)
                sortie.append(ln)
    data = gzip.compress(b'\n'.join(sortie) + (b'\n' if sortie else b''), mtime=0)
    return data, {'sources': len(sources), 'lines_in': n_in,
                  'lines_out': len(sortie), 'duplicates_removed': n_in - len(sortie),
                  'sha256': sha256_hex(data)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('consolidate')
    c.add_argument('--inbox', required=True)
    c.add_argument('--provider', required=True)
    c.add_argument('--day', required=True)
    c.add_argument('--out', required=True)
    c.add_argument('--base-file')
    r = sub.add_parser('recover')
    r.add_argument('--artifact-dir', required=True)
    r.add_argument('--repo', required=True)
    r.add_argument('--branch', required=True)
    a = ap.parse_args()
    if a.cmd == 'consolidate':
        data, rep = consolidate(a.inbox, a.provider, a.day, a.base_file)
        tmp = a.out + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(data)
        shutil.move(tmp, a.out)
        print(json.dumps(rep, sort_keys=True))
    else:
        print(json.dumps(recover(a.artifact_dir, a.repo, a.branch), sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
