#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etalonnage_cases.py — ANALYSE CASE PAR CASE DE LA NOTE DE FIABILITÉ, SANS RIEN MODIFIER (25/11/2026, paquet 448)

POURQUOI. Lucas : « Il faut que l'on analyse en détail les résultats de chaque case avant toute modification. »
Le paquet 447 proposait d'étirer ou de resserrer le % selon la case de fiabilité, appris sur l'archive. C'est l'idée du
paquet 317, mise en place en Challenger puis RETIRÉE le 21/11 (paquet 319) : l'archive n'a pas les résultats ITF hommes,
son Elo Challenger paraît trop sûr de lui alors qu'il ne l'est pas en production. L'étude 447 est donc remplacée par
cette analyse, qui ne propose ni n'applique aucune correction.

CE QUI EST DÉCRIT, case par case (case = circuit × expérience du moins connu des deux : moins de 30, 30–99, 100–299,
300 matchs et plus ; en direct, × ampleur des signaux : nulle, moins de 0,15, 0,15 et plus en logit), sur trois
sources mises côte à côte :
  1. REJEU « COMME EN PRODUCTION » : archive depuis 2012 + résultats ITF hommes du dépôt (etude_depart_itf.matchs),
     Elo réglé comme la production (elo.de_production, départs par niveau), mis à jour après chaque match ; l'Elo seul,
     sans les signaux ni la simulation (comme le contrôle du paquet 319). Trois fenêtres : 2018–2022, 2023–2024,
     2025 → mai 2026. Pour le Challenger, SEULE la fenêtre 2025 → mai 2026 a les résultats ITF hommes en entier : les
     deux autres sont publiées pour mémoire (« sans ITF hommes ») et ne servent pas à lire le Challenger.
  2. Pour l'ATP et la WTA, le même rejeu sur 2018–2022 et sur 2023 → mai 2026 (deux périodes, même sens exigé).
  3. NOS MATCHS EN DIRECT (Tennis_Edge_Lab/live/pronostics_resultats.json, premier % publié, sans abandon) : le % publié,
     et le même match sans les signaux de circuit (fiches de match, controle.signaux_circuit) ; par niveau de fiabilité
     (note v3), et pour chaque critère « fragile ».
Pour chaque case : matchs, % moyen annoncé au favori, % réel du favori, pente d'étalonnage (y ~ σ(a·logit p), avec son
erreur type), log loss, log loss attendu (celui qu'on aurait si le % était exact) et l'écart entre les deux, et le
détail par tranche de % annoncé (50–60, 60–70, 70–80, 80–90, 90 et plus).

RÈGLE DE LECTURE ÉCRITE LE 25/11/2026, AVANT DE REGARDER LES RÉSULTATS :
  — une case n'est LISIBLE qu'avec au moins 1 000 matchs ; en dessous, « tendance seulement » ;
  — « % trop sûrs » si pente + 2 erreurs types < 1 ; « % trop timides » si pente − 2 erreurs types > 1 ; sinon
    « conforme à l'erreur près » ;
  — Challenger : la référence est le rejeu 2025 → mai 2026 ; ATP / WTA : les deux périodes du rejeu, et une case n'a un
    sens que si les deux disent la même chose ;
  — le direct ne sert qu'à confirmer ou contredire la référence (« d'accord », « en désaccord », « trop peu de matchs ») ;
  — rien n'est décidé par ce paquet ; toute correction viendrait d'une décision de Lucas après lecture, avec une règle
    écrite à part (apprise sur une période, jugée sur une autre, ≥ 0,001 sur ≥ 1 000 matchs, circuit par circuit).

Rapport public : simulateur/rapport_etalonnage_cases.json — comptes et moyennes seulement, aucun nom de joueur.
L'entrée du journal (paquet 448) est écrite par cette analyse avec ses chiffres.

Usage : python simulateur/etude_etalonnage_cases.py /tmp/sackmann .
        python simulateur/etude_etalonnage_cases.py --journal-depuis-rapport simulateur/rapport_etalonnage_cases.json
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

PAQUET = 448
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
EXPERIENCE = (0, 30, 100, 300, 10 ** 9)
NOM_CLASSE = {0: 'moins de 30 matchs', 1: '30–99 matchs', 2: '100–299 matchs', 3: '300 matchs et plus'}
AMPLEUR = 0.15
NOM_AMPLEUR = {0: 'sans signal', 1: 'signaux < 0,15', 2: 'signaux ≥ 0,15'}
TRANCHES = ((.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01))
FENETRES = (('2018–2022', dt.date(2018, 1, 1), dt.date(2023, 1, 1)),
            ('2023–2024', dt.date(2023, 1, 1), dt.date(2025, 1, 1)),
            ('2025 → mai 2026', dt.date(2025, 1, 1), dt.date(2026, 6, 1)))
DEUXIEME_PERIODE = '2023 → mai 2026'
MIN_LISIBLE = 1000
MIN_PENTE = 20
NIVEAUX = ('fragile', 'prudent', 'correct', 'solide')
SORTIE = os.path.join(ICI, 'rapport_etalonnage_cases.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_448.json')


# ------------------------------------------------------------------ mesures (z = logit du % donné au vainqueur)
def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ll(z):
    return -math.log(max(_sg(z), 1e-12))


def ll_attendu(z):
    p = min(max(_sg(z), 1e-12), 1 - 1e-12)
    return -(p * math.log(p) + (1 - p) * math.log(1 - p))


def classe_experience(n):
    for i, (lo, hi) in enumerate(zip(EXPERIENCE[:-1], EXPERIENCE[1:])):
        if lo <= n < hi:
            return i
    return 0


def classe_ampleur(a):
    a = abs(a or 0.0)
    return 0 if a < 1e-9 else 1 if a < AMPLEUR else 2


def pente(Z, iterations=60):
    """(a, erreur type) tels que le vainqueur ~ σ(a·z) : Newton à un paramètre, erreur type par l'information."""
    a, h = 1.0, 0.0
    for _ in range(iterations):
        g = h = 0.0
        for z in Z:
            q = _sg(a * z)
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 1e-12:
            break
        pas = max(min(g / h, 2.0), -2.0)
        a -= pas
        if abs(pas) < 1e-9:
            break
    return a, (1 / math.sqrt(h) if h > 1e-12 else None)


def lecture(a, et, n):
    if not n:
        return 'aucun match'
    if a is None:
        return f"moins de {MIN_PENTE} matchs : pas de pente"
    sens = ('% trop sûrs' if et is not None and a + 2 * et < 1 else
            '% trop timides' if et is not None and a - 2 * et > 1 else 'conforme à l\'erreur près')
    return sens if n >= MIN_LISIBLE else f"tendance seulement ({sens})"


def sens(d):
    """-1 trop sûrs, +1 trop timides, 0 conforme (même règle que lecture, sans le seuil de 1 000)."""
    if not d or not d.get('matchs') or d.get('pente_erreur_type') is None:
        return None
    a, et = d['pente'], d['pente_erreur_type']
    return -1 if a + 2 * et < 1 else 1 if a - 2 * et > 1 else 0


def decrire(Z):
    """Z : logits du % donné au vainqueur. Tout ce qu'on publie pour une case."""
    n = len(Z)
    if not n:
        return {'matchs': 0}
    a, et = pente(Z) if n >= MIN_PENTE else (None, None)
    fav = [max(_sg(z), 1 - _sg(z)) for z in Z]
    juste = [1.0 if z > 0 else 0.5 if z == 0 else 0.0 for z in Z]
    d = [ll(z) - ll_attendu(z) for z in Z]
    m = sum(d) / n
    et_d = math.sqrt(sum((v - m) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    tr = {}
    for lo, hi in TRANCHES:
        i = [k for k, f in enumerate(fav) if lo <= f < hi]
        if i:
            tr[f"{round(100 * lo)}{'+' if hi > 1 else '–' + str(round(100 * hi))}"] = {
                'matchs': len(i), 'annonce_pct': round(100 * sum(fav[k] for k in i) / len(i), 1),
                'reel_pct': round(100 * sum(juste[k] for k in i) / len(i), 1)}
    return {'matchs': n, 'favori_annonce_pct': round(100 * sum(fav) / n, 1),
            'favori_reel_pct': round(100 * sum(juste) / n, 1),
            'pente': round(a, 3) if a is not None else None, 'pente_erreur_type': round(et, 3) if et is not None else None,
            'log_loss': round(sum(ll(z) for z in Z) / n, 4), 'log_loss_attendu': round(sum(ll_attendu(z) for z in Z) / n, 4),
            'ecart_a_l_attendu': round(m, 4), 'ecart_erreur_type': round(et_d, 4),
            'par_tranche': tr, 'lecture': lecture(a, et, n)}


# ------------------------------------------------------------------ source 1 et 2 : le rejeu comme en production
def rejeu(archive, racine):
    """[(circuit, date, n_min, z du vainqueur)] pour ATP, WTA, Challenger depuis 2018 : Elo de production seul,
    résultats ITF hommes compris (comme simulateur/verif_comme_en_production.py)."""
    import backtest_pronostic as BP
    import elo as E
    import etude_depart_itf as ED
    M, n_itf = ED.matchs(archive, racine)
    el, bas = E.de_production(racine)
    debut, fin = FENETRES[0][1], FENETRES[-1][2]
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if c in CIRCUITS and debut <= m['date'] < fin and not m.get('abandon') and m.get('niveau') != 'D':
            rows.append((c, m['date'], min(el.matchs(g), el.matchs(p)), _lg(el.proba(g, p, s))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows, n_itf


def decrire_rejeu(rows):
    out = {}
    for c in CIRCUITS:
        R = [r for r in rows if r[0] == c]
        fen = {nom: (lo, hi) for nom, lo, hi in FENETRES}
        if c != 'CH':
            fen[DEUXIEME_PERIODE] = (FENETRES[1][1], FENETRES[-1][2])
        bloc = {'tout': {}, 'par_classe': {}}
        for nom, (lo, hi) in fen.items():
            bloc['tout'][nom] = decrire([z for _, d, _, z in R if lo <= d < hi])
            for i in range(4):
                bloc['par_classe'].setdefault(str(i), {'classe': NOM_CLASSE[i]})[nom] = decrire(
                    [z for _, d, n, z in R if lo <= d < hi and classe_experience(n) == i])
        if c == 'CH':
            bloc['reference'] = FENETRES[-1][0]
            bloc['pour_memoire'] = [FENETRES[0][0], FENETRES[1][0]]
            bloc['note'] = ("2018–2022 et 2023–2024 n'ont pas (ou pas en entier) les résultats ITF hommes : l'Elo du "
                            "Challenger y est faussé ; publiés pour mémoire, jamais lus")
        else:
            bloc['reference'] = [FENETRES[0][0], DEUXIEME_PERIODE]
        out[c] = bloc
    return out


def reference(rejeu_c, c, i):
    """Le sens de la case dans le rejeu de référence : -1, 0, +1, None (sources en désaccord ou trop peu)."""
    pc = rejeu_c[c]['par_classe'][str(i)]
    if c == 'CH':
        d = pc.get(FENETRES[-1][0])
        return (sens(d) if d and d.get('matchs', 0) >= MIN_LISIBLE else None), d
    a, b = pc.get(FENETRES[0][0]), pc.get(DEUXIEME_PERIODE)
    if not a or not b or min(a.get('matchs', 0), b.get('matchs', 0)) < MIN_LISIBLE:
        return None, b
    return (sens(a) if sens(a) == sens(b) else None), b


# ------------------------------------------------------------------ source 3 : nos matchs en direct
def _fiches(racine):
    F = {}
    for chemin in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', 'fiches', '*.json.gz'))):
        try:
            with gzip.open(chemin, 'rt', encoding='utf-8') as f:
                F.update(json.load(f))
        except (OSError, ValueError):
            continue
    return F


def lignes_direct(racine):
    """Une ligne par match terminé (sans abandon) : circuit, expérience du moins connu, z publié, ampleur et z sans
    signaux (fiche), niveau et critères fragiles de la note v3."""
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    F = _fiches(racine)
    out = []
    for m in doc.get('matchs') or []:
        reel = m.get('reel') or {}
        p = m.get('p_affiche')
        mj = [x for x in (m.get('matchs_joues') or []) if x is not None]
        if (p is None or m.get('circuit') not in CIRCUITS or reel.get('gagnant') not in ('home', 'away')
                or reel.get('interrompu') or len(mj) != 2):
            continue
        y = reel['gagnant'] == 'home'
        vu = lambda q: _lg(q) if y else -_lg(q)  # noqa: E731
        fi = m.get('fiabilite') or {}
        pr = m.get('premier') or {}
        pe, ps = (pr.get('stats') or {}).get('p_home'), (pr.get('simulation') or {}).get('p_home')
        r = {'c': m['circuit'], 'n': min(mj), 'z': vu(p), 'jour': str(m.get('debut') or '')[:10],
             'z_elo': vu(pe) if pe is not None else None, 'z_simulation': vu(ps) if ps is not None else None,
             'niveau': fi.get('niveau') if fi.get('version_fiabilite') == 'pente_v3' else None,
             'criteres': list(fi.get('fragile_criteres') or []) if fi.get('version_fiabilite') == 'pente_v3' else None}
        dern = (F.get(m.get('uid')) or {}).get('dernier') or {}
        sc = (dern.get('controle') or {}).get('signaux_circuit') or {}
        if dern.get('p_home') is not None:
            dec = {k: float(v) for k, v in (sc.get('decalages') or {}).items() if isinstance(v, (int, float))}
            r['ampleur'] = sum(dec.values())
            r['signaux'] = sorted(dec)
            r['decalages'] = {k: (v if y else -v) for k, v in dec.items()}      # vus du vainqueur
            r['z_fiche'] = vu(dern['p_home'])
            r['z_sans'] = vu(sc['p_home_sans']) if sc.get('p_home_sans') is not None else r['z_fiche']
        out.append(r)
    return out


def verdict(ref, d):
    """Le direct (d) face au sens de référence du rejeu (ref : -1, 0, +1 ou None)."""
    sd, nd = sens(d), (d or {}).get('matchs', 0)
    if ref is None:
        return 'référence illisible (moins de 1 000 matchs ou périodes en désaccord)'
    if nd < 100 or sd is None:
        return 'trop peu de matchs en direct'
    return 'd\'accord' if sd == ref else 'en désaccord' if sd * ref == -1 else 'le direct ne tranche pas'


def effet_des_signaux(F):
    """Pour chaque signal de circuit : sur les matchs où il joue, log loss sans lui moins log loss avec (> 0 : il aide)
    et son décalage moyen vers le favori annoncé (> 0 : il rend le favori plus favori)."""
    out = {}
    for s in sorted({s for r in F for s in r.get('decalages') or {}}):
        G = [r for r in F if s in (r.get('decalages') or {})]
        gains = [ll(r['z_fiche'] - r['decalages'][s]) - ll(r['z_fiche']) for r in G]
        vers_fav = [r['decalages'][s] * (1 if r['z_fiche'] > 0 else -1) for r in G]
        n = len(G)
        m = sum(gains) / n
        et = math.sqrt(sum((v - m) ** 2 for v in gains) / max(n - 1, 1)) / math.sqrt(n)
        out[s] = {'matchs': n, 'gain_log_loss': round(m, 4), 'erreur_type': round(et, 4),
                  'decalage_moyen_vers_le_favori': round(sum(vers_fav) / n, 3)}
    return out


def pentes_note_v3(racine):
    """{'CH|1': pente moyenne des cases de la note v3 de cette classe (pondérée par ses matchs)} — la note v3 en place
    (simulateur/rapport_fiabilite_v3.json, apprise sur l'archive 2016–2022)."""
    try:
        with open(os.path.join(racine, 'simulateur', 'rapport_fiabilite_v3.json'), encoding='utf-8') as f:
            mod = json.load(f).get('modele') or {}
    except (OSError, ValueError):
        return {}
    out = {}
    for c in CIRCUITS:
        for i in range(4):
            ks = [k for k in mod if k.startswith(f'{c}|{i}|') and isinstance(mod[k], dict)]
            w = sum(mod[k].get('matchs', 0) for k in ks)
            if w:
                out[f'{c}|{i}'] = round(sum(mod[k]['pente'] * mod[k]['matchs'] for k in ks) / w, 3)
    return out


def decrire_direct(L, rejeu_c, criteres=None, note_v3=None):
    par_classe, par_case, accords = {}, {}, {}
    note_v3 = note_v3 or {}
    for c in CIRCUITS:
        for i in range(4):
            G = [r for r in L if r['c'] == c and classe_experience(r['n']) == i]
            k = f"{c}|{i}"
            F = [r for r in G if 'z_fiche' in r]
            par_classe[k] = {'circuit': NOM_CIRCUIT[c], 'classe': NOM_CLASSE[i], 'publie': decrire([r['z'] for r in G]),
                             'elo_seul': decrire([r['z_elo'] for r in G if r.get('z_elo') is not None]),
                             'simulation_seule': decrire([r['z_simulation'] for r in G if r.get('z_simulation') is not None]),
                             'fiche_avec_signaux': decrire([r['z_fiche'] for r in F]),
                             'fiche_sans_signaux': decrire([r['z_sans'] for r in F]),
                             'chaque_signal': effet_des_signaux(F)}
            ref, dref = reference(rejeu_c, c, i)
            accords[k] = {'circuit': NOM_CIRCUIT[c], 'classe': NOM_CLASSE[i],
                          'pente_de_la_note_v3': note_v3.get(k),
                          'rejeu_pente': (dref or {}).get('pente'), 'rejeu_matchs': (dref or {}).get('matchs', 0),
                          'direct_pente': par_classe[k]['publie'].get('pente'),
                          'direct_matchs': par_classe[k]['publie'].get('matchs', 0),
                          'direct_elo_seul_pente': par_classe[k]['elo_seul'].get('pente'),
                          'verdict': verdict(ref, par_classe[k]['publie']),
                          'verdict_elo_seul': verdict(ref, par_classe[k]['elo_seul'])}
            for a in range(3):
                H = [r for r in F if classe_ampleur(r['ampleur']) == a]
                if H:
                    par_case[f"{c}|{i}|{a}"] = {'circuit': NOM_CIRCUIT[c], 'classe': NOM_CLASSE[i], 'ampleur': NOM_AMPLEUR[a],
                                                'publie': decrire([r['z'] for r in H]),
                                                'sans_signaux': decrire([r['z_sans'] for r in H])}
    V = [r for r in L if r.get('niveau')]
    par_niveau = {}
    for nv in NIVEAUX:
        G = [r for r in V if r['niveau'] == nv]
        if not G:
            continue
        par_niveau[nv] = {'tout': decrire([r['z'] for r in G]), 'composition': {}}
        for c in CIRCUITS:
            for i in range(4):
                H = [r for r in G if r['c'] == c and classe_experience(r['n']) == i]
                if H:
                    par_niveau[nv]['composition'][f"{c}|{i}"] = {'matchs': len(H), **{
                        kk: vv for kk, vv in decrire([r['z'] for r in H]).items()
                        if kk in ('favori_annonce_pct', 'favori_reel_pct', 'pente', 'ecart_a_l_attendu')}}
    sig = {}
    for r in L:
        for s in r.get('signaux') or []:
            sig.setdefault(f"{r['c']}|{classe_experience(r['n'])}", {}).setdefault(s, 0)
            sig[f"{r['c']}|{classe_experience(r['n'])}"][s] += 1
    jours = sorted(r['jour'] for r in L if r['jour'])
    return {'matchs': len(L), 'du': jours[0] if jours else None, 'au': jours[-1] if jours else None,
            'avec_fiche': sum('z_fiche' in r for r in L), 'note_v3': len(V),
            'par_classe': par_classe, 'par_case': par_case, 'accord_avec_le_rejeu': accords,
            'par_niveau_note_v3': par_niveau, 'signaux_appliques_par_classe': sig,
            'criteres_fragiles': criteres or {}}


def criteres_fragiles(racine):
    """Chaque critère « fragile » (simulateur/surveillance_fragilite.py), sur tous nos matchs, groupe contre reste."""
    import surveillance_fragilite as SF
    ancien = SF.SEMAINES
    try:
        SF.SEMAINES = 520
        R = SF.lignes(racine, dt.date.today())
    finally:
        SF.SEMAINES = ancien
    try:
        actifs = set(SF.actifs(racine))
    except Exception:  # noqa: BLE001
        actifs = set()
    Z = lambda G: [_lg(r['p']) if r['y'] else -_lg(r['p']) for r in G]  # noqa: E731
    out = {}
    for k, (libelle, f) in SF.CRITERES.items():
        G = [r for r in R if f(r)]
        A = [r for r in R if not f(r)]
        out[k] = {'libelle': libelle, 'actif': k in actifs, 'groupe': decrire(Z(G)),
                  'reste': {kk: vv for kk, vv in decrire(Z(A)).items() if kk != 'par_tranche'}}
    return out


def corrections_en_place(racine):
    out = []
    try:
        with open(os.path.join(racine, 'simulateur', 'correction_niveaux.json'), encoding='utf-8') as f:
            for c, v in (json.load(f).get('corrections') or {}).items():
                for nv, x in v.items():
                    out.append({'quoi': f"{NOM_CIRCUIT.get(c, c)}, niveau « {nv} »", 'pente': x.get('pente'),
                                'active_le': x.get('active_le'), 'retiree': bool(x.get('retiree')), 'paquet': 270,
                                'signal': 'niveau_fiabilite'})
    except (OSError, ValueError):
        pass
    try:
        with open(os.path.join(racine, 'simulateur', 'corrections_chercheur.json'), encoding='utf-8') as f:
            for x in json.load(f).get('corrections') or []:
                out.append({'quoi': f"{NOM_CIRCUIT.get(x.get('circuit'), x.get('circuit'))}, surface {x.get('surface')}",
                            'pente': x.get('pente'), 'active_le': x.get('active_le'), 'retiree': bool(x.get('retire')),
                            'paquet': 322, 'signal': 'terre_challenger'})
    except (OSError, ValueError):
        pass
    try:
        with open(os.path.join(racine, 'simulateur', 'pente_cases.json'), encoding='utf-8') as f:
            for c, x in (json.load(f).get('circuits') or {}).items():
                out.append({'quoi': f"{NOM_CIRCUIT.get(c, c)}, pente de chaque case (archive)", 'active_le': x.get('active_le'),
                            'retiree': bool(x.get('retire')), 'paquet': 318})
    except (OSError, ValueError):
        pass
    return out


# ------------------------------------------------------------------ journal
def fr(v):
    return str(v).replace('.', ',')


def phrase_resultats(doc):
    morceaux = []
    for k, v in doc['direct']['accord_avec_le_rejeu'].items():
        if v['rejeu_matchs'] < MIN_LISIBLE:
            continue
        nv3 = f" (note v3 : {fr(v['pente_de_la_note_v3'])})" if v.get('pente_de_la_note_v3') is not None else ''
        morceaux.append(f"{v['circuit']} {v['classe']} : pente {fr(v['rejeu_pente'])} au rejeu ({v['rejeu_matchs']} matchs){nv3}, "
                        f"{fr(v['direct_pente'])} publiée en direct et {fr(v['direct_elo_seul_pente'])} pour l'Elo seul "
                        f"({v['direct_matchs']} matchs) — {v['verdict']}")
    niv = doc['direct'].get('par_niveau_note_v3') or {}
    if niv:
        morceaux.append('en direct par niveau : ' + ', '.join(
            f"{n} pente {fr(x['tout']['pente'])} ({x['tout']['matchs']} matchs)" for n, x in niv.items()))
    return ' ; '.join(morceaux) + '.'


def entree_journal(doc, gabarit):
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + ' CHIFFRES : ' + phrase_resultats(doc) + ' Le % de victoire ne change pas.',
            'garde_fou': gabarit['garde_fou']}


def ajouter_au_journal(chemin, entree):
    with open(chemin, encoding='utf-8') as f:
        doc = json.load(f)
    L = doc.setdefault('changements', [])
    for i, x in enumerate(L):
        if x.get('paquet') == entree['paquet']:
            L[i] = entree
            break
    else:
        L.append(entree)
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')


def afficher(doc):
    """Ce qui part dans le journal du run (public) : comptes et pentes seulement."""
    for c in CIRCUITS:
        b = doc['rejeu']['circuits'][c]
        print(f"== {NOM_CIRCUIT[c]} — rejeu comme en production (référence : {b['reference']})")
        for i in range(4):
            pc = b['par_classe'][str(i)]
            print('   ', pc['classe'], ' | '.join(f"{n} : {x.get('matchs', 0)} m., pente {x.get('pente')}, annoncé "
                                                 f"{x.get('favori_annonce_pct')} / réel {x.get('favori_reel_pct')}"
                                                 for n, x in pc.items() if isinstance(x, dict)))
    print('== Direct', doc['direct']['matchs'], 'matchs', doc['direct']['du'], '→', doc['direct']['au'])
    for k, v in doc['direct']['accord_avec_le_rejeu'].items():
        print('   ', k, v)
    for nv, v in doc['direct']['par_niveau_note_v3'].items():
        t = v['tout']
        print('   niveau', nv, t['matchs'], 'm., pente', t['pente'], 'écart à l\'attendu', t['ecart_a_l_attendu'])
    for k, v in doc['direct']['criteres_fragiles'].items():
        print('   critère', k, 'actif' if v['actif'] else '', v['groupe'].get('matchs'), 'm., pente', v['groupe'].get('pente'),
              'contre', v['reste'].get('pente'))


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows, n_itf = rejeu(archive, racine)
    rj = decrire_rejeu(rows)
    try:
        crit = criteres_fragiles(racine)
    except Exception as e:  # noqa: BLE001
        crit = {'_erreur': type(e).__name__}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'nature': 'analyse seule : aucune correction proposée ni appliquée',
           'cases': ("circuit | expérience du moins connu (0 : < 30, 1 : 30–99, 2 : 100–299, 3 : 300 +) ; en direct, | ampleur "
                     "des signaux (0 : nulle, 1 : < 0,15, 2 : ≥ 0,15)"),
           'regle_de_lecture': ("case lisible à partir de 1 000 matchs ; « trop sûrs » si pente + 2 erreurs types < 1, « trop "
                                "timides » si pente − 2 erreurs types > 1 ; référence Challenger : rejeu 2025 → mai 2026 "
                                "(ITF hommes compris) ; ATP / WTA : 2018–2022 et 2023 → mai 2026, même sens exigé ; le "
                                "direct confirme ou contredit, il ne décide pas"),
           'rejeu': {'elo': "de production, résultats ITF hommes compris, mis à jour après chaque match ; Elo seul (sans "
                            "signaux ni simulation)", 'itf_hommes_dans_le_rejeu': n_itf, 'circuits': rj},
           'direct': decrire_direct(lignes_direct(racine), rj, crit, pentes_note_v3(racine)),
           'note_v3_en_place': ("pentes de cases apprises sur l'archive 2016–2022 (rapport_fiabilite_v3.json), où l'Elo "
                                "Challenger n'a pas les résultats ITF hommes ; la note d'un match = 100 · min(a, 1/a)"),
           'corrections_en_place': corrections_en_place(racine)}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    ajouter_au_journal(JOURNAL, doc['entree_journal'])
    afficher(doc)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
