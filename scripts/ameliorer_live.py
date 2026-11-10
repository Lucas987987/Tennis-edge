from pathlib import Path
p=Path('algo/index.html')
s=p.read_text()
old="const n=Math.floor(rand(3,8)), shots=[];"
if old not in s:
    if "const n=Math.floor(rand(7,14)), shots=[];" in s:
        print("Animation déjà mise à jour : aucune modification nécessaire")
        raise SystemExit(0)
    raise RuntimeError("Version inattendue de l’animation : arrêt sans modification")
s=s.replace(old,"const n=Math.floor(rand(7,14)), shots=[];",1)
s=s.replace("const lead=.75, end=.65, duration=lead+legs.reduce((a,b)=>a+b,0)+end;","const lead=2.2, end=1.25, duration=lead+legs.reduce((a,b)=>a+b,0)+end;",1)
s=s.replace("return clamp(d/235*rand(.85,1.35),.70,1.7);","return clamp(d/235*rand(1.65,2.35),1.45,3.15);",1)
s=s.replace("shots.push({player:server,x:server===0?34:326,y:side?132:68,type:'service'});","shots.push({player:server,x:server===0?15:345,y:side?132:68,type:'service'});",1)
s=s.replace("const travel=clamp(distance/105,.20,.90);","const travel=clamp(distance/72,.32,1.45);",1)
s=s.replace("const recover=base(i), recoverTime=Math.min(hit+.48,st.duration-.05);","const recover=base(i), recoverTime=Math.min(hit+.85,st.duration-.05);",1)
s=s.replace("const u=clamp(t/st.lead,0,1);\n      height=24*Math.sin(Math.PI*u);p={x:shots[0].x,y:shots[0].y-height};","const u=clamp(t/st.lead,0,1);\n      height=22*Math.sin(Math.PI*Math.max(0,(u-.40)/.60));p={x:shots[0].x,y:shots[0].y-height};",1)
s=s.replace("const eased=u<.5?2*u*u:1-2*(1-u)*(1-u);","const eased=u;",1)
s=s.replace("if(!document.hidden&&now-last>=33){","if(!document.hidden&&now-last>=16){",1)
s=s.replace("const home=base(i),shots=st.shots;","const home=base(i),shots=st.shots;",1)
# No generated new score: preserve all live-score logic.
p.write_text(s)
print('Patched:',p)
