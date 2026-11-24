# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 412, Lucas) — un paquet qui change un worker le fait redéployer (plus d'étape à la main) ;
texte d'accueil public sans « cotes »."""
import pathlib
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
