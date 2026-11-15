"""Bridge dais, step 7 (pipeline/kit.md): the FBX for ArmorPaint, source/bridge-dais.fbx.
Run in the live Blender after dais_pack.py: exec(open(<this file>).read()). Only the mesh, edge smoothing, no animation,
no leaf bones; the object stays in place.
"""
import bpy

SRC = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/bridge-dais/source'
ob = bpy.data.objects['BridgeDais']
bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
print(bpy.ops.export_scene.fbx(filepath=SRC + '/bridge-dais.fbx', use_selection=True, object_types={'MESH'},
                               mesh_smooth_type='EDGE', bake_anim=False, add_leaf_bones=False))
bpy.ops.object.select_all(action='DESELECT')
