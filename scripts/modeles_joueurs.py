#!/usr/bin/env python3
"""modeles_joueurs.py — prépare les joueurs 3D du direct (13/11/2026, paquet 264, demande de Lucas).

Source : « Universal Base Characters » de Quaternius (licence CC0 1.0 : domaine public, usage commercial libre,
aucune attribution exigée), dossier « Base Characters/Godot - UE » (glTF) et « Hairstyles/Rigged to Head Bone ».
Le fichier produit (algo/modeles/joueurs3d.bin, ~2 Mo) est servi par le site lui-même : rien n'est chargé ailleurs.

Ce que fait le script, une fois pour toutes (la page n'a plus qu'à lire le résultat) :
  1. lit les deux corps (homme, femme), leurs yeux, quatre coiffures et deux sourcils ;
  2. replie les doigts (poings fermés sur le manche) puis rattache les doigts à la main : 23 os au lieu de 65 ;
  3. HABILLE les joueurs : chaque sommet reçoit une classe (peau, maillot, côtés du maillot, short, liseré,
     blanc — chaussettes, chaussures, poignets —, semelle, bandeau) et le tissu est légèrement décollé de la peau
     (short ample, évasé en bas) ; les couleurs sont choisies dans la page, joueur par joueur ;
  4. réduit les textures (peau 1024 px, cheveux 512 px, JPEG) et écrit un seul fichier binaire.

Usage : python3 scripts/modeles_joueurs.py "<dossier Universal Base Characters[Standard]>" algo/modeles/joueurs3d.bin
"""
import io
import json
import math
import os
import struct
import sys

import numpy as np
from PIL import Image

GARDES = ['root', 'pelvis', 'spine_01', 'spine_02', 'spine_03', 'neck_01', 'Head', 'clavicle_l', 'upperarm_l',
          'lowerarm_l', 'hand_l', 'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r', 'thigh_l', 'calf_l', 'foot_l',
          'ball_l', 'thigh_r', 'calf_r', 'foot_r', 'ball_r']
# classes de sommets (la page leur donne une couleur)
PEAU, MAILLOT, COTE, SHORT, LISERE, BLANC, SEMELLE, BANDEAU = range(8)
TYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NB = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


class Gltf:
    def __init__(self, chemin):
        self.dossier = os.path.dirname(chemin)
        self.g = json.load(open(chemin, encoding='utf-8'))
        self.bin = open(os.path.join(self.dossier, self.g['buffers'][0]['uri']), 'rb').read()

    def acc(self, i):
        a = self.g['accessors'][i]
        bv = self.g['bufferViews'][a['bufferView']]
        t, n = TYPES[a['componentType']], NB[a['type']]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        pas = bv.get('byteStride') or np.dtype(t).itemsize * n
        brut = np.frombuffer(self.bin, dtype=np.uint8, count=pas * (a['count'] - 1) + np.dtype(t).itemsize * n, offset=off)
        out = np.lib.stride_tricks.as_strided(brut, shape=(a['count'], np.dtype(t).itemsize * n), strides=(pas, 1)).copy()
        v = out.view(t).reshape(a['count'], n)
        if a.get('normalized'):
            v = v.astype(np.float32) / np.iinfo(t).max
        return v

    def noeud(self, nom):
        return next(i for i, n in enumerate(self.g['nodes']) if n.get('name') == nom)

    def mesh(self, nom_noeud):
        n = self.g['nodes'][self.noeud(nom_noeud)]
        p = self.g['meshes'][n['mesh']]['primitives'][0]
        A = p['attributes']
        return {'pos': self.acc(A['POSITION']).astype(np.float64), 'nor': self.acc(A['NORMAL']).astype(np.float64),
                'uv': self.acc(A['TEXCOORD_0']).astype(np.float64), 'j': self.acc(A['JOINTS_0']).astype(np.int32),
                'w': self.acc(A['WEIGHTS_0']).astype(np.float64), 'idx': self.acc(p['indices']).reshape(-1),
                'noms_os': [self.g['nodes'][k]['name'] for k in self.g['skins'][n['skin']]['joints']]}


def matrice(n):
    if 'matrix' in n:
        return np.array(n['matrix'], dtype=np.float64).reshape(4, 4).T
    t, r, s = n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1]), n.get('scale', [1, 1, 1])
    x, y, z, w = r
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * np.array(s); M[:3, 3] = t
    return M


def squelette(gl):
    """Os gardés : parent, translation et rotation locales de repos, matrice monde de repos."""
    N = gl.g['nodes']
    parent = {}
    for i, n in enumerate(N):
        for c in n.get('children', []):
            parent[c] = i
    monde = {}

    def W(i):
        if i not in monde:
            monde[i] = (W(parent[i]) if i in parent else np.eye(4)) @ matrice(N[i])
        return monde[i]
    idx = [gl.noeud(n) for n in GARDES]
    out = []
    for k, i in enumerate(idx):
        p = parent.get(i)
        while p is not None and N[p]['name'] not in GARDES:          # remonte jusqu'à un os gardé
            p = parent.get(p)
        pk = GARDES.index(N[p]['name']) if p is not None and N[p]['name'] in GARDES else -1
        loc = np.linalg.inv(W(p)) @ W(i) if pk >= 0 else W(i)
        out.append({'nom': GARDES[k], 'parent': pk, 'loc': loc, 'monde': W(i)})
    return out, W, idx


def quat(R):
    m = R[:3, :3]
    t = m.trace()
    if t > 0:
        s = math.sqrt(t + 1) * 2; return [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]]))
    if i == 0:
        s = math.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2; return [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
    if i == 1:
        s = math.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2; return [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
    s = math.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2; return [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s]


def rot_axe(axe, a):
    axe = np.asarray(axe, dtype=np.float64); axe = axe / np.linalg.norm(axe)
    x, y, z = axe; c, s = math.cos(a), math.sin(a)
    R = np.eye(4)
    R[:3, :3] = [[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                 [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                 [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]]
    return R


def poings(gl, M, W):
    """Replie les doigts (poing fermé) : déplace les sommets attachés aux phalanges, comme le ferait l'animation."""
    N = gl.g['nodes']
    noms = M['noms_os']
    nouveau = {}
    for cote, s in (('l', 1), ('r', -1)):
        for doigt, angle in (('index', 1.25), ('middle', 1.3), ('ring', 1.3), ('pinky', 1.3), ('thumb', 0.55)):
            chaine = [f'{doigt}_0{k}_{cote}' for k in (1, 2, 3)]
            acc = np.eye(4)
            for nom in chaine:
                i = gl.noeud(nom)
                piv = W(i)[:3, 3]
                axe = [0, 0, 1] if doigt != 'thumb' else [1 * s, 0, 0.6]
                R = rot_axe(axe, -s * angle if doigt != 'thumb' else s * angle * 0.6)      # vers la paume (paumes vers le bas au repos)
                T = np.eye(4); T[:3, 3] = piv; Ti = np.eye(4); Ti[:3, 3] = -piv
                acc = acc @ (T @ R @ Ti)
                nouveau[nom] = acc.copy()
    pos = M['pos'].copy(); nor = M['nor'].copy()
    for v in range(len(pos)):
        P = np.zeros(3); Nn = np.zeros(3); tot = 0
        for k in range(4):
            w = M['w'][v, k]
            if w <= 0:
                continue
            m = nouveau.get(noms[M['j'][v, k]])
            if m is None:
                P += w * pos[v]; Nn += w * nor[v]
            else:
                P += w * (m[:3, :3] @ pos[v] + m[:3, 3]); Nn += w * (m[:3, :3] @ nor[v])
            tot += w
        if tot > 0:
            pos[v] = P / tot; nor[v] = Nn / (np.linalg.norm(Nn) or 1)
    M['pos'], M['nor'] = pos, nor
    return M


def reduire_os(M):
    """Poids des os supprimés (doigts, bouts) reportés sur l'os gardé le plus proche dans la hiérarchie."""
    def garde(nom):
        if nom in GARDES:
            return GARDES.index(nom)
        for c in ('l', 'r'):
            if nom.endswith('_' + c) and any(nom.startswith(d) for d in ('index', 'middle', 'ring', 'pinky', 'thumb')):
                return GARDES.index('hand_' + c)
            if nom == 'ball_leaf_' + c:
                return GARDES.index('ball_' + c)
        return 0
    table = np.array([garde(n) for n in M['noms_os']])
    J = table[M['j']]
    Wt = M['w'].copy()
    # fusion des poids d'un même os
    for v in range(len(J)):
        d = {}
        for k in range(4):
            if Wt[v, k] > 0:
                d[J[v, k]] = d.get(J[v, k], 0) + Wt[v, k]
        it = sorted(d.items(), key=lambda x: -x[1])[:4] or [(0, 1.0)]
        s = sum(w for _, w in it)
        J[v] = [j for j, _ in it] + [it[0][0]] * (4 - len(it))
        Wt[v] = [w / s for _, w in it] + [0] * (4 - len(it))
    M['j'], M['w'] = J, Wt
    return M


def habiller(M, sexe):
    """Classe de chaque sommet (en pose de repos, bras en croix) et tissu décollé de la peau."""
    P, Nn, J = M['pos'], M['nor'], M['j']
    dom = [GARDES[J[v, 0]] for v in range(len(P))]
    cls = np.zeros(len(P), dtype=np.uint8)
    dec = np.zeros(len(P))
    haut_short = 0.6 if sexe == 'H' else 0.66
    for v, (x, y, z) in enumerate(P):
        d = dom[v]
        ax = abs(x)
        if d in ('foot_l', 'foot_r', 'ball_l', 'ball_r') or y < 0.11:
            cls[v], dec[v] = (SEMELLE, 0.012) if y < 0.025 else (BLANC, 0.012)
        elif y < 0.24 and d.startswith('calf'):
            cls[v], dec[v] = BLANC, 0.004
        elif d.startswith('lowerarm') and 0.62 < ax < 0.69:
            cls[v], dec[v] = BLANC, 0.006
        elif d in ('Head',) and 1.71 < y < 1.75 and z < 0.09:
            cls[v], dec[v] = BANDEAU, 0.005
        elif (d in ('pelvis',) or (d.startswith('thigh') and y > haut_short) or (d.startswith('spine_01') and y < 1.0)) and y < 1.03:
            hem = d.startswith('thigh') and y < haut_short + 0.03
            cls[v] = LISERE if (hem or (ax > 0.17 and abs(z) < 0.035 and y < 1.0 and d.startswith('thigh'))) else SHORT
            dec[v] = 0.012 + (0.02 * max(0.0, (0.86 - y) / 0.26) if d.startswith('thigh') else 0.0)
        elif d.startswith('spine') or d.startswith('clavicle') or (d.startswith('upperarm') and ax < 0.36) or (d == 'pelvis' and y >= 1.03):
            if d.startswith('upperarm') and ax > 0.34:
                cls[v] = COTE                                               # bord de manche
            else:
                cls[v] = COTE if (abs(z) < 0.045 and ax > 0.12 and y < 1.42) else MAILLOT
            dec[v] = 0.008
        if sexe == 'F' and cls[v] == PEAU and d.startswith('spine') and y > 1.0:
            cls[v], dec[v] = MAILLOT, 0.008
    # tissu décollé de la peau par un champ LISSE (sans déchirure aux bords) : le maillot (même règle que la page),
    # le short (plus ample en bas) ; chaussures, chaussettes et poignets gardent leur décalage par classe
    def rampe(v, a, b):
        t = np.clip((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax, rcou = np.abs(x), np.hypot(x, z + 0.03)
    corps_ = np.array([d.startswith(('spine', 'clavicle', 'upperarm', 'pelvis', 'thigh')) for d in dom])
    w_m = rampe(ax, 0.36, 0.33) * rampe(y, 0.97, 1.0) * np.maximum(rampe(y, 1.45, 1.42), rampe(rcou, 0.075, 0.095)) * rampe(y, 1.58, 1.55)
    w_s = rampe(y, haut_short - 0.02, haut_short + 0.01) * rampe(y, 1.06, 1.02)
    evase = np.where([d.startswith('thigh') for d in dom], 0.02 * np.clip((0.86 - y) / 0.26, 0, 1), 0.0)
    tissu = np.maximum(0.007 * w_m, (0.012 + evase) * w_s) * corps_
    autres = np.isin(cls, [BLANC, SEMELLE])
    dec = np.where(autres, dec, tissu)
    M['pos'] = P + Nn * dec[:, None]
    M['cls'] = cls
    return M


def jpeg(chemin, taille, qualite=82):
    im = Image.open(chemin).convert('RGB')
    im = im.resize((taille, taille), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'JPEG', quality=qualite, optimize=True); return b.getvalue()


class Ecrivain:
    def __init__(self):
        self.blob = bytearray(); self.json = {}

    def morceau(self, arr):
        while len(self.blob) % 4:
            self.blob.append(0)
        off = len(self.blob); self.blob += np.ascontiguousarray(arr).tobytes(); return off

    def primitive(self, M, tex):
        n = len(M['pos'])
        q = {'n': n, 'tex': tex,
             'pos': self.morceau(M['pos'].astype(np.float32)),
             'nor': self.morceau(np.clip(np.round(M['nor'] * 127), -127, 127).astype(np.int8)),
             'uv': self.morceau(np.clip(np.round(M['uv'] * 65535), 0, 65535).astype(np.uint16)),
             'jnt': self.morceau(M['j'].astype(np.uint8)),
             'wgt': self.morceau(np.clip(np.round(M['w'] * 255), 0, 255).astype(np.uint8)),
             'cls': self.morceau(M.get('cls', np.zeros(n, dtype=np.uint8)).astype(np.uint8))}
        idx = M['idx'].astype(np.uint16 if n < 65536 else np.uint32)
        q['idx'], q['ni'], q['i32'] = self.morceau(idx), len(idx), n >= 65536
        return q

    def ecrire(self, chemin):
        js = json.dumps(self.json, separators=(',', ':')).encode()
        js += b' ' * ((4 - len(js) % 4) % 4)
        with open(chemin, 'wb') as f:
            f.write(b'TEJ3' + struct.pack('<I', len(js)) + js + bytes(self.blob))


def principal(src, sortie):
    base = os.path.join(src, 'Base Characters', 'Godot - UE')
    coif = os.path.join(src, 'Hairstyles', 'Rigged to Head Bone', 'glTF (Godot -Unreal)')
    tex = os.path.join(src, 'Base Characters', 'Textures')
    E = Ecrivain()
    corps = {}
    for sexe, fichier, noeud in (('H', 'Superhero_Male_FullBody.gltf', 'SuperHero_Male'), ('F', 'Superhero_Female_FullBody.gltf', None)):
        gl = Gltf(os.path.join(base, fichier))
        if noeud is None:
            noeud = next(n['name'] for n in gl.g['nodes'] if 'mesh' in n and 'Superhero' in gl.g['meshes'][n['mesh']]['name'])
        os_, W, _ = squelette(gl)
        if sexe == 'H':
            E.json['os'] = {'noms': GARDES, 'parents': [o['parent'] for o in os_],
                            't': [list(map(float, o['loc'][:3, 3])) for o in os_], 'q': [list(map(float, quat(o['loc']))) for o in os_],
                            'ibm': E.morceau(np.array([np.linalg.inv(o['monde']).T.reshape(-1) for o in os_], dtype=np.float32))}
        M = habiller(reduire_os(poings(gl, gl.mesh(noeud), W)), sexe)
        yeux = reduire_os(gl.mesh('Eyes'))
        corps[sexe] = {'corps': E.primitive(M, 'peau'), 'yeux': E.primitive(yeux, 'yeux')}
    E.json['corps'] = corps
    E.json['cheveux'] = {}
    for nom, fichier, t in (('court', 'Hair_SimpleParted', 'cheveux1'), ('ras', 'Hair_Buzzed', 'cheveux1'),
                            ('chignon', 'Hair_Buns', 'cheveux2'), ('long', 'Hair_Long', 'cheveux2'),
                            ('sourcils_H', 'Eyebrows_Regular', 'cheveux1'), ('sourcils_F', 'Eyebrows_Female', 'cheveux2')):
        gl = Gltf(os.path.join(coif, fichier + '.gltf'))
        nd = next(n['name'] for n in gl.g['nodes'] if 'mesh' in n)
        E.json['cheveux'][nom] = E.primitive(reduire_os(gl.mesh(nd)), t)
    E.json['images'] = {}
    for nom, f, t in (('peau_H_clair', 'T_Superhero_Male_Ligh.png', 1024), ('peau_H_fonce', 'T_Superhero_Male_Dark.png', 1024),
                      ('peau_F_clair', 'T_Superhero_Female_Light_BaseColor.png', 1024), ('peau_F_fonce', 'T_Superhero_Female_Dark_BaseColor.png', 1024),
                      ('cheveux1', 'T_Hair_1_BaseColor.png', 512), ('cheveux2', 'T_Hair_2_BaseColor.png', 512), ('yeux', 'T_Eye_Brown.png', 128)):
        b = jpeg(os.path.join(tex, f), t)
        E.json['images'][nom] = [E.morceau(np.frombuffer(b, dtype=np.uint8)), len(b)]
    E.json['licence'] = 'Quaternius, Universal Base Characters : CC0 1.0 (domaine public)'
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    E.ecrire(sortie)
    print(f'{sortie} : {os.path.getsize(sortie) / 1e6:.2f} Mo')


if __name__ == '__main__':
    principal(sys.argv[1], sys.argv[2])
