# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 435) — surveillance du site : un message à la panne, un au retour, rien entre les deux."""
import importlib.util
import pathlib

R = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('surv', R / 'scripts' / 'surveillance_site.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def test_verifier_tout_va_bien():
    def lec(url):
        return (200, '<title>Game Set Algo</title>', 0.2) if url.endswith('/') else (200, '{"ok":true}', 0.1)
    assert S.verifier(lec, pause=lambda s: None) == []


def test_verifier_retente_une_fois():
    vus = []
    def lec(url):
        vus.append(url)
        if url.endswith('/') and vus.count(url) == 1:
            return 522, '', 1.0                                    # petite coupure, puis ça revient
        return (200, 'Game Set Algo', 0.2) if url.endswith('/') else (200, '{}', 0.1)
    assert S.verifier(lec, pause=lambda s: None) == []


def test_verifier_panne():
    pbs = S.verifier(lambda url: (503, '', 0.1), pause=lambda s: None)
    assert pbs == ['accueil : HTTP 503', 'worker : HTTP 503']


def test_un_message_par_changement_d_etat():
    assert S.message(['accueil : HTTP 503'], False).startswith('🔴')
    assert S.message(['accueil : HTTP 503'], True) is None          # toujours en panne : pas de nouveau message
    assert S.message([], True).startswith('🟢')
    assert S.message([], False) is None


def test_workflow_et_pas_de_fausse_visite():
    W = (R / '.github' / 'workflows' / 'surveillance_site.yml').read_text(encoding='utf-8')
    assert "cron: '*/10 * * * *'" in W and 'run: python3 scripts/surveillance_site.py' in W
    assert 'actions: read' in W
    assert all('/site.json' not in u for _, u, _ in S.VERIFS)       # site.json compterait une visite
    assert all('/live' != u[-5:] for _, u, _ in S.VERIFS)           # /live pourrait appeler TennisApi


def test_hebergeur_cloudflare_en_premier():
    P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    i = P.index('const heb = `'); ligne = P[i:P.index('\n', i)]
    assert ligne.index('Cloudflare, Inc.') < ligne.index('GitHub, Inc.')
    assert "'Copie de secours :'" in ligne


def test_sauvegarde_quotidienne_des_comptes():
    V = (R / 'workers' / 'algo' / 'ventes.js').read_text(encoding='utf-8')
    assert "PREFIXES_SAUVES = ['comptes/u/', 'comptes/codes/', 'factures/']" in V
    assert 'await sauvegarderComptes(env)' in V and 'JOURS_SAUVES = 14' in V
