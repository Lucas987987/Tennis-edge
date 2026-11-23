"""Paquet 375 — envois Telegram coupés sous 4 096 caractères et jamais bloquants (run rouge du 23/11)."""
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import telegram_envoi as TE  # noqa: E402


def test_morceaux_et_echappement():
    t = '\n'.join(f'<b>L{i}</b> a < b & c' for i in range(400))
    M = TE.morceaux(TE.echapper(t))
    assert len(M) > 1 and all(len(m) <= TE.LIMITE for m in M)
    assert '&lt; b &amp; c' in M[0] and '<b>L0</b>' in M[0]
    assert all(m.count('<b>') == m.count('</b>') for m in M)
    assert TE.morceaux('a\n\nb') == ['a\n\nb']
    assert [len(m) for m in TE.morceaux('z' * 9000)] == [4000, 4000, 1000]


def test_envoi_coupe_et_echec_non_bloquant(monkeypatch):
    import urllib.request
    vus = []

    class R:
        def read(self):
            return b'{}'

    def ok(url, data=None, timeout=None):
        vus.append(len(data))
        return R()
    monkeypatch.setattr(urllib.request, 'urlopen', ok)
    assert TE.envoyer('x\n' * 5000, tok='t', chat='c') == 3 and len(vus) == 3

    def ko(*a, **k):
        raise OSError('refus')
    monkeypatch.setattr(urllib.request, 'urlopen', ko)
    assert TE.envoyer('court', tok='t', chat='c') == 0
    monkeypatch.delenv('TELEGRAM_TOKEN', raising=False)
    assert TE.envoyer('sans jeton', chat='c') == 0


def test_rapports_branches():
    for f in ('chercheur', 'etude_algo_cloture', 'etude_marches_derives', 'apres_match', 'suivi_desaccords_pinnacle',
              'roi_algo'):
        assert 'telegram_envoi' in open(os.path.join(RACINE, 'simulateur', f + '.py'), encoding='utf-8').read(), f
    for f in ('canal_clv_recap', 'barometre', 'canal_recap', 'sante_chaine', 'health_check', 'audit_qa'):
        assert '_morceaux_tg(' in open(os.path.join(RACINE, 'scripts', f + '.py'), encoding='utf-8').read(), f


def test_documentation_comptee_par_joueur():
    import collections
    import elo as E
    import etude_documentation as EDO
    import pronostics_du_jour as PJ
    al = {E.cle('Santiago Rodriguez Taverna'): E.cle('Santiago Fa Rodriguez Taverna')}
    n = collections.Counter({E.cle('Santiago Fa Rodriguez Taverna'): 14000, E.cle('Santiago Rodriguez Taverna'): 1500})
    f = EDO.fusionner(n, al)
    assert EDO.balles(f, al, 'Santiago Rodriguez Taverna') == 15500 == EDO.balles(f, al, 'Santiago Fa Rodriguez Taverna')
    avant = (PJ.BALLES_CUMULEES, PJ.ALIAS_BALLES)
    try:
        PJ.BALLES_CUMULEES, PJ.ALIAS_BALLES = dict(f), al
        assert PJ.balles_de('Santiago Rodriguez Taverna') == 15500 and PJ.balles_de('Inconnu') == 0
    finally:
        PJ.BALLES_CUMULEES, PJ.ALIAS_BALLES = avant
