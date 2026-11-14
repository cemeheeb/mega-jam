"""Ceiling tiles (SourceArt/environment/common/ceiling-tiles), built from the author's reference picture of 15.11
(source/ceiling-tiles-1.png). There is no Tripo mesh: the sizes come from the recipe (75 x 75 cm, 5 cm thick), the
proportions of the details are measured on the picture.

Run in the live Blender (MCP): exec(open(<this file>).read()). Millimetres, scaled to metres at build.
Blender axes: the face looks up (+Z), as in the picture; in the game it looks down (the panels go on upside down,
like the ceiling lamps in build_rooms.py). Origin: the middle of the face, the panel goes down to z = -50 mm.

Objects (collection CeilingTiles, one material CeilingTiles), in a row along X as in the picture:
- CeilingTile: plain, a square inset pressed 2 mm deep with 45 degree walls;
- CeilingTileLight: a frosted diffuser (zone frosted) in a graphite gasket;
- CeilingTileVent: the same gasket around a plenum 40 mm deep, 13 tilted graphite louvres on a middle rib;
- CeilingTileHatch: access hatch: an orange seam groove, a quarter-turn latch (aluminium bar in a graphite cup with an
  aluminium bezel) and a blank graphite label plate in a shallow pocket.
Common frame: plan corners R 8, top edge rounded R 5, bottom edge R 3, two seam grooves round the sides (three
stacked plates in the picture), a button-head screw with a hex socket in a counterbore in every corner.

Flat faces with holes are filled by bridge(): two closed loops walked by angle, triangles merged into convex quads;
every loop shares its points with the walls next to it, so there are no T-junctions. UV of the face is (x, y), one
island with the top rounding of the edge. The back and the sides are hidden on the ceiling: UV x 0.25.
"""
import bpy, importlib, sys
from math import sin, cos, pi, radians, atan2, tau
from mathutils import Vector, Matrix

KIT_DIR = '/Users/cemeheeb/Projects/ludum-dare/tools/blender/kit'
if KIT_DIR not in sys.path:
    sys.path.insert(0, KIT_DIR)
import kit_lib
importlib.reload(kit_lib)
from kit_lib import B, I4, T, frame, rr, bevel, build

KIT = 'CeilingTiles'
col = bpy.data.collections.get(KIT) or bpy.data.collections.new(KIT)
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
mat = bpy.data.materials.get(KIT) or bpy.data.materials.new(KIT)
MM = 0.001

# ---------------- measurements, mm ----------------
S = 750                  # panel size: the 75 cm grid of the wall columns
H2 = S / 2
THICK = 50
R_PLAN = 8               # plan corner radius
B_TOP, B_BOT = 5, 3      # rounded top and bottom edges
CAP = H2 - B_TOP         # 370: the flat face ends here
CORNER = H2 - R_PLAN     # 367: centre of the plan corner arcs, the same for every inset
SEAMS = (26, 38)         # side seam grooves, depth below the face
SEAM_D = 1.2             # groove depth; 1 mm half height
SCREW = H2 - 38          # 337: screw centres
CB_R, CB_D = 16, 4       # counterbore radius and depth (about 32 mm across in the picture)
HEAD_R = 11.5            # button head
HEX_R = 3.5
BLOCK = 304              # inner corner of the square around a screw
BLOCK_HATCH = 316        # the hatch groove comes closer: the corner must stay outside its rounded corner
ROW = 850                # spacing in the row
UV_HIDDEN = 0.25

INSET = (275, 16)        # CeilingTile: pressed inset, half size and corner radius
OPENING = (295, 26)      # light and vent: opening in the face
GASKET = [(0, 0), (0, -4), (2, -4), (2, -2.5), (19, -2.5), (21, -4.5)]   # (inset, z): gap, gasket 17 mm wide
LOUVRES = 13
BLADE = (30, 3, 1.2, -40, -9)    # width, thickness, edge radius, tilt (degrees; faces +Y as in the picture), top z
PLENUM = -40
GROOVE = (319, 30, 8, 1.5)       # hatch seam: half size, corner radius, width, depth
SPLIT_X = -15                    # the hatch door face is filled in two cells, latch | label
LATCH = (-190, 35)               # latch centre
LATCH_R, CUP_R, CUP_D = 75, 65, 25
BAR = (124, 26, 4, 78)           # bar handle: length, width, plan radius, angle (degrees)
LABEL = (175, -230, 180, 60, 6)  # label pocket: centre x, y, width, height, corner radius

PROF = (bevel(-THICK, B_BOT, up=False) + [(0, -THICK + B_BOT)]
        + [p for s in sorted(SEAMS, reverse=True) for p in ((0, -s - 1), (SEAM_D, -s), (0, -s + 1))]
        + [(0, -B_TOP)] + bevel(0, B_TOP))
SPLIT0, SPLIT1 = 3, len(PROF) - 4          # the bottom rounding unfolds with the back, the top one with the face


# ---------------- helpers ----------------
def rrs(hw, hh, R, seg, st=((), (), (), ())):
    """kit_lib.rr with extra points on the straight sides: st = (right: y, top: x, left: y, bottom: x), absolute
    coordinates along the side, the same for every inset (the arc centres do not move with the inset)."""
    pts = []
    cs = [(hw - R, -hh + R, -90), (hw - R, hh - R, 0), (-hw + R, hh - R, 90), (-hw + R, -hh + R, 180)]
    for k, (cx, cy, a) in enumerate(cs):
        for j in range(seg + 1):
            t = radians(a + 90 * j / seg)
            pts.append((cx + R * cos(t), cy + R * sin(t)))
        if k == 0:
            pts += [(hw, y) for y in sorted(st[0])]
        elif k == 1:
            pts += [(x, hh) for x in sorted(st[1], reverse=True)]
        elif k == 2:
            pts += [(-hw, y) for y in sorted(st[2], reverse=True)]
        else:
            pts += [(x, -hh) for x in sorted(st[3])]
    return pts


def circle(c, r, n, a0=0.0):
    return [(c[0] + r * cos(a0 + i * tau / n), c[1] + r * sin(a0 + i * tau / n)) for i in range(n)]


def area(P):
    return 0.5 * sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))


def convex(q):
    for i in range(len(q)):
        a, b_, c = q[i - 1], q[i], q[(i + 1) % len(q)]
        if (b_[0] - a[0]) * (c[1] - b_[1]) - (b_[1] - a[1]) * (c[0] - b_[0]) <= 1e-6:
            return False
    return True


STATS = {'faces': 0, 'bad': 0, 'area_err': 0.0}


def bridge(b, outer, inner, z, isl, zone, c=(0, 0), uvf=None, M=I4):
    """Flat faces at height z between two closed CCW loops, both star-shaped around c: the loops are walked by angle
    around c, a triangle each time one of them advances; neighbouring triangles become a quad where it is convex."""
    uvf = uvf or (lambda p: p)
    ang = lambda p: atan2(p[1] - c[1], p[0] - c[0])
    a0 = ang(outer[0])

    def walk(L, start):
        L = L[start:] + L[:start]
        A = [a0 + ((ang(L[0]) - a0 + pi) % tau) - pi]
        for p in L[1:]:
            x = ang(p)
            while x < A[-1]:
                x += tau
            while x - A[-1] > tau:
                x -= tau
            A.append(x)
        return L + [L[0]], A + [A[0] + tau]

    O, A = walk(outer, 0)
    k = min(range(len(inner)), key=lambda i: abs(((ang(inner[i]) - a0 + pi) % tau) - pi))
    I, Bn = walk(inner, k)
    n, m = len(O) - 1, len(I) - 1
    steps, i, j = [], 0, 0
    while i < n or j < m:
        go = j >= m or (i < n and A[i + 1] <= Bn[j + 1])
        if i < n and j < m:     # near a corner of a long hole the angle rule can fold a triangle: take the other step
            to = area([O[i], O[i + 1], I[j]])
            ti = area([O[i], I[j + 1], I[j]])
            if go and to <= 1e-6 < ti:
                go = False
            elif not go and ti <= 1e-6 < to:
                go = True
        if go:
            steps.append(('o', i, j))
            i += 1
        else:
            steps.append(('i', i, j))
            j += 1
    faces, s = [], 0
    while s < len(steps):
        t, i, j = steps[s]
        if s + 1 < len(steps) and steps[s + 1][0] != t:
            q = [O[i], O[i + 1], I[j + 1], I[j]]
            if convex(q):
                faces.append(q)
                s += 2
                continue
        faces.append([O[i], O[i + 1], I[j]] if t == 'o' else [O[i], I[j + 1], I[j]])
        s += 1
    tot = 0.0
    for f in faces:
        a = area(f)
        tot += a
        STATS['faces'] += 1
        if a <= 1e-6:
            STATS['bad'] += 1
        b.face(M, [(x, y, z) for x, y in f], [uvf(p) for p in f], isl, zone)
    STATS['area_err'] = max(STATS['area_err'], abs(tot - (area(outer) - area(inner))))


def shell(b, M, shape, prof, zones, cap0=True, cap1=True, cap1_zone=None):
    """navigator_build.shell without cuts: outline shape(d) through (inset, z) levels; flat steps and caps are
    projected exactly, walls and roundings are straight strips at their mean inset."""
    m = len(prof)
    if isinstance(zones, str):
        zones = [zones] * (m - 1)
    O = [shape(d) for d, z in prof]
    N = len(O[0])
    V = lambda j, i: (O[j][i % N][0], O[j][i % N][1], prof[j][1])
    kind = ['flat' if abs(prof[j + 1][1] - prof[j][1]) < 1e-9 else 'wall' for j in range(m - 1)]
    groups = []
    for j in range(m - 1):
        if groups and groups[-1][0] == kind[j]:
            groups[-1][2] = j + 1
        else:
            groups.append([kind[j], j, j + 1])
    flat_uv = lambda p, up: (p[0], p[1]) if up else (-p[0], p[1])
    isl0 = b.isl() if cap0 else None
    if cap0:
        idx = list(range(N))[::-1]
        b.face(M, [V(0, i) for i in idx], [flat_uv(V(0, i), False) for i in idx], isl0, zones[0])
    last = None
    for g, (k, j0, j1) in enumerate(groups):
        if k == 'flat':
            up = prof[j1][0] > prof[j0][0]
            isl = isl0 if (g == 0 and cap0 and not up) else b.isl()
            for j in range(j0, j1):
                for i in range(N):
                    q = [V(j, i), V(j, i + 1), V(j + 1, i + 1), V(j + 1, i)]
                    b.face(M, q, [flat_uv(p, up) for p in q], isl, zones[j])
            last = (isl, up)
        else:
            dm = sum(prof[j][0] for j in range(j0, j1 + 1)) / (j1 - j0 + 1)
            ref = shape(dm)
            per = [0.0]
            for i in range(N):
                per.append(per[-1] + (Vector(ref[(i + 1) % N]) - Vector(ref[i])).length)
            vs = [0.0]
            for j in range(j0, j1):
                vs.append(vs[-1] + (Vector(prof[j + 1]) - Vector(prof[j])).length)
            isl = b.isl()
            for j in range(j0, j1):
                for i in range(N):
                    q = [V(j, i), V(j, i + 1), V(j + 1, i + 1), V(j + 1, i)]
                    t0, t1 = vs[j - j0], vs[j + 1 - j0]
                    b.face(M, q, [(per[i], t0), (per[i + 1], t0), (per[i + 1], t1), (per[i], t1)], isl, zones[j])
            last = None
    if cap1:
        isl = last[0] if last and last[1] else b.isl()
        b.face(M, [V(m - 1, i) for i in range(N)], [flat_uv(V(m - 1, i), True) for i in range(N)], isl,
               cap1_zone or zones[-1])


def slab_yz(b, poly, x0, x1, zone):
    """Polygon in world YZ, thickness along X (navigator_build.slab_yz)."""
    b.slab(T((x0 + x1) / 2, 0, 0) @ frame((0, 1, 0), (1, 0, 0), (0, 0, -1)), [(y, -z) for y, z in poly], x1 - x0, zone)


def to_metres(b):
    b.F = [([p * MM for p in pts], [(u * MM, v * MM) for u, v in uvs], isl, zone, soft) for pts, uvs, isl, zone, soft in b.F]


# ---------------- the frame: corners with screws ----------------
def corner_block(block):
    """Top right corner: the flat face between the square around the screw and its counterbore, CCW, with a point
    wherever a 15 degree ray from the screw centre meets a straight side (so the counterbore circle bridges evenly).
    Returns the polygon, the stations on the outer sides and the inner chain (the sides facing the middle)."""
    arc = [(CORNER + (R_PLAN - B_TOP) * cos(radians(30 * j)), CORNER + (R_PLAN - B_TOP) * sin(radians(30 * j))) for j in range(4)]
    base = [(block, block), (CAP, block)] + arc + [(block, CAP)]
    out = []
    for e in range(len(base)):
        p, q = Vector(base[e]), Vector(base[(e + 1) % len(base)])
        out.append(tuple(p))
        if 2 <= e <= 4:          # arc edges: no extra points, the frame's prism has none there
            continue
        d = q - p
        hits = []
        for k in range(24):
            r = Vector((cos(radians(15 * k)), sin(radians(15 * k))))
            den = r.x * d.y - r.y * d.x
            if abs(den) < 1e-12:
                continue
            w = p - Vector((SCREW, SCREW))
            t = (r.y * w.x - r.x * w.y) / den      # along the edge: p + d t = screw + r s
            s = (d.y * w.x - d.x * w.y) / den      # along the ray
            if s > 0 and 1e-4 < t < 1 - 1e-4 and min((p + d * t - p).length, (p + d * t - q).length) > 0.05:
                hits.append(t)
        out += [tuple(p + d * t) for t in sorted(hits)]
    st = sorted({round(y, 6) for x, y in out if abs(x - CAP) < 1e-6 and y < CORNER - 1e-6})
    chain = sorted([p for p in out if abs(p[1] - block) < 1e-6], key=lambda p: -p[0])
    chain += sorted([p for p in out if abs(p[0] - block) < 1e-6 and p[1] > block + 1e-6], key=lambda p: p[1])
    return out, st, chain


def corners(block):
    """Blocks of the four corners (CCW each), the stations of the frame sides and the notched loop round the
    middle of the face (CCW)."""
    P, st, chain = corner_block(block)
    st = sorted(set(st) | {-y for y in st})
    mir = [(1, 1), (-1, 1), (-1, -1), (1, -1)]         # TR, TL, BL, BR: counter-clockwise
    blocks, loop = [], []
    for sx, sy in mir:
        flip = sx * sy < 0
        q = [(sx * x, sy * y) for x, y in P]
        ch = [(sx * x, sy * y) for x, y in chain]
        if flip:
            q.reverse()
            ch.reverse()
        blocks.append(((sx * SCREW, sy * SCREW), q))
        loop += ch
    return blocks, st, loop


def screw(b, c):
    """Counterbore, button head and hex socket at c (24 segments, angles of 15 degrees like the block rays)."""
    M = T(c[0], c[1], 0)
    shell(b, M, lambda d: circle((0, 0), CB_R - d, 24), [(0, 0), (0, -CB_D), (CB_R - HEAD_R, -CB_D)], 'white',
          cap0=False, cap1=False)
    top = b.n + 1
    b.lathe(M, 24, [('strip', [(HEAD_R, -CB_D), (HEAD_R, -2.6)], 'aluminium'),
                    ('polar', [(HEAD_R, -2.6), (HEAD_R - 0.134, -2.1), (HEAD_R - 0.5, -1.734), (HEAD_R - 1, -1.6)],
                     'aluminium', 'end')])
    hexagon = lambda d: circle((0, 0), HEX_R - d, 6, pi / 2)
    # the flat top continues the polar ring of the lathe: uv = position turned by -90 degrees (lathe a0 = 90)
    bridge(b, circle((0, 0), HEAD_R - 1, 24, pi / 2), hexagon(0), -1.6, top, 'aluminium', uvf=lambda p: (p[1], -p[0]), M=M)
    shell(b, M, hexagon, [(0, -1.6), (0, -3.4)], 'graphite', cap0=False, cap1=True)


def frame_panel(block, middle, st_extra=None):
    """Body of a panel with the four screws; the face is bridged from the notched loop to `middle` (CCW loop).
    Returns the builder, the hidden islands and the island of the face."""
    b = B()
    blocks, st, loop = corners(block)
    shape = lambda d: rrs(H2 - d, H2 - d, R_PLAN - d, 3, (st, st, st, st))
    i0, i1, i2 = b.prism(I4, S, S, R_PLAN, 3, PROF, 'white', split0=SPLIT0, split1=SPLIT1, cap0=True, cap1=False,
                         shape=shape)
    for c, P in blocks:
        bridge(b, P, circle(c, CB_R, 24), 0, i2, 'white', c=c)
    f0 = len(b.F)
    screw(b, blocks[0][0])
    f1 = len(b.F)
    for c, P in blocks[1:]:
        b.copy(f0, f1, T(c[0] - blocks[0][0][0], c[1] - blocks[0][0][1], 0))
    bridge(b, loop, middle, 0, i2, 'white')
    return b, [i0, i1], i2


PARTS = []


# ---------------- CeilingTile: plain, pressed inset ----------------
h, r = INSET
inset = lambda d: rr(2 * (h - d), 2 * (h - d), r - d, 3)
b, hid, top = frame_panel(BLOCK, inset(0))
shell(b, I4, inset, [(0, 0), (2, -2)], 'white', cap0=False, cap1=True)
PARTS.append(('CeilingTile', b, hid))


# ---------------- CeilingTileLight and CeilingTileVent: gasket in an opening ----------------
h, r = OPENING
opening = lambda d: rr(2 * (h - d), 2 * (h - d), r - d, 3)
GZ = ['white'] + ['graphite'] * (len(GASKET) - 2)

b, hid, top = frame_panel(BLOCK, opening(0))
gi = GASKET[-1][0]                              # inner edge of the gasket
shell(b, I4, opening, GASKET + [(gi, -5)], GZ + ['graphite'], cap0=False, cap1=True, cap1_zone='frosted')
PARTS.append(('CeilingTileLight', b, hid))

b, hid, top = frame_panel(BLOCK, opening(0))
shell(b, I4, opening, GASKET + [(gi, PLENUM)], GZ + ['graphite'], cap0=False, cap1=True)
half = h - gi                                   # 274: the plenum walls
bw, bt, br, tilt, btop = BLADE
pitch = 2 * half / LOUVRES
rot = Matrix.Rotation(radians(tilt), 2)
sect = [rot @ Vector(p) for p in rr(bw, bt, br, 3)]
zc = btop - max(p.y for p in sect)              # blade centre: its top edge at btop
f0 = len(b.F)
slab_yz(b, [(p.x - half + pitch / 2, p.y + zc) for p in sect], -half - 0.5, half + 0.5, 'graphite')
f1 = len(b.F)
for k in range(1, LOUVRES):
    b.copy(f0, f1, T(0, k * pitch, 0))
slab_yz(b, [(-half - 0.5, PLENUM), (half + 0.5, PLENUM), (half + 0.5, btop - 4), (-half - 0.5, btop - 4)], -1.5, 1.5, 'graphite')
PARTS.append(('CeilingTileVent', b, hid))


# ---------------- CeilingTileHatch: seam groove, latch, label ----------------
gh, gr, gw, gd = GROOVE
# points every 55 mm along the sides and the split line: a long bare side next to the latch would let the bridge
# fan across the hole
EVEN = [55 * k for k in range(-5, 6)]
groove = lambda d: rrs(gh - d, gh - d, gr - d, 3, (EVEN, EVEN + [SPLIT_X], EVEN, EVEN + [SPLIT_X]))
b, hid, top = frame_panel(BLOCK_HATCH, groove(0))
shell(b, I4, groove, [(0, 0), (0, -gd), (gw, -gd), (gw, 0)], 'orange', cap0=False, cap1=False)

door = groove(gw)
it = next(i for i, p in enumerate(door) if abs(p[0] - SPLIT_X) < 1e-6 and p[1] > 0)
ib = next(i for i, p in enumerate(door) if abs(p[0] - SPLIT_X) < 1e-6 and p[1] < 0)
left = door[it:ib + 1] if it < ib else door[it:] + door[:ib + 1]
right = door[ib:it + 1] if ib < it else door[ib:] + door[:it + 1]
left += [(SPLIT_X, y) for y in EVEN]                 # up the split line
right += [(SPLIT_X, y) for y in EVEN[::-1]]          # and down it

lx, ly = LATCH
bridge(b, left, circle(LATCH, LATCH_R, 32, pi / 2), 0, top, 'white', c=LATCH)
b.lathe(T(lx, ly, 0), 32, [
    ('strip', [(LATCH_R, 0), (LATCH_R, -3)], 'white'),
    ('polar', [(LATCH_R, -3), (LATCH_R - 1, -3)], 'graphite', 'end'),
    ('strip', [(LATCH_R - 1, -3), (LATCH_R - 1, 0)], 'aluminium'),
    ('polar', [(74, 0), (73.866, 0.5), (73.5, 0.866), (73, 1), (66, 1), (65.5, 0.866), (65.134, 0.5), (CUP_R, 0)],
     'aluminium', 'end'),
    ('strip', [(CUP_R, 0), (CUP_R, -CUP_D)], 'graphite'),
    ('polar', [(CUP_R, -CUP_D), (0, -CUP_D)], 'graphite', 'end')])
bl, bw_, bR, ba = BAR
b.prism(T(lx, ly, 0) @ Matrix.Rotation(radians(ba), 4, 'Z'), bl, bw_, bR, 3,
        [(0, -CUP_D), (0, -1.5)] + bevel(0, 1.5), 'aluminium', split0=0, split1=1, cap0=False, cap1=True)

cx, cy, lw, lh, lr = LABEL
lst = (-60, -30, 0, 30, 60)
label = lambda d: rrs(lw / 2 - d, lh / 2 - d, lr - d, 3, ((), lst, (), lst))
bridge(b, right, [(x + cx, y + cy) for x, y in label(0)], 0, top, 'white', c=(cx, cy))
shell(b, T(cx, cy, 0), label, [(0, 0), (0, -1.5)], 'white', cap0=False, cap1=True, cap1_zone='graphite')
PARTS.append(('CeilingTileHatch', b, hid))


# ---------------- build ----------------
HIDDEN = {}
objs = {}
for k, (name, b, hid) in enumerate(PARTS):
    for n_, (pts, uvs, isl, zone, soft) in enumerate(b.F):
        if isl in hid:
            b.F[n_] = (pts, [(u * UV_HIDDEN, v * UV_HIDDEN) for u, v in uvs], isl, zone, soft)
    HIDDEN[name] = hid
    to_metres(b)
    ob = build(name, b, Vector(((k - 1.5) * ROW, 0, THICK)) * MM, col, mat)
    objs[name] = ob
    me = ob.data
    print(name, 'faces', len(me.polygons), 'tris', sum(len(p.vertices) - 2 for p in me.polygons), 'islands', b.n,
          'dims mm', [round(d * 1000, 1) for d in ob.dimensions])
bpy.context.scene['kit_hidden'] = HIDDEN
print('bridge faces', STATS['faces'], 'non-positive', STATS['bad'], 'worst area error mm2', round(STATS['area_err'], 4))
