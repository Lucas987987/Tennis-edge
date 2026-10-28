#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_peu_documentes.py — AVANT toute collecte historique : TennisApi a-t-il des feuilles de match que nous
n'avons pas, pour les joueurs Challenger peu documentés ? (28/10/2026)

Constat du 28/10 (419 matchs jugés depuis le 21/10) : 19,8 % des joueurs Challenger pronostiqués ont moins de
1 500 balles de service effectives ; quand le moins documenté des deux est entre 500 et 1 500, l'algo trouve 47 %
des vainqueurs pour 70 % de confiance (55 matchs). Leurs matchs Challenger de l'archive Sackmann ont presque
tous une feuille : ce qui manque, ce sont surtout leurs matchs ITF (absents de l'archive masculine) — et TennisApi
n'a de statistiques que pour ~6 % des matchs ITF collectés. D'où cette sonde, avant de dépenser du quota.

Méthode (≈ 600 requêtes, budget réglable) :
  1. joueurs ciblés : ceux des matchs Challenger jugés depuis le 21/10 (pronostics_resultats.json) avec moins de
     1 500 balles effectives (profils de l'archive + feuilles, demi-vie 1 an, comme la production) ; nom relié
     comme en production (elo.unifier) ; identifiant TennisApi lu dans nos feuilles ;
  2. leurs matchs passés : /api/tennis/player/{id}/events/previous/{page} (repli /team/), jusqu'au 1er juin 2024 ;
  3. chaque match en simple terminé est « connu » si nous avons déjà sa feuille (archive ou feuilles, même jour
     ± 1 et un mot du nom de l'adversaire en commun), sinon « manquant » ;
  4. pour chaque joueur et chaque catégorie (ITF, Challenger…), jusqu'à 3 matchs manquants tirés au sort (graine
     fixe) : /api/tennis/event/{id}/statistics — la feuille existe-t-elle, et est-elle cohérente ?
  5. estimation : feuilles récupérables = manquants × taux de feuilles de leur catégorie ; balles gagnées =
     Σ (balles moyennes d'une feuille × poids d'ancienneté du match), par joueur.

RÈGLE FIXÉE LE 28/10/2026, AVANT TOUT RÉSULTAT DE LA SONDE :
  la collecte historique n'est construite que si (a) au moins 300 feuilles récupérables sont estimées au total ET
  (b) la médiane des joueurs ciblés gagnerait au moins 50 % de balles effectives. Sinon, pas de collecte : le
  manque est dans des matchs que personne ne documente, et la piste suivante est autre (résultats sans feuille).
  Si la règle passe, la collecte sera jugée à son tour AVANT d'entrer en production : profils reconstruits avec et
  sans les feuilles récupérées, vraisemblance des points de service des joueurs ciblés sur leurs matchs Challenger
  jugés (après la date des feuilles ajoutées), adoption si la log-vraisemblance par point gagne au moins 0,001.

Sortie : simulateur/sonde_peu_documentes.json (descriptif, aucune cote) + résumé dans le journal du run.
Usage : python scripts/sonde_peu_documentes.py <archive Sackmann> [racine] [budget]
Env : RAPIDAPI_KEY ; FEUILLES_RESERVE (défaut 6 000 : la collecte du jour garde son quota).
"""
import datetime as dt
import json
import os
import random
import statistics
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))

DEPUIS = dt.date(2024, 6, 1)
DEBUT_JUGES = '2026-10-21'
SEUIL_BALLES = 1500.0
MAX_JOUEURS = 80
PAGES_MAX = 4
TIRAGE_PAR_CATEGORIE = 3
DEMI_VIE = 365.0
REGLE_FEUILLES_MIN = 300
REGLE_GAIN_MEDIAN = 0.50
SORTIE = os.path.join('simulateur', 'sonde_peu_documentes.json')


# ------------------------------------------------------------------ hors réseau (testable)
def mots(nom):
    import donnees
    return {w for w in donnees.norm(nom) if len(w) >= 3}


def balles_effectives(tout, jour):
    """{clé E.cle: (balles de service effectives au jour, nom)} — mêmes sommes que profils_service (demi-vie 1 an)."""
    import elo as E
    import profils_service as PS
    P = PS.construire(tout, cle=E.cle, demi_vie=DEMI_VIE)
    doc = P.exporter(jour, n_min=0.0)
    i = doc['champs'].index('svpt')
    return {k: (v['sommes']['all'][i], v.get('nom') or k) for k, v in doc['joueurs'].items() if v['sommes'].get('all')}


def cibles(resultats, balles, ids_par_cle):
    """[(nom, clé, balles, id TennisApi)] des joueurs Challenger jugés depuis le 21/10 sous 1 500 balles.
    balles : {clé: (balles, nom)} ; ids_par_cle : {clé: (id, nom)}."""
    import elo as E
    M = [m for m in (resultats or {}).get('matchs') or []
         if m.get('circuit') == 'CH' and str(m.get('debut'))[:10] >= DEBUT_JUGES]
    noms = [n for m in M for n in (m['home'], m['away'])]
    alias = E.unifier({k: v[1] for k, v in balles.items()}, noms)      # nom écrit autrement -> clé connue
    alias_id = E.unifier({k: v[1] for k, v in ids_par_cle.items()}, noms)
    b_de = lambda kb: (balles.get(kb) or (0.0, ''))[0]
    vus, out = {}, []
    for n in noms:
        k = E.cle(n)
        kb = alias.get(k, k)
        if b_de(kb) >= SEUIL_BALLES:
            continue
        vus[n] = vus.get(n, 0) + 1
    for n, nb in sorted(vus.items(), key=lambda x: -x[1]):
        k = E.cle(n)
        kb = alias.get(k, k)
        i = (ids_par_cle.get(alias_id.get(k, k)) or (None, ''))[0]
        if i and all(x[1] != kb for x in out):
            out.append((n, kb, round(b_de(kb), 1), i))
    return out[:MAX_JOUEURS]


def connus_par_joueur(tout, cles):
    """{clé: [(date, mots de l'adversaire)]} des matchs AVEC feuille des joueurs ciblés."""
    import elo as E
    out = {k: [] for k in cles}
    for m in tout:
        if not m.get('detail') or m['date'] < DEPUIS - dt.timedelta(days=2):
            continue
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        if g in out:
            out[g].append((m['date'], mots(m['nom_p'])))
        if p in out:
            out[p].append((m['date'], mots(m['nom_g'])))
    return out


def est_connu(connus, jour, adversaire):
    w = mots(adversaire)
    return any(abs((d - jour).days) <= 1 and (w & mw) for d, mw in connus)


def categorie(e):
    import feuilles_match as FM
    return FM.norm(((e.get('tournament') or {}).get('category') or {}).get('name')) or 'inconnue'


def poids(jour, aujourd_hui):
    return 0.5 ** ((aujourd_hui - jour).days / DEMI_VIE)


def decider(par_joueur, feuilles_estimees):
    gains = [x['gain_relatif'] for x in par_joueur if x.get('gain_relatif') is not None]
    med = statistics.median(gains) if gains else None
    ok = feuilles_estimees >= REGLE_FEUILLES_MIN and med is not None and med >= REGLE_GAIN_MEDIAN
    return {'feuilles_recuperables_estimees': round(feuilles_estimees), 'gain_median_balles': round(med, 3) if med is not None else None,
            'collecte_justifiee': bool(ok),
            'regle': (f"collecte seulement si ≥ {REGLE_FEUILLES_MIN} feuilles récupérables estimées ET gain médian ≥ "
                      f"{int(100 * REGLE_GAIN_MEDIAN)} % de balles effectives (fixée le 28/10/2026, avant la sonde)")}


# ------------------------------------------------------------------ réseau
def matchs_passes(c, id_joueur, journal=print):
    """Événements passés du joueur (jusqu'à DEPUIS ou PAGES_MAX pages) ; None si l'adresse ne répond pas."""
    out, base = [], None
    for page in range(PAGES_MAX):
        for b in ([base] if base else ['player', 'team']):
            code, doc = c.get(f"/api/tennis/{b}/{id_joueur}/events/previous/{page}")
            if code == 200 and doc and doc.get('events') is not None:
                base = b
                break
        else:
            if page == 0:
                journal(f"  joueur {id_joueur} : historique indisponible (HTTP {code})")
                return None
            break
        ev = doc.get('events') or []
        out.extend(ev)
        plus_vieux = min((e.get('startTimestamp') or 0) for e in ev) if ev else 0
        if not doc.get('hasNextPage') or not ev or dt.datetime.fromtimestamp(plus_vieux, dt.timezone.utc).date() < DEPUIS:
            break
    return out


def sonder(c, joueurs, connus, aujourd_hui, journal=print):
    import feuilles as FE
    import feuilles_match as FM
    alea = random.Random(28102026)
    par_cat, par_joueur, balles_feuille = {}, [], []
    for nom, k, b, i in joueurs:
        ev = matchs_passes(c, i, journal)
        if ev is None:
            continue
        manquants = {}
        connus_j = 0
        for e in ev:
            if not e.get('id') or not e.get('startTimestamp') or not FM.est_simple(e):
                continue
            if (e.get('status') or {}).get('type') != 'finished':
                continue
            jour = FM.jour_utc(e['startTimestamp'])
            if jour < DEPUIS:
                continue
            h, a = e.get('homeTeam') or {}, e.get('awayTeam') or {}
            adv = a if h.get('id') == i else h
            cat = categorie(e)
            x = par_cat.setdefault(cat, {'matchs': 0, 'connus': 0, 'manquants': 0, 'sondes': 0, 'avec_feuille': 0})
            x['matchs'] += 1
            if est_connu(connus.get(k, []), jour, adv.get('name')):
                x['connus'] += 1
                connus_j += 1
            else:
                x['manquants'] += 1
                manquants.setdefault(cat, []).append((e['id'], jour, h.get('id') == i))
        par_joueur.append({'nom': nom, 'balles': b, 'connus': connus_j,
                           'manquants': {cat: [(eid, j.isoformat()) for eid, j, _ in L] for cat, L in manquants.items()},
                           '_m': manquants})
        for cat, L in manquants.items():
            for eid, jour, est_home in alea.sample(L, min(TIRAGE_PAR_CATEGORIE, len(L))):
                code, doc = c.get(f"/api/tennis/event/{eid}/statistics")
                par_cat[cat]['sondes'] += 1
                st = (FM.stats_compactes(doc) or {}).get('ALL') if code == 200 else None
                d = FE.detail(st, 0 if est_home else 2) if st else None
                if d:
                    par_cat[cat]['avec_feuille'] += 1
                    balles_feuille.append(d[0])
    moy = statistics.mean(balles_feuille) if balles_feuille else 0.0
    taux = {cat: (x['avec_feuille'] / x['sondes'] if x['sondes'] else 0.0) for cat, x in par_cat.items()}
    total = 0.0
    for p in par_joueur:
        M = p.pop('_m')
        est = sum(taux.get(cat, 0.0) for cat, L in M.items() for _ in L)
        gain = sum(taux.get(cat, 0.0) * moy * poids(j, aujourd_hui) for cat, L in M.items() for _, j, _ in L)
        total += est
        p['feuilles_recuperables_estimees'] = round(est, 1)
        p['balles_gagnees_estimees'] = round(gain, 1)
        p['gain_relatif'] = round(gain / max(p['balles'], 100.0), 3)
        p['manquants'] = {cat: len(L) for cat, L in p['manquants'].items()}
    for cat, x in par_cat.items():
        x['taux_feuilles'] = round(taux[cat], 3)
    return par_cat, par_joueur, total, moy


def main(argv):
    import donnees
    import elo as E
    import feuilles as FE
    import feuilles_match as FM
    args = [a for a in argv[1:]]
    if not args:
        print('Usage : python scripts/sonde_peu_documentes.py <archive Sackmann> [racine] [budget]')
        return 2
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    budget = int(args[2]) if len(args) > 2 else 600
    cle_api = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle_api:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    M = donnees.charger(args[0], 2016)
    fin_sack = max(m['date'] for m in M)
    F = [m for m in FE.charger(racine) if m['date'] > fin_sack]
    tout = sorted(M + F, key=lambda m: m['date'])
    auj = dt.datetime.now(dt.timezone.utc).date()
    balles = balles_effectives(tout, max(m['date'] for m in tout))
    ids = {}
    for r in FE.lire(racine):
        for cote in ('home', 'away'):
            j = r.get(cote) or {}
            if j.get('id') and j.get('nom'):
                ids.setdefault(E.cle(j['nom']), (j['id'], j['nom']))
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        resultats = json.load(f)
    joueurs = cibles(resultats, balles, ids)
    print(f"Sonde : {len(joueurs)} joueurs Challenger sous {int(SEUIL_BALLES)} balles · budget {budget} requêtes")
    connus = connus_par_joueur(tout, {k for _, k, _, _ in joueurs})
    c = FM.Client(cle_api, budget=budget, reserve=int(os.environ.get('FEUILLES_RESERVE', '6000')))
    arret = None
    try:
        par_cat, par_joueur, total, moy = sonder(c, joueurs, connus, auj)
    except FM.QuotaAtteint as e:
        print(f"::warning::Arrêt : {e} — sonde incomplète, rien n'est conclu.")
        arret, par_cat, par_joueur, total, moy = str(e), {}, [], 0.0, 0.0
    verdict = decider(par_joueur, total) if not arret else {'collecte_justifiee': False, 'regle': 'sonde incomplète'}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'depuis': DEPUIS.isoformat(),
           'joueurs_cibles': len(joueurs), 'joueurs_sondes': len(par_joueur), 'requetes': c.n,
           'codes': {str(k): v for k, v in c.codes.items()}, 'quota_restant': c.restant, 'arret': arret,
           'balles_moyennes_par_feuille': round(moy, 1), 'par_categorie': par_cat, 'verdict': verdict,
           'par_joueur': sorted(par_joueur, key=lambda x: -x.get('feuilles_recuperables_estimees', 0))}
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print('Par catégorie (matchs depuis le 1er juin 2024) :')
    for cat, x in sorted(par_cat.items(), key=lambda kv: -kv[1]['matchs']):
        print(f"  {cat} : {x['matchs']} matchs, {x['connus']} déjà avec feuille, {x['manquants']} manquants · "
              f"feuilles trouvées {x['avec_feuille']}/{x['sondes']} sondés ({100 * x['taux_feuilles']:.0f} %)")
    print(f"Verdict : {json.dumps(verdict, ensure_ascii=False)}")
    print(f"Requêtes : {c.n} · codes {c.codes} · quota restant annoncé : {c.restant}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
