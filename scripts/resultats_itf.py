#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resultats_itf.py — RÉSULTATS des matchs ITF hommes (vainqueur et score, SANS feuille de statistiques) — 28/10/2026.

Pourquoi : la sonde du 28/10 (scripts/sonde_peu_documentes.py) montre que les joueurs Challenger peu documentés
jouent surtout en ITF (2 192 matchs depuis juin 2024 pour 58 joueurs, contre 867 en Challenger) ; ces matchs n'ont
presque jamais de statistiques (6 %), mais ils ont un vainqueur et un score. Ils peuvent nourrir le NIVEAU (Elo) de
ces joueurs. ITF utilisé comme DONNÉE seulement : jamais pronostiqué, jamais parié (décision de Lucas, 28/10/2026).

Rien n'entre en production ici : stockage à part (resultats_itf/), lu seulement par simulateur/etude_itf_elo.py,
qui juge l'apport selon une règle fixée avant résultat.

Par jour (UTC) : l'index du jour (1 requête), puis les matchs de la catégorie « ITF Men » (1 requête) — on garde les
matchs en simple, terminés, qui COMMENCENT ce jour-là. ~2 requêtes par jour : ~1 800 pour juin 2024 → aujourd'hui.
Stockage : resultats_itf/AAAA-MM.jsonl.gz (un fichier par mois, une ligne par match), resultats_itf/etat.json
(jours faits). Un jour passé depuis plus de 3 jours n'est plus redemandé : relancer reprend où on s'est arrêté.
Garde-fous de feuilles_match.py : budget par passage, arrêt sous la réserve de quota, 5 requêtes/s, clé jamais affichée.

Usage : python scripts/resultats_itf.py [debut AAAA-MM-JJ] [fin AAAA-MM-JJ] [budget]
Env : RAPIDAPI_KEY ; FEUILLES_RESERVE (défaut ici : 6 000).
"""
import datetime as dt
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

DOSSIER = os.environ.get('ITF_DOSSIER', 'resultats_itf')
DEBUT = '2024-06-01'
CATEGORIE = 'itf men'
DELAI_COMPLET_J = 3
CHAMPS = ('id', 'jour', 'debut', 'tournoi', 'tournoi_id', 'surface', 'tour', 'meilleur_des', 'vainqueur',
          'statut', 'score_home', 'score_away')


def compacte(e, categorie):
    """Fiche réduite : identité, joueurs (id, nom, rang), score set par set, vainqueur, statut."""
    f = FM.fiche(e, categorie)
    out = {k: f[k] for k in CHAMPS}
    for cote in ('home', 'away'):
        j = f[cote]
        out[cote] = {k: j[k] for k in ('id', 'nom', 'rang') if j.get(k) is not None}
    return out


def chemin_mois(mois, dossier=DOSSIER):
    return os.path.join(dossier, f"{mois}.jsonl.gz")


def lire_mois(mois, dossier=DOSSIER):
    try:
        with gzip.open(chemin_mois(mois, dossier), 'rt', encoding='utf-8') as f:
            return {r['id']: r for r in (json.loads(l) for l in f if l.strip())}
    except (OSError, ValueError):
        return {}


def ecrire_mois(mois, recs, dossier=DOSSIER):
    os.makedirs(dossier, exist_ok=True)
    lignes = ''.join(json.dumps(recs[k], ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                     for k in sorted(recs))
    p = chemin_mois(mois, dossier)
    with open(p + '.tmp', 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as g:
            g.write(lignes.encode('utf-8'))
    os.replace(p + '.tmp', p)


def lire_etat(dossier=DOSSIER):
    try:
        with open(os.path.join(dossier, 'etat.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'jours': {}}


def collecter_jour(c, jour):
    """{id: fiche} des matchs ITF hommes en simple, terminés, commencés ce jour ; None si l'index ne répond pas."""
    d = dt.date.fromisoformat(jour)
    code, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
    if code == 204:
        return {}
    if code != 200:
        return None
    out = {}
    for cat in FM.categories_du_jour(idx, (CATEGORIE,)):
        code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
        if code not in (200, 204):
            return None
        for e in (doc or {}).get('events') or []:
            if not e.get('id') or not e.get('startTimestamp') or FM.jour_utc(e['startTimestamp']).isoformat() != jour:
                continue
            if not FM.est_simple(e) or (e.get('status') or {}).get('type') != 'finished':
                continue
            out[e['id']] = compacte(e, cat['nom'])
    return out


def lire_tout(racine):
    """Toutes les fiches stockées (pour l'étude)."""
    import glob
    out = []
    for p in sorted(glob.glob(os.path.join(racine, DOSSIER, '20*.jsonl.gz'))):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                out.extend(json.loads(l) for l in f if l.strip())
        except (OSError, ValueError):
            continue
    return out


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    auj = dt.datetime.now(dt.timezone.utc).date()
    debut = argv[1] if len(argv) > 1 and argv[1] else DEBUT
    fin = argv[2] if len(argv) > 2 and argv[2] else (auj - dt.timedelta(days=1)).isoformat()
    budget = int(argv[3]) if len(argv) > 3 and argv[3] else 2500
    etat = lire_etat()
    jours, d = [], dt.date.fromisoformat(debut)
    while d <= dt.date.fromisoformat(fin):
        if not (etat['jours'].get(d.isoformat()) or {}).get('complet'):
            jours.append(d.isoformat())
        d += dt.timedelta(days=1)
    c = FM.Client(cle, budget=budget, reserve=int(os.environ.get('FEUILLES_RESERVE', '6000')))
    print(f"Résultats ITF hommes : {debut} → {fin} · {len(jours)} jour(s) à faire · budget {budget}, réserve {c.reserve}")
    arret, mois_ouverts, faits = None, {}, 0
    try:
        for j in jours:
            r = collecter_jour(c, j)
            if r is None:
                print(f"  {j} : indisponible, repris au prochain passage")
                continue
            m = j[:7]
            if m not in mois_ouverts:
                mois_ouverts[m] = lire_mois(m)
            mois_ouverts[m].update(r)
            etat['jours'][j] = {'matchs': len(r), 'complet': (auj - dt.date.fromisoformat(j)).days > DELAI_COMPLET_J}
            faits += 1
            if faits % 60 == 0:
                print(f"  … {j} : {sum(len(v) for v in mois_ouverts.values())} matchs ce passage", flush=True)
    except FM.QuotaAtteint as e:
        arret = str(e)
        print(f"::warning::Arrêt : {arret} — le prochain passage reprendra.")
    finally:
        for m, recs in mois_ouverts.items():
            ecrire_mois(m, recs)
        etat['dernier_passage'] = {'le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                                   'requetes': c.n, 'codes': {str(k): v for k, v in c.codes.items()},
                                   'quota_restant': c.restant, 'arret': arret}
        etat['total'] = {'jours': len(etat['jours']), 'matchs': sum(v['matchs'] for v in etat['jours'].values())}
        os.makedirs(DOSSIER, exist_ok=True)
        with open(os.path.join(DOSSIER, 'etat.json'), 'w', encoding='utf-8') as f:
            json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Jours traités : {faits} · requêtes {c.n} · codes {c.codes} · quota restant {c.restant} · "
          f"total {etat['total']['matchs']} matchs sur {etat['total']['jours']} jours")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
