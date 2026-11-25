# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 433) — direct poussé (WebSocket /live/flux) avec retour automatique à la redemande de /live."""
import pathlib

R = pathlib.Path(__file__).resolve().parent.parent
P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')
W = (R / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')
T = (R / 'workers' / 'algo' / 'wrangler.toml').read_text(encoding='utf-8')


def test_page():
    assert "new WebSocket('wss://' + location.host + '/live/flux')" in P
    assert 'if (fluxActif()) return;' in P and 'setInterval(chargerLive, 3000)' in P      # secours toujours là
    assert "if (document.hidden) fermerFlux(); else { ouvrirFlux();" in P
    assert 'o.maj < LIVE.majVu' in P                                                      # pas de retour en arrière
    assert '[2e3, 5e3, 15e3, 60e3]' in P and 'ev.code === 4000 ? 3600e3' in P


def test_worker_et_config():
    assert 'export class DirectLive' in W and "url.pathname === '/live/flux'" in W
    assert 'FLUX_MAX_TOURS_JOUR = 45000' in W and 'FLUX_MAX_CONNEXIONS = 5000' in W
    assert "new WebSocketRequestResponsePair('ping', 'pong')" in W
    assert "connect-src 'self' wss://gamesetalgo.com wss://algo.tennis-edge.workers.dev;" in W
    assert 'class_name = "DirectLive"' in T and 'new_sqlite_classes = ["DirectLive"]' in T
    i = W.index('export class DirectLive'); bloc = W[i:W.index('async function flux(', i)]
    for mot in ('RAPIDAPI_KEY', 'march', 'Pinnacle', 'http'):                             # rien d'autre que live()
        assert mot not in bloc.replace('https://interne/live', ''), mot


def test_mesure_tennisapi_privee():
    assert 'conso: undefined' in W                                     # jamais renvoyée par /live
    assert "export const CONSO_R2 = 'prive/tennisapi_conso.json'" in W
    V = (R / 'workers' / 'algo' / 'ventes.js').read_text(encoding='utf-8')
    C = (R / 'workers' / 'algo' / 'comptes.js').read_text(encoding='utf-8')
    assert 'export async function consoTennisApi(env)' in V and 'tennisapi: await consoTennisApi(env)' in V
    assert "tapi(o.tennisapi||[])" in C
