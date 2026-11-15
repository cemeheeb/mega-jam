"""Sleep capsule: FBX for Unreal with flat zone materials (15.11, first pass, before the textures of kit.md).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        SourceArt/environment/living/sleep-capsule/source/sleep-capsule.blend --python-exit-code 1 \
        --python SourceArt/environment/living/sleep-capsule/source/export_sleep_capsule.py

Nothing is saved into the blend. The author asked to put the capsule into the game while it is still at step 2 of
pipeline/kit.md (built from primitives, zones as preview colours): there is no atlas and no ArmorPaint textures yet,
so every zone becomes its own material slot MI_Capsule<Zone> and Unreal fills it with a flat M_KitSolid instance
(tools/ue/import_sleep_capsule.py), as the ceiling tiles do. Panel seams, grille slots and the tread ribs live in the
height map of the later steps and are not in this mesh. When the textures are baked, the same mesh is exported again
with one slot and M_Kit.

Writes into the asset folder (parent of source/):
- SM_SleepCapsule.fbx: object SleepCapsule as is, origin in the middle of the body footprint on the floor, open side
  -Y in Blender = +Y in Unreal, head at -X; centimetres (scene unit 0.01 m for the export, as the other kit exports);
  Triangulate with custom normals last; collision UCX_ boxes: the bunk up to the mattress top, both end walls, the
  canopy and the step, so the space over the mattress stays open (an item lies there).
- zones.json: zone -> linear preview colour of the blend, read by the Unreal import.
"""
import json
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(SRC)
NAME = "SleepCapsule"
ZONES = ['white', 'aluminium', 'graphite', 'orange', 'teal', 'frosted', 'glass', 'satin', 'plastic', 'grille', 'fabric', 'linen']

# collision boxes, metres (measured on the mesh by rays, 15.11): the mattress top is at 0.61, the inner faces of the
# end walls at -0.992 and 0.995, the canopy underside at 1.69, the base front at -0.446, the step ends at -0.702
BOXES = [((-1.182, -0.446, 0.0), (1.182, 0.5, 0.61)),       # bunk with the mattress
         ((-1.182, -0.5, 0.0), (-0.992, 0.5, 1.8)),         # head wall
         ((0.995, -0.5, 0.0), (1.182, 0.5, 1.8)),           # foot wall
         ((-1.182, -0.5, 1.69), (1.182, 0.5, 1.8)),         # canopy
         ((-0.85, -0.702, 0.0), (0.97, -0.446, 0.152))]     # step


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
    assert src.matrix_world.is_identity, "SleepCapsule is expected at the origin, unscaled"
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
        me.materials.append(bpy.data.materials.new(f"MI_Capsule{title}"))
        palette[f"Capsule{title}"] = [round(float(v), 4) for v in colours[loop_start[np.argmax(zone == z)]][:3]]
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
