from pathlib import Path
p=Path('algo/index.html')
s=p.read_text(encoding='utf-8')
if 'te-cartes-pleine-largeur-v2' in s:
 print('Déjà installé'); raise SystemExit(0)
def change(a,b):
 global s
 assert s.count(a)==1,(a[:80],s.count(a))
 s=s.replace(a,b,1)
css='''<style>
/* te-cartes-pleine-largeur-v2 */
.mdj > .fiche{display:contents}
.mdj > .fiche > *{grid-column:1/-1;min-width:0}
.mdj > .fiche > .duelx{grid-column:1;grid-row:2}
.mdj > .fiche > .cartes{grid-column:1/-1;width:100%;box-sizing:border-box;margin:0!important}
.mdj > .fiche > .cartes .cj-corps{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);align-items:center;gap:clamp(12px,3vw,32px)}
.mdj > .fiche > .cartes .cj-r{max-width:460px}
@media(max-width:650px){.mdj > .fiche > .cartes .cj-corps{grid-template-columns:1fr}.mdj > .fiche > .cartes .cj-r{max-width:320px}}
@media(min-width:820px){.mdj > .fiche > .duelx{grid-column:2;grid-row:1}}
</style>'''
change('</head>',css+'</head>')
change("  const bAnalyse = document.getElementById('b-analyse-detaillee');",'''  const cartesPleineLargeur = zone.querySelector('.duelx .cartes');
  const fichePleineLargeur = zone.querySelector('.mdj > .fiche');
  if (cartesPleineLargeur && fichePleineLargeur) fichePleineLargeur.querySelector('.duelx').after(cartesPleineLargeur);
  const bAnalyse = document.getElementById('b-analyse-detaillee');''')
change("if (el.classList.contains('duelx') || el.id === 'post-zone'","if (el.classList.contains('duelx') || el.classList.contains('cartes') || el.id === 'post-zone'")
change("let cur = f.querySelector('.duelx');","let cur = f.querySelector(':scope > .cartes') || f.querySelector('.duelx');")
start=s.index('${corps}${m.cartes && m.cartes.descriptif_seulement')
end=s.index(" : ''}</div>`;",start)+len(" : ''}")
s=s[:start]+'${corps}'+s[end:]
p.write_text(s,encoding='utf-8')
print('Cartes pleine largeur, radar live doublon supprimé')
