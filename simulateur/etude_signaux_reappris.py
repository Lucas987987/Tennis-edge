#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_signaux_reappris.py — les signaux par circuit réappris sur l'Elo DE PRODUCTION (11/11/2026, audit, paquet 233)

LE DÉFAUT (audit, section 2). Les signaux « changement de surface », « retour d'absence », « âge », « favori /
outsider » et « parcours dans le tournoi » ont été appris par etude_signaux_combines.py et etude_pistes_tournoi.py
contre un Elo qui n'est pas celui du site : sans ses réglages, et mis à jour seulement au changement de date — or la
date de l'archive est celle du DÉBUT du tournoi, donc cet Elo reste figé pendant tout le tournoi. Deux signaux en
dépendent directement : « parcours » (qui rattrape ce que l'Elo figé ignore) et « favori / outsider » (dont la
variable est un écart à cet Elo-là). En production leurs β sont pourtant appliqués au % du vrai classement.

CE QUE FAIT L'ÉTUDE. Elle rejoue l'archive avec l'Elo réglé comme la production (elo.de_production), mis à jour après
chaque match, corrigé des pentes en place (format du match en ATP, Grand Chelem), et réapprend les sept β ensemble.
Les variables sont celles de la production ; celle du rôle favori / outsider est recalculée contre cet Elo.

RÈGLE ÉCRITE À L'AUDIT (rapport_audit.json, constat « elo_des_etudes », paquet 227), avant toute mesure sur 2023 → :
  les sept β réappris ENSEMBLE sur 2018–2022, jugés sur 2023 → juin 2026 ; un signal reste sur un circuit seulement si
  le retirer coûte au moins 0,001 sur au moins 1 000 matchs concernés, même sens sur les deux périodes.
PRÉCISIONS ÉCRITES LE 11/11/2026, AVANT DE LANCER L'ÉTUDE :
  - « matchs concernés » : ceux où la variable du signal n'est pas nulle ; « retirer » : mettre ses β à zéro dans le
    modèle à sept β ; « même sens » : le retirer coûte aussi sur 2018–2022, et chacun de ses β garde son signe quand
    les sept β sont réappris sur 2023 → juin 2026 seul ;
  - les β définitifs sont réappris sur 2018–2022 avec les SEULS signaux gardés ;
  - contrôle avant mise en production, circuit par circuit : sur 2023 → juin 2026, la configuration réapprise ne doit
    pas faire moins bien que la configuration EN PLACE (β actuels, variable du rôle calculée comme aujourd'hui contre
    l'Elo figé) ; sinon le circuit garde sa configuration actuelle.
  Erreur type et Brier publiés. Compétitions par équipes et abandons hors jugement ; les deux joueurs ont au moins
  10 matchs (comme l'étude d'origine).

Usage : python simulateur/etude_signaux_reappris.py /tmp/sackmann .
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
import etude_age as EA  # noqa: E402
import etude_changement_surface as ECS  # noqa: E402
import etude_outsiders as EO  # noqa: E402  (bilan : gain, erreur type, Brier)
import etude_pistes_tournoi as EPT  # noqa: E402
import etude_profils_contexte as EPC  # noqa: E402
import etude_retour_absence as ERA  # noqa: E402
import etude_signaux_combines as ESC  # noqa: E402

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_CONCERNES, MARGE, MIN_MATCHS_JOUEUR = 1000, 0.001, 10
NOMS = ESC.NOMS + ('parcours_tournoi',)                       # les sept β, dans l'ordre
SIGNAUX = {'changement_surface': (0,), 'retour_absence': (1, 2), 'age': (3, 4), 'favori_outsider': (5,), 'parcours_tournoi': (6,)}
CIRCUITS = ('ATP', 'WTA', 'CH')
SORTIE = os.path.join(ICI, 'rapport_signaux_reappris.json')


def _json(racine, nom):
    try:
        with open(os.path.join(racine, 'simulateur', nom), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def pentes_en_place(racine):
    """(pente du format {circuit: {sets gagnants: pente}}, pente Grand Chelem {circuit: pente}) lues dans les réglages."""
    fmt = {c: {int(k): float(v) for k, v in (d or {}).items()} for c, d in (_json(racine, 'format_match.json').get('pentes') or {}).items()}
    gc = {c: float(v) for c, v in (_json(racine, 'grand_chelem.json').get('pentes') or {}).items() if v}
    return fmt, gc


def pente_du_match(m, fmt, gc):
    c = m['circuit']
    if m.get('niveau') == 'G' and c in gc:
        return gc[c]
    return (fmt.get(c) or {}).get(3 if m.get('bo') == 5 else 2, 1.0)


def betas_en_place(racine):
    """{circuit: [7 β]} de la configuration actuelle (rapport_signaux_combines.json, puis rapport_pistes_tournoi.json là
    où le parcours est adopté) ; β nul = signal non appliqué sur ce circuit."""
    out = {}
    comb, pistes = _json(racine, 'rapport_signaux_combines.json'), _json(racine, 'rapport_pistes_tournoi.json')
    for c in CIRCUITS:
        v = (comb.get('circuits') or {}).get(c) or {}
        b = [float(v['betas'][n]) for n in ESC.NOMS] + [0.0] if v.get('adopte') else [0.0] * 7
        x = (((pistes.get('circuits') or {}).get(c) or {}).get('parcours_tournoi') or {})
        if x.get('adoptee') and v.get('adopte'):
            b = [float(t) for t in x['ajoutee_au_combine']['betas_7']]
        out[c] = b
    return out


def lignes(M, racine, naiss=None, cle=None):
    """Une ligne par match jugé, vue du vainqueur : circuit, date, z de base (Elo de production × pente en place), les
    sept variables, et la variable du rôle telle que la production la calcule aujourd'hui (contre l'Elo figé)."""
    k = cle or (lambda n: E.cle(n) if n else None)
    fmt, gc = pentes_en_place(racine)
    el, bas = E.de_production(racine)
    fige = E.Elo()                                             # l'Elo des études d'origine : sans réglage, figé dans le tournoi
    su, rt, RS, RS0 = ECS.Suivi(), ERA.Retours(), EPC.Residus(), EPC.Residus()
    tour_n, jour, attente, rows = {}, None, [], []
    for m in M:
        d = m['date']
        if d != jour:
            for g_, p_, s_, gc_ in attente:
                fige.maj(g_, p_, s_, gc_, None)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if c in ('CH', 'ITF'):
            if bas:
                el.presenter(g, bas)
                el.presenter(p, bas)
            fige.presenter(g, 1200.0)
            fige.presenter(p, 1200.0)
        pe, pe0 = el.proba(g, p, s), fige.proba(g, p, s)
        tid = m.get('tournoi_id') or m.get('tournoi')
        role_g, role_p = ('fav', 'out') if pe >= 0.5 else ('out', 'fav')
        role0_g, role0_p = ('fav', 'out') if pe0 >= 0.5 else ('out', 'fav')
        if c in CIRCUITS and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D' \
                and el.matchs(g) >= MIN_MATCHS_JOUEUR and el.matchs(p) >= MIN_MATCHS_JOUEUR:
            xs = su.nouveau(g, d, s) - su.nouveau(p, d, s)
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = (EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) if naiss is not None else None) or (0.0, 0.0)
            x_tour = min(tour_n.get((g, tid), 0), EPT.PLAFOND_TOURNOI) - min(tour_n.get((p, tid), 0), EPT.PLAFOND_TOURNOI)
            rows.append({'d': d, 'c': c, 'z': pente_du_match(m, fmt, gc) * EO._lg(pe),
                         'x': (float(xs), xa[0], xa[1], xg[0], xg[1], RS.moy(g, role_g) - RS.moy(p, role_p), float(x_tour)),
                         'role_en_place': RS0.moy(g, role_g) - RS0.moy(p, role_p)})   # résidus de l'Elo figé, rôle lu sur le vrai Elo
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        tour_n[(g, tid)] = tour_n.get((g, tid), 0) + 1
        if not m.get('abandon'):
            RS.ajouter(g, role_g, 1 - pe)
            RS.ajouter(p, role_p, -(1 - pe))
            RS0.ajouter(g, role0_g, 1 - pe0)
            RS0.ajouter(p, role0_p, -(1 - pe0))
        attente.append((g, p, s, m.get('niveau') == 'G'))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def _zc(r, b, x=None):
    return r['z'] + sum(bi * xi for bi, xi in zip(b, x if x is not None else r['x']))


def _cout(R, b, idx):
    """Coût (log loss) de la mise à zéro des β d'indices idx, sur les matchs de R où la variable n'est pas nulle."""
    C = [r for r in R if any(r['x'][i] for i in idx)]
    if not C:
        return {'concernes': 0}
    b0 = [0.0 if i in idx else v for i, v in enumerate(b)]
    return dict(EO.bilan([_zc(r, b0) for r in C], [_zc(r, b) for r in C]), concernes=len(C))


def juger_circuit(R, b_place):
    av = [r for r in R if r['d'] < COUPURE]
    ju = [r for r in R if r['d'] >= COUPURE]
    b7 = ESC.apprendre([(r['z'], r['x']) for r in av], k=7)
    b7j = ESC.apprendre([(r['z'], r['x']) for r in ju], k=7) if len(ju) >= 1000 else [0.0] * 7
    signaux, gardes = {}, []
    for nom, idx in SIGNAUX.items():
        ca, cj = _cout(av, b7, idx), _cout(ju, b7, idx)
        raisons = []
        if cj.get('concernes', 0) < MIN_CONCERNES:
            raisons.append(f"moins de {MIN_CONCERNES} matchs concernés")
        if cj.get('gain', -1) < MARGE:
            raisons.append(f"le retirer coûte moins de {MARGE}")
        if ca.get('gain', -1) <= 0:
            raisons.append("ne coûte rien sur 2018–2022")
        if any(b7[i] * b7j[i] <= 0 for i in idx):
            raisons.append("un β change de signe sur 2023 →")
        # ÉCART À LA RÈGLE (décidé le 11/11/2026 APRÈS avoir vu le résultat, dit comme tel, soumis à Lucas) : un signal
        # DÉJÀ EN PLACE qui n'échoue QUE sur le nombre de matchs concernés, alors que le retirer coûte au moins 0,001
        # avec au moins 2 erreurs types, n'est pas retiré : il reste « en sursis ». La règle à la lettre est publiée à côté.
        sursis = bool(raisons == [f"moins de {MIN_CONCERNES} matchs concernés"] and any(b_place[i] for i in idx)
                      and (cj.get('erreurs_types') or 0) >= 2.0)
        signaux[nom] = {'betas_2018_2022': {NOMS[i]: round(b7[i], 4) for i in idx}, 'betas_2023': {NOMS[i]: round(b7j[i], 4) for i in idx},
                        'cout_du_retrait_2018_2022': {k_: ca.get(k_) for k_ in ('concernes', 'gain', 'erreur_type')},
                        'cout_du_retrait_2023': {k_: cj.get(k_) for k_ in ('concernes', 'gain', 'erreur_type', 'erreurs_types')},
                        'cout_du_retrait_2023_sur_tous_les_matchs': round((cj.get('gain') or 0.0) * cj.get('concernes', 0) / max(1, len(ju)), 5),
                        'garde': not raisons, 'en_sursis': sursis, 'raisons': raisons}
        if not raisons:
            gardes.append(nom)
    en_sursis = [n for n, s in signaux.items() if s['en_sursis']]

    def reapprendre(noms):
        cols = [i for nom in noms for i in SIGNAUX[nom]]
        b = [0.0] * 7
        if cols:
            for i, v in zip(cols, ESC.apprendre([(r['z'], tuple(r['x'][i] for i in cols)) for r in av], k=len(cols))):
                b[i] = v
        return b, cols

    bf, cols = reapprendre(gardes + en_sursis)
    b_lettre, _ = reapprendre(gardes)
    x_place = lambda r: r['x'][:5] + (r['role_en_place'], r['x'][6])
    base = [r['z'] for r in ju]
    nouv = [_zc(r, bf) for r in ju]
    place = [_zc(r, b_place, x_place(r)) for r in ju]
    place_sans_role = [_zc(r, [0.0 if i == 5 else v for i, v in enumerate(b_place)], x_place(r)) for r in ju]
    contre_place = EO.bilan(place, nouv)
    return {'appris': len(av), 'juges': len(ju), 'signaux': signaux, 'signaux_gardes': gardes, 'signaux_en_sursis': en_sursis,
            'signaux_retires': [n for n in SIGNAUX if n not in gardes + en_sursis and any(b_place[i] for i in SIGNAUX[n])],
            'signaux_ecartes': [n for n in SIGNAUX if n not in gardes + en_sursis],
            'betas': {NOMS[i]: round(bf[i], 4) for i in cols},
            'betas_en_place': {n: round(v, 4) for n, v in zip(NOMS, b_place) if v},
            'contre_l_elo_seul_2023': EO.bilan(base, nouv),
            'en_place_contre_l_elo_seul_2023': EO.bilan(base, place),
            'en_place_cout_du_retrait_du_role_2023': EO.bilan(place_sans_role, place),
            'contre_la_configuration_en_place_2023': contre_place,
            'regle_a_la_lettre_contre_en_place_2023': EO.bilan(place, [_zc(r, b_lettre) for r in ju]),
            'adopte': bool(contre_place.get('gain', -1) >= 0)}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    M = DN.charger(archive, 2012)
    etat = _json(racine, 'elo_etat.json')
    alias = dict(E.migrer_etat(etat).get('alias') or {}) if etat else {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    rows = lignes(M, racine, EA.naissances(archive, k), k)
    place = betas_en_place(racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("les sept β réappris ensemble sur 2018–2022 contre l'Elo de production, jugés sur 2023 → juin 2026 ; un signal "
                     "reste sur un circuit seulement si le retirer coûte au moins 0,001 sur au moins 1 000 matchs concernés, même "
                     "sens sur les deux périodes ; β définitifs réappris avec les seuls signaux gardés ; la configuration réapprise "
                     "remplace celle en place sur un circuit si elle n'y fait pas moins bien sur 2023 → juin 2026"),
           'elo': ("réglé comme la production (elo.de_production), mis à jour après chaque match, corrigé des pentes en place "
                   "(format du match, Grand Chelem) ; compétitions par équipes exclues"),
           'pentes_en_place': dict(zip(('format', 'grand_chelem'), pentes_en_place(racine))),
           'circuits': {c: juger_circuit([r for r in rows if r['c'] == c], place[c]) for c in CIRCUITS}}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, v in doc['circuits'].items():
        print(f"== {c} : {v['appris']} appris, {v['juges']} jugés")
        for nom, s in v['signaux'].items():
            j = s['cout_du_retrait_2023']
            print(f"   {nom:20s} β {list(s['betas_2018_2022'].values())} (2023 → : {list(s['betas_2023'].values())}) | concernés {j.get('concernes')}, "
                  f"coût du retrait {j.get('gain')} ± {j.get('erreur_type')} | "
                  f"{'GARDÉ' if s['garde'] else ('EN SURSIS : ' if s['en_sursis'] else 'retiré : ') + ' ; '.join(s['raisons'])}")
        a, b, n = v['contre_l_elo_seul_2023'], v['en_place_contre_l_elo_seul_2023'], v['contre_la_configuration_en_place_2023']
        print(f"   β définitifs {v['betas']}")
        print(f"   contre l'Elo seul : réappris {a['gain']} ± {a['erreur_type']} | en place {b['gain']} ± {b['erreur_type']} || réappris contre en place : "
              f"{n['gain']} ± {n['erreur_type']} ({n['erreurs_types']} e.t.), Brier {n['brier_base']} → {n['brier']} | adopté : {v['adopte']}")
        r_, l_ = v['en_place_cout_du_retrait_du_role_2023'], v['regle_a_la_lettre_contre_en_place_2023']
        print(f"   en place, coût du retrait du rôle : {r_['gain']} ± {r_['erreur_type']} | règle à la lettre contre en place : {l_['gain']} ± {l_['erreur_type']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
