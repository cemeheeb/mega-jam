"""Bridge dais (SourceArt/environment/bridge/bridge-dais): the low round raised floor under the captain's couch,
built from primitives after the approved picture source/bridge-dais-1.webp (pipeline/kit.md, step 2).

Run in the live Blender (MCP): exec(open(<this file>).read()). Millimetres, scaled to metres at build.
Blender axes: Z up, origin in the middle of the bottom. South, the walk-up side with the passage to the couch, is -X
(Unreal takes (x, -y, z) * 100, so -X stays south with yaw 0). Size of the grey cylinder it replaces (build_rooms.py
bridge, Post_Dais): 2400 mm across, 120 mm high. The picture is about 300 mm high at that width; the author kept 120,
so the side is the picture's side squeezed 2.5 times in height (15.11).

One object BridgeDais (collection BridgeDais, material BridgeDais):
- top: eight white floor plates (seams every 45 degrees, in the height map), two screws at the outer corners of each,
  a 12 mm aluminium trim ring at the edge, an orange stripe on the rounded top edge; in the middle a satin steel frame
  ring, eight graphite anti-slip rubber tiles 2 mm down, split by satin steel bars, an inner frame ring and the round
  brushed aluminium mounting plate with four bolts for the couch;
- side: light aluminium wall on a recessed graphite plinth, four long recessed panels (at 0, 90, 180, 270 degrees,
  66 degrees long) with a teal light strip in a slot, and four narrow vertical niches between them at 45 degrees.
The side wall is drawn flat (arc length x, height z, depth h outwards) with its recesses, cut into the 256 facet
columns of the lathe parts and bent onto the faceted cylinder: the faces stay planar and the uv stay exact lengths.

Islands. Repeats share islands, as the rules say, except where the dais gets worn (only the south passage, the
author's zone, 15.11): the two south top sectors (135-225 degrees) and the south quarter of the side (140.6-230.6)
have islands of their own, the other six sectors and three quarters lie on one master each. The eight rubber tiles all
have their own (worn round the couch). Screws, bolts and bars share one island per kind. Faces of shared copies carry
the face attribute shared = 1: the bake rasterises only the masters, at their real place.
Zones -> materials: white paint, aluminium, graphite, orange, teal (light strip), plastic = graphite rubber tiles,
satin = steel frames and bars, frosted = brushed aluminium plate and the light steel screws and bolts.
"""
import bpy, bmesh, importlib, sys
from math import sin, cos, pi, radians, floor, ceil, hypot
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon

KIT_DIR = '/Users/cemeheeb/Projects/ludum-dare/tools/blender/kit'
if KIT_DIR not in sys.path:
    sys.path.insert(0, KIT_DIR)
import kit_lib
importlib.reload(kit_lib)
from kit_lib import B, I4, T, rr, ZONES

KIT = 'BridgeDais'
col = bpy.data.collections.get(KIT) or bpy.data.collections.new(KIT)
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
mat = bpy.data.materials.get(KIT) or bpy.data.materials.new(KIT)
MM = 0.001

# ---------------- measurements, mm ----------------
R = 1200.0                 # outer wall
N = 256                    # facets round the dais (1.40625 degrees, 29.45 mm at the wall)
DA = 2 * pi / N
DX = R * DA                # one facet column of the flat wall
Z_STEP = 8.0               # wall bottom; under it the plinth, set back to R_PLINTH
R_PLINTH = 1188.0
Z_ROUND, B_ROUND = 102.0, 18.0   # rounded top edge: quarter round of 18 mm from z 102, top edge at r 1182
R_TOP = R - B_ROUND
R_TRIM = 1170.0            # aluminium trim ring R_TRIM..R_TOP; white plates inside it
R_FRAME_OUT, R_FRAME_IN = 632.0, 618.0     # outer frame ring, its inner wall drops to the tiles
Z_TOP, Z_TILE = 120.0, 118.0
R_INNER_OUT, R_PLATE = 339.0, 327.0        # inner frame ring, then the mounting plate
PANEL_SPAN = 33.0          # degrees each way from 0, 90, 180, 270
PANEL_Z0, PANEL_Z1, PANEL_RC, PANEL_DEPTH = 30.0, 80.0, 8.0, 4.0
SLOT_END, SLOT_Z, SLOT_H, SLOT_RC, SLOT_DEPTH = 45.0, 57.0, 12.0, 5.5, 5.0   # light slot in the panel floor
NICHE_W, NICHE_Z0, NICHE_Z1, NICHE_RC, NICHE_DEPTH = 34.0, 28.0, 82.0, 6.0, 8.0
SCREW_R, SCREW_T = 1128.0, 55.0    # plate screws: radius, offset from the seam along the edge
BOLT_R = 265.0             # mounting plate bolts at 45 + k * 90 degrees
BAR_W = 10.0               # steel bars between the tiles
Q0 = -28                   # first facet of the master side quarter: -39.375 degrees, between a panel and a niche
NCOL = 64                  # facets in a side quarter
P_LEN = NCOL * DX
X_PANEL = 28 * DX          # panel centre (0 degrees) in the quarter
X_NICHE = 60 * DX          # niche centre (45 degrees)
L_PANEL = 2 * radians(PANEL_SPAN) * R

b = B()
SHARED = set()             # face indices of shared copies
HIDDEN = set()             # islands at a quarter of the density (never seen)


# ---------------- helpers ----------------
def P(r, z, i):
    return (r * cos(i * DA), r * sin(i * DA), z)


def arc_lathe(i0, i1, specs):
    """kit_lib lathe over the facets i0..i1-1 of N (first point on +X). 'strip': u along the arc at r_ref, v along the
    profile; 'polar': the ring going towards the axis, uv its true top view. Returns the islands."""
    out = []
    for sp in specs:
        kind, pts, zones = sp[0], sp[1], sp[2]
        if not isinstance(zones, (list, tuple)):
            zones = [zones] * (len(pts) - 1)
        isl = b.isl()
        out.append(isl)
        L = [0.0]
        for j in range(len(pts) - 1):
            L.append(L[-1] + hypot(pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]))
        if kind == 'strip':
            du = 2 * (sp[3] if len(sp) > 3 else max(p[0] for p in pts)) * sin(pi / N)
            uv = lambda j, i, du=du, L=L: ((i - i0) * du, L[j])
        else:
            rho = [pts[-1][0] + (L[-1] - l) for l in L]
            uv = lambda j, i, rho=rho: (rho[j] * cos(i * DA), rho[j] * sin(i * DA))
        for j in range(len(pts) - 1):
            (r0, z0), (r1, z1) = pts[j], pts[j + 1]
            for i in range(i0, i1):
                b.face(I4, [P(r0, z0, i), P(r0, z0, i + 1), P(r1, z1, i + 1), P(r1, z1, i)],
                       [uv(j, i), uv(j, i + 1), uv(j + 1, i + 1), uv(j + 1, i)], isl, zones[j])
    return out


def newell(q):
    n = [0.0, 0.0, 0.0]
    for i in range(len(q)):
        a, c = q[i], q[(i + 1) % len(q)]
        n[0] += (a[1] - c[1]) * (a[2] + c[2])
        n[1] += (a[2] - c[2]) * (a[0] + c[0])
        n[2] += (a[0] - c[0]) * (a[1] + c[1])
    return n


def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


# ---------------- the flat side wall: x along the arc at R, z up, h outwards ----------------
TH0 = Q0 * DA


def bend(x, z, h):
    """Onto the faceted cylinder: affine inside each facet column, so planar flat faces stay planar."""
    k = min(max(int(floor(x / DX + 1e-9)), 0), NCOL - 1)
    t = (x - k * DX) / DX
    a0, a1 = TH0 + k * DA, TH0 + (k + 1) * DA
    r = R + h
    return (r * ((1 - t) * cos(a0) + t * cos(a1)), r * ((1 - t) * sin(a0) + t * sin(a1)), z)


def snap(x):
    k = round(x / DX)
    return k * DX if abs(x - k * DX) < 0.02 else x


def clip_half(pts, uvs, c, sgn):
    """Keep sgn * (x - c) >= 0. The cut point is always interpolated from the end with the smaller x, so that two
    faces sharing an edge cut it at the same point."""
    op, ou = [], []
    n = len(pts)
    for i in range(n):
        p, q, u, w = pts[i], pts[(i + 1) % n], uvs[i], uvs[(i + 1) % n]
        pin, qin = sgn * (p[0] - c) >= -1e-9, sgn * (q[0] - c) >= -1e-9
        if pin:
            op.append(p)
            ou.append(u)
        if pin != qin:
            a, aw, e, ew = (p, u, q, w) if p[0] < q[0] else (q, w, p, u)
            t = (c - a[0]) / (e[0] - a[0])
            op.append((c, a[1] + (e[1] - a[1]) * t, a[2] + (e[2] - a[2]) * t))
            ou.append((aw[0] + (ew[0] - aw[0]) * t, aw[1] + (ew[1] - aw[1]) * t))
    return op, ou


def flat_face(pts, uvs, isl, zone):
    pts = [(snap(x), z, h) for x, z, h in pts]
    xs = [p[0] for p in pts]
    k0 = max(int(floor(min(xs) / DX + 1e-9)), 0)
    k1 = min(int(ceil(max(xs) / DX - 1e-9)), NCOL)
    for k in range(k0, max(k1, k0 + 1)):
        p, u = clip_half(pts, uvs, k * DX, 1)
        p, u = clip_half(p, u, (k + 1) * DX, -1)
        qp, qu = [], []
        for a, w in zip(p, u):
            if not qp or max(abs(a[0] - qp[-1][0]), abs(a[1] - qp[-1][1]), abs(a[2] - qp[-1][2])) > 1e-6:
                qp.append(a)
                qu.append(w)
        while len(qp) > 1 and max(abs(qp[0][i] - qp[-1][i]) for i in range(3)) <= 1e-6:
            qp.pop()
            qu.pop()
        if len(qp) < 3 or Vector(newell(qp)).length < 2e-4:
            continue
        b.face(I4, [bend(*a) for a in qp], qu, isl, zone)


def recess(cx, cz, shape, levels, zones, zone_floor, hole=None):
    """A pocket in the flat wall: shape(d) is the outline (x, z) about the centre inset by d, CCW; levels (d, h) go from
    the surface to the floor. One island: the floor at its true size, the walls unfolded round it like prism caps."""
    isl = b.isl()
    m = len(levels)
    seg = [hypot(levels[j + 1][0] - levels[j][0], levels[j + 1][1] - levels[j][1]) for j in range(m - 1)]
    c = [sum(seg[j:]) for j in range(m)]
    O = [shape(d) for d, h in levels]
    U = [shape(levels[-1][0] - c[j]) for j in range(m)]
    n = len(O[0])
    for j in range(m - 1):
        for i in range(n):
            i2 = (i + 1) % n
            q = [(cx + O[j][i][0], cz + O[j][i][1], levels[j][1]), (cx + O[j][i2][0], cz + O[j][i2][1], levels[j][1]),
                 (cx + O[j + 1][i2][0], cz + O[j + 1][i2][1], levels[j + 1][1]), (cx + O[j + 1][i][0], cz + O[j + 1][i][1], levels[j + 1][1])]
            uv = [(cx + U[j][i][0], cz + U[j][i][1]), (cx + U[j][i2][0], cz + U[j][i2][1]),
                  (cx + U[j + 1][i2][0], cz + U[j + 1][i2][1]), (cx + U[j + 1][i][0], cz + U[j + 1][i][1])]
            nn = newell(q)
            fx, fz = sum(a[0] for a in q) / 4, sum(a[1] for a in q) / 4
            if nn[0] * (cx - fx) + nn[1] * (cz - fz) < 0:      # walls face the middle of the pocket
                q.reverse()
                uv.reverse()
            flat_face(q, uv, isl, zones[j])
    fl = [(cx + x, cz + z) for x, z in O[-1]]
    hf = levels[-1][1]
    if hole is None:
        flat_face([(x, z, hf) for x, z in fl], fl, isl, zone_floor)
    else:
        allp = fl + hole
        for t in tessellate_polygon([fl, hole]):
            tri = [allp[k] for k in t]
            if area2(tri) < 0:
                tri.reverse()
            flat_face([(x, z, hf) for x, z in tri], tri, isl, zone_floor)
    return isl


def at(cx, cz):
    return lambda pts: [(cx + x, cz + z) for x, z in pts]


panel_shape = lambda d: rr(L_PANEL - 2 * d, PANEL_Z1 - PANEL_Z0 - 2 * d, PANEL_RC - d, 3)
slot_shape = lambda d: rr(L_PANEL - 2 * SLOT_END - 2 * d, SLOT_H - 2 * d, SLOT_RC - d, 3)
niche_shape = lambda d: rr(NICHE_W - 2 * d, NICHE_Z1 - NICHE_Z0 - 2 * d, NICHE_RC - d, 3)
PZ, NZ = (PANEL_Z0 + PANEL_Z1) / 2, (NICHE_Z0 + NICHE_Z1) / 2

# ---------------- side quarter (master), -39.375 .. 50.625 degrees ----------------
w0 = len(b.F)
wall = b.isl()
outer = [(0.0, Z_STEP), (P_LEN, Z_STEP), (P_LEN, Z_ROUND), (0.0, Z_ROUND)]
holes = [at(X_PANEL, PZ)(panel_shape(0)), at(X_NICHE, NZ)(niche_shape(0))]
allp = outer + holes[0] + holes[1]
tri_area = 0.0
for t in tessellate_polygon([outer] + holes):
    tri = [allp[k] for k in t]
    if area2(tri) < 0:
        tri.reverse()
    tri_area += area2(tri) / 2
    flat_face([(x, z, 0.0) for x, z in tri], tri, wall, 'aluminium')
hole_area = sum(abs(area2(hh)) / 2 for hh in holes)
print('wall fill check: triangles', round(tri_area), 'expected', round(P_LEN * (Z_ROUND - Z_STEP) - hole_area))
# rounded top edge: outer facet aluminium (the thin light line under the stripe), the two upper ones orange
prof = [(0.0, Z_ROUND)] + [(-a, z) for a, z in kit_lib.bevel(Z_TOP, B_ROUND)]
v = Z_ROUND
for j, zone in enumerate(('aluminium', 'orange', 'orange')):
    (h0, z0), (h1, z1) = prof[j], prof[j + 1]
    v1 = v + hypot(h1 - h0, z1 - z0)
    flat_face([(0.0, z0, h0), (P_LEN, z0, h0), (P_LEN, z1, h1), (0.0, z1, h1)],
              [(0.0, v), (P_LEN, v), (P_LEN, v1), (0.0, v1)], wall, zone)
    # u stays the arc at R: the top facet is 1.5 % short (allowed on rounding belts of a side strip)
    v = v1
slot_hole = at(X_PANEL, SLOT_Z)(slot_shape(0))
recess(X_PANEL, PZ, panel_shape, [(0, 0), (1, -1), (1, -PANEL_DEPTH)], ['aluminium', 'aluminium'], 'aluminium', hole=slot_hole)
recess(X_PANEL, SLOT_Z, slot_shape, [(0, -PANEL_DEPTH), (1, -PANEL_DEPTH - 1), (1, -PANEL_DEPTH - SLOT_DEPTH)],
       ['graphite', 'graphite'], 'teal')
recess(X_NICHE, NZ, niche_shape, [(0, 0), (1, -1), (1, -NICHE_DEPTH)], ['aluminium', 'aluminium'], 'graphite')
plinth, step = arc_lathe(Q0, Q0 + NCOL, [('strip', [(R_PLINTH, 0.0), (R_PLINTH, Z_STEP)], 'graphite', R_PLINTH),
                                         ('strip', [(R_PLINTH, Z_STEP), (R, Z_STEP)], 'aluminium', (R + R_PLINTH) / 2)])
HIDDEN.add(step)
w1 = len(b.F)


def rot(deg):
    return Matrix.Rotation(radians(deg), 4, 'Z')


def copy_shared(i0, i1, M):
    n0 = len(b.F)
    b.copy(i0, i1, M)
    SHARED.update(range(n0, len(b.F)))


def copy_own(i0, i1, M):
    n0 = len(b.F)
    b.copy(i0, i1, M)
    remap = {}
    for j in range(n0, len(b.F)):
        pts, uvs, isl, zone, soft = b.F[j]
        if isl not in remap:
            remap[isl] = b.isl()
            if isl in HIDDEN:
                HIDDEN.add(remap[isl])
        b.F[j] = (pts, uvs, remap[isl], zone, soft)


copy_shared(w0, w1, rot(90))
copy_own(w0, w1, rot(180))          # the south quarter: worn, islands of its own
copy_shared(w0, w1, rot(270))

# ---------------- top sector (master), 0 .. 45 degrees ----------------
s0 = len(b.F)
arc_lathe(0, N // 8, [('strip', [(R_TOP, Z_TOP), (R_TRIM, Z_TOP)], 'aluminium', (R_TOP + R_TRIM) / 2),
                      ('polar', [(R_TRIM, Z_TOP), (R_FRAME_OUT, Z_TOP)], 'white'),
                      ('strip', [(R_FRAME_OUT, Z_TOP), (R_FRAME_IN, Z_TOP), (R_FRAME_IN, Z_TILE)], 'satin', (R_FRAME_OUT + R_FRAME_IN) / 2),
                      ('strip', [(R_INNER_OUT, Z_TILE), (R_INNER_OUT, Z_TOP), (R_PLATE, Z_TOP)], 'satin', (R_INNER_OUT + R_PLATE) / 2)])
s1 = len(b.F)
for k in range(1, 8):
    (copy_own if k in (3, 4) else copy_shared)(s0, s1, rot(45 * k))      # 135-225 degrees: the south passage
t0 = len(b.F)
arc_lathe(0, N // 8, [('polar', [(R_FRAME_IN, Z_TILE), (R_INNER_OUT, Z_TILE)], 'plastic')])
t1 = len(b.F)
for k in range(1, 8):
    copy_own(t0, t1, rot(45 * k))     # every tile its own: worn round the couch
# mounting plate: one face, its true top view as uv
isl = b.isl()
ring = [P(R_PLATE, Z_TOP, i) for i in range(N)]
b.face(I4, ring, [(x, y) for x, y, z in ring], isl, 'frosted')

# ---------------- bars between the tiles: top and two sides, open ends and bottom (they sit in the frame) ----------------
isl = b.isl()
x0, x1, hw = R_INNER_OUT - 0.1, R_FRAME_IN + 0.1, BAR_W / 2
g0 = len(b.F)
b.face(I4, [(x0, -hw, Z_TILE), (x1, -hw, Z_TILE), (x1, -hw, Z_TOP), (x0, -hw, Z_TOP)],
       [(x0, -2), (x1, -2), (x1, 0), (x0, 0)], isl, 'satin')
b.face(I4, [(x0, -hw, Z_TOP), (x1, -hw, Z_TOP), (x1, hw, Z_TOP), (x0, hw, Z_TOP)],
       [(x0, 0), (x1, 0), (x1, BAR_W), (x0, BAR_W)], isl, 'satin')
b.face(I4, [(x1, hw, Z_TILE), (x0, hw, Z_TILE), (x0, hw, Z_TOP), (x1, hw, Z_TOP)],
       [(x1, BAR_W + 2), (x0, BAR_W + 2), (x0, BAR_W), (x1, BAR_W)], isl, 'satin')
g1 = len(b.F)
for k in range(1, 8):
    copy_shared(g0, g1, rot(45 * k))


# ---------------- screws and bolts: washer, domed head, socket; one master each; light steel as in the picture ----------------
def screw(s, z0=Z_TOP):
    i0 = len(b.F)
    b.lathe(T(0, 0, z0), 16, [('strip', [(11 * s, 0), (11 * s, 0.8 * s)], 'frosted'),
                              ('polar', [(11 * s, 0.8 * s), (8 * s, 0.8 * s), (7.8 * s, 1.6 * s), (7 * s, 2.4 * s), (5.4 * s, 2.9 * s), (2.5 * s, 3 * s)], 'frosted', 'end'),
                              ('strip', [(2.5 * s, 3 * s), (2.5 * s, 1.8 * s)], 'frosted'),
                              ('polar', [(2.5 * s, 1.8 * s), (0, 1.8 * s)], 'frosted', 'end')])
    return i0, len(b.F)


i0, i1 = screw(1.0)
first = None
for k in range(8):
    for a in (k * pi / 4 + SCREW_T / SCREW_R, (k + 1) * pi / 4 - SCREW_T / SCREW_R):
        M = Matrix.Rotation(a, 4, 'Z') @ T(SCREW_R, 0, 0)
        if first is None:
            first = M
            for j in range(i0, i1):
                pts, uvs, isl_, zone, soft = b.F[j]
                b.F[j] = ([M @ p for p in pts], uvs, isl_, zone, soft)
        else:
            copy_shared(i0, i1, M @ first.inverted())
i0, i1 = screw(1.9)
first = None
for k in range(4):
    M = Matrix.Rotation(radians(45 + 90 * k), 4, 'Z') @ T(BOLT_R, 0, 0)
    if first is None:
        first = M
        for j in range(i0, i1):
            pts, uvs, isl_, zone, soft = b.F[j]
            b.F[j] = ([M @ p for p in pts], uvs, isl_, zone, soft)
    else:
        copy_shared(i0, i1, M @ first.inverted())

# ---------------- build ----------------
for k, (pts, uvs, isl_, zone, soft) in enumerate(b.F):
    s = 0.25 if isl_ in HIDDEN else 1.0
    b.F[k] = ([p * MM for p in pts], [(u * MM * s, v_ * MM * s) for u, v_ in uvs], isl_, zone, soft)

old = bpy.data.objects.get(KIT)
if old:
    me_old = old.data
    bpy.data.objects.remove(old)
    if me_old.users == 0:
        bpy.data.meshes.remove(me_old)
me = bpy.data.meshes.new(KIT + '.Mesh')
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('UVMap')
zl = bm.faces.layers.int.new('zone')
il = bm.faces.layers.int.new('island')
shl = bm.faces.layers.int.new('shared')
for k, (pts, uvs, isl_, zone, soft) in enumerate(b.F):
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    for l, u in zip(f.loops, uvs):
        l[uvl].uv = u
    f[zl] = ZONES.index(zone)
    f[il] = isl_
    f[shl] = int(k in SHARED)
    f.smooth = True
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-5)
for e in bm.edges:
    fs = e.link_faces
    seam = len(fs) != 2 or fs[0][il] != fs[1][il]
    if not seam:
        for vv in e.verts:
            a = [l[uvl].uv for l in fs[0].loops if l.vert == vv][0]
            c = [l[uvl].uv for l in fs[1].loops if l.vert == vv][0]
            if (a - c).length > 1e-6:
                seam = True
    e.seam = seam
bm.normal_update()
for e in bm.edges:
    fs = e.link_faces
    if len(fs) == 2:
        e.smooth = e.calc_face_angle() <= radians(35)
zero = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
bm.to_mesh(me)
bm.free()
me.materials.append(mat)
ob = bpy.data.objects.new(KIT, me)
col.objects.link(ob)
bpy.context.scene['dais_hidden'] = sorted(HIDDEN)
print('faces', len(me.polygons), 'of', len(b.F), 'tris', sum(len(p.vertices) - 2 for p in me.polygons), 'islands', b.n,
      'shared faces', sum(a.value for a in me.attributes['shared'].data), 'zero-area faces', zero,
      'dims mm', [round(d * 1000, 1) for d in ob.dimensions])
