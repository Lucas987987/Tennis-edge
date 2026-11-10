from pathlib import Path
p=Path('algo/index.html')
s=p.read_text(encoding='utf-8')
marker='<!-- TE_MATCH_UI_2026_11 -->'
if marker in s:
    print('Déjà installé');raise SystemExit(0)
def change(a,b,expected=1):
 global s
 n=s.count(a)
 if n!=expected: raise RuntimeError(f'Attendu {expected} occurrence(s), trouvé {n}: {a[:95]!r}')
 s=s.replace(a,b)
# Cartes immédiatement sous les probabilités, avant les boutons de partage.
change('        ${rendType(m)}${rendFiabilite(m.fiabilite, true)}\n', '        ${rendType(m)}${rendFiabilite(m.fiabilite, true)}\n        ${rendCartes(m)}\n')
change('      </div>\n      ${rendCartes(m)}\n      <div class="panel live-match"','      </div>\n      <div class="panel live-match"')
# La carte a son propre panneau; éviter un emboîtement de panneaux mal dimensionné.
change('<div class="panel cartes" style="padding:16px">','<div class="panel cartes" style="padding:16px;margin:14px 0">')
# Nouvel onglet live dans la barre de filtres.
change('        <button type="button" data-circuit="CH" aria-pressed="false">CH</button>\n      </div>', '        <button type="button" data-circuit="CH" aria-pressed="false">CH</button>\n        <button type="button" data-circuit="LIVE" aria-pressed="false">🔴 LIVE</button>\n      </div>')
change("(circuit==='TOUS' || m.circuit===circuit) &&", "(circuit==='TOUS' || (circuit==='LIVE' ? !!LIVE.par_uid[m.uid] : m.circuit===circuit)) &&")
# Tiroir des matchs terminés au début de la liste, sauf dans le filtre LIVE.
change("ul.innerHTML = visibles.map(ligneMatch).join('') + (termines.length ? `<li class=\"finished-group\"><details ${etaitOuvert?'open':''}><summary>${esc(L==='fr'?'Matchs terminés':'Finished matches')} (${termines.length})</summary><ul class=\"list\">${visiblesFinis.map(ligneMatch).join('')}</ul></details></li>` : '');", "ul.innerHTML = (termines.length && circuit!=='LIVE' ? `<li class=\"finished-group\"><details ${etaitOuvert?'open':''}><summary>${esc(L==='fr'?'Matchs terminés':'Finished matches')} (${termines.length})</summary><ul class=\"list\">${visiblesFinis.map(ligneMatch).join('')}</ul></details></li>` : '') + visibles.map(ligneMatch).join('');")
# Quand le flux live n'a pas de match, indiquer explicitement le résultat.
change("ul.innerHTML = `<li class=\"empty\" style=\"display:block\">${esc(t('liste_vide'))}</li>`;", "ul.innerHTML = `<li class=\"empty\" style=\"display:block\">${esc(circuit==='LIVE' ? (L==='fr'?'Aucun match en direct actuellement.':'No live matches at the moment.') : t('liste_vide'))}</li>`;")
# Permettre au LIVE d'être actualisé par le mécanisme existant, sans ajouter de requête API.
change("const tous = matchsFiltres();\n  // Un match est terminé", "const tous = matchsFiltres();\n  // Un match est terminé")
# Indicateur de version dans le document
change('</head>',marker+'\n</head>')
p.write_text(s,encoding='utf-8')
print('OK: cartes sous le duel, terminés en premier, filtre LIVE fondé sur LIVE.par_uid')
