"""Navigator console: FBX and textures for Unreal (pipeline/unreal.md «Выгрузка из Blender», kit.md step 11).

    cd SourceArt && /Applications/Blender.app/Contents/MacOS/Blender -b \
        environment/bridge/navigator-console/source/navigator-console.blend --python-exit-code 1 \
        --python environment/bridge/navigator-console/source/export_navigator_console.py

Nothing is saved into the blend. Writes into the asset folder (parent of source/):
- SM_NavigatorConsole.fbx: the console with both monitors joined in (no moving parts, one Static Mesh), origin at
  the middle of the bottom, operator side -Y in Blender = +Y in Unreal; mesh already in centimetres (scene unit
  0.01 m for the export): the MCP import goes through FbxFactory without unit conversion (unreal.md, first import);
  one slot MI_NavigatorConsole; Triangulate with custom normals last; two collision boxes UCX_: the body up to the
  desk top, the monitor shelf with the monitors (one convex hull would put a wall over the desk, where items lie);
- T_NavigatorConsole_BaseColor/ORM/Emissive.png: copies of source/export (ArmorPaint + navigator_post.py);
- T_NavigatorConsole_Normal.png: green channel inverted (OpenGL -> DirectX), so Flip Green stays off in Unreal.
Textures stay 2048 (not 1024 as in kit.md step 11): the author asked for finer scratches on the key panel (14.11),
at 1024 they would blur away.
"""
import os
import shutil

import bpy
import numpy as np
from mathutils import Matrix, Vector

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(SRC)
NAME = "NavigatorConsole"
SLOT = "MI_NavigatorConsole"
DESK_TOP = 1.003          # m, the working surface; the monitor shelf rises behind it to 1.074


def textures():
    exp = os.path.join(SRC, "export")
    for key, suffix in (("base", "BaseColor"), ("orm", "ORM"), ("emission", "Emissive")):
        shutil.copyfile(os.path.join(exp, f"navigator-console_{key}.png"), os.path.join(OUT, f"T_{NAME}_{suffix}.png"))
    im = bpy.data.images.load(os.path.join(exp, "navigator-console_nor.png"))
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    n = px[..., :3] * 2 - 1
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    n[..., 1] = -n[..., 1]
    px[..., :3] = n * 0.5 + 0.5
    px[..., 3] = 1
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUT, f"T_{NAME}_Normal.png")
    im.file_format = "PNG"
    bpy.context.scene.render.image_settings.color_mode = "RGB"
    im.save()
    print("textures", w, "x", h, "normal G inverted, mean z", round(float(n[..., 2].mean()), 4))


def box(name, lo, hi):
    xs, ys, zs = (lo.x, hi.x), (lo.y, hi.y), (lo.z, hi.z)
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x in xs for y in ys for z in zs], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bounds(pts):
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def mesh():
    col = bpy.data.collections[NAME]
    root = col.objects[NAME]
    parts = [root] + sorted((o for o in col.objects if o.parent == root), key=lambda o: o.name)
    assert [o.name for o in parts] == [NAME, "NavigatorMonitorLeft", "NavigatorMonitorRight"], [o.name for o in parts]
    root_inv = root.matrix_world.inverted()
    copies = []
    for o in parts:
        c = o.copy()
        c.data = o.data.copy()
        bpy.context.scene.collection.objects.link(c)
        c.parent = None
        c.data.transform(root_inv @ o.matrix_world)     # in the root's space: origin = middle of the bottom
        c.matrix_world = Matrix.Identity(4)
        c.hide_set(False)
        c.hide_viewport = False
        copies.append(c)
    # collision from the parts before the join (metres): body to the desk top, shelf + monitors above it
    body = [v.co for v in copies[0].data.vertices]
    lo, hi = bounds(body)
    shelf = [p for p in body if p.z > DESK_TOP + 0.005] + [v.co for c in copies[1:] for v in c.data.vertices]
    slo, shi = bounds(shelf)
    slo.z = DESK_TOP
    ucx = [box(f"UCX_SM_{NAME}_00", lo, Vector((hi.x, hi.y, DESK_TOP))), box(f"UCX_SM_{NAME}_01", slo, shi)]

    bpy.ops.object.select_all(action="DESELECT")
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.join()
    ob = copies[0]
    ob.name = ob.data.name = "SM_" + NAME
    mat = bpy.data.materials.new(SLOT)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
    assert [u.name for u in ob.data.uv_layers] == ["UVMap"], [u.name for u in ob.data.uv_layers]

    # centimetres: mesh x 100 under a 0.01 m scene unit, so the file carries UnitScaleFactor 1 and the size is right
    # with or without unit conversion on import
    bpy.context.scene.unit_settings.scale_length = 0.01
    for o in [ob] + ucx:
        o.data.transform(Matrix.Scale(100.0, 4))
    tri = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
    tri.keep_custom_normals = True

    bpy.ops.object.select_all(action="DESELECT")
    for o in [ob] + ucx:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, f"SM_{NAME}.fbx")
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False, use_tspace=False,
        use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False, colors_type="NONE",
    )
    dg = bpy.context.evaluated_depsgraph_get()
    tris = len(ob.evaluated_get(dg).data.polygons)
    a, b = bounds([v.co for v in ob.data.vertices])
    print(f"SM_{NAME}.fbx tris {tris} size_cm {b.x - a.x:.1f} x {b.y - a.y:.1f} x {b.z - a.z:.1f} lo {tuple(round(c, 1) for c in a)}")
    for o in ucx:
        a, b = bounds([v.co for v in o.data.vertices])
        print(f"  {o.name}: {tuple(round(c, 1) for c in a)} .. {tuple(round(c, 1) for c in b)} cm")


textures()
mesh()
