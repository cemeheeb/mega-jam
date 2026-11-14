"""Ceiling tiles: FBX for Unreal (pipeline/unreal.md), from source/ceiling-tiles.blend.

    /Applications/Blender.app/Contents/MacOS/Blender -b SourceArt/environment/common/ceiling-tiles/source/ceiling-tiles.blend \
        --python-exit-code 1 --python SourceArt/environment/common/ceiling-tiles/source/export_ceiling_tiles.py

The tiles are built by tools/blender/kit/ceiling_tiles_build.py (75 x 75 cm, 5 cm thick, origin in the middle of the
face, the face looks up, the panel goes down to z = -5 cm). The ceiling is seen from 3 m away, so the tiles skip the
mask and ArmorPaint steps of pipeline/kit.md: no textures, each zone of the face attribute `zone` becomes its own
material slot MI_Ceiling<Zone>, a flat M_KitSolid instance in Unreal (tools/ue/import_ceiling_tiles.py takes the values
of the zone palette of the CeilingTiles material). The frosted diffuser of the light tile glows.

Writes SM_<Object>.fbx into the asset folder: centimetres (scene unit 0.01 m: the MCP import goes through the old
FbxFactory with no unit conversion), Triangulate keeping the normals of the sharp edges, no collision (the room's
ceiling box above the tiles has it). build_rooms.py puts the tiles on upside down, like the ceiling lamps.
"""
import os

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
OBJECTS = ("CeilingTile", "CeilingTileLight", "CeilingTileVent", "CeilingTileHatch")
ZONES = ["white", "aluminium", "graphite", "orange", "teal", "frosted", "glass", "satin", "plastic", "grille"]  # kit_lib


def export(name):
    src = bpy.data.objects[name + "_Source"]
    me = src.data.copy()                     # the original stays as built
    ob = bpy.data.objects.new(name + "_Export", me)
    bpy.context.scene.collection.objects.link(ob)
    zones = sorted({z.value for z in me.attributes["zone"].data})
    me.materials.clear()
    for z in zones:
        label = ZONES[z].capitalize()
        me.materials.append(bpy.data.materials.get(f"MI_Ceiling{label}") or bpy.data.materials.new(f"MI_Ceiling{label}"))
    slot = {z: i for i, z in enumerate(zones)}
    values = [slot[z.value] for z in me.attributes["zone"].data]
    me.polygons.foreach_set("material_index", values)
    me.transform(Matrix.Scale(100.0, 4))     # metres -> centimetres, about the object origin
    me.update()
    tri = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
    tri.keep_custom_normals = True
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    ob.name = name                           # the FBX node name; the source object gets a suffix meanwhile
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, f"SM_{name}.fbx"),
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False, use_tspace=False,
        use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False, colors_type="NONE",
    )
    dg = bpy.context.evaluated_depsgraph_get()
    tris = len(ob.evaluated_get(dg).data.polygons)
    co = [v.co for v in me.vertices]
    lo = [round(min(c[i] for c in co), 2) for i in range(3)]
    hi = [round(max(c[i] for c in co), 2) for i in range(3)]
    print(f"SM_{name}.fbx: tris {tris}, slots {[m.name for m in me.materials]}, cm {lo} .. {hi}")


bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 0.01
for n in OBJECTS:
    bpy.data.objects[n].name = n + "_Source"
for n in OBJECTS:
    export(n)
