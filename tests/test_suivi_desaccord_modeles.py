"""Paquet 383 — piste suivie : désaccords stats / simulation en Challenger (règle écrite le 23/11/2026)."""
import gzip
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import suivi_desaccord_modeles as S  # noqa: E402


def _racine(tmp, matchs):
    """matchs : [(uid, jour, circuit, comb, stats, simu, gagnant, interrompu)]"""
    os.makedirs(tmp / 'simulateur' / 'journal_pronostics')
    os.makedirs(tmp / 'Tennis_Edge_Lab' / 'live')
    with gzip.open(tmp / 'simulateur' / 'journal_pronostics' / '2026-11-24.jsonl.gz', 'wt', encoding='utf-8') as f:
        for uid, j, c, pc, ps, pm, *_ in matchs:
            for passage, k in ((f'{j}T08:00:00Z', 0.5), (f'{j}T11:00:00Z', 1.0), (f'{j}T13:00:00Z', None)):
                q = lambda p: 0.99 if k is None else (0.5 if k == 0.5 else p)  # noqa: E731
                f.write(json.dumps({'uid': uid, 'passage': passage, 'debut_utc': f'{j}T12:00:00+00:00', 'circuit': c,
                                    'home': 'A', 'away': 'B', 'combinaison': {'p_home': q(pc)},
                                    'stats': {'p_home': q(ps)}, 'simulation': {'p_home': q(pm)}}) + '\n')
    res = [{'uid': m[0], 'reel': {'gagnant': m[6], 'interrompu': m[7]}} for m in matchs]
    json.dump({'matchs': res}, open(tmp / 'Tennis_Edge_Lab' / 'live' / 'pronostics_resultats.json', 'w'))
    return str(tmp)


def test_seuls_les_desaccords_juges_apres_le_debut_comptent(tmp_path):
    r = _racine(tmp_path, [
        ('u1', '2026-11-24', 'CH', 0.55, 0.40, 0.70, 'away', None),   # désaccord, juge
        ('u2', '2026-11-24', 'CH', 0.60, 0.60, 0.65, 'home', None),   # accord : ignoré
        ('u3', '2026-11-23', 'CH', 0.55, 0.40, 0.70, 'away', None),   # avant le début du jugement
        ('u4', '2026-11-25', 'CH', 0.55, 0.40, 0.70, 'away', 'abandon'),
        ('u5', '2026-11-25', 'WTA', 0.45, 0.60, 0.30, 'home', None),
    ])
    assert S.main(['x', r]) == 0
    stock = json.load(open(os.path.join(r, S.STOCK)))['matchs']
    assert sorted(x['c'] for x in stock.values()) == ['CH', 'WTA']
    assert all(len(k) == 16 and 'u' not in k[:0] for k in stock)        # empreinte, pas l'uid
    ch = [x for x in stock.values() if x['c'] == 'CH'][0]
    assert (ch['comb'], ch['stats'], ch['y']) == (0.55, 0.4, 0)          # dernier passage AVANT le début
    R = json.load(open(os.path.join(r, S.SORTIE)))
    assert R['statut'] == 'en cours' and R['challenger']['matchs'] == 1 and R['challenger']['gain_log_loss'] > 0
    assert S.main(['x', r]) == 0                                            # un match déjà jugé n'est pas recompté
    assert len(json.load(open(os.path.join(r, S.STOCK)))['matchs']) == 2


def _stock(n, gain_pos=True, moitie_contraire=False):
    out = []
    for i in range(n):
        y = i % 3 != 0
        bon = gain_pos and not (moitie_contraire and i >= n // 2)
        out.append({'c': 'CH', 'd': f'2026-12-{1 + i * 28 // n:02d}', 'y': int(y),
                    'comb': 0.5, 'stats': (0.62 + 0.05 * (i % 2) if y else 0.38) if bon else (0.42 if y else 0.58 + 0.05 * (i % 2)), 'simu': 0.5})
    return out


def test_decision_a_1000_cas():
    assert S.decision(_stock(999))[0] == 'en cours'
    st, m, raisons = S.decision(_stock(1000))
    assert st == 'retenue' and not raisons and m['erreurs_types'] >= 2
    st, _, raisons = S.decision(_stock(1000, gain_pos=False))
    assert st == 'écartée' and raisons
    st, _, raisons = S.decision(_stock(1000, moitie_contraire=True))
    assert st == 'écartée' and 'pas le même sens sur les deux moitiés' in raisons


def test_aucun_nom_ni_cote_dans_les_sorties(tmp_path):
    r = _racine(tmp_path, [('2026-11-24_jean_dupont_paul_martin', '2026-11-24', 'CH', 0.55, 0.40, 0.70, 'away', None)])
    S.main(['x', r])
    for f in (S.STOCK, S.SORTIE):
        t = open(os.path.join(r, f), encoding='utf-8').read().lower()
        assert 'dupont' not in t and 'pinnacle' not in t and 'cote' not in t and 'marché' not in t
