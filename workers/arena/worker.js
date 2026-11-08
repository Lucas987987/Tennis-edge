/** Tennis Edge Arena V1: isolated Cloudflare Worker; does not import or change simulation engine.
 * Bindings: ARENA_DB (D1), ARENA_SESSION_SECRET, ARENA_ADMIN_TOKEN, ARENA_ORIGIN.
 * Identity: signed session tokens minted by an existing trusted authentication backend only.
 */
const json=(v,status=200,headers={})=>new Response(JSON.stringify(v),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store',...headers}});
const enc=new TextEncoder();
const b64url=(bytes)=>btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
const fromB64=(str)=>Uint8Array.from(atob(str.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-str.length%4)%4)),c=>c.charCodeAt(0));
async function hmac(secret,value){const key=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);return b64url(new Uint8Array(await crypto.subtle.sign('HMAC',key,enc.encode(value))));}
async function auth(request,env){const token=(request.headers.get('authorization')||'').replace(/^Bearer /i,'');const parts=token.split('.');if(parts.length!==2||!env.ARENA_SESSION_SECRET)return null;let payload;try{payload=JSON.parse(new TextDecoder().decode(fromB64(parts[0])));}catch{return null;}if(!payload.sub||typeof payload.sub!=='string'||payload.sub.length>128||!Number.isFinite(payload.exp)||payload.exp<=Date.now()/1000)return null;const expected=await hmac(env.ARENA_SESSION_SECRET,parts[0]);const a=enc.encode(expected),b=enc.encode(parts[1]);if(a.length!==b.length)return null;let diff=0;for(let i=0;i<a.length;i++)diff|=a[i]^b[i];return diff===0?payload.sub:null;}
function cors(req,env){const origin=req.headers.get('origin');return origin&&origin===env.ARENA_ORIGIN?{'access-control-allow-origin':origin,'vary':'Origin','access-control-allow-headers':'authorization,content-type','access-control-allow-methods':'GET,POST,OPTIONS'}:{};}
const fail=(message,status=400,h={})=>json({error:message},status,h);
async function body(req){if(Number(req.headers.get('content-length')||0)>4096)throw Error('Payload too large');const s=await req.text();if(s.length>4096)throw Error('Payload too large');return JSON.parse(s);}
const PUBLIC_TTLS={'/api/arena/challenges':45,'/api/arena/leaderboard':180,'/api/arena/rankings':180,'/api/arena/rewards':300};
async function publicCacheGet(request,path,headers){
 const ttl=PUBLIC_TTLS[path];if(!ttl||request.method!=='GET')return null;
 try{const cached=await caches.default.match(new Request(new URL(path,new URL(request.url).origin).toString()));
  if(!cached)return null;
  const h=new Headers(cached.headers);for(const [k,v] of Object.entries(headers))h.set(k,v);
  h.set('x-arena-cache','HIT');h.set('cache-control','no-store');
  return new Response(cached.body,{status:cached.status,headers:h});
 }catch{return null;}
}
async function publicCachePut(request,path,response,ctx){
 const ttl=PUBLIC_TTLS[path];if(!ttl||!response.ok||!ctx?.waitUntil)return;
 try{const key=new Request(new URL(path,new URL(request.url).origin).toString());
  const h=new Headers({'content-type':'application/json; charset=utf-8','cache-control':`public, max-age=${ttl}`});
  const stored=new Response(response.clone().body,{status:200,headers:h});
  ctx.waitUntil(caches.default.put(key,stored).catch(()=>{}));
 }catch{}
}
export default {async fetch(request,env,ctx){const headers=cors(request,env);if(request.method==='OPTIONS')return new Response(null,{status:204,headers});if(!env.ARENA_DB)return fail('ARENA_DB binding missing',503,headers);const url=new URL(request.url),path=url.pathname;const hit=await publicCacheGet(request,path,headers);if(hit)return hit;try{
if(request.method==='GET'&&path==='/api/arena/challenges'){const r=await env.ARENA_DB.prepare("SELECT id,title,player_a,player_b,starts_at,closes_at,status FROM arena_challenges WHERE status='open' AND closes_at>datetime('now') ORDER BY starts_at LIMIT 50").all();const response=json({challenges:r.results},200,headers);await publicCachePut(request,path,response,ctx);return response;}
if(request.method==='GET'&&path==='/api/arena/leaderboard'){const r=await env.ARENA_DB.prepare('SELECT display_name,xp FROM arena_users ORDER BY xp DESC,id LIMIT 100').all();const response=json({leaders:r.results},200,headers);await publicCachePut(request,path,response,ctx);return response;}

if(request.method==='GET'&&path==='/api/arena/rankings'){
 const weekly=await env.ARENA_DB.prepare("SELECT u.display_name,SUM(e.xp_delta) xp FROM arena_point_events e JOIN arena_users u ON u.id=e.user_id WHERE e.created_at>=datetime('now','-7 days') GROUP BY e.user_id ORDER BY xp DESC LIMIT 20").all();
 const monthly=await env.ARENA_DB.prepare("SELECT u.display_name,SUM(e.xp_delta) xp FROM arena_point_events e JOIN arena_users u ON u.id=e.user_id WHERE e.created_at>=datetime('now','start of month') GROUP BY e.user_id ORDER BY xp DESC LIMIT 20").all();
 const response=json({weekly:weekly.results,monthly:monthly.results},200,headers);await publicCachePut(request,path,response,ctx);return response;
}
if(request.method==='GET'&&path==='/api/arena/rewards'){const r=await env.ARENA_DB.prepare('SELECT id,title,cost,stock FROM arena_rewards WHERE enabled=1 ORDER BY cost').all();const response=json({rewards:r.results},200,headers);await publicCachePut(request,path,response,ctx);return response;}

if(request.method==='POST'&&path==='/api/arena/test-login'){
 if(!env.ARENA_TEST_ACCESS_KEY||env.ARENA_TEST_ACCESS_KEY.length<32)return fail('Private test disabled',403,headers);
 const data=await body(request),supplied=String(data.access_key||'');
 const a=enc.encode(supplied),b=enc.encode(env.ARENA_TEST_ACCESS_KEY);let diff=a.length^b.length;
 for(let i=0;i<Math.max(a.length,b.length)&&i<4096;i++)diff|=(a[i]||0)^(b[i]||0);
 if(diff!==0)return fail('Invalid test key',403,headers);
 const sub='arena-private-tester';
 await env.ARENA_DB.prepare('INSERT OR IGNORE INTO arena_users(id,display_name) VALUES(?,?)').bind(sub,'Testeur Arena').run();
 const payload=b64url(enc.encode(JSON.stringify({sub,exp:Math.floor(Date.now()/1000)+3600})));
 return json({token:payload+'.'+await hmac(env.ARENA_SESSION_SECRET,payload)},200,headers);
}

if(request.method==='POST'&&path==='/api/arena/admin/challenge'){
 const supplied=request.headers.get('x-arena-admin-token')||'';
 if(!env.ARENA_ADMIN_TOKEN||supplied!==env.ARENA_ADMIN_TOKEN)return fail('Forbidden',403,headers);
 const d=await body(request);
 const title=String(d.title||'').trim(),a=String(d.player_a||'').trim(),b=String(d.player_b||'').trim();
 const circuit=String(d.circuit||'').trim().toUpperCase();
 if(!['ATP','WTA','CHALLENGER'].includes(circuit)||title.length<5||title.length>100||a.length<2||a.length>80||b.length<2||b.length>80||a===b)return fail('Invalid challenge',400,headers);
 const start=String(d.starts_at||'');
 if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(start))return fail('Use UTC ISO timestamp',400,headers);
 const ts=Date.parse(start);
 if(!Number.isFinite(ts)||ts<Date.now()+10*60000||ts>Date.now()+30*86400000)return fail('Start must be 10 min to 30 days in future',400,headers);
 const id='real-'+crypto.randomUUID();
 const close=new Date(ts-5*60000).toISOString().slice(0,19).replace('T',' ');
 const startSql=new Date(ts).toISOString().slice(0,19).replace('T',' ');
 await env.ARENA_DB.prepare("INSERT INTO arena_challenges(id,title,player_a,player_b,starts_at,closes_at,status) VALUES(?,?,?,?,?,?,'open')").bind(id,circuit+' · '+title,a,b,startSql,close).run();
 return json({ok:true,id,closes_at:close},201,headers);
}
const user=await auth(request,env);if(!user)return fail('Authentication required',401,headers);
if(request.method==='GET'&&path==='/api/arena/me'){const r=await env.ARENA_DB.prepare('SELECT id,display_name,xp,points FROM arena_users WHERE id=?').bind(user).first();return json({profile:r},200,headers);}
if(request.method==='POST'&&path==='/api/arena/join'){const data=await body(request);const name=String(data.display_name||'').trim();if(name.length<2||name.length>32||!/^[-\p{L}\p{N} ._]+$/u.test(name))return fail('Invalid name',400,headers);await env.ARENA_DB.prepare('INSERT OR IGNORE INTO arena_users(id,display_name) VALUES(?,?)').bind(user,name).run();return json({ok:true},200,headers);}
if(request.method==='POST'&&path==='/api/arena/predict'){const data=await body(request);if(!['a','b'].includes(data.pick)||typeof data.challenge_id!=='string'||data.challenge_id.length>128)return fail('Invalid prediction',400,headers);const challenge=await env.ARENA_DB.prepare("SELECT id FROM arena_challenges WHERE id=? AND status='open' AND closes_at>datetime('now') AND starts_at>datetime('now')").bind(data.challenge_id).first();if(!challenge)return fail('Challenge closed',409,headers);const r=await env.ARENA_DB.prepare('INSERT OR IGNORE INTO arena_predictions(user_id,challenge_id,pick) SELECT ?,?,? WHERE EXISTS(SELECT 1 FROM arena_users WHERE id=?)').bind(user,data.challenge_id,data.pick,user).run();if(r.meta.changes!==1)return fail('Already predicted or not enrolled',409,headers);return json({ok:true},201,headers);}
if(request.method==='POST'&&path==='/api/arena/redeem'){const data=await body(request);if(typeof data.reward_id!=='string'||data.reward_id.length>128)return fail('Invalid reward',400,headers);const reward=await env.ARENA_DB.prepare('SELECT id,cost,stock FROM arena_rewards WHERE id=? AND enabled=1').bind(data.reward_id).first();if(!reward||reward.stock<1)return fail('Unavailable',409,headers);
const id=crypto.randomUUID();try{await env.ARENA_DB.prepare('INSERT INTO arena_redemptions(id,user_id,reward_id,cost) VALUES(?,?,?,?)').bind(id,user,data.reward_id,reward.cost).run();}catch{return fail('Insufficient points or unavailable',409,headers);}
return json({ok:true,redemption_id:id},201,headers);
}
if(request.method==='GET'&&path==='/api/arena/me/cards'){
 const r=await env.ARENA_DB.prepare('SELECT card_id,player_name,earned_at FROM arena_cards WHERE user_id=? ORDER BY earned_at DESC').bind(user).all();
 return json({cards:r.results},200,headers);
}
if(request.method==='POST'&&path==='/api/arena/test/settle'){
 if(user!=='arena-private-tester'||!env.ARENA_TEST_ACCESS_KEY)return fail('Forbidden',403,headers);
 const data=await body(request);
 if(!['arena-demo-1','arena-demo-2','arena-demo-3'].includes(data.challenge_id)||!['a','b'].includes(data.winner))return fail('Invalid demo result',400,headers);
 const existing=await env.ARENA_DB.prepare('SELECT status FROM arena_challenges WHERE id=?').bind(data.challenge_id).first();
 if(!existing||existing.status!=='open')return fail('Demo already settled',409,headers);
 // Close a fictional challenge before settlement. The D1 settlement trigger awards XP and points atomically.
 await env.ARENA_DB.prepare("UPDATE arena_challenges SET closes_at=datetime('now','-1 minute') WHERE id=? AND status='open'").bind(data.challenge_id).run();
 try{await env.ARENA_DB.prepare('INSERT INTO arena_settlements(challenge_id,winner) VALUES(?,?)').bind(data.challenge_id,data.winner).run();}
 catch{return fail('Demo settlement failed or already completed',409,headers);}
 const result=await env.ARENA_DB.prepare('SELECT id,status,winner FROM arena_challenges WHERE id=?').bind(data.challenge_id).first();
 return json({ok:true,challenge:result},200,headers);
}
if(request.method==='POST'&&path==='/api/arena/admin/settle'){if(!env.ARENA_ADMIN_TOKEN||request.headers.get('x-arena-admin-token')!==env.ARENA_ADMIN_TOKEN)return fail('Forbidden',403,headers);const data=await body(request);if(typeof data.challenge_id!=='string'||!['a','b'].includes(data.winner))return fail('Invalid result',400,headers);const challenge=await env.ARENA_DB.prepare("SELECT id FROM arena_challenges WHERE id=? AND closes_at<=datetime('now')").bind(data.challenge_id).first();if(!challenge)return fail('Not ready',409,headers);try{await env.ARENA_DB.prepare('INSERT INTO arena_settlements(challenge_id,winner) VALUES(?,?)').bind(data.challenge_id,data.winner).run();}catch{return fail('Already settled',409,headers);}return json({ok:true},200,headers);}
return fail('Not found',404,headers);
}catch(e){return fail(e instanceof SyntaxError?'Invalid JSON':'Request failed',e instanceof SyntaxError?400:500,headers);}}};
