"""Sleep capsule (SourceArt/environment/living/sleep-capsule), rebuilt from the Tripo mesh (source/tripo/) and the
approved picture images/sleep-capsule-1.webp (pipeline/kit.md, step 2).

Run in the live Blender (MCP): exec(open(<this file>).read(), {}). Millimetres, scaled to metres at build.
Blender axes: X along the bunk (head at -X, as the pillow in the picture), the open side at -Y, Z up. Origin: middle
of the body footprint on the floor (the step stands out in front of it).

Measurements. Tripo units x 2360 = mm: the body is 2360 x 1000 like the grey boxes of the card. The Tripo mesh is a
trapezoid (end walls 976 deep at the floor, 730 at the top, outer faces leaning in); the author wants a box with no
narrowing (15.11), so every wall is vertical and 1000 deep all the way up. Height: at that scale the Tripo mesh is
1552 mm tall with 0.8 m over the mattress; the author chose 1800 (15.11, "to sit up"): everything below the mattress
top keeps the Tripo heights, the headroom is stretched (canopy underside 1690, 1080 over the mattress) and the parts on
the walls in it move with it.

One object SleepCapsule (collection SleepCapsule, material SleepCapsule):
- end walls 180 mm thick, outer vertical corners rounded 40, the edges at the opening 26, an aluminium cap on top with
  a 24 mm rounding and an aluminium plinth under them;
  head wall: on the inside a raised control panel with a teal rim, the screen strip and a round button, a reading
  lamp (plate, arm, can with the lens), screws of the panels; outside a hatch (seams in the height map) with screws
  and a pull;
  foot wall: on the inside a cubby with a raised frame and a graphite liner, a graphite locker panel over it (as in
  the Tripo mesh; the picture does not show this side); outside a recessed handle with a grip bar and a latch, the
  vertical orange stripe at the front corner;
- base 900 deep (recessed 50 behind the wall fronts, as in the Tripo mesh) with the access panel (two latch slots,
  four screws), a small slot, the orange stripe broken by the panel and running on over the wall fronts (round the
  foot wall's corner onto its outer face, as in the Tripo mesh);
- the aluminium frame of the opening: a 50 x 50 bar with rounded edges, down the posts and along the bed with 70 mm
  inner bends; at the back the same frame, its head post beside the back panel;
- back panel at the head end (in the picture, with a vent grille and an access panel); the rest of the back is open
  as in the picture (the capsule stands with its back to the room wall);
- canopy: aluminium beams at the front and back, a white panel with two dark vent grilles on top; the graphite privacy
  visor under the front beam with rounded corners, a tab and two hinge pins. The Tripo mesh has a second visor and a
  second step at the back: dropped, the back stands against the wall;
- mattress of three cushions (fabric), the pillow (linen, two puffed panels with a seam), the blanket folded in three
  at the foot hanging a little over the front edge;
- the step in front: aluminium body with a graphite rubber tread and two end caps rounded at the front.
Panel seams, the grille slots and the tread ribs go into the height map (as on the dais), not into the mesh.

Zones -> materials (the 3-bit id classes): white paint, aluminium, plastic = dark graphite plastic, graphite = rubber
tread, teal = screen, rim and the lamp lens, orange, fabric = mattress, linen = pillow and blanket.
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

KIT = 'SleepCapsule'
col = bpy.data.collections.get(KIT) or bpy.data.collections.new(KIT)
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
mat = bpy.data.materials.get(KIT) or bpy.data.materials.new(KIT)
MM = 0.001

# ---------------- measurements, mm ----------------
L2, XI, D2, H = 1180.0, 1000.0, 500.0, 1800.0   # half length, inner faces of the end walls, half depth, height
Z_PL, PL_IN = 40.0, 4.0          # aluminium plinth under the end walls
Z_CAP, CAP_B = 1740.0, 24.0      # aluminium cap on the end walls, its top rounding
R_OUT, R_IN = 40.0, 26.0         # end wall vertical corners: outside, at the opening
BASE_Y, Z_BASE = 450.0, 470.0    # base front / back faces, top (the mattress lies on it)
FR_W, FR_Y = 50.0, 435.0         # frame bar 50 x 50, centre line at y = -+435 (front face -460)
FR_X, FR_Z, FR_R = 975.0, 450.0, 95.0      # posts' and rail's centre lines, bend radius of the centre line
FR_BACK_HEAD = -689.0            # back frame: head post beside the back panel
BP_X1, BP_Y0, BP_Y1 = -714.0, 420.0, 460.0 # back panel at the head end: XI..BP_X1, y BP_Y0..BP_Y1
Z_CAN0, Z_CAN1 = 1690.0, 1755.0  # canopy underside and top
BEAM_Y = 400.0                   # beams from -+400 to -+460
VIS_X, VIS_Z0, VIS_Y0, VIS_Y1 = 925.0, 1500.0, -440.0, -420.0
MAT_Y, Z_MAT = 410.0, 610.0
STRIPE = (240.0, 300.0)          # orange stripe, from the Tripo texture
ACCESS = (-610.0, 150.0, 200.0, 350.0)     # base access panel x0, x1, z0, z1
STEP_X0, STEP_X1, STEP_Y0, STEP_Z = -850.0, 970.0, -700.0, 152.0
STEP_CAP, STEP_CR, STEP_B = 70.0, 45.0, 10.0
SCREW = 5.5

b = B()
HIDDEN = set()                   # islands at a quarter of the density (against the room wall, under the mattress)


# ---------------- helpers ----------------
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


def sweep(M, path, prof, zone, caps=False):
    """Closed profile (a, w) swept along a polyline in local XZ: a across the path in its plane, w along local Y,
    mitred joints. One island: u round the profile (exact), v along the path at each profile point; caps (the
    profile itself) share one more island."""
    P = [Vector(p) for p in path]
    n = len(P)

    def nrm(i):
        d = (P[i + 1] - P[i]).normalized()
        return Vector((-d.y, d.x))

    offs = []
    for i in range(n):
        n1 = nrm(i - 1) if i > 0 else nrm(i)
        n2 = nrm(i) if i < n - 1 else nrm(i - 1)
        offs.append((n1 + n2) / (1 + n1.dot(n2)))
    K = len(prof)
    pts = [[(P[i] + offs[i] * a, w) for a, w in prof] for i in range(n)]
    V3 = lambda q: (q[0].x, q[1], q[0].y)
    U = [0.0]
    for k in range(K):
        U.append(U[-1] + hypot(prof[(k + 1) % K][0] - prof[k][0], prof[(k + 1) % K][1] - prof[k][1]))
    Vv = [[0.0] * n for _ in range(K)]
    for k in range(K):
        for i in range(1, n):
            Vv[k][i] = Vv[k][i - 1] + (pts[i][k][0] - pts[i - 1][k][0]).length
    isl = b.isl()
    for i in range(n - 1):
        mid = (P[i] + P[i + 1]) / 2
        for k in range(K):
            k2 = (k + 1) % K
            q = [V3(pts[i][k]), V3(pts[i][k2]), V3(pts[i + 1][k2]), V3(pts[i + 1][k])]
            uv = [(U[k], Vv[k][i]), (U[k + 1], Vv[k2][i]), (U[k + 1], Vv[k2][i + 1]), (U[k], Vv[k][i + 1])]
            ctr = Vector([sum(p[j] for p in q) / 4 for j in range(3)])
            # outward: away from the path centre line (local y is w, measured from the profile centre)
            radial = Vector((ctr.x - mid.x, ctr.y, ctr.z - mid.y))
            if Vector(newell(q)).dot(radial) < 0:
                q.reverse()
                uv.reverse()
            b.face(M, q, uv, isl, zone)
    if caps:
        ic = b.isl()
        for i, sgn in ((0, -1), (n - 1, 1)):
            q = [V3(p) for p in pts[i]]
            uv = [(a, w) for a, w in prof]
            j = 1 if i == 0 else n - 2
            t = Vector((P[i].x - P[j].x, 0.0, P[i].y - P[j].y))      # outwards at both ends
            if Vector(newell(q)).dot(t) < 0:
                q.reverse()
                uv.reverse()
            b.face(M, q, uv, ic, zone)
    return isl


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


# ---------------- end walls ----------------
def paint_band(p):
    return 'orange' if STRIPE[0] < p.z < STRIPE[1] else 'white'


def end_wall(s):
    xo, xi, xc = s * L2, s * XI, s * (XI + L2) / 2
    radii = (R_OUT, R_OUT, R_IN, R_IN) if s > 0 else (R_IN, R_IN, R_OUT, R_OUT)
    plan = lambda d: rr4(xc, 0.0, L2 - XI, 2 * D2, radii, d)
    b.prism(I4, 0, 0, 0, 0, [(PL_IN, 0.0), (PL_IN, Z_PL), (0.0, Z_PL)], 'aluminium', cap0=False, cap1=False, shape=plan)
    b.prism(I4, 0, 0, 0, 0, [(0.0, Z_CAP), (0.0, H - CAP_B)] + bevel(H, CAP_B), 'aluminium', cap0=False, shape=plan)
    zc = sorted([Z_PL, STRIPE[0], STRIPE[1], Z_CAP] + ([1190.0, 1550.0] if s > 0 else []))
    cv = zc[1:-1]
    yo = D2 - R_OUT                   # outer face spans -yo..yo
    xf0, xf1 = sorted((s * (XI + R_IN), s * (L2 - R_OUT)))      # front / back faces span x
    yi = D2 - R_IN                    # inner face spans -yi..yi

    # outer face (u = s * y)
    Mo = plane((xo, 0, 0), (0, s, 0), (0, 0, 1))
    if s > 0:
        def zo(p):
            if STRIPE[0] < p.z < STRIPE[1] and p.y < -340:
                return 'orange'
            return 'orange' if (-450 < p.y < -410 and 1190 < p.z < 1550) else 'white'
        hc, lc = (330.0, 800.0), (330.0, 200.0)
        hshape = lambda d: rr(56 - 2 * d, 130 - 2 * d, 14 - d, 3)
        lshape = lambda d: rr(34 - 2 * d, 64 - 2 * d, 8 - d, 3)
        holes = [[(hc[0] + x, hc[1] + y) for x, y in hshape(0)], [(lc[0] + x, lc[1] + y) for x, y in lshape(0)]]
        region(Mo, [(-yo, Z_PL), (yo, Z_PL), (yo, Z_CAP), (-yo, Z_CAP)], holes, b.isl(), zo, cuts_u=(-450, -410, -340), cuts_v=cv)
        pocket(Mo, hc[0], hc[1], hshape, [(0, 0), (2, -2), (2, -30)], ['white', 'white'], 'white')
        b.tube(Mo, [(hc[0], hc[1] - 63, -14), (hc[0], hc[1] + 63, -14)], 7, 12, 'aluminium', caps=(False, False))
        pocket(Mo, lc[0], lc[1], lshape, [(0, 0), (1.5, -1.5), (1.5, -8)], ['white', 'white'], 'plastic')
        for u, v in ((-420, 90), (420, 90), (-420, 1650), (420, 1650), (-420, 560), (420, 560)):
            screw(Mo @ T(u, v, 0))
    else:
        pc = (185.0, 193.0)           # pull of the hatch (u = -y)
        pshape = lambda d: rr(64 - 2 * d, 20 - 2 * d, 8 - d, 3)
        region(Mo, [(-yo, Z_PL), (yo, Z_PL), (yo, Z_CAP), (-yo, Z_CAP)], [[(pc[0] + x, pc[1] + y) for x, y in pshape(0)]],
               b.isl(), 'white', cuts_v=cv)
        pocket(Mo, pc[0], pc[1], pshape, [(0, 0), (1.5, -1.5), (1.5, -8)], ['white', 'white'], 'plastic')
        for u, v in ((-300, 140), (350, 140), (-300, 350), (350, 350), (-300, 930), (300, 930)):
            screw(Mo @ T(u, v, 0))
    # front face (u = x) and back face (u = -x)
    Mf = plane((0, -D2, 0), (1, 0, 0), (0, 0, 1))
    region(Mf, [(xf0, Z_PL), (xf1, Z_PL), (xf1, Z_CAP), (xf0, Z_CAP)], [], b.isl(), paint_band, cuts_v=cv)
    for v in (120, 560, 1100, 1660):
        screw(Mf @ T(xc, v, 0))
    Mb = plane((0, D2, 0), (-1, 0, 0), (0, 0, 1))
    ib = b.isl()
    HIDDEN.add(ib)
    region(Mb, [(-xf1, Z_PL), (-xf0, Z_PL), (-xf0, Z_CAP), (-xf1, Z_CAP)], [], ib, 'white', cuts_v=cv)
    # corners
    if s > 0:
        vcorner((L2 - R_OUT, -yo), R_OUT, -90, zc, paint_band)
        vcorner((L2 - R_OUT, yo), R_OUT, 0, zc, 'white')
        vcorner((XI + R_IN, yi), R_IN, 90, zc, 'white')
        vcorner((XI + R_IN, -yi), R_IN, 180, zc, paint_band)
    else:
        vcorner((-L2 + R_OUT, -yo), R_OUT, 180, zc, paint_band)
        vcorner((-L2 + R_OUT, yo), R_OUT, 90, zc, 'white')
        vcorner((-XI - R_IN, yi), R_IN, 0, zc, 'white')
        vcorner((-XI - R_IN, -yi), R_IN, 270, zc, paint_band)
    # inner face (u = -s * y): what the base and the canopy leave free
    Mi = plane((xi, 0, 0), (0, -s, 0), (0, 0, 1))
    world = [(-yi, Z_PL), (-BASE_Y, Z_PL), (-BASE_Y, Z_BASE), (BASE_Y, Z_BASE), (BASE_Y, Z_PL), (yi, Z_PL),
             (yi, Z_CAP), (FR_Y + FR_W / 2 - 6, Z_CAP), (FR_Y + FR_W / 2 - 6, Z_CAN0), (-FR_Y - FR_W / 2 + 6, Z_CAN0),
             (-FR_Y - FR_W / 2 + 6, Z_CAP), (-yi, Z_CAP)]     # the beams' 6 mm bottom roundings stay on the wall
    outer = [(-s * y, z) for y, z in world]
    zi = lambda p: 'orange' if (STRIPE[0] < p.z < STRIPE[1] and p.y < -BASE_Y + 1) else 'white'
    if s > 0:
        cc = (-100.0, 760.0)          # cubby: y = +100
        cshape = lambda d: rr(320 - 2 * d, 220 - 2 * d, 14 - d, 3)
        region(Mi, outer, [[(cc[0] + x, cc[1] + y) for x, y in cshape(-30)]], b.isl(), zi, cuts_v=cv)
        pocket(Mi, cc[0], cc[1], cshape, [(-30, 0), (-30, 3), (-27, 6), (-3, 6), (0, 3), (0, -120)],
               ['white', 'white', 'white', 'white', 'plastic'], 'plastic')
        # locker panel over it
        shell(Mi @ T(-100, 1230, 0), lambda d: rr(320 - 2 * d, 560 - 2 * d, 14 - d, 3),
              [(0, 0), (0, 3)] + bevel(5, 2), 'plastic')
        for u, v in ((-380, 640), (380, 640), (-380, 1640), (380, 1640)):
            screw(Mi @ T(u, v, 0))
    else:
        region(Mi, outer, [], b.isl(), zi, cuts_v=cv)
        head_inside(Mi)


def head_inside(Mh):
    """Head wall, inside (u = y): control panel, lamp, panel screws."""
    cu, cv = -45.0, 944.0
    shell(Mh @ T(cu, cv, 0), lambda d: rr(700 - 2 * d, 150 - 2 * d, 22 - d, 3),
          [(0, 0), (0, 8)] + bevel(11, 3) + [(11, 11), (12, 8)],
          ['plastic', 'plastic', 'plastic', 'plastic', 'teal', 'plastic'], cap1_zone='plastic')
    shell(Mh @ T(cu - 210, cv + 12, 8), lambda d: rr(210 - 2 * d, 36 - 2 * d, 5 - d, 2), [(0, 0), (0, 1.5)],
          ['plastic'], cap1_zone='teal')
    for k in range(3):        # three small indicators under the screen
        shell(Mh @ T(cu - 280 + 40 * k, cv - 32, 8), lambda d: rr(26 - 2 * d, 6 - 2 * d, 2.5 - d, 2), [(0, 0), (0, 1)],
              ['plastic'], cap1_zone='teal')
    b.lathe(Mh @ T(cu + 290, cv, 8), 16, [('strip', [(22, 0), (22, 6)], 'plastic'),
                                         ('polar', [(22, 6), (20, 8), (0, 8)], 'plastic', 'end')])
    # reading lamp
    lu, lv = -170.0, 1260.0
    b.lathe(Mh @ T(lu, lv, 0), 16, [('strip', [(32, 0), (32, 5)], 'plastic'),
                                   ('polar', [(32, 5), (29, 8), (0, 8)], 'plastic', 'end')])
    b.tube(Mh, [(lu, lv, 7), (lu, lv, 42)], 7, 12, 'plastic', caps=(False, True))
    tip = Mh @ Vector((lu, lv, 44))
    d = Vector((0.45, -0.15, -0.88)).normalized()
    ex = d.cross(Vector((0, 0, 1))).normalized()
    ey = d.cross(ex)
    Ml = frame(ex, ey, d, tip - d * 22)
    if Ml.determinant() < 0:
        Ml = frame(-ex, ey, d, tip - d * 22)
    b.lathe(Ml, 16, [('polar', [(0, 0), (27, 0), (30, 3)], 'plastic', 'start'), ('strip', [(30, 3), (30, 80)], 'plastic'),
                     ('polar', [(30, 80), (24, 80)], 'plastic', 'end'), ('strip', [(24, 80), (24, 74)], 'plastic'),
                     ('polar', [(24, 74), (0, 74)], 'teal', 'end')])
    for u, v in ((-385, 1125), (385, 1125), (-385, 1675), (385, 1675), (-385, 625), (385, 625), (-385, 790), (385, 790)):
        screw(Mh @ T(u, v, 0))


end_wall(1)
end_wall(-1)

# ---------------- base ----------------
Mbf = plane((0, -BASE_Y, 0), (1, 0, 0), (0, 0, 1))
ax0, ax1, az0, az1 = ACCESS
acu, acv = (ax0 + ax1) / 2, (az0 + az1) / 2
ashape = lambda d: rr(ax1 - ax0 - 2 * d, az1 - az0 - 2 * d, 15 - d, 3)
sshape = lambda d: rr(30 - 2 * d, 9 - 2 * d, 4 - d, 3)
lat = lambda d: rr(28 - 2 * d, 8 - 2 * d, 3.5 - d, 3)
lat_c = [(-390.0, az0 + 22), (-390.0, az1 - 22)]
# the base is a full box under the rails (the rails' bends leave its corners in view)
outer = [(-XI, 0), (STEP_X0, 0), (STEP_X0, STEP_Z), (STEP_X1, STEP_Z), (STEP_X1, 0), (XI, 0), (XI, Z_BASE), (-XI, Z_BASE)]
region(Mbf, outer, [[(acu + x, acv + y) for x, y in ashape(0)], [(-850 + x, 405 + y) for x, y in sshape(0)]], b.isl(),
       lambda p: 'orange' if (STRIPE[0] < p.z < STRIPE[1] and (p.x < -630 or p.x > 170)) else 'white',
       cuts_u=(-630, 170), cuts_v=STRIPE)
pocket(Mbf, acu, acv, ashape, [(0, 0), (1.5, -1.5), (1.5, -4)], ['white', 'white'], 'white',
       floor_holes=[[(x0 + x, y0 + y) for x, y in lat(0)] for x0, y0 in lat_c])
for x0, y0 in lat_c:
    pocket(Mbf, x0, y0, lat, [(0, 0), (1, -1), (1, -4)], ['white', 'white'], 'plastic', h0=-4)
for u, v in ((ax0 + 16, az0 + 16), (ax1 - 16, az0 + 16), (ax0 + 16, az1 - 16), (ax1 - 16, az1 - 16)):
    screw(Mbf @ T(u, v, -4))
pocket(Mbf, -850, 405, sshape, [(0, 0), (1, -1), (1, -5)], ['white', 'white'], 'plastic')
i_hid = b.isl()
HIDDEN.add(i_hid)
region(plane((0, BASE_Y, 0), (-1, 0, 0), (0, 0, 1)), [(-XI, 0), (XI, 0), (XI, Z_BASE), (-XI, Z_BASE)], [], i_hid, 'white')
i_hid = b.isl()
HIDDEN.add(i_hid)
region(plane((0, 0, Z_BASE), (1, 0, 0), (0, 1, 0)), [(-XI, -BASE_Y), (XI, -BASE_Y), (XI, BASE_Y), (-XI, BASE_Y)], [], i_hid, 'white')

# ---------------- frames of the opening ----------------
def frame_path(x0, x1):
    """Posts and rail; the posts end 30 mm up inside the beam, so the open ends never show under its rounding."""
    pts = [(x0, Z_CAN0 + 30)]
    pts += [(x0 + FR_R + FR_R * cos(radians(a)), FR_Z + FR_R + FR_R * sin(radians(a))) for a in (180, 210, 240, 270)]
    pts += [(x1 - FR_R + FR_R * cos(radians(a)), FR_Z + FR_R + FR_R * sin(radians(a))) for a in (270, 300, 330, 360)]
    return pts + [(x1, Z_CAN0 + 30)]


fr_prof = rr(FR_W, FR_W, 6, 3, 12)
sweep(T(0, -FR_Y, 0), frame_path(-FR_X, FR_X), fr_prof, 'aluminium')
sweep(T(0, FR_Y, 0), frame_path(FR_BACK_HEAD, FR_X), fr_prof, 'aluminium')

# ---------------- back panel at the head end ----------------
Mbp = plane((0, BP_Y0, 0), (1, 0, 0), (0, 0, 1))
gc, gshape = (-920.0, 1050.0), (lambda d: rr(110 - 2 * d, 600 - 2 * d, 12 - d, 3))
region(Mbp, [(-XI, Z_BASE + 5), (BP_X1, Z_BASE + 5), (BP_X1, Z_CAN0), (-XI, Z_CAN0)],
       [[(gc[0] + x, gc[1] + y) for x, y in gshape(0)]], b.isl(), 'white')
pocket(Mbp, gc[0], gc[1], gshape, [(0, 0), (1.5, -1.5), (1.5, -6)], ['white', 'white'], 'plastic')
for u, v in ((-823, 766), (-755, 766), (-823, 1334), (-755, 1334)):
    screw(Mbp @ T(u, v, 0))
i_hid = b.isl()
HIDDEN.add(i_hid)
region(plane((0, BP_Y1, 0), (-1, 0, 0), (0, 0, 1)), [(-BP_X1, Z_BASE + 5), (XI, Z_BASE + 5), (XI, Z_CAN0), (-BP_X1, Z_CAN0)],
       [], i_hid, 'white')

# ---------------- canopy ----------------
Mbeam = frame((0, 1, 0), (0, 0, 1), (1, 0, 0), (-XI, 0, 0))
zc_ = (Z_CAN0 + Z_CAN1) / 2
bh = Z_CAN1 - Z_CAN0
b.prism(Mbeam, 0, 0, 0, 0, [(0, 0), (0, 2 * XI)], 'aluminium', cap0=False, cap1=False,
        shape=lambda d: rr4(-(BEAM_Y + FR_Y + FR_W / 2) / 2, zc_, FR_Y + FR_W / 2 - BEAM_Y, bh, (0, 0, 15, 6), d))
b.prism(Mbeam, 0, 0, 0, 0, [(0, 0), (0, 2 * XI)], 'aluminium', cap0=False, cap1=False,
        shape=lambda d: rr4((BEAM_Y + FR_Y + FR_W / 2) / 2, zc_, FR_Y + FR_W / 2 - BEAM_Y, bh, (6, 15, 0, 0), d))
Mtop = plane((0, 0, Z_CAN1), (1, 0, 0), (0, 1, 0))
vent = lambda d: rr(300 - 2 * d, 420 - 2 * d, 15 - d, 3)
vents = [(-770.0, 0.0), (770.0, 0.0)]
region(Mtop, [(-XI, -BEAM_Y), (XI, -BEAM_Y), (XI, BEAM_Y), (-XI, BEAM_Y)],
       [[(x0 + x, y0 + y) for x, y in vent(0)] for x0, y0 in vents], b.isl(), 'white')
for x0, y0 in vents:
    pocket(Mtop, x0, y0, vent, [(0, 0), (1.5, -1.5), (1.5, -5)], ['white', 'white'], 'plastic')
region(plane((0, 0, Z_CAN0), (1, 0, 0), (0, -1, 0)), [(-XI, -BEAM_Y), (XI, -BEAM_Y), (XI, BEAM_Y), (-XI, BEAM_Y)], [],
       b.isl(), 'white')

# visor: wall frame (local x = x, local y = z, local z = -y), rims rounded 5
Mw = kit_lib.wall()
vprof = bevel(-VIS_Y1, 5, up=False) + [(0, -VIS_Y1 + 5), (0, -VIS_Y0 - 5)] + bevel(-VIS_Y0, 5)
b.prism(Mw, 0, 0, 0, 0, vprof, 'plastic',
        shape=lambda d: rr4(0, (VIS_Z0 + Z_CAN0) / 2, 2 * VIS_X, Z_CAN0 - VIS_Z0, (30, 6, 6, 30), d))
tprof = bevel(418, 3, up=False) + [(0, 421), (0, 445)] + bevel(448, 3)
b.prism(Mw, 0, 0, 0, 0, tprof, 'plastic', shape=lambda d: rr4(0, VIS_Z0 - 11, 130, 30, (8, 4, 4, 8), d))
for x0 in (VIS_X, -FR_X + FR_W / 2):
    b.lathe(frame((0, 1, 0), (0, 0, 1), (1, 0, 0), (x0, (VIS_Y0 + VIS_Y1) / 2, Z_CAN0 - 13)), 12,
            [('polar', [(0, 0), (11, 0)], 'aluminium', 'start'), ('strip', [(11, 0), (11, FR_X - FR_W / 2 - VIS_X)], 'aluminium'),
             ('polar', [(11, FR_X - FR_W / 2 - VIS_X), (0, FR_X - FR_W / 2 - VIS_X)], 'aluminium', 'end')])

# ---------------- mattress, pillow, blanket ----------------
mprof = bevel(Z_BASE, 8, up=False) + [(0, Z_BASE + 8), (0, Z_MAT - 25)] + bevel(Z_MAT, 25)
for x0, x1 in ((-985, -586), (-584, 414), (416, 985)):
    b.prism(T((x0 + x1) / 2, 0, 0), x1 - x0, 2 * MAT_Y, 30, 3, mprof, 'fabric', cap0=False)


def pillow(cx, cy, z0, A, C, Tk, ns=12, nt=20):
    """Two puffed panels meeting at a seam 0.32 Tk over the mattress; the bottom squashed flat. UV: arc lengths
    along the grid rows and columns from the middle."""
    zs = 0.32 * Tk
    ss = [sin(pi / 2 * (2 * k / ns - 1)) for k in range(ns + 1)]
    ts = [sin(pi / 2 * (2 * k / nt - 1)) for k in range(nt + 1)]

    def bump(s, t):
        return (max(0.0, 1 - abs(s) ** 3) ** 0.5) * (max(0.0, 1 - abs(t) ** 3) ** 0.5)

    for top in (True, False):
        G = []
        for s in ss:
            row = []
            for t in ts:
                x = A * s * (1 - 0.05 * (1 - t * t))
                y = C * t * (1 - 0.035 * (1 - s * s))
                g = bump(s, t)
                z = z0 + zs + (Tk - zs) * g ** 0.7 if top else z0 + zs * (1 - g ** 0.3)
                row.append(Vector((cx + x, cy + y, z)))
            G.append(row)
        km, lm = ns // 2, nt // 2
        Uu = [[0.0] * (nt + 1) for _ in range(ns + 1)]
        Vv = [[0.0] * (nt + 1) for _ in range(ns + 1)]
        for l in range(nt + 1):
            for k in range(km + 1, ns + 1):
                Uu[k][l] = Uu[k - 1][l] + (G[k][l] - G[k - 1][l]).length
            for k in range(km - 1, -1, -1):
                Uu[k][l] = Uu[k + 1][l] - (G[k][l] - G[k + 1][l]).length
        for k in range(ns + 1):
            for l in range(lm + 1, nt + 1):
                Vv[k][l] = Vv[k][l - 1] + (G[k][l] - G[k][l - 1]).length
            for l in range(lm - 1, -1, -1):
                Vv[k][l] = Vv[k][l + 1] - (G[k][l] - G[k][l + 1]).length
        isl = b.isl()
        for k in range(ns):
            for l in range(nt):
                idx = [(k, l), (k + 1, l), (k + 1, l + 1), (k, l + 1)]
                if not top:
                    idx.reverse()
                b.face(I4, [G[a][c] for a, c in idx], [(Uu[a][c] if top else -Uu[a][c], Vv[a][c]) for a, c in idx], isl, 'linen')


pillow(-765.0, 10.0, Z_MAT, 180.0, 310.0, 125.0)

# blanket folded in three: one cloth zig-zag (local X = -y, width along x), a soft 18 mm profile with rounded hems,
# 2 mm between the layers; the top layer ends 60 mm short of the front fold; the front hangs over the mattress edge
# and the middle puffs up a little
TB, RB = 18.0, 10.0
YB, YF = 250.0, -460.0
z1, z2, z3 = Z_MAT + RB, Z_MAT + 3 * RB, Z_MAT + 5 * RB
path = [(-YB, z1), (-YF, z1)]
path += [(-YF + RB * cos(radians(a)), (z1 + z2) / 2 + RB * sin(radians(a))) for a in (-60, -30, 0, 30, 60)]
path += [(-YF, z2), (-YB, z2)]
path += [(-YB + RB * cos(radians(a)), (z2 + z3) / 2 + RB * sin(radians(a))) for a in (-120, -150, -180, -210, -240)]
path += [(-YB, z3), (-YF - 60, z3)]
# straight runs cut into 90 mm pieces, so the droop and the puff bend them
fine = [path[0]]
for p in path[1:]:
    a, c = Vector(fine[-1]), Vector(p)
    k = max(1, ceil((c - a).length / 90))
    fine += [tuple(a + (c - a) * (j / k)) for j in range(1, k + 1)]
i0 = len(b.F)
sweep(T(685, 0, 0) @ frame((0, -1, 0), (1, 0, 0), (0, 0, 1)), fine, rr(TB, 430, 8, 3, 8), 'linen', caps=True)
for f in range(i0, len(b.F)):
    pts, uvs, isl, zone, soft = b.F[f]
    new = []
    for p in pts:
        xr = (p.x - 685) / 215
        dz = 4 * max(0.0, 1 - xr * xr) * (p.z - Z_MAT) / (6 * RB)
        if p.y < -380:
            dz -= 35 * ((-380 - p.y) / 90) ** 2
        new.append(Vector((p.x, p.y, p.z + dz)))
    b.F[f] = (new, uvs, isl, zone, soft)

# ---------------- step ----------------
bx0, bx1 = STEP_X0 + STEP_CAP, STEP_X1 - STEP_CAP
Msf = plane((0, STEP_Y0, 0), (1, 0, 0), (0, 0, 1))
region(Msf, [(bx0, 0), (bx1, 0), (bx1, STEP_Z - STEP_B), (bx0, STEP_Z - STEP_B)], [], b.isl(), 'aluminium')
isl = b.isl()
arc = [(STEP_Y0 + STEP_B - STEP_B * cos(radians(a)), STEP_Z - STEP_B + STEP_B * sin(radians(a))) for a in (0, 30, 60, 90)]
for k in range(3):
    (ya, za), (yb, zb) = arc[k], arc[k + 1]
    v0, v1 = k * 2 * STEP_B * sin(radians(15)), (k + 1) * 2 * STEP_B * sin(radians(15))
    b.face(I4, [(bx0, ya, za), (bx1, ya, za), (bx1, yb, zb), (bx0, yb, zb)], [(bx0, v0), (bx1, v0), (bx1, v1), (bx0, v1)], isl, 'aluminium')
Mst = plane((0, 0, STEP_Z), (1, 0, 0), (0, 1, 0))
tread =lambda d: rr(bx1 - bx0 - 50 - 2 * d, -BASE_Y - STEP_Y0 - 50 - 2 * d, 6 - d, 3)
tc = ((bx0 + bx1) / 2, (STEP_Y0 - BASE_Y) / 2)
region(Mst, [(bx0, STEP_Y0 + STEP_B), (bx1, STEP_Y0 + STEP_B), (bx1, -BASE_Y), (bx0, -BASE_Y)],
       [[(tc[0] + x, tc[1] + y) for x, y in tread(0)]], b.isl(), 'aluminium')
pocket(Mst, tc[0], tc[1], tread, [(0, 0), (1, -1), (1, -3)], ['aluminium', 'aluminium'], 'graphite')


def cap_shape(side, d):
    """Step end cap in plan: the outer side and the front inset by d, the outer front corner rounded."""
    y0, y1 = STEP_Y0 + d, -BASE_Y
    if side < 0:
        x0, x1 = STEP_X0 + d, bx0
        r = STEP_CR - d
        c = (x0 + r, y0 + r)
        arcp = [(c[0] + r * cos(radians(a)), c[1] + r * sin(radians(a))) for a in (180, 210, 240, 270)]
        return [(x1, y0), (x1, y1), (x0, y1)] + arcp
    x0, x1 = bx1, STEP_X1 - d
    r = STEP_CR - d
    c = (x1 - r, y0 + r)
    arcp = [(c[0] + r * cos(radians(a)), c[1] + r * sin(radians(a))) for a in (270, 300, 330, 360)]
    return [(x0, y0)] + arcp + [(x1, y1), (x0, y1)]


for side in (-1, 1):
    b.prism(I4, 0, 0, 0, 0, [(0, 0), (0, STEP_Z - STEP_B)] + bevel(STEP_Z, STEP_B), 'aluminium', cap0=False,
            shape=lambda d, side=side: cap_shape(side, d))
    cxs = (STEP_X0 + bx0) / 2 if side < 0 else (bx1 + STEP_X1) / 2
    for v in (40, 112):
        screw(Msf @ T(cxs, v, 0))

# ---------------- build ----------------
def buried(pts, zone):
    """Faces the prisms make where they sit against other parts: the beams' inner sides in the canopy panel,
    the step caps' inner sides against the body and their backs against the base."""
    if zone != 'aluminium':
        return False
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    eq = lambda vals, c: all(abs(v - c) < 0.01 for v in vals)
    if (eq(ys, BEAM_Y) or eq(ys, -BEAM_Y)) and min(zs) > Z_CAN0 - 0.01:
        return True
    if max(zs) < STEP_Z + 0.01 and max(ys) < -BASE_Y + 0.01:
        if eq(xs, bx0) or eq(xs, bx1) or eq(ys, -BASE_Y):
            return True
    return False


n0 = len(b.F)
b.F = [f for f in b.F if not buried(f[0], f[3])]
print('buried faces dropped', n0 - len(b.F))
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
           'orange': (0.85, 0.22, 0.03), 'teal': (0.2, 0.75, 0.78), 'plastic': (0.13, 0.14, 0.15),
           'fabric': (0.22, 0.33, 0.33), 'linen': (0.78, 0.76, 0.72)}
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
