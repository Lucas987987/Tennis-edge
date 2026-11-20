#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_vitesse_elo.py — l'Elo de la WTA réagit-il trop lentement ? Et la note de départ des joueurs venus des petits
niveaux est-elle trop basse ? (11/11/2026, audit, paquet 229)

Constats de l'audit, faits sur 2018–2022 SEULEMENT (simulateur/rapport_audit.json, paquets 227 et 228) :
  - WTA : une vitesse K × 1,25 gagne 0,0019 de log loss ; un Elo rapide (vitesse × 2,5) ajouté au nôtre gagne 0,0023
    (3,7 erreurs types). ATP et Challenger : rien.
  - Départ à 1300 au lieu de 1200 pour les joueurs vus d'abord en Challenger ou en ITF : ATP +0,0021, WTA +0,0012.
Le journal a rejeté le 29/10/2026 « vitesse propre aux hommes et aux femmes », sur un choix fait sur la seule année 2025.

Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match. Les femmes sont reconnues à leur identifiant d'archive (« wta: »). Matchs jugés : sans abandon, et sans les
compétitions par équipes (Coupe Davis, Billie Jean King Cup : dans l'Elo, jamais dans le jugement — sans cette
exclusion, le départ à 1350 « gagnait » 0,0024 en ATP, entièrement grâce à 845 matchs de Coupe Davis).

RÈGLES ÉCRITES LE 11/11/2026 (rapport_audit.json), AVANT DE REGARDER 2023 → :
  ÉTAPE 1 — vitesse en WTA. La FORME est choisie sur 2018–2022 (plus grand gain de log loss en WTA) parmi :
    vitesse K × 1,1 · × 1,25 · × 1,4 pour les joueuses, ou « Elo rapide » (un second Elo à vitesse × 2,5, ajouté au
    nôtre : logit p' = logit p + β · (logit p rapide − logit p), β appris sur 2018–2022).
    Elle est jugée UNE SEULE FOIS sur 2023 → juin 2026 et retenue si, en WTA : gain ≥ 0,001 sur ≥ 1 000 matchs,
    gain ≥ 2 erreurs types, gain positif sur les deux périodes.
  ÉTAPE 2 — départ des petits niveaux, avec le format ATP en place (pente 0,815 en 2 sets gagnants, paquet 228) et
    l'étape 1 en place si elle est retenue. La valeur est choisie sur 2018–2022 dans 1250 · 1300 · 1350 (plus grande
    moyenne des gains ATP et WTA, Challenger non dégradé de plus de 0,0005). Jugée une seule fois sur 2023 → juin
    2026 et retenue si un circuit au moins (ATP ou WTA) gagne ≥ 0,001 sur ≥ 1 000 matchs avec ≥ 2 erreurs types et un
    gain positif sur les deux périodes, ET si aucun circuit ne perd plus de 0,0005.
  Le Brier est publié à côté de la log loss ; il ne décide pas.

Usage : python simulateur/etude_vitesse_elo.py /tmp/sackmann .
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES, DEGRADATION_MAX = 1000, 0.001, 2.0, 0.0005
VITESSES, VITESSE_RAPIDE, DEPARTS = (1.1, 1.25, 1.4), 2.5, (1250.0, 1300.0, 1350.0)
PENTE_FORMAT = {('ATP', 3): 0.815}                           # paquet 228, en production
CIRCUITS = ('ATP', 'WTA', 'CH')
SORTIE = os.path.join(ICI, 'rapport_vitesse_elo.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


def ll(z):
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


def brier(z):
    return (1 - _sg(z)) ** 2


def femme(m):
    return str(m.get('gagnant') or '').startswith('wta:')


def rejouer(M, k, racine, vitesse_f=1.0, depart=None, rapide=False):
    """[(circuit, date, format, z, z rapide ou None)] dans l'ordre de M. vitesse_f : vitesse des joueuses ;
    depart : note de départ des petits niveaux (None = celle de la production) ; rapide : second Elo à vitesse × 2,5."""
    el, bas = E.de_production(racine)
    bas = depart if depart is not None else bas
    vite = E.Elo(**E.options_production(racine)[0]) if rapide else None
    rows = []
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, f = m['circuit'], m['surface'], femme(m)
        for e_ in (el, vite):
            if e_ is None:
                continue
            if bas and c in ('CH', 'ITF'):
                e_.presenter(g, bas)
                e_.presenter(p, bas)
            v = (vitesse_f if f else 1.0) * (VITESSE_RAPIDE if e_ is vite else 1.0)
            e_.regler_vitesse(g, v)
            e_.regler_vitesse(p, v)
        if c in CIRCUITS and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            rows.append((c, m['date'], m['bo'], _lg(el.proba(g, p, s)), _lg(vite.proba(g, p, s)) if vite else None))
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
        if vite:
            vite.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows


def beta_rapide(paires):
    """β qui minimise la log loss de σ(z + β·(z rapide − z)) ; Newton."""
    b = 0.0
    for _ in range(60):
        g = h = 0.0
        for z, zr in paires:
            x = zr - z
            q = _sg(z + b * x)
            g += (q - 1) * x
            h += q * (1 - q) * x * x
        if h < 1e-9:
            break
        b -= g / h
    return b


def compare(base, variante):
    """Gain de la variante sur la base, mêmes matchs : log loss (avec erreur type) et Brier."""
    n = len(base)
    if not n:
        return {'matchs': 0}
    d = [ll(a) - ll(b) for a, b in zip(base, variante)]
    moy = sum(d) / n
    et = math.sqrt(sum((x - moy) ** 2 for x in d) / n) / math.sqrt(n)
    return {'matchs': n, 'log_loss_base': round(sum(ll(a) for a in base) / n, 5),
            'log_loss': round(sum(ll(b) for b in variante) / n, 5), 'gain': round(moy, 5),
            'erreur_type': round(et, 5), 'erreurs_types': round(moy / et, 2) if et else None,
            'brier_base': round(sum(brier(a) for a in base) / n, 5), 'brier': round(sum(brier(b) for b in variante) / n, 5)}


def passe(appr, juge):
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if (juge.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f"gain sous {MIN_ERREURS_TYPES:g} erreurs types")
    if appr.get('gain', -1) <= 0:
        raisons.append("pas de gain sur 2018–2022")
    return not raisons, raisons


def _z(rows, c, periode, format_atp=False, col=3):
    out = []
    for r in rows:
        if r[0] != c or (r[1] < COUPURE) != (periode == 'appr'):
            continue
        out.append((PENTE_FORMAT.get((r[0], r[2]), 1.0) if format_atp else 1.0) * r[col])
    return out


def etape_vitesse(M, k, racine):
    base = rejouer(M, k, racine, rapide=True)
    cands = {}
    for v in VITESSES:
        rows = rejouer(M, k, racine, vitesse_f=v)
        cands[f"vitesse × {v:g}"] = {'vitesse': v, 'rows': rows,
                                     '2018–2022': compare(_z(base, 'WTA', 'appr'), _z(rows, 'WTA', 'appr'))}
    PA = [(r[3], r[4]) for r in base if r[0] == 'WTA' and r[1] < COUPURE]
    b = beta_rapide(PA)
    melange = [(r[0], r[1], r[2], r[3] + (b * (r[4] - r[3]) if r[0] == 'WTA' else 0.0), None) for r in base]   # WTA seulement
    cands['Elo rapide'] = {'beta': round(b, 4), 'rows': melange,
                           '2018–2022': compare(_z(base, 'WTA', 'appr'), _z(melange, 'WTA', 'appr'))}
    choix = max(cands, key=lambda n: cands[n]['2018–2022']['gain'])
    C = cands[choix]
    juge = compare(_z(base, 'WTA', 'juge'), _z(C['rows'], 'WTA', 'juge'))
    ok, raisons = passe(C['2018–2022'], juge)
    out = {'candidats_2018_2022': {n: {kk: vv for kk, vv in c.items() if kk != 'rows'} for n, c in cands.items()},
           'forme_choisie': choix, '2023 → juin 2026': juge, 'retenue': ok, 'raisons': raisons,
           'autres_circuits_2023': {c: compare(_z(base, c, 'juge'), _z(C['rows'], c, 'juge')) for c in ('ATP', 'CH')}}
    return out, C, base


def etape_depart(M, k, racine, vitesse_f):
    base = rejouer(M, k, racine, vitesse_f=vitesse_f)
    cands = {}
    for d in DEPARTS:
        rows = rejouer(M, k, racine, vitesse_f=vitesse_f, depart=d)
        A = {c: compare(_z(base, c, 'appr', True), _z(rows, c, 'appr', True)) for c in CIRCUITS}
        cands[d] = {'rows': rows, '2018–2022': A,
                    'note': (A['ATP']['gain'] + A['WTA']['gain']) / 2 if A['CH']['gain'] >= -DEGRADATION_MAX else -1.0}
    choix = max(cands, key=lambda d: cands[d]['note'])
    J = {c: compare(_z(base, c, 'juge', True), _z(cands[choix]['rows'], c, 'juge', True)) for c in CIRCUITS}
    verdicts = {c: passe(cands[choix]['2018–2022'][c], J[c]) for c in ('ATP', 'WTA')}
    degrade = [c for c in CIRCUITS if J[c].get('gain', 0) < -DEGRADATION_MAX]
    ok = any(v[0] for v in verdicts.values()) and not degrade
    raisons = ([f"{c} : {', '.join(v[1])}" for c, v in verdicts.items() if not v[0]] if not any(v[0] for v in verdicts.values()) else []) \
        + ([f"dégrade {', '.join(degrade)} de plus de {DEGRADATION_MAX}"] if degrade else [])
    return {'candidats_2018_2022': {f"{d:g}": {'gains': {c: v['2018–2022'][c]['gain'] for c in CIRCUITS}} for d, v in cands.items()},
            'depart_choisi': choix, '2018–2022': cands[choix]['2018–2022'], '2023 → juin 2026': J,
            'passe_par_circuit': {c: {'passe': v[0], 'raisons': v[1]} for c, v in verdicts.items()},
            'retenu': ok, 'raisons': raisons}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    v1, C, _ = etape_vitesse(M, k, racine)
    print('ÉTAPE 1 —', v1['forme_choisie'], '| 2023 → :', v1['2023 → juin 2026'], '| retenue :', v1['retenue'], v1['raisons'], flush=True)
    vitesse_en_place = C.get('vitesse', 1.0) if (v1['retenue'] and 'vitesse' in C) else 1.0
    v2 = etape_depart(M, k, racine, vitesse_en_place)
    print('ÉTAPE 2 — départ', v2['depart_choisi'], '| 2023 → :', {c: (x['gain'], x['erreur_type']) for c, x in v2['2023 → juin 2026'].items()},
          '| retenu :', v2['retenu'], v2['raisons'])
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("étape 1 : forme de la vitesse WTA choisie sur 2018–2022, jugée une fois sur 2023 → juin 2026 "
                     "(gain ≥ 0,001 sur ≥ 1 000 matchs, ≥ 2 erreurs types, positif sur les deux périodes) ; étape 2 : "
                     "départ des petits niveaux choisi sur 2018–2022, même jugement sur l'ATP ou la WTA, aucun circuit "
                     "dégradé de plus de 0,0005"),
           'elo': "réglé comme la production (elo.de_production), mis à jour après chaque match",
           'vitesse_wta': v1, 'vitesse_wta_en_place_pour_l_etape_2': vitesse_en_place, 'depart_petits_niveaux': v2}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
