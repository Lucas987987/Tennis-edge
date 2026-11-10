from pathlib import Path
import json,unicodedata
p=Path('algo/donnees.json')
if not p.exists():raise SystemExit('Source algo/donnees.json absente')
d=json.loads(p.read_text());matches=d.get('matchs',[]) if isinstance(d,dict) else []
def norm(s):return ''.join(x for x in unicodedata.normalize('NFKD',str(s).lower()) if not unicodedata.combining(x) and x.isalnum())
cards={}
for m in matches:
 if not isinstance(m,dict):continue
 for c in (m.get('cartes') or {}).get('joueurs',[]):
  if not isinstance(c,dict):continue
  name=c.get('nom') or c.get('name');note=c.get('note')
  if not name or not isinstance(note,(int,float)):continue
  key=norm(name)
  item={'name':name,'note':round(note),'attrs':c.get('attributs') or {},'surfaces':c.get('surfaces') or {},'country':c.get('pays') or ''}
  if key not in cards or len(item['attrs'])>len(cards[key]['attrs']):cards[key]=item
Path('arena/player_cards.json').write_text(json.dumps(cards,ensure_ascii=False),encoding='utf-8')
js=Path('arena/arena.js');s=js.read_text(encoding='utf-8')
marker='/* ARENA_REUSE_EXISTING_CARDS_V1 */'
if marker not in s:
 injection='''/* ARENA_REUSE_EXISTING_CARDS_V1 */
const teCardData={};
const teCardKey=s=>String(s||'').normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const teStatsCard=(name,unlocked)=>{
 const c=teCardData[teCardKey(name)];if(!c)return null;
 const attributes=Object.entries(c.attrs||{}).filter(([k,v])=>Number.isFinite(Number(v))).slice(0,6).map(([k,v])=>`<span><b>${Math.round(Number(v))}</b> ${safe(k.toUpperCase().slice(0,5))}</span>`).join('');
 const surfaces=Object.entries(c.surfaces||{}).filter(([k,v])=>Number.isFinite(Number(v))).map(([k,v])=>`<span>${safe(k)} <b>${Math.round(Number(v))}</b></span>`).join('');
 const initials=String(name).trim().split(/\\s+/).slice(0,2).map(x=>x[0]||'').join('').toUpperCase();
 return `<article class="te-stat-card"><div class="te-stat-head"><strong>${Math.round(c.note)}</strong><span>${safe(c.country)}</span></div><div class="te-stat-ball">${safe(initials)}</div><h3>${safe(name)}</h3><div class="te-stat-attrs">${attributes||'Statistiques non disponibles'}</div><div class="te-stat-surfaces">${surfaces}</div><small>${unlocked?'✓ Débloquée':'À gagner'}</small></article>`;
};
fetch('./player_cards.json?v=1').then(r=>r.ok?r.json():{}).then(d=>{Object.assign(teCardData,d);drawChallenges();if(token())refreshMyCollection();}).catch(()=>{});
'''
 needle='const rarityFor=name=>'
 if s.count(needle)!=1:raise SystemExit('Signature rarityFor introuvable')
 s=s.replace(needle,injection+needle,1)
 needle='const cardMarkup=(name,{unlocked=false,rarity}={})=>{'
 if s.count(needle)!=1:raise SystemExit('Signature cardMarkup introuvable')
 s=s.replace(needle,needle+'\n const existing=teStatsCard(name,unlocked);if(existing)return existing;',1)
 js.write_text(s,encoding='utf-8')
css=Path('arena/arena-ui.css');s=css.read_text(encoding='utf-8')
if 'ARENA_REUSE_EXISTING_CARDS_V1' not in s:
 s+='''\n/* ARENA_REUSE_EXISTING_CARDS_V1 */
.te-stat-card{border:2px solid #e6b74f;border-radius:16px;padding:15px;background:linear-gradient(150deg,#2a2456,#0e0b2b);color:#fff;box-shadow:0 0 15px #e6b74f44;display:grid;gap:10px;min-width:0}.te-stat-head{display:flex;justify-content:space-between}.te-stat-head strong{font-size:3rem;color:#ffdf66;line-height:1}.te-stat-ball{width:65px;height:65px;border-radius:50%;background:#c8ff39;color:#141414;font-size:1.4rem;font-weight:900;display:grid;place-items:center;margin:auto}.te-stat-card h3{text-align:center;text-transform:uppercase;margin:0}.te-stat-attrs{display:grid;grid-template-columns:1fr 1fr;gap:9px;border-block:1px solid #ffffff44;padding:12px 0}.te-stat-attrs b{color:#80f9bd}.te-stat-surfaces{display:flex;justify-content:space-between;gap:8px}.te-stat-card>small{text-align:center;color:#c2b9d8}\n'''
 css.write_text(s,encoding='utf-8')
print('Cartes exportées :',len(cards),'— Arena adaptée')
