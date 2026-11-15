"""Cartridge vault (SourceArt/environment/computer/cartridge-vault), rebuilt from the author's Tripo mesh
(source/tripo/cartridge-vault.fbx) and the picture images/cartridge-vault-1.png (pipeline/kit.md, step 2).

Run in Blender (MCP): exec(open(<this file>).read(), {}). Millimetres, scaled to metres at build.
Blender axes: X across the cabinet, the front with the slots at -Y, Z up. Origin: middle of the footprint on the floor.
In Unreal (x, -y, z) x 100: the front looks to +Y, as the card asks.

Measurements. The Tripo mesh is 1.0 tall: x 1801 = mm, so the cabinet is 1800 tall like the grey box of the card and
1591 wide (the box: 1600). Depth: the Tripo body is 650 (front face -322, back +328; the reference is moved 3 mm so the
body is centred), not 400 as the grey box: built as the reference, the room script has to set the vault 0.65 deep.
Numbers from rays cast at the reference every 4 mm from the front, the sides and the top; the details that the
low-poly Tripo mesh smears (the bezels, the cartridges, the keypad) from the picture, fitted to the Tripo grid.

One object CartridgeVault (collection CartridgeVault, material CartridgeVault):
- white body: vertical edges chamfered 50, all top edges chamfered 70 (as the Tripo top, 45 degrees), a 12 mm chamfer
  round the bottom; the orange stripe 1664-1726 all round right under the top chamfer (in the picture it runs across the
  front, the right column and the left side);
- four feet 62 tall under the corners (Tripo): the outer faces vertical, the lower 30 mm bevelled in by 28, the inner
  faces sloping (front cut-out 640 -> 596 at the left, 552 -> 508 at the right; side cut-outs +-130 -> +-92);
- front: the opening 1220 x 1459 (x -690..530, z 145..1604) with a 6 mm chamfer, white reveal 31 deep to the graphite
  plate; on the plate twelve bezels 299 x 480 (pitch 305 x 486, 6 mm grooves between them), each a rounded frame 6 proud
  of the plate with a 3 mm round, a 17 mm flat ring and an 8 mm lip down into a pocket 243 x 424 that goes 400 deep;
- ten cartridges, the two empty slots as in the picture and the Tripo mesh (middle row right, bottom row third):
  graphite body 225 x 404, top corners chamfered 18, face 40 behind the bezel front, resting on the pocket floor;
  on the face a grip rail at the left, a raised strip at the right (the vent slots in it go into the height map),
  two screws at the top corners, the aluminium handle: top mount with the teal window and a button, bottom mount, and
  between them a 70 x 14 bar 201 long with a 26 mm gap behind it for the fingers (rules.md: grip >= 110-120, gap 25-30;
  in the picture the handle looks flat on the cartridge, a lever you could not take hold of); the handle front is flush
  with the bezels, as in the Tripo mesh;
- orange gussets with a concave face in the two bottom corners of every pocket mouth;
- empty pockets: floor grate (its slots in the height map), two runners, a connector plate on the back wall and a
  guide post at the back right;
- right column: the keypad (graphite housing 124 x 255, 14 proud, teal screen, 3 x 4 keys) at x 644, z 1257 as in the
  Tripo mesh; four screws of the lower access panel (its outline, like the other panel seams, in the height map);
- sides as in the Tripo mesh: on the left two grip recesses near the back (180 x 372 and 180 x 376, 29 deep), on the
  right one recessed panel 376 x 332, 21 deep; all with a 3 mm round on the edge.
Panel seams, the vent slots, the grate slots and the seam on the cartridge go into the height map, not into the mesh.

Zones: white paint, aluminium (handles, screws), graphite (front plate, bezels, cartridges, keypad housing), plastic (keys),
teal (screens), orange (stripe, gussets).
"""
import bpy, bmesh, importlib, sys
from math import sin, cos, radians, hypot, sqrt
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

KIT_DIR = '/Users/cemeheeb/Projects/ludum-dare/tools/blender/kit'
if KIT_DIR not in sys.path:
    sys.path.insert(0, KIT_DIR)
import kit_lib
importlib.reload(kit_lib)
from kit_lib import B, I4, T, frame, bevel, build

KIT = 'CartridgeVault'
col = bpy.data.collections.get(KIT) or bpy.data.collections.new(KIT)
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
mat = bpy.data.materials.get(KIT) or bpy.data.materials.new(KIT)
MM = 0.001

# ---------------- measurements, mm ----------------
W2, D2, H = 795.0, 325.0, 1800.0       # half width, half depth, height
CV, CT = 50.0, 70.0                    # chamfers: vertical edges, top edges
ZB, DB = 62.0, 12.0                    # body bottom (top of the feet), bottom chamfer
STRIPE = (1664.0, 1726.0)              # orange stripe
OX0, OX1, OZ0, OZ1 = -690.0, 530.0, 145.0, 1604.0   # slot opening in the front
CE = 6.0                               # chamfer on the opening edge
REVEAL = 31.0                          # white reveal from the front face to the graphite plate
Y_PLATE = -D2 + REVEAL                 # -294: the plate, the bottom of the grooves between the bezels
COLS, ROWS, GAP = 4, 3, 6.0
PX, PZ = (OX1 - OX0) / COLS, (OZ1 - OZ0) / ROWS     # 305 x 486.3
BW, BH = PX - GAP, PZ - GAP                         # bezel 299 x 480.3
BZ_R, BZ_H, BZ_RING, BZ_LIP = 16.0, 6.0, 20.0, 28.0  # bezel corner radius, height over the plate, ring to d, lip to d
OPW, OPH = BW - 2 * BZ_LIP, BH - 2 * BZ_LIP         # pocket 243 x 424.3
POCKET = 400.0                         # pocket depth from the bezel front
EMPTY = {(1, 3), (0, 2)}               # (row from the bottom, column from the left)
CART_W, CART_H, CART_D, CART_IN = 225.0, 404.0, 300.0, 40.0
HX = -21.0                             # handle centre off the cartridge centre
KEY_X, KEY_Z = 644.0, 1257.0           # keypad centre
SCREW = 5.5

b = B()
HIDDEN = set()                         # islands at a quarter of the density: the back, the bottom, filled pockets
SQ2 = sqrt(2.0)


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
    """Rectangle w x h about (cx, cy) inset by d; corner radii - d, a radius of 0 stays one sharp point. CCW."""
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


def rrv(w, h, R, d=0.0, seg=3, rmin=1.0):
    """Rounded rectangle about (0, 0) inset by d whose corner radius stops shrinking at rmin (rr4 would go negative)."""
    hw, hh = w / 2 - d, h / 2 - d
    r = max(rmin, R - d)
    pts = []
    for sx, sy, a in ((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)):
        ccx, ccy = sx * (hw - r), sy * (hh - r)
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


def pocket(M, cu, cv, shape, levels, zones, zone_floor, floor_holes=(), h0=0.0, floor=True):
    """Pocket or raised lip in the plane M at (cu, cv): shape(d) is the outline about (0, 0), CCW, the same point
    count for every d; levels (d, h) from the surface (h = 0) to the floor, d > 0 inwards, h < 0 into the surface.
    One island: the floor at its true size, the walls unrolled round it. floor=False: walls only (capsule_build.py
    plus this switch)."""
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
            exp = (-nd * ey / L, nd * ex / L, nh)
            nn = newell(q)
            if nn[0] * exp[0] + nn[1] * exp[1] + nn[2] * exp[2] < 0:
                q.reverse()
                uv.reverse()
            b.face(M, q, uv, isl, zones[j])
    if floor:
        fl = [(cu + x, cv + y) for x, y in O[-1]]
        region(M, fl, list(floor_holes), isl, zone_floor, h=h0 + levels[-1][1])
    return isl


def shell(M, shape, prof, zones, cap1_zone=None):
    """Raised boss on a surface: outline shape(d) through (inset, height) levels, no bottom cap; flat steps and the
    cap projected exactly, walls as straight strips (capsule_build.py)."""
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


def hull(points, zone, drop=None):
    """Convex solid through the points; every flat face is its own island, unrolled exactly in its plane."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.dissolve_limit(bm, angle_limit=radians(0.5), verts=list(bm.verts), edges=list(bm.edges))
    for f in bm.faces:
        n = f.normal.normalized()
        c = f.calc_center_median()
        if drop and drop(n, c):
            continue
        up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((0, 1, 0))
        ev = (up - n * up.dot(n)).normalized()
        eu = ev.cross(n)
        pts = [v.co.copy() for v in f.verts]
        b.face(I4, pts, [(p.dot(eu), p.dot(ev)) for p in pts], b.isl(), zone)
    bm.free()


def to_metres(bb):
    bb.F = [([p * MM for p in pts], [(u * MM, v * MM) for u, v in uvs], isl, zone, soft) for pts, uvs, isl, zone, soft in bb.F]


# screws: one master (lathe), copies share its islands
_bs = B()
_bs.lathe(I4, 12, [('strip', [(SCREW, 0.0), (SCREW, 0.8)], 'aluminium'),
                   ('polar', [(SCREW, 0.8), (4.5, 1.8), (2.5, 2.3), (0.0, 2.4)], 'aluminium', 'end')])
_screw_isl = {}


def screw(M):
    for pts, uvs, isl, zone, soft in _bs.F:
        if isl not in _screw_isl:
            _screw_isl[isl] = b.isl()
        b.F.append(([M @ p for p in pts], list(uvs), _screw_isl[isl], zone, soft))


def paint(p):
    return 'orange' if STRIPE[0] < p.z < STRIPE[1] else 'white'


SUPPORT = 2.0                          # flat ring round a rounded edge: keeps the smoothed normals off the big face


def round_in(depth, r=3.0):
    """Levels of a recess with an r mm round on its edge: a flat SUPPORT ring, then the round from d = -r down the wall
    to the floor. Without the ring the vertices of the big triangulated face take the tilted normal of the round and
    the face shows a shading streak across it."""
    return [(-r - SUPPORT, 0.0), (-r, 0.0), (-r + r * cos(radians(60)), -r + r * sin(radians(60))),
            (-r + r * cos(radians(30)), -r + r * sin(radians(30))), (0.0, -r), (0.0, -depth)]


# ---------------- body ----------------
def octa(d):
    """Footprint inset by d, the 45 degree corner chamfers moved with their faces (true offset). CCW from +z,
    edges: 0 front, 1 front-right chamfer, 2 right, 3, 4 back, 5, 6 left, 7 front-left chamfer."""
    c = CV - d * (2 - SQ2)
    w, e = W2 - d, D2 - d
    return [Vector(p) for p in ((-w + c, -e), (w - c, -e), (w, -e + c), (w, e - c), (w - c, e), (-w + c, e), (-w, e - c), (-w, -e + c))]


O0, OB, OT = octa(0), octa(DB), octa(CT)
Z0, Z1 = ZB + DB, H - CT                     # the vertical walls
VB = DB * SQ2                                # v at the bottom of the vertical walls
vprof = lambda z: VB + (z - Z0)
VT = vprof(Z1)
EL = [(O0[(e + 1) % 8] - O0[e]).length for e in range(8)]
uoff, isl_of = {}, {}
for grp in ([7, 0, 1], [2, 3], [4], [5, 6]):        # front with its chamfers, right, back, left: one island each
    isl = b.isl()
    u = 0.0
    for e in grp:
        uoff[e], isl_of[e] = u, isl
        u += EL[e]
HIDDEN.add(isl_of[4])

# holes of the vertical walls, in the plane of each wall: u from its first corner, v = z
LEFT_RECESS = [(115.0, 1322.0, 180.0, 372.0, 24.0, 29.0), (115.0, 476.0, 180.0, 376.0, 24.0, 29.0)]   # u, v, w, h, R, depth
RIGHT_RECESS = [(299.0, 478.0, 376.0, 332.0, 12.0, 21.0)]
OPEN_U = ((OX0 + OX1) / 2 + (W2 - CV), (OZ0 + OZ1) / 2, OX1 - OX0, OZ1 - OZ0)
holes = {
    0: [rr4(OPEN_U[0], OPEN_U[1], OPEN_U[2], OPEN_U[3], (0, 0, 0, 0), -CE)],
    2: [rr4(u, v, w, h, (R,) * 4, -3.0 - SUPPORT) for u, v, w, h, R, dep in RIGHT_RECESS],
    6: [rr4(u, v, w, h, (R,) * 4, -3.0 - SUPPORT) for u, v, w, h, R, dep in LEFT_RECESS],
}
wall_M = {}
for e in range(8):
    A0, B0, Ab, Bb, At, Bt = O0[e], O0[(e + 1) % 8], OB[e], OB[(e + 1) % 8], OT[e], OT[(e + 1) % 8]
    L, u0, isl = EL[e], uoff[e], isl_of[e]
    b.face(I4, [(Ab.x, Ab.y, ZB), (Bb.x, Bb.y, ZB), (B0.x, B0.y, Z0), (A0.x, A0.y, Z0)],
           [(u0, 0), (u0 + L, 0), (u0 + L, VB), (u0, VB)], isl, 'white')
    b.face(I4, [(A0.x, A0.y, Z1), (B0.x, B0.y, Z1), (Bt.x, Bt.y, H), (At.x, At.y, H)],
           [(u0, VT), (u0 + L, VT), (u0 + L, VT + CT * SQ2), (u0, VT + CT * SQ2)], isl, 'white')
    M = plane((A0.x, A0.y, 0.0), (B0 - A0).normalized().to_3d(), (0, 0, 1))
    wall_M[e] = M
    region(M, [(0, Z0), (L, Z0), (L, Z1), (0, Z1)], holes.get(e, []), isl, paint, cuts_v=STRIPE,
           uvf=lambda u, v, u0=u0: (u0 + u, vprof(v)))
isl = b.isl()
b.face(I4, [(p.x, p.y, H) for p in OT], [(p.x, p.y) for p in OT], isl, 'white')              # top
isl = b.isl()
HIDDEN.add(isl)
b.face(I4, [(p.x, p.y, ZB) for p in OB[::-1]], [(-p.x, p.y) for p in OB[::-1]], isl, 'white')  # bottom

# side recesses
for e, rec in ((6, LEFT_RECESS), (2, RIGHT_RECESS)):
    for u, v, w, h, R, dep in rec:
        pocket(wall_M[e], u, v, lambda d, w=w, h=h, R=R: rr4(0, 0, w, h, (R,) * 4, d), round_in(dep), ['white'] * 5, 'white')


# ---------------- feet ----------------
def foot(sx, sy):
    xo_t, yo_t = sx * (W2 - DB), sy * (D2 - DB)
    xo_b, yo_b = sx * (W2 - DB - 28.0), sy * (D2 - DB - 28.0)
    xin_t, xin_b = (-596.0, -640.0) if sx < 0 else (508.0, 552.0)
    yin_t, yin_b = sy * 92.0, sy * 130.0
    zm = 30.0
    t = zm / ZB
    xin_m, yin_m = xin_b + (xin_t - xin_b) * t, yin_b + (yin_t - yin_b) * t
    c_t, c_b = CV - DB * (2 - SQ2), CV - (DB + 28.0) * (2 - SQ2)

    def poly(xo, yo, xi, yi, c, z):
        gx, gy = (1 if xi > xo else -1), (1 if yi > yo else -1)
        return [(xo + gx * c, yo, z), (xi, yo, z), (xi, yi, z), (xo, yi, z), (xo, yo + gy * c, z)]

    pts = poly(xo_t, yo_t, xin_t, yin_t, c_t, ZB) + poly(xo_t, yo_t, xin_m, yin_m, c_t, zm) + poly(xo_b, yo_b, xin_b, yin_b, c_b, 0.0)
    hull(pts, 'white', drop=lambda n, c: n.z > 0.99 and abs(c.z - ZB) < 0.1)


for sx in (-1, 1):
    for sy in (-1, 1):
        foot(sx, sy)

# ---------------- front: reveal, graphite plate, bezels, pockets ----------------
Mf = wall_M[0]                                  # u = x + 745, v = z, normal -Y, h = -(y + 325)
UO = W2 - CV
cells = [(r, c, OX0 + PX * (c + 0.5), OZ0 + PZ * (r + 0.5)) for r in range(ROWS) for c in range(COLS)]
bezel_shape = lambda d: rrv(BW, BH, BZ_R, d, 3, 4.0)
plate_holes = [[(cx + UO + x, cz + y) for x, y in bezel_shape(0.0)] for r, c, cx, cz in cells]
pocket(Mf, OPEN_U[0], OPEN_U[1], lambda d: rr4(0, 0, OPEN_U[2], OPEN_U[3], (0, 0, 0, 0), d),
       [(-CE, 0.0), (0.0, -CE), (0.0, -REVEAL)], ['white', 'white'], 'graphite', floor_holes=plate_holes)

Mb = plane((0.0, Y_PLATE, 0.0), (1, 0, 0), (0, 0, 1))      # u = x, v = z, h toward the viewer from the plate
BEZEL_LV = [(0.0, 0.0), (0.0, BZ_H - 3.0)] + [(3.0 - 3.0 * cos(radians(t)), BZ_H - 3.0 + 3.0 * sin(radians(t))) for t in (30, 60, 90)] \
    + [(BZ_RING, BZ_H), (BZ_LIP, BZ_H - 8.0), (BZ_LIP, -40.0)]
GUSSET = 30.0


def gusset(x, z, sx):
    """Orange corner piece at a pocket mouth corner (x, z): legs GUSSET, concave face; sx = +1 left corner, -1 right."""
    L = GUSSET
    pts = [(0.0, 0.0), (L, 0.0)] + [(L + L * cos(radians(a)), L + L * sin(radians(a))) for a in (240, 210)] + [(0.0, L)]
    b.slab(T(x, Y_PLATE + 17.0, z), [(sx * px, pz) for px, pz in pts], 26.0, 'orange')   # y -290..-264, before the cartridge


def cartridge(cx, cz):
    czc = cz - OPH / 2 + CART_H / 2                       # resting on the pocket floor
    Mc0 = Mb @ T(cx, czc, -(CART_IN - BZ_H) - CART_D)
    cs = lambda d: (lambda k: [(-(CART_W / 2 - d) + (5 - d * k), -(CART_H / 2 - d)), ((CART_W / 2 - d) - (5 - d * k), -(CART_H / 2 - d)),
                               ((CART_W / 2 - d), -(CART_H / 2 - d) + (5 - d * k)), ((CART_W / 2 - d), (CART_H / 2 - d) - (18 - d * k)),
                               ((CART_W / 2 - d) - (18 - d * k), (CART_H / 2 - d)), (-(CART_W / 2 - d) + (18 - d * k), (CART_H / 2 - d)),
                               (-(CART_W / 2 - d), (CART_H / 2 - d) - (18 - d * k)), (-(CART_W / 2 - d), -(CART_H / 2 - d) + (5 - d * k))])(2 - SQ2)
    shell(Mc0, cs, [(0.0, 0.0), (0.0, CART_D - 3.0)] + bevel(CART_D, 3.0), 'graphite')
    Mc = Mb @ T(cx, czc, -(CART_IN - BZ_H))              # the cartridge face, h toward the viewer
    shell(Mc @ T(-86.0, 5.0, 0.0), lambda d: rrv(16, 250, 8, d, 3, 1.0), [(0.0, 0.0), (0.0, 4.0)] + bevel(6.0, 2.0), 'graphite')
    shell(Mc @ T(88.0, -15.0, 0.0), lambda d: rrv(24, 330, 4, d, 2, 1.0), [(0.0, 0.0), (0.0, 2.0)] + bevel(3.0, 1.0), 'graphite')
    for sx in (-1, 1):
        screw(Mc @ T(sx * 85.0, CART_H / 2 - 24.0, 0.0))
    # handle: mounts 40 proud, the bar between them with the finger gap behind it
    mount = [(0.0, 0.0), (0.0, 36.0)] + bevel(40.0, 4.0)
    shell(Mc @ T(HX, 139.5, 0.0), lambda d: rrv(84, 92, 12, d, 3, 2.0), mount, 'aluminium')
    shell(Mc @ T(HX, -142.5, 0.0), lambda d: rrv(84, 70, 12, d, 3, 2.0), mount, 'aluminium')
    shell(Mc @ T(HX, 152.0, 40.0), lambda d: rrv(46, 40, 4, d, 2, 1.0), [(0.0, 0.0), (0.0, 0.8)], 'teal')
    shell(Mc @ T(HX, 113.0, 40.0), lambda d: rrv(34, 11, 5.5, d, 3, 0.5), [(0.0, 0.0), (0.0, 1.5)] + bevel(2.5, 1.0), 'aluminium')
    b.prism(Mc @ T(HX, -7.0, 0.0), 70.0, 221.0, 6.0, 2,
            bevel(26.0, 3.0, up=False) + [(0.0, 29.0), (0.0, 37.0)] + bevel(40.0, 3.0), 'aluminium')


def empty_inside(cx, cz):
    zf = cz - OPH / 2                                      # pocket floor
    yb = Y_PLATE + POCKET - BZ_H                           # back wall, +100
    Mfl = plane((cx, 0.0, zf), (1, 0, 0), (0, 1, 0))       # floor: u = x - cx, v = y, normal +Z
    shell(Mfl @ T(0.0, -95.0, 0.0), lambda d: rrv(215, 350, 4, d, 1, 0.5), [(0.0, 0.0), (0.0, 6.0)] + bevel(8.0, 2.0), 'graphite')
    for sx in (-1, 1):
        shell(Mfl @ T(sx * 114.0, -95.0, 0.0), lambda d: rrv(10, 350, 2, d, 1, 0.5), [(0.0, 0.0), (0.0, 10.0)], 'graphite')
    Mbk = plane((cx, yb, 0.0), (1, 0, 0), (0, 0, 1))      # back wall, normal -Y
    shell(Mbk @ T(-15.0, cz + 5.0, 0.0), lambda d: rrv(160, 330, 6, d, 2, 1.0), [(0.0, 0.0), (0.0, 8.0)] + bevel(10.0, 2.0), 'graphite')
    b.prism(T(cx + 95.0, yb - 22.0, zf), 14.0, 14.0, 3.0, 1, [(0.0, 0.0), (0.0, OPH)], 'graphite')


for r, c, cx, cz in cells:
    pocket(Mb, cx, cz, bezel_shape, BEZEL_LV, ['graphite'] * (len(BEZEL_LV) - 1), None, floor=False)
    deep = pocket(Mb, cx, cz, bezel_shape, [(BZ_LIP, -40.0), (BZ_LIP, -(POCKET - BZ_H))], ['graphite'], 'graphite')
    x0, z0 = cx - OPW / 2, cz - OPH / 2
    gusset(x0, z0, 1)
    gusset(x0 + OPW, z0, -1)
    if (r, c) in EMPTY:
        empty_inside(cx, cz)
    else:
        HIDDEN.add(deep)
        cartridge(cx, cz)

# ---------------- right column: keypad and the access panel screws ----------------
ku = KEY_X + UO
shell(Mf @ T(ku, KEY_Z, 0.0), lambda d: rrv(124, 255, 14, d, 3, 2.0), [(0.0, 0.0), (0.0, 10.0)] + bevel(14.0, 4.0), 'graphite')
shell(Mf @ T(ku, KEY_Z + 56.5, 14.0), lambda d: rrv(84, 46, 4, d, 2, 1.0), [(0.0, 0.0), (0.0, 0.8)], 'teal')
for k in range(4):
    for i in range(3):
        shell(Mf @ T(ku + (i - 1) * 29.0, KEY_Z + 8.0 - 26.0 * k, 14.0), lambda d: rrv(22, 19, 3, d, 2, 0.5),
              [(0.0, 0.0), (0.0, 2.5)] + bevel(4.0, 1.5), 'plastic')
for x, z in ((575.0, 590.0), (710.0, 590.0), (575.0, 262.0), (710.0, 262.0)):
    screw(Mf @ T(x + UO, z, 0.0))

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
PREVIEW = {'white': (0.83, 0.82, 0.79), 'aluminium': (0.6, 0.62, 0.64), 'graphite': (0.06, 0.065, 0.07),
           'orange': (0.85, 0.22, 0.03), 'teal': (0.2, 0.75, 0.78), 'plastic': (0.13, 0.14, 0.15)}
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
