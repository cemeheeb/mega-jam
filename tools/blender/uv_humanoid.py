"""UV-развёртка сгенерированного персонажа в Blender: лицо и кисти получают больше места в текстуре.

Работает с активным мешем: человек в А-позе, рост по оси Z, лицом к −Y, симметрия по X.
Пороги заданы долями роста и подобраны под модель инженера из Tripo (рукава до локтя слиты с торсом).

Этапы (вызываются из Blender по очереди, чтобы смотреть результат каждого):
    import importlib, sys; sys.path.insert(0, ".../tools/blender"); import uv_humanoid as U; importlib.reload(U)
    U.classify()      # разметить части, записать в атрибут грани uv_region и цвет uv_region_color
    U.seams()         # швы по границам частей и разрезы по скрытым линиям
    U.unwrap()        # новая развёртка в слой UVMap, плотность по частям, упаковка
    U.bake(path)      # перенести цвет со старой развёртки на новую, сохранить картинку
"""

import collections
import heapq
import math

import bmesh
import bpy
from mathutils import Vector

# Части модели.
HEAD, HAND_L, HAND_R, ARM_L, ARM_R, TORSO, PANTS, BOOT_L, BOOT_R, PART = range(1, 11)
NAMES = {HEAD: "head", HAND_L: "hand_l", HAND_R: "hand_r", ARM_L: "arm_l", ARM_R: "arm_r", TORSO: "torso",
         PANTS: "pants", BOOT_L: "boot_l", BOOT_R: "boot_r", PART: "part"}
COLORS = {HEAD: (0.9, 0.2, 0.2), HAND_L: (0.2, 0.9, 0.2), HAND_R: (0.1, 0.6, 0.1), ARM_L: (0.2, 0.4, 1.0),
          ARM_R: (0.1, 0.2, 0.7), TORSO: (0.95, 0.85, 0.2), PANTS: (0.8, 0.4, 0.9), BOOT_L: (0.2, 0.9, 0.9),
          BOOT_R: (0.1, 0.6, 0.6), PART: (0.5, 0.5, 0.5)}

# Во сколько раз плотнее обычного (по стороне пикселя) лежит часть в текстуре.
DENSITY = {HEAD: 1.4, HAND_L: 2.4, HAND_R: 2.4, ARM_L: 1.15, ARM_R: 1.15, TORSO: 1.0, PANTS: 0.9,
           BOOT_L: 0.85, BOOT_R: 0.85, PART: 0.85}
FACE = 1                 # половина головы: лицо (uv_sub == 1), остальное — волосы, уши, затылок
FACE_DENSITY = 3.2

# Пороги в долях роста.
CFG = dict(
    neck_front=(-0.05, 0.858),   # (y, z) спереди под бородой
    neck_back=(0.05, 0.875),     # (y, z) сзади над воротником
    wrist_z=0.49,
    hand_x=0.14,
    boot_z=0.08,
    waist_z=0.572,               # нижний край ремня
    arm_top_z=0.845,
    # граница «рука — торс»: (z, |x|). Выше локтя рукав слит с торсом, ниже рука отдельно.
    arm_x=((0.52, 0.128), (0.54, 0.125), (0.56, 0.116), (0.58, 0.111), (0.60, 0.105), (0.62, 0.103), (1.0, 0.103)),
    arm_free_z=0.60,             # ниже этой высоты рука точно отдельна от торса
    arm_sure_x=0.128,            # дальше от оси — точно рука
    torso_sure_x=0.082,          # ближе к оси — точно торс
    # лицо: точно лицо — спереди, между бородой и линией волос, не шире скул
    face_y=-0.028, face_z=(0.872, 0.945), face_x=0.036,
    # точно не лицо — за ушами, выше линии волос, сбоку от скул
    scalp_y=0.004, scalp_z=0.968, scalp_x=0.047,
)

NEW_UV = "UVMap"
REGION = "uv_region"
SUB = "uv_sub"        # половина части: ладонь или тыльная сторона кисти, подошва или верх ботинка


def _obj():
    o = bpy.context.active_object
    if not o or o.type != "MESH":
        raise RuntimeError("нужен активный меш")
    if o.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    return o


def _lerp_table(table, z):
    if z <= table[0][0]:
        return table[0][1]
    for (z0, v0), (z1, v1) in zip(table, table[1:]):
        if z <= z1:
            return v0 + (v1 - v0) * (z - z0) / (z1 - z0)
    return table[-1][1]


def _frame(o, bm):
    """Функции перевода в координаты «доли роста»: ноги на z=0, макушка на z=1."""
    M = o.matrix_world
    zs = [(M @ v.co).z for v in bm.verts]
    z0, height = min(zs), max(zs) - min(zs)

    def norm(co):
        c = M @ co
        return Vector((c.x / height, c.y / height, (c.z - z0) / height))
    return norm


def _concavity(e):
    """0 для плоского или выпуклого ребра, до 1 для складки внутрь на 30 градусов и больше."""
    if len(e.link_faces) != 2:
        return 0.0
    f, g = e.link_faces
    if (g.calc_center_median() - f.calc_center_median()).dot(f.normal) <= 1e-7:
        return 0.0
    return min(1.0, math.degrees(f.normal.angle(g.normal, 0.0)) / 30.0)


def _components(bm):
    comp, cid = {}, 0
    for f in bm.faces:
        if f.index in comp:
            continue
        stack = [f]
        comp[f.index] = cid
        while stack:
            x = stack.pop()
            for e in x.edges:
                for g in e.link_faces:
                    if g.index not in comp:
                        comp[g.index] = cid
                        stack.append(g)
        cid += 1
    return comp


def classify(cfg=None):
    """Размечает грани по частям. Высота модели приводится к 1, поэтому пороги — доли роста."""
    cfg = {**CFG, **(cfg or {})}
    o = _obj()
    me = o.data
    M = o.matrix_world
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    zs = [(M @ v.co).z for v in bm.verts]
    z0, height = min(zs), max(zs) - min(zs)

    def center(f):
        c = M @ f.calc_center_median()
        return Vector((c.x / height, c.y / height, (c.z - z0) / height))

    comp = _components(bm)
    main = collections.Counter(comp.values()).most_common(1)[0][0]
    (yf, zf), (yb, zb) = cfg["neck_front"], cfg["neck_back"]
    label = {}
    centers = {f.index: center(f) for f in bm.faces}
    unsure = set()
    for f in bm.faces:
        c = centers[f.index]
        if comp[f.index] != main:
            label[f.index] = PART
            continue
        neck_z = zf + (zb - zf) * min(1.0, max(0.0, (c.y - yf) / (yb - yf)))
        left = c.x < 0
        arm = ARM_L if left else ARM_R
        if c.z > neck_z:
            lab = HEAD
        elif c.z < cfg["boot_z"]:
            lab = BOOT_L if left else BOOT_R
        elif abs(c.x) > cfg["hand_x"] and c.z < cfg["wrist_z"]:
            lab = HAND_L if left else HAND_R
        elif c.z < cfg["waist_z"] and abs(c.x) <= _lerp_table(cfg["arm_x"], c.z):
            lab = PANTS
        elif c.z < cfg["wrist_z"]:
            lab = PANTS
        elif c.z < cfg["arm_free_z"]:
            lab = arm if abs(c.x) > _lerp_table(cfg["arm_x"], c.z) else TORSO
        elif c.z < cfg["arm_top_z"] and abs(c.x) > cfg["arm_sure_x"]:
            lab = arm
        elif abs(c.x) < cfg["torso_sure_x"] or c.z >= cfg["arm_top_z"]:
            lab = TORSO
        else:
            lab = 0            # слитая зона рукава и торса: решит «водораздел» ниже
            unsure.add(f.index)
        label[f.index] = lab

    # Слитая зона: грань достаётся руке или торсу — кто ближе по поверхности, причём переход через
    # вогнутую складку стоит дорого. Граница сама ложится в складку между рукавом и торсом.
    heap = []
    dist = {}
    for f in bm.faces:
        if label[f.index] in (ARM_L, ARM_R, TORSO):
            for e in f.edges:
                if any(g.index in unsure for g in e.link_faces):
                    dist[f.index] = 0.0
                    heap.append((0.0, f.index, label[f.index]))
                    break
    heapq.heapify(heap)
    while heap:
        d, fi, lab = heapq.heappop(heap)
        if fi in unsure:
            if label[fi]:
                continue
            label[fi] = lab
        f = bm.faces[fi]
        for e in f.edges:
            for g in e.link_faces:
                if g.index in unsure and not label[g.index]:
                    nd = d + (centers[g.index] - centers[fi]).length * (1.0 + 12.0 * _concavity(e))
                    if nd < dist.get(g.index, 1e18):
                        dist[g.index] = nd
                        heapq.heappush(heap, (nd, g.index, lab))
    for fi in unsure:
        if not label[fi]:
            label[fi] = TORSO

    # Сгладить зубцы границ: грань, у которой большинство соседей другой части, переходит к ним.
    for _ in range(3):
        changed = 0
        for f in bm.faces:
            if label[f.index] == PART:
                continue
            near = collections.Counter(label[g.index] for e in f.edges for g in e.link_faces if g is not f and label[g.index] != PART)
            if not near:
                continue
            best, n = near.most_common(1)[0]
            if best != label[f.index] and n >= max(3, len(f.edges) - 1):
                label[f.index] = best
                changed += 1
        if not changed:
            break
    # Оторванные клочки (например, верх воротника, попавший выше плоскости шеи) отдать соседней части.
    seen = set()
    for f in bm.faces:
        if f.index in seen or label[f.index] == PART:
            continue
        group, stack = [f], [f]
        seen.add(f.index)
        while stack:
            x = stack.pop()
            for e in x.edges:
                for g in e.link_faces:
                    if g.index not in seen and label[g.index] == label[f.index]:
                        seen.add(g.index)
                        group.append(g)
                        stack.append(g)
        if len(group) < 60:
            near = collections.Counter(label[g.index] for x in group for e in x.edges for g in e.link_faces
                                       if label[g.index] not in (label[f.index], PART))
            if near:
                to = near.most_common(1)[0][0]
                for x in group:
                    label[x.index] = to
    bm.free()

    attr = me.attributes.get(REGION) or me.attributes.new(REGION, "INT", "FACE")
    attr.data.foreach_set("value", [label[i] for i in range(len(me.polygons))])
    col = me.color_attributes.get(REGION + "_color") or me.color_attributes.new(REGION + "_color", "BYTE_COLOR", "CORNER")
    for p in me.polygons:
        c = COLORS[label[p.index]]
        for li in p.loop_indices:
            col.data[li].color = (c[0], c[1], c[2], 1.0)
    me.color_attributes.active_color = col
    count = collections.Counter(label.values())
    print("regions:", {NAMES[k]: v for k, v in sorted(count.items())})
    return count


# ---------------------------------------------------------------------------------------------
# Швы
# ---------------------------------------------------------------------------------------------

def _path(bm, P, start, goals, allowed, penalty=None):
    """Кратчайший путь по рёбрам от вершины start до любой из goals внутри allowed.
    penalty(i) >= 0 удорожает рёбра у «нежелательных» вершин: так путь прижимается к нужной линии."""
    goals = set(goals)
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist.get(i, 1e18):
            continue
        if i in goals and i != start:
            edges = []
            while i != start:
                e = prev[i]
                edges.append(e)
                i = e.other_vert(bm.verts[i]).index
            return edges
        v = bm.verts[i]
        for e in v.link_edges:
            j = e.other_vert(v).index
            if j not in allowed and j not in goals:
                continue
            w = (P[i] - P[j]).length
            if penalty:
                w *= 1.0 + 0.5 * (penalty(i) + penalty(j))
            nd = d + w
            if nd < dist.get(j, 1e18):
                dist[j] = nd
                prev[j] = e
                heapq.heappush(heap, (nd, j))
    return []


def _profile(P, verts, step=0.02):
    """По высоте: наименьший и наибольший |x| среди вершин. Нужен, чтобы прижать шов к внутренней или внешней линии."""
    table = {}
    for i in verts:
        b = int(P[i].z / step)
        a = abs(P[i].x)
        lo, hi = table.get(b, (a, a))
        table[b] = (min(lo, a), max(hi, a))

    def at(z):
        b = int(z / step)
        for k in range(0, 6):
            for bb in (b - k, b + k):
                if bb in table:
                    return table[bb]
        return (0.0, 0.0)
    return at


def _watershed(bm, C, state, weight):
    """state: грань -> метка, 0 — «спорная». Спорная грань получает метку ближайшей по поверхности размеченной,
    причём шаг через вогнутую складку стоит в weight раз дороже: граница ложится в складки."""
    heap = []
    for fi, lab in state.items():
        if lab:
            f = bm.faces[fi]
            if any(state.get(g.index, -1) == 0 for e in f.edges for g in e.link_faces):
                heap.append((0.0, fi, lab))
    heapq.heapify(heap)
    dist = {}
    done = set()
    while heap:
        d, fi, lab = heapq.heappop(heap)
        if state[fi] == 0:
            state[fi] = lab
        elif fi in done or state[fi] != lab:
            continue
        done.add(fi)
        for e in bm.faces[fi].edges:
            for g in e.link_faces:
                if state.get(g.index, -1) == 0:
                    nd = d + (C[g.index] - C[fi]).length * (1.0 + weight * _concavity(e))
                    if nd < dist.get(g.index, 1e18):
                        dist[g.index] = nd
                        heapq.heappush(heap, (nd, g.index, lab))


def _clean_sub(faces, sub, min_size):
    """Мелкие островки половины (меньше min_size граней) отдаёт соседней половине; сглаживает зубцы."""
    index = {f.index for f in faces}
    for _ in range(4):
        seen, changed = set(), False
        for f in faces:
            if f.index in seen:
                continue
            group, stack = [f], [f]
            seen.add(f.index)
            while stack:
                x = stack.pop()
                for e in x.edges:
                    for g in e.link_faces:
                        if g.index in index and g.index not in seen and sub[g.index] == sub[f.index]:
                            seen.add(g.index)
                            group.append(g)
                            stack.append(g)
            if len(group) < min_size:
                near = collections.Counter(sub[g.index] for x in group for e in x.edges for g in e.link_faces
                                           if g.index in index and sub[g.index] != sub[f.index])
                if near:
                    to = near.most_common(1)[0][0]
                    for x in group:
                        sub[x.index] = to
                    changed = True
        for f in faces:
            near = collections.Counter(sub[g.index] for e in f.edges for g in e.link_faces if g is not f and g.index in index)
            if near:
                best, n = near.most_common(1)[0]
                if best != sub[f.index] and n >= max(3, len(f.edges) - 1):
                    sub[f.index] = best
                    changed = True
        if not changed:
            break


def seams(cfg=None):
    """Ставит швы: границы частей, половины кистей и ботинок, разрезы по скрытым линиям."""
    import numpy as np
    cfg = {**CFG, **(cfg or {})}
    o = _obj()
    me = o.data
    R = o.matrix_world.to_3x3()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    norm = _frame(o, bm)
    P = {v.index: norm(v.co) for v in bm.verts}
    lay = bm.faces.layers.int[REGION]
    label = {f.index: f[lay] for f in bm.faces}
    sub = {f.index: 0 for f in bm.faces}
    by = collections.defaultdict(list)
    for f in bm.faces:
        by[label[f.index]].append(f)
    vs = {k: {v.index for f in fs for v in f.verts} for k, fs in by.items()}
    for e in bm.edges:
        e.seam = False
    report = []

    # Кисть: ладонь и тыльная сторона. Ось толщины — направление наименьшего разброса вершин.
    for hand in (HAND_L, HAND_R):
        pts = np.array([P[i] for i in vs[hand]])
        w, vec = np.linalg.eigh(np.cov((pts - pts.mean(axis=0)).T))
        axis = Vector(vec[:, 0])
        for f in by[hand]:
            sub[f.index] = 1 if (R @ f.normal).dot(axis) > 0 else 2
        _clean_sub(by[hand], sub, 14)

    # Голова: лицо отдельным островом. «Точно лицо» и «точно не лицо» заданы грубо, спорную полосу
    # делит водораздел: граница ложится в складки (линия волос, виски, под челюстью).
    C = {f.index: norm(f.calc_center_median()) for f in by[HEAD]}
    state = {}
    for f in by[HEAD]:
        c = C[f.index]
        if c.y < cfg["face_y"] and cfg["face_z"][0] < c.z < cfg["face_z"][1] and abs(c.x) < cfg["face_x"]:
            state[f.index] = FACE
        elif c.y > cfg["scalp_y"] or c.z > cfg["scalp_z"] or abs(c.x) > cfg["scalp_x"]:
            state[f.index] = 2
        else:
            state[f.index] = 0
    _watershed(bm, C, state, 10.0)
    for f in by[HEAD]:
        sub[f.index] = state[f.index] or 2
    _clean_sub(by[HEAD], sub, 120)

    # Ботинок: протектор и шнурки не дают резать его по линиям. Грани делятся по тому, куда смотрят
    # (шесть сторон), мелкие клочки сливаются с соседями: получается десяток ровных островов.
    for boot in (BOOT_L, BOOT_R):
        for f in by[boot]:
            n = (R @ f.normal).normalized()
            axis = max(range(3), key=lambda a: abs(n[a]))
            sub[f.index] = 1 + axis * 2 + (1 if n[axis] > 0 else 0)
        _clean_sub(by[boot], sub, 24)

    # Швы по границам частей и половин. Отдельные детали (подсумки, пряжка) режутся при развёртке.
    for e in bm.edges:
        if len(e.link_faces) == 2:
            f, g = e.link_faces
            if label[f.index] != PART and (label[f.index], sub[f.index]) != (label[g.index], sub[g.index]):
                e.seam = True

    def cut(name, start, goals, allowed, penalty=None):
        edges = _path(bm, P, start, goals, allowed, penalty)
        for e in edges:
            e.seam = True
        report.append(f"{name}: {len(edges)}")
        return edges

    waist = vs[TORSO] & vs[PANTS]
    neck = vs[TORSO] & vs[HEAD]
    centre = {i for i in vs[PANTS] if abs(P[i].x) <= 0.004}
    crotch = min(centre, key=lambda i: P[i].z)
    for arm, hand, boot, sign in ((ARM_L, HAND_L, BOOT_L, -1.0), (ARM_R, HAND_R, BOOT_R, 1.0)):
        side = "L" if sign < 0 else "R"
        joint = vs[arm] & vs[TORSO]
        low = min(joint, key=lambda i: P[i].z)       # где рука отходит от торса
        top = max(joint, key=lambda i: P[i].z)       # верх плеча
        prof = _profile(P, [i for i in vs[arm] if P[i].z < P[low].z])
        cut(f"arm inner {side}", low, vs[arm] & vs[hand], vs[arm],
            lambda i: 4.0 * max(0.0, abs(P[i].x) - prof(P[i].z)[0]) / 0.02)
        cut(f"torso side {side}", low, waist, vs[TORSO])
        cut(f"shoulder {side}", top, neck, vs[TORSO])
        leg = {i for i in vs[PANTS] if P[i].x * sign > 0.004}
        prof_leg = _profile(P, leg)
        cut(f"leg inner {side}", crotch, vs[PANTS] & vs[boot], leg | centre,
            lambda i: 4.0 * max(0.0, abs(P[i].x) - prof_leg(P[i].z)[0]) / 0.02)

    # Штаны: разрез по центру спереди и сзади (как шов и молния у комбинезона) — каждая штанина отдельным островом.
    front = min((i for i in waist if abs(P[i].x) < 0.012), key=lambda i: P[i].y)
    rear = max((i for i in waist if abs(P[i].x) < 0.012), key=lambda i: P[i].y)
    yc = P[crotch].y
    cut("pants centre front", front, {crotch}, {i for i in vs[PANTS] if P[i].y <= yc + 0.004}, lambda i: 20.0 * abs(P[i].x) / 0.02)
    cut("pants centre back", rear, {crotch}, {i for i in vs[PANTS] if P[i].y >= yc - 0.004}, lambda i: 20.0 * abs(P[i].x) / 0.02)

    # Голова: разрез по затылку и темени, от шеи до верхнего края лица.
    face_edge = {v.index for f in by[HEAD] if sub[f.index] == FACE for v in f.verts} & \
                {v.index for f in by[HEAD] if sub[f.index] != FACE for v in f.verts}
    back = max((i for i in neck if abs(P[i].x) < 0.012), key=lambda i: P[i].y)
    rest = {v.index for f in by[HEAD] if sub[f.index] != FACE for v in f.verts}
    cut("head top and back", back, {i for i in face_edge if P[i].z > cfg["face_z"][1] - 0.02}, rest, lambda i: 20.0 * abs(P[i].x) / 0.02)

    sl = bm.faces.layers.int.get(SUB) or bm.faces.layers.int.new(SUB)
    for f in bm.faces:
        f[sl] = sub[f.index]
    bm.to_mesh(me)
    bm.free()
    me.update()
    n = sum(1 for e in me.edges if e.use_seam)
    print("seam edges:", n, "| cuts:", "; ".join(report))
    return n


# ---------------------------------------------------------------------------------------------
# Развёртка и упаковка
# ---------------------------------------------------------------------------------------------

def _view3d():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                region = next(r for r in area.regions if r.type == "WINDOW")
                return dict(window=win, area=area, region=region)
    raise RuntimeError("нет окна 3D-вида")


def _uv_islands(bm, uv):
    """Острова развёртки: группы граней, соединённых общими рёбрами с совпадающими UV."""
    def joined(e, f, g):
        lf = next(l for l in f.loops if l.edge is e)
        lg = next(l for l in g.loops if l.edge is e)
        return ((lf[uv].uv - lg.link_loop_next[uv].uv).length < 1e-6 and
                (lf.link_loop_next[uv].uv - lg[uv].uv).length < 1e-6)
    seen, islands = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        group, stack = [f], [f]
        seen.add(f.index)
        while stack:
            x = stack.pop()
            for e in x.edges:
                for g in e.link_faces:
                    if g.index not in seen and joined(e, x, g):
                        seen.add(g.index)
                        group.append(g)
                        stack.append(g)
        islands.append(group)
    return islands


def _uv_area(f, uv, signed=False):
    pts = [l[uv].uv for l in f.loops]
    a = 0.0
    for i in range(1, len(pts) - 1):
        a += (pts[i] - pts[0]).cross(pts[i + 1] - pts[0]) / 2.0
    return a if signed else abs(a)


def unwrap(density=None, margin=0.004, rotate="ANY"):
    """Новая развёртка в слой UVMap по швам, плотность по частям, упаковка. Старый слой не трогается."""
    density = {**DENSITY, **(density or {})}
    o = _obj()
    me = o.data
    if NEW_UV in me.uv_layers:
        me.uv_layers.remove(me.uv_layers[NEW_UV])
    new = me.uv_layers.new(name=NEW_UV)
    me.uv_layers.active = new
    region = [d.value for d in me.attributes[REGION].data]

    def select(pred):
        bpy.ops.object.mode_set(mode="OBJECT")
        for p in me.polygons:
            p.select = pred(region[p.index])
        for e in me.edges:
            e.select = False
        for v in me.vertices:
            v.select = False
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")

    with bpy.context.temp_override(**_view3d()):
        auto = (PART,)                      # мелкие отдельные детали: проекция по углам граней
        select(lambda r: r not in auto)
        bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", fill_holes=True, correct_aspect=True, iterations=30,
                          no_flip=True, margin_method="FRACTION", margin=0.0)
        select(lambda r: r in auto)
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0, correct_aspect=True)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.average_islands_scale()

        # плотность по частям: остров растягивается вокруг своего центра
        bm = bmesh.from_edit_mesh(me)
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv[NEW_UV]
        lay = bm.faces.layers.int[REGION]
        sl = bm.faces.layers.int[SUB]
        for group in _uv_islands(bm, uv):
            k = FACE_DENSITY if (group[0][lay] == HEAD and group[0][sl] == FACE) else density[group[0][lay]]
            loops = [l for f in group for l in f.loops]
            cx = sum(l[uv].uv.x for l in loops) / len(loops)
            cy = sum(l[uv].uv.y for l in loops) / len(loops)
            for l in loops:
                l[uv].uv.x = cx + (l[uv].uv.x - cx) * k
                l[uv].uv.y = cy + (l[uv].uv.y - cy) * k
        bmesh.update_edit_mesh(me)
        bpy.ops.uv.pack_islands(rotate=True, rotate_method=rotate, scale=True, margin_method="FRACTION", margin=margin,
                                shape_method="CONCAVE")
        bpy.ops.object.mode_set(mode="OBJECT")
    return stats()


def stats(layer=NEW_UV):
    """Сколько места в текстуре у каждой части, относительная плотность и искажения."""
    o = _obj()
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv[layer]
    lay = bm.faces.layers.int[REGION]
    sl = bm.faces.layers.int.get(SUB)

    def key(f):
        return "face" if (sl and f[lay] == HEAD and f[sl] == FACE) else NAMES[f[lay]]
    islands = _uv_islands(bm, uv)
    per = collections.defaultdict(lambda: [0, 0.0, 0.0, 0])
    total3, totaluv, flipped, worst = 0.0, 0.0, 0, []
    for group in islands:
        ratios = []
        for f in group:
            a3, auv = f.calc_area(), _uv_area(f, uv, signed=True)
            s = per[key(f)]
            s[0] += 1
            s[1] += a3
            s[2] += abs(auv)
            total3 += a3
            totaluv += abs(auv)
            if a3 > 1e-12:
                ratios.append(abs(auv) / a3)
        signs = sum(1 for f in group if _uv_area(f, uv, signed=True) < 0)
        flipped += min(signs, len(group) - signs)
        per[key(group[0])][3] += 1
        if ratios:
            ratios.sort()
            med = ratios[len(ratios) // 2]
            lo, hi = ratios[int(len(ratios) * 0.05)], ratios[int(len(ratios) * 0.95)]
            worst.append((round(max(med / max(lo, 1e-12), hi / max(med, 1e-12)), 2), key(group[0]), len(group)))
    bm.free()
    out = {}
    for k, (n, a3, auv, isl) in sorted(per.items()):
        out[k] = dict(faces=n, islands=isl, uv_share=round(100 * auv / totaluv, 1),
                             density=round(math.sqrt((auv / totaluv) / (a3 / total3)), 2))
    worst.sort(reverse=True)
    print("islands:", len(islands), "| coverage: %.1f%%" % (100 * totaluv), "| flipped faces:", flipped)
    for k, v in out.items():
        print("  %-7s" % k, v)
    print("  largest area distortion inside one island (p95 / median):", worst[:8])
    return out


# ---------------------------------------------------------------------------------------------
# Перенос текстуры со старой развёртки на новую
# ---------------------------------------------------------------------------------------------

def bake(path, size=4096, margin=16, apply=True, name="basecolor_uv2"):
    """Запекает цвет исходной текстуры (по старой развёртке) в новую картинку по слою UVMap и сохраняет её в path.
    apply=True — после запекания материал переключается на новую картинку и новую развёртку.
    Исходный файл текстуры не изменяется."""
    o = _obj()
    me = o.data
    mat = o.active_material
    nt = mat.node_tree
    src = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and n.name != "UV2_TARGET")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    old_uv = next(u.name for u in me.uv_layers if u.name != NEW_UV)
    if src.image.name == name:
        raise RuntimeError("материал уже переключён на новую текстуру: запекать не из чего")

    # исходная текстура читается по старой развёртке явно
    uvn = nt.nodes.get("UV2_SOURCE_UV") or nt.nodes.new("ShaderNodeUVMap")
    uvn.name = "UV2_SOURCE_UV"
    uvn.uv_map = old_uv
    uvn.location = (src.location.x - 220, src.location.y)
    nt.links.new(uvn.outputs["UV"], src.inputs["Vector"])

    img = bpy.data.images.get(name)
    if img and tuple(img.size) != (size, size):
        bpy.data.images.remove(img)
        img = None
    img = img or bpy.data.images.new(name, size, size, alpha=False)
    tgt = nt.nodes.get("UV2_TARGET") or nt.nodes.new("ShaderNodeTexImage")
    tgt.name = "UV2_TARGET"
    tgt.image = img
    tgt.location = (src.location.x, src.location.y - 320)
    for n in nt.nodes:
        n.select = False
    tgt.select = True
    nt.nodes.active = tgt

    # цвет без света: на время запекания поверхность — чистое свечение цветом текстуры
    surface = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(src.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    scene = bpy.context.scene
    saved = (scene.render.engine, me.uv_layers.active.name)
    me.uv_layers.active = me.uv_layers[NEW_UV]
    for other in bpy.context.selected_objects:
        other.select_set(False)
    o.select_set(True)
    try:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 4
        scene.cycles.device = "CPU"
        scene.render.bake.margin = margin
        scene.render.bake.margin_type = "EXTEND"
        scene.render.bake.use_clear = True
        scene.render.bake.target = "IMAGE_TEXTURES"
        scene.render.bake.use_selected_to_active = False
        with bpy.context.temp_override(**_view3d()):
            bpy.ops.object.bake(type="EMIT")
    finally:
        nt.nodes.remove(emit)
        if surface:
            nt.links.new(surface, out.inputs["Surface"])
        scene.render.engine = saved[0]

    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    if apply:
        src.image = img
        uvn.uv_map = NEW_UV
        me.uv_layers[NEW_UV].active_render = True
        nt.nodes.remove(tgt)
    else:
        me.uv_layers.active = me.uv_layers[saved[1]]
    print("baked", size, "->", path, "| applied:", apply)
    return path
