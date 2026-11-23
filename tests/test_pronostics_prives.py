"""Paquet 378 — les pronostics à venir ne sont plus dans le dépôt public (publication différée)."""
import gzip
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import pronostics_prives as PP  # noqa: E402

MAINTENANT = '2026-11-23T12:00'


class FauxR2:
    def __init__(self):
        self.m = {}

    def list(self, prefix):
        return [(k, len(v)) for k, v in sorted(self.m.items()) if k.startswith(prefix)]

    def get_with_etag(self, k):
        return (self.m[k], 'e') if k in self.m else None

    def put(self, k, data, **kw):
        self.m[k] = bytes(data)


def _monde(r):
    os.makedirs(os.path.join(r, 'algo'))
    os.makedirs(os.path.join(r, PP.FICHES))
    m = lambda u, d, p: {'uid': u, 'debut': d, 'home': 'A', 'away': 'B', 'p_home': p, 'simulation': {'n': 1}}
    doc = {'match_du_jour': {'uid': 'u3'}, 'pronostics_du': 'x',
           'matchs': [m('u1', '2026-11-23T10:00', .61), m('u2', '2026-11-23T15:00', .77), m('u3', '2026-11-23T18:00', .66)]}
    json.dump(doc, open(os.path.join(r, PP.DONNEES), 'w'))
    lignes = [{'uid': 'u1', 'debut': '2026-11-23T10:00', 'p': .61}, {'uid': 'u2', 'debut': '2026-11-23T15:00', 'p': .77}]
    open(os.path.join(r, PP.LOG), 'w').write(''.join(json.dumps(l) + '\n' for l in lignes))
    with gzip.open(os.path.join(r, PP.JOURNAL, '2026-11-23.jsonl.gz'), 'wt') as f:
        f.write(''.join(json.dumps(l) + '\n' for l in lignes))
    with gzip.open(os.path.join(r, PP.FICHES, '2026-11-23.json.gz'), 'wt') as f:
        json.dump({'u1': {'debut': '2026-11-23T10:00', 'premier': {'p': .6}}, 'u2': {'debut': '2026-11-23T15:00'}}, f)


def test_version_publique_ne_garde_que_les_matchs_commences(tmp_path):
    r = str(tmp_path)
    _monde(r)
    b = PP.rendre_public(r, MAINTENANT)
    assert b[PP.LOG] == (1, 2)
    log = open(os.path.join(r, PP.LOG)).read()
    assert '"u1"' in log and '"u2"' not in log and '0.77' not in log
    j = gzip.open(os.path.join(r, PP.JOURNAL, '2026-11-23.jsonl.gz'), 'rt').read()
    assert '"u2"' not in j and '"u1"' in j
    fi = json.load(gzip.open(os.path.join(r, PP.FICHES, '2026-11-23.json.gz'), 'rt'))
    assert set(fi) == {'u1'}
    d = json.load(open(os.path.join(r, PP.DONNEES)))
    par = {m['uid']: m for m in d['matchs']}
    assert par['u3']['p_home'] == .66                 # le match du jour, offert
    assert par['u2'].get('verrou') and 'p_home' not in par['u2']
    assert par['u1'].get('verrou') and 'sets' not in par['u1']        # 390 : commencé → au plus le % de l'algo
    assert d['pronostics_du'] == 'x'                  # fraîcheur lue par les contrôles de la chaîne


def test_coffre_push_pull_et_garde_fou(tmp_path, monkeypatch):
    r = str(tmp_path)
    _monde(r)
    R = FauxR2()
    # premier passage : coffre vide → la version complète part au coffre
    assert PP.pull(R, r) == 0
    assert PP.push(R, r) == 0
    assert b'0.77' in R.m[PP.PREFIXE + PP.LOG]
    PP.rendre_public(r, MAINTENANT)
    # passage suivant SANS rapatriement : la copie publique n'écrase jamais le coffre
    os.remove(os.path.join(r, PP.MARQUE))
    assert PP.push(R, r) == 1
    assert b'0.77' in R.m[PP.PREFIXE + PP.LOG]
    # rapatriement : la version complète revient, un nouveau pronostic s'ajoute, seul le fichier changé repart
    assert PP.pull(R, r) == 4
    assert '0.77' in open(os.path.join(r, PP.LOG)).read()
    with open(os.path.join(r, PP.LOG), 'a') as f:
        f.write(json.dumps({'uid': 'u4', 'debut': '2026-11-24T10:00', 'p': .58}) + '\n')
    envoyes = []
    vrai_put = R.put
    R.put = lambda k, d, **kw: (envoyes.append(k), vrai_put(k, d))
    assert PP.push(R, r) == 0
    assert envoyes == [PP.PREFIXE + PP.LOG]
    # lecteur : seulement le site complet, sans devenir rédacteur
    os.remove(os.path.join(r, PP.MARQUE))
    assert PP.pull(R, r, 'algo/donnees.json') == 1
    assert not os.path.exists(os.path.join(r, PP.MARQUE))


def test_workflows_branches():
    W = os.path.join(RACINE, '.github', 'workflows')
    q = open(os.path.join(W, 'pronostics_quotidien.yml'), encoding='utf-8').read()
    assert 'pronostics_prives.py pull .' in q and 'pronostics_prives.py push .' in q and 'pronostics_prives.py public .' in q
    assert q.index('pronostics_prives.py push .') < q.index('pronostics_prives.py public .') < q.index('git commit -m "Pronostics du jour')
    for f in ('pages.yml', 'classements_du_jour.yml', 'video_simulation.yml', 'video_resume.yml', 'qualite_donnees.yml',
              'arena_cartes_existantes.yml'):
        assert 'pronostics_prives.py pull .' in open(os.path.join(W, f), encoding='utf-8').read(), f
    assert 'pronostics_prives.py rendre .' in open(os.path.join(W, 'qualite_donnees.yml'), encoding='utf-8').read()
