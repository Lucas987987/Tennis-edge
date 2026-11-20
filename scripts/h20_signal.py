#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h20_signal.py — H20 « Outsider WTA soutenu par Pinnacle », alerte EN DIRECT (canal privé).

RÈGLE : celle du gel (Tennis_Edge_Lab/registry/gel_h20.json), lue ici et
vérifiée par empreinte — jamais redéfinie. Mêmes calculs que l'Explorateur
(Tennis_Edge_Lab/explorer_matchs.py), à l'instant de décision de chaque horizon :
  — horizons 24 h, 6 h, 1 h, 10 min avant le début (dans cet ordre) ;
  — Pinnacle cote les deux joueurs à la décision (dernier point de moins de
    12 h / 3 h / 1 h / 50 min selon l'horizon, les deux à moins de 30 min) ;
  — circuit WTA, cote Pinnacle du joueur de 2 à 3,19 ;
  — mouvement = probabilité Pinnacle juste à l'horizon − celle du premier point
    Pinnacle, de +3,15 à +20 pts (le joueur a été soutenu) ;
  — prix d'entrée : meilleur book jouable hors Pinnacle, cote de 30 min au plus,
    commission de bourse déduite (réglage de l'Explorateur). S'il n'y en a pas,
    la décision compte quand même (comme dans l'Explorateur), sans CLV mesurable ;
  — un seul pari par (match, joueur) : le premier horizon qui remplit la règle.

Le verdict officiel est celui du Lab (Tennis_Edge_Lab/h20.py, courbes complètes) ;
ce journal (h20_signal_log.jsonl, écrit une fois) sert à comparer ce qui a été envoyé.

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
import meilleurs_prix               # noqa: E402 — 3 meilleurs prix (affichage)
import scenarios                    # noqa: E402 — scénarios en sets (affichage)

_spec = importlib.util.spec_from_file_location('tennis_edge_books_h20',
                                               os.path.join(RACINE, 'Tennis_Edge_Lab', 'books.py'))
books = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(books)

CURVES = os.environ.get('CURVES', 'book_curves_live.jsonl')
GEL = os.path.join(RACINE, 'Tennis_Edge_Lab', 'registry', 'gel_h20.json')
ETAT = 'h20_signal_state.json'
LOG = 'h20_signal_log.jsonl'
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
RATTRAPAGE_MIN = float(os.environ.get('RATTRAPAGE_MIN', '20'))
# (avance en min, ancienneté max du point Pinnacle en min) — bookmakers_sets_v5.HORIZONS
HORIZONS = {'24h': (1440, 720), '6h': (360, 180), '1h': (60, 60), '10m': (10, 50)}
SCHEMA = 1


def regle():
    """La règle gelée, avec contrôle d'empreinte (même calcul que Tennis_Edge_Lab/h20.empreinte)."""
    with open(GEL, encoding='utf-8') as f:
        doc = json.load(f)
    r = doc['regle']
    sha = hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    if sha != doc.get('sha256'):
        raise SystemExit(f"❌ gel H20 MODIFIÉ (empreinte {sha[:12]} ≠ {str(doc.get('sha256'))[:12]}) : aucune alerte.")
    return r, sha


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', '')).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


_spec2 = importlib.util.spec_from_file_location('tennis_edge_meta_h20',
                                                os.path.join(RACINE, 'Tennis_Edge_Lab', 'tennis_meta.py'))
meta = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(meta)


def circuit(tournoi):
    """Exactement le découpage du Lab (tennis_meta.circuit_of) ; doubles exclus comme dans l'Explorateur."""
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
    """Décision H20 pour un joueur à un horizon : dict, ou None si la règle n'est pas remplie."""
    lead, stale = HORIZONS[horizon]
    decision = g['_ct'] - datetime.timedelta(minutes=lead)
    pin = g.get('pinnacle')
    if not pin:
        return None
    autre = 'a' if side == 'h' else 'h'
    ps, po = point(pin[side], decision, stale), point(pin[autre], decision, stale)
    if not ps or not po or abs((ps[0] - po[0]).total_seconds()) > 1800:
        return None
    if not (R['cote_pin_min'] <= ps[1] <= R['cote_pin_max']):
        return None
    juste = books.fair_close(ps[1], po[1])
    juste_open = books.fair_close(pin[side][0][1], pin[autre][0][1])
    if not juste or not juste_open:
        return None
    ampleur = 100 * (1 / juste - 1 / juste_open)
    if not (R['ampleur_pts_min'] <= ampleur <= R['ampleur_pts_max']):
        return None
    best = None
    for b, s in g.items():
        if b.startswith('_') or b == 'pinnacle' or not books.flags(b)['jouable']:
            continue
        q = point(s[side], decision, R['age_max_min'])
        if not q:
            continue
        net = books.effective_odds(b, q[1])
        if best is None or net > best['net']:
            best = {'book': b, 'cote': q[1], 'net': net, 'age_min': (decision - q[0]).total_seconds() / 60}
    if best is None:                        # comptée quand même (règle de l'Explorateur), sans prix jouable
        best = {'book': None, 'cote': None, 'net': None, 'age_min': None}
    return {'horizon': horizon, 'decision': decision, 'pin': ps[1], 'pin_autre': po[1], 'juste': juste,
            'pin_open': pin[side][0][1], 'ampleur_pts': ampleur,
            'ecart_pct': 100 * (best['net'] / juste - 1) if best['net'] else None, **best}


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
    """Bilan prospectif du Lab (live/h20.json), s'il existe."""
    try:
        v = json.load(open(os.path.join(RACINE, 'Tennis_Edge_Lab', 'live', 'h20.json'), encoding='utf-8'))
        p = v['prospectif']
        return (p['clv_n'], p.get('clv_moy_pct'), v['regle']['cible_n'], p.get('regles') or 0, p.get('roi_pct'))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def message(g, side, d, R, maintenant):
    joueur = g['_home'] if side == 'h' else g['_away']
    adv = g['_away'] if side == 'h' else g['_home']
    lead = (g['_ct'] - maintenant).total_seconds() / 60
    lead_txt = f"{int(lead)} min" if lead < 60 else f"{int(lead // 60)}h{int(lead % 60):02d}"
    L = [f"🧪 <b>H20 — Outsider WTA soutenu par Pinnacle</b>",
         f"{lien_joueur.duo_html(joueur, adv)}",
         f"{g.get('_tour') or '?'} · T-{lead_txt} · horizon {d['horizon']}",
         f"📈 Pinnacle {d['pin_open']:.2f} → <b>{d['pin']:.2f}</b> · probabilité <b>{d['ampleur_pts']:+.1f} pts</b>",
         ]
    if d['book']:
        net = f" (net {d['net']:.2f})" if abs(d['net'] - d['cote']) > 1e-9 else ''
        L.append(f"💶 <b>{d['book']} @ {d['cote']:.2f}</b>{net} · cote juste Pinnacle {d['juste']:.2f} "
                 f"({d['ecart_pct']:+.1f} %) · cote vieille de {d['age_min']:.0f} min")
    else:
        L.append(f"💶 Aucun book jouable de moins de 30 min (cote juste Pinnacle {d['juste']:.2f}) : "
                 f"décision comptée, sans CLV mesurable")
    prix = meilleurs_prix.ligne(g, side, maintenant)  # 3 meilleurs prix frais (affichage seul)
    if prix:
        L.append(prix)
    sc = scenarios.ligne(g, side, maintenant)  # 2-0 / 2-1… depuis la cote Pinnacle (affichage seul)
    if sc:
        L.append(sc)
    n, clv, cible, n_roi, roi = suivi() or (0, None, R['cible_n'], 0, None)
    L.append(f"\n📊 <b>Suivi</b> : {n}/{cible} paris" + (f" · CLV {clv:+.1f} %" if clv is not None else ''))
    if n_roi and roi is not None:
        L.append(f"💰 <b>ROI {roi:+.1f} %</b> sur {n_roi} pari(s) dénoué(s) — bruit à ce stade : H20 se juge sur la CLV.")
    else:
        L.append("💰 ROI : aucun pari dénoué depuis le gel pour l'instant.")
    L.append(f"\n<i>Hypothèse gelée le {R['gele_le']}, NON VALIDÉE. "
             f"Jugée sur la CLV, cible {R['cible_n']}. Ne pas diffuser.</i>")
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
        if g['_ct'] <= maintenant or circuit(g.get('_tour')) not in R['circuits']:
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
                rec = {'schema': SCHEMA, 'hypothese': 'H20', 'uid': uid, 'joueur': joueur, 'adversaire': adv,
                       'side': side, 'tournoi': g.get('_tour'), 'circuit': circuit(g.get('_tour')),
                       'horizon': d['horizon'], 'detecte_le': d['decision'].isoformat(timespec='seconds'),
                       'signale_le': maintenant.isoformat(timespec='seconds'), 'commence': g['_ct'].isoformat(),
                       'book': d['book'], 'cote': d['cote'] and round(d['cote'], 3),
                       'cote_nette': d['net'] and round(d['net'], 4),
                       'age_cote_min': None if d['age_min'] is None else round(d['age_min'], 1), 'pin': d['pin'], 'pin_autre': d['pin_autre'],
                       'juste': round(d['juste'], 4),
                       'ecart_pct': None if d['ecart_pct'] is None else round(d['ecart_pct'], 3),
                       'pin_open': d['pin_open'], 'ampleur_pts': round(d['ampleur_pts'], 3),
                       'envoye': ok, 'statut_envoi': statut(ok), 'regle_hash': sha[:12], 'gele_le': R['gele_le']}
                if ecrire:
                    with open(LOG, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                produites.append(rec)
                etat[cle] = {'t': maintenant.isoformat(timespec='seconds'), 'horizon': horizon, 'book': d['book'],
                             'cote': d['cote'] and round(d['cote'], 2), 'envoye': ok, 'commence': g['_ct'].isoformat()}
                break
    return produites


def main():
    R, sha = regle()
    maintenant = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    if os.environ.get('H20_MAINTENANT'):            # rejeu (tests) : instant simulé
        maintenant = _dt(os.environ['H20_MAINTENANT'])
    print(f"H20 SIGNAL (canal privé) — WTA, cote Pinnacle {R['cote_pin_min']:g}–{R['cote_pin_max']:g}, "
          f"mouvement +{R['ampleur_pts_min']:g} à +{R['ampleur_pts_max']:g} pts · gel {sha[:12]}" + ("  [DRY RUN]" if DRY_RUN else ""))
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
    print(f"  {len(games)} matchs · {len(recs)} détection(s) H20 · {sum(r['envoye'] for r in recs)} envoyée(s)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
