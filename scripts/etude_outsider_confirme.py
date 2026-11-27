#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_outsider_confirme.py — L'OUTSIDER QUI A GAGNÉ AU TOUR PRÉCÉDENT, ET QUI EST ENCORE OUTSIDER, GAGNE-T-IL PLUS
SOUVENT QUE SON % ? (27/11/2026, paquet 522, Lucas : « il faut que l'on analyse si l'outsider gagne son match du tour
précédent et qu'il est à nouveau outsider, gagne-t-il plus souvent ? » — « les trois » : tennis, tennis de table,
badminton). LECTURE SEULE : aucune cote, rien ne change dans l'algo ; un rapport de comptes et de moyennes, sans nom.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI :
  Le % de l'algo avant chaque match, rejoué dans l'ordre (chaque match est prédit avant que son résultat ne mette les
  notes à jour) :
    tennis           Elo du site (simulateur/elo.py, réglages FiveThirtyEight, surface 50/50, K × 1,1 en Grand
                     Chelem), sur NOS données tennis-data (historique/tennis_data.csv.gz : ATP et WTA, 2010 →
                     14/01/2026 ; le seul fichier qui donne le tournoi) ; matchs d'un même jour prédits ensemble ;
    tennis de table  Elo E2 de l'étude 487 (réglage lu dans tennis_de_table/rapport_elo_tt.json), historique collecté ;
    badminton        Elo retenu aux étapes 3 et 4 (a = 400, c = 0,3, w = 1, s = 32, doubles au joueur).
  CAS : un joueur (une paire en double) est l'OUTSIDER de l'algo (% < 50) d'un match M ; son match précédent était dans le
    MÊME tournoi (même nom), au plus FENETRE jours avant (tennis 10, tennis de table 3, badminton 7), il y était aussi
    outsider (% < 50) et il l'a GAGNÉ. Question : gagne-t-il M plus souvent que son % ?
  Périodes (celles de chaque sport) :
    tennis           mise en route 2010–2017 (non jugée), APPRENTISSAGE 2018–2022, JUGEMENT 2023 → 14/01/2026 ;
    tennis de table  mise en route 120 jours, APPRENTISSAGE → 30/09/2025, JUGEMENT 01/10/2025 → fin ;
    badminton        mise en route 120 jours, APPRENTISSAGE → 31/12/2022, JUGEMENT 01/01/2023 → fin.
  Mesure : un décalage β appris sur l'apprentissage : logit p' = logit p + β (p = % de l'outsider). RETENU pour un
    groupe (circuit, ligue ou épreuve) si, sur au moins 1 000 cas jugés, β fait gagner au moins 0,001 de log loss par
    cas sur le jugement ET si β appris sur le jugement a le même signe (même sens sur les deux périodes). Moins de
    1 000 cas jugés : « trop peu de cas » (rien n'est conclu). Groupe par groupe (tennis : ATP, WTA ; tennis de table :
    International, Pologne ; badminton : les 5 épreuves), puis tout le sport.
  Publiés sans décider : victoires réelles contre % annoncé des cas (par période), et deux témoins — l'outsider qui a
    gagné au tour précédent comme FAVORI, et tous les outsiders — pour voir si l'écart est propre à l'outsider confirmé.
Rapport : rapport_outsider_confirme.json (racine du dépôt).
Usage : python scripts/etude_outsider_confirme.py [racine] [tennis,tt,badminton]
"""
import csv
import datetime as dt
import glob
import gzip
import io
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
MARGE, MIN_CAS = 0.001, 1000
FENETRE_J = {'tennis': 10, 'tt': 3, 'badminton': 7}
GRAND_CHELEM = ('australian open', 'french open', 'roland garros', 'wimbledon', 'us open')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


# ------------------------------------------------------------------ les cas, quel que soit le sport
def cas(matchs, fenetre_j):
    """matchs : [(t, jour, groupe, periode, tournoi, ent_h, ent_a, y, p_h)] dans l'ordre, p_h = % de l'algo AVANT le
    match. Renvoie {'confirme': [...], 'apres_favori': [...], 'outsiders': [...]}, chaque élément (groupe, période,
    p_outsider, gagné). Le match précédent d'un joueur est cherché AVANT ce match (son résultat est connu)."""
    dernier = {}                       # entité → (t, tournoi, gagné, était outsider)
    out = {'confirme': [], 'apres_favori': [], 'outsiders': []}
    for t, jour, g, per, tournoi, eh, ea, y, ph in matchs:
        for e, p, gagne in ((eh, ph, y == 1), (ea, 1 - ph, y == 0)):
            if per and p < 0.5:
                out['outsiders'].append((g, per, p, gagne))
                d = dernier.get(e)
                if d and d[1] == tournoi and 0 <= t - d[0] <= fenetre_j * 86400 and d[2]:
                    out['confirme' if d[3] else 'apres_favori'].append((g, per, p, gagne))
        dernier[eh] = (t, tournoi, y == 1, ph < 0.5)
        dernier[ea] = (t, tournoi, y == 0, ph > 0.5)
    return out


def ll(C, beta=0.0):
    return sum(-math.log(_sg(_lg(p) + beta)) if w else -math.log(1 - _sg(_lg(p) + beta)) for p, w in C) / len(C)


def beta_mv(C, iters=30):
    """Décalage β du logit qui maximise la vraisemblance (Newton)."""
    b = 0.0
    for _ in range(iters):
        g = h = 0.0
        for p, w in C:
            q = _sg(_lg(p) + b)
            g += w - q
            h -= q * (1 - q)
        if h == 0:
            break
        pas = g / h
        b -= pas
        if abs(pas) < 1e-9:
            break
    return b


def decrire(C):
    if not C:
        return {'cas': 0}
    return {'cas': len(C), 'gagnes_pct': round(100 * sum(w for _, w in C) / len(C), 1),
            'annonce_pct': round(100 * sum(p for p, _ in C) / len(C), 1)}


def juger(L):
    """L : [(période, p, gagné)] d'un groupe → verdict selon la règle."""
    A = [(p, w) for per, p, w in L if per == 'A']
    B = [(p, w) for per, p, w in L if per == 'B']
    d = {'apprentissage': decrire(A), 'jugement': decrire(B)}
    if len(A) < 30 or not B:
        d['verdict'] = 'trop_peu_de_cas'
        return d
    bA = beta_mv(A)
    gain = ll(B) - ll(B, bA)
    bB = beta_mv(B) if len(B) >= 30 else None
    d.update(beta_appris=round(bA, 4), gain_juge_par_cas=round(gain, 5),
             beta_jugement=None if bB is None else round(bB, 4))
    if len(B) < MIN_CAS:
        d['verdict'] = 'trop_peu_de_cas'
    else:
        d['verdict'] = 'retenu' if gain >= MARGE and bB is not None and (bA > 0) == (bB > 0) else 'non_retenu'
    return d


def resumer(out, groupes):
    rep = {}
    for nom, L in out.items():
        par = {}
        for g in list(groupes) + ['tout']:
            G = [(per, p, w) for gg, per, p, w in L if g == 'tout' or gg == g]
            par[g] = juger(G) if nom == 'confirme' else {'apprentissage': decrire([(p, w) for per, p, w in G if per == 'A']),
                                                         'jugement': decrire([(p, w) for per, p, w in G if per == 'B'])}
        rep[nom] = par
    return rep


# ------------------------------------------------------------------ tennis (nos données tennis-data)
def matchs_tennis(racine):
    sys.path.insert(0, os.path.join(racine, 'simulateur'))
    import elo as E
    with gzip.open(os.path.join(racine, 'historique', 'tennis_data.csv.gz'), 'rt', encoding='utf-8') as f:
        R = list(csv.DictReader(f))
    R.sort(key=lambda r: r['date'])
    elo, out = {c: E.Elo() for c in ('ATP', 'WTA')}, []
    i = 0
    while i < len(R):
        j = i
        while j < len(R) and R[j]['date'] == R[i]['date']:
            j += 1
        jour = R[i]['date']
        an = int(jour[:4])
        per = None if an < 2018 else ('A' if an <= 2022 else 'B')
        t = int(dt.datetime.fromisoformat(jour).replace(tzinfo=dt.timezone.utc).timestamp())
        bloc = []
        for r in R[i:j]:
            c = r['circuit'] if r['circuit'] in elo else None
            if not c or not r['vainqueur'] or not r['perdant']:
                continue
            w, l = E.cle(r['vainqueur']), E.cle(r['perdant'])
            if w == l:
                continue
            sf = r.get('surface')
            p_w = elo[c].proba(w, l, sf)
            # h = l'ordre alphabétique des clés (aucun avantage au vainqueur) ; y = 1 si h gagne
            h, a, y, ph = (w, l, 1, p_w) if w < l else (l, w, 0, 1 - p_w)
            out.append((t, jour, c, per, (c, r['tournoi']), (c, h), (c, a), y, ph))
            bloc.append((c, w, l, sf, any(g in str(r['tournoi']).lower() for g in GRAND_CHELEM)))
        for c, w, l, sf, gc in bloc:                      # les résultats du jour, après les pronostics du jour
            elo[c].maj(w, l, sf, gc)
        i = j
    return out, ('ATP', 'WTA')


# ------------------------------------------------------------------ tennis de table
def matchs_tt(racine):
    sys.path.insert(0, os.path.join(racine, 'tennis_de_table'))
    import elo_tt as ET
    reg = (((json.load(open(os.path.join(racine, 'tennis_de_table', 'rapport_elo_tt.json'), encoding='utf-8'))
             .get('reglages_appris') or {}).get('E2') or {}).get('reglage')) or [400, 0.6, 0.5, 20]
    L = []
    for p in sorted(glob.glob(os.path.join(racine, ET.DOSSIER, '20*', '20*.jsonl.gz'))):
        jour = os.path.basename(p)[:10]
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for l in f:
                if not l.strip():
                    continue
                r = json.loads(l)
                m = ET.match_de(r, jour)
                if m:                                       # l'Elo est rejoué sur TOUT l'historique (comme le produit)
                    L.append((m, str(r.get('tournoi') or '')))
    L.sort(key=lambda x: (x[0][0], x[0][3], x[0][4]))
    M = [m for m, _ in L]
    P = ET.rejouer(M, a=reg[0], c=reg[1], w=reg[2], s=reg[3])
    debut = dt.date.fromisoformat(M[0][1]) + dt.timedelta(days=120)
    out = []
    for (m, tournoi), p in zip(L, P):
        d = dt.date.fromisoformat(m[1])
        per = None if d < debut or m[2] not in ('International', 'Poland') else ('A' if d < dt.date(2025, 10, 1) else 'B')
        out.append((m[0], m[1], m[2], per, (m[2], tournoi), m[3], m[4], m[5], p))
    return out, ('International', 'Poland')


# ------------------------------------------------------------------ badminton
def matchs_badminton(racine):
    sys.path.insert(0, os.path.join(racine, 'badminton'))
    import elo_badminton as EB
    import etude_etape4_badminton as S4
    L = []
    for p in sorted(glob.glob(os.path.join(racine, EB.DOSSIER, '20*', '20*.jsonl.gz'))):
        jour = os.path.basename(p)[:10]
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for l in f:
                if l.strip():
                    r = json.loads(l)
                    m, _ = EB.ligne_lue(r, jour)
                    if m and m['id'] is not None:
                        L.append((m['id'], str(r.get('tournoi') or '')))
    tournoi = dict(L)
    M, _ = EB.lire(racine)
    # EB.lire ne garde pas l'identifiant du match : on le retrouve par (t, camps)
    ids = {}
    for p in sorted(glob.glob(os.path.join(racine, EB.DOSSIER, '20*', '20*.jsonl.gz'))):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for l in f:
                if l.strip():
                    r = json.loads(l)
                    ids.setdefault((int(r.get('t') or 0), (r.get('h') or [None])[0], (r.get('a') or [None])[0]), r.get('id'))
    P = S4.rejouer(M, *S4.DEPART_REGLAGE)
    debut = dt.date.fromisoformat(M[0][1]) + dt.timedelta(days=120)
    out = []
    for m, p in zip(M, P):
        d = dt.date.fromisoformat(m[1])
        per = None if d < debut else ('A' if d < dt.date(2023, 1, 1) else 'B')
        tn = tournoi.get(ids.get((m[0], m[3], m[4])), '')
        out.append((m[0], m[1], m[2], per, tn, m[3], m[4], m[5], p))
    return out, tuple(EB.EPREUVES)


SPORTS = {'tennis': matchs_tennis, 'tt': matchs_tt, 'badminton': matchs_badminton}


def etudier(racine, sports=('tennis', 'tt', 'badminton'), journal=print):
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'regle_ecrite_le': '2026-11-27',
           'etude': 'outsider_confirme', 'sports': {}}
    for sp in sports:
        try:
            M, groupes = SPORTS[sp](racine)
        except (OSError, ValueError, ImportError) as e:
            journal(f'{sp} : données indisponibles ({type(e).__name__})')
            continue
        out = cas(M, FENETRE_J[sp])
        r = resumer(out, groupes)
        r['matchs'] = len(M)
        rep['sports'][sp] = r
        journal(f'{sp} : {len(M)} matchs')
        for g, d in r['confirme'].items():
            a, b = d['apprentissage'], d['jugement']
            journal(f"  outsider confirmé · {g} : apprentissage {a.get('cas', 0)} cas ({a.get('gagnes_pct', '—')} % gagnés, "
                    f"annoncé {a.get('annonce_pct', '—')} %) ; jugement {b.get('cas', 0)} cas ({b.get('gagnes_pct', '—')} % gagnés, "
                    f"annoncé {b.get('annonce_pct', '—')} %) ; β {d.get('beta_appris')} / {d.get('beta_jugement')}, "
                    f"gain {d.get('gain_juge_par_cas')} → {d['verdict']}")
        for nom in ('apres_favori', 'outsiders'):
            for g, d in r[nom].items():
                b = d['jugement']
                journal(f"  témoin {nom} · {g} : jugement {b.get('cas', 0)} cas, {b.get('gagnes_pct', '—')} % gagnés, "
                        f"annoncé {b.get('annonce_pct', '—')} %")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    sports = tuple(argv[2].split(',')) if len(argv) > 2 else ('tennis', 'tt', 'badminton')
    rep = etudier(racine, sports)
    with open(os.path.join(racine, 'rapport_outsider_confirme.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
