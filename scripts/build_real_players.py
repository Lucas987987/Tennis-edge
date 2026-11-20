"""Run with Blender: blender -b -t 2 --python scripts/build_real_players.py -- /path/to/source /path/to/output"""
import bpy, sys, os
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:]
src=Path(args[0]); out=Path(args[1]);out.mkdir(parents=True,exist_ok=True)
for name in ('nathan','sophia'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fbx=src/f'renderpeople_{name}.fbx'
    bpy.ops.import_scene.fbx(filepath=str(fbx),use_anim=True)
    image=src/f'renderpeople_{name}.png'
    for mat in bpy.data.materials:
        if not mat.use_nodes: mat.use_nodes=True
        bsdf=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if bsdf and image.exists():
            tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image=bpy.data.images.load(str(image),check_existing=True)
            mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    bpy.ops.export_scene.gltf(filepath=str(out/f'player_{"a" if name=="nathan" else "b"}.glb'),export_format='GLB',export_apply=False,export_animations=True,export_image_format='AUTO')
    print('EXPORTED',name,(out/f'player_{"a" if name=="nathan" else "b"}.glb').stat().st_size)
