#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roi_algo.py — ROI de l'algorithme aux cotes Pinnacle de clôture (23/10/2026). INTERNE : Telegram privé seulement,
jamais sur le site public.

RÈGLES FIXÉES LE 23/10/2026, AVANT D'AVOIR VU LE MOINDRE CHIFFRE (ne pas les modifier après coup) :
  R1 « vainqueur » : 1 unité sur le joueur que l'algo donne gagnant, à la cote Pinnacle de clôture.
  R2 « valeur 5 % » : 1 unité sur le joueur dont (% de l'algo × cote Pinnacle de clôture) ≥ 1,05.
Cote de clôture : dernière cote Pinnacle capturée avant le début (closing_lines ; capture fiable seulement).
Pourquoi la clôture : c'est la cote la plus dure à battre ; on ne suppose aucune meilleure cote prise plus tôt.
Exclus : ITF (non joué), abandons et forfaits (règlement variable selon le book), matchs sans clôture Pinnacle.

Deux échantillons, jamais mélangés :
  — EN DIRECT : le dernier pronostic affiché avant le match (journal depuis le 21/10/2026) — le seul qui compte ;
  — REJOUÉ : les pronostics hors échantillon (entraînement progressif), pour le volume.
Rappel de méthode : pas de conclusion avant 30 paris au moins ; un ROI se lit avec son intervalle à 95 %.
Usage : python simulateur/roi_algo.py [racine] [--telegram]
"""
import datetime as dt
import json
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
SEUIL_VALEUR = 1.05
N_MIN = 30
CIRCUITS = ('ATP', 'WTA', 'CH')
LIB = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}


def _ts(s):
    try:
        d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=None) if d.tzinfo is None else d.astimezone(dt.timezone.utc).replace(tzinfo=None)


def clotures(racine):
    """{uid: (cote_home, cote_away)} — Pinnacle à la clôture, uid = AAAA-MM-JJ_home_away (et l'inverse)."""
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
        c = e.get('closing') or {}
        ch = ca = None
        if c.get('reliable') and c.get('home') and c.get('away'):
            ch, ca = float(c['home']), float(c['away'])
        else:
            avant = [h for h in e.get('history') or [] if _ts(h.get('t')) and _ts(h['t']) < debut]
            if avant:
                h = max(avant, key=lambda x: _ts(x['t']))
                try:
                    ch, ca = float(h['home']), float(h['away'])
                except (KeyError, TypeError, ValueError):
                    pass
        if not ch or not ca or ch <= 1 or ca <= 1:
            continue
        a, b = NR.slug(e['home']), NR.slug(e['away'])
        out[f"{debut.date()}_{a}_{b}"] = (ch, ca)
        out.setdefault(f"{debut.date()}_{b}_{a}", (ca, ch))
    return out


def _cote(C, uid, debut):
    """Clôture du match (même jour, sinon ± 1 jour : fuseaux)."""
    if uid in C:
        return C[uid]
    try:
        j = dt.date.fromisoformat(uid[:10])
    except ValueError:
        return None
    reste = uid[11:]
    for d in (-1, 1):
        k = f"{j + dt.timedelta(days=d)}_{reste}"
        if k in C:
            return C[k]
    return None


def direct(racine):
    """[(uid, circuit, p_home, gagnant)] — dernier pronostic affiché avant le match (sinon le premier)."""
    try:
        R = json.load(open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    out = []
    for m in R.get('matchs') or []:
        reel = m.get('reel') or {}
        if m.get('circuit') not in CIRCUITS or reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        p = None
        for bloc in ('dernier', 'premier'):
            for k in ('combinaison', 'simulation', 'stats'):
                v = (m.get(bloc) or {}).get(k)
                if p is None and isinstance(v, dict) and v.get('p_home') is not None:
                    p = float(v['p_home'])
        if p is not None:
            out.append((m['uid'], m['circuit'], p, reel['gagnant']))
    return out


def rejoue(racine):
    """[(uid, circuit, p_home, gagnant)] — pronostics hors échantillon reliés aux clôtures Pinnacle
    (même jointure que etude_rentabilite_marches.py : noms, ± 1 jour)."""
    import gzip
    import etude_rentabilite_marches as ER
    M = ER.matchs_pinnacle(racine, ER._books(racine))
    H = ER.pronostics_historiques(racine, M)
    circ = {}
    try:
        with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
            for l in f:
                r = json.loads(l)
                circ[(r['jour'], round(r['p_algo'] or -1, 4))] = r.get('circuit')
    except (OSError, ValueError):
        pass
    out = []
    for uid, (p, g) in H.items():
        c = circ.get((uid[:10], round(p, 4))) or circ.get((uid[:10], round(1 - p, 4))) or '?'
        if c in CIRCUITS or c == '?':
            out.append((uid, c, p, g))
    return out


def paris(L, C):
    """Applique R1 et R2. Renvoie {'R1': [...], 'R2': [...]} de (circuit, cote, gagné)."""
    out = {'R1': [], 'R2': []}
    for uid, circuit, p, g in L:
        c = _cote(C, uid, None)
        if not c:
            continue
        ch, ca = c
        cote1, gagne1 = (ch, g == 'home') if p >= 0.5 else (ca, g == 'away')
        out['R1'].append((circuit, cote1, gagne1))
        for prob, cote, cote_gagne in ((p, ch, g == 'home'), (1 - p, ca, g == 'away')):
            if prob * cote >= SEUIL_VALEUR:
                out['R2'].append((circuit, cote, cote_gagne))
    return out


def _ic(gains, n_boot=2000, graine=7):
    if len(gains) < 2:
        return None
    rnd = random.Random(graine)
    m = sorted(sum(rnd.choice(gains) for _ in gains) / len(gains) for _ in range(n_boot))
    return [round(m[int(.025 * n_boot)], 3), round(m[int(.975 * n_boot)], 3)]


def bilan(P):
    gains = [(c - 1) if ok else -1.0 for _, c, ok in P]
    n = len(gains)
    if not n:
        return {'n': 0}
    return {'n': n, 'gagnes': sum(1 for *_, ok in P if ok), 'unites': round(sum(gains), 2),
            'roi': round(sum(gains) / n, 3), 'cote_moy': round(sum(c for _, c, _ in P) / n, 2), 'ic95': _ic(gains)}


def avant_apres(L, C, racine):
    """29/10/2026 — pour chaque changement mis en production (simulateur/journal_changements.json) : l'algo face à la
    clôture Pinnacle AVANT et APRÈS sa date, sur l'échantillon EN DIRECT. Log loss de l'algo et de la clôture (sans
    marge) sur les mêmes matchs, et ROI de R1. L'écart algo − clôture qui se resserre = l'algo se rapproche du prix juste.
    Suivi seulement : pas de conclusion sous 30 matchs de chaque côté."""
    import math
    try:
        J = json.load(open(os.path.join(racine, 'simulateur', 'journal_changements.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    dates = sorted({c['date'] for c in J.get('changements') or [] if c.get('statut') == 'production'})

    def bloc(X):
        pts = []
        for uid, circuit, p, g in X:
            c = _cote(C, uid, None)
            if not c:
                continue
            qh, qa = 1 / c[0], 1 / c[1]
            pm, y = qh / (qh + qa), g == 'home'
            ll = lambda q: -math.log(min(max(q if y else 1 - q, 1e-6), 1 - 1e-6))
            pts.append((ll(p), ll(pm)))
        n = len(pts)
        if not n:
            return {'n': 0}
        la, lm = sum(a for a, _ in pts) / n, sum(b for _, b in pts) / n
        return {'n': n, 'log_loss_algo': round(la, 4), 'log_loss_cloture': round(lm, 4), 'ecart': round(la - lm, 4),
                'R1': bilan(paris(X, C)['R1']), 'conclusion_possible': n >= N_MIN}
    return [{'date': d, 'avant': bloc([x for x in L if x[0][:10] < d]), 'apres': bloc([x for x in L if x[0][:10] >= d])}
            for d in dates]


def calculer(racine):
    C = clotures(racine)
    L = direct(racine)
    out = {'direct': {}, 'n_pronostics': len(L), 'n_avec_cloture': sum(1 for x in L if _cote(C, x[0], None)), 'rejoue': {},
           'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'source_probabilites': 'dernier pronostic indépendant affiché avant le match, sinon premier',
           'source_cotes': 'dernière cote Pinnacle fiable capturée avant le début ; jamais une cote postérieure',
           'regles': {'R1': '1 unité sur le vainqueur annoncé',
                      'R2': f'1 unité sur chaque côté si probabilité × cote >= {SEUIL_VALEUR}'},
           'minimum_pour_conclure': N_MIN,
           'avertissement': 'Le marché sert seulement à évaluer le rendement ; il ne modifie pas le modèle indépendant.'}
    for regle, P in paris(L, C).items():
        out['direct'][regle] = dict(bilan(P), par_circuit={LIB[c]: bilan([x for x in P if x[0] == c]) for c in CIRCUITS})
    try:
        Rj = rejoue(racine)
    except Exception as e:  # noqa: BLE001
        print(f"rejoué indisponible ({type(e).__name__}: {e})")
        Rj = []
    out['avant_apres'] = avant_apres(L, C, racine)
    out['n_rejoue'] = len(Rj)
    for regle, P in paris(Rj, C).items():
        out['rejoue'][regle] = dict(bilan(P), par_circuit={LIB[c]: bilan([x for x in P if x[0] == c]) for c in CIRCUITS})
    return out


def _ligne(nom, b):
    if not b.get('n'):
        return f"{nom} : aucun pari"
    ic = b.get('ic95')
    s = (f"{nom} : {b['n']} paris · {b['gagnes']} gagnés · {b['unites']:+.2f} u · ROI {100 * b['roi']:+.1f} %"
         + (f" (IC95 {100 * ic[0]:+.0f} / {100 * ic[1]:+.0f} %)" if ic else '') + f" · cote moy. {b['cote_moy']}")
    return s + ('' if b['n'] >= N_MIN else f" — moins de {N_MIN} paris : rien à conclure")


def message(r):
    L = ["<b>🔒 ROI de l'algo (interne)</b> — cotes Pinnacle de clôture, 1 unité par pari",
         f"Pronostics jugés en direct : {r['n_pronostics']} · avec clôture Pinnacle : {r['n_avec_cloture']}", ""]
    for regle, titre in (('R1', 'R1 vainqueur de l\'algo'), ('R2', 'R2 valeur ≥ 5 %')):
        b = r['direct'].get(regle) or {'n': 0}
        L.append(_ligne(titre, b))
        for c, bc in (b.get('par_circuit') or {}).items():
            if bc.get('n'):
                L.append(f"   {c} : {bc['n']} · ROI {100 * bc['roi']:+.1f} %")
    if r.get('n_rejoue'):
        L += ["", f"<b>Rejoué hors échantillon</b> (depuis août, {r['n_rejoue']} matchs avec clôture) :"]
        for regle, titre in (('R1', 'R1 vainqueur'), ('R2', 'R2 valeur ≥ 5 %')):
            b = r['rejoue'].get(regle) or {'n': 0}
            L.append(_ligne(titre, b))
            for c, bc in (b.get('par_circuit') or {}).items():
                if bc.get('n'):
                    L.append(f"   {c} : {bc['n']} · ROI {100 * bc['roi']:+.1f} %")
    for x in r.get('avant_apres') or []:
        a, b = x['avant'], x['apres']
        if not a.get('n') or not b.get('n'):
            continue
        L += ["", f"<b>Changement du {x['date']}</b> — écart log loss algo − clôture (plus bas = plus proche du prix juste)",
              f"   avant : {a['n']} matchs · écart {a['ecart']:+.4f} · R1 ROI {100 * (a['R1'].get('roi') or 0):+.1f} %",
              f"   après : {b['n']} matchs · écart {b['ecart']:+.4f} · R1 ROI {100 * (b['R1'].get('roi') or 0):+.1f} %"
              + ('' if b['conclusion_possible'] else ' — moins de 30 matchs : rien à conclure')]
    L += ["", "Règles fixées le 23/10/2026 avant tout résultat. Validation = CLV ; ce ROI est un suivi."]
    return '\n'.join(L)


def envoyer(texte):
    import urllib.parse
    import urllib.request
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        print('Telegram non configuré.')
        return
    data = urllib.parse.urlencode({'chat_id': chat, 'text': texte, 'parse_mode': 'HTML',
                                   'disable_web_page_preview': 'true'}).encode()
    urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20).read()


def main(argv):
    racine = next((a for a in argv[1:] if not a.startswith('--')), os.path.join(ICI, '..'))
    r = calculer(racine)
    chemin = os.path.join(racine, 'simulateur', 'rapport_roi_algo.json')
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    texte = message(r)
    # 23/10/2026 : le dépôt est public, ses journaux de runs aussi : avec --telegram, rien n'est affiché dans le log.
    if '--telegram' not in argv:
        print(texte)
    else:
        print('ROI calculé : envoyé sur le Telegram privé (non affiché ici, journal public).')
    # Le rapport JSON garde le calcul reproductible ; Telegram reste une notification privée séparée.
    if '--telegram' in argv:
        envoyer(texte)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
