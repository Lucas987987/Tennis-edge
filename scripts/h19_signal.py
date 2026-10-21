#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h19_signal.py — H19 « valeur contre Pinnacle juste », alerte EN DIRECT (canal privé).

RÈGLE : celle du gel (Tennis_Edge_Lab/registry/gel_h19.json), lue ici et
vérifiée par empreinte — jamais redéfinie. Appliquée EXACTEMENT comme dans
le Lab (Tennis_Edge_Lab/valeur.py), à l'instant de décision de chaque horizon :
  — horizons 24 h, 6 h, 1 h, 10 min avant le début (dans cet ordre) ;
  — Pinnacle cote les deux joueurs à la décision (dernier point de moins de
    12 h / 3 h / 1 h / 50 min selon l'horizon, les deux à moins de 30 min) ;
  — meilleur prix d'un book de la liste gelée, cote de 30 min au plus,
    commission de bourse déduite ;
  — écart = prix net / cote Pinnacle juste (méthode puissance) − 1, de +2 à +8 % ;
  — un seul pari par (match, joueur) : le premier horizon qui remplit la règle.

Le script tourne à chaque passage de courbes_alertes (toutes les 3 à 6 min) et
traite chaque horizon dont l'instant de décision vient de passer (moins de
RATTRAPAGE_MIN minutes). Il journalise TOUTE détection (h19_signal_log.jsonl,
écrit une fois, jamais modifié) et l'envoie sur le canal PRIVÉ.

Le verdict officiel de H19 reste celui du Lab, sur les courbes de TOUS les
matchs ; ce journal sert à comparer ce qui a été envoyé, et à mesurer le délai
entre l'alerte et le prix réellement disponible.

Env : CURVES (book_curves_live.jsonl), TELEGRAM_TOKEN / TELEGRAM_CHAT_ID,
      DRY_RUN=1, RATTRAPAGE_MIN (défaut 20). 0 requête API.
"""
import datetime
import hashlib
import importlib.util
import json
import os
import sys
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, ICI)
import oddspapi_v5 as ov          # noqa: E402 — lecture des courbes, écriture atomique
import lien_joueur                # noqa: E402

_spec = importlib.util.spec_from_file_location('tennis_edge_books_h19',
                                               os.path.join(RACINE, 'Tennis_Edge_Lab', 'books.py'))
books = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(books)

CURVES = os.environ.get('CURVES', 'book_curves_live.jsonl')
GEL = os.path.join(RACINE, 'Tennis_Edge_Lab', 'registry', 'gel_h19.json')
ETAT = 'h19_signal_state.json'
LOG = 'h19_signal_log.jsonl'
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
RATTRAPAGE_MIN = float(os.environ.get('RATTRAPAGE_MIN', '20'))
# (avance en min, ancienneté max du point Pinnacle en min) — bookmakers_sets_v5.HORIZONS
HORIZONS = {'24h': (1440, 720), '6h': (360, 180), '1h': (60, 60), '10m': (10, 50)}
CIRCUITS_OK = ('ATP', 'WTA', 'Challenger', 'Grand Chelem')
SCHEMA = 1


def regle():
    """La règle gelée, avec contrôle d'empreinte (même calcul que valeur.empreinte)."""
    with open(GEL, encoding='utf-8') as f:
        doc = json.load(f)
    r = doc['regle']
    sha = hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    if sha != doc.get('sha256'):
        raise SystemExit(f"❌ gel H19 MODIFIÉ (empreinte {sha[:12]} ≠ {str(doc.get('sha256'))[:12]}) : aucune alerte.")
    return r, sha


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', '')).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


_spec2 = importlib.util.spec_from_file_location('tennis_edge_meta_h19',
                                                os.path.join(RACINE, 'Tennis_Edge_Lab', 'tennis_meta.py'))
meta = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(meta)


def circuit(tournoi):
    """Exactement le découpage du Lab (tennis_meta.circuit_of) ; doubles exclus comme dans valeur.py."""
    if 'double' in str(tournoi or '').lower():
        return None
    return meta.circuit_of(tournoi)


def charger():
    """{uid: {'_ct','_home','_away','_tour', book: {'h': [(t, cote)], 'a': [...]}}}"""
    games = {}
    try:
        lignes = ov.open_curves(CURVES)
    except FileNotFoundError as e:
        print(f"  ❌ {e}")
        return games
    for ligne in lignes:
        try:
            r = json.loads(ligne)
        except ValueError:
            continue
        ct = _dt(r.get('commence_time'))
        if ct is None or not r.get('book') or not r.get('uid'):
            continue
        serie = lambda k: sorted((t, float(o)) for t, o in ((_dt(p[0]), p[1]) for p in (r.get(k) or []))
                                 if t and o and t < ct)
        h, a = serie('home_curve'), serie('away_curve')
        if not h or not a:
            continue
        g = games.setdefault(r['uid'], {'_ct': ct, '_home': r.get('home'), '_away': r.get('away'),
                                        '_tour': r.get('tournament')})
        g[str(r['book']).lower()] = {'h': h, 'a': a}
    return games


def point(serie, t, max_age_min=None):
    """Dernier (heure, cote) au plus tard à t, et pas plus vieux que max_age_min."""
    best = None
    for tt, o in serie:
        if tt <= t:
            best = (tt, o)
        else:
            break
    if best and max_age_min is not None and (t - best[0]).total_seconds() / 60 > max_age_min:
        return None
    return best


def evaluer(g, side, horizon, R):
    """Décision H19 pour un joueur à un horizon : dict, ou None si la règle n'est pas remplie."""
    lead, stale = HORIZONS[horizon]
    decision = g['_ct'] - datetime.timedelta(minutes=lead)
    pin = g.get('pinnacle')
    if not pin:
        return None
    ps = point(pin[side], decision, stale)
    po = point(pin['a' if side == 'h' else 'h'], decision, stale)
    if not ps or not po or abs((ps[0] - po[0]).total_seconds()) > 1800:
        return None
    juste = books.fair_close(ps[1], po[1])
    if not juste:
        return None
    best = None
    for b in R['books']:
        s = g.get(b)
        if not s:
            continue
        q = point(s[side], decision, R['age_max_min'])
        if not q:
            continue
        net = books.effective_odds(b, q[1])
        if best is None or net > best['net']:
            best = {'book': b, 'cote': q[1], 'net': net, 'age_min': (decision - q[0]).total_seconds() / 60}
    if best is None:
        return None
    ecart = 100 * (best['net'] / juste - 1)
    if not (R['ecart_min_pct'] <= ecart < R['ecart_max_pct']):
        return None
    return {'horizon': horizon, 'decision': decision, 'pin': ps[1], 'pin_autre': po[1], 'juste': juste,
            'ecart_pct': ecart, **best}


def envoyer(texte):
    """Canal PRIVÉ uniquement (TELEGRAM_CHAT_ID). Vérifie la réponse, pas seulement l'absence d'erreur."""
    token, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if DRY_RUN or not token or not chat:
        print(f"  [non envoyé] {texte.splitlines()[0]}")
        return False
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode({'chat_id': chat, 'text': texte, 'parse_mode': 'HTML',
                                         'disable_web_page_preview': 'true'}).encode())
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:   # noqa: BLE001
        print(f"  ⚠️ Telegram : {e}")
        return False


def suivi():
    """Bilan prospectif du Lab (valeur.json), s'il existe."""
    try:
        v = json.load(open(os.path.join(RACINE, 'Tennis_Edge_Lab', 'live', 'valeur.json'), encoding='utf-8'))
        p = v['h19']['prospectif']
        roi = p.get('roi') or {}
        return (p['n'], (p.get('clv') or {}).get('mean'), v['h19']['regle']['cible_n'],
                roi.get('n') or 0, roi.get('mean'))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def message(g, side, d, R, maintenant):
    joueur = g['_home'] if side == 'h' else g['_away']
    adv = g['_away'] if side == 'h' else g['_home']
    lead = (g['_ct'] - maintenant).total_seconds() / 60
    lead_txt = f"{int(lead)} min" if lead < 60 else f"{int(lead // 60)}h{int(lead % 60):02d}"
    net = f" (net {d['net']:.2f})" if abs(d['net'] - d['cote']) > 1e-9 else ''
    L = [f"🧪 <b>H19 — Valeur contre Pinnacle juste</b>",
         f"{lien_joueur.duo_html(joueur, adv)}",
         f"{g.get('_tour') or '?'} · T-{lead_txt} · horizon {d['horizon']}",
         f"💶 <b>{d['book']} @ {d['cote']:.2f}</b>{net} · cote juste Pinnacle {d['juste']:.2f} → "
         f"<b>écart {d['ecart_pct']:+.1f} %</b>",
         f"Pinnacle {d['pin']:.2f} · cote du book vieille de {d['age_min']:.0f} min",
         "⏱️ L'avantage vient d'une erreur de prix : il disparaît vite (le book corrige)."]
    s = suivi()
    if s:
        n, clv, cible, n_roi, roi = s
        L.append(f"\n📊 <b>Suivi</b> : {n}/{cible} paris" + (f" · CLV {clv:+.1f} %" if clv is not None else ''))
        if n_roi and roi is not None:
            L.append(f"ROI {roi:+.1f} % sur {n_roi} pari(s) dénoué(s) — à ce stade, bruit : H19 se juge sur la CLV.")
    L.append(f"\n<i>Hypothèse gelée le {R['gele_le']}, NON VALIDÉE. Jugée sur la CLV, cible {R['cible_n']}. "
             f"Ne pas diffuser.</i>")
    return '\n'.join(L)


def statut(envoye):
    if envoye:
        return 'envoyé'
    if DRY_RUN:
        return 'non tenté (DRY_RUN)'
    if not os.environ.get('TELEGRAM_TOKEN') or not os.environ.get('TELEGRAM_CHAT_ID'):
        return 'non tenté (jeton Telegram absent)'
    return 'échec Telegram'


def traiter(games, etat, maintenant, R, sha, ecrire=True):
    """Une passe du détecteur à l'instant `maintenant` ; renvoie les lignes de journal produites."""
    produites = []
    for uid, g in games.items():
        if g['_ct'] <= maintenant or circuit(g.get('_tour')) not in CIRCUITS_OK:
            continue
        for side in ('h', 'a'):
            cle = f"{uid}|{side}"
            if cle in etat:
                continue                              # un pari par (match, joueur)
            for horizon in ('24h', '6h', '1h', '10m'):
                lead, _ = HORIZONS[horizon]
                decision = g['_ct'] - datetime.timedelta(minutes=lead)
                if decision > maintenant:
                    break                             # horizons suivants : pas encore leur heure
                retard = (maintenant - decision).total_seconds() / 60
                d = evaluer(g, side, horizon, R)
                if d is None:
                    continue
                if retard > RATTRAPAGE_MIN:
                    # Horizon passé depuis trop longtemps (script arrêté) : noté comme
                    # manqué, sans alerte — le Lab le compte quand même.
                    etat[cle] = {'t': maintenant.isoformat(timespec='seconds'), 'horizon': horizon,
                                 'manque': True, 'commence': g['_ct'].isoformat()}
                    break
                ok = envoyer(message(g, side, d, R, maintenant)) if ecrire else False
                joueur, adv = (g['_home'], g['_away']) if side == 'h' else (g['_away'], g['_home'])
                rec = {'schema': SCHEMA, 'hypothese': 'H19', 'uid': uid, 'joueur': joueur, 'adversaire': adv,
                       'side': side, 'tournoi': g.get('_tour'), 'circuit': circuit(g.get('_tour')),
                       'horizon': d['horizon'], 'detecte_le': d['decision'].isoformat(timespec='seconds'),
                       'signale_le': maintenant.isoformat(timespec='seconds'), 'commence': g['_ct'].isoformat(),
                       'book': d['book'], 'cote': round(d['cote'], 3), 'cote_nette': round(d['net'], 4),
                       'age_cote_min': round(d['age_min'], 1), 'pin': d['pin'], 'pin_autre': d['pin_autre'],
                       'juste': round(d['juste'], 4), 'ecart_pct': round(d['ecart_pct'], 3),
                       'envoye': ok, 'statut_envoi': statut(ok), 'regle_hash': sha[:12], 'gele_le': R['gele_le']}
                if ecrire:
                    with open(LOG, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                produites.append(rec)
                etat[cle] = {'t': maintenant.isoformat(timespec='seconds'), 'horizon': horizon, 'book': d['book'],
                             'cote': round(d['cote'], 2), 'envoye': ok, 'commence': g['_ct'].isoformat()}
                break
    return produites


def main():
    R, sha = regle()
    maintenant = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    if os.environ.get('H19_MAINTENANT'):            # rejeu (tests) : instant simulé
        maintenant = _dt(os.environ['H19_MAINTENANT'])
    print(f"H19 SIGNAL (canal privé) — écart {R['ecart_min_pct']:g}–{R['ecart_max_pct']:g} % vs Pinnacle juste · "
          f"{len(R['books'])} books · gel {sha[:12]}" + ("  [DRY RUN]" if DRY_RUN else ""))
    try:
        etat = json.load(open(ETAT, encoding='utf-8'))
    except (OSError, ValueError):
        etat = {}
    games = charger()
    recs = traiter(games, etat, maintenant, R, sha)
    # purge : matchs commencés depuis plus de 2 jours
    limite = maintenant - datetime.timedelta(days=2)
    etat = {k: v for k, v in etat.items() if (_dt(v.get('commence')) or maintenant) > limite}
    ov.ecriture_atomique(ETAT, etat, ensure_ascii=False, indent=1)
    print(f"  {len(games)} matchs · {len(recs)} détection(s) H19 · {sum(r['envoye'] for r in recs)} envoyée(s)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
