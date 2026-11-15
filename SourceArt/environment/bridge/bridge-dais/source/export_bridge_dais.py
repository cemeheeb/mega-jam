"""Bridge dais: FBX and textures for Unreal (pipeline/unreal.md «Выгрузка из Blender», kit.md step 11).
Copied from export_navigator_console.py.

    cd SourceArt && /Applications/Blender.app/Contents/MacOS/Blender -b \
        environment/bridge/bridge-dais/source/bridge-dais.blend --python-exit-code 1 \
        --python environment/bridge/bridge-dais/source/export_bridge_dais.py

Nothing is saved into the blend. Writes into the asset folder (parent of source/):
- SM_BridgeDais.fbx: one Static Mesh, origin at the middle of the bottom, the worn walk-up side at -X (south in Unreal
  with yaw 0); mesh already in centimetres (scene unit 0.01 m for the export): the MCP import goes through FbxFactory
  without unit conversion (unreal.md, first import); one slot MI_BridgeDais; Triangulate with custom normals last;
  collision one convex UCX_: a 32-sided prism 240 cm across, 0..12 cm, so that one walks up onto the top and the couch
  stands on it (the bolts on the mounting plate, 0.6 cm higher, stay out of it);
- T_BridgeDais_BaseColor/ORM/Emissive.png: copies of source/export (ArmorPaint + dais_post.py), the light strips in
  Emissive;
- T_BridgeDais_Normal.png: green channel inverted (OpenGL -> DirectX), so Flip Green stays off in Unreal.
Textures stay 2048 (not 1024 as in kit.md step 11), as the navigator console's: on a 2.4 m floor 1024 gives 2.3 mm
texels and the plate seams and the rubber pebbles blur away.
"""
import os
import shutil
from math import cos, sin, pi

import bpy
import numpy as np
from mathutils import Matrix, Vector

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(SRC)
NAME = "BridgeDais"
SLOT = "MI_BridgeDais"
R, TOP, SIDES = 1.2, 0.12, 32       # collision prism, metres


def textures():
    exp = os.path.join(SRC, "export")
    for key, suffix in (("base", "BaseColor"), ("orm", "ORM"), ("emission", "Emissive")):
        shutil.copyfile(os.path.join(exp, f"bridge-dais_{key}.png"), os.path.join(OUT, f"T_{NAME}_{suffix}.png"))
    im = bpy.data.images.load(os.path.join(exp, "bridge-dais_nor.png"))
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


def prism(name):
    verts = [(R * cos(2 * pi * i / SIDES), R * sin(2 * pi * i / SIDES), z) for z in (0.0, TOP) for i in range(SIDES)]
    faces = [tuple(range(SIDES))[::-1], tuple(range(SIDES, 2 * SIDES))]
    faces += [(i, (i + 1) % SIDES, SIDES + (i + 1) % SIDES, SIDES + i) for i in range(SIDES)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bounds(pts):
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def mesh():
    src = bpy.data.collections[NAME].objects[NAME]
    ob = src.copy()
    ob.data = src.data.copy()
    bpy.context.scene.collection.objects.link(ob)
    ob.data.transform(src.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    ob.hide_set(False)
    ob.hide_viewport = False
    ob.name = ob.data.name = "SM_" + NAME
    mat = bpy.data.materials.new(SLOT)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
    assert [u.name for u in ob.data.uv_layers] == ["UVMap"], [u.name for u in ob.data.uv_layers]
    ucx = [prism(f"UCX_SM_{NAME}_00")]

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
