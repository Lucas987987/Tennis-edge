#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
allsports.py — client d'AllSportsApi (RapidAPI, allsportsapi2.p.rapidapi.com), 26/11/2026.

Même auteur et mêmes réponses que TennisApi, avec son propre quota : formule Pro (requêtes
illimitées, 6 par seconde) activée par Lucas le 26/11/2026 pour un mois, puis retour possible
à la formule gratuite (100 par jour). Le quota de TennisApi n'est jamais touché.

  • 5 requêtes par seconde au plus (pause entre deux requêtes) ;
  • un 429 (trop rapide) : une pause de 3 s et UNE nouvelle tentative ;
  • 401/403 (abonnement absent) ou quota restant ≤ réserve : arrêt propre (Arret) ;
  • budget de temps : arrêt propre quand il est dépassé, pour laisser le temps de publier.
Le journal ne montre jamais la clé.
"""
import gzip
import json
import os
import time
import urllib.error
import urllib.request

HOTE = 'allsportsapi2.p.rapidapi.com'
PAUSE = float(os.environ.get('ALLSPORTS_PAUSE', '0.2'))
RESERVE = int(os.environ.get('ALLSPORTS_RESERVE', '20'))


class Arret(Exception):
    pass


class Client:
    def __init__(self, cle, minutes=None, reserve=RESERVE, ouvrir=None, pause=PAUSE, horloge=time.monotonic,
                 dormir=time.sleep):
        self.cle, self.reserve, self.pause = cle, reserve, pause
        self.ouvrir = ouvrir or urllib.request.urlopen
        self.horloge, self.dormir = horloge, dormir
        self.fin = horloge() + minutes * 60 if minutes else None
        self.n, self.restant, self.codes, self.octets, self.dernier = 0, None, {}, 0, None

    def _une(self, chemin):
        if self.dernier is not None and self.pause:
            attente = self.pause - (self.horloge() - self.dernier)
            if attente > 0:
                self.dormir(attente)
        self.dernier = self.horloge()
        self.n += 1
        req = urllib.request.Request(f"https://{HOTE}{chemin}", headers={
            'X-RapidAPI-Key': self.cle, 'X-RapidAPI-Host': HOTE, 'Accept': 'application/json'})
        brut, ent = b'', {}
        try:
            with self.ouvrir(req, timeout=40) as r:
                code = r.status
                ent = {k.lower(): v for k, v in dict(r.headers).items()}
                brut = r.read()
        except urllib.error.HTTPError as e:
            code = e.code
            ent = {k.lower(): v for k, v in dict(e.headers or {}).items()}
        except Exception as e:  # noqa: BLE001
            code = type(e).__name__
        self.codes[code] = self.codes.get(code, 0) + 1
        self.octets += len(brut or b'')
        try:
            self.restant = int(ent.get('x-ratelimit-requests-remaining'))
        except (TypeError, ValueError):
            pass
        return code, brut

    def get(self, chemin):
        """(code, json | None). Lève Arret (temps écoulé, abonnement absent, quota bas)."""
        if self.fin is not None and self.horloge() >= self.fin:
            raise Arret('temps du passage écoulé')
        if self.restant is not None and self.restant <= self.reserve:
            raise Arret(f'quota restant {self.restant} ≤ réserve {self.reserve}')
        code, brut = self._une(chemin)
        if code == 429:
            self.dormir(3)
            code, brut = self._une(chemin)
        if code in (401, 403):
            raise Arret(f'{code} : abonnement absent ou clé refusée')
        if code == 429:
            raise Arret('429 répété : limite de requêtes')
        try:
            return code, (json.loads(brut.decode('utf-8', 'replace')) if brut else None)
        except ValueError:
            return code, None

    def bilan(self):
        return (f"{self.n} requêtes, codes {dict(sorted((str(k), v) for k, v in self.codes.items()))}, "
                f"{self.octets / 1e6:.1f} Mo, quota restant {self.restant}")


def lire_jsonl(p):
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            return [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        return None


def ecrire_jsonl(p, lignes):
    """Écrit un .jsonl.gz reproductible (mtime 0), seulement si le contenu change."""
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    txt = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n' for r in lignes)
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            if f.read() == txt:
                return False
    except OSError:
        pass
    with open(p + '.tmp', 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as g:
            g.write(txt.encode('utf-8'))
    os.replace(p + '.tmp', p)
    return True
