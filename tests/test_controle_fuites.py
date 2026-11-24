# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 416) — contrôle des fuites : aucun pronostic d'un match à venir dans le dépôt public."""
import gzip
import json
import os
import pathlib
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import controle_fuites as CF  # noqa: E402
import pronostics_prives as PP  # noqa: E402


def _site(tmp, matchs, offert=None):
    (tmp / 'algo').mkdir(parents=True, exist_ok=True)
    (tmp / 'algo' / 'donnees.json').write_text(json.dumps({'match_du_jour': {'uid': offert}, 'matchs': matchs}), encoding='utf-8')


def test_detecte_les_formes_de_fuite(tmp_path):
    _site(tmp_path, [{'uid': 'futur', 'debut_utc': '2099-01-01T10:00:00+00:00', 'verrou': True},
                     {'uid': 'offert', 'debut_utc': '2099-01-01T12:00:00+00:00', 'p_home': 0.6},
                     {'uid': 'passe', 'debut_utc': '2000-01-01T10:00:00+00:00'}], offert='offert')
    futurs = CF.matchs_a_venir(str(tmp_path))
    assert futurs == {'futur'}
    f = tmp_path / 'a.jsonl'
    f.write_text(json.dumps({'uid': 'futur', 'combinaison': {'p_home': 0.7}}) + '\n', encoding='utf-8')
    assert CF.fuite_dans(str(f), futurs)
    g = tmp_path / 'b.json'
    g.write_text(json.dumps({'matchs': {'futur': {'pin': [1.5, 2.6], 'p_home': 0.62}}}), encoding='utf-8')
    assert CF.fuite_dans(str(g), futurs)
    h = tmp_path / 'c.jsonl.gz'
    with gzip.open(h, 'wt') as x:
        x.write(json.dumps({'uid': 'futur', 'champion': 0.31}) + '\n')
    assert CF.fuite_dans(str(h), futurs)
    ok = tmp_path / 'd.json'
    ok.write_text(json.dumps({'matchs': [{'uid': 'futur', 'home': 'A', 'away': 'B'}], 'seuils': {'futur': 0.05}}), encoding='utf-8')
    assert not CF.fuite_dans(str(ok), futurs)                     # affiche seule, seuil sans pronostic
    assert not CF.fuite_dans(str(tmp_path / 'algo' / 'donnees.json'), futurs)
    assert CF.main(['x', str(tmp_path), 'a.jsonl', 'd.json']) == 1


def test_match_retarde_reste_prive():
    t = json.dumps({'uid': 'retarde', 'debut': '2026-11-24T12:00'}) + '\n' + json.dumps({'uid': 'parti', 'debut': '2026-11-24T11:00'}) + '\n'
    pub = PP.public_log(t, '2026-11-24T14:00', {'retarde': '2026-11-24T16:15'})
    assert '"retarde"' not in pub and '"parti"' in pub
    assert PP.public_fiches({'retarde': {'debut': '2026-11-24T12:00'}}, '2026-11-24T14:00', {'retarde': '2026-11-24T16:15'}) == {}


def test_branche_dans_les_workflows_et_lab_prive():
    for wf in ('pronostics_quotidien.yml', 'courbes_alertes.yml'):
        y = (R / '.github' / 'workflows' / wf).read_text(encoding='utf-8')
        assert 'python scripts/controle_fuites.py . || true' in y and 'git reset -q -- "$f"' in y, wf
    assert 'Tennis_Edge_Lab/live/pronostics_marche.json' in (R / '.gitignore').read_text(encoding='utf-8')
    import cotes_privees as CP
    assert ('Tennis_Edge_Lab/live/pronostics_marche.json', 'prive/site/Tennis_Edge_Lab/live/pronostics_marche.json') in CP.SITE_LAB
