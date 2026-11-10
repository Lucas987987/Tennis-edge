from pathlib import Path
p=Path('algo/index.html')
s=p.read_text(encoding='utf-8')
marker='/* Tennis Edge : cartes horizontales + radar accessible en direct (11/2026) */'
if marker in s:
    print('Correctif deja applique'); raise SystemExit(0)
assert 'function rendMatchLive(){' in s
assert '${terrainLive(m, r, fini)}${tableauLive(m, r, fini, true)}${barreLive(m, r, fini, true)}${corps}</div>`;' in s
assert '<div class="cj-corps"><div class="cj-g">' in s
# Le radar utilise les memes donnees de cartes que l'avant-match, jamais les points du direct.
old='${terrainLive(m, r, fini)}${tableauLive(m, r, fini, true)}${barreLive(m, r, fini, true)}${corps}</div>`;'
new='${terrainLive(m, r, fini)}${tableauLive(m, r, fini, true)}${barreLive(m, r, fini, true)}${corps}${m.cartes && m.cartes.descriptif_seulement === true && Array.isArray(m.cartes.joueurs) && m.cartes.joueurs.length === 2 ? `<details class="lv-radar"><summary>📊 ${esc(L===\'fr\'?\'Radar des joueurs\':\'Player radar\')}</summary><div class="cartes lv-radar-content">${radarCartes(m.cartes.joueurs)}</div><p class="styles-note">${esc(t(\'cj_note\'))}</p></details>` : \'\'}</div>`;'
assert s.count(old)==1
s=s.replace(old,new)
css='''
<style id="te-horizontal-player-cards">
'''+marker+'''
/* Garder la presentation du duel au-dessus des cartes, en pleine largeur de page. */
.mdj:has(.cartes) { align-items:start; }
.mdj > .fiche > .cartes { min-width:0; }
.cartes .cj-corps {display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);gap:14px;align-items:center}
.cartes .cj-g {min-width:0;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.cartes .cj-corps > div {min-width:0}
.cartes .cj-r {max-width:100%;margin:0 auto}
.lv-radar {margin:14px 0 0;border:1px solid var(--line2);border-radius:12px;padding:10px 12px}
.lv-radar summary {cursor:pointer;font-weight:700;color:var(--ink)}
.lv-radar-content {padding:12px 0 0;max-width:450px;margin:auto}
.lv-radar .cj-r {width:100%;max-width:350px}
@media(max-width:640px){
 .cartes .cj-corps {grid-template-columns:minmax(0,1fr) minmax(0,.9fr);gap:8px}
 .cartes .cj-g {gap:5px}
 .cartes .cj-in {padding:7px 5px}
 .cartes .cj-n {font-size:1.6rem}
 .cartes .cj-m {width:36px;height:36px;font-size:.85rem}
 .cartes .cj-m:before,.cartes .cj-m:after {width:36px;height:36px}
 .cartes .cj-r text {font-size:10px}
}
</style>
'''
assert '</head>' in s
s=s.replace('</head>',css+'</head>',1)
p.write_text(s,encoding='utf-8')
print('Correctif applique : cartes en largeur et radar live')
