# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 421) — projections figées contre scores réels, par tranche de %."""
import gzip
import json
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'simulateur'))
import etude_projections_tranches as E  # noqa: E402


def _monter(tmp, n=240):
    jp = tmp / 'simulateur' / 'journal_pronostics'
    jp.mkdir(parents=True)
    (tmp / 'Tennis_Edge_Lab' / 'live').mkdir(parents=True)
    res, lig, pas = [], [], []
    for i in range(n):
        uid = f'2026-11-10_m{i}'
        gagne_fav = i % 10 < 7                                   # le favori (home) gagne 7 fois sur 10
        score = '6-3 6-4' if gagne_fav else '3-6 4-6'
        res.append({'uid': uid, 'circuit': 'CH', 'reel': {'gagnant': 'home' if gagne_fav else 'away', 'score': score}})
        lig.append({'uid': uid, 'lignes': {'favori': 'home', 'meilleur_des': 3, 'set1_home': 0.7, 'tie_break': 0.2,
                                           'set_decisif': 0.3, 'handicap_favori_1.5': 0.6, 'total_plus_18.5': 0.6}})
        pas.append({'uid': uid, 'passage': '2026-11-10T08:00:00Z', 'debut_utc': '2026-11-10T10:00:00+00:00',
                    'meilleur_des': 3, 'combinaison': {'p_home': 0.7, 'sets': {'2-0': 0.5, '2-1': 0.2, '1-2': 0.2, '0-2': 0.1}}})
    # un passage APRÈS le début ne compte jamais, une seconde ligne figée non plus
    pas.append({'uid': 'x', 'passage': '2026-11-10T12:00:00Z', 'debut_utc': '2026-11-10T10:00:00+00:00', 'combinaison': {'p_home': .9}})
    lig.append({'uid': '2026-11-10_m0', 'lignes': {'favori': 'away', 'set1_home': 0.1}})
    res.append({'uid': 'itf', 'circuit': 'ITF', 'reel': {'gagnant': 'home', 'score': '6-0 6-0'}})
    res.append({'uid': 'int', 'circuit': 'CH', 'reel': {'gagnant': 'home', 'score': '6-0', 'interrompu': True}})
    (tmp / 'Tennis_Edge_Lab' / 'live' / 'pronostics_resultats.json').write_text(json.dumps({'matchs': res}))
    (jp / 'lignes_algo_v1.jsonl').write_text('\n'.join(json.dumps(x) for x in lig) + '\n')
    with gzip.open(jp / '2026-11-10.jsonl.gz', 'wt') as f:
        f.write('\n'.join(json.dumps(x) for x in pas) + '\n')


def test_etude(tmp_path):
    _monter(tmp_path)
    R = E.etudier(str(tmp_path))
    assert R['matchs_juges'] == 240                             # ITF, interrompu, passage tardif : exclus
    v = R['projections']['vainqueur']['par_circuit']['TOUS']
    assert v['n'] == 240 and v['annonce_pct'] == 70.0 and v['arrive_pct'] == 70.0
    assert v['tranches']['70-75']['verdict'] == 'tient' and v['avis'] in ('met le modèle en valeur', 'à corriger avant affichage')
    s1 = R['projections']['set1_favori']['par_circuit']['CH']
    assert s1['n'] == 240 and s1['annonce_pct'] == 70.0           # la première ligne figée, vue du favori
    ss = R['projections']['sets_secs_favori']['par_circuit']['TOUS']
    assert ss['annonce_pct'] == 50.0 and ss['arrive_pct'] == 70.0
    tb = R['projections']['tie_break']['par_circuit']['TOUS']
    assert tb['arrive_pct'] == 0.0 and tb['tranches']['80-85']['bon_pct'] == 100.0
    assert R['projections']['total_plus_18.5']['libelle'] == 'Plus de 18,5 jeux dans le match'
    assert list(R['projections'])[:3] == ['vainqueur', 'set1_favori', 'sets_secs_favori']


def test_trop_tot_et_sans_nom(tmp_path):
    _monter(tmp_path, n=60)
    R = E.etudier(str(tmp_path))
    assert R['projections']['vainqueur']['par_circuit']['TOUS']['avis'] == 'trop tôt'
    E.main(['x', str(tmp_path), '--sortie', str(tmp_path / 'r.json')])
    txt = (tmp_path / 'r.json').read_text(encoding='utf-8')
    assert 'm1' not in txt and 'cote' not in txt and 'Pinnacle' not in txt


def test_workflow():
    y = (R / '.github' / 'workflows' / 'etude_projections.yml').read_text(encoding='utf-8')
    assert 'python simulateur/etude_projections_tranches.py .' in y and 'workflow_dispatch:' in y
    assert 'git push --force' not in y and 'simulateur/rapport_projections_tranches.json' in y
