#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_niveaux_fiabilite.py — UNE ÉTUDE PAR NIVEAU DE FIABILITÉ : fragile, prudent, correct, solide (18/11/2026,
paquet 269, demande de Lucas après le paquet 268 : « il faut une étude pour chaque niveau de fiabilité »).

Échantillon : celui de etude_a_ou_b.matchs (pronostics EN DIRECT jugés, premier pronostic, ATP / WTA / Challenger,
sans abandon). A = joueur donné gagnant au premier pronostic. Aucune cote. Rien n'entre dans le % de victoire.

Pour CHAQUE niveau, en tout et circuit par circuit :
  1. justesse du % : réussite réelle contre annoncée, Brier, log loss, PENTE d'étalonnage a (réel ~ σ(a · logit p) ;
     1 = nos % se réalisent tels quels ; < 1 = trop sûrs d'eux ; > 1 = trop prudents) ;
  2. tranches du % annoncé à l'intérieur du niveau (moins de 58 %, 58–70, 70–80, 80 et plus) ;
  3. anatomie des défaites À L'INTÉRIEUR du niveau : mêmes critères connus avant le match que le paquet 268
     (désaccord Elo / simulation, joueurs peu connus, matchs similaires, score instable, surface, tranche).

RÈGLES FIXÉES AVANT DE REGARDER LES RÉSULTATS (ne pas les modifier après coup) :
  — anatomie : un critère est « à étudier sur l'archive » si, avec au moins 30 matchs sur chacune des deux moitiés
    chronologiques, A y réussit moins que prévu de plus de 1,96 erreur type sur les DEUX moitiés ; « trop tôt » sous
    60 matchs ;
  — correction du niveau : la pente a est ajustée sur la 1re moitié chronologique et appliquée à la 2de. « Correction
    à proposer » si, avec au moins 100 matchs par moitié, la log loss de la 2de moitié baisse d'au moins 0,001 ET la
    pente ajustée sur la 2de moitié est du même côté de 1 que celle de la 1re ; « trop tôt » sous 100 matchs par
    moitié ; sinon « pas de correction ». Jugé en tout et circuit par circuit ; un circuit ne reprend pas le verdict
    d'un autre. Rien n'est appliqué automatiquement : une correction passe ensuite par un paquet, avec sa règle de
    retrait.
  — RETRAIT d'une correction en place (paquet 270, simulateur/correction_niveaux.json) : sur les matchs corrigés jugés
    (circuit et niveau de la correction), log loss AVEC et SANS la correction (les deux % sont gardés dans la fiche) ;
    avec au moins 100 matchs, si la log loss AVEC dépasse celle SANS d'au moins 0,001, la correction est retirée
    (retiree = true dans le fichier, lu à chaque passage des pronostics).
Sortie publique : simulateur/rapport_niveaux_fiabilite.json (aucun nom, aucune cote). Descriptif.
Usage : python simulateur/etude_niveaux_fiabilite.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_a_ou_b as AB  # noqa: E402

NIVEAUX, CIRCUITS = AB.NIVEAUX, AB.CIRCUITS
N_MOITIE_CORR, GAIN_MIN = 100, 0.001
EPS = 1e-6


def _lg(p):
    p = min(max(p, EPS), 1 - EPS)
    return math.log(p / (1 - p))


def _sig(z):
    return 1 / (1 + math.exp(-z))


def pente(X):
    """Pente a de réel ~ σ(a · logit p_A), par Newton (sans constante : la symétrie A / B l'impose)."""
    a = 1.0
    for _ in range(50):
        g = h = 0.0
        for x in X:
            z = _lg(x['p_a'])
            q = _sig(a * z)
            g += (float(x['a_gagne']) - q) * z
            h += q * (1 - q) * z * z
        if h <= 0:
            break
        pas = g / h
        a += pas
        if abs(pas) < 1e-7:
            break
    return a


def log_loss(X, a=1.0):
    s = 0.0
    for x in X:
        q = min(max(_sig(a * _lg(x['p_a'])), EPS), 1 - EPS)
        s -= math.log(q if x['a_gagne'] else 1 - q)
    return s / len(X)


def mesures(X):
    n = len(X)
    if not n:
        return None
    reel, prevu = sum(x['a_gagne'] for x in X) / n, sum(x['p_a'] for x in X) / n
    return {'n': n, 'reussite_reelle_pct': round(100 * reel, 1), 'reussite_annoncee_pct': round(100 * prevu, 1),
            'ecart_pts': round(100 * (reel - prevu), 1),
            'brier': round(sum((x['p_a'] - x['a_gagne']) ** 2 for x in X) / n, 4),
            'log_loss': round(log_loss(X), 4), 'pente': round(pente(X), 3) if n >= 20 else None}


def correction(X):
    m1, m2 = X[:len(X) // 2], X[len(X) // 2:]
    if len(m1) < N_MOITIE_CORR or len(m2) < N_MOITIE_CORR:
        return {'verdict': 'trop tôt', 'n_moities': [len(m1), len(m2)]}
    a1, a2 = pente(m1), pente(m2)
    gain = log_loss(m2) - log_loss(m2, a1)
    ok = gain >= GAIN_MIN and (a1 - 1) * (a2 - 1) > 0
    return {'n_moities': [len(m1), len(m2)], 'pente_1re_moitie': round(a1, 3), 'pente_2de_moitie': round(a2, 3),
            'gain_log_loss_2de_moitie': round(gain, 4),
            'verdict': ('correction à proposer : ' + ('rapprocher le % de 50 %' if a1 < 1 else 'écarter le % de 50 %'))
            if ok else 'pas de correction'}


def tranche(p):
    return 'moins de 58 %' if p < .58 else '58–70 %' if p < .70 else '70–80 %' if p < .80 else '80 % et plus'


def anatomie_niveau(X):
    K = {}
    for x in X:
        for k in AB.criteres(x):
            if not k.startswith('niveau : '):
                K.setdefault(k, []).append(x)
    out = {}
    for k, G in sorted(K.items()):
        g = AB._groupe(G)
        h1, h2 = AB._groupe(G[:len(G) // 2]), AB._groupe(G[len(G) // 2:])
        a_etudier = bool(h1 and h2 and h1['n'] >= AB.N_MOITIE_ANAT and h2['n'] >= AB.N_MOITIE_ANAT
                         and h1['sous_prevu'] and h2['sous_prevu'])
        g.pop('sous_prevu')
        g['moities_ecart_pts'] = [h1['ecart_pts'] if h1 else None, h2['ecart_pts'] if h2 else None]
        g['verdict'] = 'à étudier sur l\'archive' if a_etudier else ('trop tôt' if len(G) < 2 * AB.N_MOITIE_ANAT else 'rien à signaler')
        out[k] = g
    return out


def etude_niveau(X):
    out = {'ensemble': mesures(X), 'correction': correction(X) if X else {'verdict': 'trop tôt'}}
    out['tranches'] = {t: mesures([x for x in X if tranche(x['p_a']) == t]) for t in
                       ('moins de 58 %', '58–70 %', '70–80 %', '80 % et plus')}
    out['par_circuit'] = {}
    for c in CIRCUITS:
        Xc = [x for x in X if x['circuit'] == c]
        out['par_circuit'][c] = {'mesures': mesures(Xc), 'correction': correction(Xc) if Xc else {'verdict': 'trop tôt'}}
    out['anatomie'] = anatomie_niveau(X)
    return out


N_RETRAIT, PERTE_RETRAIT = 100, 0.001


def suivi_corrections(racine, M):
    """Règle de retrait de l'en-tête ; renvoie (suivi, document du fichier modifié ou None)."""
    chemin = os.path.join(racine, 'simulateur', 'correction_niveaux.json')
    try:
        with open(chemin, encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}, None
    suivi, change = {}, False
    for c, nv in (doc.get('corrections') or {}).items():
        for n, v in (nv or {}).items():
            avec, sans = [], []
            for x in M:
                k = ((x['m'].get('fiabilite') or {}).get('correction_niveau')) or {}
                if x['circuit'] != c or k.get('niveau') != n or k.get('p_home_avec_correction') is None:
                    continue
                y = (x['m'].get('reel') or {}).get('gagnant') == 'home'
                for L, q in ((avec, k['p_home_avec_correction']), (sans, k['p_home_sans_correction'])):
                    q = min(max(float(q), EPS), 1 - EPS)
                    L.append(-math.log(q if y else 1 - q))
            r = {'pente': v.get('pente'), 'retiree': bool(v.get('retiree')), 'n': len(avec)}
            if avec:
                r['log_loss_avec'], r['log_loss_sans'] = round(sum(avec) / len(avec), 4), round(sum(sans) / len(sans), 4)
            if len(avec) >= N_RETRAIT and not v.get('retiree') and r['log_loss_avec'] - r['log_loss_sans'] >= PERTE_RETRAIT:
                v['retiree'], v['retiree_le'] = True, dt.date.today().isoformat()
                r['retiree'], change = True, True
            r['verdict'] = 'retirée' if r['retiree'] else ('trop tôt' if len(avec) < N_RETRAIT else 'gardée')
            suivi[f'{c}|{n}'] = r
    return suivi, (doc if change else None)


def rapport(racine, M=None):
    M = AB.matchs(racine) if M is None else M
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 269,
            'definition': 'A = joueur donné gagnant par l\'algo au premier pronostic ; pente 1 = % justes ; '
                          '< 1 = trop sûrs ; > 1 = trop prudents',
            'regles': __doc__.split('RÈGLES FIXÉES AVANT DE REGARDER LES RÉSULTATS (ne pas les modifier après coup) :')[1]
            .split('Sortie publique')[0].replace('\n', ' ').strip(),
            'descriptif': 'le % de victoire ne change pas', 'matchs': len(M),
            'niveaux': {nv: etude_niveau([x for x in M if x['niveau'] == nv]) for nv in NIVEAUX},
            'corrections_en_place': suivi_corrections(racine, M)[0]}


if __name__ == '__main__':
    racine = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..')
    M = AB.matchs(racine)
    r = rapport(racine, M)
    with open(os.path.join(racine, 'simulateur', 'rapport_niveaux_fiabilite.json'), 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    _, nouveau = suivi_corrections(racine, M)
    if nouveau:                                      # règle de retrait déclenchée : le fichier est réécrit
        with open(os.path.join(racine, 'simulateur', 'correction_niveaux.json'), 'w', encoding='utf-8') as f:
            json.dump(nouveau, f, ensure_ascii=False, indent=1)
        print('Correction retirée :', {k: v for k, v in r['corrections_en_place'].items()})
    for nv, e in r['niveaux'].items():
        m, c = e['ensemble'] or {}, e['correction']
        print(f"{nv:8s} n={m.get('n')} réel {m.get('reussite_reelle_pct')} / annoncé {m.get('reussite_annoncee_pct')} "
              f"· pente {m.get('pente')} · {c['verdict']} {c.get('pente_1re_moitie', '')} {c.get('pente_2de_moitie', '')} {c.get('gain_log_loss_2de_moitie', '')}")
        for cc, v in e['par_circuit'].items():
            mm = v['mesures'] or {}
            print(f"    {cc:3s} n={mm.get('n')} écart {mm.get('ecart_pts')} pente {mm.get('pente')} · {v['correction']['verdict']}")
        sig = [k for k, g in e['anatomie'].items() if g['verdict'].startswith('à étudier')]
        print('    à étudier :', sig or 'aucun')
