#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_a_ou_b.py — JOUER A OU B, NIVEAU DE FIABILITÉ PAR NIVEAU, ET L'ANATOMIE DE NOS DÉFAITES (18/11/2026, paquet 268,
demande de Lucas : « analyser les réussites et les échecs, éviter certaines défaites, voir si jouer A ou B est le plus
intéressant selon fragile, prudent, correct, solide »).

A = le joueur que l'algo donne gagnant au PREMIER pronostic (le moment où Lucas peut décider, 29/10/2026) ;
B = l'autre joueur. Niveau de fiabilité = celui figé avant le match dans nos fiches (fragile, prudent, correct, solide).
Échantillon : nos pronostics EN DIRECT jugés (Tennis_Edge_Lab/live/pronostics_resultats.json), ATP, WTA, Challenger ;
exclus ITF, abandons et forfaits, matchs sans niveau. Chaque circuit est jugé à part.

PARTIE PRIVÉE (Telegram privé seulement, jamais écrite dans le dépôt public) — la CLV, seule validation des paris :
  cote prise = dernière cote Pinnacle relevée au plus tard au premier pronostic ; à défaut, la première relevée dans les
  6 heures qui suivent (et avant le match) ; sinon le match est exclu. Clôture = celle de roi_algo.clotures (dernière
  cote Pinnacle avant le début, capture fiable). Cote juste de clôture = clôture sans marge (méthode proportionnelle).
  CLV d'un côté = cote prise / cote juste de clôture − 1. Calculée pour A et pour B, dans chaque case niveau × circuit.

RÈGLE FIXÉE AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup) :
  — moins de 30 matchs dans une case : « trop tôt », rien n'est conclu ;
  — sinon, intervalle à 95 % (bootstrap, 2 000 tirages, graine 7) de la CLV moyenne : « A positif » si la borne basse
    de A est > 0 ; « B positif » si la borne basse de B est > 0 ; « négatif » si les bornes hautes de A et de B sont
    toutes deux < 0 ; « indécis » sinon ;
  — un côté positif n'est « CONFIRMÉ » que si la CLV moyenne de ce côté est aussi > 0 sur chacune des deux moitiés
    chronologiques de la case (au moins 15 matchs par moitié). Rien n'est appliqué automatiquement : la décision de
    jouer reste à Lucas, et elle se retire si la case repasse en « indécis » ou « négatif ».

PARTIE PUBLIQUE (simulateur/rapport_anatomie_defaites.json : aucun nom, aucune cote) — l'anatomie de nos défaites :
  pour chaque critère connu AVANT le match (niveau, tranche du % annoncé, Elo et simulation en désaccord, écart Elo /
  simulation ≥ 10 points, joueur à moins de 30 ou 60 matchs, matchs similaires plus pessimistes que nous d'au moins
  3 points, score instable, surface), réussite réelle de A contre réussite annoncée (moyenne du % de A).
  RÈGLE (fixée avant) : un critère est « à étudier sur l'archive » si, avec au moins 30 matchs sur chacune des deux
  moitiés chronologiques, A y réussit moins que prévu de plus de 1,96 erreur type sur les DEUX moitiés. Ce n'est pas un
  filtre : un critère ne sert à éviter une défaite qu'après la règle de l'archive (apprendre 2018–2022, juger
  2023 → juin 2026, log loss ≥ 0,001 sur ≥ 1 000 cas, même sens, circuit par circuit). Descriptif : le % ne change pas.
Usage : python simulateur/etude_a_ou_b.py [racine] [--telegram]
"""
import datetime as dt
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
NIVEAUX = ('fragile', 'prudent', 'correct', 'solide')
CIRCUITS = ('ATP', 'WTA', 'CH')
LIB = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger', 'tous': 'tous circuits'}
N_MIN, N_MOITIE, N_MOITIE_ANAT = 30, 15, 30
DELAI_PRISE_H = 6
Z = 1.96


def _ts(s):
    try:
        d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=None) if d.tzinfo is None else d.astimezone(dt.timezone.utc).replace(tzinfo=None)


def _p_home(m):
    """% de home au PREMIER pronostic (combinaison, sinon simulation, sinon stats)."""
    for k in ('combinaison', 'simulation', 'stats'):
        v = (m.get('premier') or {}).get(k)
        if isinstance(v, dict) and v.get('p_home') is not None:
            return float(v['p_home'])
    return None


def matchs(racine):
    """Matchs jugés du direct : dicts {uid, circuit, niveau, p_a, a (0 home / 1 away), a_gagne, decision, debut, m}."""
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            R = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for m in R.get('matchs') or []:
        reel, f = m.get('reel') or {}, m.get('fiabilite') or {}
        niveau = f.get('niveau') if isinstance(f, dict) else None
        if m.get('circuit') not in CIRCUITS or niveau not in NIVEAUX:
            continue
        if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        p = _p_home(m)
        if p is None:
            continue
        a = 0 if p >= 0.5 else 1
        out.append({'uid': m['uid'], 'circuit': m['circuit'], 'niveau': niveau, 'p_a': max(p, 1 - p), 'a': a,
                    'a_gagne': (reel['gagnant'] == 'home') == (a == 0), 'decision': _ts(m.get('pronostique_le')),
                    'debut': _ts(m.get('debut')), 'm': m})
    out.sort(key=lambda x: (x['decision'] or dt.datetime.min, x['uid']))
    return out


# ── partie privée : cotes ───────────────────────────────────────────────────────────────────────────────────────────
def historiques(racine):
    """{clé AAAA-MM-JJ_home_away: (inverse?, entrée closing_store)} dans les deux sens."""
    sys.path.insert(0, os.path.join(racine, 'scripts'))
    import closing_store as CS
    import nos_resultats as NR
    cwd = os.getcwd()
    try:
        os.chdir(racine)
        d = CS.load_all(max_age_days=None)
    finally:
        os.chdir(cwd)
    out = {}
    for e in d.values():
        debut = _ts(e.get('commence_time'))
        if not debut or not e.get('home') or not e.get('away'):
            continue
        a, b = NR.slug(e['home']), NR.slug(e['away'])
        out[f"{debut.date()}_{a}_{b}"] = (False, e)
        out.setdefault(f"{debut.date()}_{b}_{a}", (True, e))
    return out


def _cherche(H, uid):
    if uid in H:
        return H[uid]
    try:
        j = dt.date.fromisoformat(uid[:10])
    except ValueError:
        return None
    for d in (-1, 1):
        k = f"{j + dt.timedelta(days=d)}_{uid[11:]}"
        if k in H:
            return H[k]
    return None


def prise(e, decision, debut):
    """(cote home, cote away, 'exacte' | 'dans_6h') de l'entrée closing_store, ou None."""
    if decision is None:
        return None
    L = []
    for h in e.get('history') or []:
        t = _ts(h.get('t'))
        try:
            ch, ca = float(h['home']), float(h['away'])
        except (KeyError, TypeError, ValueError):
            continue
        if t and ch > 1 and ca > 1 and (debut is None or t < debut):
            L.append((t, ch, ca))
    if not L:
        return None
    avant = [x for x in L if x[0] <= decision]
    if avant:
        x = max(avant)
        return x[1], x[2], 'exacte'
    apres = [x for x in L if x[0] <= decision + dt.timedelta(hours=DELAI_PRISE_H)]
    if apres:
        x = min(apres)
        return x[1], x[2], 'dans_6h'
    return None


def clv_cases(racine, M=None):
    """[{circuit, niveau, clv_a, clv_b, gain_a, gain_b, prise}] — un par match retenu, ordre chronologique."""
    import roi_algo as RA
    M = matchs(racine) if M is None else M
    C, H = RA.clotures(racine), historiques(racine)
    out, exclus = [], {'sans_cloture': 0, 'sans_cote_prise': 0}
    for x in M:
        c = RA._cote(C, x['uid'], None)
        if not c:
            exclus['sans_cloture'] += 1
            continue
        h = _cherche(H, x['uid'])
        pr = prise(h[1], x['decision'], x['debut']) if h else None
        if not pr:
            exclus['sans_cote_prise'] += 1
            continue
        ph, pa, mode = pr
        if h[0]:
            ph, pa = pa, ph
        ch, ca = c
        juste_h = 1 / ((1 / ch) / (1 / ch + 1 / ca))
        juste_a = 1 / ((1 / ca) / (1 / ch + 1 / ca))
        prA, prB = (ph, pa) if x['a'] == 0 else (pa, ph)
        jA, jB = (juste_h, juste_a) if x['a'] == 0 else (juste_a, juste_h)
        out.append({'circuit': x['circuit'], 'niveau': x['niveau'], 'clv_a': prA / jA - 1, 'clv_b': prB / jB - 1,
                    'gain_a': prA - 1 if x['a_gagne'] else -1.0, 'gain_b': -1.0 if x['a_gagne'] else prB - 1,
                    'prise': mode})
    return out, exclus


def _ic(v, n_boot=2000, graine=7):
    rnd = random.Random(graine)
    m = sorted(sum(rnd.choice(v) for _ in v) / len(v) for _ in range(n_boot))
    return m[int(.025 * n_boot)], m[int(.975 * n_boot)]


def verdict_case(L):
    """Règle de l'en-tête appliquée à une case (liste chronologique)."""
    n = len(L)
    r = {'n': n, 'prise_exacte': sum(x['prise'] == 'exacte' for x in L)}
    if n == 0:
        return dict(r, verdict='trop tot')
    for c in ('a', 'b'):
        v = [x['clv_' + c] for x in L]
        r['clv_' + c] = round(100 * sum(v) / n, 2)
        g = [x['gain_' + c] for x in L]
        r['roi_' + c] = round(100 * sum(g) / n, 1)
    if n < N_MIN:
        return dict(r, verdict='trop tot')
    ics = {c: _ic([x['clv_' + c] for x in L]) for c in ('a', 'b')}
    for c in ('a', 'b'):
        r['ic_' + c] = [round(100 * ics[c][0], 2), round(100 * ics[c][1], 2)]
    if ics['a'][0] > 0:
        v, cote = 'A positif', 'a'
    elif ics['b'][0] > 0:
        v, cote = 'B positif', 'b'
    elif ics['a'][1] < 0 and ics['b'][1] < 0:
        v, cote = 'négatif', None
    else:
        v, cote = 'indécis', None
    if cote:
        m1, m2 = L[:n // 2], L[n // 2:]
        ok = len(m1) >= N_MOITIE and len(m2) >= N_MOITIE and all(sum(x['clv_' + cote] for x in h) > 0 for h in (m1, m2))
        v += ' — CONFIRMÉ' if ok else ' — à confirmer'
    return dict(r, verdict=v)


def prive(racine, M=None):
    L, exclus = clv_cases(racine, M)
    cases = {}
    for c in CIRCUITS + ('tous',):
        for nv in NIVEAUX + ('tous',):
            X = [x for x in L if (c == 'tous' or x['circuit'] == c) and (nv == 'tous' or x['niveau'] == nv)]
            cases[f'{c}|{nv}'] = verdict_case(X)
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs': len(L),
            'exclus': exclus, 'cases': cases}


# ── partie publique : anatomie des défaites (aucune cote) ───────────────────────────────────────────────────────────
def criteres(x):
    m, f = x['m'], x['m'].get('fiabilite') or {}
    p = x['p_a']
    out = {'niveau : ' + x['niveau']: True,
           'tranche : ' + ('moins de 58 %' if p < .58 else '58–70 %' if p < .70 else '70–80 %' if p < .80 else '80 % et plus'): True}
    pe = ((m.get('premier') or {}).get('stats') or {}).get('p_home')
    ps = ((m.get('premier') or {}).get('simulation') or {}).get('p_home')
    if pe is not None and ps is not None:
        out['Elo et simulation en désaccord sur le vainqueur'] = (pe >= .5) != (ps >= .5)
        out['écart Elo / simulation ≥ 10 points'] = abs(pe - ps) >= .10
    mj = m.get('matchs_joues')
    if isinstance(mj, (list, tuple)) and len(mj) == 2 and all(isinstance(v, (int, float)) for v in mj):
        out['un joueur à moins de 30 matchs'] = min(mj) < 30
        out['un joueur à moins de 60 matchs'] = min(mj) < 60
    ms = f.get('matchs_similaires') or {}
    if ms.get('ecart_reel_moins_prevu') is not None:
        e = float(ms['ecart_reel_moins_prevu'])
        e_a = e if x['a'] == 0 else -e
        out['matchs similaires plus pessimistes pour A (≥ 3 points)'] = e_a <= -0.03
    if f.get('stabilite_score_modal'):
        out['score instable'] = f.get('stabilite_score_modal') == 'fragile'
    if m.get('surface'):
        out['surface : ' + str(m['surface'])] = True
    return {k: v for k, v in out.items() if v}


def _groupe(X):
    n = len(X)
    if not n:
        return None
    reel, prevu = sum(x['a_gagne'] for x in X) / n, sum(x['p_a'] for x in X) / n
    et = math.sqrt(sum(x['p_a'] * (1 - x['p_a']) for x in X)) / n
    return {'n': n, 'reussite_reelle_pct': round(100 * reel, 1), 'reussite_annoncee_pct': round(100 * prevu, 1),
            'ecart_pts': round(100 * (reel - prevu), 1), 'sous_prevu': reel - prevu < -Z * et}


def anatomie(M):
    out = {}
    for c in CIRCUITS + ('tous',):
        X = [x for x in M if c == 'tous' or x['circuit'] == c]
        if not X:
            continue
        K = {}
        for x in X:
            for k in criteres(x):
                K.setdefault(k, []).append(x)
        r = {'ensemble': _groupe(X), 'criteres': {}}
        for k, G in sorted(K.items()):
            g = _groupe(G)
            m1, m2 = G[:len(G) // 2], G[len(G) // 2:]
            h1, h2 = _groupe(m1), _groupe(m2)
            a_etudier = bool(h1 and h2 and h1['n'] >= N_MOITIE_ANAT and h2['n'] >= N_MOITIE_ANAT and h1['sous_prevu'] and h2['sous_prevu'])
            g.pop('sous_prevu')
            g['moities_ecart_pts'] = [h1['ecart_pts'] if h1 else None, h2['ecart_pts'] if h2 else None]
            g['verdict'] = 'à étudier sur l\'archive' if a_etudier else ('trop tôt' if len(G) < 2 * N_MOITIE_ANAT else 'rien à signaler')
            r['criteres'][k] = g
        r['ensemble'].pop('sous_prevu')
        out[c] = r
    return out


def _nettoie(d):
    if isinstance(d, dict):
        return {k: _nettoie(v) for k, v in d.items() if k != 'sous_prevu'}
    return d


def public(racine, M=None):
    M = matchs(racine) if M is None else M
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 268,
            'definition': 'A = joueur donné gagnant par l\'algo au premier pronostic ; critères connus avant le match',
            'regle': __doc__.split('RÈGLE (fixée avant) :')[1].split('Usage')[0].replace('\n', ' ').strip(),
            'descriptif': 'le % de victoire ne change pas', 'matchs': len(M),
            'par_niveau': {c: {nv: _nettoie(_groupe([x for x in M if (c == 'tous' or x['circuit'] == c) and x['niveau'] == nv])
                               ) for nv in NIVEAUX} for c in CIRCUITS + ('tous',)},
            'anatomie': anatomie(M)}




def message(P, A):
    L = ['🔒 A ou B par niveau de fiabilité (CLV au premier pronostic, Pinnacle)', f"{P['matchs']} matchs retenus · exclus : "
         f"{P['exclus']['sans_cloture']} sans clôture, {P['exclus']['sans_cote_prise']} sans cote au moment du pronostic", '']
    for c in CIRCUITS + ('tous',):
        L.append(f"— {LIB[c]}")
        for nv in NIVEAUX + ('tous',):
            r = P['cases'][f'{c}|{nv}']
            if not r['n']:
                continue
            L.append(f"  {nv} : n={r['n']} · CLV A {r['clv_a']:+.2f} % / B {r['clv_b']:+.2f} % · {r['verdict']}")
    sig = [(c, k) for c, r in A['anatomie'].items() for k, g in r['criteres'].items() if g['verdict'].startswith('à étudier')]
    L += ['', 'Défaites — critères à étudier sur l\'archive : ' + (', '.join(f'{k} ({LIB[c]})' for c, k in sig) if sig else 'aucun')]
    L.append('Règle : rien sous 30 matchs ; positif = IC 95 % au-dessus de 0 ; confirmé = positif sur les deux moitiés.')
    return '\n'.join(L)


def envoyer(texte):
    import urllib.request
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        print('Telegram non configuré : message non envoyé')
        return
    data = json.dumps({'chat_id': chat, 'text': texte[:4000]}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendMessage', data=data,
                                 headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=30).read()


def main(argv):
    racine = next((a for a in argv if not a.startswith('--')), os.path.join(ICI, '..'))
    M = matchs(racine)
    A = public(racine, M)
    with open(os.path.join(racine, 'simulateur', 'rapport_anatomie_defaites.json'), 'w', encoding='utf-8') as f:
        json.dump(A, f, ensure_ascii=False, indent=1)
    P = prive(racine, M)                                   # jamais écrit dans le dépôt
    texte = message(P, A)
    if '--telegram' in argv:
        envoyer(texte)
    else:
        print(texte)


if __name__ == '__main__':
    main(sys.argv[1:])
