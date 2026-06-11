#!/usr/bin/env python3
"""
fetch_results_settlement.py — Flux RAPIDE de resultats via OddsPapi /settlement (v5).

Role (architecture "vitesse maintenant, verite ensuite") :
- Pour chaque match deja suivi en CLV (clv_history.jsonl porte fixture_id + noms),
  on demande la notation officielle du bookmaker (/fixtures/settlement) des qu'il est
  fini, et on en deduit le vainqueur de facon EXACTE (par fixtureId, zero ambiguite de
  noms) + le score en sets.
- Sorties :
    1) resultats_oddspapi.json  -> store EXACT keye par fixtureId (provisoire).
    2) gap-fill du backtest (colonne `resultat`/`src_resultat`) par NOMS, en reutilisant
       le matching eprouve de fetch_results_fast (same_player) -> nourrit les analyses
       existantes sans rien changer en aval.

REGLE : provisoire. Sackmann (fetch_results.py) reste PRIORITAIRE et ECRASE ensuite.
Ce module ne remplit QUE des resultats MANQUANTS (gap-fill) ; il ne verrouille aucun CLV.

Quota : 1 appel /settlement par match fini non encore resolu (dedup via le store).
Cle via env RAPIDAPI_KEY. Ne modifie jamais les fichiers en lecture seule.
"""
import json, os, datetime

import oddspapi_v5 as ov
# Reutilise le matching de fetch_results_fast (helpers au niveau module ;
# run() seulement sous __main__ -> import sans effet de bord)
from fetch_results_fast import same_player

CLV_LOG          = os.environ.get('CLV_LOG_FILE', 'clv_history.jsonl')
STORE            = os.environ.get('RESULTATS_OP_FILE', 'resultats_oddspapi.json')
BACKTEST         = os.environ.get('BACKTEST_FILE', 'backtest_tennis.csv')
# Marge avant de considerer un match "probablement fini" (h apres le coup d'envoi).
FINISHED_AFTER_H = float(os.environ.get('FINISHED_AFTER_H', '4'))
MAX_CALLS        = int(os.environ.get('MAX_SETTLEMENT_CALLS', '60'))


def parse_iso(s):
    if not s:
        return None
    s = str(s).replace('Z', '+00:00')
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def load_clv_matches():
    """Matchs uniques suivis en CLV : {fixture_id: {home,away,commence_time,tournament}}."""
    out = {}
    if not os.path.exists(CLV_LOG):
        return out
    with open(CLV_LOG, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            fid = d.get('fixture_id')
            if not fid:
                continue
            out[fid] = {
                'home': d.get('home', ''), 'away': d.get('away', ''),
                'commence_time': d.get('commence_time', ''),
                'tournament': d.get('tournament', ''),
            }
    return out


def load_store():
    if os.path.exists(STORE):
        try:
            return json.load(open(STORE, encoding='utf-8'))
        except Exception:
            pass
    return {}


def main():
    if not os.environ.get('RAPIDAPI_KEY'):
        print("X RAPIDAPI_KEY absente -- abandon")
        return

    matches = load_clv_matches()
    store = load_store()
    now = datetime.datetime.now(datetime.timezone.utc)

    # candidats = suivis en CLV, probablement finis, pas encore resolus dans le store
    todo = []
    for fid, m in matches.items():
        if fid in store and store[fid].get('winner'):
            continue
        ct = parse_iso(m['commence_time'])
        if ct is not None:
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=datetime.timezone.utc)
            if (now - ct).total_seconds() < FINISHED_AFTER_H * 3600:
                continue   # pas encore (probablement) fini
        todo.append((fid, m))

    print(f"[i] {len(matches)} matchs suivis | {len(store)} deja resolus | {len(todo)} a interroger")
    todo = todo[:MAX_CALLS]

    resolved = 0
    parsed = []   # (home, away, winner_name) pour gap-fill backtest
    for fid, m in todo:
        r = ov.settlement_result(fid)
        if not r['finished'] or not r['winner']:
            print(f"  .. {fid} {m['home']} v {m['away']} : pas encore note ({r['status_name']})")
            continue
        winner_name = m['home'] if r['winner'] == 'home' else m['away']
        sets = None
        if r['p1_sets'] is not None and r['p2_sets'] is not None:
            sets = f"{r['p1_sets']}-{r['p2_sets']}"
        store[fid] = {
            'home': m['home'], 'away': m['away'],
            'tournament': m['tournament'],
            'winner': r['winner'],           # 'home' / 'away'
            'winner_name': winner_name,
            'sets': sets,
            'p1_sets': r['p1_sets'], 'p2_sets': r['p2_sets'],
            'source': 'oddspapi_settlement', 'provisional': True,
            'resolved_at': now.isoformat(),
        }
        parsed.append((m['home'], m['away'], winner_name))
        resolved += 1
        print(f"  OK {fid} {m['home']} v {m['away']} -> {winner_name} ({sets})")

    # store exact (fixtureId)
    with open(STORE, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nOK {STORE} : +{resolved} nouveaux | {len(store)} au total")

    # gap-fill backtest par NOMS (src='oddspapi', ne remplit QUE le manquant)
    fill_backtest(parsed)


def fill_backtest(parsed):
    if not parsed or not os.path.exists(BACKTEST):
        return
    with open(BACKTEST, encoding='utf-8') as f:
        lines = [l for l in f.read().split('\n') if l.strip()]
    if len(lines) < 2:
        return
    headers = lines[0].split(';')
    def idx(n): return headers.index(n) if n in headers else -1
    iJA, iJB = idx('joueurA'), idx('joueurB')
    iRes = idx('resultat')
    iSrc = idx('src_resultat')
    if min(iJA, iJB, iRes) < 0:
        print("  !! Colonnes backtest manquantes : gap-fill CSV desactive")
        return
    rows = [l.split(';') for l in lines[1:]]
    for r in rows:
        while len(r) < len(headers):
            r.append('')
    created_src = False
    if iSrc < 0:
        headers.append('src_resultat'); iSrc = len(headers) - 1
        for r in rows:
            r.append('')
        created_src = True

    updated = 0; ambigus = 0
    for r in rows:
        if r[iRes].strip() not in ('', 'nan'):
            continue   # gap-fill only : ne jamais ecraser (Sackmann/Matchstat prioritaires)
        ja, jb = r[iJA], r[iJB]
        cands = [w for (a, b, w) in parsed
                 if (same_player(ja, a) and same_player(jb, b))
                 or (same_player(ja, b) and same_player(jb, a))]
        if not cands:
            continue
        if len({same_player(c, ja) for c in cands}) > 1:
            ambigus += 1; continue   # vainqueurs contradictoires -> on s'abstient
        win_name = cands[0]
        r[iRes] = '1' if same_player(win_name, ja) else '0'
        if iSrc >= 0:
            r[iSrc] = 'oddspapi'
        updated += 1

    if updated or created_src:
        out = [';'.join(headers)] + [';'.join(r) for r in rows]
        with open(BACKTEST, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out) + '\n')
    print(f"OK backtest (matching par noms) : {updated} resultats remplis" +
          (f" | !! {ambigus} ambigus" if ambigus else ""))


if __name__ == '__main__':
    main()
