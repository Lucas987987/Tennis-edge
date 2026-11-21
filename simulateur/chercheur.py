#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chercheur.py — LE CHERCHEUR AUTOMATIQUE (21/11/2026, paquet 320, décision de Lucas : « Oui »).

Chaque semaine, il balaie des familles de pistes et classe celles qui amélioreraient les % sur des matchs jamais vus.
Il ne change RIEN dans l'algo : il propose, Lucas décide, et une piste retenue n'entre que par un paquet à part avec sa
règle de retrait.

REJEU « COMME EN PRODUCTION » : archive Sackmann + résultats ITF hommes (etude_depart_itf.matchs), Elo de production
(départs en place), mêmes clés de joueurs que la production. BASE = ce que l'algo fait déjà et qu'on sait rejouer :
Elo + changement de surface, retour d'absence, âge (β appris sur 2018–2022) ; en Challenger, en plus, les deux décalages
d'outsider (paquet 274) et la zone d'hésitation (paquets 314–315). Le reste de la production (simulation, arbres) n'est
pas rejoué : une piste retenue est une CANDIDATE, à confirmer avant toute mise en place.

PÉRIODES (le piège des paquets 229, 230 et 318 : l'archive n'a les résultats ITF hommes que depuis juin 2024) :
  ATP, WTA   — apprendre sur 2018–2022, juger sur 2023 → juin 2026 ;
  Challenger — apprendre du 01/01/2025 au 30/09/2025, juger du 01/10/2025 au 31/05/2026 (Elo nourri des ITF hommes).

FAMILLES DE PISTES :
  pentes (le % rapproché de 50 % ou éloigné, case par case) : tous les matchs du circuit, niveau du tournoi, tour,
  surface, saison, format (2 ou 3 sets gagnants), expérience du moins connu ;
  décalages (vers le joueur concerné) : écart de classement, jours de repos, matchs joués sur 14 jours, gaucher contre
  droitier, joueur à domicile, qualifié, invité, expérience.

RÈGLE ÉCRITE LE 21/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup), piste par piste et
CIRCUIT PAR CIRCUIT : le paramètre est appris sur la période d'apprentissage, puis jugé une seule fois sur la période
de jugement. CANDIDATE si : au moins 1 000 matchs jugés concernés ; gain de log loss ≥ 0,001 ; gain ≥ 3,3 erreurs types
(seuil plus strict que pour une étude seule, parce que le chercheur teste beaucoup de pistes à la fois) ; et le paramètre
réappris sur la période de jugement va dans le MÊME SENS (pente du même côté de 1, décalage du même signe).
Rapport public : simulateur/rapport_chercheur.json (aucun nom de joueur). Les 3 meilleures candidates partent sur le
Telegram privé. Le % ne change pas.
Usage : python simulateur/chercheur.py /tmp/sackmann . [--telegram]
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402
import backtest_pronostic as BP  # noqa: E402
import etude_depart_itf as ED  # noqa: E402
import etude_age as EA  # noqa: E402
import etude_changement_surface as ECS  # noqa: E402
import etude_retour_absence as ERA  # noqa: E402
import etude_signaux_combines as ESC  # noqa: E402
import etude_outsiders as EO  # noqa: E402
import etude_outsiders_gagnants as EOG  # noqa: E402
import etude_outsiders_vague2 as EV2  # noqa: E402
import etude_hesitation as EH  # noqa: E402
import etude_fiabilite_v3 as V3  # noqa: E402

MIN_JUGES, MARGE, MIN_ERREURS_TYPES, MIN_CASE = 1000, 0.001, 3.3, 300
PERIODES = {'ATP': ((dt.date(2018, 1, 1), dt.date(2023, 1, 1)), (dt.date(2023, 1, 1), dt.date(2026, 7, 1))),
            'WTA': ((dt.date(2018, 1, 1), dt.date(2023, 1, 1)), (dt.date(2023, 1, 1), dt.date(2026, 7, 1))),
            'CH': ((dt.date(2025, 1, 1), dt.date(2025, 10, 1)), (dt.date(2025, 10, 1), dt.date(2026, 6, 1)))}
DEBUT = dt.date(2018, 1, 1)
HESITATION = {'classement': 0.0447, 'invitation': -0.202, 'experience': 0.0526}
SORTIE = os.path.join(ICI, 'rapport_chercheur.json')
_lg, _sg = EOG._lg, EOG._sg


def lignes(archive, racine):
    """Une ligne par match (ATP, WTA, Challenger depuis 2018), vue du VAINQUEUR : z (Elo), x5 (signaux en place) et ce
    que chaque piste voit des deux joueurs."""
    M, n_itf = ED.matchs(archive, racine)
    if not n_itf:                                   # sans les ITF hommes, le Challenger ne serait PAS comme en production
        raise SystemExit('Résultats ITF hommes introuvables (resultats_itf/ et scripts/resultats_itf.py) : rejeu impossible.')
    X, P = EOG.extras(archive), EOG.pays_tournois(racine)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    dernier, nb, jours = {}, {}, {}
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d, tid = m['circuit'], m.get('surface'), m['date'], m.get('tournoi_id')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon') and m.get('niveau') != 'D':
            z = _lg(el.proba(g, p, s))
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            ex = X.get((str(tid or ''), m.get('num') or 0, m.get('nom_g') or ''))
            pt = EOG.pays_du(m.get('tournoi'), P)

            def vue(j, ioc, rang, entree, main):
                dj = dernier.get(j)
                L = jours.get(j, [])
                return {'long': bool(dj and dj[0] == tid and dj[1]), 'court': bool(not dj or dj[0] != tid or not dj[1]),
                        'rang': rang, 'qualifie': entree in ('Q', 'LL'), 'invite': entree == 'WC',
                        'domicile': bool(pt and EOG.CIO.get(ioc) == pt), 'experience': nb.get(j, 0),
                        'gaucher': main == 'L', 'droitier': main == 'R', 'n_elo': el.matchs(j),
                        'repos': (d - L[-1]).days if L else None, 'charge14': sum(1 for x in L if 0 <= (d - x).days <= 14)}
            vg = vue(g, ex[0] if ex else '', ex[2] if ex else None, m.get('entree_g') or '', m.get('main_g'))
            vp = vue(p, ex[1] if ex else '', ex[3] if ex else None, m.get('entree_p') or '', m.get('main_p'))
            rows.append({'c': c, 'd': d, 'z': z, 'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1],
                                                         xg[0], xg[1]),
                         'niveau': m.get('niveau'), 'tour': m.get('tour'), 'surface': s, 'bo': m.get('bo'), 'vg': vg, 'vp': vp})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        long_match = len(m.get('sets') or []) >= (5 if m.get('bo') == 5 else 3)
        for j in (g, p):
            dernier[j] = (tid, long_match)
            if c in ('ATP', 'WTA', 'CH'):
                nb[j] = nb.get(j, 0) + 1
            L = jours.setdefault(j, [])
            L.append(d)
            if len(L) > 30:
                del L[:-30]
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def poser_base(rows, racine):
    """zb = ce que l'algo fait déjà et qu'on sait rejouer (voir l'en-tête)."""
    betas = EO.poser_la_base(rows)
    EV2.poser_ch_en_place(rows, EV2.decalages_ch(racine))
    for r in rows:
        if r['c'] != 'CH':
            continue
        x = EH.zone(r)
        if not x:
            continue
        zf, f, a, y = x
        dlt = sum(b * EH.indice(n, f, a) for n, b in HESITATION.items())
        r['zb'] += dlt if y else -dlt
    return betas


def _saison(r):
    m = r['d'].month
    return 'janvier-février' if m <= 2 else ('mars-mai' if m <= 5 else ('juin-août' if m <= 8 else 'septembre-décembre'))


def _exp(r):
    n = min(r['vg']['n_elo'], r['vp']['n_elo'])
    return 'moins de 30' if n < 30 else ('30 à 99' if n < 100 else ('100 à 299' if n < 300 else '300 et plus'))


TOURS = {0: 'qualifications, 1er tour', 1: 'qualifications, 2e tour', 2: 'qualifications, 3e tour', 3: 'qualifications, 4e tour',
         4: '1er tour (128)', 5: '64es', 6: '32es ou poule', 7: '8es', 8: 'quarts', 9: 'demies', 10: 'finale'}
PENTES = {'tous les matchs': lambda r: 'tous', 'niveau du tournoi': lambda r: r['niveau'],
          'tour': lambda r: TOURS.get(r['tour'], r['tour']), 'surface': lambda r: r['surface'],
          'saison': _saison, 'format': lambda r: r['bo'], 'expérience du moins connu': _exp}


def _rang(v):
    return math.log2(v['rang']) if v['rang'] and v['rang'] > 0 else None


def _ecart_rang(g, p):
    a, b = _rang(g), _rang(p)
    return 0.0 if a is None or b is None else max(-4.0, min(4.0, b - a))


DECALAGES = {
    'écart de classement': _ecart_rang,
    'jours de repos': lambda g, p: 0.0 if g['repos'] is None or p['repos'] is None else (min(g['repos'], 21) - min(p['repos'], 21)) / 7,
    'matchs sur 14 jours': lambda g, p: (min(g['charge14'], 8) - min(p['charge14'], 8)) / 4,
    'gaucher contre droitier': lambda g, p: float(g['gaucher'] and p['droitier']) - float(p['gaucher'] and g['droitier']),
    'à domicile': lambda g, p: float(g['domicile']) - float(p['domicile']),
    'qualifié': lambda g, p: float(g['qualifie']) - float(p['qualifie']),
    'invité': lambda g, p: float(g['invite']) - float(p['invite']),
    'expérience': lambda g, p: math.log1p(g['experience']) - math.log1p(p['experience']),
}


def _periode(r):
    (a0, a1), (j0, j1) = PERIODES[r['c']]
    return 'A' if a0 <= r['d'] < a1 else ('J' if j0 <= r['d'] < j1 else None)


def _verdict(b, meme_sens):
    raisons = []
    if b.get('matchs', 0) < MIN_JUGES:
        raisons.append(f'moins de {MIN_JUGES} matchs jugés')
    if b.get('gain', -1) < MARGE:
        raisons.append(f'gain sous {MARGE}')
    if (b.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f'gain sous {MIN_ERREURS_TYPES:g} erreurs types')
    if not meme_sens:
        raisons.append("pas le même sens sur les deux périodes")
    return raisons


def pistes_pente(rows, c, famille, cle):
    out, cases = [], {}
    for r in rows:
        if r['c'] == c and r.get('per'):
            cases.setdefault(cle(r), {'A': [], 'J': []})[r['per']].append(r['zb'])
    for v, d in cases.items():
        if v is None or len(d['A']) < MIN_CASE or len(d['J']) < 50:
            continue
        a, aj = V3.pente(d['A']), V3.pente(d['J'])
        b = EO.bilan(d['J'], [a * z for z in d['J']])
        raisons = _verdict(b, (a - 1) * (aj - 1) > 0)
        out.append({'famille': famille, 'circuit': c, 'case': str(v), 'forme': 'pente', 'parametre': round(a, 4),
                    'parametre_jugement': round(aj, 4), 'jugement': b, 'candidate': not raisons, 'raisons': raisons})
    return out


def pistes_decalage(rows, c, famille, f):
    A, J = [], []
    for r in rows:
        if r['c'] != c or not r.get('per'):
            continue
        x = f(r['vg'], r['vp'])
        if x:
            (A if r['per'] == 'A' else J).append((r['zb'], (x,)))
    if len(A) < MIN_CASE or len(J) < 50:
        return []
    b0, bj = ESC.apprendre(A, k=1)[0], ESC.apprendre(J, k=1)[0]
    b = EO.bilan([z for z, _ in J], [z + b0 * x[0] for z, x in J])
    raisons = _verdict(b, b0 * bj > 0)
    return [{'famille': famille, 'circuit': c, 'case': 'matchs concernés', 'forme': 'décalage', 'parametre': round(b0, 4),
             'parametre_jugement': round(bj, 4), 'jugement': b, 'candidate': not raisons, 'raisons': raisons}]


def regle():
    return (__doc__.split('RÈGLE ÉCRITE LE 21/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup),')[1]
            .split('Rapport public')[0].replace('\n', ' ').replace('  ', ' ').strip())


def chercher(rows):
    for r in rows:
        r['per'] = _periode(r)
    out = []
    for c in ('ATP', 'WTA', 'CH'):
        for fam, cle in PENTES.items():
            out += pistes_pente(rows, c, fam, cle)
        for fam, f in DECALAGES.items():
            out += pistes_decalage(rows, c, fam, f)
    out.sort(key=lambda p: -(p['jugement'].get('erreurs_types') or -99))
    return out


def message(doc):
    C = [p for p in doc['pistes'] if p['candidate']][:3]
    if not C:
        return f"🔎 Chercheur ({doc['genere_le'][:10]}) : {doc['pistes_testees']} pistes testées, aucune candidate."
    L = [f"🔎 Chercheur ({doc['genere_le'][:10]}) : {doc['candidates']} candidate(s) sur {doc['pistes_testees']} pistes. Les meilleures :"]
    for p in C:
        j = p['jugement']
        L.append(f"• {p['circuit']} · {p['famille']} · {p['case']} ({p['forme']} {p['parametre']}) : {j['matchs']} matchs, "
                 f"gain {j['gain']} ({j['erreurs_types']} erreurs types), Brier {j['brier_base']} → {j['brier']}")
    L.append("Candidates seulement : à confirmer avant toute mise en place.")
    return '\n'.join(L)


def telegram(texte):
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        print('Telegram non configuré : message non envoyé.')
        return
    data = urllib.parse.urlencode({'chat_id': chat, 'text': texte}).encode()
    urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=30).read()


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 and not argv[2].startswith('--') else '.')
    rows = lignes(archive, racine)
    betas = poser_base(rows, racine)
    P = chercher(rows)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 320, 'regle': regle(),
           'periodes': {c: {'apprentissage': [str(a0), str(a1)], 'jugement': [str(j0), str(j1)]} for c, ((a0, a1), (j0, j1)) in PERIODES.items()},
           'base': {'signaux': 'surface, absence, âge', 'betas': betas,
                    'challenger_en_plus': "décalages d'outsider (paquet 274), zone d'hésitation (paquets 314–315)"},
           'pistes_testees': len(P), 'candidates': sum(p['candidate'] for p in P), 'pistes': P,
           'descriptif': 'le % de victoire ne change pas'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    txt = message(doc)
    print(txt)
    if '--telegram' in argv:
        telegram(txt)


if __name__ == '__main__':
    main(sys.argv)
