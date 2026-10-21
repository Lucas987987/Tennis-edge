#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suivi_direct.py — verdicts des hypothèses gelées sur les ALERTES EN DIRECT.

DÉCISION DU 16/10/2026 (Lucas) : un verdict se rend sur ce que le canal a
réellement détecté, AU MOMENT où il l'a détecté. Les champs de décision
(cote, book, Pinnacle ouverture, délai…) sont écrits une fois par
h*_signal.py dans h*_signal_log.jsonl et ne sont JAMAIS modifiés. Ce script
n'y touche pas : il AJOUTE seulement, dans des fichiers séparés,

    * le résultat (set_results.json par uid exact, sinon index des matchs
      par PAIRE exacte de joueurs, de la veille du début jusqu'à J+7, premier
      résultat à partir du jour du match — jamais par le seul nom) ;
    * la clôture Pinnacle des deux côtés (dernier point avant le début,
      clv_history via clv_source) ;
    * la CLV Pinnacle (dé-margination PUISSANCE, books.fair_close du Lab ;
      entrée nette de commission, books.effective_odds) ;
    * le P&L au prix JOURNALISÉ, et le drapeau « dénoué ».

La reconstruction (moves_detail_hist.csv) n'entre PAS dans les verdicts :
elle reste un contrôle (onglet Réconciliation du Lab, ligne « contrôle »
de validation_report).

RÈGLES DE COMPTAGE (explicites) :
    1. un pari par (hypothèse, uid, côté) = la PREMIÈRE détection ;
    2. seules les détections STRICTEMENT après la date de gel comptent
       (jour de detecte_le > gele_le) ;
    3. un doublon entre hypothèses compte pour CHAQUE hypothèse (une
       détection H15 doublon de H13 est une détection H15 valide, marquée
       « non envoyée ») ;
    4. lignes identiques (fusion git « union ») dédupliquées.

Sorties :
    suivi_direct/resultats.json — table compacte des champs AJOUTÉS, réécrite
                                  seulement si son contenu change ;
    verdicts_direct.json        — un bloc par hypothèse, mêmes champs que la
                                  page du Worker (n, gains, taux, seuil, écart,
                                  IC95, ROI, P&L, CLV…) + n détectées /
                                  envoyées / dénouées, moitiés, avancement.

Usage : python scripts/suivi_direct.py [racine]     (0 requête réseau)
"""
import collections
import contextlib
import datetime as dt
import importlib.util
import io
import json
import math
import os
import pathlib
import re
import sys
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT / 'Tennis_Edge_Lab'
OUT_VERDICTS = 'verdicts_direct.json'
OUT_RESULTS = 'suivi_direct/resultats.json'
FENETRE_JOURS = 7          # résultat cherché jusqu'à 7 jours après le début annoncé
SEUIL_SANS_RESULTAT = 10.0  # % : au-delà, aucun verdict ne peut être verrouillé
CODES = ('H13', 'H14', 'H15', 'H16', 'H16B', 'H17', 'H18')
LOGS = {c: f'{c.lower()}_signal_log.jsonl' for c in CODES}

# Libellé, cible de n (volume où l'IC95 devient lisible) et référence
# in-sample — recopiés des docstrings des fonctions *_watch de
# validation_report.py (ce sont les valeurs que la table D1 `hypotheses`
# du Worker portait, hors dépôt). NON confirmatoires.
META = {
    'H13': ('ROI bande cote 2-3', 300, {'n': 316, 'taux': 47.5, 'seuil': 42.2, 'roi': 13.7}, 'roi_bande_watch'),
    'H14': ('amplitude + timing', 166, {'n': 275, 'taux': 53.1, 'seuil': 46.0, 'roi': 20.9}, 'roi_ampli_watch'),
    'H15': ('bande cote 2,40-3,10', 150, {'n': 225, 'taux': 45.8, 'seuil': 37.5, 'roi': 23.4}, 'bande_240_310_watch'),
    'H16': ('favori net (pin<1,80)', 600, {'n': 580, 'taux': 74.0, 'seuil': 70.2, 'roi': 5.5}, 'bande_favori_watch'),
    'H16B': ('favori sans ultra (pin 1,30-1,80)', 400, {'n': 463, 'taux': 71.3, 'seuil': 66.5, 'roi': 7.0}, 'favori_sans_ultra_watch'),
    'H17': ('écart entrée 0-3 %', 350, {'n': 255, 'taux': 59.6, 'seuil': 54.1, 'roi': 12.4}, 'ecart_entree_watch'),
    'H18': ('Favorite Steam Value', 150, {'n': 123, 'taux': 78.0, 'seuil': 70.2, 'roi': 11.8}, 'favorite_steam_value_watch'),
}
NOTES = {
    'H14': "Canal en direct créé le 16/10/2026 : l'échantillon en direct commence à son déploiement.",
    'H15': "Bande recouverte par H13 : jusqu'au 21/10/2026 H15 n'envoyait pas les matchs déjà couverts ; depuis, ils partent marqués « déjà signalé ». Toutes ses détections comptent.",
    'H16B': 'Sous-ensemble de H16 : non indépendante (Holm).',
    'H18': 'Intersection de H16 et H17 : non indépendante (Holm).',
}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    added = str(path.parent) not in sys.path
    if added:
        sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(str(path.parent))
    return module


books = _load(LAB / 'books.py', 'tennis_edge_sd_books')
clv_stats = _load(LAB / 'clv_stats.py', 'tennis_edge_sd_clv_stats')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def side_depuis_uid(uid, joueur):
    """'home'/'away' déduit du uid 'AAAA-MM-JJ_home_away' (lignes sans `side`, H13 avant le schéma 2).
    Ne tranche que si le nom colle à UNE seule extrémité (copie de h13_populations)."""
    if not uid or not joueur:
        return None
    base = uid[11:] if re.match(r'^\d{4}-\d\d-\d\d_', uid) else uid
    u, j = norm(base), norm(joueur)
    if not j:
        return None
    d, f = u.startswith(j), u.endswith(j)
    if d and not f:
        return 'home'
    if f and not d:
        return 'away'
    return None


def read_jsonl(path):
    out = []
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def gel(code, vr):
    return {'H13': vr.FREEZE_DATE_ROIBANDE, 'H14': vr.FREEZE_DATE_AMPLI, 'H15': vr.FREEZE_DATE_H15,
            'H16': vr.FREEZE_DATE_H16, 'H16B': vr.FREEZE_DATE_H16B, 'H17': vr.FREEZE_DATE_H17,
            'H18': vr.FREEZE_DATE_H18}[code]


def load_validation_report(root):
    """Module validation_report importé depuis root/scripts (sorties muettes)."""
    path = pathlib.Path(root) / 'scripts' / 'validation_report.py'
    spec = importlib.util.spec_from_file_location('tennis_edge_sd_vr', path)
    module = importlib.util.module_from_spec(spec)
    old = list(sys.path)
    sys.path.insert(0, str(path.parent))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(module)
    finally:
        sys.path[:] = old
    return module


# ------------------------------------------------------------------ journal
def detections(root, vr):
    """Première détection par (H, uid, côté), après le gel. Lignes du journal inchangées."""
    out = {}
    for code in CODES:
        rows = read_jsonl(pathlib.Path(root) / LOGS[code])
        seen, items = set(), {}
        for r in rows:
            blob = json.dumps(r, sort_keys=True, ensure_ascii=False)
            if blob in seen:
                continue                                  # doublon de fusion « union »
            seen.add(blob)
            uid = r.get('uid')
            if not uid or r.get('cote') in (None, ''):
                continue
            side = r.get('side') or side_depuis_uid(uid, r.get('joueur'))
            key = (uid, side or norm(r.get('joueur')))
            t = str(r.get('detecte_le') or r.get('signale_le') or '')
            if key not in items or t < str(items[key].get('detecte_le') or items[key].get('signale_le') or ''):
                items[key] = dict(r, _side=side)
        freeze = gel(code, vr)
        first_day = min((str(r.get('detecte_le') or r.get('signale_le'))[:10] for r in items.values()), default=None)
        kept = [r for r in items.values() if str(r.get('detecte_le') or r.get('signale_le'))[:10] > freeze]
        kept.sort(key=lambda r: (str(r.get('detecte_le') or r.get('signale_le')), r['uid']))
        out[code] = {'gel': freeze, 'journal': len(rows), 'premiere_detection': first_day, 'lignes': kept,
                     'avant_gel': len(items) - len(kept)}
    return out


# ------------------------------------------------------------------ ajouts
class Ajouts:
    """Résultat (paire exacte), clôture Pinnacle et CLV : rien d'autre."""

    def __init__(self, root):
        root = pathlib.Path(root)
        self.root = root
        try:
            self.sets = json.loads((root / 'set_results.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.sets = {}
        self.ex = _load(LAB / 'explorer_build.py', 'tennis_edge_sd_explorer')
        self.ex.ROOT = root
        self.pin = self.ex.PinnacleIndex(root / 'clv_history.jsonl')
        self.by_uid = {}
        for items in self.pin.by_player.values():
            for it in items:
                if it.get('uid'):
                    self.by_uid[it['uid']] = it
        self.results = self.ex.Results(root)
        # Index PAIRE -> [(jour, vainqueur)] pour la fenêtre [début − 1 j ; début + 7 j].
        self.by_pair = collections.defaultdict(list)
        for (jour, pair), winner in self.results.index.items():
            self.by_pair[pair].append((jour, winner))
        for v in self.by_pair.values():
            v.sort()

    def par_paire(self, joueur, adv, start):
        """Résultat par PAIRE exacte de joueurs (jamais un seul nom).

        Fenêtre : jamais avant la veille du début, au plus 7 jours après (matchs
        reportés, dates de règlement décalées). On garde le PREMIER résultat à
        partir du jour du match ; à défaut, celui de la veille."""
        if start is None or not joueur or not adv:
            return None, None
        pair = tuple(sorted((self.ex.name_key(joueur), self.ex.name_key(adv))))
        jour = start.date()
        lo, hi = (jour - dt.timedelta(days=1)).isoformat(), (jour + dt.timedelta(days=FENETRE_JOURS)).isoformat()
        cands = [(d, w) for d, w in self.by_pair.get(pair, []) if lo <= d <= hi]
        if not cands:
            return None, None
        apres = [c for c in cands if c[0] >= jour.isoformat()]
        d, w = (apres or cands)[0]
        ecart = (dt.date.fromisoformat(d) - jour).days
        return w == self.ex.name_key(joueur), f"paire exacte ({ecart:+d} j)"

    def pour(self, r):
        uid, side = r['uid'], r.get('_side')
        joueur, adv = r.get('joueur'), r.get('adversaire')
        start = self.ex.parse_time(r.get('commence'))
        item = self.by_uid.get(uid)
        pside = None
        if item is not None:
            if norm(item.get('home')) == norm(joueur):
                pside = 'home'
            elif norm(item.get('away')) == norm(joueur):
                pside = 'away'
            else:
                item = None
        if item is None:
            item, pside = self.pin.find(joueur, start, adv)
        # 1. set_results par uid EXACT du journal, côté journalisé.
        won, src = None, 'inconnu'
        res = (self.sets.get(uid) or {}).get('match')
        res_item = (self.sets.get(item['uid']) or {}).get('match') if item is not None and item.get('uid') else None
        if res in ('home', 'away') and side in ('home', 'away'):
            won, src = res == side, 'set_results (uid)'
        elif res_item in ('home', 'away') and pside:
            # 2. set_results par uid EXACT du match Pinnacle (clv_history).
            won, src = res_item == pside, 'set_results (uid clv_history)'
        else:
            # 3. PAIRE exacte de joueurs, de la veille à J+7 (jamais un seul nom).
            won, src = self.par_paire(joueur, adv, start)
            src = src or 'inconnu'
        close = close_adv = None
        if item is not None and pside:
            other = 'away' if pside == 'home' else 'home'
            a, b = item['curves'].get(pside) or [], item['curves'].get(other) or []
            if a and b:
                close, close_adv = a[-1][1], b[-1][1]
        cote, book = float(r['cote']), books.normalize(r.get('book'))
        clv = books.clv_pin_pct(book, cote, close, close_adv) if close and close_adv else None
        pnl = books.pnl(book, cote, won) if won is not None else None
        return {'gagne': None if won is None else int(won), 'pnl': None if pnl is None else round(pnl, 4),
                'pin_close': close, 'pin_close_adv': close_adv,
                'clv_pin': None if clv is None else round(clv, 3), 'source_resultat': src,
                'denoue': won is not None}


# ------------------------------------------------------------------ statistiques
def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def r1(x):
    return None if x is None else round(x, 1)


def clv_bloc(items):
    """CLV Pinnacle sur TOUTES les détections dont la clôture est connue (dénouées ou non) :
    la CLV ne dépend pas du résultat. items : [(clv_pin, jour)]."""
    s = clv_stats.summary([c for c, _ in items], [j for _, j in items])
    vals = [c for c, _ in items if c is not None]
    return {'clv_moyen': r1(s['mean_pct']), 'clv_pin_moyen': r1(s['mean_pct']),
            'clv_pin_ic95': None if not s['ci95'] else [r1(x) for x in s['ci95']],
            'clv_pin_p': None if s['p_one_sided'] is None else round(s['p_one_sided'], 4),
            'clv_n': s['n'], 'clv_positif': r1(100 * sum(1 for c in vals if c > 0) / len(vals)) if vals else None}


def bloc(paris, clv_items=None):
    """paris : [{cote, book, gagne, pnl, clv_pin, jour, lead_min}] dénoués ; clv_items : voir clv_bloc."""
    n = len(paris)
    if not n:
        return {'n': 0, **(clv_bloc(clv_items) if clv_items else {})}
    k = sum(p['gagne'] for p in paris)
    seuil = 100 * sum(1 / books.effective_odds(p['book'], p['cote']) for p in paris) / n
    taux = 100 * k / n
    lo, hi = wilson(k, n)
    pnl = sum(p['pnl'] for p in paris)
    clv = clv_bloc(clv_items if clv_items is not None else [(p['clv_pin'], p['jour']) for p in paris])
    leads = [p['lead_min'] for p in paris if p.get('lead_min') is not None]
    jours = sorted(p['jour'] for p in paris)
    return {
        'n': n, 'gains': k, 'taux': r1(taux), 'seuil': r1(seuil), 'ecart': r1(taux - seuil),
        'ic95': [r1(lo), r1(hi)], 'roi': r1(100 * pnl / n), 'pnl': r1(pnl),
        'cote_moyenne': round(sum(p['cote'] for p in paris) / n, 2),
        # Compatibilité de l'API : clv_moyen = CLV PINNACLE (puissance) depuis
        # le 16/10/2026 — l'ancien Worker y mettait la CLV du même book.
        **clv,
        'lead_moyen_h': r1(sum(leads) / len(leads) / 60) if leads else None,
        'periode': f"{jours[0]} -> {jours[-1]}",
        'verdict': 'SURVIT' if lo > seuil else ('REJET' if hi < seuil else 'ne tranche pas'),
    }


def garde(lignes, n_denouees, now):
    """GARDE DE VERROUILLAGE (16/10/2026, approuvée par Lucas).

    Aucun verdict ne peut être verrouillé ni déclaré tant que plus de 10 % des
    détections post-gel DONT LE MATCH A COMMENCÉ n'ont pas de résultat, quel
    que soit n. (Un match à venir ne peut pas encore avoir de résultat : il
    n'entre pas au dénominateur.) Évite de juger sur un sous-ensemble dont la
    sélection dépendrait de la disponibilité des résultats."""
    commencees = 0
    for r in lignes:
        try:
            t = dt.datetime.fromisoformat(str(r.get('commence')).replace('Z', '+00:00'))
        except ValueError:
            t = None
        if t is not None and t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        if t is None or t <= now:
            commencees += 1
    sans = max(0, commencees - n_denouees)
    pct = round(100 * sans / commencees, 1) if commencees else 0.0
    ok = pct <= SEUIL_SANS_RESULTAT
    statut = ('verrouillable (résultats complets à ' + f"{100 - pct:.0f} %)" if ok
              else f"en attente de résultats ({pct:.1f} % sans résultat)".replace('.', ','))
    return {'n_commencees': commencees, 'n_sans_resultat': sans, 'sans_resultat_pct': pct,
            'verrouillable': ok, 'statut': statut}


def verdicts(root=ROOT, vr=None, ajouts=None, maintenant=None):
    root = pathlib.Path(root)
    vr = vr or load_validation_report(root)
    det = detections(root, vr)
    ajouts = ajouts or Ajouts(root)
    now = maintenant or dt.datetime.now(dt.timezone.utc)
    table, hyps = {}, []
    for code in CODES:
        d = det[code]
        paris, clv_all, n_env, n_dbl, n_ech = [], [], 0, 0, 0
        for r in d['lignes']:
            a = ajouts.pour(r)
            key = f"{code}|{r['uid']}|{r.get('_side') or norm(r.get('joueur'))}"
            table[key] = {k: a[k] for k in ('gagne', 'pnl', 'pin_close', 'pin_close_adv', 'clv_pin', 'source_resultat')}
            if r.get('envoye') is True and not r.get('doublon'):
                n_env += 1
            elif r.get('doublon'):
                n_dbl += 1
            else:
                n_ech += 1
            clv_all.append((a['clv_pin'], str(r.get('detecte_le') or r.get('signale_le'))[:10]))
            if a['denoue']:
                paris.append({'cote': float(r['cote']), 'book': books.normalize(r.get('book')),
                              'gagne': a['gagne'], 'pnl': a['pnl'], 'clv_pin': a['clv_pin'],
                              'jour': str(r.get('detecte_le') or r.get('signale_le'))[:10],
                              'lead_min': r.get('lead_min')})
        o = bloc(paris, clv_all)
        o.update({'n_detectees': len(d['lignes']), 'n_envoyees': n_env, 'n_doublons': n_dbl,
                  'n_non_envoyees_autres': n_ech, 'n_denouees': len(paris)})
        o.update(garde(d['lignes'], len(paris), now))
        if not o['verrouillable'] and o.get('n'):
            o['verdict'] = o['statut']
        half = (len(paris) + 1) // 2
        moities = [paris[:half], paris[half:]] if len(paris) >= 2 else []
        rep = []
        for i, m in enumerate(moities, 1):
            b = bloc(m)
            rep.append({'moitie': i, 'n': b['n'], 'roi': b.get('roi'), 'ecart': b.get('ecart'),
                        'clv_pin': b.get('clv_pin_moyen')})
        top = sorted((p['pnl'] for p in paris), reverse=True)[:5]
        total = sum(p['pnl'] for p in paris)
        libelle, cible, ref, watch = META[code]
        controle = None
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                cur = os.getcwd()
                os.chdir(root)
                try:
                    res = getattr(vr, watch)()
                finally:
                    os.chdir(cur)
            if res:
                controle = {'n': res[1], 'gains': res[0], 'seuil': r1(100 * res[2]),
                            'ecart': r1(100 * (res[0] / res[1] - res[2])),
                            'source': 'moves_detail_hist.csv (reconstruction, contrôle uniquement)'}
        except Exception as exc:  # le contrôle ne bloque jamais le verdict
            controle = {'erreur': f'{type(exc).__name__}: {str(exc)[:120]}'}
        nd = o['n']
        hyps.append({
            'code': code, 'libelle': libelle, 'gele_le': d['gel'], 'cible': cible,
            'regle': _regle(code, vr), 'note': NOTES.get(code),
            'source': 'alertes en direct (h*_signal_log.jsonl)',
            'debut_direct': d['premiere_detection'], 'journal_lignes': d['journal'],
            'detections_avant_gel': d['avant_gel'],
            'reference_in_sample': dict(ref, avertissement="NON confirmatoire : l'hypothèse a été trouvée sur ces données"),
            'in_sample_recalcule': {'n': 0},
            'out_of_sample': o, 'replication': rep,
            'concentration_5_meilleurs': r1(100 * sum(top) / total) if paris and total > 0 else None,
            'avancement': round(100 * nd / cible) if nd else 0, 'restant': max(0, cible - nd),
            'controle_reconstruction': controle,
            'statut': o['statut'],
        })
    doc = {'schema_version': 1, 'genere_le': now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
           'source': 'h*_signal_log.jsonl (décision) + suivi_direct/resultats.json (ajouts)',
           'regles_de_comptage': [
               'un pari par (hypothèse, uid, côté) = la première détection',
               'détections strictement après la date de gel (jour de detecte_le > gele_le)',
               "un doublon entre hypothèses compte pour chaque hypothèse (marqué non envoyé)",
               "résultat par uid exact ou paire exacte de joueurs (veille du début à J+7), jamais par un seul nom",
               f"garde : aucun verdict verrouillable si plus de {SEUIL_SANS_RESULTAT:g} % des détections de matchs commencés sont sans résultat",
               "CLV Pinnacle : clôture sans marge (puissance), entrée nette de commission, sur toutes les détections dont la clôture est connue",
           ],
           'hypotheses': hyps}
    return doc, table


def _regle(code, vr):
    return {'H13': f"{vr.H13_COTE_MIN:.2f} ≤ cote entrée ≤ {vr.H13_COTE_MAX:.2f}",
            'H14': f"mouvement Pinnacle > {vr.H14_MOVE_MIN_PCT:g} % à la détection, {vr.H14_LEAD_MIN / 60:.0f}–{vr.H14_LEAD_MAX / 60:.0f} h avant",
            'H15': f"{vr.H15_COTE_MIN:.2f} ≤ cote entrée < {vr.H15_COTE_MAX:.2f}",
            'H16': f"Pinnacle ouverture < {vr.H16_PIN_OPEN_MAX:.2f}",
            'H16B': f"{vr.H16B_PIN_OPEN_MIN:.2f} ≤ Pinnacle ouverture < {vr.H16_PIN_OPEN_MAX:.2f}",
            'H17': f"{vr.H17_ECART_MIN:.0f} ≤ écart entrée vs Pinnacle ouverture < {vr.H17_ECART_MAX:.0f} %",
            'H18': f"Pinnacle ouverture < {vr.H16_PIN_OPEN_MAX:.2f} et écart {vr.H17_ECART_MIN:.0f}–{vr.H17_ECART_MAX:.0f} %"}[code]


def ecrire_si_change(path, doc, volatile=('genere_le',)):
    path = pathlib.Path(path)
    new = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=False) + '\n'
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding='utf-8'))
            strip = lambda d: {k: v for k, v in d.items() if k not in volatile} if isinstance(d, dict) else d
            if strip(old) == strip(json.loads(new)):
                return False
        except ValueError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding='utf-8')
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = pathlib.Path(argv[0]) if argv else pathlib.Path.cwd()
    doc, table = verdicts(root)
    t = ecrire_si_change(root / OUT_RESULTS, {'schema_version': 1, 'champs': 'ajoutés après coup ; jamais de champ de décision',
                                              'paris': dict(sorted(table.items()))})
    v = ecrire_si_change(root / OUT_VERDICTS, doc)
    for h in doc['hypotheses']:
        o = h['out_of_sample']
        print(f"{h['code']}: détectées {o['n_detectees']} · envoyées {o['n_envoyees']} · doublons {o['n_doublons']}"
              f" · dénouées {o['n_denouees']} · ROI {o.get('roi')} % · écart {o.get('ecart')} pts"
              f" · CLV Pinnacle {o.get('clv_pin_moyen')} % (n={o.get('clv_n', 0)})")
    print(f"resultats.json {'écrit' if t else 'inchangé'} · verdicts_direct.json {'écrit' if v else 'inchangé'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
