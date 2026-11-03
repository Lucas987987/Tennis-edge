from pathlib import Path
import ast
p=Path('simulateur/pronostics_du_jour.py')
s=p.read_text(encoding='utf-8')
start=s.index('    ecart = abs(victoire - p_home)',s.index('def distribution_exacte_du_match('))
end=s.index('    rows = DE.scores_ordonnes(distribution)',start)
replacement=(
"    # Ancrage identique a match_simule.noeuds_de_forme : [0.005, 0.995].\n"
"    cible_exacte = min(max(p_home, 0.005), 0.995) if p_home is not None else None\n"
"    ecart = abs(victoire - cible_exacte) if cible_exacte is not None else 0.0\n"
"    if not controle['ok'] or (cible_exacte is not None and ecart > 1e-8):\n"
"        raise ValueError(f'Distribution exacte incohérente pour {h}–{a}: {controle}, victoire={victoire}, cible_exacte={cible_exacte}, simulation={p_home}')\n"
"    if p_home is not None and cible_exacte != p_home:\n"
"        print(f'::warning::Ancrage borne pour {h}–{a}: simulation={p_home}, cible_exacte={cible_exacte}')\n"
)
s=s[:start]+replacement+s[end:]
ast.parse(s)
assert abs(0.004999999999711853-min(max(0.0047,0.005),0.995)) < 1e-8
p.write_text(s,encoding='utf-8')
print('V4 correction applied and syntax validated')
