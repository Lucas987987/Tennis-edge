#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_set_results.py — Migration UNE FOIS des clés de set_results.json vers
l'uid CANONIQUE 'YYYY-MM-DD_home_away' (celui des courbes/journal).

Contexte : closing_lines.json contient des uid de DEUX formats (ancien
'atp_tournoi_x_vs_y' et date). fetch_set_results a écrit set_results.json avec
ces clés-là -> 0 jointure avec les courbes (uid date) -> pas de ROI possible.

Méthode : pour CHAQUE entrée de closing_lines (peu importe sa clé), on
reconstruit l'uid canonique depuis ses champs commence_time/home/away avec
EXACTEMENT le slug de build_live_curves, et on y copie le résultat trouvé sous
la clé closing dans set_results. Les anciennes clés sont conservées (aucune
perte) ; les uid canoniques déjà présents ne sont pas écrasés.

Usage : python scripts/migrate_set_results.py   (racine du repo, puis commit)
"""
import json, re, unicodedata

def _norm(s):  # IDENTIQUE à build_live_curves._norm
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')

def _slug(commence, home, away):  # IDENTIQUE à build_live_curves._slug
    return f"{(commence or '')[:10]}_{_norm(home)}_{_norm(away)}"

def main():
    sr = json.load(open('set_results.json', encoding='utf-8'))
    cl = json.load(open('closing_lines.json', encoding='utf-8'))
    out = dict(sr)
    migrated = skipped = nofields = 0
    for key, m in cl.items():
        if key not in sr:
            continue
        ct, h, a = m.get('commence_time'), m.get('home'), m.get('away')
        if not (ct and h and a):
            nofields += 1
            continue
        canon = _slug(ct, h, a)
        if canon == key or canon in out:
            skipped += 1
            continue
        out[canon] = sr[key]
        migrated += 1
    json.dump(out, open('set_results.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print(f"✅ {migrated} résultats dupliqués sous l'uid canonique | "
          f"{skipped} déjà OK/identiques | {nofields} sans champs | total {len(out)}")

if __name__ == '__main__':
    main()
