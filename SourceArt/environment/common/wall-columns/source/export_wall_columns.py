"""Колонки-шкафы стены из Singula: FBX и текстуры для Unreal (pipeline/unreal.md).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python SourceArt/environment/common/wall-columns/source/export_wall_columns.py

Источник — готовые glb набора из Singula (environment/common/wall-columns, сделаны 12 ноября 2026, ADR-031/032
AssetStudio), скопированные без изменений в source/singula/. Сам набор здесь не перестраивается: его скрипты сборки,
запекания и износа живут в Singula.

На каждый glb:
- корень и его дети (крышка антресоли) сливаются в один меш с началом корня: середина задней стенки на полу.
  Крышка в игре не открывается, отдельная деталь ей не нужна;
- меш пишется сразу в сантиметрах (единица сцены 0,01 м), как у героя: импорт MCP идёт через старый FbxFactory
  без перевода единиц;
- материалы заменяются временными с именами экземпляров Unreal: WallColumns -> MI_WallColumns, остальные X -> MI_X;
- коллизия — одна коробка UCX_<меш>_00 по габаритам меша: в ниши игрок не заходит, а противники обходят коробки;
- последним в стек — Triangulate с сохранением заданных нормалей.
Оси Blender: x вдоль ряда, лицо в −Y; в Unreal лицо смотрит в +Y.
Текстуры набора (2048, 8 бит RGB) копируются как T_WallColumns_BaseColor.png и T_WallColumns_ORM.png.
"""

import glob
import os
import shutil
import struct

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "singula")
OUT = os.path.dirname(HERE)
SET = "WallColumns"


def textures():
    for src, dst in (("wall-columns_base.png", "T_WallColumns_BaseColor.png"), ("wall-columns_orm.png", "T_WallColumns_ORM.png")):
        path = os.path.join(SRC, src)
        with open(path, "rb") as f:
            head = f.read(26)
        w, h, depth, colour = struct.unpack(">IIBB", head[16:26])
        assert (depth, colour) == (8, 2), (src, depth, colour)   # 8 бит RGB без альфы
        shutil.copyfile(path, os.path.join(OUT, dst))
        print("texture", dst, w, h)


def temp_material(name, cache):
    target = "MI_" + name
    if target not in cache:
        mat = bpy.data.materials.new(target)
        mat.use_nodes = True
        cache[target] = mat
    return cache[target]


def collision_box(name, lo, hi):
    xs, ys, zs = (lo.x, hi.x), (lo.y, hi.y), (lo.z, hi.z)
    verts = [(x, y, z) for x in xs for y in ys for z in zs]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def export_one(glb):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    # единицу сцены менять только после импорта: импортёр glTF сам делит размеры на неё
    bpy.context.scene.unit_settings.scale_length = 0.01
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    roots = [o for o in meshes if o.parent is None]
    assert len(roots) == 1 and all(o.type == "MESH" for o in bpy.context.scene.objects), [o.name for o in bpy.context.scene.objects]
    root = roots[0]
    assert root.matrix_world == Matrix.Identity(4), root.matrix_world

    # дети: положение в вершины, затем слить с корнем
    for ob in meshes:
        if ob is not root:
            mw = ob.matrix_world.copy()
            ob.parent = None
            ob.data.transform(mw)
            ob.matrix_world = Matrix.Identity(4)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in meshes:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    if len(meshes) > 1:
        bpy.ops.object.join()

    name = "SM_" + root.name
    root.name = name
    root.data.name = name
    root.data.transform(Matrix.Scale(100.0, 4))   # метры -> сантиметры
    if root.data.uv_layers:
        root.data.uv_layers[0].name = "UVMap"
    cache = {}
    for i, slot in enumerate(root.data.materials):
        root.data.materials[i] = temp_material(slot.name, cache)

    pts = [v.co for v in root.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    ucx = collision_box(f"UCX_{name}_00", lo, hi)

    tri = root.modifiers.new("ExportTriangulate", "TRIANGULATE")
    if hasattr(tri, "keep_custom_normals"):
        tri.keep_custom_normals = True

    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    ucx.select_set(True)
    bpy.context.view_layer.objects.active = root
    path = os.path.join(OUT, name + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=False,
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_triangles=False,
        use_tspace=False,
        use_custom_props=False,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="STRIP",
        embed_textures=False,
        colors_type="NONE",
    )
    size = hi - lo
    print(f"fbx {name}.fbx tris~{sum(len(p.vertices) - 2 for p in root.data.polygons)} "
          f"size_cm {size.x:.1f} x {size.y:.1f} x {size.z:.1f} lo {tuple(round(c, 1) for c in lo)} "
          f"materials {[m.name for m in root.data.materials]}")


def main():
    textures()
    files = sorted(glob.glob(os.path.join(SRC, "*.glb")))
    assert len(files) == 13, len(files)
    for glb in files:
        export_one(glb)


main()
