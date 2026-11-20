#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
barometre.py — Baromètre des opérateurs (tennis), hebdo et mensuel.

Publie un état FACTUEL du marché, calculé sur les cotes capturées :
  • Marge (overround) moyenne de chaque opérateur — plus elle est basse, plus le
    prix rendu au parieur est élevé.
  • Fréquence de meilleure cote — à quelle fréquence l'opérateur affiche le
    meilleur prix du panel sur un match donné.
  • Générosité vs juste prix — écart moyen au fair estimé (dévig Shin sur la
    référence Pinnacle) ; positif = prix au-dessus du juste prix.
  • Réactivité — écart-type de l'écart au fair : plus il est faible, plus
    l'opérateur suit la référence de près.
  • Couverture — nombre de matchs de tennis cotés sur la période.

Aucun pronostic, aucune incitation : c'est une mesure du marché, publiable telle
quelle (pied de page 18+ / jeu responsable).

Env : PERIOD (week|month|both, def both), CURVES (liste séparée par des virgules),
      MIN_MATCHS (12), FOCUS (sous-ensemble d'opérateurs à mettre en avant, ex.
      les books FR), TELEGRAM_TOKEN, TELEGRAM_PUBLIC_CHAT_ID, DRY_RUN, OUT_DIR.
"""
import os, json, math, datetime, statistics as st, urllib.request, urllib.parse
from collections import defaultdict

CURVES  = [c.strip() for c in os.environ.get(
    'CURVES', 'book_curves_live.jsonl,book_curves.jsonl').split(',') if c.strip()]
PERIOD  = os.environ.get('PERIOD', 'both')
MIN_M   = int(os.environ.get('MIN_MATCHS', '12'))
# Opérateurs AGRÉÉS ANJ (seuls promouvables auprès du public français ; la liste
# officielle fait foi : anj.fr/offre-de-jeu-et-marche/operateurs-agrees).
# Ce sont les SEULS qui peuvent porter un lien d'affiliation.
ANJ = [b.strip() for b in os.environ.get(
    'ANJ_BOOKS',
    'winamax.fr,unibet.fr,zebet.fr,netbet.fr,bwin.fr,betsson.fr,bet365.fr,'
    'genybet.fr,feelingbet.fr,circusbet.fr,vbet.fr,pmu').split(',') if b.strip()]
# Références de marché : servent au CALCUL du juste prix, jamais promues, sans lien.
REFS = [b.strip() for b in os.environ.get('REF_BOOKS', 'pinnacle,betfair-ex').split(',') if b.strip()]
# Liens d'affiliation : fichier JSON {"unibet.fr": "https://...", ...}. Un lien
# n'est utilisé QUE si l'opérateur est dans ANJ (garde-fou : promouvoir un
# opérateur non agréé est une infraction, pour l'affilié comme pour l'opérateur).
AFF_FILE = os.environ.get('AFFILIATES', 'affiliates.json')
SHARP   = os.environ.get('SHARP', 'pinnacle')
OUT_DIR = os.environ.get('OUT_DIR', '.')
TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
CHAT    = os.environ.get('TELEGRAM_PUBLIC_CHAT_ID', '')
DRY     = os.environ.get('DRY_RUN', '') == '1' or not (TOKEN and CHAT)

FOOTER = ("\n—\nℹ️ Mesures factuelles calculées sur les cotes captées (référence Pinnacle, "
          "juste prix par dévig Shin). Information, pas un conseil.\n"
          "18+ | joueurs-info-service.fr · 09 74 75 13 13")


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def shin_ph(oh, oa):
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


def load(days):
    """{uid: {book: (cote_home, cote_away)}} sur les matchs des `days` derniers jours,
    au dernier point PRÉ-MATCH de chaque opérateur."""
    now = datetime.datetime.utcnow()
    cut = now - datetime.timedelta(days=days)
    games = defaultdict(dict)
    for src in CURVES:
        if not os.path.exists(src):
            continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            ct = _dt(r.get('commence_time'))
            if not ct or ct < cut or ct > now:
                continue
            def last_pre(seq):
                pts = [(_dt(p[0]), p[1]) for p in (seq or []) if _dt(p[0]) and p[1] and p[1] > 1]
                pts = sorted(x for x in pts if x[0] < ct)
                return pts[-1][1] if pts else None
            h, a = last_pre(r.get('home_curve')), last_pre(r.get('away_curve'))
            if h and a:
                games[r['uid']][r['book']] = (h, a)
    return games


def compute(games):
    marge, ecart, best, cover = defaultdict(list), defaultdict(list), defaultdict(int), defaultdict(int)
    n_best = 0
    for uid, books in games.items():
        ref = books.get(SHARP)
        for b, (oh, oa) in books.items():
            cover[b] += 1
            marge[b].append((1/oh + 1/oa - 1) * 100)
        if ref:
            ph = shin_ph(*ref)
            for b, (oh, oa) in books.items():
                if b == SHARP:
                    continue
                fh, fa = 1/ph, 1/(1-ph)
                ecart[b].append(((oh/fh - 1) + (oa/fa - 1)) / 2 * 100)
        # meilleure cote : par côté, qui affiche le prix le plus élevé
        for idx in (0, 1):
            vals = [(v[idx], b) for b, v in books.items()]
            if len(vals) < 3:
                continue
            n_best += 1
            top = max(vals)[0]
            for v, b in vals:
                if v >= top - 1e-9:
                    best[b] += 1
    rows = []
    for b in cover:
        if cover[b] < MIN_M:
            continue
        rows.append(dict(
            book=b, n=cover[b],
            marge=st.mean(marge[b]) if marge[b] else None,
            ecart=st.mean(ecart[b]) if ecart[b] else None,
            stab=st.pstdev(ecart[b]) if len(ecart[b]) > 1 else None,
            best=100 * best[b] / n_best if n_best else 0))
    return sorted(rows, key=lambda r: (r['marge'] is None, r['marge']))


def load_affiliates():
    if not os.path.exists(AFF_FILE):
        return {}
    try:
        d = json.load(open(AFF_FILE, encoding='utf-8'))
    except Exception:
        return {}
    # garde-fou : on ne retient que les liens d'operateurs AGREES
    return {k: v for k, v in d.items() if k in ANJ and isinstance(v, str) and v.startswith('http')}


def render(rows, label, ndays, ngames):
    if not rows:
        return None
    aff = load_affiliates()
    agrees = [r for r in rows if r['book'] in ANJ]
    refs = [r for r in rows if r['book'] in REFS]
    L = [f"📊 BAROMÈTRE DES OPÉRATEURS — {label}",
         f"Tennis · {ngames} matchs analysés · {ndays} derniers jours", ""]

    if agrees:
        L.append("Opérateurs agréés ANJ — marge moyenne (plus bas = prix rendu plus élevé) :")
        for r in sorted(agrees, key=lambda x: x['marge']):
            lien = f"\n     → {aff[r['book']]}" if r['book'] in aff else ""
            best = f" · meilleure cote {r['best']:.0f}% des cas" if r['best'] else ""
            L.append(f"  {r['book']} : {r['marge']:.1f}%{best} ({r['n']} matchs){lien}")

    if refs:
        L.append("\nRéférences de marché (servent au calcul du juste prix, non promues) :")
        for r in refs:
            L.append(f"  {r['book']} : marge {r['marge']:.1f}% ({r['n']} matchs)")

    ecarts = [r for r in agrees if r['ecart'] is not None]
    if ecarts:
        L.append("\nÉcart moyen au juste prix estimé (0% = prix fair) :")
        for r in sorted(ecarts, key=lambda x: -x['ecart']):
            sv = ""
            if r['stab'] is not None:
                sv = f" · suivi {'serré' if r['stab'] < 3 else 'plus lâche'}"
            L.append(f"  {r['book']} : {r['ecart']:+.1f}%{sv}")

    L.append("\nMéthode : dernier prix pré-match de chaque opérateur, juste prix par "
             "dévig Shin sur la référence de marché. Chiffres bruts, sans classement "
             "éditorial : à chacun d'en tirer ses conclusions. Calcul rejouable.")
    foot = FOOTER
    if aff:
        foot = ("\n—\n🔗 Publicité — partenariat commercial : les liens ci-dessus sont des liens "
                "d'affiliation vers des opérateurs agréés par l'ANJ. Ils ne modifient "
                "en rien les mesures, produites automatiquement par script." + FOOTER)
    return "\n".join(L) + foot


def tg(text):
    if DRY:
        print("--- DRY RUN ---\n" + text)
        return
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=urllib.parse.urlencode({'chat_id': CHAT, 'text': text,
                                     'disable_web_page_preview': 'true'}).encode())
    urllib.request.urlopen(req, timeout=15)


def run(days, label, slug):
    games = load(days)
    rows = compute(games)
    msg = render(rows, label, days, len(games))
    if not msg:
        print(f"baromètre {slug} : pas assez de données ({len(games)} matchs)")
        return
    tg(msg)
    try:
        with open(os.path.join(OUT_DIR, f"barometre_{slug}.md"), 'w', encoding='utf-8') as f:
            f.write(msg)
    except Exception:
        pass
    print(f"baromètre {slug} publié : {len(rows)} opérateurs, {len(games)} matchs")


if __name__ == '__main__':
    if PERIOD in ('week', 'both'):
        run(7, "SEMAINE", "hebdo")
    if PERIOD in ('month', 'both'):
        run(30, "MOIS", "mensuel")
