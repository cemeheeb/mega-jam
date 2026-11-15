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
Наборы мебели (dining-set, cargo-crates, medbay-kit; 15.11, вторая партия) — несколько предметов в ряд одной
моделью: таблица parts режет их по островам, у каждого предмета свой размер, поворот, привязка и коллизия UCX;
drop убирает лишние острова (Tripo поставил у стола две фигурки людей). Ядро двигателя получает патрубки
в четыре стороны (Tripo сделал в две) и карту свечения по бирюзовым пикселям цвета.
Импорт в Unreal — tools/ue/import_props.py.
"""
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "SourceArt")

# карточка: имя меша, размер (м) — число (по наибольшей стороне), ("z", высота) или (x, y, z) по осям,
# привязка bottom / center, шероховатость и металл для ORM, коллизия-коробка.
# pose: "back" — положить на спину лицом вверх (манометр стоял на штуцере); "upright" — длинную ось поставить
# вертикально, тяжёлым концом вниз (разводной ключ стоял наискосок: в руке он висит за конец рукояти,
# на пол его кладёт поза из таблицы моделей в RunItem.cpp)
def item(name, size, rough, metal, **more):
    return dict(name=name, size=size, pivot="bottom", rough=rough, metal=metal, **more)


def part(name, seed, size, **more):
    return dict(name=name, seed=seed, size=size, **more)


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
    # ---- вторая партия (15.11): мебель комнат вместо серых коробок build_rooms.py ----
    # ядро: от пола до потолка 3,0 м, пропорции Tripo (основание 2,27 м); коллизия — призма по основанию
    "environment/engine/warp-core": dict(name="WarpCore", size=("z", 3.0), pivot="bottom", rough=0.45, metal=0.2,
                                         fix="stubs4", ucx=("prism", 12), emissive="teal"),
    # унитаз: глубина 73 см, как у заглушки с бачком (55 + 18); высота и ширина — по пропорциям Tripo
    "environment/living/space-toilet": dict(name="SpaceToilet", size=("y", 0.73), pivot="bottom", rough=0.4, metal=0.1,
                                            ucx=True, emissive="teal"),
    # parts: имя меша, точка предмета в сырых осях Tripo (к ней относятся острова сетки), размер в игре.
    # turn — поворот вокруг Z после выравнивания (длинная сторона стола у Tripo вдоль Y, в комнате — вдоль X);
    # ucx: True — коробка по габариту, "tall" — коробка на каждую высокую створку; straight=False — не выравнивать
    "environment/common/dining-set": dict(
        material="DiningSet", rough=0.55, metal=0.1, drop=[((-0.47, -0.35), (0.235, 0.345))],      # две фигурки людей
        parts=[part("MessTable", (-0.40, -0.03), (2.0, 0.8, 0.78), turn=90, ucx=True),
               part("MessBench", (-0.045, -0.04), (2.0, 0.30, 0.45), turn=90, ucx=True),
               part("CrewTable", (0.245, -0.01), (1.2, 0.8, 0.78), turn=90, ucx=True),
               part("Stool", (0.445, -0.01), (0.36, 0.36, 0.45), ucx=True)]),
    "environment/cargo/cargo-crates": dict(
        material="CargoCrates", rough=0.5, metal=0.4,
        parts=[part("CrateLarge", (-0.37, 0.0), (1.2, 1.2, 1.2), ucx=True),
               part("CrateMedium", (-0.025, 0.0), (1.0, 1.0, 1.0), ucx=True),
               part("CrateSmall", (0.23, 0.0), (0.8, 0.8, 0.8), ucx=True),
               part("Barrel", (0.425, 0.0), (0.64, 0.64, 0.90), ucx=True)]),
    # лампа висит на потолке: привязка — верх её крепления; ширма стоит зигзагом, как у Tripo
    "environment/medbay/medbay-kit": dict(
        material="MedbayKit", rough=0.5, metal=0.2,
        parts=[part("SurgicalLamp", (-0.25, -0.30), ("z", 1.0), pivot="top", straight=False),
               part("PrivacyScreen", (-0.24, 0.22), ("z", 1.70), ucx="tall", straight=False),
               part("InstrumentTrolley", (0.17, 0.28), ("z", 0.85), ucx=True),
               part("BiohazardBin", (0.43, 0.30), ("z", 0.65), ucx=True)]),
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
    if a.get("emissive") == "teal":
        # светится бирюзовое: стекло колонны ядра, индикаторы. Остальное — чёрное; сила — EmissiveStrength в Unreal
        rgb = px.reshape(-1, 4)
        teal = (rgb[:, 1] - rgb[:, 0] > 0.10) & (rgb[:, 2] - rgb[:, 0] > 0.08) & (np.maximum(rgb[:, 1], rgb[:, 2]) > 0.30)
        glow = np.zeros_like(rgb)
        glow[:, 3] = 1.0
        glow[teal, :3] = rgb[teal, :3]
        em = bpy.data.images.new("emissive", w, h, alpha=False, is_data=True)
        em.pixels.foreach_set(glow.ravel())
        em.filepath_raw = os.path.join(out, f"T_{mat}_Emissive.png")
        em.file_format = "PNG"
        em.save()
        print(f"   свечение: {teal.mean() * 100:.1f}% пикселей")
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


def split_by_seeds(ob, seeds, drop=()):
    """Острова сетки — к ближайшей из точек seeds (x, y); на каждую точку свой объект. Острова, чья середина
    попала в прямоугольник из drop ((x0, x1), (y0, y1)), выбрасываются."""
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
        if any(x0 <= cx <= x1 and y0 <= cy <= y1 for (x0, x1), (y0, y1) in drop):
            print(f"   выброшен остров: {len(verts)} вершин у ({cx:.2f}, {cy:.2f})")
            group.append(-1)
            continue
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


def coords(me):
    pts = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", pts)
    return pts.reshape(-1, 3).astype(np.float64)


def straighten(me):
    """Tripo ставит предметы чуть наискосок: повернуть вокруг Z так, чтобы габарит в плане стал наименьшим."""
    pts = coords(me)[:, :2]
    pts = pts - (pts.min(axis=0) + pts.max(axis=0)) / 2

    def area(deg):
        c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
        x, y = pts[:, 0] * c - pts[:, 1] * s, pts[:, 0] * s + pts[:, 1] * c
        return (x.max() - x.min()) * (y.max() - y.min())

    best = min(np.arange(-45.0, 45.01, 0.25), key=area)
    if area(best) > area(0.0) * 0.99:
        return 0.0                       # круглое или уже ровное
    lo, hi = bounds(me)
    c = (lo + hi) / 2
    me.transform(Matrix.Translation((c.x, c.y, 0)) @ Matrix.Rotation(np.radians(best), 4, "Z") @ Matrix.Translation((-c.x, -c.y, 0)))
    return float(best)


def scale_to(me, size):
    """size: число — по наибольшей стороне; ("z" | "y", длина) — по одной оси, пропорции прежние; (x, y, z) — по осям."""
    lo, hi = bounds(me)
    d = hi - lo
    if isinstance(size, tuple) and size[0] in ("y", "z"):
        s = Vector((size[1] / (d.z if size[0] == "z" else d.y),) * 3)
    elif isinstance(size, tuple):
        s = Vector((size[0] / d.x, size[1] / d.y, size[2] / d.z))
    else:
        s = Vector((size / max(d),) * 3)
    me.transform(Matrix.Diagonal((s.x, s.y, s.z, 1.0)))
    return s


def islands_of(me):
    """Острова сетки: списки номеров вершин."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    seen, out = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, verts = [v], []
        seen.add(v.index)
        while stack:
            u = stack.pop()
            verts.append(u.index)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        out.append(verts)
    bm.free()
    return out


def stubs_four_ways(me):
    """Ядро: Tripo поставил патрубки на хомутах в две стороны, по карточке их четыре. Острова-патрубки
    (небольшие, далеко от оси) копируются с поворотом на 90° вокруг оси колонны."""
    pts = coords(me)
    stubs = [vs for vs in islands_of(me) if 40 <= len(vs) <= 200 and np.hypot(*pts[vs, :2].mean(axis=0)) > 0.25]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    for vs in stubs:
        chosen = set(vs)
        geom = [bm.verts[i] for i in vs] + [f for f in bm.faces if all(v.index in chosen for v in f.verts)]
        new = bmesh.ops.duplicate(bm, geom=geom)["geom"]
        bmesh.ops.rotate(bm, verts=[g for g in new if isinstance(g, bmesh.types.BMVert)], cent=(0, 0, 0),
                         matrix=Matrix.Rotation(np.pi / 2, 3, "Z"))
        bm.verts.ensure_lookup_table()
    bm.to_mesh(me)
    bm.free()
    print(f"   патрубки: было {len(stubs)}, стало {len(stubs) * 2}")


def prism(name, radius, z0, z1, sides):
    """Выпуклая призма вокруг оси Z — коллизия круглого предмета."""
    ring = [(radius * np.cos(2 * np.pi * k / sides), radius * np.sin(2 * np.pi * k / sides)) for k in range(sides)]
    verts = [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
    faces = [(k, (k + 1) % sides, sides + (k + 1) % sides, sides + k) for k in range(sides)]
    faces += [tuple(range(sides - 1, -1, -1)), tuple(range(sides, 2 * sides))]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def collision(o, kind):
    """Объекты коллизии UCX для меша o (в метрах, как сам меш)."""
    if not kind:
        return []
    lo, hi = bounds(o.data)
    if kind is True:
        return [box(f"UCX_{o.name}_00", lo, hi)]
    if kind == "tall":
        # ширма: коробка на каждую створку — остров высотой больше половины предмета; не тоньше 4 см
        pts = coords(o.data)
        out = []
        for vs in islands_of(o.data):
            a, b = pts[vs].min(axis=0), pts[vs].max(axis=0)
            if b[2] - a[2] < 0.5 * (hi.z - lo.z):
                continue
            for i in (0, 1):
                if b[i] - a[i] < 0.04:
                    m = (a[i] + b[i]) / 2
                    a[i], b[i] = m - 0.02, m + 0.02
            out.append(box(f"UCX_{o.name}_{len(out):02d}", Vector(a), Vector(b)))
        return out
    if kind[0] == "prism":
        return [prism(f"UCX_{o.name}_00", min(hi.x - lo.x, hi.y - lo.y) / 2, lo.z, hi.z, kind[1])]
    raise ValueError(kind)


def top_at_centre(me):
    """Высота верхней поверхности над точкой привязки (столешница, полка): луч сверху вниз по оси Z."""
    tree = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    hit = tree.ray_cast(Vector((0, 0, 100)), Vector((0, 0, -1)))
    return hit[0].z if hit[0] is not None else float("nan")


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
    mat_name = a.get("material") or a["name"]
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
        pts = coords(ob.data)
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
    if a.get("fix") == "stubs4":
        stubs_four_ways(ob.data)

    if "parts" in a:
        # набор: у каждого предмета своё выравнивание, поворот и размер
        specs = a["parts"]
        objs = split_by_seeds(ob, [sp["seed"] for sp in specs], a.get("drop", ()))
        for o, sp in zip(objs, specs):
            o.name = o.data.name = "SM_" + sp["name"]
            angle = straighten(o.data) if sp.get("straight", True) else 0.0
            if sp.get("turn"):
                lo, hi = bounds(o.data)
                c = (lo + hi) / 2
                o.data.transform(Matrix.Translation((c.x, c.y, 0)) @ Matrix.Rotation(np.radians(sp["turn"]), 4, "Z")
                                 @ Matrix.Translation((-c.x, -c.y, 0)))
            lo, hi = bounds(o.data)
            d = hi - lo
            k = scale_to(o.data, sp["size"])
            print(f"   {o.name}: выровнен на {angle:+.2f}°, у Tripo {d.x:.3f} x {d.y:.3f} x {d.z:.3f}, "
                  f"растяжение {k.x / k.z:.2f} x {k.y / k.z:.2f} x 1")
    else:
        # размер
        s = scale_to(ob.data, a["size"])
        if "split" in a:
            seeds = [(x * s.x, y * s.y) for x, y in a["split"]]
            objs = split_by_seeds(ob, seeds)
            for k, o in enumerate(objs):
                o.name = o.data.name = f"SM_{a['name']}{k + 1}"
        else:
            ob.name = ob.data.name = "SM_" + a["name"]
            objs = [ob]
        specs = [a] * len(objs)

    for o, sp in zip(objs, specs):
        before = tris_of(o)
        if a.get("max_tris") and before > a["max_tris"]:
            mod = o.modifiers.new("Decimate", "DECIMATE")
            mod.ratio = a["max_tris"] / before
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier=mod.name)
        lo, hi = bounds(o.data)
        c = (lo + hi) / 2
        pivot = sp.get("pivot") or a.get("pivot", "bottom")
        if pivot == "top":
            # висит на потолке: привязка — середина верхней площадки крепления
            pts = coords(o.data)
            top = pts[pts[:, 2] > hi.z - 0.03 * (hi.z - lo.z)]
            m = (top.min(axis=0) + top.max(axis=0)) / 2
            o.data.transform(Matrix.Translation((-m[0], -m[1], -hi.z)))
            pts = coords(o.data)
            low = pts[pts[:, 2] < pts[:, 2].min() + 0.35 * (hi.z - lo.z)]
            lc = (low.min(axis=0) + low.max(axis=0)) / 2
            print(f"   {o.name}: нижняя треть (плафон) — середина ({lc[0] * 100:.1f}, {lc[1] * 100:.1f}) см от привязки, "
                  f"поперечник {(low.max(axis=0) - low.min(axis=0))[:2].max() * 100:.1f} см")
        else:
            o.data.transform(Matrix.Translation((-c.x, -c.y, -lo.z if pivot == "bottom" else -c.z)))
        lo, hi = bounds(o.data)
        d = hi - lo
        print(f"   {o.name}: {d.x * 100:.1f} x {d.y * 100:.1f} x {d.z * 100:.1f} см, низ {lo.z * 100:.1f}, "
              f"верх над привязкой {top_at_centre(o.data) * 100:.1f}, треугольников {before} -> {tris_of(o)}")

    # миниатюра: предметы набора разложены в ряд, только на время кадра
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
    for o, sp in zip(objs, specs):
        ucx = collision(o, sp.get("ucx"))
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
        if ucx:
            print(f"   {o.name}: коллизия — {len(ucx)} шт.")
    print(f"## {card}: {len(objs)} FBX, текстура {width} px, слот MI_{mat_name}")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for card in ASSETS:
        if not args or card.split("/")[-1] in args:
            process(card)


main()
