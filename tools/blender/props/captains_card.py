"""Карта капитана (items/captains-card, 15.11): модель из примитивов по картинке автора, текстуры и FBX для Unreal.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python tools/blender/props/captains_card.py [-- <папка для проверочных рендеров>]

Меша Tripo нет: автор дал картинку (images/captains-card-1.webp) и попросил сгенерировать ассет в Blender, а
генераторов у Blender MCP не было (15.11). Карта простая, поэтому собрана скриптом, как ремоделинг наборов, а
текстуры нарисованы здесь же, без ArmorPaint: ровные цвета зон, рельеф эмблемы и чипа — карта высот в нормали,
износ — текстурами Singula (common/fine-scratches, common/weathering), без шума (pipeline/kit.md, «Маска потёртостей»).

Размер по карточке: 10 × 6 × 0,5 см (крупнее настоящей, чтобы читалась с третьего лица). Оси Blender: карта лежит
лицом вверх, длинная сторона по X, оранжевый конец в −X, отверстие с кольцом в углу +X +Y, светящаяся полоса —
на длинном торце −Y (у картинки: ближний торец справа). Начало — середина дна корпуса. Кольцо проходит в отверстие
наискось и под углом карты уходит ниже дна на 2 мм: в игре это скрыто под самой картой.

В папку карточки пишет:
  SM_CaptainsCard.fbx                         сантиметры, слот MI_CaptainsCard, без коллизии (вещи без неё)
  T_CaptainsCard_BaseColor.png / _ORM.png / _Normal.png (DirectX) / _Emissive.png    1024 × 1024
  source/captains-card.blend                  сцена в метрах с материалом
  source/captains-card_nor_gl.png             нормали OpenGL для материала в Blender
  preview.png                                 миниатюра для Студии
Импорт в Unreal — tools/ue/import_props.py captains-card (свечение полосы — GLOW там же).
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "SourceArt")
CARD = "items/captains-card"
STEM = "captains-card"
NAME = "CaptainsCard"
OUT = os.path.join(ROOT, CARD)

# ---- размеры, мм ----
L, W, T, R = 100.0, 60.0, 5.0, 6.0          # карта и радиус углов
BEVEL = 0.8                                  # фаска рёбер лица и дна
RIM = 1.2                                    # графитовая кромка по краю лица (белая пластина утоплена в рамку)
HX, HY = L / 2 - 7.0, W / 2 - 7.0           # отверстие под кольцо
HOLE_R = 2.95
# люверс: замкнутый профиль (r, z) вокруг оси отверстия: трубка в отверстии и бортик на лице
GROMMET = [(2.3, 0.1), (2.9, 0.1), (2.9, T), (4.15, T), (4.15, T + 0.15), (3.9, T + 0.45), (2.6, T + 0.45), (2.3, T + 0.25)]
RING_R, RING_WIRE, RING_TILT = 7.0, 0.7, math.radians(25)    # кольцо: радиус, проволока, наклон проволоки в отверстии
RING_LEAN = math.radians(35)                 # кольцо завалено вбок вокруг проволоки в отверстии: сверху читается кольцом
STRIP = (8.0, 42.0)                          # светящаяся полоса на торце −Y: от x до x, высота 1,1 мм посередине
ORANGE_X = -21.0                             # оранжевый конец: от края до этой линии
CHIP = (-9.0, 1.5, 13.0, 10.0, 1.6)          # чип: центр, размер, радиус углов
EMBLEM_X = 22.0                              # эмблема: звезда над тремя шевронами
STAR = (EMBLEM_X, 17.0, 4.6, 1.9)
CHEVRONS = [9.0, 2.0, -5.0]                  # y вершин шевронов
CHEV_ARM, CHEV_ANGLE, CHEV_BAR = 10.0, math.radians(35), 2.6
DEBOSS, CHIP_UP, GROOVE = 0.35, 0.06, 0.05   # глубина эмблемы, высота чипа, глубина прорезей контактов

# ---- развёртка: области атласа (u0, u1, v0, v1) и плотность, доля текстуры на мм ----
S = 0.0098                                   # лицо и торцы: ~10 пикселей на мм
SB = 0.0043                                  # дно
TOP = (0.01, 0.01 + L * S, 0.40, 0.40 + W * S)
YWALL = (0.01, 0.01 + L * S, 0.33, 0.33 + T * S)
XWALL = (0.01, 0.01 + W * S, 0.27, 0.27 + T * S)
BOTTOM = (0.01, 0.01 + L * SB, 0.005, 0.005 + W * SB)
ALU = (0.63, 0.75, 0.27, 0.32)
STEEL = (0.78, 0.99, 0.27, 0.32)
TEAL = (0.50, 0.62, 0.05, 0.20)
SIZE = 1024

# ---- цвета (sRGB, как в файле), шероховатость, металл ----
def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)], np.float32)


WHITE, WHITE_DEEP = hexc("#E6E3DD"), hexc("#BFBAB1")   # дно эмблемы темнее: в Unreal светлое на белом пропадало
ORANGE = hexc("#F26A21")
GRAPHITE = hexc("#2E3236")
GOLD, GOLD_GROOVE = hexc("#C8A24E"), hexc("#6E5A2C")
ALUMINIUM = hexc("#B9BCC0")
STEELC = hexc("#9EA2A6")
TEALC = hexc("#5FC6C9")
ROUGH = {"white": 0.5, "orange": 0.45, "graphite": 0.65, "gold": 0.3, "alu": 0.35, "steel": 0.28, "teal": 0.3}

PART_BODY, PART_GROMMET, PART_RING, PART_STRIP = 0, 1, 2, 3


# ======================= геометрия (мм) =======================

def rounded_rect(lx, ly, r, n=12):
    """Контур против часовой стрелки, начало в правом нижнем углу."""
    pts = []
    for cx, cy, a0 in ((lx / 2 - r, -ly / 2 + r, -90), (lx / 2 - r, ly / 2 - r, 0), (-lx / 2 + r, ly / 2 - r, 90), (-lx / 2 + r, -ly / 2 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def new_object(name, bm, part):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    attr = me.attributes.new("part", "INT", "FACE")
    attr.data.foreach_set("value", [part] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def body():
    bm = bmesh.new()
    outline = rounded_rect(L, W, R)
    bot = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    top = [bm.verts.new((x, y, T)) for x, y in outline]
    f_top = bm.faces.new(top)
    f_bot = bm.faces.new(list(reversed(bot)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    edges = [e for e in bm.edges if f_top in e.link_faces or f_bot in e.link_faces]
    bmesh.ops.bevel(bm, geom=edges, offset=BEVEL, offset_type="OFFSET", segments=3, profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    ob = new_object("Body", bm, PART_BODY)
    # отверстие: вычитание цилиндра (точное), результат запекается в меш
    cut = bmesh.new()
    bmesh.ops.create_cone(cut, cap_ends=True, cap_tris=False, segments=32, radius1=HOLE_R, radius2=HOLE_R, depth=T * 3,
                          matrix=Matrix.Translation((HX, HY, T / 2)))
    cutter = new_object("HoleCutter", cut, PART_BODY)
    mod = ob.modifiers.new("Hole", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    try:
        mod.solver = "EXACT"
    except TypeError:
        pass
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    if "part" not in me.attributes:
        me.attributes.new("part", "INT", "FACE")
    me.attributes["part"].data.foreach_set("value", [PART_BODY] * len(me.polygons))
    return ob


def lathe(profile, segments, centre):
    bm = bmesh.new()
    rings = []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        rings.append([bm.verts.new((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a), z)) for r, z in profile])
    m = len(profile)
    for k in range(segments):
        a, b = rings[k], rings[(k + 1) % segments]
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def ring():
    """Кольцо проходит через центр отверстия; в этой точке проволока идёт под RING_TILT к вертикали и наружу от угла,
    а само кольцо завалено вбок на RING_LEAN вокруг этой проволоки."""
    bm = bmesh.new()
    major, minor = 48, 12
    grid = []
    for i in range(major):
        a = 2 * math.pi * i / major
        row = []
        for j in range(minor):
            b = 2 * math.pi * j / minor
            rr = RING_R + RING_WIRE * math.cos(b)
            row.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), RING_WIRE * math.sin(b))))
        grid.append(row)
    for i in range(major):
        for j in range(minor):
            bm.faces.new((grid[i][j], grid[(i + 1) % major][j], grid[(i + 1) % major][(j + 1) % minor], grid[i][(j + 1) % minor]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    d = Vector((1, 1, 0)).normalized()
    z = Vector((0, 0, 1))
    u = math.cos(RING_TILT) * d + math.sin(RING_TILT) * z
    v = -math.sin(RING_TILT) * d + math.cos(RING_TILT) * z
    side = u.cross(v)
    u = math.cos(RING_LEAN) * u + math.sin(RING_LEAN) * side      # поворот плоскости кольца вокруг касательной v
    n = u.cross(v)
    h = Vector((HX, HY, T / 2))
    c = h + RING_R * u
    m = Matrix(((u.x, v.x, n.x, c.x), (u.y, v.y, n.y, c.y), (u.z, v.z, n.z, c.z), (0, 0, 0, 1)))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return bm


def strip():
    bm = bmesh.new()
    lo = Vector((STRIP[0], -W / 2 - 0.12, T / 2 - 0.55))
    hi = Vector((STRIP[1], -W / 2 + 0.4, T / 2 + 0.55))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*(hi - lo), 1.0)))
    return bm


def build_mesh():
    parts = [body(), new_object("Grommet", lathe(GROMMET, 32, (HX, HY)), PART_GROMMET),
             new_object("Ring", ring(), PART_RING), new_object("Strip", strip(), PART_STRIP)]
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = "SM_" + NAME
    ob.data.name = "SM_" + NAME
    return ob


def unwrap(ob):
    """Развёртка по областям атласа. Лицо, торцы и дно — проекцией в мм (плотность S, у дна SB); у торцов и стенок
    отверстия — по главной горизонтальной оси нормали. Люверс, кольцо и полоса — ровные цвета, любая раскладка
    внутри своей области."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify()
    part = bm.faces.layers.int.get("part")

    def box(region, a, b, alo, ahi, blo, bhi):
        u0, u1, v0, v1 = region
        pad = 6.0 / SIZE
        return (u0 + pad + (u1 - u0 - 2 * pad) * min(1, max(0, (a - alo) / (ahi - alo))),
                v0 + pad + (v1 - v0 - 2 * pad) * min(1, max(0, (b - blo) / (bhi - blo))))

    for f in bm.faces:
        p = f[part]
        n = f.normal
        for lp in f.loops:
            x, y, z = lp.vert.co
            if p == PART_BODY:
                if n.z > 0.5:
                    c = (TOP[0] + (x + L / 2) * S, TOP[2] + (y + W / 2) * S)
                elif n.z < -0.5:
                    c = (BOTTOM[0] + (x + L / 2) * SB, BOTTOM[2] + (y + W / 2) * SB)
                elif abs(n.y) >= abs(n.x):
                    c = (YWALL[0] + (x + L / 2) * S, YWALL[2] + z * S)
                else:
                    c = (XWALL[0] + (y + W / 2) * S, XWALL[2] + z * S)
            elif p == PART_GROMMET:
                c = box(ALU, x, z, HX - 4.2, HX + 4.2, 0, T + 0.5)
            elif p == PART_RING:
                c = box(STEEL, x - y, z, -12, 12, -6, 12)
            else:
                c = box(TEAL, x, z, STRIP[0], STRIP[1], 0, T)
            lp[uv].uv = c
    bm.to_mesh(me)
    bm.free()
    me.uv_layers[0].name = "UVMap"


# ======================= текстуры =======================

def load_grey(path):
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[:, :, 0].copy()


def bilinear(tex, x, y):
    h, w = tex.shape
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    x0, y0 = x0 % w, y0 % h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    return (tex[y0, x0] * (1 - fx) * (1 - fy) + tex[y0, x1] * fx * (1 - fy)
            + tex[y1, x0] * (1 - fx) * fy + tex[y1, x1] * fx * fy)


class Wear:
    """Износ по pipeline/kit.md: царапины — две раскладки fine-scratches (вторая повёрнута на четверть), растянутые
    по процентилям 60…99,5; weathering — как есть. Плитки мельче, чем у мебели (× 0,4, как у уплотнённых деталей):
    0,24 и 0,30 м у царапин, 0,40 м у weathering — иначе на 10 см карты не попадает ни одной царапины."""

    def __init__(self):
        common = os.path.join(ROOT, "environment", "common")
        self.scratch = load_grey(os.path.join(common, "fine-scratches", "fine-scratches.png"))
        self.weather = load_grey(os.path.join(common, "weathering", "weathering.png"))
        self.p0, self.p1 = np.percentile(self.scratch, [60, 99.5])

    def __call__(self, a, b, off):
        """a, b — координаты поверхности в мм; off — свой сдвиг поверхности (мм), чтобы узоры лица, торцов и дна
        не совпадали. Возвращает (царапины, weathering), оба 0…1."""
        a, b = a + off[0], b + off[1]
        k = SIZE / 1000.0
        s1 = bilinear(self.scratch, a * k / 0.24, b * k / 0.24)
        s2 = bilinear(self.scratch, b * k / 0.30, -a * k / 0.30)
        st = lambda s: np.clip((s - self.p0) / (self.p1 - self.p0), 0, 1)
        return np.maximum(st(s1), 0.85 * st(s2)), bilinear(self.weather, a * k / 0.40, b * k / 0.40)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def mix(c, target, t):
    t = np.asarray(t, np.float32)[..., None]
    return c * (1 - t) + target * t


def box_blur(a, r):
    if r <= 0:
        return a
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
        n = a.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        a = (hi - lo) / (2 * r + 1)
    return a


def sd_round_box(x, y, cx, cy, lx, ly, r):
    qx = np.abs(x - cx) - (lx / 2 - r)
    qy = np.abs(y - cy) - (ly / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_segment(x, y, ax, ay, bx, by):
    px, py, dx, dy = x - ax, y - ay, bx - ax, by - ay
    h = np.clip((px * dx + py * dy) / (dx * dx + dy * dy), 0, 1)
    return np.hypot(px - dx * h, py - dy * h)


def inside_polygon(x, y, pts):
    inside = np.zeros(x.shape, bool)
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        cross = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0)
        inside ^= cross
    return inside


def region_grid(region, margin=4):
    """Пиксели области с запасом: срезы строк и столбцов и координаты центров текселей (u, v)."""
    u0, u1, v0, v1 = region
    c0, c1 = max(0, int(math.floor(u0 * SIZE)) - margin), min(SIZE, int(math.ceil(u1 * SIZE)) + margin)
    r0, r1 = max(0, int(math.floor(v0 * SIZE)) - margin), min(SIZE, int(math.ceil(v1 * SIZE)) + margin)
    u = (np.arange(c0, c1) + 0.5) / SIZE
    v = (np.arange(r0, r1) + 0.5) / SIZE
    uu, vv = np.meshgrid(u, v)
    return (slice(r0, r1), slice(c0, c1)), uu, vv


def paint():
    base = np.zeros((SIZE, SIZE, 3), np.float32)
    base[:] = GRAPHITE
    rough = np.full((SIZE, SIZE), ROUGH["graphite"], np.float32)
    metal = np.zeros((SIZE, SIZE), np.float32)
    ao = np.ones((SIZE, SIZE), np.float32)
    height = np.zeros((SIZE, SIZE), np.float32)
    emit = np.zeros((SIZE, SIZE, 3), np.float32)
    wear = Wear()

    # --- лицо ---
    sl, uu, vv = region_grid(TOP)
    x = (uu - TOP[0]) / S - L / 2
    y = (vv - TOP[2]) / S - W / 2
    inner = -sd_round_box(x, y, 0, 0, L, W, R)               # расстояние до края карты внутрь, мм
    scr, wth = wear(x, y, (0.0, 0.0))
    plate = inner > RIM
    orange = plate & (x < ORANGE_X)
    white = plate & ~orange
    c = np.empty(x.shape + (3,), np.float32)
    c[:] = GRAPHITE
    c[white] = WHITE
    c[orange] = ORANGE
    r = np.where(orange, ROUGH["orange"], np.where(white, ROUGH["white"], ROUGH["graphite"])).astype(np.float32)
    # эмблема: звезда и шевроны, выдавлены внутрь
    sx, sy, so, si = STAR
    star = [(sx + (so if k % 2 == 0 else si) * math.cos(math.radians(90 + 36 * k)),
             sy + (so if k % 2 == 0 else si) * math.sin(math.radians(90 + 36 * k))) for k in range(10)]
    emblem = inside_polygon(x, y, star)
    for ay in CHEVRONS:
        dx, dy = CHEV_ARM * math.cos(CHEV_ANGLE), CHEV_ARM * math.sin(CHEV_ANGLE)
        d = np.minimum(sd_segment(x, y, EMBLEM_X, ay, EMBLEM_X - dx, ay - dy), sd_segment(x, y, EMBLEM_X, ay, EMBLEM_X + dx, ay - dy))
        emblem |= d < CHEV_BAR / 2
    emblem_s = box_blur(emblem.astype(np.float32), 2)
    c = mix(c, WHITE_DEEP, emblem_s * white)
    # чип: золото, прорези контактов
    cx, cy, cw, ch, cr = CHIP
    chip = sd_round_box(x, y, cx, cy, cw, ch, cr) < 0
    gx = np.abs(x - cx)
    groove = chip & ((np.abs(gx - 2.2) < 0.17)
                     | ((gx > 2.2) & (np.abs(np.abs(y - cy) - 1.7) < 0.17))
                     | ((gx < 2.2) & (np.abs(y - cy - 0.6) < 0.17)))
    c[chip] = GOLD
    c[groove] = GOLD_GROOVE
    r[chip] = ROUGH["gold"]
    m = chip.astype(np.float32)
    # износ: царапины и потёртости weathering; сильнее на оранжевом конце (за него держат) и у края карты
    rub = np.where(orange, 0.55 + 0.45 * smoothstep(ORANGE_X, -L / 2 + 5, x), 0.0)
    edge = (1 - smoothstep(RIM, RIM + 1.6, inner)) * plate
    scuff, chips = smoothstep(0.06, 0.2, wth), smoothstep(0.5, 0.7, wth)
    c = mix(c, hexc("#F6CDAE"), 0.5 * scr * rub)                         # царапины по краске до грунта
    c = mix(c, hexc("#F59A63"), 0.35 * scuff * rub)                       # затёртые полосы
    c = mix(c, hexc("#E9E5DE"), chips * rub)                              # сколы оранжевого до белого
    c = mix(c, hexc("#B9B5AD"), 0.22 * scr * white * (1 - chip))         # лёгкие царапины на белом
    c = mix(c, hexc("#8F9091"), 0.6 * chips * edge * white)              # сколы белого у края
    c = mix(c, np.where(orange[..., None], hexc("#F7B48B"), hexc("#CFCBC3")), 0.55 * edge * scuff)
    c = mix(c, hexc("#62676C"), (0.45 * scr + 0.5 * scuff) * (~plate))  # кромка: светлее на трущихся местах
    c = mix(c, hexc("#E3CC8A"), 0.35 * scr * chip)
    r = r + 0.12 * scr * (1 - m)
    base[sl] = c
    rough[sl] = r
    metal[sl] = m
    # рельеф лица: эмблема вниз, чип вверх, прорези контактов вниз
    h = -DEBOSS * emblem_s * plate + CHIP_UP * box_blur(chip.astype(np.float32), 1) - GROOVE * box_blur(groove.astype(np.float32), 1)
    height[sl] = h
    ao[sl] = 1 - 0.25 * emblem_s - 0.25 * groove

    # --- торцы и дно: графит с износом ---
    for region, coords, off in ((YWALL, lambda u, v: ((u - YWALL[0]) / S - L / 2, (v - YWALL[2]) / S), (300.0, 40.0)),
                                (XWALL, lambda u, v: ((u - XWALL[0]) / S - W / 2, (v - XWALL[2]) / S), (40.0, 500.0)),
                                (BOTTOM, lambda u, v: ((u - BOTTOM[0]) / SB - L / 2, (v - BOTTOM[2]) / SB - W / 2), (700.0, 700.0))):
        sl, uu, vv = region_grid(region)
        a, b = coords(uu, vv)
        scr, wth = wear(a, b, off)
        c = np.empty(a.shape + (3,), np.float32)
        c[:] = GRAPHITE
        c = mix(c, hexc("#62676C"), 0.3 * scr + 0.3 * smoothstep(0.06, 0.2, wth))
        base[sl] = c
        rough[sl] = ROUGH["graphite"] + 0.1 * scr

    # --- ровные металлы и свечение ---
    for region, col, key, met in ((ALU, ALUMINIUM, "alu", 1.0), (STEEL, STEELC, "steel", 1.0), (TEAL, TEALC, "teal", 0.0)):
        sl, _, _ = region_grid(region)
        base[sl] = col
        rough[sl] = ROUGH[key]
        metal[sl] = met
    sl, _, _ = region_grid(TEAL)
    emit[sl] = TEALC

    # --- нормали из высот (мм): OpenGL, y картинки снизу вверх, как пиксели Blender ---
    px = 1.0 / (S * SIZE)
    gy, gx = np.gradient(height, px)
    nrm = np.dstack([-gx, -gy, np.ones_like(height)])
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    return base, np.dstack([ao, np.clip(rough, 0, 1), metal]), nrm, emit


def save_png(path, rgb):
    h, w, _ = rgb.shape
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=False, is_data=True)
    im.pixels.foreach_set(np.dstack([np.clip(rgb, 0, 1), np.ones((h, w), np.float32)]).ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def write_textures():
    base, orm, nrm, emit = paint()
    save_png(os.path.join(OUT, f"T_{NAME}_BaseColor.png"), base)
    save_png(os.path.join(OUT, f"T_{NAME}_ORM.png"), orm)
    save_png(os.path.join(OUT, f"T_{NAME}_Emissive.png"), emit)
    save_png(os.path.join(OUT, "source", f"{STEM}_nor_gl.png"), nrm * 0.5 + 0.5)
    dx = nrm.copy()
    dx[:, :, 1] *= -1                       # Unreal ждёт DirectX: зелёный инвертирован (pipeline/unreal.md)
    save_png(os.path.join(OUT, f"T_{NAME}_Normal.png"), dx * 0.5 + 0.5)


def material():
    m = bpy.data.materials.new("MI_" + NAME)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

    def tex(path, data, x, y):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(path)
        if data:
            t.image.colorspace_settings.name = "Non-Color"
        t.location = (x, y)
        return t

    base = tex(os.path.join(OUT, f"T_{NAME}_BaseColor.png"), False, -700, 300)
    orm = tex(os.path.join(OUT, f"T_{NAME}_ORM.png"), True, -700, 0)
    nor = tex(os.path.join(OUT, "source", f"{STEM}_nor_gl.png"), True, -700, -300)
    emi = tex(os.path.join(OUT, f"T_{NAME}_Emissive.png"), False, -700, -600)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-400, 0)
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.location = (-400, -300)
    nt.links.new(base.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    nt.links.new(nor.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(emi.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 2.0
    return m


# ======================= сцена, миниатюра, выгрузка =======================

def bounds(ob):
    co = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return Vector(co.min(0)), Vector(co.max(0))


def camera(name, target, direction, scale, ortho=True):
    data = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(cam)
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = scale
    else:
        data.lens = 85
    cam.location = target + Vector(direction).normalized() * (scale * 4 if ortho else scale)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def preview(ob):
    """Миниатюра Студии, как у tripo_props.py: Workbench, текстура, орто 3/4."""
    scene = bpy.context.scene
    lo, hi = bounds(ob)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = scene.render.resolution_y = 512
    cam = camera("preview", (lo + hi) / 2, (0.6, -1.0, 0.45), max(hi - lo) * 1.3)
    scene.render.filepath = os.path.join(OUT, "preview.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)


def check_renders(ob, folder):
    """Проверочные кадры EEVEE: 3/4 как на картинке автора, сверху, торец с полосой, кольцо крупно."""
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = scene.render.resolution_y = 900
    world = bpy.data.worlds.new("Check")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.56, 0.58, 1)
    bg.inputs["Strength"].default_value = 0.8
    scene.world = world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(40), math.radians(-25), math.radians(30))
    scene.collection.objects.link(sun)
    floor_me = bpy.data.meshes.new("Floor")
    floor_me.from_pydata([(-1, -1, -0.0021), (1, -1, -0.0021), (1, 1, -0.0021), (-1, 1, -0.0021)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new("Floor", floor_me)
    fm = bpy.data.materials.new("FloorGrey")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.5, 0.5, 0.52, 1)
    floor_me.materials.append(fm)
    scene.collection.objects.link(floor)
    c = Vector((0, 0, 0.0025))
    for name, direction, scale, ortho in (("check_34", (-0.35, -1.0, 0.95), 0.13, True),
                                          ("check_top", (0, -0.001, 1), 0.12, True),
                                          ("check_edge", (0.25, -1.0, 0.18), 0.11, True),
                                          ("check_ring", (0.9, 0.2, 0.6), 0.16, False)):
        target = Vector((0.043, 0.023, 0.004)) if name == "check_ring" else c
        cam = camera(name, target, direction, scale, ortho)
        scene.render.filepath = os.path.join(folder, name + ".png")
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam, do_unlink=True)


def export(ob):
    bpy.context.scene.unit_settings.scale_length = 0.01
    ob.data.transform(Matrix.Scale(100.0, 4))
    tri = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
    tri.keep_custom_normals = True
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
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


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    os.makedirs(os.path.join(OUT, "source"), exist_ok=True)

    ob = build_mesh()
    unwrap(ob)
    me = ob.data
    me.transform(Matrix.Scale(0.001, 4))          # мм -> м
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(40))
    wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA"
    wn.keep_sharp = True
    write_textures()
    me.materials.clear()                          # после объединения частей в списке пустой слот
    me.materials.append(material())

    # проверка сетки
    bm = bmesh.new()
    bm.from_mesh(me)
    bad = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    loose = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    bm.free()
    lo, hi = bounds(ob)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    print(f"## {ob.name}: {(hi.x - lo.x) * 100:.2f} × {(hi.y - lo.y) * 100:.2f} × {(hi.z - lo.z) * 100:.2f} см "
          f"(z от {lo.z * 100:.2f}), {len(me.polygons)} граней, {tris} треугольников; рёбер с 3+ гранями {bad}, "
          f"свободных {loose}, вырожденных граней {degenerate}")

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "source", STEM + ".blend"), compress=True)
    preview(ob)
    if args:
        os.makedirs(args[0], exist_ok=True)
        check_renders(ob, args[0])
    export(ob)
    print(f"## записано: SM_{NAME}.fbx, T_{NAME}_BaseColor/ORM/Normal/Emissive.png, source/{STEM}.blend, preview.png")


main()
