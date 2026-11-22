"""Paquet 353 — contrôle de la bascule privée (coffre complet, frais, hors du dépôt public)."""
import datetime as dt
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import controle_prive as CPV  # noqa: E402
import cotes_privees as CP  # noqa: E402


class Client:
    def __init__(self, o):
        self.o = o

    def head_object(self, Bucket, Key):
        if Key not in self.o:
            raise KeyError(Key)
        taille, age = self.o[Key]
        return {'ContentLength': taille, 'LastModified': dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=age)}


class FauxR2:
    def __init__(self, o):
        self.client, self.bucket = Client(o), 'b'


INV = [('closing_lines.json', 'chaud/closing_lines.json', 'chauds'),
       ('moves_detail_hist.csv', 'prive/moves_detail_hist.csv', 'mouvements'),
       ('book_lag_report.json', 'prive/book_lag_report.json', 'book_lag'),
       ('paper_trades_set2.jsonl', 'prive/paper_trades_set2.jsonl', 'suivi')]


def _site(age=1):
    return {CP.PREFIXE_SITE_DIRECT + n: (10, age) for n in CP.SITE_DIRECT}


def test_tout_va_bien(monkeypatch):
    monkeypatch.setattr(CPV, 'suivis', lambda c: set())
    r2 = FauxR2({'chaud/closing_lines.json': (10, 1), 'prive/moves_detail_hist.csv': (10, 5),
                 'prive/book_lag_report.json': (10, 500), **_site()})
    d = CPV.controler(r2, 'prive', INV)
    assert d['problemes'] == [] and d['avertissements'] == []
    assert {L['fichier']: L['etat'] for L in d['fichiers']}['paper_trades_set2.jsonl'] == 'jamais créé'  # optionnel


def test_problemes_en_prive_avertissements_sinon(monkeypatch):
    monkeypatch.setattr(CPV, 'suivis', lambda c: {'moves_detail_hist.csv', 'book_lag_report.json'})
    r2 = FauxR2({'chaud/closing_lines.json': (10, 20), 'prive/moves_detail_hist.csv': (10, 5),
                 'prive/book_lag_report.json': (10, 500), **_site()})
    d = CPV.controler(r2, 'prive', INV)
    etats = {L['fichier']: L['etat'] for L in d['fichiers']}
    assert etats['closing_lines.json'].startswith('périmé')
    assert etats['moves_detail_hist.csv'] == 'encore dans le dépôt public'
    assert {p['fichier'] for p in d['problemes']} == {'closing_lines.json', 'moves_detail_hist.csv'}
    assert [p['fichier'] for p in d['avertissements']] == ['book_lag_report.json']  # sans rédacteur régulier
    d = CPV.controler(r2, 'double', INV)
    assert d['problemes'] == [] and len(d['avertissements']) == 1                   # hors « prive » : dans git = normal


def test_absent_et_site(monkeypatch):
    monkeypatch.setattr(CPV, 'suivis', lambda c: set())
    r2 = FauxR2({'chaud/closing_lines.json': (10, 1)})
    d = CPV.controler(r2, 'prive', INV)
    noms = {p['fichier'] for p in d['problemes']}
    assert 'moves_detail_hist.csv' in noms                                          # rédacteur régulier : absent = panne
    assert any(n.startswith('site privé du Lab') for n in noms)


def test_inventaire_complet():
    inv = CPV.inventaire()
    fichiers = [f for f, _, _ in inv]
    assert len(fichiers) == len(set(fichiers))
    for f in ('closing_lines.json', 'moves_detail_hist.csv', 'kalshi_lead_obs.jsonl', 'h18_signal_log.jsonl',
              'players_profile.json', 'direct_matchs.json'):
        assert f in fichiers, f
    assert all(k.startswith(('chaud/', 'prive/')) for _, k, _ in inv)
    for f in CPV.FRAICHEUR_H:
        assert f in fichiers, f


def test_workflow_et_worker():
    y = open(os.path.join(RACINE, '.github', 'workflows', 'controle_prive.yml'), encoding='utf-8').read()
    assert 'types: [controle_prive]' in y and 'contents: read' in y and 'python3 scripts/controle_prive.py' in y
    w = open(os.path.join(RACINE, 'workers', 'tennis-edge-closing', 'worker.js'), encoding='utf-8').read()
    assert "workflowFile: 'controle_prive.yml'" in w and "evenement: 'controle_prive'" in w


def test_pas_encore_au_coffre_mais_dans_git_avertit(monkeypatch):
    # 355 : le jour de la bascule, un fichier encore dans git et pas encore envoyé : avertissement, pas une panne
    monkeypatch.setattr(CPV, 'suivis', lambda c: {'moves_detail_hist.csv'})
    r2 = FauxR2({'chaud/closing_lines.json': (10, 1), **_site()})
    d = CPV.controler(r2, 'prive', INV)
    assert 'moves_detail_hist.csv' not in {p['fichier'] for p in d['problemes']}
    assert 'moves_detail_hist.csv' in {p['fichier'] for p in d['avertissements']}
