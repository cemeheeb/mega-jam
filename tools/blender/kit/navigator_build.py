"""Navigator console (SourceArt/environment/bridge/navigator-console), rebuilt from the Tripo mesh by its measurements.

Run in the live Blender (MCP): exec(open(<this file>).read()). Millimetres, scaled to metres at build.
Tripo units x 1582 = mm: the desk is 1500 mm wide like the grey box it replaces. Heights checked against the Tripo
mesh by rays (desk top 1003, mat flush in a 3 mm inset, slope 37 degrees from y 133 to 228, shelf 1074).
Blender axes: X across the console, the operator stands at -Y, Z up. Origin: middle of the footprint on the floor.

Objects (collection NavigatorConsole, one material NavigatorConsole):
- NavigatorConsole: cabinet with the orange stripe groove, plinth with feet, desk (ends rounded in plan at the front,
  the mat inset between them), the sloped strip with three dark plates (the middle one thin: in the Tripo mesh the
  toggles stand on the bare slope, in the picture the strip is dark all along); on them, on one grid, keys and
  seven illuminated on/off rocker switches in place of the Tripo toggles (the author's changes of 14.11);
- NavigatorMonitorLeft / NavigatorMonitorRight: the same geometry and islands (the left mesh is a copy), except the
  left screen, which has an island of its own; children of the console, origin at the bottom of the stand foot.
"""
import bpy, importlib, sys
from math import sin, cos, tan, pi, radians, degrees, hypot, atan2, acos, ceil
from mathutils import Vector, Matrix

KIT_DIR = '/Users/cemeheeb/Projects/ludum-dare/tools/blender/kit'
if KIT_DIR not in sys.path:
    sys.path.insert(0, KIT_DIR)
import kit_lib
importlib.reload(kit_lib)
from kit_lib import B, I4, T, frame, rr, bevel, build

KIT = 'NavigatorConsole'
col = bpy.data.collections.get(KIT) or bpy.data.collections.new(KIT)
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
mat = bpy.data.materials.get(KIT) or bpy.data.materials.new(KIT)
MM = 0.001
MIRROR_X = Matrix.Scale(-1, 4, (1, 0, 0))

# ---------------- measurements, mm ----------------
CAB_W2 = 740             # cabinet half width
CAB_Y0, CAB_Y1 = -193, 460
CAB_RF, CAB_RB = 80, 20  # front / back corner radii in plan
Z_PLINTH = 123           # plinth top = cabinet bottom
Z_DESK = 889             # desk underside = cabinet top
STRIPE = (157, 225, 6)   # orange stripe groove: bottom, top, depth
FOOT_W2 = 729            # plinth feet: 11 mm in from the cabinet sides
CUT_X = 479              # front and back toe cut-outs between the feet
CUT_Y0, CUT_Y1 = -84, 358
CUT_R = 40               # rounded top corners of the cut-outs
DESK_W2 = 750
DESK_Y0, DESK_Y1 = -460, 460
Z_TOP = 1003             # desk top
Z_MAT = 1000             # mat: flush with a 3 mm edge (Tripo: a groove at x = +-662, no pocket)
POCKET_X = 662           # desk ends (cheeks) from here to DESK_W2
POCKET_Y0, POCKET_Y1 = -395, 92
END_R = 55               # desk ends: front outer corner rounded in plan
Y_JOIN = 100             # cheek: flat front block up to here, sloped profile behind
SLOPE_Y0, SLOPE_Y1 = 133, 228    # straight part of the slope (37 degrees), fillets on both ends
Z_SHELF = 1074
MON_X = 358              # monitor centres
MON_W, MON_H, MON_D = 669, 413, 53
MON_Y, MON_Z = 320, 1375          # housing centre
MON_TILT = 4                      # degrees, the top leans back
BEZEL = (27, 21, 47)              # sides, top, bottom
FOOT = (350, 152, 14, 343)        # stand foot: width, depth, thickness, centre y
NECK = (165, 45, 1080, 1300, 362) # neck: width, depth, bottom, top, centre y


# ---------------- helpers (as in Singula console_build.py) ----------------
def arc(cx, cz, R, a0, a1, steps=3):
    return [(cx + R * cos(radians(a0 + (a1 - a0) * k / steps)), cz + R * sin(radians(a0 + (a1 - a0) * k / steps))) for k in range(steps + 1)]


def slab_yz(b, poly, x0, x1, zone):
    """Polygon in world YZ, thickness along X."""
    b.slab(T((x0 + x1) / 2, 0, 0) @ frame((0, 1, 0), (1, 0, 0), (0, 0, -1)), [(y, -z) for y, z in poly], x1 - x0, zone)


def slab_xz(b, poly, y0, y1, zone):
    """Polygon in world XZ, thickness along Y."""
    b.slab(T(0, (y0 + y1) / 2, 0), poly, y1 - y0, zone)


def rounded(poly, radii):
    """Closed polygon with fillets: radii[i] at vertex i (0 = sharp), arcs in steps of at most 30 degrees.
    Works for convex and concave corners."""
    n = len(poly)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % n])
        R = radii[i]
        if R <= 0:
            out.append(tuple(p1))
            continue
        a, c = (p0 - p1).normalized(), (p2 - p1).normalized()
        ang = acos(max(-1.0, min(1.0, a.dot(c))))          # interior angle between the two edges
        t = R / tan(ang / 2)                               # tangent length
        q0, q2 = p1 + a * t, p1 + c * t
        bis = (a + c).normalized()
        ctr = p1 + bis * (R / sin(ang / 2))
        a0 = atan2(q0.y - ctr.y, q0.x - ctr.x)
        a1 = atan2(q2.y - ctr.y, q2.x - ctr.x)
        d = (a1 - a0 + pi) % (2 * pi) - pi
        steps = max(1, ceil(abs(degrees(d)) / 30 - 1e-6))
        for k in range(steps + 1):
            t_ = a0 + d * k / steps
            out.append((ctr.x + R * cos(t_), ctr.y + R * sin(t_)))
    return out


def shell(b, M, shape, prof, zones, cap0=True, cap1=True, cap1_zone=None, cuts=None):
    """Singula console_build.shell: outline shape(d) through (inset, z) levels; flat steps and caps projected exactly,
    walls and roundings as straight strips at their mean inset. cap1_zone: zone of the top cap (default: last segment).
    cuts: outline point indices where a wall strip starts a new island (a long wrap-around strip would set the scale
    of the whole atlas)."""
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
                per.append(per[-1] + hypot(ref[(i + 1) % N][0] - ref[i][0], ref[(i + 1) % N][1] - ref[i][1]))
            vs = [0.0]
            for j in range(j0, j1):
                vs.append(vs[-1] + hypot(prof[j + 1][0] - prof[j][0], prof[j + 1][1] - prof[j][1]))
            # island and u origin of every outline segment: one strip, or a strip per run between cuts
            starts = sorted(cuts) if cuts else [0]
            seg_isl, seg_u = {}, {}
            for c_, s0 in enumerate(starts):
                s1 = starts[(c_ + 1) % len(starts)] + (N if c_ + 1 == len(starts) else 0)
                isl = b.isl()
                for ii in range(s0, s1):
                    i = ii % N
                    seg_isl[i] = isl
                    seg_u[i] = per[ii] - per[s0] if ii < N else per[N] - per[s0] + per[i]
            for j in range(j0, j1):
                for i in range(N):
                    q = [V(j, i), V(j, i + 1), V(j + 1, i + 1), V(j + 1, i)]
                    t0, t1 = vs[j - j0], vs[j + 1 - j0]
                    u0, u1 = seg_u[i], seg_u[i] + per[i + 1] - per[i]
                    b.face(M, q, [(u0, t0), (u1, t0), (u1, t1), (u0, t1)], seg_isl[i], zones[j])
            last = None
    if cap1:
        isl = last[0] if last and last[1] else b.isl()
        b.face(M, [V(m - 1, i) for i in range(N)], [flat_uv(V(m - 1, i), True) for i in range(N)], isl, cap1_zone or zones[-1])


def box(b, x0, x1, y0, y1, z0, z1, zone, cap0=True, cap1=True, R=0, seg=0):
    b.prism(T((x0 + x1) / 2, (y0 + y1) / 2, 0), x1 - x0, y1 - y0, R, seg, [(0, z0), (0, z1)], zone, split0=0, split1=1, cap0=cap0, cap1=cap1)


def to_metres(b):
    b.F = [([p * MM for p in pts], [(u * MM, v * MM) for u, v in uvs], isl, zone, soft) for pts, uvs, isl, zone, soft in b.F]


PARTS = []      # (name, builder, location, parent, hidden islands)


# ---------------- NavigatorConsole ----------------
b = B()
hid = []


def cab_shape(d):
    """Cabinet plan, CCW from +Z: big rounded front corners, small back ones; same point count for every inset."""
    hw, y0, y1 = CAB_W2 - d, CAB_Y0 + d, CAB_Y1 - d
    rf, rb = CAB_RF - d, CAB_RB - d
    pts = []
    for cx, cy, a, R in ((hw - rf, y0 + rf, -90, rf), (hw - rb, y1 - rb, 0, rb), (-hw + rb, y1 - rb, 90, rb), (-hw + rf, y0 + rf, 180, rf)):
        for k in range(4):
            t = radians(a + 30 * k)
            pts.append((cx + R * cos(t), cy + R * sin(t)))
    return pts


# cabinet: the stripe groove all round; the top is under the desk (open), the bottom shows over the toe cut-outs
s0, s1, sd = STRIPE
hid.append(b.n)                     # the bottom cap island
shell(b, I4, cab_shape, [(0, Z_PLINTH), (0, s0), (sd, s0), (sd, s1), (0, s1), (0, Z_DESK)],
      ['white', 'white', 'orange', 'white', 'white'], cap0=True, cap1=False, cuts=[3, 7, 11, 15])   # a strip per side

# plinth: middle block between the feet (front and back set back), feet full depth with rounded cut-out corners
hid.append(b.n)
box(b, -CUT_X, CUT_X, CUT_Y0, CUT_Y1, 0, Z_PLINTH, 'white', cap0=False, cap1=False)
# Feet: the outer corners rounded in plan like the cabinet over them (author, 14.11), on the same centres across:
# the foot is 11 mm in from the cabinet side, so R = cabinet R - 11 (front 69, back 9); the gap round a corner runs
# from 11 mm at the side to the 2 mm at the front and 0 at the back. A prism up Z whose outline only moves its inner
# side: in along the quarter round of the toe cut-out corner (CUT_R) at the top.
FOOT_Y0, FOOT_Y1 = CAB_Y0 + 2, CAB_Y1
FOOT_RF, FOOT_RB = CAB_RF - (CAB_W2 - FOOT_W2), CAB_RB - (CAB_W2 - FOOT_W2)


def foot_shape(d):
    """Right foot plan, CCW from +Z; d < 0 moves the inner side (x = CUT_X) in by -d."""
    xi = CUT_X + d
    pts = [(xi, FOOT_Y0)]
    for cx, cy, a, R in ((FOOT_W2 - FOOT_RF, FOOT_Y0 + FOOT_RF, -90, FOOT_RF), (FOOT_W2 - FOOT_RB, FOOT_Y1 - FOOT_RB, 0, FOOT_RB)):
        for k in range(4):
            t = radians(a + 30 * k)
            pts.append((cx + R * cos(t), cy + R * sin(t)))
    return pts + [(xi, FOOT_Y1)]


foot_prof = [(0, 0), (0, Z_PLINTH - CUT_R)] + [(-(CUT_R - CUT_R * cos(radians(t))), Z_PLINTH - CUT_R + CUT_R * sin(radians(t))) for t in (30, 60, 90)]
i0 = len(b.F)
b.prism(I4, 0, 0, 0, 0, foot_prof, 'white', split0=0, split1=len(foot_prof) - 1, cap0=False, cap1=False, shape=foot_shape)
i1 = len(b.F)
b.copy(i0, i1, MIRROR_X)

# desk: side profile (y, z), counter-clockwise seen from +X
FRONT_R, LIP_R, SHELF_R, BACK_R = 8, 4, 36, 8
SLOPE_FILLET = 90


def desk_profile(pocket):
    """pocket: the middle piece, full depth with the mat inset; else the cheek's back part from Y_JOIN."""
    y0 = DESK_Y0 if pocket else Y_JOIN
    pts = [(y0, Z_DESK)] + ([(CAB_Y0, Z_DESK)] if pocket else []) + [(DESK_Y1, Z_DESK), (DESK_Y1, Z_SHELF), (SLOPE_Y1, Z_SHELF), (SLOPE_Y0, Z_TOP)]
    rad = [LIP_R if pocket else 0] + ([0] if pocket else []) + [0, BACK_R, SHELF_R, SLOPE_FILLET]
    if pocket:
        pts += [(POCKET_Y1, Z_TOP), (POCKET_Y1, Z_MAT), (POCKET_Y0, Z_MAT), (POCKET_Y0, Z_TOP)]
        rad += [0, 0, 0, 0]
    pts += [(y0, Z_TOP)]
    rad += [FRONT_R if pocket else 0]
    # CCW from +X in (y, z): bottom front -> bottom back -> up the back -> over the top to the front
    return rounded(pts, rad)


def cheek_front_shape(d):
    """Plan of the cheek's front block, CCW from +Z. Only the front edge rounds over (inset d); the corner arc
    slides with it so the outer side, the inner side and the back stay put and meet the other parts flush."""
    cx, cy, R = DESK_W2 - END_R + d, DESK_Y0 + END_R, END_R - d
    return [(POCKET_X, DESK_Y0 + d)] + [(cx + R * cos(radians(a)), cy + R * sin(radians(a))) for a in (-90, -60, -30, 0)] + \
           [(DESK_W2, Y_JOIN), (POCKET_X, Y_JOIN)]


def desk_zones(poly):
    """Zone per profile edge: the pocket floor is the dark mat, everything else paint."""
    z = []
    n = len(poly)
    for i in range(n):
        (ya, za), (yb, zb) = poly[i], poly[(i + 1) % n]
        mat_floor = abs(za - Z_MAT) < 1e-6 and abs(zb - Z_MAT) < 1e-6
        z.append('graphite' if mat_floor else 'white')
    return z


def slab_yz_zones(b, poly, x0, x1, zones):
    """slab_yz with a zone per rim edge (caps take the first zone)."""
    M = T((x0 + x1) / 2, 0, 0) @ frame((0, 1, 0), (1, 0, 0), (0, 0, -1))
    P = [Vector((y, -z)) for y, z in poly]
    Z = list(zones)
    n = len(P)
    if sum(P[i].x * P[(i + 1) % n].y - P[(i + 1) % n].x * P[i].y for i in range(n)) < 0:
        P.reverse()
        Z = [Z[(-i - 2) % n] for i in range(n)]
    w = x1 - x0
    h = w / 2
    ic, ir = b.isl(), b.isl()
    b.face(M, [(p.x, -h, p.y) for p in P], [(p.x, p.y) for p in P], ic, 'white')
    b.face(M, [(p.x, h, p.y) for p in P[::-1]], [(p.x, p.y) for p in P[::-1]], ic, 'white')
    L = 0.0
    for i in range(n):
        a, c = P[i], P[(i + 1) % n]
        if i > 0:
            # the rim breaks into islands at sharp turns between edges of at least 10 mm (not at the 3 mm mat walls)
            pa = P[i - 1]
            if (a - pa).length >= 10 and (c - a).length >= 10 and (a - pa).normalized().dot((c - a).normalized()) < 0.5:
                ir, L = b.isl(), 0.0
        L2 = L + (c - a).length
        b.face(M, [(a.x, -h, a.y), (a.x, h, a.y), (c.x, h, c.y), (c.x, -h, c.y)], [(L, w), (L, 0), (L2, 0), (L2, w)], ir, Z[i])
        L = L2
    return ic, ir


cheek = desk_profile(False)
i0 = len(b.F)
shell(b, I4, cheek_front_shape, bevel(Z_DESK, LIP_R, up=False) + [(0, Z_DESK + LIP_R), (0, Z_TOP - FRONT_R)] + bevel(Z_TOP, FRONT_R),
      'white', cap0=True, cap1=True)                    # the right end of the desk; the left end is its mirror
slab_yz(b, cheek, POCKET_X, DESK_W2, 'white')
i1 = len(b.F)
b.copy(i0, i1, MIRROR_X)
mid = desk_profile(True)
ic, ir = slab_yz_zones(b, mid, -POCKET_X, POCKET_X, desk_zones(mid))   # its end caps lie on the cheeks: dropped below

# sloped strip: frame on the slope plane, s up the slope from its foot, local z along the normal
SL = Vector((SLOPE_Y1 - SLOPE_Y0, Z_SHELF - Z_TOP))
SLOPE_LEN = SL.length
u = SL.normalized()
nrm = Vector((-u.y, u.x))


def on_slope(x, s, h=0.0):
    return T(x, SLOPE_Y0 + u.x * s + nrm.x * h, Z_TOP + u.y * s + nrm.y * h) @ frame((1, 0, 0), (0, u.x, u.y), (0, nrm.x, nrm.y))


# Everything on the strip stands on one grid (author, 14.11: «все кнопки должны быть распределены по сетке»):
# cells 40 mm along the strip (column centres x = 20 + 40 k) and 36 mm up the slope (rows at s 40 and 76).
# Keys 30 x 28 fill one cell, wide keys two. Plates end on cell borders: left 14 cells, middle 8, right 8.
CELL_X, ROW_S = 40, (40, 76)
gx = lambda k: 20 + CELL_X * k
PLATE_S = (20, 96)
PLATE_TOP, MID_TOP = 4.0, 1.5
PANEL_UV = 2.5          # the plates, keys and switches get 2.5 times the texel density: their scratches are finer
PANEL = [b.n]           # islands of the panel: from here to the end of the switches (author, 14.11)
for x0, x1, top, bv in ((-600, -40, PLATE_TOP, 1.5), (-40, 280, MID_TOP, 1.0), (280, 600, PLATE_TOP, 1.5)):
    hid.append(b.n)
    b.prism(on_slope((x0 + x1) / 2, sum(PLATE_S) / 2), x1 - x0, PLATE_S[1] - PLATE_S[0], 5, 3,
            [(0, -3), (0, top - bv)] + bevel(top, bv), 'plastic', split0=0, split1=1, cap0=False)


def moved(x0, s0_, h0, x, s, h):
    """Rigid move along the slope from one spot to another."""
    return on_slope(x, s, h) @ on_slope(x0, s0_, h0).inverted()


def copy_own(i0, i1, M):
    """b.copy, but the copy gets islands of its own: its own place in the atlas, so the keys and switches do not all
    carry the same scratches (the author, 14.11)."""
    n0 = len(b.F)
    b.copy(i0, i1, M)
    remap = {}
    for j in range(n0, len(b.F)):
        pts, uvs, isl, zone, soft = b.F[j]
        if isl not in remap:
            remap[isl] = b.isl()
        b.F[j] = (pts, uvs, remap[isl], zone, soft)


def key(xc, sc, w, h, t, first=None):
    """Key cap on a plate; copies repeat the first key of the same size, each on islands of its own."""
    if first is None:
        i0 = len(b.F)
        b.prism(on_slope(xc, sc, PLATE_TOP), w, h, 3, 3, [(0, -1), (0, t - 1.5)] + bevel(t, 1.5), 'frosted', split0=0, split1=1, cap0=False)
        return (i0, len(b.F), xc, sc)
    i0, i1, x0, s0_ = first
    copy_own(i0, i1, moved(x0, s0_, PLATE_TOP, xc, sc, PLATE_TOP))


KEY_W, KEY_H, KEY_T = 30, 28, 6
KEY2_W = 2 * CELL_X - (CELL_X - KEY_W)          # two cells wide, same gaps
# left plate, columns -15..-2: empty, five, gap, six, empty; the back row of the six starts with a double key
# right plate, columns 7..14: empty, two (a double key over them at the back), gap, three switches, empty
k1 = key(gx(-14), ROW_S[0], KEY_W, KEY_H, KEY_T)
for k in range(-14, -2):
    if k == -9:
        continue
    for r in (0, 1):
        if (k, r) == (-14, 0) or (r == 1 and k in (-8, -7)):
            continue
        key(gx(k), ROW_S[r], KEY_W, KEY_H, KEY_T, first=k1)
for k in (8, 9):
    key(gx(k), ROW_S[0], KEY_W, KEY_H, KEY_T, first=k1)
k2 = key((gx(-8) + gx(-7)) / 2, ROW_S[1], KEY2_W, KEY_H, KEY_T)
key((gx(8) + gx(9)) / 2, ROW_S[1], KEY2_W, KEY_H, KEY_T, first=k2)


SW_S = sum(ROW_S) / 2                            # switches take both rows of their column
SW_H = 2 * (ROW_S[1] - ROW_S[0]) - (ROW_S[1] - ROW_S[0] - KEY_H)    # 64: two cells high, same gaps
SW_TILT = 8


def rocker(xc, h0, on, first=None):
    """Illuminated on/off rocker (author, 14.11: lamps right on the buttons, every toggle of the panel replaced):
    satin bezel over two key cells, the cap rocks about its middle (far end up when on, near end up when off),
    a glass lamp window in the far half of the cap. Caps and bezels of one state repeat the first one, each on islands
    of its own; every lamp window has its own too, so each can take its own colour and lit state in the texture."""
    M = on_slope(xc, SW_S, h0)
    cap = M @ T(0, 0, 3) @ Matrix.Rotation(radians(SW_TILT if on else -SW_TILT), 4, 'X')
    if first is not None:
        i0, i1, x0, hh = first
        copy_own(i0, i1, moved(x0, SW_S, hh, xc, SW_S, h0))
    else:
        i0 = len(b.F)
        b.prism(M, KEY_W, SW_H, 3, 3, [(0, -1), (0, 2)] + bevel(3, 1), 'satin', split0=0, split1=1, cap0=False)
        b.prism(cap, 22, SW_H - 8, 2, 3, [(0, -4), (0, 3.5)] + bevel(5, 1.5), 'frosted', split0=0, split1=1, cap0=False)
        first = (i0, len(b.F), xc, h0)
    b.prism(cap @ T(0, 15, 0), 14, 12, 1.5, 3, [(0, 4), (0, 5.5)] + bevel(6, 0.5), 'glass', split0=0, split1=1, cap0=False)
    return first


# middle plate: four in the middle columns 1..4 (two empty at each end); right plate: columns 11..13
r_on = rocker(gx(1), MID_TOP, True)
r_off = rocker(gx(3), MID_TOP, False)
rocker(gx(2), MID_TOP, True, r_on)
rocker(gx(4), MID_TOP, True, r_on)
for k, on in ((11, True), (12, False), (13, True)):
    rocker(gx(k), PLATE_TOP, on, r_on if on else r_off)
PANEL.append(b.n)

# internal faces where the desk parts meet (coincident pairs would give 4-face edges and confuse the bake rays):
# the middle piece's end caps and the joint walls between the cheek's front block and its sloped back part
b.F = [f for f in b.F if not (f[2] == ic or all(abs(p.y - Y_JOIN) < 1e-6 and abs(p.x) >= POCKET_X - 1e-6 for p in f[0]))]
# the underside of the middle piece over the cabinet is never seen (it closes the cabinet top): no texels for it
b.F = [f for f in b.F if not all(abs(p.z - Z_DESK) < 1e-6 and p.y >= CAB_Y0 - 1e-6 and abs(p.x) <= POCKET_X + 1e-6 for p in f[0])]
PARTS.append(('NavigatorConsole', b, (0, 0, 0), None, hid))


# ---------------- monitor (shared mesh), origin at the bottom centre of the stand foot ----------------
b = B()
hid = []
fw, fd, ft, fy = FOOT
O = Vector((MON_X, fy, Z_SHELF))          # monitor origin in console space (right monitor)
hid.append(b.n)
b.prism(I4, fw, fd, 12, 3, [(0, 0), (0, ft - 3)] + bevel(ft, 3), 'white', split0=0, split1=1, cap0=False)
nw, nd, nz0, nz1, ny = NECK
# the neck: a closed block (author, 14.11: not a hollow tube), its top back edge cut by a chamfer towards the back of
# the housing; seen from the side a rectangle with one corner cut, the chamfer corners rounded; its sides rounded R 6
# like the old box. Built as a prism along X: the side profile is the outline, the bevel rings round the two sides.
NECK_CH, NECK_R = 18, 5


def inset_poly(P, d):
    """A convex CCW polygon moved inwards by d: every edge offset, consecutive lines intersected."""
    n = len(P)
    L = []
    for i in range(n):
        a, c = Vector(P[i]), Vector(P[(i + 1) % n])
        e = (c - a).normalized()
        nn = Vector((-e.y, e.x))
        L.append((a + nn * d, e))
    out = []
    for i in range(n):
        (p, u), (q, v) = L[i - 1], L[i]
        t = ((q - p).x * v.y - (q - p).y * v.x) / (u.x * v.y - u.y * v.x)
        out.append(tuple(p + u * t))
    return out


ny0, ny1, nzb, nzt = ny - fy - nd / 2, ny - fy + nd / 2, ft - 1, nz1 - Z_SHELF
NECK_SIDE = [(ny0, nzb), (ny1, nzb), (ny1, nzt - NECK_CH), (ny1 - NECK_CH, nzt), (ny0, nzt)]
neck_shape = lambda d: rounded(inset_poly(NECK_SIDE, d), [0, 0, max(NECK_R - d, 0.5), max(NECK_R - d, 0.5), 0])
b.prism(frame((0, 1, 0), (0, 0, 1), (1, 0, 0)), 0, 0, 0, 0,
        bevel(-nw / 2, 6, up=False) + [(0, -nw / 2 + 6), (0, nw / 2 - 6)] + bevel(nw / 2, 6), 'white',
        split0=3, split1=4, cap0=True, cap1=True, shape=neck_shape)

sw, st, sb = BEZEL
SCR_W, SCR_H = MON_W - 2 * sw, MON_H - st - sb
SCR_C = (sb - st) / 2                     # screen centre above the housing centre


def mon_shape(d):
    if d < 50:
        return rr(MON_W - 2 * d, MON_H - 2 * d, 12 - d, 3)
    e = d - 100
    return [(x, y + SCR_C) for x, y in rr(SCR_W - 2 * e, SCR_H - 2 * e, 4, 3)]


Mh = T(0, MON_Y - fy, MON_Z - Z_SHELF) @ Matrix.Rotation(radians(-MON_TILT), 4, 'X') @ frame((1, 0, 0), (0, 0, 1), (0, -1, 0)) @ T(0, 0, -MON_D / 2)
shell(b, Mh, mon_shape, [(0, 0), (0, MON_D - 4)] + bevel(MON_D, 4) + [(100, MON_D), (100, MON_D - 10)],
      ['white'] * 5 + ['plastic'], cap0=True, cap1=True, cap1_zone='teal', cuts=[3, 7, 11, 15])
PARTS.append(('NavigatorMonitorRight', b, tuple(O), 'NavigatorConsole', hid))


# ---------------- build ----------------
HIDDEN = {}
objs = {}
for name, b, loc, parent, hid in PARTS:
    for k, (pts, uvs, isl, zone, soft) in enumerate(b.F):
        if isl in hid:
            b.F[k] = (pts, [(u_ * 0.25, v_ * 0.25) for u_, v_ in uvs], isl, zone, soft)
        elif name == 'NavigatorConsole' and PANEL[0] <= isl < PANEL[1]:
            b.F[k] = (pts, [(u_ * PANEL_UV, v_ * PANEL_UV) for u_, v_ in uvs], isl, zone, soft)
    HIDDEN[name] = hid
    to_metres(b)
    ob = build(name, b, Vector(loc) * MM, col, mat)
    if parent:
        ob.parent = objs[parent]
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = Vector(loc) * MM
    objs[name] = ob
    me = ob.data
    print(name, 'faces', len(me.polygons), 'tris', sum(len(p.vertices) - 2 for p in me.polygons), 'islands', b.n,
          'dims mm', [round(d * 1000, 1) for d in ob.dimensions])

# the left monitor: a copy of the right one's mesh; only its screen gets an island of its own (the picture shows a
# star chart on the left screen and orbits on the right), the rest is packed onto the right monitor's islands
right = objs['NavigatorMonitorRight']
left = bpy.data.objects.get('NavigatorMonitorLeft')
if left:
    me_old = left.data
    bpy.data.objects.remove(left)
    if me_old.users == 0 and me_old != right.data:
        bpy.data.meshes.remove(me_old)
me_l = right.data.copy()
me_l.name = 'NavigatorMonitorLeft.Mesh'
zone_a, isl_a = me_l.attributes['zone'].data, me_l.attributes['island'].data
SCREEN_ISLAND = max(a.value for a in isl_a) + 1
for p in me_l.polygons:
    if zone_a[p.index].value == kit_lib.ZONES.index('teal'):
        isl_a[p.index].value = SCREEN_ISLAND
left = bpy.data.objects.new('NavigatorMonitorLeft', me_l)
col.objects.link(left)
left.parent = objs['NavigatorConsole']
left.location = (-MON_X * MM, right.location.y, right.location.z)
HIDDEN['NavigatorMonitorLeft'] = HIDDEN['NavigatorMonitorRight']
bpy.context.scene['kit_hidden'] = HIDDEN
print('total tris', sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (objs['NavigatorConsole'], right, left)))
