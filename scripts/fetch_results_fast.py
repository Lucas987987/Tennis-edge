#!/usr/bin/env python3
"""
fetch_results_fast.py — Flux RAPIDE de résultats via l'API Tennis (Matchstat/RapidAPI).

Rôle dans l'architecture "vitesse maintenant, vérité ensuite" :
- Remplit la colonne `resultat` du backtest dès qu'un match est joué (sans attendre
  les ~10j de retard de Sackmann), pour pouvoir rafraîchir la forme et analyser vite.
- Sackmann (fetch_results.py) repassera ensuite et ÉCRASERA ces résultats avec sa
  donnée fiable + les stats détaillées. Ce module ne touche donc QUE `resultat`
  (et `anomalie`), et marque sa source via une colonne `src_resultat` si présente.

Principe : pour chaque tournoi présent dans le backtest avec des résultats manquants,
on lit son ID dans tournois_ids.json, on fait 1 appel getTournamentResults, on parse
récursivement (tout objet ayant 'match_winner'), et on matche par noms des 2 joueurs.

Économe en quota : 1 requête par tournoi à compléter (pas par match).

Clé via env RAPIDAPI_KEY. Ne modifie jamais les fichiers en lecture seule.
"""
import urllib.request, urllib.error, json, os, re, unicodedata, datetime

# ── Config ───────────────────────────────────────────────
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
BACKTEST = os.environ.get('BACKTEST_FILE', 'backtest_tennis.csv')
IDS_FILE = os.environ.get('TOURN_IDS_FILE', 'tournois_ids.json')

HEADERS = {
    'x-rapidapi-host': HOST,
    'x-rapidapi-key': RAPIDAPI_KEY,
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'application/json',
}


# ── Utilitaires ──────────────────────────────────────────
def norm_name(s):
    """Normalise un nom : minuscules, sans accents, sans tirets/points, espaces simples.
    Cohérent avec fetch_results.py + gère les tirets (Carreno-Busta vs Carreno Busta)."""
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('-', ' ')
    return re.sub(r'[.\s]+', ' ', s).strip()


def last_name(full):
    """Dernier mot du nom normalisé (nom de famille, discriminant)."""
    n = norm_name(full)
    return n.split(' ')[-1] if n else ''


def api_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            remaining = r.headers.get('x-ratelimit-requests-remaining', '?')
            return json.loads(r.read()), remaining
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:200]
        print(f"  ⚠️ HTTP {e.code}: {body}")
        return None, '?'
    except Exception as e:
        print(f"  ⚠️ Erreur réseau: {e}")
        return None, '?'


def find_api_matches(obj, out):
    """Aplatit la réponse getTournamentResults : récupère tout objet ayant 'match_winner'."""
    if isinstance(obj, dict):
        if 'match_winner' in obj:
            out.append(obj)
        else:
            for v in obj.values():
                find_api_matches(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_api_matches(v, out)


def winner_lastname(m):
    """Renvoie le nom de famille normalisé du vainqueur d'un match API."""
    wid = m.get('match_winner')
    p1, p2 = m.get('player1', {}), m.get('player2', {})
    if wid == p1.get('id'):
        return last_name(p1.get('name', ''))
    if wid == p2.get('id'):
        return last_name(p2.get('name', ''))
    return ''


def detect_anomalie_from_result(result):
    """Détecte un abandon depuis le champ result de l'API (ex: '6-3 4-1 ret.')."""
    if not result:
        return ''
    s = str(result).lower()
    if 'ret' in s or 'w/o' in s or 'walkover' in s or 'def' in s or 'aband' in s:
        return 'abandon'
    return ''


# ── Cœur ─────────────────────────────────────────────────
def run():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente — abandon")
        return

    # Charger la table de correspondance tournoi -> {tour, id}
    if not os.path.exists(IDS_FILE):
        print(f"❌ {IDS_FILE} introuvable. Crée-le avec le mapping nom->id.")
        return
    with open(IDS_FILE, encoding='utf-8') as f:
        tourn_ids = json.load(f)
    print(f"✅ {len(tourn_ids)} tournois connus dans {IDS_FILE}")

    # Charger le backtest
    if not os.path.exists(BACKTEST):
        print(f"❌ {BACKTEST} introuvable")
        return
    with open(BACKTEST, encoding='utf-8') as f:
        content = f.read()
    lines = [l for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        print("Backtest vide"); return
    headers = lines[0].split(';')

    def idx(name):
        return headers.index(name) if name in headers else -1
    iJA, iJB = idx('joueurA'), idx('joueurB')
    iRes, iAno = idx('resultat'), idx('anomalie')
    iTour, iDt = idx('tournoi'), idx('date_match')
    iSrc = idx('src_resultat')  # optionnelle : marque la source du résultat
    if iJA < 0 or iJB < 0 or iRes < 0 or iTour < 0:
        print("❌ Colonnes essentielles manquantes (joueurA/joueurB/resultat/tournoi)")
        return

    # Repérer les tournois ayant des résultats manquants
    rows = [l.split(';') for l in lines[1:]]
    for r in rows:
        while len(r) < len(headers):
            r.append('')

    tournois_a_completer = {}
    for r in rows:
        if r[iRes].strip() in ('', 'nan'):
            tournois_a_completer.setdefault(r[iTour].strip(), 0)
            tournois_a_completer[r[iTour].strip()] += 1

    if not tournois_a_completer:
        print("✅ Aucun résultat manquant — rien à faire")
        return
    print(f"\nTournois avec résultats manquants:")
    for t, n in tournois_a_completer.items():
        known = "✓" if t in tourn_ids else "✗ (ID inconnu)"
        print(f"  {n}x  {t}  [{known}]")

    # Pour chaque tournoi connu, 1 appel API et matching
    remaining = '?'
    total_updated = 0
    for tname, _ in tournois_a_completer.items():
        if tname not in tourn_ids:
            print(f"\n⏭️  {tname} : ID inconnu, ignoré (à ajouter dans {IDS_FILE})")
            continue
        info = tourn_ids[tname]
        tour, tid = info.get('tour'), info.get('id')
        url = f"https://{HOST}/tennis/v2/{tour}/tournament/results/{tid}"
        print(f"\n=== {tname} (id={tid}, {tour}) ===")
        data, remaining = api_get(url)
        if data is None:
            continue
        api_matches = []
        find_api_matches(data, api_matches)
        print(f"  {len(api_matches)} matchs récupérés de l'API")

        # Deux index pour un matching robuste :
        #  - par NOM COMPLET normalisé (prioritaire : distingue les frères, ex. Cerundolo)
        #  - par NOM DE FAMILLE (repli : gère les variations de prénom)
        # valeur : (nom_complet_gagnant, nom_famille_gagnant, result_str)
        api_full = {}   # frozenset(noms complets) -> infos
        api_last = {}   # frozenset(noms de famille) -> infos | None si ambigu
        for m in api_matches:
            n1 = norm_name(m.get('player1', {}).get('name', ''))
            n2 = norm_name(m.get('player2', {}).get('name', ''))
            if not n1 or not n2:
                continue
            wid = m.get('match_winner')
            p1, p2 = m.get('player1', {}), m.get('player2', {})
            win_full = n1 if wid == p1.get('id') else (n2 if wid == p2.get('id') else '')
            win_last = win_full.split(' ')[-1] if win_full else ''
            result_str = m.get('result', '')
            api_full[frozenset((n1, n2))] = (win_full, win_last, result_str)
            lk = frozenset((n1.split(' ')[-1], n2.split(' ')[-1]))
            # si collision sur les noms de famille, on marque l'entrée ambiguë (None)
            api_last[lk] = None if lk in api_last else (win_full, win_last, result_str)

        # Matcher les lignes du backtest de ce tournoi
        updated = 0
        ambigus = 0
        for r in rows:
            if r[iTour].strip() != tname:
                continue
            if r[iRes].strip() not in ('', 'nan'):
                continue  # déjà rempli
            na = norm_name(r[iJA])
            nb = norm_name(r[iJB])
            la, lb = na.split(' ')[-1], nb.split(' ')[-1]

            # 1) tentative par nom complet (le plus sûr)
            info = api_full.get(frozenset((na, nb)))
            # 2) repli par nom de famille, seulement si non ambigu
            if info is None:
                lk = frozenset((la, lb))
                cand = api_last.get(lk)
                if cand is None and lk in api_last:
                    ambigus += 1  # collision détectée, on n'ose pas matcher
                else:
                    info = cand

            if info:
                win_full, win_last, result_str = info
                # joueurA gagne ? Comparaison sur nom complet si possible, sinon famille
                if win_full in (na, nb):
                    r[iRes] = '1' if win_full == na else '0'
                else:
                    r[iRes] = '1' if win_last == la else '0'
                if iAno >= 0 and not r[iAno].strip():
                    ano = detect_anomalie_from_result(result_str)
                    if ano:
                        r[iAno] = ano
                if iSrc >= 0:
                    r[iSrc] = 'api_fast'
                updated += 1
        msg = f"  ✅ {updated} matchs mis à jour"
        if ambigus:
            msg += f" | ⚠️ {ambigus} non matchés (noms de famille ambigus)"
        print(msg)
        total_updated += updated

    print(f"\n=== TOTAL: {total_updated} résultats ajoutés (source rapide) ===")
    print(f"Requêtes API restantes ce mois: {remaining}")

    if total_updated > 0:
        # Réécrire le backtest (avec \n final pour éviter les lignes collées)
        out_lines = [';'.join(headers)] + [';'.join(r) for r in rows]
        csv_final = '\n'.join(out_lines) + '\n'
        with open(BACKTEST, 'w', encoding='utf-8') as f:
            f.write(csv_final)
        print(f"✅ {BACKTEST} mis à jour")
    else:
        print("Aucune modification à écrire")


if __name__ == '__main__':
    run()
