# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 440) — « Demande à l'algo » complète : 4 thèmes, simulation, stats prévues et historique."""
import json
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent.parent
P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
sys.path.insert(0, str(R / 'scripts'))
import pages_seo as PS  # noqa: E402


def _cat():
    i = P.index('function qaCatalogue(m){')
    return P[i:P.index('\nfunction rendQuestion(m){', i)]


def test_quatre_themes_et_questions():
    assert "['match', {fr:'Match'" in P and "['histo', {fr:'Historique'" in P
    c = _cat()
    for q in ("add('gagne'", "add('set1'", "add('remonte'", "add(`sets_${h}${a}`", "add('decisif'", "add('tb'", "add('total'",
              "add('nb_jeux'", "add('duree'", "add('f_' + c", "add('p_' + c", "add('forme'", "add('apres_s1'", "add('pays'",
              "add('style'", "add('tranche'", "add('algo_joueur'"):
        assert q in c, q
    for k in ('aces', 'doubles_fautes', 'breaks', 'premiere_pct', 'balles_break_obtenues', 'gagnes_1re_pct', 'gagnes_2e_pct',
              'jeux_service_gagnes_pct', 'points_gagnes'):
        assert f"['{k}'," in c, k


def test_historique_dit_qu_il_ne_change_pas_le_pct():
    assert "Historique : il ne change pas le % de ce match." in P
    c = _cat()
    assert c.count('histo: true') >= 6
    for mot in ('marché', 'Pinnacle', 'value', 'pari'):
        assert mot not in c, mot


def test_joueurs_perf_json(tmp_path):
    ms = [{'uid': f'2026-11-{20 - i:02d}_aa_x{i}', 'debut': f'2026-11-{20 - i:02d}T10:00', 'home': 'Aaa Bbb', 'away': f'Xx{i}',
           'tournoi': 'T', 'circuit': 'CH', 'surface': 'Clay', 'premier': {'combinaison': {'p_home': 0.6}},
           'reel': {'gagnant': 'home' if i % 2 else 'away', 'score': '6-4 6-4', 'sets': '2-0'}} for i in range(6)]
    PS.construire({'matchs': ms}, str(tmp_path), maintenant='2026-11-24T12:00', bilans={}, donnees={})
    J = json.loads((tmp_path / 'joueurs_perf.json').read_text(encoding='utf-8'))
    n, a, v, f = J['Aaa Bbb']
    assert (n, a, v) == (6, 0.6, 3) and isinstance(f, int)
    W = (R / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')
    assert "'/joueurs_perf.json': 'joueurs_perf.json'" in W and "lireJson('joueurs_perf.json')" in P
