"""Burned navigator console (the author's Tripo model, 14.11): FBX and textures for Unreal (pipeline/unreal.md).

    cd SourceArt && /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python environment/bridge/navigator-console/source/export_navigator_console_burned.py

Source: source/tripo-burned/burned_console.fbx with its base colour (Tripo, one texture). The damage generator
swaps SM_NavigatorConsole for SM_NavigatorConsole_Burned in a burned room, so the burned one is fitted onto the
intact console: one uniform scale so the width is the same 1.5 m, origin in the middle of the bottom, back edge
at the intact back (y = +0.46 m in Blender, -46 cm in Unreal), operator side -Y in Blender = +Y in Unreal.
Debris spills forward past the intact front onto the floor; collision is the intact console's two boxes, so the
room's floor grid does not change and the debris can be walked over.
Writes into the asset folder: SM_NavigatorConsole_Burned.fbx (slot MI_NavigatorConsoleBurned, centimetres),
T_NavigatorConsoleBurned_BaseColor.png (2048), T_NavigatorConsoleBurned_ORM.png (flat 4 x 4: AO 1, rough 0.8,
metal 0: Tripo gave no ORM). No normal and no emissive map: M_Kit's flat normal and black emissive.
"""
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(SRC)
TRIPO = os.path.join(SRC, "tripo-burned", "burned_console.fbx")
NAME = "NavigatorConsole_Burned"
SLOT = "MI_NavigatorConsoleBurned"
TEX = "T_NavigatorConsoleBurned"
WIDTH, BACK = 1.5, 0.46          # m, the intact console: x -0.75..0.75, back edge at y = +0.46
DESK_TOP, SHELF_FRONT, TOP = 1.003, 0.147, 1.583   # the intact console's collision boxes (export_navigator_console.py)


def textures():
    src = bpy.data.images.load(os.path.join(SRC, "tripo-burned", "burned_console.fbm", "burned_console_basecolor.jpg"))
    src.colorspace_settings.name = "Non-Color"      # raw values in and out
    w, h = src.size
    px = np.empty(w * h * 4, np.float32)
    src.pixels.foreach_get(px)
    im = bpy.data.images.new("base", w, h, alpha=False, is_data=True)
    im.pixels.foreach_set(px)
    im.filepath_raw = os.path.join(OUT, f"{TEX}_BaseColor.png")
    im.file_format = "PNG"
    im.save()
    orm = bpy.data.images.new("orm", 4, 4, alpha=False, is_data=True)
    orm.pixels.foreach_set(np.tile(np.array([1.0, 0.8, 0.0, 1.0], np.float32), 16))
    orm.filepath_raw = os.path.join(OUT, f"{TEX}_ORM.png")
    orm.file_format = "PNG"
    orm.save()
    print("textures", im.size[0], "x", im.size[1])


def box(name, lo, hi):
    xs, ys, zs = (lo.x, hi.x), (lo.y, hi.y), (lo.z, hi.z)
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x in xs for y in ys for z in zs], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mesh():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.fbx(filepath=TRIPO)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(meshes) == 1, [o.name for o in meshes]
    ob = meshes[0]
    ob.data.transform(ob.matrix_world)            # Tripo's FBX carries a 90 degree turn on the object
    ob.matrix_world = Matrix.Identity(4)
    pts = [v.co for v in ob.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    s = WIDTH / (hi.x - lo.x)
    move = Vector((-(lo.x + hi.x) / 2 * s, BACK - hi.y * s, -lo.z * s))
    ob.data.transform(Matrix.Translation(move) @ Matrix.Scale(s, 4))
    ob.name = ob.data.name = "SM_" + NAME
    ob.data.uv_layers[0].name = "UVMap"
    mat = bpy.data.materials.new(SLOT)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
    pts = [v.co for v in ob.data.vertices]
    a = Vector([min(p[i] for p in pts) for i in range(3)])
    b = Vector([max(p[i] for p in pts) for i in range(3)])
    print(f"scale {s:.4f}, size_m {b.x - a.x:.3f} x {b.y - a.y:.3f} x {b.z - a.z:.3f}, lo {tuple(round(c, 3) for c in a)}")
    ucx = [box(f"UCX_SM_{NAME}_00", Vector((-WIDTH / 2, -BACK, 0)), Vector((WIDTH / 2, BACK, DESK_TOP))),
           box(f"UCX_SM_{NAME}_01", Vector((-WIDTH / 2, SHELF_FRONT, DESK_TOP)), Vector((WIDTH / 2, BACK, TOP)))]

    bpy.context.scene.unit_settings.scale_length = 0.01
    for o in [ob] + ucx:
        o.data.transform(Matrix.Scale(100.0, 4))
    tri = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
    tri.keep_custom_normals = True
    bpy.ops.object.select_all(action="DESELECT")
    for o in [ob] + ucx:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, f"SM_{NAME}.fbx"),
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False, use_tspace=False,
        use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False, colors_type="NONE",
    )
    dg = bpy.context.evaluated_depsgraph_get()
    print(f"SM_{NAME}.fbx tris {len(ob.evaluated_get(dg).data.polygons)}")


textures()
mesh()
