"""Герой: сгладить веса на шве «корпус — рукав» под мышками (фоновый Blender).

    B=/Applications/Blender.app/Contents/MacOS/Blender
    E=SourceArt/characters/engineer/source/engineer.blend
    $B -b $E --python tools/blender/characters/engineer_armpit.py -- check        # только посчитать
    $B -b $E --python tools/blender/characters/engineer_armpit.py -- apply $E     # сгладить и сохранить

Зачем: у сетки Tripo рукава срослись с боками, а веса переносились с манекена по ближайшей поверхности. На высоте
подмышки соседние вершины шва через одну привязаны то целиком к спине (spine_03/04), то целиком к плечу
(upperarm_twist_01/02): разница весов у соседей около 0,5. Пока рука висит, этого не видно; в стойке и на замахе
плечо уходит, и шов рвётся зубцами — тёмный пучок под мышкой (замечание автора 15.11).
Правка: вершины, у которых веса резко отличаются от соседей (JUMP), и их окрестность в RINGS колец сглаживаются
по рёбрам ITERATIONS раз — переход от корпуса к рукаву становится плавным, шов тянется, а не рвётся.
Прежде пробовал отбирать вершины по расстоянию от оси предплечья — рукав у локтя широкий, порог резал сам рукав.
"""
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
JUMP = 0.22         # насколько веса вершины отличаются от среднего по соседям (0 — как у соседей, 1 — совсем другие)
RINGS = 3
ITERATIONS = 10
body = bpy.data.objects["Engineer_Body"]
me = body.data
names = {g.index: g.name for g in body.vertex_groups}
W = [dict((g.group, g.weight) for g in v.groups if g.weight > 0.0005) for v in me.vertices]
nb = [[] for _ in me.vertices]
for e in me.edges:
    a, b = e.vertices
    nb[a].append(b)
    nb[b].append(a)


def jump(i):
    if not nb[i]:
        return 0.0
    keys = set(W[i])
    for j in nb[i]:
        keys |= set(W[j])
    return 0.5 * sum(abs(W[i].get(k, 0.0) - sum(W[j].get(k, 0.0) for j in nb[i]) / len(nb[i])) for k in keys)


def in_region(i):
    # полоса подмышек: по бокам корпуса на высоте от локтя до плеча
    p = body.matrix_world @ me.vertices[i].co
    return 0.14 < abs(p.x) < 0.32 and 1.12 < p.z < 1.40


region = [i for i in range(len(me.vertices)) if in_region(i)]
seeds = [i for i in region if jump(i) > JUMP]
zone = set(seeds)
for _ in range(RINGS):
    zone |= {j for i in zone for j in nb[i]}
print("ARMPIT before: %d vertices with a jump over %.2f (max %.2f); zone %d vertices" % (
    len(seeds), JUMP, max((jump(i) for i in seeds), default=0.0), len(zone)))
if argv[0] == "apply":
    for _ in range(ITERATIONS):
        new = {}
        for i in zone:
            keys = set(W[i])
            for j in nb[i]:
                keys |= set(W[j])
            new[i] = {k: 0.5 * W[i].get(k, 0.0) + 0.5 * sum(W[j].get(k, 0.0) for j in nb[i]) / len(nb[i]) for k in keys}
        for i, w in new.items():
            W[i] = w
    for i in zone:
        w = {k: x for k, x in W[i].items() if x > 0.01}
        total = sum(w.values())
        for g in list(me.vertices[i].groups):
            if g.group not in w:
                body.vertex_groups[g.group].remove([i])
        for k, x in w.items():
            body.vertex_groups[k].add([i], x / total, "REPLACE")
        W[i] = {k: x / total for k, x in w.items()}
    left = [i for i in region if jump(i) > JUMP]
    print("ARMPIT after: %d vertices with a jump over %.2f (max %.2f)" % (len(left), JUMP, max((jump(i) for i in region), default=0.0)))
    bpy.ops.wm.save_as_mainfile(filepath=argv[1], copy=False)
    print("SAVED", argv[1])
