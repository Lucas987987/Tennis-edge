#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_notes_fiabilite.py — la note de fiabilité affichée tient-elle sa promesse ? (04/11/2026, demande de Lucas)

La note (fiabilite.py) dit « robustesse de l'estimation », pas « chance que le favori gagne ». Ce qu'elle doit donc
prédire : l'écart entre ce qu'on annonce et ce qui arrive. Mesure par match :
    surprise = log loss réelle − log loss attendue,   attendue = −[p ln p + (1−p) ln(1−p)]
(0 en moyenne si nos probabilités sont justes ; > 0 : les résultats nous surprennent plus que nous ne l'annoncions).
Une bonne note : surprise ≈ 0 pour les notes hautes, nettement > 0 pour les notes basses. Lu aussi : réussite du
favori contre réussite annoncée, Brier, par niveau, par tranche de note, par circuit, et pour chaque COMPOSANTE de
la note (laquelle trompe ?). Population : nos pronostics figés jugés après match (pronostics_resultats.json).
Descriptif : aucune règle d'adoption ici ; une correction de la note serait une autre étude, à règle fixée d'avance.
Usage : python simulateur/etude_notes_fiabilite.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, 'rapport_notes_fiabilite.json')
COMPOSANTES = ('donnees', 'accord_modeles', 'calibration', 'performance_circuit', 'profondeur_historique')


def _c(p):
    return min(max(float(p), 1e-6), 1 - 1e-6)


def lignes(racine):
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    out = []
    for m in doc.get('matchs') or []:
        f_ = m.get('fiabilite') or {}
        reel = m.get('reel') or {}
        p = m.get('p_affiche')
        if f_.get('note') is None or p is None or reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        p, y = _c(p), int(reel['gagnant'] == 'home')
        ll = -math.log(p if y else 1 - p)
        att = -(p * math.log(p) + (1 - p) * math.log(1 - p))
        pr = m.get('premier') or {}
        pe, ps = (pr.get('stats') or {}).get('p_home'), (pr.get('simulation') or {}).get('p_home')
        mj = m.get('matchs_joues') or [None, None]
        fav = 0 if p >= .5 else 1
        try:
            avance_h = (dt.datetime.fromisoformat(str(m.get('debut'))[:16]) -
                        dt.datetime.fromisoformat(str(m.get('pronostique_le'))[:16])).total_seconds() / 3600
        except ValueError:
            avance_h = None
        out.append({'surface': m.get('surface'), 'p_elo': pe, 'p_sim': ps, 'xp_fav': mj[fav], 'xp_out': mj[1 - fav],
                    'avance_h': avance_h, 'voisins': ((f_.get('matchs_similaires') or {}).get('ecart_reel_moins_prevu')),
                    'tournoi': m.get('tournoi'),
                    'c': m.get('circuit'), 'note': f_['note'], 'note_v2': f_.get('note_v2'), 'niveau': f_.get('niveau'),
                    'comp': f_.get('composantes') or {}, 'p': p, 'y': y, 'll': ll, 'surprise': ll - att,
                    'fav_gagne': int((p >= .5) == (y == 1)), 'pf': max(p, 1 - p), 'brier': (p - y) ** 2,
                    'jour': str(m.get('debut') or '')[:10]})
    return out


def bloc(R):
    n = len(R)
    if not n:
        return None
    moy = lambda k: sum(r[k] for r in R) / n
    s = moy('surprise')
    et = math.sqrt(sum((r['surprise'] - s) ** 2 for r in R) / max(1, n - 1) / n)
    return {'matchs': n, 'reussite_pct': round(100 * moy('fav_gagne'), 1), 'reussite_annoncee_pct': round(100 * moy('pf'), 1),
            'log_loss': round(moy('ll'), 4), 'surprise': round(s, 4), 'surprise_ic95': [round(s - 1.96 * et, 4), round(s + 1.96 * et, 4)],
            'brier': round(moy('brier'), 4)}


def tranches(R, cle, bornes):
    out = {}
    for lo, hi in zip(bornes[:-1], bornes[1:]):
        sub = [r for r in R if r[cle] is not None and lo <= r[cle] < hi]
        if sub:
            out[f'{lo}–{hi - 1}'] = bloc(sub)
    return out


def tiers(R, f):
    """Trois groupes de taille égale selon f(r) (bas, milieu, haut)."""
    S = sorted([r for r in R if f(r) is not None], key=f)
    k = len(S) // 3
    G = {'bas': S[:k], 'milieu': S[k:2 * k], 'haut': S[2 * k:]}
    return {g: dict(bloc(v), valeurs=[f(v[0]), f(v[-1])]) for g, v in G.items() if v}


def classe(v, bornes, unite=''):
    if v is None:
        return None
    for lo, hi in zip(bornes[:-1], bornes[1:]):
        if lo <= v < hi:
            return f'{lo}–{hi}{unite}'
    return None


DECOUPES = {
    'note (par 5 points)': lambda r: classe(r['note'], list(range(40, 95, 5))),
    'confiance du favori': lambda r: classe(round(100 * r['pf']), [50, 55, 60, 65, 70, 75, 80, 85, 101], ' %'),
    'surface': lambda r: r['surface'],
    'expérience du favori (matchs)': lambda r: classe(r['xp_fav'], [0, 30, 100, 200, 400, 10000]),
    "expérience de l'outsider (matchs)": lambda r: classe(r['xp_out'], [0, 30, 100, 200, 400, 10000]),
    'favori plus expérimenté ?': lambda r: None if r['xp_fav'] is None or r['xp_out'] is None else
        ('oui (×2 ou plus)' if r['xp_fav'] >= 2 * r['xp_out'] else 'non (×2 ou plus pour l’outsider)' if r['xp_out'] >= 2 * r['xp_fav'] else 'comparable'),
    'écart Elo – simulation (points)': lambda r: None if r['p_elo'] is None or r['p_sim'] is None else
        classe(round(100 * abs(r['p_elo'] - r['p_sim'])), [0, 5, 10, 15, 20, 101]),
    'Elo et simulation d’accord sur le favori ?': lambda r: None if r['p_elo'] is None or r['p_sim'] is None else
        ('oui' if (r['p_elo'] >= .5) == (r['p_sim'] >= .5) else 'non'),
    'qui pousse le favori ?': lambda r: None if r['p_elo'] is None or r['p_sim'] is None else
        ('l’Elo plus que la simulation' if abs(r['p_elo'] - .5) > abs(r['p_sim'] - .5) else 'la simulation plus que l’Elo'),
    'pronostic figé combien d’heures avant': lambda r: classe(r['avance_h'], [0, 6, 12, 24, 48, 1000], ' h'),
    'matchs similaires : réel − prévu': lambda r: None if r['voisins'] is None else
        ('voisins sous le prévu (< −3 pts)' if r['voisins'] < -0.03 else 'voisins au-dessus (> +3 pts)' if r['voisins'] > 0.03 else 'voisins justes'),
    'jour du match': lambda r: r['jour'],
    **{f'composante {k}': (lambda r, k=k: classe(r['comp'].get(k), [0, 40, 50, 60, 70, 80, 90, 101])) for k in COMPOSANTES},
}


def decouper(R, min_n=15):
    """Chaque découpe × chaque circuit (et tous) : bloc par case de ≥ min_n matchs ; ★ si l'IC 95 % de la surprise
    exclut 0 (attention : beaucoup de cases, donc des ★ par hasard sont attendus — 1 sur 20)."""
    out = {}
    for nom, f in DECOUPES.items():
        out[nom] = {}
        for c in ('tous', 'ATP', 'WTA', 'CH'):
            Rc = R if c == 'tous' else [r for r in R if r['c'] == c]
            cases = {}
            for r in Rc:
                k = f(r)
                if k is not None:
                    cases.setdefault(k, []).append(r)
            out[nom][c] = {k: dict(bloc(v), signal=bloc(v)['surprise_ic95'][0] > 0 or bloc(v)['surprise_ic95'][1] < 0)
                           for k, v in sorted(cases.items()) if len(v) >= min_n}
    return out


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    R = lignes(racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'definition': ("surprise = log loss réelle − log loss attendue (0 si nos probabilités sont justes ; > 0 : "
                          "moins fiable qu'annoncé). Une bonne note : surprise ≈ 0 en haut, > 0 en bas."),
           'tous': bloc(R),
           'par_niveau': {nv: bloc([r for r in R if r['niveau'] == nv]) for nv in ('fragile', 'prudent', 'correct', 'solide')},
           'par_note': tranches(R, 'note', [0, 50, 60, 70, 80, 90, 101]),
           'tiers_note': tiers(R, lambda r: r['note']),
           'tiers_note_v2': tiers(R, lambda r: r['note_v2']),
           'par_circuit': {c: {'tous': bloc([r for r in R if r['c'] == c]), 'tiers_note': tiers([r for r in R if r['c'] == c], lambda r: r['note'])}
                           for c in ('ATP', 'WTA', 'CH')},
           'composantes': {k: tiers(R, lambda r, k=k: r['comp'].get(k)) for k in COMPOSANTES},
           # la note n'est-elle qu'un reflet de la confiance ? surprise par tiers de note À confiance égale (gros favoris à part)
           'note_selon_confiance': {g: tiers([r for r in R if lo <= r['pf'] < hi], lambda r: r['note'])
                                    for g, (lo, hi) in (('favori 50–65 %', (0.5, 0.65)), ('favori 65 % et plus', (0.65, 1.01)))},
           'decoupes': decouper(R)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
