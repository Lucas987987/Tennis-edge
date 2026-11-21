#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mouvements_mixamo.py — ajoute des mouvements captés Mixamo au fichier des joueurs 3D (21/11/2026, paquet 326).

Demande de Lucas : « utiliser des mouvements de Mixamo pour améliorer les déplacements et les mouvements de nos vidéos ».
Mixamo n'a aucun coup de tennis : on y prend l'attente, les pas chassés, la course arrière, les gestes après le point
(poing serré, victoire, joie, saut, déception, « non » de la tête, abattu, applaudissements) et l'arbitre assis.

LICENCE : les animations Mixamo (Adobe) sont libres d'usage dans un projet, mais leurs fichiers d'origine ne doivent pas
être redistribués. Les .fbx ne sont donc JAMAIS mis dans le dépôt : ce script les lit sur la machine de celui qui les a
téléchargés et n'écrit que le mouvement converti, intégré au fichier des modèles du site (algo/modeles/joueurs3d.bin).

Conversion : lecteur FBX binaire maison (pas de dépendance) ; pour chacun des 23 os du modèle (Quaternius), la rotation
monde par rapport à la pose de repos, comme les boucles de la Universal Animation Library (paquet 265), après avoir
aligné les deux poses de repos os par os (direction de chaque os). Strafe_Right de Mixamo n'étant qu'un pas isolé, le
pas chassé vers la droite est le pas chassé vers la gauche vu dans un miroir. Vitesse au sol des boucles : celle du
bassin dans le fichier d'origine.

Usage : python scripts/mouvements_mixamo.py <dossier des .fbx> algo/modeles/joueurs3d.bin algo/modeles/joueurs3d.bin
"""
import json, os, struct, sys, zlib
import numpy as np
"""Lecteur minimal de FBX binaire (Mixamo) : nœuds, propriétés, tableaux compressés."""

class Noeud:
    __slots__ = ('nom', 'props', 'enfants')
    def __init__(s, nom, props, enfants): s.nom, s.props, s.enfants = nom, props, enfants
    def un(s, nom):
        for e in s.enfants:
            if e.nom == nom: return e
        return None
    def tous(s, nom): return [e for e in s.enfants if e.nom == nom]

ARR = {'f': ('<f', 4), 'd': ('<d', 8), 'l': ('<q', 8), 'i': ('<i', 4), 'b': ('<b', 1)}

def lire(chemin):
    b = open(chemin, 'rb').read()
    assert b[:18] == b'Kaydara FBX Binary'
    ver = struct.unpack('<I', b[23:27])[0]
    grand = ver >= 7500
    def prop(o):
        t = chr(b[o]); o += 1
        if t == 'Y': return struct.unpack_from('<h', b, o)[0], o + 2
        if t == 'C': return bool(b[o]), o + 1
        if t == 'I': return struct.unpack_from('<i', b, o)[0], o + 4
        if t == 'F': return struct.unpack_from('<f', b, o)[0], o + 4
        if t == 'D': return struct.unpack_from('<d', b, o)[0], o + 8
        if t == 'L': return struct.unpack_from('<q', b, o)[0], o + 8
        if t in ARR:
            n, enc, ln = struct.unpack_from('<III', b, o); o += 12
            raw = b[o:o + ln]; o += ln
            if enc == 1: raw = zlib.decompress(raw)
            return np.frombuffer(raw, dtype=ARR[t][0], count=n), o
        if t in 'SR':
            n = struct.unpack_from('<I', b, o)[0]; o += 4
            v = b[o:o + n]; o += n
            return (v.decode('utf-8', 'replace') if t == 'S' else v), o
        raise ValueError(t)
    def noeud(o):
        if grand: fin, np_, pl = struct.unpack_from('<QQQ', b, o); o += 24
        else: fin, np_, pl = struct.unpack_from('<III', b, o); o += 12
        if fin == 0: return None, o
        ln = b[o]; o += 1
        nom = b[o:o + ln].decode(); o += ln
        props = []
        for _ in range(np_):
            v, o = prop(o); props.append(v)
        enfants = []
        while o < fin:
            e, o = noeud(o)
            if e is None: break
            enfants.append(e)
        return Noeud(nom, props, enfants), fin
    o, racine = 27, []
    while o < len(b) - 200:
        e, o2 = noeud(o)
        if e is None: break
        racine.append(e); o = o2
    return Noeud('racine', [], racine), ver

"""Mouvements Mixamo (FBX) → rotations monde par rapport au repos, comme les boucles de la Universal Animation Library."""

TICK = 46186158000.0

def euler_xyz(d):                      # FBX eEulerXYZ : R = Rz · Ry · Rx (degrés)
    x, y, z = np.radians(d)
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]); Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx

def p70(n):
    out = {}
    pp = n.un('Properties70')
    if pp:
        for p in pp.tous('P'): out[p.props[0]] = p.props[4:]
    return out

class Squelette:
    def __init__(s, chemin):
        r, _ = lire(chemin)
        obj, con = r.un('Objects'), r.un('Connections')
        s.mod, s.cn, s.cv = {}, {}, {}
        for e in obj.enfants:
            if e.nom == 'Model': s.mod[e.props[0]] = {'nom': e.props[1].split('\x00')[0], 'p': p70(e), 'parent': None}
            elif e.nom == 'AnimationCurveNode': s.cn[e.props[0]] = {'nom': e.props[1].split('\x00')[0], 'p': p70(e), 'courbes': {}, 'cible': None}
            elif e.nom == 'AnimationCurve':
                s.cv[e.props[0]] = (e.un('KeyTime').props[0].astype(np.float64) / TICK, e.un('KeyValueFloat').props[0].astype(np.float64))
        for c in con.tous('C'):
            t, a, b = c.props[0], c.props[1], c.props[2]
            if t == 'OO' and a in s.mod and b in s.mod: s.mod[a]['parent'] = b
            elif t == 'OP' and a in s.cv and b in s.cn: s.cn[b]['courbes'][c.props[3]] = a
            elif t == 'OP' and a in s.cn and b in s.mod: s.cn[a]['cible'] = (b, c.props[3])
        s.par_nom = {m['nom']: k for k, m in s.mod.items()}
        s.anim = {}
        for k, n in s.cn.items():
            if n['cible']: s.anim[(n['cible'][0], n['cible'][1])] = n
        s.duree = max((v[0][-1] for v in s.cv.values()), default=0.0)

    def local(s, k, t):
        m = s.mod[k]; p = m['p']
        def val(prop, defaut):
            n = s.anim.get((k, prop))
            if not n: return np.array(p.get(prop, defaut), float)
            out = []
            for ax, d in zip('XYZ', p.get(prop, defaut)):
                c = n['courbes'].get('d|' + ax)
                if c is None: out.append(float(n['p'].get('d|' + ax, [d])[0])); continue
                ts, vs = s.cv[c]; out.append(float(np.interp(t, ts, vs)))
            return np.array(out)
        T = val('Lcl Translation', [0, 0, 0]); R = val('Lcl Rotation', [0, 0, 0])
        pre = euler_xyz(p.get('PreRotation', [0, 0, 0])); post = euler_xyz(p.get('PostRotation', [0, 0, 0]))
        return T, pre @ euler_xyz(R) @ post.T

    def monde(s, t, noms):
        cache = {}
        def W(k):
            if k in cache: return cache[k]
            T, R = s.local(k, t)
            pa = s.mod[k]['parent']
            if pa is None or pa not in s.mod: out = (T, R)
            else:
                Tp, Rp = W(pa); out = (Tp + Rp @ T, Rp @ R)
            cache[k] = out; return out
        return {n: W(s.par_nom[n]) for n in noms}

"""Transfert Mixamo → squelette Quaternius (23 os) : rotation monde par rapport au repos, avec alignement des repos."""

CORR = {'pelvis': 'Hips', 'spine_01': 'Spine', 'spine_02': 'Spine1', 'spine_03': 'Spine2', 'neck_01': 'Neck', 'Head': 'Head',
        'clavicle_l': 'LeftShoulder', 'upperarm_l': 'LeftArm', 'lowerarm_l': 'LeftForeArm', 'hand_l': 'LeftHand',
        'clavicle_r': 'RightShoulder', 'upperarm_r': 'RightArm', 'lowerarm_r': 'RightForeArm', 'hand_r': 'RightHand',
        'thigh_l': 'LeftUpLeg', 'calf_l': 'LeftLeg', 'foot_l': 'LeftFoot', 'ball_l': 'LeftToeBase',
        'thigh_r': 'RightUpLeg', 'calf_r': 'RightLeg', 'foot_r': 'RightFoot', 'ball_r': 'RightToeBase'}
ENFANT = {'pelvis': 'spine_01', 'spine_01': 'spine_02', 'spine_02': 'spine_03', 'spine_03': 'neck_01', 'neck_01': 'Head',
          'clavicle_l': 'upperarm_l', 'upperarm_l': 'lowerarm_l', 'lowerarm_l': 'hand_l',
          'clavicle_r': 'upperarm_r', 'upperarm_r': 'lowerarm_r', 'lowerarm_r': 'hand_r',
          'thigh_l': 'calf_l', 'calf_l': 'foot_l', 'foot_l': 'ball_l', 'thigh_r': 'calf_r', 'calf_r': 'foot_r', 'foot_r': 'ball_r'}

def q2R(q):
    x, y, z, w = q
    return np.array([[1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)], [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
                     [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]])
def R2q(R):
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1) * 2; q = [(R[2,1] - R[1,2]) / s, (R[0,2] - R[2,0]) / s, (R[1,0] - R[0,1]) / s, 0.25 * s]
    elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
        s = np.sqrt(1 + R[0,0] - R[1,1] - R[2,2]) * 2; q = [0.25 * s, (R[0,1] + R[1,0]) / s, (R[0,2] + R[2,0]) / s, (R[2,1] - R[1,2]) / s]
    elif R[1,1] > R[2,2]:
        s = np.sqrt(1 + R[1,1] - R[0,0] - R[2,2]) * 2; q = [(R[0,1] + R[1,0]) / s, 0.25 * s, (R[1,2] + R[2,1]) / s, (R[0,2] - R[2,0]) / s]
    else:
        s = np.sqrt(1 + R[2,2] - R[0,0] - R[1,1]) * 2; q = [(R[0,2] + R[2,0]) / s, (R[1,2] + R[2,1]) / s, 0.25 * s, (R[1,0] - R[0,1]) / s]
    q = np.array(q); return q / np.linalg.norm(q)
def entre(a, b):                         # rotation qui amène la direction a sur b
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b); v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.9999: return -np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)
def ortho(M):
    U, _, Vt = np.linalg.svd(M); return U @ Vt

def cible_repos(binp):
    b = open(binp, 'rb').read(); n = struct.unpack('<I', b[4:8])[0]; J = json.loads(b[8:8 + n]); O = J['os']
    W, P = [], []
    for k, nom in enumerate(O['noms']):
        R, t, p = q2R(O['q'][k]), np.array(O['t'][k]), O['parents'][k]
        if p < 0: W.append(R); P.append(t)
        else: W.append(W[p] @ R); P.append(P[p] + W[p] @ t)
    return O, W, P, J['clips_bassin']

def source_repos(chemin):
    r, _ = lire(chemin); obj = r.un('Objects')
    noms = {e.props[0]: e.props[1].split('\x00')[0] for e in obj.tous('Model')}
    W, P = {}, {}
    for pose in obj.tous('Pose'):
        for pn in pose.tous('PoseNode'):
            nm = noms.get(pn.un('Node').props[0])
            if not nm or nm in W: continue
            M = np.array(pn.un('Matrix').props[0], float).reshape(4, 4).T
            W[nm] = ortho(M[:3, :3]); P[nm] = M[:3, 3]
    return W, P

def convertir(chemin, binp, fps=30, garde_bras=True):
    O, Wt0, Pt0, bassin_cible = cible_repos(binp)
    Ws0, Ps0 = source_repos(chemin)
    S = Squelette(chemin)
    noms = O['noms']; mx = lambda n: 'mixamorig:' + CORR[n]
    A = {}
    for k, n in enumerate(noms):
        if n not in CORR: continue
        e = ENFANT.get(n)
        if n == 'pelvis': A[n] = np.eye(3)                          # le bassin garde son repos (os court : direction peu sûre)
        elif e:
            dt = Pt0[noms.index(e)] - Pt0[k]; ds = Ps0[mx(e)] - Ps0[mx(n)]
            A[n] = entre(dt, ds)
        else:
            A[n] = A.get(noms[O['parents'][k]], np.eye(3))
    h0 = Ps0['mixamorig:Hips'][1]                                   # hauteur du bassin au repos (cm)
    nf = max(2, int(round(S.duree * fps)) + 1)
    Q = np.zeros((nf, len(noms), 4)); T = np.zeros((nf, 3)); Q[:, :, 3] = 1
    for f in range(nf):
        Wm = S.monde(f / fps, [mx(n) for n in noms if n in CORR])
        for k, n in enumerate(noms):
            if n not in CORR: continue
            Ds = Wm[mx(n)][1] @ Ws0[mx(n)].T
            Q[f, k] = R2q(Ds @ A[n])
        T[f] = (Wm['mixamorig:Hips'][0] - Ps0['mixamorig:Hips']) / h0 * bassin_cible   # à l'échelle du bassin des boucles UAL
    return {'dur': (nf - 1) / fps, 'fps': fps, 'Q': Q, 'T': T, 'A': A, 'O': O, 'Wt0': Wt0, 'Pt0': Pt0}

def pose_monde(c, f):
    """positions monde des os de la cible à l'image f (contrôle)."""
    O, Wt0, Pt0 = c['O'], c['Wt0'], c['Pt0']; W, P = [], []
    for k, n in enumerate(O['noms']):
        R = q2R(c['Q'][f, k]) @ Wt0[k]; p = O['parents'][k]
        if p < 0: W.append(R); P.append(Pt0[k].copy())
        else:
            t = Wt0[p].T @ (Pt0[k] - Pt0[p])            # translation locale de repos
            W.append(R); P.append(P[p] + W[p] @ t)
            if n == 'pelvis': P[-1] = P[-1] + np.array([0, c['T'][f][1] * Pt0[k][1] / 0.9167, 0])
    return np.array(P)

"""Ajoute les mouvements Mixamo (convertis) au fichier des modèles : algo/modeles/joueurs3d.bin."""

FICHIERS = {'MX_Idle': 'Standing_Idle', 'MX_StrafeG': 'Left_Strafe', 'MX_Recul': 'Running_Backward',
            'MX_Saut': 'Jump', 'MX_Poing': 'Standing_Fist_Pump', 'MX_Victoire': 'Victory', 'MX_Joie': 'Cheering',
            'MX_Decu': 'Disappointed', 'MX_Non': 'Shaking_Head_No', 'MX_Abattu': 'Defeated', 'MX_Applaudit': 'Clapping',
            'MX_Assis': 'Sitting_Idle'}
BOUCLES = {'MX_Idle', 'MX_StrafeG', 'MX_StrafeD', 'MX_Recul', 'MX_Applaudit', 'MX_Assis'}

def vitesse_sol(c):
    """vitesse au sol d'une boucle « sur place » : celle du pied d'appui (le plus bas), en m/s (médiane)."""
    N = c['O']['noms']; fl, fr = N.index('foot_l'), N.index('foot_r')
    P = np.array([pose_monde(c, f) for f in range(len(c['Q']))])
    appui = np.where(P[:, fl, 1] < P[:, fr, 1], fl, fr)
    v = []
    for f in range(1, len(P)):
        k = appui[f]
        if appui[f - 1] != k: continue
        d = P[f, k, [0, 2]] - P[f - 1, k, [0, 2]]
        v.append(np.hypot(*d) * c['fps'])
    return float(np.median(v)) if v else 0.0

def vitesse_racine(chemin):
    S = Squelette(chemin); a, b = S.monde(0, ['mixamorig:Hips'])['mixamorig:Hips'][0], S.monde(S.duree, ['mixamorig:Hips'])['mixamorig:Hips'][0]
    return float(np.hypot(b[0] - a[0], b[2] - a[2]) / 100 / S.duree)

def miroir(c):
    """le même mouvement vu dans un miroir (gauche ↔ droite) : Strafe_Right de Mixamo n'est qu'un pas isolé, pas une boucle."""
    N = c['O']['noms']; Q = np.zeros_like(c['Q'])
    for k, n in enumerate(N):
        m = n[:-2] + ('_r' if n.endswith('_l') else '_l') if n.endswith(('_l', '_r')) else n
        q = c['Q'][:, N.index(m)]; Q[:, k] = np.stack([q[:, 0], -q[:, 1], -q[:, 2], q[:, 3]], 1)
    T = c['T'].copy(); T[:, 0] *= -1
    return dict(c, Q=Q, T=T)

def principal(src, binp, sortie):
    b = open(binp, 'rb').read(); n = struct.unpack('<I', b[4:8])[0]; J = json.loads(b[8:8 + n]); blob = bytearray(b[8 + n:])
    anciens = [v for k, v in J['clips'].items() if k.startswith('MX_')]
    if anciens:                                   # relance : les mouvements Mixamo sont à la fin du fichier, on les remplace
        del blob[min(min(v['q'], v['t']) for v in anciens):]
    J['clips'] = {k: v for k, v in J['clips'].items() if not k.startswith('MX_')}
    def morceau(arr):
        while len(blob) % 4: blob.append(0)
        o = len(blob); blob.extend(np.ascontiguousarray(arr).tobytes()); return o
    faits = []
    for nom, f in FICHIERS.items():
        c = convertir(os.path.join(src, f + '.fbx'), binp)
        vit = vitesse_racine(os.path.join(src, f + '.fbx')) if nom in ('MX_StrafeG', 'MX_Recul') else 0.0
        faits.append((nom, f, c, vit))
        if nom == 'MX_StrafeG': faits.append(('MX_StrafeD', f + ' (miroir)', miroir(c), vit))
    for nom, f, c, vit in faits:
        q = np.clip(np.round(c['Q'] * 32767), -32767, 32767).astype(np.int16)
        J['clips'][nom] = {'dur': round(c['dur'], 4), 'fps': c['fps'], 'nf': int(c['Q'].shape[0]), 'vitesse': round(vit, 3),
                           'boucle': nom in BOUCLES, 'q': morceau(q), 't': morceau(c['T'].astype(np.float32))}
        print(nom, f, round(c['dur'], 2), 's', int(c['Q'].shape[0]), 'images', 'vitesse', round(vit, 2))
    if 'Mixamo' not in J['licence']: J['licence'] += ' ; gestes, attente et déplacements latéraux : Mixamo (Adobe), intégrés au projet (fichiers d\'origine non distribués)'
    js = json.dumps(J, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4)
    open(sortie, 'wb').write(b'TEJ3' + struct.pack('<I', len(js)) + js + bytes(blob))
    print(sortie, round(os.path.getsize(sortie) / 1e6, 2), 'Mo')

if __name__ == '__main__':
    principal(sys.argv[1], sys.argv[2], sys.argv[3])
