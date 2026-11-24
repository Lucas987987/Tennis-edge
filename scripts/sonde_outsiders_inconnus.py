#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_outsiders_inconnus.py — l'outsider « peu documenté » l'est-il vraiment, ou nous manque-t-il ses matchs ?
(23/11/2026, paquet 397, Lucas : « il doit y avoir des erreurs dans nos données ou l'algo loupe quelque chose »)

Constat du 23/11 (matchs jugés du 21/10 au 22/11) : quand l'outsider a moins de 30 matchs dans notre classement et le
favori 30 ou plus, l'algo annonce le favori à 82,8 % et il gagne 74,4 % (90 matchs). Sur l'archive (2023 → 2026), le
même profil allait dans l'autre sens. Hypothèse : en direct, une partie des matchs récents de ces joueurs (ITF, juniors,
autres circuits) n'arrive pas dans notre classement, qui les croit plus faibles qu'ils ne sont.

Méthode (≈ 2 à 4 requêtes par joueur, budget réglable) :
  1. joueurs : les OUTSIDERS de ce profil (favori ≥ 50 %, outsider < 30 matchs classés, favori ≥ 30), matchs ATP, WTA,
     Challenger jugés depuis le 21/10 ; identifiant TennisApi lu dans nos feuilles de match ;
  2. leurs matchs passés chez TennisApi (/player/{id}/events/previous), en simple, terminés, depuis le 01/06/2024 ;
  3. comparaison au nombre de matchs de leur classement chez nous (simulateur/elo_etat.json, mêmes alias qu'en
     production) ; le détail des matchs TennisApi par catégorie (ITF, Challenger, juniors…).

RÈGLE FIXÉE LE 23/11/2026, AVANT LA SONDE :
  DONNÉES MANQUANTES si, pour la MÉDIANE des outsiders sondés (au moins 30 joueurs), TennisApi connaît au moins
  2 fois plus de matchs terminés depuis le 01/06/2024 que notre classement n'en compte en tout, ET au moins 10 de plus.
  Alors : collecte des catégories manquantes (étude à part, jugée avant la production). Sinon : nos données ne sont
  pas en cause, le profil passe en suivi (règle à part) comme un défaut du modèle.
Sortie : simulateur/sonde_outsiders_inconnus.json (aucune cote) ; le journal n'affiche que des nombres.
Usage : python scripts/sonde_outsiders_inconnus.py [racine] [budget]
Env : RAPIDAPI_KEY ; FEUILLES_RESERVE (défaut 6 000).
"""
import collections
import datetime as dt
import glob
import gzip
import json
import os
import statistics
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))

DEPUIS = dt.date(2024, 6, 1)
DEBUT_JUGES = '2026-10-21'
SEUIL_MATCHS = 30
MIN_JOUEURS, RAPPORT_MIN, ECART_MIN = 30, 2.0, 10
SORTIE = os.path.join('simulateur', 'sonde_outsiders_inconnus.json')


def cibles(resultats, juge):
    """[(nom, jour, uid, outsider_a_gagne)] — un par outsider (son match le plus récent)."""
    out = {}
    for m in resultats.get('matchs') or []:
        if m.get('circuit') not in ('ATP', 'WTA', 'CH') or str(m.get('debut'))[:10] < DEBUT_JUGES:
            continue
        reel = m.get('reel') or {}
        if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        p = juge(m)
        mj = m.get('matchs_joues') or [None, None]
        if p is None or None in mj:
            continue
        fav_home = p >= 0.5
        mf, mo = (mj[0], mj[1]) if fav_home else (mj[1], mj[0])
        if mo >= SEUIL_MATCHS or mf < SEUIL_MATCHS:
            continue
        nom = m['away'] if fav_home else m['home']
        gagne = (reel['gagnant'] == 'home') != fav_home
        out[nom] = (nom, str(m['debut'])[:10], m.get('uid'), gagne)
    return sorted(out.values())


def ids_des_feuilles(racine, cle):
    """{clé du joueur: identifiant TennisApi} d'après nos feuilles de match."""
    ids = {}
    for f in sorted(glob.glob(os.path.join(racine, 'feuilles', '2026-*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                for c in ('home', 'away'):
                    j = r.get(c) or {}
                    if j.get('id') and j.get('nom'):
                        ids[cle(j['nom'])] = j['id']
    return ids


def compter(evenements):
    """Matchs en simple terminés depuis DEPUIS, par catégorie."""
    import feuilles_match as FM
    par = collections.Counter()
    for e in evenements or []:
        if (e.get('status') or {}).get('type') != 'finished' or not FM.est_simple(e):
            continue
        ts = e.get('startTimestamp') or 0
        if dt.datetime.fromtimestamp(ts, dt.timezone.utc).date() < DEPUIS:
            continue
        cat = FM.norm(((e.get('tournament') or {}).get('category') or {}).get('name')) or 'inconnue'
        par[cat] += 1
    return par


def doublons_possibles(noms, J, cle, mots):
    """Sans réseau : un joueur peu documenté dont le nom de famille existe chez nous avec un prénom proche et PLUS de
    matchs (« Aleksandr » / « Alexander Shevchenko », « Zachary » / « Zach Viiala ») — à vérifier, rien n'est relié ici."""
    import difflib
    par_nom = collections.defaultdict(list)
    for k, v in J.items():
        t = mots(v.get('nom') or '')
        if t:
            par_nom[t[-1]].append((k, v))
    out = []
    for n in sorted(set(noms)):
        k, t = cle(n), mots(n)
        if not t:
            continue
        pren, mine = ' '.join(t[:-1]), int((J.get(k) or {}).get('matchs') or 0)
        for k2, v2 in par_nom.get(t[-1], []):
            if k2 == k or int(v2.get('matchs') or 0) <= mine:
                continue
            p2 = ' '.join(mots(v2['nom'])[:-1])
            r = difflib.SequenceMatcher(None, pren.replace(' ', ''), p2.replace(' ', '')).ratio()
            if r >= 0.7:
                out.append({'joueur': n, 'matchs': mine, 'autre_nom': v2['nom'], 'matchs_autre': int(v2['matchs']),
                            'proximite_prenom': round(r, 2)})
    return out


def decider(par_joueur):
    L = [x for x in par_joueur if x.get('tennisapi') is not None]
    if len(L) < MIN_JOUEURS:
        return {'donnees_manquantes': None, 'raison': f'{len(L)} joueurs sondés (il en faut {MIN_JOUEURS})'}
    rapports = [x['tennisapi'] / max(1, x['classement']) for x in L]
    ecarts = [x['tennisapi'] - x['classement'] for x in L]
    r, e = statistics.median(rapports), statistics.median(ecarts)
    ok = r >= RAPPORT_MIN and e >= ECART_MIN
    return {'donnees_manquantes': ok, 'rapport_median': round(r, 2), 'ecart_median': e, 'joueurs': len(L),
            'regle': f'médiane TennisApi / classement ≥ {RAPPORT_MIN:g} et écart médian ≥ {ECART_MIN}'}


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    budget = int(argv[2]) if len(argv) > 2 else 500
    import elo as E
    import vitrine as V
    import feuilles_match as FM
    import sonde_peu_documentes as SP
    etat = json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8'))
    alias, J = etat.get('alias') or {}, etat.get('joueurs') or {}
    cle = lambda n: alias.get(E.cle(n), E.cle(n))  # noqa: E731
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        res = json.load(f)
    joueurs = cibles(res, lambda m: V._juge(m)[0])
    ids = ids_des_feuilles(racine, cle)
    doubles = doublons_possibles([n for n, *_ in joueurs], J, cle, E.mots)
    print(f"Identités à vérifier (même nom de famille, prénom proche, plus de matchs) : {len(doubles)}")
    print(f"Sonde : {len(joueurs)} outsiders peu documentés · budget {budget} requêtes")
    cle_api = os.environ.get('RAPIDAPI_KEY')
    if not cle_api:
        print('::error::RAPIDAPI_KEY absente')
        return 1
    c = FM.Client(cle_api, budget=budget, reserve=int(os.environ.get('FEUILLES_RESERVE', '6000')))
    par_joueur, cats, arret = [], collections.Counter(), None
    for nom, jour, uid, gagne in joueurs:
        k = cle(nom)
        x = {'joueur': nom, 'classement': int((J.get(k) or {}).get('matchs') or 0), 'a_gagne': gagne, 'tennisapi': None}
        i = ids.get(k)
        if i:
            try:
                ev = SP.matchs_passes(c, i, journal=lambda *_: None)
            except FM.QuotaAtteint as e:
                arret = str(e)
                break
            if ev is not None:
                par = compter(ev)
                x['tennisapi'], x['par_categorie'] = sum(par.values()), dict(par)
                cats.update(par)
        par_joueur.append(x)
    verdict = decider(par_joueur) if not arret else {'donnees_manquantes': None, 'raison': 'sonde incomplète : ' + arret}
    sondes = [x for x in par_joueur if x['tennisapi'] is not None]
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'depuis': DEPUIS.isoformat(),
           'regle': verdict.get('regle') or __doc__.split('RÈGLE FIXÉE')[1].split('Sortie')[0].strip(),
           'outsiders': len(joueurs), 'sondes': len(sondes), 'requetes': c.n, 'quota_restant': c.restant,
           'verdict': verdict, 'par_categorie': dict(cats.most_common()),
           'vainqueurs_contre_battus': {
               'vainqueurs': [x['tennisapi'] - x['classement'] for x in sondes if x['a_gagne']],
               'battus': [x['tennisapi'] - x['classement'] for x in sondes if not x['a_gagne']]},
           'identites_a_verifier': doubles, 'par_joueur': par_joueur}
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"Sondés : {len(sondes)} · requêtes {c.n} · quota restant {c.restant}" + (f" · ARRÊT : {arret}" if arret else ''))
    if arret and getattr(c, 'reset_s', None):
        fin = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=c.reset_s)
        print(f"Quota TennisApi renouvelé dans {c.reset_s // 3600} h {c.reset_s % 3600 // 60:02d} "
              f"(vers {fin.strftime('%d/%m %H:%M')} UTC)")
    if sondes:
        print(f"Matchs depuis le 01/06/2024 chez TennisApi (médiane) : {statistics.median(x['tennisapi'] for x in sondes)} · "
              f"dans notre classement (médiane, en tout) : {statistics.median(x['classement'] for x in sondes)}")
        for cat, n in cats.most_common(8):
            print(f"  {cat} : {n} matchs")
    print(f"Verdict : {json.dumps(verdict, ensure_ascii=False)}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
