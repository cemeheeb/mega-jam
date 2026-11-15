"""Модели Tripo автора для заглушек игры (15.11): размер, точка привязки, текстуры и FBX для Unreal.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python tools/blender/props/tripo_props.py -- [имя карточки ...]

Без имён обрабатывает все карточки из таблицы ASSETS. Лёгкий путь без ремоделинга (как у сгоревших колонок):
меш Tripo source/tripo/<карточка>.fbx приходит в кубе 1 × 1 × 1 м, осью Z вверх, лицом в −Y; здесь он получает
игровой размер и точку привязки и выгружается по pipeline/unreal.md (сантиметры, лицо в Unreal — +Y).
В папку карточки пишет:
  SM_<Имя>.fbx                слот MI_<Материал>; у створки шлюза — коробка коллизии UCX
  T_<Материал>_BaseColor.png  цвет Tripo как есть
  T_<Материал>_ORM.png        ровный 4 × 4: Tripo даёт только цвет, шероховатость и металл — числом на весь предмет
  source/<карточка>.blend     сцена в метрах с текстурой
  preview.png                 миниатюра для Студии
Грибы (fungus-clusters) — один меш из пяти кучек: режется на SM_Fungus1–5 по островам сетки, каждая кучка
упрощается до 2 тыс. треугольников (в комнате их десятки) и встаёт центром дна в ноль.
Импорт в Unreal — tools/ue/import_props.py.
"""
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "SourceArt")

# карточка: имя меша, размер (м) — число (по наибольшей стороне), ("z", высота) или (x, y, z) по осям,
# привязка bottom / center, шероховатость и металл для ORM, коллизия-коробка.
# pose: "back" — положить на спину лицом вверх (манометр стоял на штуцере); "upright" — длинную ось поставить
# вертикально, тяжёлым концом вниз (разводной ключ стоял наискосок: в руке он висит за конец рукояти,
# на пол его кладёт поза из таблицы моделей в RunItem.cpp)
def item(name, size, rough, metal, **more):
    return dict(name=name, size=size, pivot="bottom", rough=rough, metal=metal, **more)


ASSETS = {
    "items/sealant-can": item("SealantCan", ("z", 0.22), 0.5, 0.3),
    "items/voice-recorder": item("VoiceRecorder", ("z", 0.12), 0.55, 0.2),
    "items/rubber-duck": item("RubberDuck", 0.09, 0.6, 0.0),
    "items/ration-tin": item("RationTin", 0.14, 0.4, 0.6),
    "items/pressure-gauge": item("PressureGauge", 0.11, 0.4, 0.5, pose="back"),
    "items/power-cell": item("PowerCell", ("z", 0.24), 0.5, 0.2),
    "items/pipe-wrench": item("PipeWrench", 0.45, 0.5, 0.6, pose="upright"),
    "items/duct-tape": item("DuctTape", 0.11, 0.75, 0.0),
    "items/paper-note": item("PaperNote", 0.15, 0.9, 0.0),
    "items/gyroscope": item("Gyroscope", 0.14, 0.35, 0.7),
    "items/fuse": item("Fuse", 0.16, 0.5, 0.2),
    "items/family-photo": item("FamilyPhoto", 0.15, 0.45, 0.3),
    "items/dog-tag": item("DogTag", 0.13, 0.35, 0.8),
    "items/data-cartridge": item("DataCartridge", 0.15, 0.6, 0.0),
    "items/coolant-valve": dict(name="CoolantValve", size=0.11, pivot="bottom", rough=0.45, metal=0.5),
    "items/circuit-board": dict(name="CircuitBoard", size=0.16, pivot="bottom", rough=0.6, metal=0.0),
    "environment/common/space-suit-helmet": dict(name="SpaceSuitHelmet", size=0.37, pivot="center", rough=0.4, metal=0.0),
    "environment/common/space-suit": dict(name="SpaceSuit", size=("z", 1.9), pivot="bottom", rough=0.6, metal=0.0),
    "characters/maintenance-robot": dict(name="MaintenanceRobot", size=("z", 1.3), pivot="bottom", rough=0.55, metal=0.2),
    # створка: 150 × 225 см, как коробка-заглушка; толщина 12 см (у заглушки 10)
    "environment/common/airlock-door": dict(name="AirlockDoor", size=(1.5, 0.12, 2.25), pivot="center", rough=0.5, metal=0.1, ucx=True),
    # набор шириной 1 м: самые высокие грибы около 36 см
    "environment/common/fungus-clusters": dict(name="Fungus", material="FungusClusters", size=1.0, pivot="bottom", rough=0.75, metal=0.0,
                                               split=[(0.30, -0.30), (0.0, 0.30), (0.33, 0.30), (-0.35, 0.30), (-0.20, -0.27)],
                                               max_tris=2000),
}


def bounds(me):
    pts = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", pts)
    pts = pts.reshape(-1, 3)
    return Vector(pts.min(axis=0)), Vector(pts.max(axis=0))


def write_textures(card, mat):
    out = os.path.join(ROOT, card)
    stem = card.split("/")[-1]
    src = bpy.data.images.load(os.path.join(out, "source", "tripo", stem + ".fbm", stem + "_basecolor.jpg"))
    src.colorspace_settings.name = "Non-Color"      # значения как в файле
    w, h = src.size
    px = np.empty(w * h * 4, np.float32)
    src.pixels.foreach_get(px)
    im = bpy.data.images.new("base", w, h, alpha=False, is_data=True)
    im.pixels.foreach_set(px)
    im.filepath_raw = os.path.join(out, f"T_{mat}_BaseColor.png")
    im.file_format = "PNG"
    im.save()
    a = ASSETS[card]
    orm = bpy.data.images.new("orm", 4, 4, alpha=False, is_data=True)
    orm.pixels.foreach_set(np.tile(np.array([1.0, a["rough"], a["metal"], 1.0], np.float32), 16))
    orm.filepath_raw = os.path.join(out, f"T_{mat}_ORM.png")
    orm.file_format = "PNG"
    orm.save()
    return w


def material(card, mat):
    m = bpy.data.materials.new("MI_" + mat)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(ROOT, card, f"T_{mat}_BaseColor.png"))
    m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = ASSETS[card]["rough"]
    bsdf.inputs["Metallic"].default_value = ASSETS[card]["metal"]
    return m


def split_by_seeds(ob, seeds):
    """Острова сетки — к ближайшей из точек seeds (x, y); на каждую точку свой объект."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    owner = [-1] * len(bm.verts)
    islands = []
    for v in bm.verts:
        if owner[v.index] != -1:
            continue
        idx = len(islands)
        stack, verts = [v], []
        owner[v.index] = idx
        while stack:
            u = stack.pop()
            verts.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if owner[w.index] == -1:
                    owner[w.index] = idx
                    stack.append(w)
        islands.append(verts)
    group = []
    for verts in islands:
        cx = sum(v.co.x for v in verts) / len(verts)
        cy = sum(v.co.y for v in verts) / len(verts)
        group.append(min(range(len(seeds)), key=lambda k: (cx - seeds[k][0]) ** 2 + (cy - seeds[k][1]) ** 2))
    parts = []
    for k in range(len(seeds)):
        part = bm.copy()
        part.verts.ensure_lookup_table()
        bmesh.ops.delete(part, geom=[part.verts[i] for i in range(len(part.verts)) if group[owner[i]] != k], context="VERTS")
        me = bpy.data.meshes.new(f"part{k}")
        part.to_mesh(me)
        part.free()
        o = bpy.data.objects.new(f"part{k}", me)
        bpy.context.scene.collection.objects.link(o)
        for m in ob.data.materials:
            me.materials.append(m)
        parts.append(o)
    bm.free()
    bpy.data.objects.remove(ob, do_unlink=True)
    return parts


def box(name, lo, hi):
    xs, ys, zs = (lo.x, hi.x), (lo.y, hi.y), (lo.z, hi.z)
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x in xs for y in ys for z in zs], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def tris_of(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def preview(card, objs):
    scene = bpy.context.scene
    lo = Vector([min(bounds(o.data)[0][i] + o.location[i] for o in objs) for i in range(3)])
    hi = Vector([max(bounds(o.data)[1][i] + o.location[i] for o in objs) for i in range(3)])
    d = hi - lo
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = scene.render.resolution_y = 512
    cam_data = bpy.data.cameras.new("preview")
    cam = bpy.data.objects.new("preview", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(d) * 1.3
    c = (lo + hi) / 2
    direction = Vector((0.6, -1.0, 0.45)).normalized()
    cam.location = c + direction * max(d) * 4
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(ROOT, card, "preview.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)


def process(card):
    a = ASSETS[card]
    out = os.path.join(ROOT, card)
    stem = card.split("/")[-1]
    mat_name = a.get("material", a["name"])
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.import_scene.fbx(filepath=os.path.join(out, "source", "tripo", stem + ".fbx"))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(meshes) == 1, [o.name for o in meshes]
    ob = meshes[0]
    ob.data.transform(ob.matrix_world)            # у FBX из Tripo поворот на 90° лежит на объекте
    ob.matrix_world = Matrix.Identity(4)
    width = write_textures(card, mat_name)
    mat = material(card, mat_name)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
    ob.data.uv_layers[0].name = "UVMap"

    # поза
    if a.get("pose") == "back":
        ob.data.transform(Matrix.Rotation(-np.pi / 2, 4, "X"))       # лицо (−Y) смотрит вверх
    elif a.get("pose") == "upright":
        # главные оси облака вершин: самая длинная встаёт вертикально, самая тонкая — вдоль Y (ключ лежал
        # наискосок и был чуть повёрнут вокруг себя); тяжёлый конец, где вершин больше, — вниз
        pts = np.empty(len(ob.data.vertices) * 3, np.float32)
        ob.data.vertices.foreach_get("co", pts)
        pts = pts.reshape(-1, 3).astype(np.float64)
        c = pts.mean(axis=0)
        w, v = np.linalg.eigh(np.cov((pts - c).T))            # по возрастанию: тонкая, средняя, длинная
        thin, long_ = v[:, 0], v[:, 2]
        t = (pts - c) @ long_
        if np.sum(t > 0) > np.sum(t < 0):                     # больше вершин на положительном конце — там головка
            long_ = -long_                                    # ось смотрит от головки к концу рукояти
        mid = np.cross(thin, long_)                           # правая тройка: X = средняя, Y = тонкая, Z = длинная
        rot = Matrix((tuple(mid), tuple(thin), tuple(long_))).to_4x4()
        ob.data.transform(Matrix.Translation(Vector(-c)))
        ob.data.transform(rot)
        print(f"   поза upright: длинная ось была {tuple(round(float(x), 2) for x in long_)}")

    # размер
    lo, hi = bounds(ob.data)
    d = hi - lo
    size = a["size"]
    if isinstance(size, tuple) and size[0] == "z":
        s = Vector((size[1] / d.z,) * 3)
    elif isinstance(size, tuple):
        s = Vector((size[0] / d.x, size[1] / d.y, size[2] / d.z))
    else:
        s = Vector((size / max(d),) * 3)
    ob.data.transform(Matrix.Diagonal((s.x, s.y, s.z, 1.0)))

    if "split" in a:
        seeds = [(x * s.x, y * s.y) for x, y in a["split"]]
        objs = split_by_seeds(ob, seeds)
        for k, o in enumerate(objs):
            o.name = o.data.name = f"SM_{a['name']}{k + 1}"
    else:
        ob.name = ob.data.name = "SM_" + a["name"]
        objs = [ob]

    for o in objs:
        before = tris_of(o)
        if a.get("max_tris") and before > a["max_tris"]:
            mod = o.modifiers.new("Decimate", "DECIMATE")
            mod.ratio = a["max_tris"] / before
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier=mod.name)
        lo, hi = bounds(o.data)
        c = (lo + hi) / 2
        o.data.transform(Matrix.Translation((-c.x, -c.y, -lo.z if a["pivot"] == "bottom" else -c.z)))
        lo, hi = bounds(o.data)
        d = hi - lo
        print(f"   {o.name}: {d.x * 100:.1f} x {d.y * 100:.1f} x {d.z * 100:.1f} см, низ {lo.z * 100:.1f}, треугольников {before} -> {tris_of(o)}")

    # миниатюра: кучки грибов разложены в ряд, только на время кадра
    if len(objs) > 1:
        x = 0.0
        for o in objs:
            lo, hi = bounds(o.data)
            o.location.x = x - lo.x
            x += (hi.x - lo.x) + 0.05
    preview(card, objs)
    for o in objs:
        o.location = (0, 0, 0)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "source", stem + ".blend"), copy=True)

    # выгрузка: сантиметры, как у остальных наборов (pipeline/unreal.md)
    bpy.context.scene.unit_settings.scale_length = 0.01
    for o in objs:
        ucx = []
        if a.get("ucx"):
            lo, hi = bounds(o.data)
            ucx = [box(f"UCX_{o.name}_00", lo, hi)]
        for e in [o] + ucx:
            e.data.transform(Matrix.Scale(100.0, 4))
        tri = o.modifiers.new("ExportTriangulate", "TRIANGULATE")
        tri.keep_custom_normals = True
        bpy.ops.object.select_all(action="DESELECT")
        for e in [o] + ucx:
            e.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.export_scene.fbx(
            filepath=os.path.join(out, f"{o.name}.fbx"),
            use_selection=True, object_types={"MESH"},
            apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
            axis_forward="-Z", axis_up="Y", bake_space_transform=False,
            use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False, use_tspace=False,
            use_custom_props=False, add_leaf_bones=False, bake_anim=False,
            path_mode="STRIP", embed_textures=False, colors_type="NONE",
        )
    print(f"## {card}: {len(objs)} FBX, текстура {width} px, слот MI_{mat_name}")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for card in ASSETS:
        if not args or card.split("/")[-1] in args:
            process(card)


main()
