#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sauvegarde_depot.py — copie du dépôt dans R2, chaque semaine (29/10/2026).

Pourquoi : le code, les pronostics figés, les bilans après match, les cotes de clôture, l'historique CLV, les feuilles
de match (payées en quota TennisApi) et les résultats ITF n'existaient qu'en UN exemplaire, sur GitHub. Les ticks et
les courbes live (parts/) sont déjà dans R2 : ils sont exclus de l'archive.

Contenu : un .tar.gz de l'arbre du dépôt (sans .git ni parts/), ~100 Mo. Aucun secret : le dépôt n'en contient pas
(les clés sont dans les secrets GitHub, jamais copiées ici).

Emplacements FIXES, réécrits à tour de rôle (le code R2 ne supprime jamais rien, la place reste bornée) :
  sauvegardes/depot/hebdo-0 … hebdo-3.tar.gz   la semaine ISO modulo 4 → les 4 dernières semaines ;
  sauvegardes/depot/mensuel-0 … mensuel-2.tar.gz  la 1re sauvegarde de chaque mois, mois modulo 3 → 3 derniers mois.
  sauvegardes/depot/index.json                  date, commit, taille, empreinte SHA-256 de chaque emplacement.
Au plus 7 archives (~0,7 Go) dans les 10 Go gratuits de R2. Chaque envoi est relu et son empreinte comparée.

Restaurer : tableau de bord Cloudflare → R2 → compartiment → sauvegardes/depot/ → télécharger l'archive voulue
(index.json dit laquelle est la plus récente) ; ou ce workflow, action « telecharger » (artefact GitHub).

Usage : python scripts/sauvegarde_depot.py sauvegarder [racine]
        python scripts/sauvegarde_depot.py lister
        python scripts/sauvegarde_depot.py telecharger <emplacement> <fichier>
"""
import datetime as dt
import hashlib
import io
import json
import os
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PREFIXE = 'sauvegardes/depot/'
EXCLUS_RACINE = {'.git', 'parts'}
EXCLUS_PARTOUT = {'__pycache__', '.pytest_cache'}
N_HEBDO, N_MENSUEL = 4, 3


def emplacements(jour, index):
    """Emplacements à écrire ce jour : toujours l'hebdomadaire ; le mensuel si le mois n'a pas encore le sien."""
    out = [f"hebdo-{jour.isocalendar()[1] % N_HEBDO}"]
    m = f"mensuel-{jour.month % N_MENSUEL}"
    deja = (index.get(m) or {}).get('date', '')
    if deja[:7] != jour.isoformat()[:7]:
        out.append(m)
    return out


def _garder(chemin_rel):
    parts = chemin_rel.split('/')
    return parts[0] not in EXCLUS_RACINE and not any(p in EXCLUS_PARTOUT for p in parts)


def archiver(racine):
    """(octets du .tar.gz, nombre de fichiers) de l'arbre, sans .git, parts/ ni caches ; ordre et dates fixes."""
    fichiers = []
    for d, sous, noms in os.walk(racine):
        rel_d = os.path.relpath(d, racine).replace(os.sep, '/')
        rel_d = '' if rel_d == '.' else rel_d + '/'
        sous[:] = sorted(s for s in sous if _garder(rel_d + s))
        for n in sorted(noms):
            rel = rel_d + n
            if _garder(rel) and os.path.isfile(os.path.join(d, n)) and not os.path.islink(os.path.join(d, n)):
                fichiers.append(rel)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6) as tar:
        for rel in fichiers:
            info = tar.gettarinfo(os.path.join(racine, rel), arcname=rel)
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, '', ''
            with open(os.path.join(racine, rel), 'rb') as f:
                tar.addfile(info, f)
    return buf.getvalue(), len(fichiers)


def lire_index(r2):
    data = r2.get(PREFIXE + 'index.json')
    try:
        return json.loads(data) if data else {}
    except ValueError:
        return {}


def _client():
    import r2_io
    r2 = r2_io.client()
    if r2 is not None and hasattr(r2.client, 'timeout'):      # MiniS3 : ~100 Mo en un envoi
        r2.client.timeout = 600
    return r2


def sauvegarder(racine='.', r2=None, jour=None, commit=None):
    r2 = r2 or _client()
    if r2 is None:
        print('::error::R2 indisponible (secrets absents) : pas de sauvegarde.')
        return 1
    jour = jour or dt.datetime.now(dt.timezone.utc).date()
    commit = commit or os.environ.get('GITHUB_SHA', '')
    data, n = archiver(racine)
    sha = hashlib.sha256(data).hexdigest()
    index = lire_index(r2)
    for e in emplacements(jour, index):
        cle = f"{PREFIXE}{e}.tar.gz"
        r2.put(cle, data, content_type='application/gzip', metadata={'date': jour.isoformat(), 'commit': commit[:12]})
        relu = r2.get(cle) or b''
        if hashlib.sha256(relu).hexdigest() != sha:
            print(f"::error::{cle} : la copie relue ne correspond pas (empreinte différente).")
            return 1
        index[e] = {'date': jour.isoformat(), 'commit': commit, 'octets': len(data), 'fichiers': n, 'sha256': sha}
        print(f"✅ {cle} : {len(data) / 1e6:.1f} Mo, {n} fichiers, relu et vérifié (commit {commit[:12] or '—'})")
    r2.put(PREFIXE + 'index.json', json.dumps(index, indent=1, sort_keys=True).encode('utf-8'),
           content_type='application/json')
    lister(r2, index)
    return 0


def lister(r2=None, index=None):
    r2 = r2 or _client()
    if r2 is None:
        print('R2 indisponible.')
        return 1
    index = index if index is not None else lire_index(r2)
    if not index:
        print('Aucune sauvegarde.')
        return 0
    print('Sauvegardes (la plus récente en premier) :')
    for e, v in sorted(index.items(), key=lambda kv: kv[1].get('date', ''), reverse=True):
        print(f"  {e:<10} {v.get('date')} · {v.get('octets', 0) / 1e6:6.1f} Mo · {v.get('fichiers')} fichiers · "
              f"commit {str(v.get('commit'))[:12]}")
    return 0


def telecharger(emplacement, sortie, r2=None):
    r2 = r2 or _client()
    data = r2.get(f"{PREFIXE}{emplacement}.tar.gz") if r2 else None
    if not data:
        print(f"::error::Emplacement {emplacement} introuvable.")
        return 1
    attendu = (lire_index(r2).get(emplacement) or {}).get('sha256')
    if attendu and hashlib.sha256(data).hexdigest() != attendu:
        print('::error::Archive téléchargée : empreinte différente de l index.')
        return 1
    with open(sortie, 'wb') as f:
        f.write(data)
    print(f"✅ {emplacement} → {sortie} ({len(data) / 1e6:.1f} Mo, empreinte vérifiée)")
    return 0


def main(argv):
    action = argv[1] if len(argv) > 1 else 'sauvegarder'
    if action == 'sauvegarder':
        return sauvegarder(argv[2] if len(argv) > 2 else '.')
    if action == 'lister':
        return lister()
    if action == 'telecharger' and len(argv) > 3:
        return telecharger(argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
