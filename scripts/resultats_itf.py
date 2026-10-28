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

28/10/2026 (1er run coupé par la limite de 40 min, tout perdu car écrit à la fin) : chaque MOIS est écrit dès qu'on
passe au suivant (et l'état avec lui), et le script s'arrête de lui-même après ITF_MINUTES (défaut 45) : un passage
coupé ne perd plus que le mois en cours ; le suivant reprend là.

Usage : python scripts/resultats_itf.py [debut AAAA-MM-JJ] [fin AAAA-MM-JJ] [budget]
Env : RAPIDAPI_KEY ; FEUILLES_RESERVE (défaut ici : 6 000) ; ITF_MINUTES (défaut 45).
"""
import datetime as dt
import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

# 28/10/2026 — ITF FEMMES (ITF_SEXE=F) : l'archive Sackmann contient l'ITF féminin jusqu'au 02/06/2026 ; depuis, plus rien
# (feuilles_match.py ne collecte plus l'ITF depuis le 22/10, et pas de résultats sans feuille). On reprend donc le
# 25/05/2026 (chevauchement d'une semaine ; un match déjà dans l'archive est écarté par l'étude).
SEXE = os.environ.get('ITF_SEXE', 'H').upper()
DOSSIER_HOMMES, DOSSIER_FEMMES = 'resultats_itf', 'resultats_itf_femmes'
DOSSIER = os.environ.get('ITF_DOSSIER', DOSSIER_FEMMES if SEXE == 'F' else DOSSIER_HOMMES)
DEBUT = '2026-05-25' if SEXE == 'F' else '2024-06-01'
CATEGORIE = 'itf women' if SEXE == 'F' else 'itf men'
DELAI_COMPLET_J = 3
MINUTES = float(os.environ.get('ITF_MINUTES', '45'))
CHAMPS = ('categorie', 'id', 'jour', 'debut', 'tournoi', 'tournoi_id', 'surface', 'tour', 'meilleur_des', 'vainqueur',
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


def lire_tout(racine, dossier=DOSSIER_HOMMES):
    """Toutes les fiches stockées d'un dossier (hommes par défaut ; DOSSIER_FEMMES pour l'ITF féminin)."""
    import glob
    out = []
    for p in sorted(glob.glob(os.path.join(racine, dossier, '20*.jsonl.gz'))):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                out.extend(json.loads(l) for l in f if l.strip())
        except (OSError, ValueError):
            continue
    return out


def ecrire_etat(etat, c, arret, dossier=DOSSIER):
    etat['dernier_passage'] = {'le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                               'requetes': c.n, 'codes': {str(k): v for k, v in c.codes.items()},
                               'quota_restant': c.restant, 'arret': arret}
    etat['total'] = {'jours': len(etat['jours']), 'matchs': sum(v['matchs'] for v in etat['jours'].values())}
    os.makedirs(dossier, exist_ok=True)
    with open(os.path.join(dossier, 'etat.json') + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(os.path.join(dossier, 'etat.json') + '.tmp', os.path.join(dossier, 'etat.json'))


def passer(c, jours, etat, auj, collecter=None, limite_s=None, horloge=time.monotonic, journal=None, dossier=DOSSIER):
    """Collecte les jours dans l'ordre ; chaque mois est écrit (avec l'état) dès qu'on passe au suivant.
    Renvoie (jours faits, raison d'arrêt ou None)."""
    collecter = collecter or collecter_jour
    journal = journal or (lambda *a: print(*a, flush=True))
    t0, mois, recs, faits, arret = horloge(), None, {}, 0, None

    def vider():
        if mois is not None:
            ecrire_mois(mois, recs, dossier)
            ecrire_etat(etat, c, arret, dossier)
    try:
        for j in jours:
            if limite_s is not None and horloge() - t0 > limite_s:
                arret = f"temps du passage écoulé ({limite_s / 60:.0f} min)"
                journal(f"::notice::Arrêt : {arret} — le prochain passage reprendra au {j}.")
                break
            if j[:7] != mois:
                vider()
                mois, recs = j[:7], lire_mois(j[:7], dossier)
            r = collecter(c, j)
            if r is None:
                journal(f"  {j} : indisponible, repris au prochain passage")
                continue
            recs.update(r)
            etat['jours'][j] = {'matchs': len(r), 'complet': (auj - dt.date.fromisoformat(j)).days > DELAI_COMPLET_J}
            faits += 1
            if faits % 60 == 0:
                journal(f"  … {j} : {sum(v['matchs'] for v in etat['jours'].values())} matchs au total")
    except FM.QuotaAtteint as e:
        arret = str(e)
        journal(f"::warning::Arrêt : {arret} — le prochain passage reprendra.")
    finally:
        vider()
    return faits, arret


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
    print(f"Résultats {CATEGORIE.upper()} : {debut} → {fin} · {len(jours)} jour(s) à faire · budget {budget}, réserve {c.reserve}, "
          f"{MINUTES:.0f} min au plus")
    faits, arret = passer(c, jours, etat, auj, limite_s=MINUTES * 60)
    ecrire_etat(etat, c, arret)
    print(f"Jours traités : {faits} · requêtes {c.n} · codes {c.codes} · quota restant {c.restant} · "
          f"total {etat['total']['matchs']} matchs sur {etat['total']['jours']} jours")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
