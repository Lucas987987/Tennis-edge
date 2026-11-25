#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publier_r2.py — LE SITE SERVI PAR CLOUDFLARE, PLUS PAR GITHUB PAGES (22/11/2026, paquet 334, demande de Lucas :
« basculer un maximum de choses en privé »).

Constat : le dépôt est public et GitHub Pages publiait tout _site à tout le monde : le site de l'algo (public, c'est
voulu), mais aussi le Lab (CLV, journaux de suivi, recherches), l'ancien tableau de bord et ses fichiers de cotes.

Ce que fait ce script, à chaque publication (pages.yml), sans rien afficher du contenu :
  envoyer     : range _site dans le bucket R2 privé (celui du coffre) :
                  algo/** et arena/**  -> site/…        (public : servi par le worker « algo »)
                  tout le reste         -> prive/site/…  (Lab, tableau : servi par le worker SEULEMENT avec la clé)
                Seuls les fichiers modifiés partent (manifeste MD5 par préfixe : site/manifeste.json,
                prive/site/manifeste.json). Sortie : nombre de fichiers et d'octets, jamais leur contenu.
  telecharger : rapatrie un dossier publié (ex. la version précédente des données du Lab, que publish_guard.py
                compare à la nouvelle) dans un dossier local.
GitHub Pages ne garde ensuite que algo/ (secours du worker) et arena/ (jeu public) : voir pages.yml.

Usage : python scripts/publier_r2.py envoyer --site _site
        python scripts/publier_r2.py telecharger --prefixe prive/site/Tennis_Edge_Lab/live/ --vers /tmp/lab
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PUBLICS = ('algo/', 'arena/')
PREFIXE_PUBLIC = 'site/'
PREFIXE_PRIVE = 'prive/site/'
MANIFESTE = 'manifeste.json'
TYPES = {
    'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'mjs': 'text/javascript; charset=utf-8',
    'css': 'text/css; charset=utf-8', 'json': 'application/json; charset=utf-8', 'csv': 'text/csv; charset=utf-8',
    'txt': 'text/plain; charset=utf-8', 'md': 'text/plain; charset=utf-8', 'svg': 'image/svg+xml', 'png': 'image/png',
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp', 'ico': 'image/x-icon', 'gz': 'application/gzip',
    'woff2': 'font/woff2', 'glb': 'model/gltf-binary', 'bin': 'application/octet-stream', 'mp3': 'audio/mpeg',
    'ogg': 'audio/ogg', 'wav': 'audio/wav', 'webmanifest': 'application/manifest+json',
}


def type_de(chemin):
    return TYPES.get(chemin.rsplit('.', 1)[-1].lower() if '.' in chemin else '', 'application/octet-stream')


def cle_de(rel):
    """Chemin relatif de _site -> clé R2 (public ou privé)."""
    rel = rel.replace(os.sep, '/').lstrip('/')
    return (PREFIXE_PUBLIC if rel.startswith(PUBLICS) else PREFIXE_PRIVE) + rel


def fichiers(site):
    out = []
    for d, _, noms in os.walk(site):
        for n in noms:
            p = os.path.join(d, n)
            rel = os.path.relpath(p, site).replace(os.sep, '/')
            if rel == '.nojekyll' or rel.startswith('.git/'):
                continue
            out.append(rel)
    return sorted(out, key=ordre_envoi)


def ordre_envoi(rel):
    """24/11/2026 (paquet 424) : les PAGES partent en dernier, les pages d'accueil (index.html) tout à la fin. Avant, l'ordre
    alphabétique envoyait algo/index.html AVANT algo/style-<empreinte>.css : pendant l'envoi, la nouvelle page pointait
    vers une feuille de style pas encore dans R2 → page sans mise en forme (vu le 24/11 à 22 h, après le paquet 423). Une
    page ne part donc qu'une fois tout ce qu'elle charge (styles, scripts, données, polices, images) déjà en place."""
    nom = rel.rsplit('/', 1)[-1]
    return (nom == 'index.html', rel.endswith('.html'), rel)


def _manifeste(r2, prefixe):
    try:
        b = r2.get(prefixe + MANIFESTE)
        return json.loads(b) if b else {}
    except Exception:  # noqa: BLE001 — manifeste illisible : tout repart
        return {}


TACHES = 16           # 424 : envois en parallèle (un par un : ~10 000 fichiers ne passaient plus avant l'annulation)
POINT = 400           # 424 : manifeste réécrit tous les 400 envois : un run annulé ne fait pas tout repartir


def envoyer(r2, site, journal=print, taches=TACHES, point=POINT, urls_indexnow=None):
    """24/11/2026 (paquet 424, Lucas : « déploy page ko, le site n'est toujours pas revenu »). Avec les ~5 000 pages de
    référencement (×2 langues), l'envoi un par un durait plus de 20 minutes ; la publication suivante l'annulait
    (pages.yml, cancel-in-progress) AVANT l'écriture du manifeste, si bien que tout repartait à chaque fois et que la
    nouvelle page d'accueil restait en ligne sans sa feuille de style. Désormais : envois en parallèle, par vagues
    (fichiers chargés par les pages → pages → pages d'accueil, chaque vague finie avant la suivante), et manifeste
    réécrit en cours de route avec ce qui est déjà parti."""
    from concurrent.futures import ThreadPoolExecutor
    rels = fichiers(site)
    anciens = {p: _manifeste(r2, p) for p in (PREFIXE_PUBLIC, PREFIXE_PRIVE)}
    nouveaux = {p: {} for p in anciens}
    faits = {p: dict(m) for p, m in anciens.items()}        # ce qui est réellement dans R2, mis à jour en cours de route
    n = {'public': [0, 0], 'prive': [0, 0], 'inchanges': 0}
    vagues = {}
    for rel in rels:
        cle = cle_de(rel)
        pre = PREFIXE_PUBLIC if cle.startswith(PREFIXE_PUBLIC) else PREFIXE_PRIVE
        with open(os.path.join(site, rel), 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        nom = cle[len(pre):]
        nouveaux[pre][nom] = md5
        if anciens[pre].get(nom) == md5:
            n['inchanges'] += 1
            continue
        vagues.setdefault(ordre_envoi(rel)[:2], []).append((rel, cle, pre, nom, md5))

    def ecrire_manifeste(m_par_pre):
        for pre, m in m_par_pre.items():
            r2.put(pre + MANIFESTE, json.dumps(m, sort_keys=True, separators=(',', ':')).encode(),
                   content_type='application/json')

    def un(t):
        rel, cle, pre, nom, md5 = t
        with open(os.path.join(site, rel), 'rb') as f:
            data = f.read()
        r2.put(cle, data, content_type=type_de(rel))
        return t, len(data)

    depuis_point = 0
    with ThreadPoolExecutor(max_workers=max(1, taches)) as ex:
        for v in sorted(vagues):                             # chaque vague est finie avant la suivante
            for (rel, cle, pre, nom, md5), taille in ex.map(un, vagues[v]):
                faits[pre][nom] = md5
                k = 'public' if pre == PREFIXE_PUBLIC else 'prive'
                n[k][0] += 1
                n[k][1] += taille
                depuis_point += 1
                if depuis_point >= point:
                    ecrire_manifeste(faits)
                    depuis_point = 0
    ecrire_manifeste({p: m for p, m in nouveaux.items() if m != anciens[p] or faits[p] != anciens[p]})
    if urls_indexnow:                                        # 444 : pages publiques envoyées → IndexNow (scripts/indexnow.py)
        import indexnow
        envoyees = [t[0] for v in vagues.values() for t in v if t[2] == PREFIXE_PUBLIC]
        with open(urls_indexnow, 'w', encoding='utf-8') as f:
            f.write(''.join(u + '\n' for u in sorted({indexnow.url_de(r) for r in envoyees} - {None})))
    journal(f"R2 : {len(rels)} fichiers · public envoyés {n['public'][0]} ({n['public'][1] // 1024} Ko) · "
            f"privés envoyés {n['prive'][0]} ({n['prive'][1] // 1024} Ko) · inchangés {n['inchanges']}")
    return n


def telecharger(r2, prefixe, vers, journal=print):
    """Fichiers DIRECTEMENT sous le préfixe (pas les sous-dossiers) -> dossier local."""
    os.makedirs(vers, exist_ok=True)
    k = 0
    for cle, _taille in r2.list(prefixe):
        nom = cle[len(prefixe):]
        if not nom or '/' in nom:
            continue
        data = r2.get(cle)
        if data is None:
            continue
        with open(os.path.join(vers, nom), 'wb') as f:
            f.write(data)
        k += 1
    journal(f"R2 : {k} fichier(s) rapatrié(s) de {prefixe}")
    return k


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['envoyer', 'telecharger'])
    ap.add_argument('--site', default='_site')
    ap.add_argument('--prefixe', default='')
    ap.add_argument('--vers', default='')
    ap.add_argument('--urls-indexnow', default='')
    a = ap.parse_args(argv)
    import r2_io
    r2 = r2_io.client()
    if r2 is None:
        print('::warning::R2 indisponible : rien envoyé (GitHub Pages garde tout le site, comme avant).')
        return 2
    if a.action == 'envoyer':
        envoyer(r2, a.site, urls_indexnow=a.urls_indexnow or None)
        return 0
    if not a.prefixe.startswith(PREFIXE_PRIVE) and not a.prefixe.startswith(PREFIXE_PUBLIC):
        print('::error::préfixe hors du site')
        return 1
    telecharger(r2, a.prefixe, a.vers)
    return 0


if __name__ == '__main__':
    sys.exit(main())
