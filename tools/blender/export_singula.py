"""Наборы реквизита из Singula: копия glb и текстур как есть, FBX и текстуры для Unreal (pipeline/unreal.md).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python tools/blender/export_singula.py [-- набор ...]

Без аргументов выгружаются все наборы из SETS. Набор — путь от Singula/environment, например common/lamps.
Колонки стены (common/wall-columns) выгружает свой скрипт в их папке.

На набор:
- glb и текстуры верхнего уровня копируются без изменений в SourceArt/environment/<набор>/source/singula/
  (в Singula ничего не меняется, только копируется);
- каждый glb — один меш SM_<корень>.fbx: дети (крышки, рычаги, кнопки) слиты с корнем, движущихся частей
  в игре нет; начало координат — как у корня в glb;
- меш сразу в сантиметрах (единица сцены 0,01 м после импорта): импорт MCP идёт через FbxFactory без перевода единиц;
- у всех мешей набора один слот MI_<Набор> (в glb у набора один материал);
- коллизия — коробка UCX_<меш>_00 по габаритам; последним в стек — Triangulate с заданными нормалями;
- текстуры: <набор>_base/orm/nor/emission.png -> T_<Набор>_BaseColor/ORM/Normal/Emissive.png.
  Нормали в Singula выгружены для OpenGL (пресет godot ArmorPaint): в Unreal у T_*_Normal включается flip green.
Оси Blender: лицо в −Y, в Unreal оно смотрит в +Y (FBX -Z/Y, как у колонок).
"""

import glob
import os
import shutil
import struct
import sys

import bpy
from mathutils import Matrix, Vector

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SINGULA = "/Users/cemeheeb/Projects/Singula/environment"
DEST = os.path.join(PROJECT, "SourceArt", "environment")

# набор -> glb, которые берутся (None — все). Кабина и кнопки лифта не нужны: лифтов в игре нет.
SETS = {
    "common/safety-equipment": None,
    "common/lamps": None,
    "common/ventilation": None,
    "common/flexible-duct": None,
    "common/handrails": None,
    "common/door-hatch-controls": ["door-button.glb", "hatch-wheel.glb"],
    "bridge/acceleration-couch": None,
    "bridge/command-console-parts": None,
    "bridge/control-console-parts": None,
    "bridge/crew-items": None,
    "welding-gun": None,
}
MAPS = (("base", "BaseColor"), ("orm", "ORM"), ("nor", "Normal"), ("emission", "Emissive"))


def camel(set_path):
    return "".join(w.capitalize() for w in os.path.basename(set_path).split("-"))


def copy_sources(set_path, files):
    src = os.path.join(SINGULA, set_path)
    dst = os.path.join(DEST, set_path, "source", "singula")
    os.makedirs(dst, exist_ok=True)
    for f in files + sorted(glob.glob(os.path.join(src, "*.png"))):
        shutil.copyfile(os.path.join(src, os.path.basename(f)), os.path.join(dst, os.path.basename(f)))
    return dst


def textures(set_path, singula_dir):
    out = os.path.join(DEST, set_path)
    prefix = os.path.basename(set_path)
    made = []
    for key, suffix in MAPS:
        path = os.path.join(singula_dir, f"{prefix}_{key}.png")
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            head = f.read(26)
        w, h, depth, colour = struct.unpack(">IIBB", head[16:26])
        assert depth == 8 and colour in (2, 6), (path, depth, colour)
        name = f"T_{camel(set_path)}_{suffix}.png"
        shutil.copyfile(path, os.path.join(out, name))
        made.append(f"{name} {w}x{h}")
    print("textures", set_path, made)


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


def export_one(glb, out_dir, slot):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    # единицу сцены менять только после импорта: импортёр glTF сам делит размеры на неё
    bpy.context.scene.unit_settings.scale_length = 0.01
    obs = list(bpy.context.scene.objects)
    meshes = [o for o in obs if o.type == "MESH"]
    roots = [o for o in obs if o.parent is None]
    # корень — меш или пустышка с деталями (книга: обложки, листы, кольца)
    assert len(roots) == 1 and all(o.type in ("MESH", "EMPTY") for o in obs), [(o.name, o.type) for o in obs]
    top = roots[0]
    root_name = top.name
    root_mw = top.matrix_world.copy()
    for ob in meshes:
        mw = ob.matrix_world.copy()
        ob.parent = None
        ob.data.transform(mw)
        ob.matrix_world = Matrix.Identity(4)
    root = top if top.type == "MESH" else meshes[0]
    bpy.ops.object.select_all(action="DESELECT")
    for ob in meshes:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    if len(meshes) > 1:
        bpy.ops.object.join()
    # начало координат — как у корня: вернуть его поворот и сдвиг в объект, если они были
    if root_mw != Matrix.Identity(4):
        root.data.transform(root_mw.inverted())

    name = "SM_" + root_name
    root.name = name
    root.data.name = name
    root.data.transform(Matrix.Scale(100.0, 4))   # метры -> сантиметры
    if root.data.uv_layers:
        root.data.uv_layers[0].name = "UVMap"
    mat = bpy.data.materials.new(slot)
    root.data.materials.clear()
    root.data.materials.append(mat)
    for p in root.data.polygons:
        p.material_index = 0

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
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(out_dir, name + ".fbx"),
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False, use_tspace=False,
        use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False, colors_type="NONE",
    )
    size = hi - lo
    print(f"  {name}.fbx tris~{sum(len(p.vertices) - 2 for p in root.data.polygons)} "
          f"size_cm {size.x:.1f} x {size.y:.1f} x {size.z:.1f} lo {tuple(round(c, 1) for c in lo)}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for set_path in (argv or list(SETS)):
        wanted = SETS[set_path]
        src = os.path.join(SINGULA, set_path)
        files = sorted(glob.glob(os.path.join(src, "*.glb")))
        if wanted is not None:
            files = [f for f in files if os.path.basename(f) in wanted]
            assert len(files) == len(wanted), (set_path, files)
        out = os.path.join(DEST, set_path)
        os.makedirs(out, exist_ok=True)
        singula_dir = copy_sources(set_path, files)
        textures(set_path, singula_dir)
        print("set", set_path, len(files), "glb")
        for glb in files:
            export_one(os.path.join(singula_dir, os.path.basename(glb)), out, f"MI_{camel(set_path)}")


main()
