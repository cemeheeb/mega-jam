"""Server rack: FBX for Unreal with flat zone materials (15.11, first pass, before the textures of kit.md).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        SourceArt/environment/computer/server-rack/source/server-rack.blend --python-exit-code 1 \
        --python SourceArt/environment/computer/server-rack/source/export_server_rack.py

Nothing is saved into the blend. Same route as the sleep capsule (export_sleep_capsule.py): the model is at step 2
of pipeline/kit.md (built from primitives, zones as preview colours), there is no atlas and no ArmorPaint textures
yet, so every zone becomes its own material slot MI_ServerRack<Zone> and Unreal fills it with a flat M_KitSolid
instance (tools/ue/import_server_rack.py). Panel seams, side vents and the grille holes live in the height map of
the later steps and are not in this mesh. When the textures are baked, the same mesh is exported again with one slot
and M_Kit.

Writes into the asset folder (parent of source/):
- SM_ServerRack.fbx: object ServerRack as is, origin in the middle of the body footprint on the floor, front -Y in
  Blender = +Y in Unreal; centimetres (scene unit 0.01 m for the export, as the other kit exports); Triangulate with
  custom normals last; collision UCX_ boxes: the body, the cap and the block of drawers in front of the frame
  (handles included), the side recesses under the body are ignored.
- zones.json: zone -> linear preview colour of the blend, read by the Unreal import.
"""
import json
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(SRC)
NAME = "ServerRack"
ZONES = ['white', 'aluminium', 'graphite', 'orange', 'teal', 'frosted', 'glass', 'satin', 'plastic', 'grille', 'fabric', 'linen']

# collision boxes, metres (measured on the mesh, 15.11): body 1940 x 740 up to 1887, cap 1990 x 790 up to 2000,
# drawers from x -0.859 to 0.859 and z 0.211 to 1.85, their U handles stick out to y -0.412
BOXES = [((-0.97, -0.37, 0.0), (0.97, 0.37, 1.887)),         # body
         ((-0.995, -0.395, 1.887), (0.995, 0.395, 2.0)),     # cap
         ((-0.86, -0.412, 0.2), (0.86, -0.37, 1.86))]        # drawers with the handles


def box(name, lo, hi):
    xs, ys, zs = (lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2])
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x in xs for y in ys for z in zs], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def main():
    src = bpy.data.objects[NAME]
    assert src.matrix_world.is_identity, f"{NAME} is expected at the origin, unscaled"
    me = src.data.copy()                       # the source mesh stays untouched
    ob = bpy.data.objects.new("SM_" + NAME, me)
    bpy.context.scene.collection.objects.link(ob)

    n = len(me.polygons)
    zone = np.empty(n, np.int32)
    me.attributes["zone"].data.foreach_get("value", zone)
    colours = np.empty(len(me.attributes["ZonePreview"].data) * 4, np.float32)
    me.attributes["ZonePreview"].data.foreach_get("color", colours)
    colours = colours.reshape(-1, 4)
    loop_start = np.empty(n, np.int32)
    me.polygons.foreach_get("loop_start", loop_start)

    used = sorted(set(zone.tolist()))
    me.materials.clear()
    palette = {}
    for z in used:
        title = ZONES[z].capitalize()
        me.materials.append(bpy.data.materials.new(f"MI_{NAME}{title}"))
        palette[f"{NAME}{title}"] = [round(float(v), 4) for v in colours[loop_start[np.argmax(zone == z)]][:3]]
    slot = np.searchsorted(np.array(used), zone).astype(np.int32)
    me.polygons.foreach_set("material_index", slot)
    me.update()
    with open(os.path.join(OUT, "zones.json"), "w") as f:
        json.dump(palette, f, indent=1)

    ucx = [box(f"UCX_SM_{NAME}_{k:02d}", lo, hi) for k, (lo, hi) in enumerate(BOXES)]
    bpy.context.scene.unit_settings.scale_length = 0.01
    for e in [ob] + ucx:
        e.data.transform(Matrix.Scale(100.0, 4))
    tri = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
    tri.keep_custom_normals = True
    bpy.ops.object.select_all(action="DESELECT")
    for e in [ob] + ucx:
        e.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, f"SM_{NAME}.fbx"),
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="EDGE", use_triangles=False, use_tspace=False,
        use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False, colors_type="NONE",
    )
    lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in me.vertices) for i in range(3)])
    print(f"## SM_{NAME}: {hi.x - lo.x:.1f} x {hi.y - lo.y:.1f} x {hi.z - lo.z:.1f} cm, "
          f"{sum(len(p.vertices) - 2 for p in me.polygons)} triangles, slots {[m.name for m in me.materials]}, "
          f"{len(ucx)} collision boxes")
    print("## zones:", palette)


main()
