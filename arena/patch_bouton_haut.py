from pathlib import Path
p=Path('algo/index.html')
s=p.read_text(encoding='utf-8')
# Remove the bottom-right floating link, whether present from the previous integration or not.
import re
s=re.sub(r'<a\s+href="\.\./arena/"\s+style="position:fixed;bottom:18px;right:18px;[^\"]*">🏟️ Arena</a>', '', s)
# Always use an absolute GitHub Pages link; algo.tennis-edge.workers.dev is a different host.
url='https://lucas987987.github.io/Tennis-edge/arena/'
button='<a class="arena-nav" href="'+url+'" title="Jouer gratuitement à Tennis Edge Arena">🏟️ Arena</a>'
if 'class="arena-nav"' not in s:
    anchor='<div class="reglages">'
    assert anchor in s, 'En-tête introuvable'
    s=s.replace(anchor,anchor+'\n      '+button,1)
style='''
/* Arena : bouton visible dans la barre du haut, y compris sur mobile */
.arena-nav{display:inline-flex;align-items:center;justify-content:center;white-space:nowrap;min-height:34px;padding:7px 13px;border-radius:999px;background:#d4ff3a;color:#141225!important;text-decoration:none!important;font:800 13px system-ui,sans-serif;box-shadow:0 2px 12px rgba(130,170,0,.3)}
.arena-nav:hover,.arena-nav:focus-visible{background:#eaff88;outline:2px solid #80b000;outline-offset:2px}
@media(max-width:520px){.arena-nav{padding:7px 11px;font-size:12px}.reglages{gap:5px}}
'''
if '/* Arena : bouton visible' not in s:
    assert '</style>' in s
    s=s.replace('</style>',style+'</style>',1)
p.write_text(s,encoding='utf-8')
print('Bouton Arena ajouté en haut ; ancien bouton flottant supprimé')
