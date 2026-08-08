#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal_public.py — Canal public « Évolution des cotes tennis ».

Publie sur un canal Telegram PUBLIC des messages d'INFORMATION sur les
mouvements de cotes pré-match : quel joueur voit sa cote se raccourcir chez
Pinnacle (le prix de référence du marché), de combien, et où en sont les
autres opérateurs par rapport au juste prix estimé (dévig Shin).

AUCUN vocabulaire d'incitation : pas de « miser », « parier », « jouer »,
aucune promesse. C'est un flux d'observation des marchés — le positionnement
« outil d'information », conforme à l'esprit des règles FR (ANJ/DGCCRF) qui
prohibent toute communication laissant croire qu'on augmente les chances de
gagner. Chaque message porte le pied de page 18+/jeu responsable.

Fonctionnement (0 requête API — fichiers locaux uniquement) :
  - lit book_curves_live.jsonl (trajectoires pré-match multi-books),
  - détecte les mouvements Pinnacle >= paliers (PALIERS, en points de proba),
  - 1 message max par match et par palier (état canal_public_state.json),
  - loggue chaque publication dans canal_public_log.jsonl (pour le récap hebdo),
  - envoie via TELEGRAM_TOKEN + TELEGRAM_PUBLIC_CHAT_ID (DRY_RUN sinon).

Env : CURVES (book_curves_live.jsonl), PALIERS ("5,8,12"), MIN_LEAD_MIN (45),
      MAX_LEAD_MIN (2880 = 48h), STATE, LOG, DRY_RUN.
"""
import os, json, math, datetime, urllib.request, urllib.parse, re, unicodedata

CURVES   = os.environ.get('CURVES', 'book_curves_live.jsonl')
PALIERS  = [float(x)/100 for x in os.environ.get('PALIERS', '5,8,12').split(',')]
MIN_LEAD = float(os.environ.get('MIN_LEAD_MIN', '45'))     # trop tard = bruit d'avant-match
MAX_LEAD = float(os.environ.get('MAX_LEAD_MIN', '2880'))   # > 48h = pas encore pertinent
MAX_MAG  = float(os.environ.get('MAX_MAG_PTS', '20')) / 100   # au-dela = in-play probable
# Seuil de « retard » : mesure sur les ecarts REELLEMENT publies (canal_clv.py) ->
# sous 5%, l'ecart ne se referme pas (CLV median 0%, 38% de refermeture) ;
# a partir de 5% : CLV median +4,2%, 53% de refermeture. On ne signale donc que
# les ecarts >= GAP_MIN.
GAP_MIN  = float(os.environ.get('GAP_MIN_PCT', '5')) / 100
# Les EXCHANGES ne sont pas des operateurs « en retard » : sans marge integree,
# leur prix est structurellement plus haut. Les signaler fausse la mesure
# (CLV median -1,6% sur l'echantillon). On les exclut de la ligne des retards.
EXCHANGES = set(b.strip() for b in os.environ.get(
    'EXCHANGES', 'betfair-ex,betfair,matchbook,smarkets,betdaq').split(',') if b.strip())
# Publication CONDITIONNELLE des petits mouvements : sous ce palier, on ne publie
# QUE si un operateur est encore en retard (ligne 🏪). Un petit move sans retard
# n'apprend rien ("tout le monde a deja ajuste") et dilue le canal.
# Mesure sur l'historique : 13,6 -> 7,4 msg/jour, mais % de messages avec retard
# 6% -> 10% (aucun message interessant perdu). 0 = desactive la regle.
PALIER_SOLO = float(os.environ.get('PALIER_SOLO_PTS', '5')) / 100
UPCOMING = os.environ.get('UPCOMING', 'matches_oddspapi.json')  # source de verite horaires
STATE    = os.environ.get('STATE', 'canal_public_state.json')
LOG      = os.environ.get('LOG', 'canal_public_log.jsonl')
TOKEN    = os.environ.get('TELEGRAM_TOKEN', '')
CHAT     = os.environ.get('TELEGRAM_PUBLIC_CHAT_ID', '')
DRY      = os.environ.get('DRY_RUN', '') == '1' or not (TOKEN and CHAT)

FOOTER = ("\n—\nℹ️ Information sur l'évolution des marchés de cotes. "
          "Ceci n'est pas un conseil. Aucun résultat n'est garanti.\n"
          "18+ | Le jeu comporte des risques : joueurs-info-service.fr · 09 74 75 13 13")


def _norm(x):
    x = unicodedata.normalize('NFD', str(x).lower().strip())
    x = ''.join(c for c in x if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', x).strip('_')


def _pairkey(uid):
    """uid = 'YYYY-MM-DD_home_away' -> 'home_away' (identifie le match sans la date)."""
    return uid.split('_', 1)[1] if '_' in uid else uid


def load_upcoming():
    """{pairkey: commence_time} des matchs encore listes A VENIR par l'API.
    C'est la SOURCE DE VERITE : les horaires bougent (reports, 'not before'),
    et les courbes accumulees peuvent garder un commence_time perime -> des points
    IN-PLAY passent alors pour du pre-match (bug observe : Hurkacz/Giron publie
    'depart dans 3h29' alors que le match etait commence depuis 1h).
    Renvoie None si indisponible -> l'appelant continue sans ce garde (fail-open)."""
    if not os.path.exists(UPCOMING):
        return None
    try:
        d = json.load(open(UPCOMING, encoding='utf-8'))
    except Exception:
        return None
    items = d if isinstance(d, list) else list(d.values())
    out = {}
    for m in items:
        if not isinstance(m, dict):
            continue
        h, a, ct = m.get('home_team'), m.get('away_team'), m.get('commence_time')
        if not (h and a and ct):
            continue
        t = _dt(ct)
        if not t:
            continue
        k = f"{_norm(h)}_{_norm(a)}"
        if k not in out or t < out[k]:
            out[k] = t
    return out


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def shin_ph(oh, oa):
    """Proba home dévigée (Shin, 2 issues) — le « juste prix » estimé."""
    ih, ia = 1/oh, 1/oa
    s = ih + ia
    if s <= 1:
        return ih / s
    z = 0.02
    for _ in range(50):
        ph = (math.sqrt(z*z + 4*(1-z)*ih*ih/s) - z) / (2*(1-z))
        pa = (math.sqrt(z*z + 4*(1-z)*ia*ia/s) - z) / (2*(1-z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z = min(max(z + (t-1), 0.0), 0.3)
    return ph / (ph + pa)


def load_games(now):
    games = {}
    upcoming = load_upcoming()
    if not os.path.exists(CURVES):
        return games
    for line in open(CURVES, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        ct = _dt(r.get('commence_time'))
        if not ct:
            continue
        if upcoming is not None:
            official = upcoming.get(_pairkey(r['uid']))
            if official is None:
                continue          # plus liste comme a venir => commence/termine
            ct = official         # horaire officiel, pas celui (perime) de la courbe
        lead = (ct - now).total_seconds() / 60.0
        if lead < MIN_LEAD or lead > MAX_LEAD:
            continue
        def pre(seq):
            pts = [(_dt(p[0]), p[1]) for p in (seq or []) if _dt(p[0]) and p[1] and p[1] > 1]
            return sorted(x for x in pts if x[0] < ct)
        h, a = pre(r.get('home_curve')), pre(r.get('away_curve'))
        if len(h) < 2 or len(a) < 2:
            continue
        g = games.setdefault(r['uid'], {'_ct': ct, '_lead': lead,
                                        '_home': r.get('home_team') or r.get('home') or '',
                                        '_away': r.get('away_team') or r.get('away') or '',
                                        '_tour': r.get('tournament') or ''})
        g[r['book']] = {'h': h, 'a': a}
    return games


def fmt_lead(mins):
    if mins < 60:
        return f"{mins:.0f} min"
    if mins < 48*60:
        return f"{mins/60:.0f}h{int(mins % 60):02d}"
    return f"{mins/1440:.0f} j"


def tg_send(text):
    if DRY:
        print("--- DRY RUN (message non envoyé) ---")
        print(text)
        return True
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data=urllib.parse.urlencode({'chat_id': CHAT, 'text': text,
                                         'disable_web_page_preview': 'true'}).encode())
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print(f"⚠️ envoi Telegram: {e}")
        return False


def main():
    now = datetime.datetime.utcnow()
    state = {}
    if os.path.exists(STATE):
        try:
            state = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            state = {}
    games = load_games(now)
    sent = 0
    for uid, g in games.items():
        pin = g.get('pinnacle')
        if not pin:
            continue
        oh0, oa0 = pin['h'][0][1], pin['a'][0][1]
        oh1, oa1 = pin['h'][-1][1], pin['a'][-1][1]
        p0, p1 = shin_ph(oh0, oa0), shin_ph(oh1, oa1)
        shift = p1 - p0
        mag = abs(shift)
        palier = max([p for p in PALIERS if mag >= p], default=None)
        if palier is None:
            continue
        if mag > MAX_MAG:
            print(f"  ⏭️ {uid}: mouvement {mag*100:.0f} pts > {MAX_MAG*100:.0f} "
                  f"— in-play ou horaire douteux, non publie")
            continue
        if state.get(uid, 0) >= palier:
            continue                       # déjà signalé à ce palier (ou plus haut)
        side = 'h' if shift > 0 else 'a'
        name = g['_home'] if side == 'h' else g['_away']
        other = g['_away'] if side == 'h' else g['_home']
        o_open = oh0 if side == 'h' else oa0
        o_now = oh1 if side == 'h' else oa1
        p_side = p1 if side == 'h' else 1 - p1
        fair = 1.0 / p_side if p_side > 0 else None
        # opérateurs encore au-dessus du juste prix (retard d'ajustement)
        lags = []
        for b, s in g.items():
            if b.startswith('_') or b == 'pinnacle' or b in EXCHANGES:
                continue
            cur = (s['h'] if side == 'h' else s['a'])[-1][1]
            if fair and cur >= fair * (1 + GAP_MIN):
                lags.append((b, cur, (cur/fair - 1) * 100))
        lags.sort(key=lambda x: -x[2])
        if palier < PALIER_SOLO and not lags:
            continue        # petit mouvement sans operateur en retard -> pas publie
        lag_line = (" · ".join(f"{b} {c:.2f} (+{g_:.0f}% vs juste prix)" for b, c, g_ in lags[:3])
                    if lags else "tous les opérateurs suivis ont déjà ajusté")
        msg = (f"📊 ÉVOLUTION DE COTE · {g['_home']} vs {g['_away']}"
               + (f" ({g['_tour']})" if g['_tour'] else "") + "\n"
               f"📉 {name} : {o_open:.2f} → {o_now:.2f} chez Pinnacle "
               f"({mag*100:.0f} pts de probabilité en sa faveur)\n"
               f"⚖️ Juste prix estimé (dévig Shin) : {fair:.2f}\n"
               f"🕐 Départ dans {fmt_lead(g['_lead'])}\n"
               f"🏪 Ajustement des autres opérateurs : {lag_line}\n"
               f"Le marché a revu {name} à la hausse face à {other}. "
               f"Historiquement, ce type d'écart se referme avant le début du match."
               + FOOTER)
        if tg_send(msg):
            sent += 1
            state[uid] = palier
            with open(LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    't': now.isoformat(), 'uid': uid, 'palier': palier,
                    'cote_ref_avant': o_open, 'cote_ref_apres': o_now,
                    'joueur': name, 'juste_prix': round(fair, 3) if fair else None,
                    'retards': [[b, c, round(g_, 1)] for b, c, g_ in lags[:3]],
                    'commence': g['_ct'].isoformat(),
                }, ensure_ascii=False) + "\n")
    json.dump(state, open(STATE, 'w', encoding='utf-8'))
    print(f"canal public : {sent} évolution(s) publiée(s) · {len(games)} matchs en fenêtre")


if __name__ == '__main__':
    main()
