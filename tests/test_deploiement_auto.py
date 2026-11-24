# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 412, Lucas) — un paquet qui change un worker le fait redéployer (plus d'étape à la main) ;
texte d'accueil public sans « cotes »."""
import pathlib
import json
import re

R = pathlib.Path(__file__).resolve().parent.parent
WF = R / '.github' / 'workflows'


def test_appliquer_paquet_demande_les_deploiements():
    a = (WF / 'appliquer_paquet.yml').read_text(encoding='utf-8')
    assert 'event_type="deployer-$w"' in a and 'deployer; exit 0' in a
    assert "git diff --cached --name-only | sed -n 's#^workers/" in a
    for f, d in (('deploy_algo', 'algo'), ('deploy_closing', 'tennis-edge-closing'), ('deploy_joueurs', 'joueurs'),
                 ('deploy_tennis_edge_db', 'tennis-edge-db')):
        y = (WF / f'{f}.yml').read_text(encoding='utf-8')
        assert re.search(r'repository_dispatch:\n\s+types: \[deployer-' + re.escape(d) + r'\]', y), f
        assert f'algo|tennis-edge-closing|joueurs|tennis-edge-db' in a


def test_accueil_sans_cotes():
    p = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    for lede in re.findall(r'\n  lede:"([^"]+)"', p):
        assert 'cote' not in lede and 'odds' not in lede, lede


def test_alerte_si_deploiement_echoue():
    for f in ('deploy_algo', 'deploy_closing', 'deploy_joueurs', 'deploy_tennis_edge_db'):
        y = (WF / f'{f}.yml').read_text(encoding='utf-8')
        assert 'Alerte Telegram si le déploiement échoue' in y and 'if: failure()' in y, f
        assert 'curl -s -o /dev/null' in y and 'echo "$TELEGRAM' not in y, f      # jeton jamais affiché


def test_mon_compte_montre_l_abonnement():
    p = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    assert '${blocMonAbonnement()}' in p
    for cle in ('cp_abo_titre', 'cp_abo_fond', 'cp_abo_dem', 'cp_abo_ref', 'cp_abo_voir'):
        assert p.count(cle + ':') == 2, cle


def test_appli_installee_depuis_gamesetalgo_seulement():
    p = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    assert "location.href = 'https://' + HOTE_APPLI + '/?installer=1'" in p and "HOTE_APPLI = 'gamesetalgo.com'" in p
    w = (R / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')
    assert "url.pathname === '/manifest.webmanifest' && !MARQUES.has(url.hostname)" in w


def test_referencement_page():
    p = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
    tete = p[:p.index('</head>')]
    assert '<link rel="canonical" href="https://gamesetalgo.com/">' in tete
    assert '<title>Game Set Algo' in tete and 'hreflang="x-default"' in tete
    i = tete.index('application/ld+json')
    ld = json.loads(tete[tete.index('>', i) + 1:tete.index('</script>', i)])
    noms = [x.get('name') for x in ld['@graph']]
    assert noms == ['Game Set Algo', 'Game Set Algo'] and 'GameSetAlgo' in ld['@graph'][0]['alternateName']
    assert '<h1 class="logo">' in p and 'Chaque match est simulé 20 000 fois' in p[p.index('class="lede"'):][:300]
    for f, u in (('methode.html', 'methode.html'), ('apropos.html', 'apropos.html')):
        assert f'<link rel="canonical" href="https://gamesetalgo.com/{u}">' in (R / 'algo' / f).read_text(encoding='utf-8')
