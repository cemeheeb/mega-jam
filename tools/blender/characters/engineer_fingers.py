"""Пальцы героя: найти пальцы на меше кисти, поставить суставы костей по ним, раздать веса (фоновый Blender).

    B=/Applications/Blender.app/Contents/MacOS/Blender
    E=SourceArt/characters/engineer/source/engineer.blend
    $B -b $E --python tools/blender/characters/engineer_fingers.py -- analyse       # только найти суставы
    $B -b $E --python tools/blender/characters/engineer_fingers.py -- apply $E      # кости, веса, сохранить в тот же файл

Сделано один раз 15.11.2026 (решение автора: «оправь модель как надо»); на уже исправленном файле запускать не нужно:
кости встанут туда же, веса пересчитаются поверх. После — выгрузка source/export_engineer.py и импорт
tools/ue/import_engineer.py --mesh. Найденные суставы для проверки пишутся в joints.json рядом с blend-файлом.

Зачем: кисть меша Engineer_Body целиком висела на кости hand_* («пальцы не гнутся»), а кости пальцев манекена
в полтора раза длиннее пальцев героя. Что делает:
  1. Кончики пальцев — самые дальние от запястья точки поверхности кисти (по рёбрам сетки).
  2. Ось пальца — середины срезов его вершин вдоль хорды «основание — кончик». Связность не используется: у сетки
     Tripo соседние пальцы местами срослись боками. Длина пальца и доли фаланг — по пропорциям кисти.
  3. Кости: сустав переезжает на найденное место, ориентация кости довёрнута так, чтобы её ось «к следующему
     суставу» смотрела вдоль пальца героя. В Unreal у этих костей перенос «с анимации, в масштабе модели»:
     направление берётся из клипа манекена, длина — из этой модели, поэтому клипы гнут пальцы по тем же осям.
  4. Веса: вершины у ломаной суставов делят вес между костями пальца, у основания и вдали от оси — с кистью.
"""
import heapq
import json
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
MODE = argv[0]
FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
# Длина пальца от сустава основания до кончика в долях длины кисти (запястье — кончик среднего) и доли фаланг.
# У этой кисти пальцы длинные: при обычных долях (0,50 / 0,54 / 0,50 / 0,41) суставы основания садились на перепонку.
LENGTH = {"thumb": 0.34, "index": 0.575, "middle": 0.62, "ring": 0.575, "pinky": 0.47}
PARTS = {"thumb": [0.55, 0.45], "index": [0.46, 0.28, 0.26], "middle": [0.46, 0.28, 0.26], "ring": [0.46, 0.28, 0.26],
         "pinky": [0.45, 0.26, 0.29]}
CAPTURE = 0.013             # вершины ближе этого к хорде пальца (и ближе, чем к хордам соседей) — его
FULL, FADE = 0.012, 0.020   # вес пальца полный ближе FULL от ломаной суставов и сходит на нет к FADE
SMOOTH = 3                  # проходов сглаживания весов по рёбрам

arm = bpy.data.objects["root"]
body = bpy.data.objects["Engineer_Body"]
me = body.data
AW = arm.matrix_world


def chain(name, side):
    """Кости пальца от той, чья голова остаётся на месте, до последней фаланги."""
    return ([f"thumb_01_{side}", f"thumb_02_{side}", f"thumb_03_{side}"] if name == "thumb"
            else [f"{name}_metacarpal_{side}", f"{name}_01_{side}", f"{name}_02_{side}", f"{name}_03_{side}"])


def poly_near(p, line, lo=0.0, hi=1.0):
    """Ближайшая точка ломаной: (расстояние, длина вдоль ломаной). lo и hi — на сколько можно выйти за её концы."""
    best, s_at, acc = 1e9, 0.0, 0.0
    for k in range(len(line) - 1):
        ab = line[k + 1] - line[k]
        t = (p - line[k]).dot(ab) / max(ab.length_squared, 1e-12)
        t = max(lo if k == 0 else 0.0, min(hi if k == len(line) - 2 else 1.0, t))
        d = (p - (line[k] + ab * t)).length
        if d < best:
            best, s_at = d, acc + t * ab.length
        acc += ab.length
    return best, s_at


def analyse(side):
    """Суставы пальцев по мешу: {палец: {"joints": [основание, ..., кончик]}} в мировых осях, и вершины кисти."""
    gi = body.vertex_groups[f"hand_{side}"].index
    hand = [v.index for v in me.vertices if any(g.group == gi and g.weight > 0.3 for g in v.groups)]
    hset = set(hand)
    co = {i: body.matrix_world @ me.vertices[i].co for i in hand}
    adj = {i: [] for i in hand}
    for e in me.edges:
        a, b = e.vertices
        if a in hset and b in hset:
            d = (co[a] - co[b]).length
            adj[a].append((b, d))
            adj[b].append((a, d))
    # расстояние по поверхности от запястья
    wrist = AW @ arm.data.bones[f"hand_{side}"].head_local
    g = {i: 1e9 for i in hand}
    pq = []
    for s0 in sorted(hand, key=lambda i: (co[i] - wrist).length)[:25]:
        g[s0] = 0.0
        heapq.heappush(pq, (0.0, s0))
    while pq:
        d, u = heapq.heappop(pq)
        if d > g[u]:
            continue
        for v, w in adj[u]:
            if d + w < g[v]:
                g[v] = d + w
                heapq.heappush(pq, (d + w, v))
    maxima = [i for i in hand if all(g[i] >= g[j] for j, _ in adj[i]) and g[i] > 0.03]
    hand_len = max(g[i] for i in maxima)

    def bone(n):
        return AW @ arm.data.bones[f"{n}_{side}"].head_local

    # старые суставы стоят на своих пальцах (поперёк), хоть и не на месте (вдоль): по ним кончики раздаются пальцам
    prior = {f: (bone("thumb_02"), bone("thumb_03")) if f == "thumb" else (bone(f + "_01"), bone(f + "_03")) for f in FINGERS}

    def off_line(p, a, b):
        ab = (b - a).normalized()
        return ((p - a) - ab * (p - a).dot(ab)).length

    tips = {}
    for f in FINGERS:
        mine = [i for i in maxima if min(FINGERS, key=lambda q: off_line(co[i], *prior[q])) == f]
        assert mine, ("нет кончика", side, f)
        tips[f] = max(mine, key=lambda i: g[i])

    def chord_near(p, a, b):
        ab = b - a
        t = max(-0.3, min(1.0, (p - a).dot(ab) / ab.length_squared))
        return (p - (a + ab * t)).length, t

    out = {}
    chord = {f: (prior[f][0], co[tips[f]]) for f in FINGERS}
    for _ in range(2):      # второй проход — уже от найденного основания
        for f in FINGERS:
            a, b = chord[f]
            own = []
            for i in hand:
                d, t = chord_near(co[i], a, b)
                if d < CAPTURE and t > -0.25 and all(chord_near(co[i], *chord[q])[0] >= d for q in FINGERS if q != f):
                    own.append((t, i))
            centres = []
            n = 7
            for k in range(n):
                pts = [co[i] for t, i in own if k / n <= max(t, 0.0) < (k + 1) / n]
                if len(pts) >= 3:
                    centres.append(sum(pts, Vector()) / len(pts))
            centres.append(co[tips[f]])
            total = LENGTH[f] * hand_len
            # от кончика назад по осевой линии на длину пальца
            rev = centres[::-1]
            acc, line = 0.0, None
            for k in range(len(rev) - 1):
                d = (rev[k + 1] - rev[k]).length
                if acc + d >= total:
                    line = [rev[k] + (rev[k + 1] - rev[k]) * ((total - acc) / d)] + rev[k::-1]
                    break
                acc += d
            if line is None:
                # осевая линия короче пальца (у основания вершины уже ладони): продолжить назад по общему направлению
                back = (rev[-1] - rev[0]).normalized()
                line = [rev[-1] + back * (total - acc)] + centres

            def at(s1, line=line):
                for k in range(len(line) - 1):
                    d = (line[k + 1] - line[k]).length
                    if s1 <= d or k == len(line) - 2:
                        return line[k] + (line[k + 1] - line[k]) * min(1.0, s1 / max(d, 1e-9))
                    s1 -= d

            joints, s_at = [line[0]], 0.0
            for part in PARTS[f][:-1]:
                s_at += part * total
                joints.append(at(s_at))
            joints.append(co[tips[f]])
            out[f] = {"joints": joints, "total": total, "own": len(own)}
            chord[f] = (joints[0], joints[-1])
    for f in FINGERS:
        J = out[f]["joints"]
        print("FINGER %s %-6s verts %3d length %.1f cm phalanges %s" % (side, f, out[f]["own"], out[f]["total"] * 100,
              " ".join("%.1f" % ((J[k + 1] - J[k]).length * 100) for k in range(len(J) - 1))))
    print("HAND %s length %.1f cm" % (side, hand_len * 100))
    return out, co


def set_bones(side, fingers):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    inv = AW.inverted()
    for name, f in fingers.items():
        names = chain(name, side)
        targets = [inv @ p for p in f["joints"]]            # суставы и кончик в осях арматуры
        old_head = {n: eb[n].head.copy() for n in names}
        old_rot = {n: eb[n].matrix.to_3x3() for n in names}
        # ось «к следующему суставу» у каждой кости в её собственных осях (у последней — как у родителя)
        along = {}
        for k, n in enumerate(names):
            if k + 1 < len(names):
                along[n] = (old_rot[n].inverted() @ (old_head[names[k + 1]] - old_head[n])).normalized()
            else:
                along[n] = along[names[k - 1]]
        pos = [old_head[names[0]]] + targets                 # голова первой кости цепочки остаётся на месте
        for k, n in enumerate(names):
            d_old = (old_rot[n] @ along[n]).normalized()
            d_new = (pos[k + 1] - pos[k]).normalized()
            swing = d_old.rotation_difference(d_new).to_matrix()
            length = eb[n].length
            m = (swing @ old_rot[n]).to_4x4()
            m.translation = pos[k]
            eb[n].matrix = m
            eb[n].length = length
    bpy.ops.object.mode_set(mode="OBJECT")


def set_weights(side, fingers, co):
    hand_g = body.vertex_groups[f"hand_{side}"]
    count = {}
    for i, p in co.items():
        d, f = min((poly_near(p, fingers[q]["joints"], -0.35, 1.25)[0], q) for q in fingers)
        if d > FADE:
            continue
        J = fingers[f]["joints"]
        _, s_at = poly_near(p, J, -0.35, 1.25)
        seg = [(J[k + 1] - J[k]).length for k in range(len(J) - 1)]
        names = chain(f, side)[1:]                           # кости, которые гнут палец
        bounds = [0.0]
        for L in seg:
            bounds.append(bounds[-1] + L)
        blend = 0.3 * min(seg)
        w = []
        for k in range(len(names)):
            a = min(1.0, max(0.0, (s_at - (bounds[k] - blend)) / (2 * blend))) if k > 0 else 1.0
            b = min(1.0, max(0.0, ((bounds[k + 1] + blend) - s_at) / (2 * blend))) if k < len(names) - 1 else 1.0
            w.append(a * b)
        base = min(1.0, max(0.0, (s_at + 0.2 * seg[0]) / (0.55 * seg[0])))   # за суставом основания — кисть, дальше плавно палец
        base *= min(1.0, max(0.0, (FADE - d) / (FADE - FULL)))               # далеко от оси пальца — тоже кисть
        total = sum(w)
        if base <= 0.001 or total <= 0.0:
            continue
        hand_g.add([i], 1.0 - base, "REPLACE")
        for n, x in zip(names, w):
            grp = body.vertex_groups.get(n) or body.vertex_groups.new(name=n)
            grp.add([i], x / total * base, "REPLACE")
        count[f] = count.get(f, 0) + 1
    # Сглаживание по рёбрам сетки: у соседних вершин веса близкие, иначе при сгибе торчат отдельные вершины
    # и рвутся перемычки между сросшимися пальцами.
    groups = [hand_g] + [body.vertex_groups[n] for f in fingers for n in chain(f, side)[1:] if body.vertex_groups.get(n)]
    gidx = {g.index: k for k, g in enumerate(groups)}
    w = {i: [0.0] * len(groups) for i in co}
    for i in co:
        for g in me.vertices[i].groups:
            if g.group in gidx:
                w[i][gidx[g.group]] = g.weight
    nb = {i: [] for i in co}
    for e in me.edges:
        a, b = e.vertices
        if a in nb and b in nb:
            nb[a].append(b)
            nb[b].append(a)
    for _ in range(SMOOTH):
        new = {}
        for i in co:
            if not nb[i]:
                new[i] = w[i]
                continue
            avg = [sum(w[j][k] for j in nb[i]) / len(nb[i]) for k in range(len(groups))]
            new[i] = [0.5 * w[i][k] + 0.5 * avg[k] for k in range(len(groups))]
        w = new
    for i in co:
        total = sum(w[i])
        if total <= 0.0:
            continue
        for k, g in enumerate(groups):
            x = w[i][k] / total
            if x > 0.002:
                g.add([i], x, "REPLACE")
            elif k > 0:
                g.remove([i])
    print("WEIGHTS", side, count)


dump = {}
for side in ("r", "l"):
    fingers, co = analyse(side)
    dump[side] = {n: {"joints": [list(p) for p in f["joints"]]} for n, f in fingers.items()}
    if MODE == "apply":
        set_bones(side, fingers)
        set_weights(side, fingers, co)
json.dump(dump, open(bpy.path.abspath("//joints.json"), "w"))
if MODE == "apply" and len(argv) > 1:
    bpy.ops.wm.save_as_mainfile(filepath=argv[1], copy=False)
    print("SAVED", argv[1])
