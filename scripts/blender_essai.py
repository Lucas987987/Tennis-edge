#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blender_essai.py — ESSAI : notre court de tennis rendu par Blender (paquet 278, 18/11/2026, Lucas : « Installe
blender »).

But : savoir, chiffres à l'appui, si Blender peut fabriquer la vidéo du jour sur les machines gratuites de GitHub
(sans carte graphique) dans un temps raisonnable, et à quoi ressemble l'image. Rien n'est publié : les images et
les temps partent sur le Telegram privé ; le résumé du run ne contient que des temps.

La scène reprend le stade du site : court dur bleu (dimensions réglementaires), lignes, filet, tribunes et ~3 000
spectateurs (copies liées d'un même modèle, couleurs au hasard), deux joueurs (mannequins simples, maillots cyan et
rose), la balle en mouvement (flou de mouvement), lumière de nuit (projecteurs) ou de jour (ciel et soleil).
Plans : vue télé, gros plan avec flou d'arrière-plan. Moteurs : Cycles sur le processeur (débruitage OIDN) et,
si la machine le permet, EEVEE.

Lancement : blender -b --factory-startup -P scripts/blender_essai.py -- --sortie essai_blender [--echantillons 24] [--moteur eevee]
18/11/2026 (paquet 279) : 1er essai — Cycles 44,5 s par image (26 h par vidéo), EEVEE planté faute de libEGL. EEVEE est
réessayé avec l'OpenGL logiciel de Mesa (llvmpipe) dans un écran virtuel (xvfb), sur les trois plans.
Sortie : PNG + temps.json (secondes par image, par moteur et par plan).
"""
import json
import math
import os
import random
import sys
import time

import bpy

L, W, S, SL = 23.77, 10.97, 8.23, 6.40
HL = L / 2


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = {'sortie': 'essai_blender', 'echantillons': 24, 'largeur': 1080, 'hauteur': 1350, 'moteur': 'cycles', 'echantillons_eevee': 16}
    for k in range(0, len(a) - 1, 2):
        o[a[k].lstrip('-')] = a[k + 1]
    for k in ('echantillons', 'largeur', 'hauteur', 'echantillons_eevee'):
        o[k] = int(o[k])
    return o


def mat(nom, couleur, rugosite=0.6, emission=0.0, alpha=1.0, metal=0.0):
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*couleur, 1)
    b.inputs['Roughness'].default_value = rugosite
    b.inputs['Metallic'].default_value = metal
    if emission:
        for k in ('Emission Color', 'Emission'):
            if k in b.inputs:
                b.inputs[k].default_value = (*couleur, 1)
                break
        if 'Emission Strength' in b.inputs:
            b.inputs['Emission Strength'].default_value = emission
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.blend_method = 'BLEND'
        except Exception:
            pass
    return m


def hexa(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x ** 2.2 for x in c)                                         # sRGB → linéaire


def boite(nom, taille, pos, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos, rotation=rot)
    o = bpy.context.active_object
    o.name = nom
    o.scale = taille
    o.data.materials.append(m)
    return o


def plan(nom, sx, sy, pos, m):
    bpy.ops.mesh.primitive_plane_add(size=1, location=pos)
    o = bpy.context.active_object
    o.name = nom
    o.scale = (sx, sy, 1)
    o.data.materials.append(m)
    return o


def court():
    plan('sol', 40, 50, (0, 0, -0.005), mat('sol', hexa('#3a7a5c'), 0.7))
    plan('court', W + 0.6, L + 0.6, (0, 0, 0), mat('court', hexa('#2a5ea8'), 0.55))
    blanc = mat('ligne', (0.92, 0.92, 0.92), 0.5)
    e = 0.05
    for y in (-HL, HL):
        plan('fond', W, e, (0, y, 0.002), blanc)
    for x in (-W / 2, W / 2, -S / 2, S / 2):
        plan('laterale', e, L, (x, 0, 0.002), blanc)
    for y in (-SL, SL):
        plan('service', S, e, (0, y, 0.002), blanc)
    plan('centre', e, 2 * SL, (0, 0, 0.002), blanc)
    # filet : poteaux, bande blanche, mailles (transparentes)
    gris = mat('poteau', (0.8, 0.8, 0.85), 0.3, metal=0.6)
    for x in (-(W / 2 + 0.914), W / 2 + 0.914):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=1.07, location=(x, 0, 0.535))
        bpy.context.active_object.data.materials.append(gris)
    boite('bande', (W + 1.83, 0.03, 0.06), (0, 0, 0.94), blanc)
    boite('mailles', (W + 1.83, 0.01, 0.88), (0, 0, 0.47), mat('mailles', (0.02, 0.02, 0.03), 0.8, alpha=0.55))


def stade(n_spect=3000, graine=7):
    """Murs, tribunes en gradins, public : copies liées d'un même spectateur, couleurs au hasard."""
    r = random.Random(graine)
    mur = mat('mur', hexa('#16204a'), 0.6)
    bx, by = W / 2 + 4.3, HL + 6.8
    for (x, y, sx, sy) in ((0, -by, 2 * bx, 0.3), (0, by, 2 * bx, 0.3), (-bx, 0, 0.3, 2 * by), (bx, 0, 0.3, 2 * by)):
        boite('mur', (sx, sy, 1.0), (x, y, 0.5), mur)
    led = mat('led', (0.2, 0.9, 1.0), 0.4, emission=4.0)
    for (x, y, sx, sy) in ((0, -by + 0.16, 2 * bx, 0.02), (0, by - 0.16, 2 * bx, 0.02), (-bx + 0.16, 0, 0.02, 2 * by), (bx - 0.16, 0, 0.02, 2 * by)):
        boite('led', (sx, sy, 0.12), (x, y, 0.9), led)
    gradin = mat('gradin', hexa('#26244a'), 0.8)
    rangs, pas, haut = 14, 0.8, 0.42
    places = []
    for c in range(4):
        for k in range(rangs):
            d, z = k * pas, 1.1 + k * haut
            if c < 2:
                s = -1 if c == 0 else 1
                boite('g', (pas, 2 * by + 6 + 2 * d, haut), (s * (bx + 1.2 + d), 0, z - haut / 2), gradin)
                lg = 2 * by + 6 + 2 * d
                for u in range(int(lg / 0.58)):
                    places.append((s * (bx + 1.2 + d), -lg / 2 + (u + 0.5) * 0.58, z, math.pi / 2 * s))
            else:
                s = -1 if c == 2 else 1
                boite('g', (2 * bx + 2.4 + 2 * d, pas, haut), (0, s * (by + 1.2 + d), z - haut / 2), gradin)
                lg = 2 * bx + 2.4 + 2 * d
                for u in range(int(lg / 0.58)):
                    places.append((-lg / 2 + (u + 0.5) * 0.58, s * (by + 1.2 + d), z, 0 if s < 0 else math.pi))
    r.shuffle(places)
    # le spectateur type : buste + tête ; couleur du maillot par objet (Object Info → Random)
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.19, depth=0.55, location=(0, 0, 0.28))
    buste = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=0.11, location=(0, 0, 0.68))
    tete = bpy.context.active_object
    tete.data.materials.append(mat('peau', hexa('#d09a78'), 0.5))
    mm = bpy.data.materials.new('maillots')
    mm.use_nodes = True
    nt = mm.node_tree
    info = nt.nodes.new('ShaderNodeObjectInfo')
    rampe = nt.nodes.new('ShaderNodeValToRGB')
    els = rampe.color_ramp.elements
    tons = ['#d8d8e0', '#2c2c3a', '#3b4a6b', '#7a2f35', '#c9a227', '#2f5f8f', '#f0f0f0', '#a65d2e', '#4a7a5a', '#d07080']
    rampe.color_ramp.interpolation = 'CONSTANT'
    while len(els) < len(tons):
        els.new(0.5)
    for k, t in enumerate(tons):
        els[k].position = k / len(tons)
        els[k].color = (*hexa(t), 1)
    nt.links.new(info.outputs['Random'], rampe.inputs['Fac'])
    nt.links.new(rampe.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    buste.data.materials.append(mm)
    for o in (buste, tete):
        o.select_set(True)
    bpy.context.view_layer.objects.active = buste
    bpy.ops.object.join()
    modele = bpy.context.active_object
    modele.name = 'spectateur'
    coll = bpy.data.collections.new('public')
    bpy.context.scene.collection.children.link(coll)
    for k, (x, y, z, a) in enumerate(places[:n_spect]):
        o = bpy.data.objects.new(f'sp{k}', modele.data)                       # copie liée : même maillage
        o.location = (x, y, z)
        o.rotation_euler = (0, 0, a + r.uniform(-0.2, 0.2))
        s = r.uniform(0.9, 1.05)
        o.scale = (s, s, s)
        coll.objects.link(o)
    modele.hide_render = True
    return len(places[:n_spect])


def joueur(nom, couleur, x, y, face):
    """Mannequin : jambes, short, maillot, bras, tête, raquette."""
    peau = mat('peau_' + nom, hexa('#c98f6c'), 0.45)
    maillot = mat('maillot_' + nom, couleur, 0.55)
    short = mat('short_' + nom, hexa('#16244f'), 0.6)
    morceaux = []

    def cyl(r_, h, pos, m, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=r_, depth=h, location=pos, rotation=rot)
        o = bpy.context.active_object
        o.data.materials.append(m)
        bpy.ops.object.shade_smooth()
        morceaux.append(o)

    for s in (-0.11, 0.11):
        cyl(0.065, 0.85, (x + s, y, 0.45), peau)
    cyl(0.17, 0.25, (x, y, 0.95), short)
    cyl(0.19, 0.55, (x, y, 1.3), maillot)
    for s in (-1, 1):
        cyl(0.05, 0.6, (x + s * 0.27, y + 0.08 * face, 1.22), peau, rot=(0.35 * face, s * 0.25, 0))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.12, location=(x, y, 1.72))
    t = bpy.context.active_object
    t.data.materials.append(peau)
    bpy.ops.object.shade_smooth()
    morceaux.append(t)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.14, minor_radius=0.012, location=(x + 0.45, y + 0.35 * face, 1.15), rotation=(math.pi / 2.4, 0, 0))
    raq = bpy.context.active_object
    raq.data.materials.append(mat('raquette', (0.05, 0.05, 0.06), 0.3))
    morceaux.append(raq)
    return morceaux


def balle():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.033, location=(0.5, -6, 1.1))
    b = bpy.context.active_object
    b.data.materials.append(mat('balle', (0.75, 1.0, 0.1), 0.6, emission=0.6))
    bpy.ops.object.shade_smooth()
    sc = bpy.context.scene
    for f, (y, z) in ((1, (-10.5, 1.0)), (3, (-6.0, 1.8)), (5, (-1.0, 2.0))):  # elle file vers le filet : flou de mouvement
        sc.frame_set(f)
        b.location = (0.6, y, z)
        b.keyframe_insert('location')
    return b


def lumieres(jour):
    sc = bpy.context.scene
    monde = bpy.data.worlds.new('monde')
    sc.world = monde
    monde.use_nodes = True
    fond = monde.node_tree.nodes['Background']
    if jour:
        ciel = monde.node_tree.nodes.new('ShaderNodeTexSky')
        try:
            ciel.sky_type = 'NISHITA'
            ciel.sun_elevation = math.radians(38)
            ciel.sun_rotation = math.radians(150)
        except Exception:
            pass
        monde.node_tree.links.new(ciel.outputs['Color'], fond.inputs['Color'])
        fond.inputs['Strength'].default_value = 0.35
        bpy.ops.object.light_add(type='SUN', rotation=(math.radians(52), 0, math.radians(150)))
        bpy.context.active_object.data.energy = 4.5
        bpy.context.active_object.data.angle = math.radians(1.5)
    else:
        fond.inputs['Color'].default_value = (0.01, 0.008, 0.03, 1)
        fond.inputs['Strength'].default_value = 1
        for x in (-14, 14):                                                 # rampes de projecteurs du toit
            for y in (-16, -6, 6, 16):
                bpy.ops.object.light_add(type='AREA', location=(x, y, 16))
                lu = bpy.context.active_object
                lu.data.energy = 25000
                lu.data.size = 4
                lu.rotation_euler = (0, math.radians(35 if x < 0 else -35), 0)
        bpy.ops.object.light_add(type='AREA', location=(0, 0, 22))
        bpy.context.active_object.data.energy = 30000
        bpy.context.active_object.data.size = 14


def camera(nom, oeil, cible, focale_mm, flou=None):
    bpy.ops.object.camera_add(location=oeil)
    c = bpy.context.active_object
    c.name = nom
    bpy.ops.object.empty_add(location=cible)
    vise = bpy.context.active_object
    t = c.constraints.new('TRACK_TO')
    t.target = vise
    t.track_axis = 'TRACK_NEGATIVE_Z'
    t.up_axis = 'UP_Y'
    c.data.lens = focale_mm
    if flou:
        c.data.dof.use_dof = True
        c.data.dof.focus_object = flou[0]
        c.data.dof.aperture_fstop = flou[1]
    return c


def rendre(chemin, moteur, o):
    sc = bpy.context.scene
    sc.render.engine = moteur
    sc.render.resolution_x, sc.render.resolution_y = o['largeur'], o['hauteur']
    sc.render.resolution_percentage = 100
    sc.render.filepath = chemin
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_motion_blur = True
    sc.frame_set(3)
    if moteur == 'CYCLES':
        sc.cycles.device = 'CPU'
        sc.cycles.samples = o['echantillons']
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.use_denoising = True
        try:
            sc.cycles.denoiser = 'OPENIMAGEDENOISE'
        except Exception:
            pass
        sc.render.use_persistent_data = True
    else:                                                                       # EEVEE (paquet 279) : rendu OpenGL logiciel
        try:
            sc.eevee.taa_render_samples = o['echantillons_eevee']
        except Exception:
            pass
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    return round(time.time() - t0, 2)


def main():
    o = args()
    os.makedirs(o['sortie'], exist_ok=True)
    res = {'blender': bpy.app.version_string, 'processeurs': os.cpu_count(), 'resolution': [o['largeur'], o['hauteur']],
           'echantillons_cycles': o['echantillons'], 'rendus': []}
    t0 = time.time()
    eevee = o['moteur'] == 'eevee'
    for jour in (False, True):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        court()
        res['spectateurs'] = stade()
        j1 = joueur('a', hexa('#22c8e0'), 0.6, -HL - 0.8, 1)
        joueur('b', hexa('#e2449a'), -1.2, HL + 0.8, -1)
        balle()
        lumieres(jour)
        tv = camera('tv', (0, -HL - 18, 9.5), (0, -2.6, 0), 32)
        gros = camera('gros', (0.6 + 1.2, -HL + 3.6, 1.6), (0.6, -HL - 0.8, 1.45), 85, flou=(j1[6], 2.0))                     # la tête du joueur nette
        res['preparation_s'] = round(time.time() - t0, 1)
        ambiance = 'jour' if jour else 'nuit'
        plans = [('tv', tv), ('gros', gros)] if not jour else [('tv', tv)]
        for nom, cam in plans:
            bpy.context.scene.camera = cam
            for moteur in (('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE') if eevee else ('CYCLES',)):
                f = os.path.join(o['sortie'], f'{ambiance}_{nom}_{moteur.lower()}.png')
                try:
                    s = rendre(f, moteur, o)
                    res['rendus'].append({'ambiance': ambiance, 'plan': nom, 'moteur': moteur, 'secondes': s, 'ok': os.path.exists(f)})
                    print(f'{ambiance} {nom} {moteur} : {s} s', flush=True)
                    if moteur.startswith('BLENDER_EEVEE'):
                        break                                                 # EEVEE NEXT a marché : pas l'ancien
                except Exception as e:
                    res['rendus'].append({'ambiance': ambiance, 'plan': nom, 'moteur': moteur, 'erreur': str(e)[:200]})
                    print(f'{ambiance} {nom} {moteur} : échec ({e})', flush=True)
    # estimation pour la vidéo : ~85 s à 25 images/s
    ok = [r['secondes'] for r in res['rendus'] if r.get('secondes')]
    if ok:
        par_image = sum(ok) / len(ok)
        res['s_par_image'] = round(par_image, 1)
        res['video_85s_25ips_heures'] = round(par_image * 85 * 25 / 3600, 1)
    with open(os.path.join(o['sortie'], 'temps_eevee.json' if eevee else 'temps.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
