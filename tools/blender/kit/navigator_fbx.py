"""Navigator console, step 7 (pipeline/kit.md): the FBX for ArmorPaint, source/navigator-console.fbx.
Run in the live Blender after navigator_pack.py: exec(open(<this file>).read()).
Only the meshes of the collection, edge smoothing, no animation, no leaf bones; the objects stay in place.
"""
import bpy

SRC = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/navigator-console/source'
obs = [bpy.data.objects[n] for n in ('NavigatorConsole', 'NavigatorMonitorRight', 'NavigatorMonitorLeft')]
bpy.ops.object.select_all(action='DESELECT')
for o in obs:
    o.select_set(True)
bpy.context.view_layer.objects.active = obs[0]
print(bpy.ops.export_scene.fbx(filepath=SRC + '/navigator-console.fbx', use_selection=True, object_types={'MESH'},
                               mesh_smooth_type='EDGE', bake_anim=False, add_leaf_bones=False))
bpy.ops.object.select_all(action='DESELECT')
