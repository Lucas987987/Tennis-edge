#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feuilles_match.py — collecte des FEUILLES DE MATCH (TennisApi, RapidAPI, formule Pro) — 22/10/2026.

Pour chaque jour demandé (UTC) :
  1. l'index du jour : /api/tennis/calendar/{j}/{m}/{a}/categories (1 requête) ;
  2. les matchs de chaque catégorie retenue : /api/tennis/category/{id}/events/{j}/{m}/{a}
     (1 requête par catégorie ; la liste couvre ±12 h : on garde les matchs qui
     COMMENCENT ce jour-là, en simple, terminés) ;
  3. la feuille de chaque match : /api/tennis/event/{id}/statistics (1 requête par match),
     toutes périodes (match entier « ALL » et chaque set).
Catégories par défaut : ATP, WTA, Challenger, ITF hommes et femmes (et WTA 125 si
l'index en publie une). Un tournoi dont les 3 premières feuilles sont vides est
sauté pour ce passage (petits tournois ITF souvent sans statistiques).

STOCKAGE : feuilles/AAAA-MM-JJ.jsonl.gz, une ligne par match (identité, tournoi,
surface, tour, joueurs, score set par set avec tie-breaks, vainqueur, statut,
statistiques), réécrit seulement s'il change. feuilles/etat.json : bilan par jour,
quota restant. Un jour est « complet » quand il est passé depuis plus de 3 jours
et que chaque match a sa feuille (ou a été essayé 3 fois) : il n'est plus jamais
redemandé. Le rattrapage reprend donc là où il s'est arrêté.

GARDE-FOUS : budget de requêtes par passage (FEUILLES_BUDGET, défaut 4 000), arrêt
si le quota restant annoncé par RapidAPI passe sous FEUILLES_RESERVE (défaut 1 500),
5 requêtes/s au plus (formule Pro : 6/s), aucune nouvelle tentative immédiate,
la clé n'est jamais affichée.

Usage : python scripts/feuilles_match.py [debut AAAA-MM-JJ] [fin AAAA-MM-JJ] [categories]
        sans dates : avant-hier et hier (les matchs finis tard sont repris).
Env : RAPIDAPI_KEY, FEUILLES_BUDGET, FEUILLES_RESERVE, FEUILLES_DOSSIER (défaut feuilles).
"""
import datetime as dt
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HOTE = 'tennisapi1.p.rapidapi.com'
DOSSIER = os.environ.get('FEUILLES_DOSSIER', 'feuilles')
BUDGET = int(os.environ.get('FEUILLES_BUDGET', '4000'))
RESERVE = int(os.environ.get('FEUILLES_RESERVE', '1500'))
PAUSE = float(os.environ.get('FEUILLES_PAUSE', '0.2'))
# 22/10/2026 : ITF retiré — aucun pari n'y est joué, et TennisApi n'y a presque jamais de statistiques
# (≈ 600 feuilles sur 9 300). Encore demandable à la main : catégories = itf men,itf women.
CATEGORIES = ('atp', 'wta', 'challenger', 'wta 125')
ESSAIS_MAX = 3
DELAI_COMPLET_J = 3


class QuotaAtteint(Exception):
    pass


# ------------------------------------------------------------------ réseau
class Client:
    def __init__(self, cle, budget=BUDGET, reserve=RESERVE, ouvrir=None, pause=PAUSE):
        self.cle, self.budget, self.reserve, self.pause = cle, budget, reserve, pause
        self.ouvrir = ouvrir or urllib.request.urlopen
        self.n, self.restant, self.codes = 0, None, {}

    def get(self, chemin):
        """(code, json | None). Lève QuotaAtteint avant de dépasser le budget ou la réserve."""
        if self.n >= self.budget:
            raise QuotaAtteint(f"budget du passage atteint ({self.budget} requêtes)")
        if self.restant is not None and self.restant <= self.reserve:
            raise QuotaAtteint(f"quota restant {self.restant} ≤ réserve {self.reserve}")
        if self.n and self.pause:
            time.sleep(self.pause)
        self.n += 1
        req = urllib.request.Request(f"https://{HOTE}{chemin}", headers={
            'X-RapidAPI-Key': self.cle, 'X-RapidAPI-Host': HOTE, 'Accept': 'application/json'})
        brut, ent = b'', {}
        try:
            with self.ouvrir(req, timeout=30) as r:
                code = r.status
                ent = {k.lower(): v for k, v in r.headers.items()}
                brut = r.read()
        except urllib.error.HTTPError as e:
            code = e.code
            ent = {k.lower(): v for k, v in (e.headers or {}).items()}
        except Exception as e:  # noqa: BLE001
            code = type(e).__name__
        self.codes[code] = self.codes.get(code, 0) + 1
        try:
            self.restant = int(ent.get('x-ratelimit-requests-remaining'))
        except (TypeError, ValueError):
            pass
        if code == 429:
            raise QuotaAtteint('429 : limite de requêtes')
        if code in (401, 403):
            raise QuotaAtteint(f"{code} : clé refusée ou abonnement absent")
        if code != 200 or not brut:
            return code, None
        try:
            return code, json.loads(brut.decode('utf-8'))
        except ValueError:
            return code, None


# ------------------------------------------------------------------ lecture des réponses
def norm(s):
    return re.sub(r'\s+', ' ', str(s or '').strip().lower())


def categories_du_jour(doc, voulues=CATEGORIES):
    out = []
    for c in (doc or {}).get('categories') or []:
        cat = c.get('category') or {}
        nom = norm(cat.get('name'))
        if any(nom == v or (v == 'wta 125' and '125' in nom and 'wta' in nom) for v in voulues):
            out.append({'id': cat.get('id'), 'nom': cat.get('name'), 'matchs': c.get('totalEvents')})
    return out


def est_simple(e):
    h, a = e.get('homeTeam') or {}, e.get('awayTeam') or {}
    return not h.get('subTeams') and not a.get('subTeams') and '/' not in str(h.get('name')) + str(a.get('name'))


def jour_utc(ts):
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date()


def score(s):
    """{'sets': [jeux…], 'tb': [points de tie-break ou None…]}."""
    s = s or {}
    sets, tb = [], []
    for i in range(1, 6):
        v = s.get(f'period{i}')
        if v is None:
            break
        sets.append(v)
        tb.append(s.get(f'period{i}TieBreak'))
    return {'sets': sets, 'tb': tb, 'total': s.get('current')}


def infos_joueur(t):
    """playerTeamInfo compact (main, taille, naissance) s'il est fourni avec le match (22/10/2026)."""
    p = (t or {}).get('playerTeamInfo') or {}
    out = {k: p.get(k) for k in ('plays', 'height', 'birthDateTimestamp') if p.get(k) not in (None, '')}
    return out or None


def fiche(e, categorie):
    t = e.get('tournament') or {}
    ut = t.get('uniqueTournament') or {}
    h, a = e.get('homeTeam') or {}, e.get('awayTeam') or {}
    st = e.get('status') or {}
    return {'id': e.get('id'), 'custom': e.get('customId'), 'debut': e.get('startTimestamp'),
            'jour': jour_utc(e['startTimestamp']).isoformat() if e.get('startTimestamp') else None,
            'categorie': categorie, 'tournoi': t.get('name'), 'tournoi_id': ut.get('id') or t.get('id'),
            'tournoi_unique': ut.get('name'), 'surface': ut.get('groundType') or e.get('groundType'),
            'points_tournoi': ut.get('tennisPoints'), 'tour': (e.get('roundInfo') or {}).get('name'),
            'meilleur_des': e.get('bestOf') or e.get('defaultPeriodCount'),
            'home': {'id': h.get('id'), 'nom': h.get('name'), 'court': h.get('shortName'), 'pays': (h.get('country') or {}).get('alpha3'),
                     'infos': infos_joueur(h)},
            'away': {'id': a.get('id'), 'nom': a.get('name'), 'court': a.get('shortName'), 'pays': (a.get('country') or {}).get('alpha3'),
                     'infos': infos_joueur(a)},
            'premier_serveur': e.get('firstToServe'), 'vainqueur': e.get('winnerCode'),
            'statut': {'code': st.get('code'), 'texte': st.get('description'), 'type': st.get('type')},
            'score_home': score(e.get('homeScore')), 'score_away': score(e.get('awayScore')),
            'stats': None, 'essais': 0}


def stats_compactes(doc):
    """{période: {clé: [valeur home, total home, valeur away, total away]}} ; None si vide."""
    out = {}
    for p in (doc or {}).get('statistics') or []:
        per = {}
        for g in p.get('groups') or []:
            for it in g.get('statisticsItems') or []:
                k = it.get('key') or it.get('name')
                if k:
                    per[k] = [it.get('homeValue'), it.get('homeTotal'), it.get('awayValue'), it.get('awayTotal')]
        if per:
            out[str(p.get('period') or 'ALL')] = per
    return out or None


# ------------------------------------------------------------------ stockage
def chemin_jour(jour, dossier=DOSSIER):
    return os.path.join(dossier, f"{jour}.jsonl.gz")


def lire_jour(jour, dossier=DOSSIER):
    try:
        with gzip.open(chemin_jour(jour, dossier), 'rt', encoding='utf-8') as f:
            return {r['id']: r for r in (json.loads(l) for l in f if l.strip())}
    except (OSError, ValueError):
        return {}


def ecrire_jour(jour, recs, dossier=DOSSIER):
    """Réécrit le fichier du jour seulement si son contenu change (mtime gzip fixé à 0)."""
    os.makedirs(dossier, exist_ok=True)
    lignes = ''.join(json.dumps(recs[k], ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                     for k in sorted(recs))
    p = chemin_jour(jour, dossier)
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            if f.read() == lignes:
                return False
    except OSError:
        pass
    with open(p + '.tmp', 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as g:
            g.write(lignes.encode('utf-8'))
    os.replace(p + '.tmp', p)
    return True


def lire_etat(dossier=DOSSIER):
    try:
        with open(os.path.join(dossier, 'etat.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'jours': {}}


# ------------------------------------------------------------------ un jour
def collecter_jour(c, jour, voulues=CATEGORIES, aujourd_hui=None, dossier=DOSSIER, journal=print):
    """Collecte un jour ; renvoie son bilan. Lève QuotaAtteint (le travail fait est déjà écrit)."""
    aujourd_hui = aujourd_hui or dt.datetime.now(dt.timezone.utc).date()
    recs = lire_jour(jour, dossier)
    d = dt.date.fromisoformat(jour)
    code_idx, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
    cats = categories_du_jour(idx, voulues) if code_idx == 200 else []
    if code_idx not in (200, 204):
        journal(f"  {jour} : index du jour indisponible (HTTP {code_idx})")
    try:
        for cat in cats:
            code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{d.day}/{d.month}/{d.year}")
            for e in (doc or {}).get('events') or []:
                if not e.get('id') or not e.get('startTimestamp') or jour_utc(e['startTimestamp']).isoformat() != jour:
                    continue
                if not est_simple(e) or (e.get('status') or {}).get('type') != 'finished':
                    continue
                nouv = fiche(e, cat['nom'])
                old = recs.get(e['id'])
                if old:
                    nouv['stats'], nouv['essais'] = old.get('stats'), old.get('essais', 0)
                if 'walkover' in norm(nouv['statut']['texte']):
                    nouv['essais'] = ESSAIS_MAX           # forfait : pas de feuille à demander
                recs[e['id']] = nouv
        vides_par_tournoi = {}
        a_faire = [r for r in recs.values() if r['stats'] is None and r['essais'] < ESSAIS_MAX]
        a_faire.sort(key=lambda r: (('itf' in norm(r['categorie'])), r['debut'] or 0))   # grand circuit d'abord
        for r in a_faire:
            t = r['tournoi_id']
            if vides_par_tournoi.get(t, 0) >= 3:
                continue                                  # tournoi sans statistiques : on n'insiste pas
            code, doc = c.get(f"/api/tennis/event/{r['id']}/statistics")
            r['essais'] += 1
            r['stats'] = stats_compactes(doc) if code == 200 else None
            if r['stats'] is None:
                vides_par_tournoi[t] = vides_par_tournoi.get(t, 0) + 1
            else:
                vides_par_tournoi[t] = -999               # le tournoi a des statistiques
    finally:
        ecrire_jour(jour, recs, dossier)
    avec = sum(1 for r in recs.values() if r['stats'])
    restants = sum(1 for r in recs.values() if r['stats'] is None and r['essais'] < ESSAIS_MAX)
    passe = (aujourd_hui - d).days > DELAI_COMPLET_J
    par_cat = {}
    for r in recs.values():
        x = par_cat.setdefault(r['categorie'], [0, 0])
        x[0] += 1
        x[1] += bool(r['stats'])
    return {'matchs': len(recs), 'avec_stats': avec, 'a_reessayer': restants,
            'complet': bool(passe and restants == 0 and code_idx in (200, 204)),
            'categories': {k: {'matchs': v[0], 'avec_stats': v[1]} for k, v in sorted(par_cat.items())}}


def jours_a_traiter(debut, fin, etat):
    d, out = dt.date.fromisoformat(debut), []
    f = dt.date.fromisoformat(fin)
    while d <= f:
        if not (etat['jours'].get(d.isoformat()) or {}).get('complet'):
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    auj = dt.datetime.now(dt.timezone.utc).date()
    debut = argv[1] if len(argv) > 1 and argv[1] else (auj - dt.timedelta(days=2)).isoformat()
    fin = argv[2] if len(argv) > 2 and argv[2] else (auj - dt.timedelta(days=1)).isoformat()
    voulues = tuple(norm(x) for x in argv[3].split(',')) if len(argv) > 3 and argv[3].strip() else CATEGORIES
    etat = lire_etat()
    jours = jours_a_traiter(debut, fin, etat)
    c = Client(cle)
    print(f"Feuilles de match : {debut} → {fin} · {len(jours)} jour(s) à traiter · catégories {', '.join(voulues)} · "
          f"budget {c.budget} requêtes, réserve {c.reserve}")
    arret = None
    for j in jours:
        try:
            b = collecter_jour(c, j, voulues, auj)
        except QuotaAtteint as e:
            arret = str(e)
            b = None
        if b:
            etat['jours'][j] = dict(b, maj=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'))
            reprise = f" · {b['a_reessayer']} à reprendre" if b['a_reessayer'] else ''
            print(f"  {j} : {b['matchs']} matchs, {b['avec_stats']} feuilles{' · complet' if b['complet'] else ''}{reprise}",
                  flush=True)
        if arret:
            print(f"::warning::Arrêt : {arret} (au jour {j}) — le prochain passage reprendra ici.")
            break
    etat['dernier_passage'] = {'le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'debut': debut,
                               'fin': fin, 'requetes': c.n, 'codes': {str(k): v for k, v in c.codes.items()},
                               'quota_restant': c.restant, 'arret': arret}
    etat['total'] = {'jours': len(etat['jours']), 'matchs': sum(v['matchs'] for v in etat['jours'].values()),
                     'avec_stats': sum(v['avec_stats'] for v in etat['jours'].values())}
    os.makedirs(DOSSIER, exist_ok=True)
    with open(os.path.join(DOSSIER, 'etat.json'), 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Requêtes : {c.n} · codes {c.codes} · quota restant annoncé : {c.restant} · "
          f"total : {etat['total']['avec_stats']} feuilles sur {etat['total']['matchs']} matchs, {etat['total']['jours']} jours")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
