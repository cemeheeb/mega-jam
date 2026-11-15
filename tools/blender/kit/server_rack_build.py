"""Server rack (SourceArt/environment/computer/server-rack), rebuilt from the author's Tripo mesh
(source/tripo/server-rack.fbx, from Downloads/server-rack.zip 15.11) - pipeline/kit.md step 2, like the sleep capsule.

Run in the live Blender (MCP): exec(open(<this file>).read(), {}); in the background server_rack_scene.py runs it.
Millimetres, scaled to metres at build. Blender axes: X across the front, the front at -Y, Z up. Origin: middle of the
footprint on the floor. In Unreal (x, -y, z) x 100: the front faces +Y, as the card asks.

Measurements. Tripo units x 2000 = mm: the width is then 1990 like the 2 m grey box of the card; the height comes out
2000 (the card says 2400, the Tripo mesh is square from the front) and the depth 790 over the cap (card 700). Sections
of the Tripo mesh (15.11): body 1940 x 740 with vertical corners about R 70, top cap 1990 x 790, 112 tall, rounded on
top; two bays of four server drawers; rails between the rows with a teal strip and a block of status lights at its
right end; an orange paint band 117-173 mm over the front and the sides, turning the back corners; under the sides an
arch 36 mm high between a front and a back skid.

One object ServerRack (collection ServerRack, material ServerRack):
- body: front frame with eight bay openings 848 wide, 16 mm deep, a white liner; the sides flat (side panel seams and
  the vent slots go into the height map, as the capsule's panel seams); the back flat; the top hidden under the cap;
  no bottom under the skids (it stands on the floor);
- top cap: rounded rectangle R 85, a small rounding under it and a 40 mm rounding on top;
- drawer (x8, each with its own islands): graphite body 790 x 336 out of the bay floor to 40 mm in front of the frame,
  6 mm rounding round the front; a recessed grille 600 x 268 (the perforation goes into the height map); at both ends
  a handle recess 48 x 230 x 40 with a U handle bar (16 x 10, 28 mm behind it for the fingers) and a white latch tab;
- rails: a teal strip 635 x 24, 2 mm deep, five status light windows at its right end (glass, own islands each).

Zones -> materials: white paint, orange paint, plastic = dark graphite plastic (drawers, handles), grille = perforated
dark metal, teal = strip, glass = status lights.
"""
import bpy, bmesh, importlib, sys
from math import sin, cos, pi, radians, hypot, ceil
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon

KIT_DIR = '/Users/cemeheeb/Projects/ludum-dare/tools/blender/kit'
if KIT_DIR not in sys.path:
    sys.path.insert(0, KIT_DIR)
import kit_lib
importlib.reload(kit_lib)
from kit_lib import B, I4, T, frame, rr, bevel, build

KIT = 'ServerRack'
col = bpy.data.collections.get(KIT) or bpy.data.collections.new(KIT)
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
mat = bpy.data.materials.get(KIT) or bpy.data.materials.new(KIT)
MM = 0.001

# ---------------- measurements, mm ----------------
W2, D2, R_C = 970.0, 370.0, 70.0            # body half width, half depth, vertical corners
Z_TOP, H = 1887.0, 2000.0                   # body top = cap underside; top of the cap
CAP_W2, CAP_D2, CAP_R, CAP_B, CAP_B0 = 995.0, 395.0, 85.0, 40.0, 8.0
BAND = (117.0, 173.0)                       # orange band; on the back only round the corners, |x| > BACK_BAND
BACK_BAND = 860.0
BAY_X0, BAY_X1 = 40.0, 888.0                # right bay opening (the left one mirrored)
BAY_Z = [(184.0, 574.0), (618.0, 1008.0), (1052.0, 1444.0), (1488.0, 1876.0)]
BAY_R, BAY_DEPTH = 12.0, 16.0
DR_W, DR_H, DR_R, DR_OUT, DR_B = 790.0, 336.0, 10.0, 56.0, 6.0   # drawer: out of the bay floor to y = -410
GR_W, GR_H, GR_R, GR_DEPTH = 600.0, 268.0, 6.0, 10.0
HR_W, HR_H, HR_R, HR_DEPTH, HR_X = 48.0, 230.0, 8.0, 40.0, 345.0
BAR_W, BAR_T, BAR_OUT, BAR_Z, BAR_BEND = 16.0, 10.0, 33.0, 95.0, 10.0   # centre line of the U bar
TAB_W, TAB_H, TAB_T = 12.0, 40.0, 4.0
STRIP_W, STRIP_H, STRIP_R, STRIP_DEPTH, STRIP_DX = 635.0, 24.0, 4.0, 2.0, -5.5
LED_N, LED_W, LED_H, LED_GAP, LED_RIGHT = 5, 14.0, 16.0, 6.0, 12.0
SKID_FRONT, SKID_BACK, Z_UNDER, R_F = -200.0, 220.0, 36.0, 24.0

b = B()
HIDDEN = set()                              # islands at a quarter of the density (the underside)


# ---------------- helpers (from capsule_build.py) ----------------
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


def plane(o, eu, ev):
    eu, ev = Vector(eu), Vector(ev)
    return frame(eu, ev, eu.cross(ev), o)


def rr4(cx, cy, w, h, radii, d=0.0, seg=3):
    """Rectangle w x h about (cx, cy) inset by d; corners (+x,-y), (+x,+y), (-x,+y), (-x,-y) with radii - d,
    a radius of 0 stays one sharp point. CCW seen from +z."""
    hw, hh = w / 2 - d, h / 2 - d
    pts = []
    for (sx, sy, a), R in zip(((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)), radii):
        if R <= 0:
            pts.append((cx + sx * hw, cy + sy * hh))
            continue
        r = R - d
        ccx, ccy = cx + sx * (hw - r), cy + sy * (hh - r)
        for k in range(seg + 1):
            t = radians(a + 90 * k / seg)
            pts.append((ccx + r * cos(t), ccy + r * sin(t)))
    return pts


def clip(P, axis, c, keep_ge):
    out = []
    n = len(P)
    for i in range(n):
        a, e = P[i], P[(i + 1) % n]
        ia, ie = (a[axis] >= c) == keep_ge, (e[axis] >= c) == keep_ge
        if ia:
            out.append(a)
        if ia != ie and abs(e[axis] - a[axis]) > 1e-12:
            t = (c - a[axis]) / (e[axis] - a[axis])
            out.append((a[0] + t * (e[0] - a[0]), a[1] + t * (e[1] - a[1])))
    return out


def dedupe(P):
    q = []
    for p in P:
        if not q or abs(p[0] - q[-1][0]) + abs(p[1] - q[-1][1]) > 1e-6:
            q.append(p)
    while len(q) > 1 and abs(q[0][0] - q[-1][0]) + abs(q[0][1] - q[-1][1]) <= 1e-6:
        q.pop()
    return q


def region(M, outer, holes, isl, zone, h=0.0, cuts_u=(), cuts_v=(), uvf=None):
    """Flat face in the plane M (local u, v, normal +z) at height h: outline with holes, triangulated when it has
    holes, cut along u = const and v = const lines; the zone of each piece from zone(world centre) when callable."""
    uvf = uvf or (lambda u, v: (u, v))
    outer = list(outer) if area2(outer) > 0 else list(outer)[::-1]
    if holes:
        loops = [outer] + [list(hh) for hh in holes]
        allp = [p for L in loops for p in L]
        polys = []
        for t in tessellate_polygon([[Vector((x, y, 0.0)) for x, y in L] for L in loops]):
            tri = [allp[k] for k in t]
            if area2(tri) < 0:
                tri.reverse()
            polys.append(tri)
    else:
        polys = [outer]
    for c in cuts_u:
        polys = [q for P in polys for q in (clip(P, 0, c, True), clip(P, 0, c, False)) if len(q) >= 3]
    for c in cuts_v:
        polys = [q for P in polys for q in (clip(P, 1, c, True), clip(P, 1, c, False)) if len(q) >= 3]
    for P in polys:
        P = dedupe(P)
        if len(P) < 3 or abs(area2(P)) < 1e-3:
            continue
        cu, cv = sum(p[0] for p in P) / len(P), sum(p[1] for p in P) / len(P)
        z = zone(M @ Vector((cu, cv, h))) if callable(zone) else zone
        b.face(M, [(x, y, h) for x, y in P], [uvf(x, y) for x, y in P], isl, z)


def pocket(M, cu, cv, shape, levels, zones, zone_floor, floor_holes=(), h0=0.0):
    """Pocket or raised lip in the plane M at (cu, cv): shape(d) is the outline about (0, 0), CCW, the same point
    count for every d; levels (d, h) from the surface (h = 0) to the floor, d > 0 inwards, h < 0 into the surface
    (d < 0 with h > 0 makes a raised frame). One island: the floor at its true size, the walls unrolled round it."""
    isl = b.isl()
    m = len(levels)
    seg = [hypot(levels[j + 1][0] - levels[j][0], levels[j + 1][1] - levels[j][1]) for j in range(m - 1)]
    c = [sum(seg[j:]) for j in range(m)]
    O = [shape(d) for d, hh in levels]
    U = [shape(levels[-1][0] - c[j]) for j in range(m)]
    n = len(O[0])
    for j in range(m - 1):
        (d0, g0), (d1, g1) = levels[j], levels[j + 1]
        nd, nh = -(g1 - g0), d1 - d0            # air side in the (d, h) plane
        for i in range(n):
            i2 = (i + 1) % n
            P = lambda k, ii: (cu + O[k][ii][0], cv + O[k][ii][1], h0 + levels[k][1])
            q = [P(j, i), P(j, i2), P(j + 1, i2), P(j + 1, i)]
            if Vector(newell(q)).length < 1e-6:
                continue
            uv = [(cu + U[j][i][0], cv + U[j][i][1]), (cu + U[j][i2][0], cv + U[j][i2][1]),
                  (cu + U[j + 1][i2][0], cv + U[j + 1][i2][1]), (cu + U[j + 1][i][0], cv + U[j + 1][i][1])]
            ex, ey = O[j][i2][0] - O[j][i][0], O[j][i2][1] - O[j][i][1]
            L = hypot(ex, ey) or 1.0
            exp = (-nd * ey / L, nd * ex / L, nh)  # inwards = minus the outward normal (ey, -ex) of a CCW outline
            nn = newell(q)
            if nn[0] * exp[0] + nn[1] * exp[1] + nn[2] * exp[2] < 0:
                q.reverse()
                uv.reverse()
            b.face(M, q, uv, isl, zones[j])
    fl = [(cu + x, cv + y) for x, y in O[-1]]
    region(M, fl, list(floor_holes), isl, zone_floor, h=h0 + levels[-1][1])
    return isl


def shell(M, shape, prof, zones, cap1_zone=None):
    """Raised boss on a surface (navigator_build.shell without the bottom cap): outline shape(d) through
    (inset, height) levels; flat steps and the cap projected exactly, walls as straight strips."""
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
    last = None
    for k, j0, j1 in groups:
        if k == 'flat':
            isl = b.isl()
            for j in range(j0, j1):
                for i in range(N):
                    q = [V(j, i), V(j, i + 1), V(j + 1, i + 1), V(j + 1, i)]
                    if Vector(newell(q)).length < 1e-6:
                        continue
                    if newell(q)[2] < 0:
                        q.reverse()
                    b.face(M, q, [(p[0], p[1]) for p in q], isl, zones[j])
            last = isl
        else:
            dm = sum(prof[j][0] for j in range(j0, j1 + 1)) / (j1 - j0 + 1)
            ref = shape(dm)
            per = [0.0]
            for i in range(N):
                per.append(per[-1] + hypot(ref[(i + 1) % N][0] - ref[i][0], ref[(i + 1) % N][1] - ref[i][1]))
            vs = [0.0]
            for j in range(j0, j1):
                vs.append(vs[-1] + hypot(prof[j + 1][0] - prof[j][0], prof[j + 1][1] - prof[j][1]))
            isl = b.isl()
            for j in range(j0, j1):
                for i in range(N):
                    q = [V(j, i), V(j, i + 1), V(j + 1, i + 1), V(j + 1, i)]
                    t0, t1 = vs[j - j0], vs[j + 1 - j0]
                    b.face(M, q, [(per[i], t0), (per[i + 1], t0), (per[i + 1], t1), (per[i], t1)], isl, zones[j])
            last = None
    isl = last if last is not None else b.isl()
    b.face(M, [V(m - 1, i) for i in range(N)], [(V(m - 1, i)[0], V(m - 1, i)[1]) for i in range(N)], isl,
           cap1_zone or zones[-1])


def vcorner(c, R, a0, zcuts, zone):
    """Vertical rounded corner: quarter of a circle (centre c, radius R) from angle a0 CCW, in 30 degree steps,
    between the heights zcuts; one exact strip (u = arc length, v = z)."""
    isl = b.isl()
    pts = [(c[0] + R * cos(radians(a0 + 30 * k)), c[1] + R * sin(radians(a0 + 30 * k))) for k in range(4)]
    du = 2 * R * sin(radians(15))
    for k in range(3):
        for z0, z1 in zip(zcuts[:-1], zcuts[1:]):
            q = [(pts[k][0], pts[k][1], z0), (pts[k + 1][0], pts[k + 1][1], z0), (pts[k + 1][0], pts[k + 1][1], z1),
                 (pts[k][0], pts[k][1], z1)]
            ctr = Vector(((pts[k][0] + pts[k + 1][0]) / 2, (pts[k][1] + pts[k + 1][1]) / 2, (z0 + z1) / 2))
            b.face(I4, q, [(k * du, z0), ((k + 1) * du, z0), ((k + 1) * du, z1), (k * du, z1)], isl,
                   zone(ctr) if callable(zone) else zone)
    return isl




def to_metres(bb):
    bb.F = [([p * MM for p in pts], [(u * MM, v * MM) for u, v in uvs], isl, zone, soft) for pts, uvs, isl, zone, soft in bb.F]


def band_zone(p):
    return 'orange' if BAND[0] < p.z < BAND[1] else 'white'


def back_zone(p):
    return 'orange' if BAND[0] < p.z < BAND[1] and abs(p.x) > BACK_BAND else 'white'


def orient(q, uv, want):
    """Turn a face so that its normal looks along want."""
    if Vector(newell(q)).dot(Vector(want)) < 0:
        q.reverse()
        uv.reverse()
    return q, uv


def bays():
    for s in (-1, 1):
        for z0, z1 in BAY_Z:
            cx = s * (BAY_X0 + BAY_X1) / 2
            yield s, cx, (z0 + z1) / 2, BAY_X1 - BAY_X0, z1 - z0


def strips():
    for s in (-1, 1):
        for k in range(len(BAY_Z) - 1):
            cx = s * (BAY_X0 + BAY_X1) / 2 + STRIP_DX
            yield cx, (BAY_Z[k][1] + BAY_Z[k + 1][0]) / 2


def leds(cx, cz):
    x1 = cx + STRIP_W / 2 - LED_RIGHT
    out = []
    for i in range(LED_N):
        xr = x1 - i * (LED_W + LED_GAP)
        out.append([(xr, cz - LED_H / 2), (xr, cz + LED_H / 2), (xr - LED_W, cz + LED_H / 2), (xr - LED_W, cz - LED_H / 2)])
    return out


def moved(pts, cx, cz):
    return [(cx + x, cz + y) for x, y in pts]


# ---------------- body: front frame ----------------
M_FRONT = plane((0, -D2, 0), (1, 0, 0), (0, 0, 1))          # local z = -Y, out of the front
M_BAY = plane((0, -D2 + BAY_DEPTH, 0), (1, 0, 0), (0, 0, 1))
holes = [moved(rr(w, h, BAY_R, 3), cx, cz) for s, cx, cz, w, h in bays()]
holes += [moved(rr(STRIP_W, STRIP_H, STRIP_R, 2), cx, cz) for cx, cz in strips()]
xf = W2 - R_C
region(M_FRONT, [(-xf, 0), (xf, 0), (xf, Z_TOP), (-xf, Z_TOP)], holes, b.isl(), band_zone, cuts_v=BAND)

for s, cx, cz, w, h in bays():
    foot = moved(rr(DR_W, DR_H, DR_R, 3), cx, cz)
    pocket(M_FRONT, cx, cz, lambda d, w=w, h=h: rr(w - 2 * d, h - 2 * d, BAY_R - d, 3), [(0, 0), (0, -BAY_DEPTH)],
           ['white'], 'white', floor_holes=[foot])

for cx, cz in strips():
    L = leds(cx, cz)
    pocket(M_FRONT, cx, cz, lambda d: rr(STRIP_W - 2 * d, STRIP_H - 2 * d, STRIP_R - d, 2), [(0, 0), (0, -STRIP_DEPTH)],
           ['white'], 'teal', floor_holes=L)
    for o in L:
        region(M_FRONT, o, [], b.isl(), 'glass', h=-STRIP_DEPTH)

# ---------------- body: corners, sides, back ----------------
ZC = [0.0, BAND[0], BAND[1], Z_TOP]
yc = D2 - R_C
for c, a0 in (((xf, -yc), -90), ((xf, yc), 0), ((-xf, yc), 90), ((-xf, -yc), 180)):
    vcorner(c, R_C, a0, ZC, band_zone)


def side_outline():
    """Side face in (y, z): the bottom edge climbs into the arch between the skids."""
    cf, cb = (SKID_FRONT + R_F, Z_UNDER - R_F), (SKID_BACK - R_F, Z_UNDER - R_F)
    pts = [(-yc, 0.0), (SKID_FRONT, 0.0)]
    pts += [(cf[0] + R_F * cos(radians(a)), cf[1] + R_F * sin(radians(a))) for a in (180, 150, 120, 90)]
    pts += [(cb[0] + R_F * cos(radians(a)), cb[1] + R_F * sin(radians(a))) for a in (90, 60, 30, 0)]
    pts += [(SKID_BACK, 0.0), (yc, 0.0), (yc, Z_TOP), (-yc, Z_TOP)]
    return dedupe(pts)


for s in (-1, 1):
    Ms = plane((s * W2, 0, 0), (0, s, 0), (0, 0, 1))
    region(Ms, [(s * y, z) for y, z in side_outline()], [], b.isl(), band_zone, cuts_v=BAND)

M_BACK = plane((0, D2, 0), (-1, 0, 0), (0, 0, 1))
region(M_BACK, [(-xf, 0), (xf, 0), (xf, Z_TOP), (-xf, Z_TOP)], [], b.isl(), back_zone, cuts_u=(-BACK_BAND, BACK_BAND),
       cuts_v=BAND)

# ---------------- underside: skid faces, fillets, the raised middle ----------------
for y, want in ((SKID_FRONT, (0, 1, 0)), (SKID_BACK, (0, -1, 0))):
    q = [(-W2, y, 0.0), (W2, y, 0.0), (W2, y, Z_UNDER - R_F), (-W2, y, Z_UNDER - R_F)]
    uv = [(-W2, 0.0), (W2, 0.0), (W2, Z_UNDER - R_F), (-W2, Z_UNDER - R_F)]
    q, uv = orient(q, uv, want)
    b.face(I4, q, uv, b.isl(), 'white')
for cy, angs in ((SKID_FRONT + R_F, (180, 150, 120, 90)), (SKID_BACK - R_F, (90, 60, 30, 0))):
    cz = Z_UNDER - R_F
    arc = [(cy + R_F * cos(radians(a)), cz + R_F * sin(radians(a))) for a in angs]
    isl = b.isl()
    du = 2 * R_F * sin(radians(15))
    for k in range(3):
        (y0, z0), (y1, z1) = arc[k], arc[k + 1]
        q = [(-W2, y0, z0), (W2, y0, z0), (W2, y1, z1), (-W2, y1, z1)]
        uv = [(-W2, k * du), (W2, k * du), (W2, (k + 1) * du), (-W2, (k + 1) * du)]
        mid = Vector(((y0 + y1) / 2, (z0 + z1) / 2))
        q, uv = orient(q, uv, (0, cy - mid.x, cz - mid.y))
        b.face(I4, q, uv, isl, 'white')
isl = b.isl()
HIDDEN.add(isl)
yu0, yu1 = SKID_FRONT + R_F, SKID_BACK - R_F
q, uv = orient([(-W2, yu0, Z_UNDER), (W2, yu0, Z_UNDER), (W2, yu1, Z_UNDER), (-W2, yu1, Z_UNDER)],
               [(-W2, yu0), (W2, yu0), (W2, yu1), (-W2, yu1)], (0, 0, -1))
b.face(I4, q, uv, isl, 'white')

# ---------------- top cap ----------------
cap = lambda d: rr(2 * CAP_W2 - 2 * d, 2 * CAP_D2 - 2 * d, CAP_R - d, 3)
b.prism(I4, 0, 0, 0, 0, bevel(Z_TOP, CAP_B0, up=False) + [(0.0, Z_TOP + CAP_B0), (0.0, H - CAP_B)] + bevel(H, CAP_B),
        'white', cap0=False, shape=cap)
M_UNDER_CAP = plane((0, 0, Z_TOP), (1, 0, 0), (0, -1, 0))  # local z = -Z
region(M_UNDER_CAP, cap(CAP_B0), [rr(2 * W2, 2 * D2, R_C, 3)], b.isl(), 'white')


# ---------------- drawers ----------------
def drawer(cx, cz):
    Md = M_BAY @ T(cx, cz, 0)
    b.prism(Md, DR_W, DR_H, DR_R, 3, [(0.0, 0.0), (0.0, DR_OUT - DR_B)] + bevel(DR_OUT, DR_B), 'plastic',
            cap0=False, cap1=False)
    grille = lambda d: rr(GR_W - 2 * d, GR_H - 2 * d, GR_R - d, 2)
    recess = lambda d: rr(HR_W - 2 * d, HR_H - 2 * d, HR_R - d, 2)
    region(Md, rr(DR_W - 2 * DR_B, DR_H - 2 * DR_B, DR_R - DR_B, 3),
           [grille(0)] + [moved(recess(0), s * HR_X, 0) for s in (-1, 1)], b.isl(), 'plastic', h=DR_OUT)
    pocket(Md, 0, 0, grille, [(0, 0), (0, -GR_DEPTH)], ['plastic'], 'grille', h0=DR_OUT)
    for s in (-1, 1):
        pocket(Md, s * HR_X, 0, recess, [(0, 0), (0, -HR_DEPTH)], ['plastic'], 'plastic', h0=DR_OUT)
        # U bar: legs out of the recess floor, the grip 28 mm in front of it; drawn in (out, z), width along x
        Mh = Md @ T(s * HR_X, 0, DR_OUT - HR_DEPTH) @ frame((0, 0, 1), (1, 0, 0), (0, 1, 0))
        r, zo, xo = BAR_BEND, BAR_Z, BAR_OUT
        path = [(-1.0, -zo)]
        path += [(xo - r + r * cos(radians(a)), -zo + r + r * sin(radians(a))) for a in (-90, -60, -30, 0)]
        path += [(xo - r + r * cos(radians(a)), zo - r + r * sin(radians(a))) for a in (0, 30, 60, 90)]
        path += [(-1.0, zo)]
        b.sheet(Mh, dedupe(path), BAR_W, BAR_T, 'plastic')
        Mt = Md @ T(s * HR_X, 0, DR_OUT - HR_DEPTH + BAR_OUT + BAR_T / 2)
        b.prism(Mt, TAB_W, TAB_H, 3, 2, [(0.0, 0.0), (0.0, TAB_T)], 'white', cap0=False)


for s, cx, cz, w, h in bays():
    drawer(cx, cz)

# ---------------- build ----------------
for i, (pts, uvs, isl, zone, soft) in enumerate(b.F):
    if isl in HIDDEN:
        b.F[i] = (pts, [(u * 0.25, v * 0.25) for u, v in uvs], isl, zone, soft)
to_metres(b)
ob = build(KIT, b, (0, 0, 0), col, mat)
me = ob.data
isl_n = len({f[2] for f in b.F})
lo = [min(v.co[i] for v in me.vertices) for i in range(3)]
hi = [max(v.co[i] for v in me.vertices) for i in range(3)]
print(KIT, 'faces', len(me.polygons), 'tris', sum(len(p.vertices) - 2 for p in me.polygons), 'islands', isl_n,
      'size mm', [round((h - l) * 1000) for l, h in zip(lo, hi)], 'lo', [round(l * 1000) for l in lo])

# ---------------- review colours until the textures (kit.md step 10 replaces the material) ----------------
PREVIEW = {'white': (0.83, 0.82, 0.79), 'orange': (0.85, 0.22, 0.03), 'plastic': (0.13, 0.14, 0.15),
           'grille': (0.045, 0.048, 0.052), 'teal': (0.16, 0.5, 0.55), 'glass': (0.55, 0.95, 1.0)}
ca = me.color_attributes.new('ZonePreview', 'FLOAT_COLOR', 'CORNER')
za = me.attributes['zone'].data
for p in me.polygons:
    c = PREVIEW[kit_lib.ZONES[za[p.index].value]]
    for li in p.loop_indices:
        ca.data[li].color = (*c, 1.0)
if not any(n.type == 'TEX_IMAGE' for n in (mat.node_tree.nodes if mat.use_nodes else [])):
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    attr = next((n for n in nt.nodes if n.type == 'ATTRIBUTE'), None) or nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_name = 'ZonePreview'
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.55
