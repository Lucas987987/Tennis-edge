#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kalshi_collector.py — Collecte les prix Kalshi des matchs de tennis.

POURQUOI KALSHI PLUTÔT QUE POLYMARKET
La sonde (kalshi_probe.py, 5 itérations) a établi :
  • couverture ATP, WTA, CHALLENGERS et ITF — Polymarket ne cotait que
    Cincinnati. Les Challengers sont précisément le circuit où les opérateurs
    mous sont les plus lents, donc là où Tennis Edge a le plus de valeur ;
  • 4 de nos 4 matchs complets appariés (100 %) ;
  • volume jusqu'à 7,0 M sur un match, fourchette de 1 point ;
  • aucune authentification pour les données de marché.

CE QUE LA SONDE A APPRIS, ET QUI EST CÂBLÉ ICI
  1. Ne JAMAIS paginer /markets : 199 319 des 200 000 marchés lus étaient des
     paris combinés KXMVECROSSCATEGORY (99,7 % de bruit). On part de /series.
  2. Un marché Kalshi = UN RÉSULTAT, pas un match : « Iga Swiatek wins » et
     « Elena Rybakina wins » sont deux marchés du même event_ticker. L'unité
     d'appariement est donc l'ÉVÉNEMENT.
  3. Le schéma utilise yes_bid_dollars / volume_fp / open_interest_fp, et non
     yes_bid / volume.
  4. La limite de débit publique est bien plus basse que les ~20 req/s des
     comptes authentifiés : 16 req/s donnaient 55 rejets 429 sur 134 séries.

MÉCANIQUE REPRISE DU COLLECTEUR POLYMARKET (éprouvée en production)
  • partitions journalières + bascule à 60 Mo (le mur GitHub est à 100 Mo par
    fichier ; une partition de 221 Mo a fait rejeter un push entier le 19/08) ;
  • limitation de débit d'écriture (un tick par marché toutes les N secondes,
    sauf mouvement réel) — sans elle, 9,7 Go/jour ;
  • ticks maigres : les métadonnées fixes vivent dans le registre, pas répétées
    à chaque ligne ;
  • appariement strict à deux jetons communs (le piège « Tallon Griekspoor »
    vs « Tallon Tien ») ;
  • compteurs de rejet nommés : aucun filtrage silencieux.

DIFFÉRENCE MAJEURE AVEC POLYMARKET : pas de WebSocket ici. Le flux temps réel
Kalshi exige une authentification RSA-PSS même pour les canaux publics. On
interroge donc /markets en REST à intervalle régulier — ce qui suffit
largement pour une analyse sur grille de 5 minutes.

Env : KALSHI_BASE, MATCHES_FILE, KX_TICKS_DIR, KX_MARKETS_FILE, KX_STATE_FILE,
      KX_MIN_INTERVAL_S, KX_MIN_DELTA, KX_TICKS_MAX_MB, KX_PAUSE_S,
      KX_SERIES_REFRESH_S, KX_POLL_S.
Args : --duration-seconds, --once, --dry-run.
"""
import os
import sys
import json
import time
import re
import argparse
import datetime
import unicodedata
import collections
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

BASE       = os.environ.get('KALSHI_BASE', 'https://api.elections.kalshi.com/trade-api/v2')
MATCHES    = os.environ.get('MATCHES_FILE', 'matches_oddspapi.json')
TICKS_DIR  = Path(os.environ.get('KX_TICKS_DIR', 'parts'))
MARKETS_F  = Path(os.environ.get('KX_MARKETS_FILE', 'kalshi_markets.json'))
STATE_F    = Path(os.environ.get('KX_STATE_FILE', 'kalshi_collector_state.json'))
TIMEOUT    = float(os.environ.get('HTTP_TIMEOUT', '25'))

# 0,06 s (16 req/s) provoquait 55 rejets 429 sur 134 séries. 0,3 s = ~3 req/s.
PAUSE      = float(os.environ.get('KX_PAUSE_S', '0.3'))
# Une écriture par marché au plus toutes les N secondes, SAUF mouvement réel.
MIN_INTERVAL_S = float(os.environ.get('KX_MIN_INTERVAL_S', '20'))
MIN_DELTA      = float(os.environ.get('KX_MIN_DELTA', '0.002'))
# Au-delà, nouvelle partition : le mur GitHub est à 100 Mo PAR FICHIER.
TICKS_MAX_MB   = float(os.environ.get('KX_TICKS_MAX_MB', '60'))
# Les séries changent rarement ; les marchés, souvent.
SERIES_REFRESH = float(os.environ.get('KX_SERIES_REFRESH_S', '1800'))
POLL_S         = float(os.environ.get('KX_POLL_S', '60'))

TENNIS_KW = ('tennis', 'atp', 'wta', 'itf', 'challenger', 'wimbledon',
             'us open', 'roland garros', 'australian open', 'slam')
# Écartées : ne portent pas sur le vainqueur du match. Les dernières familles
# sont des faux positifs constatés (tennis de TABLE, échecs, « Taylor's Version »).
HORS_SUJET = ('total', 'spread', 'doubles', 'game winner', 'set ', 'ranked',
              'winner (', 'championship', 'job cuts', 'qualify', 'field winner',
              'exact match score', 'tiebreak', 'reach round',
              'table tennis', 'tt elite', 'ittf', 'chess', 'reputation', 'announce')


# ── Utilitaires ───────────────────────────────────────────────────────────
def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def iso_now():
    return utc_now().isoformat(timespec='milliseconds')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.lower()).strip()


def toks(s):
    return set(t for t in re.split(r'[^a-z0-9]+', norm(s)) if len(t) >= 2)


def joueur_match(nom, blob):
    """DEUX jetons communs minimum. Un seul est presque toujours un prénom
    partagé : « Tallon Griekspoor » et « Tallon Tien » ne sont pas le même
    joueur, et six joueurs du circuit se prénomment « alex »."""
    return len(toks(nom) & toks(blob)) >= 2


def txt(m):
    """Tout le texte d'un objet. Le schéma Kalshi varie selon le type de
    marché : présumer des noms de champs a déjà coûté deux runs."""
    return ' '.join(str(v) for v in m.values() if isinstance(v, str))


def ticks_path():
    """Partition courante. Recalculée à chaque écriture, donc bascule seule à
    minuit ET quand la partition atteint TICKS_MAX_MB."""
    jour = utc_now().strftime('%Y-%m-%d')
    p = TICKS_DIR / f'kx_ticks_{jour}.jsonl'
    seq = 1
    while p.exists() and p.stat().st_size / 1e6 >= TICKS_MAX_MB:
        seq += 1
        p = TICKS_DIR / f'kx_ticks_{jour}_{seq}.jsonl'
    return p


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')


def atomic_json_write(path, obj):
    tmp = Path(str(path) + '.tmp')
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def http_get(path, params=None, essais=4):
    """GET avec repli exponentiel sur 429 — un 429 non retenté est une donnée
    perdue en silence, exactement ce qu'on cherche à éliminer."""
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'TennisEdge-KalshiCollector/1.0'})
    for i in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < essais - 1:
                time.sleep(1.5 * (2 ** i))
                continue
            raise


def prix(m, cle):
    """Kalshi renvoie des dollars (0-1) dans *_dollars. Lire l'ancienne clé en
    centimes donnait None partout."""
    for k in (f'{cle}_dollars', cle):
        v = m.get(k)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        return f if f <= 1.5 else f / 100.0
    return None


def entier(m, *cles):
    for k in cles:
        v = m.get(k)
        if v is None:
            continue
        try:
            return int(float(v))
        except (TypeError, ValueError):
            continue
    return 0


# ── Matchs locaux ─────────────────────────────────────────────────────────
def make_uid(commence, home, away):
    """Même convention que book_curves : <date>_<home>_<away>, pour que les
    ticks se joignent directement aux courbes des bookmakers."""
    return f"{str(commence or '')[:10]}_{norm(home).replace(' ', '_')}_{norm(away).replace(' ', '_')}"


def matchs_locaux():
    if not os.path.exists(MATCHES):
        print(f'⚠️ {MATCHES} introuvable')
        return []
    try:
        d = json.load(open(MATCHES, encoding='utf-8'))
    except Exception as e:
        print(f'⚠️ {MATCHES} illisible : {e}')
        return []
    if isinstance(d, dict):
        d = list(d.values())
    out = []
    for x in d:
        if not isinstance(x, dict):
            continue
        h = x.get('home_team') or x.get('home')
        a = x.get('away_team') or x.get('away')
        if not h or not a:
            continue
        # Tours futurs (Qf3, WSF1...) : l'adversaire n'est pas connu, donc rien
        # ne peut s'apparier. Ils se rempliront au fil du tournoi.
        if re.fullmatch(r'w?[qs]f\d+', norm(h)) or re.fullmatch(r'w?[qs]f\d+', norm(a)):
            continue
        c = x.get('commence_time') or x.get('start_time')
        out.append({'home': h, 'away': a, 'commence': c,
                    'tournoi': x.get('sport_title') or '',
                    'uid': make_uid(c, h, a)})
    return out


# ── Découverte ────────────────────────────────────────────────────────────
def series_tennis():
    """Séries de VAINQUEUR DE MATCH. On part de /series (13 305 entrées, dont
    167 tennis) et non de /markets, noyé à 99,7 % par les paris combinés."""
    try:
        d = http_get('/series')
    except Exception as e:
        print(f'❌ /series injoignable : {e}')
        return []
    series = d.get('series') or (d if isinstance(d, list) else [])
    tennis = [s for s in series if any(k in norm(txt(s)) for k in TENNIS_KW)]
    gardees = [s for s in tennis if not any(k in norm(txt(s)) for k in HORS_SUJET)]

    def rang(s):
        tk = norm(s.get('ticker'))
        return 0 if tk.endswith('match') else 1 if 'match' in tk else 2
    gardees.sort(key=rang)
    print(f'/series : {len(series)} séries · {len(tennis)} tennis · '
          f'{len(gardees)} retenues (vainqueur de match)')
    return gardees


def collecter_marches(series):
    marches, rejets = [], collections.Counter()
    for s in series:
        tk = s.get('ticker')
        if not tk:
            continue
        try:
            r = http_get('/markets', {'series_ticker': tk,
                                      'status': 'open', 'limit': 200})
            marches.extend(r.get('markets') or [])
        except urllib.error.HTTPError as e:
            rejets[f'http_{e.code}'] += 1
        except Exception:
            rejets['erreur_reseau'] += 1
        time.sleep(PAUSE)
    if rejets:
        print(f'   rejets : {dict(rejets)}')
    return marches


def apparier(marches, locaux):
    """Associe chaque ÉVÉNEMENT Kalshi à un match local.

    Un marché = un résultat (« Iga Swiatek wins »), donc un seul joueur nommé.
    Exiger les deux joueurs dans le MÊME marché est impossible par
    construction — c'est ce qui plafonnait l'appariement de la sonde. On
    regroupe donc par event_ticker et on apparie sur le texte cumulé.
    """
    par_event = collections.defaultdict(list)
    for m in marches:
        par_event[str(m.get('event_ticker') or m.get('ticker'))].append(m)

    suivis, rejets = [], collections.Counter()
    for ev, lot in par_event.items():
        blob = ' '.join(txt(m) for m in lot)
        loc = None
        for l in locaux:
            if joueur_match(l['home'], blob) and joueur_match(l['away'], blob):
                loc = l
                break
        if not loc:
            rejets['aucun_match_local'] += 1
            continue
        for m in lot:
            # Quel joueur ce marché désigne-t-il ? Le côté est résolu ICI, une
            # seule fois : sans ça, l'analyse devrait refaire l'appariement de
            # noms sur chaque tick.
            nom = m.get('yes_sub_title') or m.get('title') or ''
            if joueur_match(loc['home'], nom):
                side = 'home'
            elif joueur_match(loc['away'], nom):
                side = 'away'
            else:
                rejets['cote_indetermine'] += 1
                continue
            suivis.append({
                'ticker': m.get('ticker'), 'event_ticker': ev,
                'title': m.get('title'), 'yes_sub_title': m.get('yes_sub_title'),
                'local_uid': loc['uid'], 'local_side': side,
                'home': loc['home'], 'away': loc['away'],
                'commence': loc['commence'], 'tournoi': loc['tournoi'],
                'close_time': m.get('close_time'),
            })
    if rejets:
        print(f'   appariement : {dict(rejets)}')
    return suivis


# ── Écriture des ticks ────────────────────────────────────────────────────
class Ecrivain:
    def __init__(self):
        self._dernier = {}
        self.ecrits = 0
        self.filtres = 0

    def _passe(self, ticker, p):
        """Écrire ? Au plus une fois par MIN_INTERVAL_S, sauf mouvement réel.

        Sur Polymarket, l'absence de ce filtre a produit 312 683 lignes en
        15 min (101 Mo) et fait rejeter un push. Ici la source est du REST
        périodique, donc le débit est déjà borné — mais un sondage à 60 s sur
        200 marchés ferait quand même 288 000 lignes par jour d'un prix
        inchangé.
        """
        prec = self._dernier.get(ticker)
        maintenant = time.monotonic()
        if prec is not None:
            t_prec, p_prec = prec
            bouge = (p is not None and p_prec is not None
                     and abs(p - p_prec) >= MIN_DELTA)
            if not bouge and (maintenant - t_prec) < MIN_INTERVAL_S:
                self.filtres += 1
                return False
        self._dernier[ticker] = (maintenant, p)
        self.ecrits += 1
        return True

    def ecrire(self, suivi, m):
        yb, ya = prix(m, 'yes_bid'), prix(m, 'yes_ask')
        mid = (yb + ya) / 2 if (yb is not None and ya is not None) else None
        if not self._passe(suivi['ticker'], mid):
            return
        # Tick MAIGRE : les métadonnées fixes (joueurs, tournoi, horaire) vivent
        # dans kalshi_markets.json, pas répétées à chaque ligne. Sur Polymarket,
        # ces champs représentaient plus de la moitié du volume écrit.
        append_jsonl(ticks_path(), {
            'ts': iso_now(),
            'ticker': suivi['ticker'],
            'event_ticker': suivi['event_ticker'],
            'local_uid': suivi['local_uid'],
            'local_side': suivi['local_side'],
            'yes_bid': yb, 'yes_ask': ya, 'mid': mid,
            'spread': (ya - yb) if (yb is not None and ya is not None) else None,
            'last': prix(m, 'last_price'),
            'yes_bid_size': entier(m, 'yes_bid_size_fp'),
            'yes_ask_size': entier(m, 'yes_ask_size_fp'),
            'volume': entier(m, 'volume_fp', 'volume'),
            'volume_24h': entier(m, 'volume_24h_fp'),
            'open_interest': entier(m, 'open_interest_fp', 'open_interest'),
            'liquidity': prix(m, 'liquidity'),
            'status': m.get('status'),
        })


def sauver_registre(suivis):
    """Registre FUSIONNÉ. Les ticks ne portent que le ticker : réécrire ce
    fichier avec les seuls marchés du moment rendrait les ticks anciens
    illisibles."""
    anciens = {}
    if MARKETS_F.exists():
        try:
            d = json.load(open(MARKETS_F, encoding='utf-8'))
            for m in (d.get('markets') or []):
                if m.get('ticker'):
                    anciens[m['ticker']] = m
        except Exception:
            pass
    for m in suivis:
        anciens[m['ticker']] = m
    atomic_json_write(MARKETS_F, {'updated_at': iso_now(),
                                  'count': len(anciens), 'actifs': len(suivis),
                                  'markets': list(anciens.values())})


def sauver_etat(**kw):
    etat = {}
    if STATE_F.exists():
        try:
            etat = json.load(open(STATE_F, encoding='utf-8'))
        except Exception:
            etat = {}
    etat.update(kw)
    etat['updated_at'] = iso_now()
    atomic_json_write(STATE_F, etat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration-seconds', type=int, default=900)
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    locaux = matchs_locaux()
    print(f'Matchs locaux exploitables : {len(locaux)}')
    if not locaux:
        print('❌ aucun match local — rien à suivre.')
        return 0

    fin = time.monotonic() + args.duration_seconds
    ecrivain = Ecrivain()
    series, t_series, suivis = [], 0.0, []
    sauver_etat(running=True, last_run_at=iso_now())

    try:
        while True:
            if time.monotonic() - t_series > SERIES_REFRESH or not series:
                series = series_tennis()
                t_series = time.monotonic()
                if not series:
                    print('❌ aucune série tennis exploitable.')
                    break

            marches = collecter_marches(series)
            suivis = apparier(marches, locaux)
            par_uid = len({s['local_uid'] for s in suivis})
            print(f'{len(marches)} marché(s) · {len(suivis)} suivi(s) '
                  f'sur {par_uid} match(s) de notre univers')

            if not args.dry_run:
                index = {s['ticker']: s for s in suivis}
                for m in marches:
                    s = index.get(m.get('ticker'))
                    if s:
                        ecrivain.ecrire(s, m)
                sauver_registre(suivis)
                print(f'   débit : {ecrivain.ecrits} écrit(s), '
                      f'{ecrivain.filtres} filtré(s)')

            if args.once or time.monotonic() >= fin:
                break
            reste = fin - time.monotonic()
            if reste < POLL_S / 2:
                print(f'⏹️ {reste:.0f}s restantes — cycle trop court, arrêt propre.')
                break
            time.sleep(min(POLL_S, reste))
    finally:
        sauver_etat(running=False, stopped_at=iso_now(),
                    derniers_suivis=len(suivis),
                    ticks_ecrits=ecrivain.ecrits)
        print('👋 Kalshi Collector arrêté')
    return 0


if __name__ == '__main__':
    sys.exit(main())
