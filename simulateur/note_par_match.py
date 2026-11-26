#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
note_par_match.py — LA NOTE DE FIABILITÉ MESURÉE MATCH PAR MATCH, DE 0 À 100 (25/11/2026, paquet 451, Lucas : « chaque
match est indépendant et doit être analysé indépendamment ; ensuite on crée des catégories pour les regrouper ; un
match peut être fiable de 0 à 100 % et non limité à quelques notes » ; « il ne faut pas de plafond, il faut la réalité »).

LA NOTE D'UN MATCH. a = pente d'étalonnage attendue POUR CE MATCH (réel ~ σ(a · logit p) ; a = 1 : nos % sont la
réalité ; a < 1 : trop tranchés ; a > 1 : trop prudents) :
    a = a_base(circuit, expérience du moins connu) × exp(Σ β_k · critère_k du match)
    note = 100 · min(a, 1/a)        (0 à 100, sans plafond) ; sens = « trop tranchés » si a < 1, « prudents » si a > 1.
  — a_base : la pente de la classe d'expérience (moins de 30, 30–99, 100–299, 300 matchs et plus). Challenger : le rejeu
    comme en production, résultats ITF hommes compris (étude 449) ; une classe dont la pente change de sens entre la
    période d'apprentissage et la période jugée (300 matchs et plus : 0,78 puis 1,25) prend la pente du circuit.
    ATP / WTA : la note v3 en place (moyenne des cases de la classe, archive).
  — gamma : sur nos matchs en direct, l'ajustement de cette pente de base pour le % PUBLIÉ (celui que la note décrit :
    Elo + simulation + signaux), ramené vers la pente du rejeu par un a priori (± 30 %) tant que les matchs sont peu
    nombreux ;
  — β_k : l'effet de chaque critère mesuré sur nos matchs en direct (surveillance_fragilite.CRITERES : favoris opposés,
    écart Elo / simulation ≥ 10 points, joueur à moins de 30 et de 60 matchs, match serré, gros favori, huitièmes,
    pronostic qui a bougé) et, depuis le paquet 452, la NOTE DE FIABILITÉ DES JOUEURS (scripts/performance_joueurs.py :
    nos % annoncés pour lui sur ses 20 derniers matchs publiés contre ses victoires ; au moins 5 matchs ; calculée
    avec ses seuls matchs ANTÉRIEURS au jour du match) : critère continu « joueur_peu_fiable » = (100 − la plus basse
    des deux notes) / 100, 0 si aucune note ; appris ENSEMBLE (un match qui remplit deux critères n'est pas compté deux fois), ramené vers
    « aucun effet » par un a priori (effet de l'ordre de ± 30 % sur la pente) tant que les matchs sont peu nombreux.
    Réappris chaque lundi sur tous nos matchs terminés jusqu'à la veille.
  — Catégories, pour lire vite : fragile < 78, prudent < 85, correct < 93, solide (seuils de simulateur/fiabilite.py).

GARDE-FOU (règle écrite avant la mise en place), chaque lundi, AVANT le réapprentissage : sur nos matchs terminés notés
depuis l'activation (sans abandon ; chaque note a été calculée avec des effets appris AVANT le match), dès 200 matchs,
on mesure si la pente annoncée par la note décrit la réalité : log loss moyenne de σ(a · logit p), a = pente du match
annoncée (la mesure de l'étude 449). Même calcul pour l'ancienne note (v3 de l'archive avec le plafond à 77, calculée à
côté ; sa pente effective : celle de sa case, ramenée à 0,77 quand le plafond joue). Si la nouvelle fait pire que
l'ancienne, « retire » passe à true : l'ancienne note revient au passage suivant. Publié à côté, sans décider : note
annoncée contre note réelle par tranche de 10 points.
Aucun % ne change : la correction Challenger « correct » (paquet 270) vise les matchs que l'ANCIENNE note classe
« correct ».

Usage : python simulateur/note_par_match.py . [--telegram]       (garde-fou, puis réapprentissage des effets)
        python simulateur/note_par_match.py . --initialiser       (pentes de base et premiers effets)
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

FICHIER = os.path.join('simulateur', 'note_par_match.json')
CIRCUITS = ('ATP', 'WTA', 'CH')
EXPERIENCE = (0, 30, 100, 300, 10 ** 9)
SD_A_PRIORI = 0.3
MIN_MATCHS, MIN_TRANCHE = 200, 20
SEUILS = {'prudent': 78, 'correct': 85, 'solide': 93}
# Challenger, rejeu comme en production (étude 449) : appris 01–09/2025, jugé 10/2025 → 05/2026
CH_APPRIS = {'0': 1.0308, '1': 1.0337, '2': 1.005, '3': 0.781, '_circuit': 1.005}
CH_JUGE = {'0': 1.154, '1': 1.131, '2': 1.183, '3': 1.248}


def classe(n):
    for i, (lo, hi) in enumerate(zip(EXPERIENCE[:-1], EXPERIENCE[1:])):
        if lo <= n < hi:
            return i
    return 0


def note(a):
    return int(round(100 * min(a, 1 / a))) if a and a > 0 else 0


def niveau(n):
    s = SEUILS
    return 'fragile' if n < s['prudent'] else 'prudent' if n < s['correct'] else 'correct' if n < s['solide'] else 'solide'


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(u):
    return 1 / (1 + math.exp(-max(min(u, 30), -30)))


# ------------------------------------------------------------------ le modèle
def charger(racine=None):
    chemin = os.path.join(racine, FICHIER) if racine else os.path.join(ICI, 'note_par_match.json')
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


CRITERE_JOUEUR = 'joueur_peu_fiable'
MIN_MATCHS_JOUEUR = 5      # paquet 452 ; gardé quand l'affichage passe à 20 matchs (paquet 458) : effet appris, ramené vers 0


def noms_criteres():
    import surveillance_fragilite as SF
    return list(SF.CRITERES) + [CRITERE_JOUEUR]


def criteres_du_match(r, x_joueur=0.0):
    """{critère: valeur} : 0/1 pour les critères de surveillance_fragilite.CRITERES (r : p, pe, ps, xp, tour, p0, p1),
    et le critère continu joueur_peu_fiable (0 à 1)."""
    import surveillance_fragilite as SF
    out = {k: int(bool(f(r))) for k, (_, f) in SF.CRITERES.items()}
    out[CRITERE_JOUEUR] = round(float(x_joueur or 0.0), 4)
    return out


# ------------------------------------------------------------------ note de fiabilité des joueurs (au jour du match)
def _note_joueur_fn():
    sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
    import performance_joueurs as PJ
    return PJ.note_fiabilite, PJ.FENETRE


def index_joueurs(enreg):
    """{clé joueur: [(jour, p annoncé pour lui, 1 si victoire)] triés} — enreg : matchs publiés terminés
    (home, away, debut, p = % home, y = 1 si home gagne)."""
    import elo as E
    idx = {}
    for r in enreg:
        if not r.get('home') or not r.get('away') or r.get('p') is None:
            continue
        j = str(r.get('debut') or '')[:10]
        idx.setdefault(E.cle(r['home']), []).append((j, float(r['p']), int(r['y'])))
        idx.setdefault(E.cle(r['away']), []).append((j, 1 - float(r['p']), 1 - int(r['y'])))
    for v in idx.values():
        v.sort()
    return idx


def x_joueur(idx, home, away, jour):
    """(100 − la plus basse des notes des deux joueurs) / 100, avec leurs seuls matchs d'avant ce jour ; 0 sinon."""
    import elo as E
    note_f, fen = _note_joueur_fn()
    notes = []
    for nom in (home, away):
        L = [(p, y) for j, p, y in (idx.get(E.cle(nom)) if nom else None) or [] if j < jour][-fen:]
        n, _ = note_f(L, MIN_MATCHS_JOUEUR)
        if n is not None:
            notes.append(n)
    return (100 - min(notes)) / 100 if notes else 0.0


def pente_du_match(M, circuit, n_min, crit):
    """(a, a_base, {critère: facteur}) ou None. a_base = pente du rejeu × l'ajustement appris sur nos matchs (gamma)."""
    i = str(classe(n_min))
    base = ((M or {}).get('pentes_base') or {}).get(circuit) or {}
    a0 = base.get(i, base.get('_circuit'))
    if not a0:
        return None
    E = (M or {}).get('effets') or {}
    a0 = float(a0) * math.exp((E.get('gamma') or {}).get(f'{circuit}|{i}', 0.0))
    eff = E.get('beta') or {}
    appl = {k: round(math.exp(eff[k] * float(v)), 3) for k, v in crit.items() if v and k in eff}
    a = a0 * math.exp(sum(eff[k] * float(v) for k, v in crit.items() if v and k in eff))
    return a, a0, appl


def evaluer_match(M, circuit, n_min, crit):
    """Ce que la fiche reçoit : note, pente, sens, effets appliqués."""
    r = pente_du_match(M, circuit, n_min, crit)
    if not r:
        return None
    a, a0, appl = r
    return {'note': note(a), 'pente_du_match': round(a, 3), 'pente_de_base': round(a0, 3), 'effets_criteres': appl,
            'sens': 'prudents' if a > 1.005 else 'tranches' if a < 0.995 else 'justes'}


# ------------------------------------------------------------------ apprentissage des effets (nos matchs en direct)
def lignes(racine, aujourdhui):
    """Nos matchs terminés avant aujourd'hui, dans l'ordre : z vu du vainqueur, circuit, expérience, critères (la note
    des joueurs calculée avec leurs seuls matchs d'avant le jour du match)."""
    import surveillance_fragilite as SF
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    ancien = SF.SEMAINES
    try:
        SF.SEMAINES = 520
        R = SF.lignes(racine, aujourdhui)           # mêmes critères que la production (tour du tableau compris)
    finally:
        SF.SEMAINES = ancien
    M = []
    for m in doc.get('matchs') or []:
        reel = m.get('reel') or {}
        if (m.get('p_affiche') is None or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu')
                or not str(m.get('debut') or '')[:10] or str(m['debut'])[:10] >= aujourdhui.isoformat()):
            continue
        M.append(m)
    if len(M) != len(R):                              # même filtre que SF.lignes : sinon, pas de note des joueurs
        M = [None] * len(R)
    enreg = [{'home': m['home'], 'away': m['away'], 'debut': m['debut'], 'p': m['p_affiche'],
              'y': int(m['reel']['gagnant'] == 'home')} for m in M if m]
    idx = index_joueurs(enreg)
    out = []
    for r, m in zip(R, M):
        if r.get('c') not in CIRCUITS or r.get('xp') is None:
            continue
        z = _lg(r['p'])
        xj = x_joueur(idx, m['home'], m['away'], str(m['debut'])[:10]) if m else 0.0
        out.append({'c': r['c'], 'n': r['xp'], 'z': z if r['y'] else -z, 'crit': criteres_du_match(r, xj)})
    return out


def _resoudre(H, g):
    m = len(g)
    A = [row[:] + [gi] for row, gi in zip(H, g)]
    for c in range(m):
        p = max(range(c, m), key=lambda i: abs(A[i][c]))
        A[c], A[p] = A[p], A[c]
        if abs(A[c][c]) < 1e-12:
            continue
        for i in range(m):
            if i != c:
                f = A[i][c] / A[c][c]
                for k in range(c, m + 1):
                    A[i][k] -= f * A[c][k]
    return [A[i][m] / A[i][i] if abs(A[i][i]) > 1e-12 else 0.0 for i in range(m)]


def apprendre_effets(L, M):
    """Appris ENSEMBLE sur nos matchs en direct (le % publié, celui que la note décrit), Newton (Fisher) :
    log a = log a_rejeu(circuit, classe) + gamma(circuit, classe) + Σ β_k · critère_k ;
    a priori N(0, SD_A_PRIORI²) sur chaque gamma (ramené vers la pente du rejeu) et chaque β (ramené vers « aucun effet »)."""
    K = noms_criteres()
    G = [f'{c}|{i}' for c in CIRCUITS for i in range(4)]
    noms = G + K
    lam = 1 / SD_A_PRIORI ** 2
    D = []
    for r in L:
        x0 = pente_du_match({'pentes_base': M['pentes_base']}, r['c'], r['n'], {})
        if x0:
            x = [1.0 if g == f"{r['c']}|{classe(r['n'])}" else 0.0 for g in G] + [float(r['crit'].get(k, 0)) for k in K]
            D.append(([(j, v) for j, v in enumerate(x) if v], r['z'], x0[1]))
    m = len(noms)
    b = [0.0] * m
    for _ in range(100):
        g = [lam * v for v in b]
        H = [[lam if i == j else 0.0 for j in range(m)] for i in range(m)]
        for idx, z, a0 in D:
            u = a0 * math.exp(sum(b[j] * v for j, v in idx)) * z
            q = _sg(u)
            w, gr = q * (1 - q) * u * u, -(1 - q) * u
            for i, vi in idx:
                g[i] += gr * vi
                for j, vj in idx:
                    H[i][j] += w * vi * vj
        d = _resoudre(H, g)
        d = [max(min(v, 1.0), -1.0) for v in d]
        b = [bi - di for bi, di in zip(b, d)]
        if max(abs(v) for v in d) < 1e-8:
            break
    cnt = [0] * m
    for idx, _, _ in D:
        for j, _ in idx:
            cnt[j] += 1
    return {'beta': {k: round(b[m - len(K) + i], 4) for i, k in enumerate(K)},
            'facteurs': {k: round(math.exp(b[m - len(K) + i]), 3) for i, k in enumerate(K)},
            'gamma': {k: round(b[i], 4) for i, k in enumerate(G) if cnt[i]},
            'pentes_base_ajustees': {k: round(float(M['pentes_base'][k.split('|')[0]].get(k.split('|')[1],
                                                    M['pentes_base'][k.split('|')[0]]['_circuit'])) * math.exp(b[i]), 3)
                                     for i, k in enumerate(G) if cnt[i]},
            'matchs_par_critere': {k: cnt[m - len(K) + i] for i, k in enumerate(K)},
            'matchs_par_classe': {k: cnt[i] for i, k in enumerate(G) if cnt[i]},
            'matchs': len(D), 'a_priori': f"chaque ajustement ~ N(0, {SD_A_PRIORI}²) sur le log de la pente"}


# ------------------------------------------------------------------ garde-fou
def pente(Z):
    a = 1.0
    for _ in range(60):
        g = h = 0.0
        for z in Z:
            q = _sg(a * z)
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 1e-12:
            break
        d = max(min(g / h, 2.0), -2.0)
        a -= d
        if abs(d) < 1e-9:
            break
    return a


def ecart(L, cle):
    """Écart moyen |note réelle − note annoncée| par tranche de 10 points (tranches d'au moins MIN_TRANCHE matchs)."""
    par, tot, n = {}, 0.0, 0
    for lo in range(0, 100, 10):
        G = [r for r in L if lo <= r[cle] < lo + 10 or (lo == 90 and r[cle] == 100)]
        if len(G) >= MIN_TRANCHE:
            a = pente([r['z'] for r in G])
            reelle = 100 * min(a, 1 / a) if a > 0 else 0.0
            annoncee = sum(r[cle] for r in G) / len(G)
            par[f'{lo}–{lo + 10}'] = {'matchs': len(G), 'pente': round(a, 3), 'note_reelle': round(reelle, 1),
                                      'note_annoncee': round(annoncee, 1)}
            tot += len(G) * abs(reelle - annoncee)
            n += len(G)
        elif G:
            par[f'{lo}–{lo + 10}'] = {'matchs': len(G), 'pente': None}
    return (round(tot / n, 2) if n else None), par


def lignes_garde_fou(doc, depuis):
    out = []
    for m in doc.get('matchs') or []:
        fi, reel = m.get('fiabilite') or {}, m.get('reel') or {}
        if (m.get('circuit') not in CIRCUITS or fi.get('pente_du_match') is None or fi.get('pente_ancienne') is None
                or fi.get('note_ancienne') is None or m.get('p_affiche') is None
                or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu')
                or str(m.get('debut') or '')[:10] < depuis):
            continue
        z = _lg(m['p_affiche'])
        out.append({'z': z if reel['gagnant'] == 'home' else -z, 'nouvelle': float(fi['note']),
                    'ancienne': float(fi['note_ancienne']), 'a_nouvelle': float(fi['pente_du_match']),
                    'a_ancienne': float(fi['pente_ancienne'])})
    return out


def _ll(u):
    return -math.log(max(_sg(u), 1e-12))


def garde_fou(racine, dec, aujourdhui):
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    L = lignes_garde_fou(doc, dec.get('active_le') or '9999')
    n = len(L)
    ll_new = round(sum(_ll(r['a_nouvelle'] * r['z']) for r in L) / n, 5) if n else None
    ll_old = round(sum(_ll(r['a_ancienne'] * r['z']) for r in L) / n, 5) if n else None
    ctl = {'jour': aujourdhui.isoformat(), 'matchs': n, 'assez': n >= MIN_MATCHS,
           'log_loss_pente_nouvelle': ll_new, 'log_loss_pente_ancienne': ll_old,
           'tranches_nouvelle': ecart(L, 'nouvelle')[1], 'tranches_ancienne': ecart(L, 'ancienne')[1]}
    if dec.get('retire'):
        ctl['verdict'] = 'déjà retirée'
    elif not ctl['assez']:
        ctl['verdict'] = f"pas encore jugée (moins de {MIN_MATCHS} matchs)"
    elif ll_new > ll_old:
        dec['retire'] = True
        dec['retiree_le'] = ctl['jour']
        ctl['verdict'] = "RETIRÉE : la note par match décrit moins bien la réalité que l'ancienne"
    else:
        ctl['verdict'] = 'gardée'
    dec['dernier_controle'] = ctl
    return ctl


# ------------------------------------------------------------------ pentes de base
def pentes_base(racine):
    with open(os.path.join(racine, 'simulateur', 'rapport_fiabilite_v3.json'), encoding='utf-8') as f:
        mod = json.load(f)['modele']
    out = {}
    for c in ('ATP', 'WTA'):
        out[c] = {'_circuit': mod['_circuits'][c]}
        for i in range(4):
            ks = [k for k in mod if k.startswith(f'{c}|{i}|')]
            w = sum(mod[k]['matchs'] for k in ks)
            if w:
                out[c][str(i)] = round(sum(mod[k]['pente'] * mod[k]['matchs'] for k in ks) / w, 4)
    ch = {'_circuit': CH_APPRIS['_circuit']}
    for i in '0123':
        meme_sens = (CH_APPRIS[i] - 1) * (CH_JUGE[i] - 1) > 0
        ch[i] = CH_APPRIS[i] if meme_sens else CH_APPRIS['_circuit']
    out['CH'] = ch
    return out


def ecrire(racine, dec):
    with open(os.path.join(racine, FICHIER), 'w', encoding='utf-8') as f:
        f.write(json.dumps(dec, ensure_ascii=False, indent=1) + '\n')


def message(ctl, eff):
    fac = ', '.join(f"{k} × {v}" for k, v in (eff.get('facteurs') or {}).items())
    return (f"🎯 Note de fiabilité par match (paquet 451) — {ctl['matchs']} matchs jugés ; la pente annoncée décrit-elle la réalité (log loss) : "
            f"nouvelle {ctl['log_loss_pente_nouvelle']}, ancienne {ctl['log_loss_pente_ancienne']} — {ctl['verdict']}\n"
            f"Effets réappris sur {eff.get('matchs')} matchs : {fac}")


def main(argv):
    racine = argv[1] if len(argv) > 1 and not argv[1].startswith('--') else '.'
    aujourdhui = dt.date.today()
    dec = charger(racine)
    if dec is None:
        raise SystemExit('fichier de décision absent : simulateur/note_par_match.json')
    if '--initialiser' not in argv:
        ctl = garde_fou(racine, dec, aujourdhui)
        print(ctl['matchs'], 'matchs ;', ctl['verdict'])
    else:
        ctl = None
    eff = apprendre_effets(lignes(racine, aujourdhui), dec)
    eff['appris_le'] = aujourdhui.isoformat()
    dec['effets'] = eff
    ecrire(racine, dec)
    print('effets réappris sur', eff['matchs'], 'matchs :', eff['facteurs'])
    if ctl and '--telegram' in argv:
        try:
            import telegram_envoi as TE
            TE.envoyer(message(ctl, eff))
        except Exception as e:  # noqa: BLE001 — le message ne doit jamais faire échouer le contrôle
            print('telegram :', type(e).__name__)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
