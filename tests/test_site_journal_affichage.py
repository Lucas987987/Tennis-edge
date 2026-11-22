"""Paquet 358 — le journal public affiche un titre pour chaque entrée (format « quoi ») et la page ne déborde plus."""
import json
import os
import re
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
HTML = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()


def test_statuts_publics_ont_un_libelle():
    sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
    import vitrine as V
    J = V.journal_changements(RACINE)
    statuts = {str(c.get('statut')) for c in J['changements'] if c.get('statut')}
    import unicodedata
    for st in statuts:
        cle = ''.join(ch for ch in unicodedata.normalize('NFD', st) if unicodedata.category(ch) != 'Mn')
        assert f'jc_{cle}:' in HTML, st


def test_titre_tire_de_quoi():
    assert "if (c.titre) return [c.titre, c.mesure || ''];" in HTML
    assert 'const p_ = q.match(' in HTML and 'NOMS = {atp:' in HTML


def test_chaque_entree_publique_a_de_quoi_faire_un_titre():
    sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
    import vitrine as V
    for c in V.journal_changements(RACINE)['changements']:
        assert c.get('titre') or str(c.get('quoi') or '').strip(), c.get('date')


def test_titres_de_tiroir_peuvent_passer_a_la_ligne():
    assert re.search(r'\.tiroir>summary \.tt\{[^}]*flex:0 1 auto;min-width:0', HTML)
