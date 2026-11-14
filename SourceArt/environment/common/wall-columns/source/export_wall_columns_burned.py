"""Burned wall columns (the author's Tripo models, 14.11): FBX and textures for Unreal (pipeline/unreal.md).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python SourceArt/environment/common/wall-columns/source/export_wall_columns_burned.py

Sources: source/tripo-burned/<Module>/burned_*.fbx with their base colour (one texture each), copied unchanged
from the author's zips. Only the modules that can burn: the author skipped the ones with nothing electrical inside
(lockers, shelf, blank); in a burned room those get soot only. The header has two versions: _Burned is the
author's second try (burned_header_2), _Burned2 the first (burned_header) with its floor debris removed, since over
the doorway it would hang in the air. The generator picks one of the versions per element by the burn seed.

The damage generator (ARunRoom::ApplyBurn, DESIGN.md §14) swaps SM_WallColumn<Module> for
SM_WallColumn<Module>_Burned (or _Burned2, ...), so each burned model is fitted onto the intact one:
- Tripo scales the whole model to 1 m, debris included, so the bounding box is no guide. The body is read off the
  top slab of the model (the top 7 % of its height): debris lies on the floor and torn panels hang lower down.
- width of that slab -> width of the intact column, full height -> intact height, depth scaled like the width;
  slab centre -> x = 0, slab back -> the intact back (y = 0, against the wall), bottom -> intact bottom.
  Torn panels and floor debris stick out in front of the face; behind the back they go into the wall.
- collision is the intact column's UCX box, read from SM_WallColumn<Module>.fbx: the room's floor grid stays the same.
- loose bits far below the body (DROP_BELOW, share of the model height) are removed: under a header they would float.
Writes into the asset folder: SM_WallColumn<Module>_Burned<N>.fbx (centimetres, slot MI_WallColumn<Module>Burned<N>),
T_WallColumn<Module>Burned<N>_BaseColor.png (2048, as Tripo gave; clean_burned_textures.py then takes the baked soot
off it) and _ORM.png (flat 4 x 4: AO 1, rough 0.8,
metal 0). <N> is empty for the first version, 2 for the second.
"""
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(SRC)
MODULES = [   # (module, version, Tripo file, drop loose parts whose top is below this share of the height)
    ("Rack", "", "burned_rack", None),
    ("Drawers", "", "burned_drawers", None),
    ("Vent", "", "burned_vent", None),
    ("Header", "", "burned_header_2", 0.2),
    ("Header", "2", "burned_header", 0.2),
]
SLAB = 0.07


def box(name, lo, hi):
    xs, ys, zs = (lo.x, hi.x), (lo.y, hi.y), (lo.z, hi.z)
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x in xs for y in ys for z in zs], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def intact_box(module):
    """The intact column's collision box in metres (its FBX is in centimetres with a 0.01 object scale)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(OUT, f"SM_WallColumn{module}.fbx"))
    ucx = [o for o in bpy.context.scene.objects if o.name.startswith("UCX_")]
    assert len(ucx) == 1, [o.name for o in bpy.context.scene.objects]
    return bounds(ucx[0])


def drop_low_islands(me, below):
    """Delete connected pieces whose highest point is under `below` (absolute z)."""
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    e = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", e)
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in e.reshape(-1, 2):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots = np.array([find(i) for i in range(n)])
    top = {}
    for r, z in zip(roots, co[:, 2]):
        top[r] = max(top.get(r, -1e9), z)
    doomed = {r for r, z in top.items() if z < below}
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    kill = [bm.verts[i] for i in range(n) if roots[i] in doomed]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    return len(kill)


def textures(module, version, tripo):
    tex = f"T_WallColumn{module}Burned{version}"
    src = bpy.data.images.load(os.path.join(SRC, "tripo-burned", module, f"{tripo}.fbm", f"{tripo}_basecolor.jpg"))
    src.colorspace_settings.name = "Non-Color"      # raw values in and out
    w, h = src.size
    px = np.empty(w * h * 4, np.float32)
    src.pixels.foreach_get(px)
    im = bpy.data.images.new("base", w, h, alpha=False, is_data=True)
    im.pixels.foreach_set(px)
    im.filepath_raw = os.path.join(OUT, f"{tex}_BaseColor.png")
    im.file_format = "PNG"
    im.save()
    orm = bpy.data.images.new("orm", 4, 4, alpha=False, is_data=True)
    orm.pixels.foreach_set(np.tile(np.array([1.0, 0.8, 0.0, 1.0], np.float32), 16))
    orm.filepath_raw = os.path.join(OUT, f"{tex}_ORM.png")
    orm.file_format = "PNG"
    orm.save()


def export(module, version, tripo, drop):
    lo_t, hi_t = intact_box(module)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(SRC, "tripo-burned", module, f"{tripo}.fbx"))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(meshes) == 1, [o.name for o in meshes]
    ob = meshes[0]
    ob.data.transform(ob.matrix_world)            # Tripo's FBX carries a 90 degree turn on the object
    ob.matrix_world = Matrix.Identity(4)
    lo, hi = bounds(ob)
    dropped = drop_low_islands(ob.data, lo.z + drop * (hi.z - lo.z)) if drop else 0
    lo, hi = bounds(ob)
    co = np.array([v.co[:] for v in ob.data.vertices])
    slab = co[co[:, 2] > hi.z - SLAB * (hi.z - lo.z)]
    x0, x1, back = slab[:, 0].min(), slab[:, 0].max(), slab[:, 1].max()
    sx = (hi_t.x - lo_t.x) / (x1 - x0)
    sz = (hi_t.z - lo_t.z) / (hi.z - lo.z)
    sy = sx
    m = Matrix.Diagonal((sx, sy, sz, 1.0))
    move = Vector((-(x0 + x1) / 2 * sx, hi_t.y - back * sy, lo_t.z - lo.z * sz))
    ob.data.transform(Matrix.Translation(move) @ m)

    name = f"SM_WallColumn{module}_Burned{version}"
    ob.name = ob.data.name = name
    ob.data.uv_layers[0].name = "UVMap"
    mat = bpy.data.materials.new(f"MI_WallColumn{module}Burned{version}")
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
    a, b = bounds(ob)
    slab_d = (back - slab[:, 1].min()) * sy
    print(f"{name}: scale x/y {sx:.3f} z {sz:.3f} (z/x {sz / sx:.3f}), dropped verts {dropped}, "
          f"size_m {b.x - a.x:.3f} x {b.y - a.y:.3f} x {b.z - a.z:.3f}, lo {tuple(round(c, 3) for c in a)}, "
          f"hi {tuple(round(c, 3) for c in b)}, top slab depth {slab_d:.3f} (intact {hi_t.y - lo_t.y:.3f})")
    ucx = box(f"UCX_{name}_00", lo_t, hi_t)

    bpy.context.scene.unit_settings.scale_length = 0.01
    for o in (ob, ucx):
        o.data.transform(Matrix.Scale(100.0, 4))
    tri = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
    tri.keep_custom_normals = True
    bpy.ops.object.select_all(action="DESELECT")
    for o in (ob, ucx):
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, f"{name}.fbx"),
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False, use_tspace=False,
        use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False, colors_type="NONE",
    )
    dg = bpy.context.evaluated_depsgraph_get()
    print(f"  {name}.fbx tris {len(ob.evaluated_get(dg).data.polygons)}")
    textures(module, version, tripo)


for module, version, tripo, drop in MODULES:
    export(module, version, tripo, drop)
