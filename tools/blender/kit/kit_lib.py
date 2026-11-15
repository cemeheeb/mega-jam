"""Builders with analytic UVs in metres: every surface is unrolled exactly where it is developable.
Copied unchanged from Singula (tools/blender/kit/kit_lib.py), the kit pipeline of pipeline/kit.md."""
import bpy, bmesh
from mathutils import Vector, Matrix
from math import sin, cos, pi, asin, radians, hypot

# fabric and linen were appended for the sleep capsule (15.11, mattress and bedding); the order stays fixed
ZONES = ['white', 'aluminium', 'graphite', 'orange', 'teal', 'frosted', 'glass', 'satin', 'plastic', 'grille', 'fabric', 'linen']
I4 = Matrix.Identity(4)


def T(x, y, z):
    return Matrix.Translation((x, y, z))


def frame(ex, ey, ez, o=(0, 0, 0)):
    M = Matrix.Identity(4)
    for i, a in enumerate((ex, ey, ez)):
        for j in range(3):
            M[j][i] = a[j]
    for j in range(3):
        M[j][3] = o[j]
    return M


def wall(o=(0, 0, 0)):
    """Outline in world XZ, extrusion towards -Y (away from the wall)."""
    return frame((1, 0, 0), (0, 0, 1), (0, -1, 0), o)


def rr(w, h, R, seg, start=0):
    """Rounded rectangle, CCW seen from +Z. seg == 0 gives sharp corners."""
    if seg == 0:
        pts = [(w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2), (-w / 2, -h / 2)]
    else:
        pts = []
        cs = [(w / 2 - R, -h / 2 + R, -90), (w / 2 - R, h / 2 - R, 0), (-w / 2 + R, h / 2 - R, 90), (-w / 2 + R, -h / 2 + R, 180)]
        for cx, cy, a in cs:
            for k in range(seg + 1):
                t = radians(a + 90 * k / seg)
                pts.append((cx + R * cos(t), cy + R * sin(t)))
    return pts[start:] + pts[:start]


def bevel(z, b, up=True):
    """Quarter round of radius b in 30 degree steps: (inset, z) levels. up: side -> cap at z; else cap at z -> side."""
    lv = [(b - b * cos(radians(t)), (z - b + b * sin(radians(t))) if up else (z + b - b * sin(radians(t)))) for t in (30, 60, 90)]
    return lv if up else lv[::-1]


class B:
    def __init__(s):
        s.F = []
        s.n = 0
        s.soft = False

    def isl(s):
        s.n += 1
        return s.n - 1

    def face(s, M, pts, uvs, isl, zone):
        s.F.append(([M @ Vector(p) for p in pts], [(float(u), float(v)) for u, v in uvs], isl, zone, s.soft))

    def copy(s, i0, i1, M):
        flip = M.determinant() < 0
        for pts, uvs, isl, zone, soft in s.F[i0:i1]:
            p = [M @ q for q in pts]
            u = list(uvs)
            if flip:
                p.reverse()
                u.reverse()
            s.F.append((p, u, isl, zone, soft))

    def slab(s, M, poly, w, zone):
        """Polygon in local XZ extruded along local Y (centred). Both caps share one exact island,
        the rim is one straight strip of exact rectangles."""
        P = [Vector(p) for p in poly]
        n = len(P)
        if sum(P[i].x * P[(i + 1) % n].y - P[(i + 1) % n].x * P[i].y for i in range(n)) < 0:
            P.reverse()
        h = w / 2
        ic, ir = s.isl(), s.isl()
        s.face(M, [(p.x, -h, p.y) for p in P], [(p.x, p.y) for p in P], ic, zone)
        s.face(M, [(p.x, h, p.y) for p in P[::-1]], [(p.x, p.y) for p in P[::-1]], ic, zone)
        L = 0.0
        for i in range(n):
            a, c = P[i], P[(i + 1) % n]
            L2 = L + (c - a).length
            s.face(M, [(a.x, -h, a.y), (a.x, h, a.y), (c.x, h, c.y), (c.x, -h, c.y)], [(L, w), (L, 0), (L2, 0), (L2, w)], ir, zone)
            L = L2

    def lathe(s, M, n, specs, a0=pi / 2, chunks=1):
        """Profile points (r, z); the outside is on the right of the travel direction.
        chunks > 1 cuts every strip into that many islands around the axis, for shorter strips in the atlas."""
        da = 2 * pi / n

        def P(r, z, i):
            a = a0 + i * da
            return (r * cos(a), r * sin(a), z)

        for sp in specs:
            kind, pts, zones = sp[0], sp[1], sp[2]
            if not isinstance(zones, (list, tuple)):
                zones = [zones] * (len(pts) - 1)
            isl = s.isl()
            parts = [isl] + [s.isl() for _ in range(chunks - 1)] if kind == 'strip' else [isl]
            L = [0.0]
            for j in range(len(pts) - 1):
                L.append(L[-1] + hypot(pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]))
            if kind == 'strip':
                rref = sp[3] if len(sp) > 3 else max(p[0] for p in pts)
                du = 2 * rref * sin(pi / n)
                uv = lambda j, i, du=du, L=L: (i * du, L[j])
            elif kind == 'polar':
                if sp[3] == 'start':
                    rho = [pts[0][0] + l for l in L]
                    sg = -1
                else:
                    rho = [pts[-1][0] + (L[-1] - l) for l in L]
                    sg = 1
                uv = lambda j, i, rho=rho, sg=sg: (rho[j] * cos(sg * i * da), rho[j] * sin(sg * i * da))
            else:  # sector: exact development of a faceted cone frustum
                (r0, z0), (r1, z1) = pts
                k = abs(r1 - r0) / hypot(r1 - r0, z1 - z0)
                beta = 2 * asin(k * sin(pi / n))
                sg = 1 if r1 < r0 else -1
                rho = [r0 / k, r1 / k]
                uv = lambda j, i, rho=rho, sg=sg, beta=beta: (rho[j] * cos(sg * i * beta), rho[j] * sin(sg * i * beta))
            for j in range(len(pts) - 1):
                (r0, z0), (r1, z1) = pts[j], pts[j + 1]
                if r0 < 1e-9 and r1 < 1e-9:
                    continue
                if r0 < 1e-9 or r1 < 1e-9:
                    jj = j + 1 if r0 < 1e-9 else j
                    r, z = pts[jj]
                    idx = list(range(n))
                    if r0 < 1e-9:
                        idx.reverse()
                    s.face(M, [P(r, z, i) for i in idx], [uv(jj, i) for i in idx], isl, zones[j])
                    continue
                for i in range(n):
                    c = i * len(parts) // n
                    o = (-c * n) // len(parts)       # minus the first segment of chunk c, ceil(c * n / chunks)
                    q = [uv(j, i), uv(j, i + 1), uv(j + 1, i + 1), uv(j + 1, i)]
                    if len(parts) > 1:
                        q = [(u + o * du, v) for u, v in q]
                    s.face(M, [P(r0, z0, i), P(r0, z0, i + 1), P(r1, z1, i + 1), P(r1, z1, i)], q, parts[c], zones[j])

    def prism(s, M, w, h, R, seg, prof, zones, split0=0, split1=None, cap0=True, cap1=True, start=0, shape=None):
        """Rounded rectangle in local XY extruded along +Z through (inset, z) levels.
        Rings below split0 unfold with the first cap, from split1 on with the last cap, the rest is one straight strip.
        shape(d) replaces the rounded rectangle: the outline inset by d (same point count for every d)."""
        if not isinstance(zones, (list, tuple)):
            zones = (zones, zones, zones)
        m = len(prof)
        if split1 is None:
            split1 = m - 1
        if R <= 0:
            seg = 0
        if shape is None:
            shape = lambda d: rr(w - 2 * d, h - 2 * d, R - d, seg, start)
        O = [shape(d) for d, z in prof]
        N = len(O[0])
        sl = [hypot(prof[j + 1][0] - prof[j][0], prof[j + 1][1] - prof[j][1]) for j in range(m - 1)]
        ref = shape(0)
        per = [0.0]
        for i in range(N):
            per.append(per[-1] + (Vector(ref[(i + 1) % N]) - Vector(ref[i])).length)
        i0, i1, i2 = s.isl(), s.isl(), s.isl()
        d0, d1 = prof[0][0], prof[-1][0]
        c0 = [sum(sl[:j]) for j in range(m)]
        c1 = [sum(sl[j:]) for j in range(m)]
        vs = [sum(sl[split0:j]) for j in range(m)]
        U0 = {j: [(-x, y) for x, y in shape(d0 - c0[j])] for j in range(split0 + 1)}
        U1 = {j: shape(d1 - c1[j]) for j in range(split1, m)}
        V = lambda j, i: (O[j][i % N][0], O[j][i % N][1], prof[j][1])
        if cap0:
            idx = list(range(N))[::-1]
            s.face(M, [V(0, i) for i in idx], [U0[0][i] for i in idx], i0, zones[0])
        if cap1:
            s.face(M, [V(m - 1, i) for i in range(N)], [U1[m - 1][i] for i in range(N)], i2, zones[2])
        for j in range(m - 1):
            for i in range(N):
                q = [V(j, i), V(j, i + 1), V(j + 1, i + 1), V(j + 1, i)]
                if j < split0:
                    uv = [U0[j][i], U0[j][(i + 1) % N], U0[j + 1][(i + 1) % N], U0[j + 1][i]]
                    s.face(M, q, uv, i0, zones[0])
                elif j < split1:
                    uv = [(per[i], vs[j]), (per[i + 1], vs[j]), (per[i + 1], vs[j + 1]), (per[i], vs[j + 1])]
                    s.face(M, q, uv, i1, zones[1])
                else:
                    uv = [U1[j][i], U1[j][(i + 1) % N], U1[j + 1][(i + 1) % N], U1[j + 1][i]]
                    s.face(M, q, uv, i2, zones[2])
        return i0, i1, i2

    def holed_plate(s, M, outline, z, hole, zone, isl=None):
        """Flat face at height z between a convex outline (CCW seen from +Z) and a round hole in its middle.
        The uv are the outline coordinates, so with the island of a prism cap it continues that cap."""
        from math import atan2
        isl = s.isl() if isl is None else isl
        N = len(outline)
        inner = []
        for x, y in outline:
            a = atan2(y, x)
            inner.append((hole * cos(a), hole * sin(a)))
        for i in range(N):
            j = (i + 1) % N
            pts = [outline[i], outline[j], inner[j], inner[i]]
            s.face(M, [(x, y, z) for x, y in pts], pts, isl, zone)

    def sheet(s, M, path, w, t, zone, zone_b=None, closed=False):
        """Bent flat bar: centre line in local XZ, width along local Y. Side A is on the left of the travel
        direction and carries the two edges and the ends in its island; side B is its own rectangle."""
        P = [Vector(p) for p in path]
        n = len(P)
        segs = n if closed else n - 1

        def nrm(i):
            d = (P[(i + 1) % n] - P[i % n]).normalized()
            return Vector((-d.y, d.x))

        A, Bp = [], []
        for i in range(n):
            n1 = nrm(i - 1) if (closed or i > 0) else nrm(i)
            n2 = nrm(i) if (closed or i < n - 1) else nrm(i - 1)
            o = (n1 + n2) / (1 + n1.dot(n2))
            A.append(P[i] + o * t / 2)
            Bp.append(P[i] - o * t / 2)
        h = w / 2
        V = lambda p, y: (p.x, y, p.y)
        uA, uB = [0.0], [0.0]
        for k in range(segs):
            uA.append(uA[-1] + (A[(k + 1) % n] - A[k]).length)
            uB.append(uB[-1] + (Bp[(k + 1) % n] - Bp[k]).length)
        ia, ib = s.isl(), s.isl()
        zb = zone_b or zone
        for k in range(segs):
            i, j = k, (k + 1) % n
            s.face(M, [V(A[i], -h), V(A[j], -h), V(A[j], h), V(A[i], h)], [(uA[k], 0), (uA[k + 1], 0), (uA[k + 1], w), (uA[k], w)], ia, zone)
            s.face(M, [V(Bp[i], h), V(Bp[j], h), V(Bp[j], -h), V(Bp[i], -h)], [(uB[k], 0), (uB[k + 1], 0), (uB[k + 1], w), (uB[k], w)], ib, zb)
            s.face(M, [V(Bp[i], -h), V(Bp[j], -h), V(A[j], -h), V(A[i], -h)], [(uA[k], -t), (uA[k + 1], -t), (uA[k + 1], 0), (uA[k], 0)], ia, zone)
            s.face(M, [V(A[i], h), V(A[j], h), V(Bp[j], h), V(Bp[i], h)], [(uA[k], w), (uA[k + 1], w), (uA[k + 1], w + t), (uA[k], w + t)], ia, zone)
        if not closed:
            U = uA[-1]
            s.face(M, [V(Bp[0], -h), V(A[0], -h), V(A[0], h), V(Bp[0], h)], [(-t, 0), (0, 0), (0, w), (-t, w)], ia, zone)
            s.face(M, [V(A[-1], -h), V(Bp[-1], -h), V(Bp[-1], h), V(A[-1], h)], [(U, 0), (U + t, 0), (U + t, w), (U, w)], ia, zone)

    def gores(s, M, path, r, n, zones, up=(0, 1, 0), share=True):
        """Round duct along a polyline with mitred bends. Every segment is a cylinder cut by its two mitre
        planes and unrolls exactly; the identical middle segments of an even bend share one island."""
        P = [Vector(p) for p in path]
        m = len(P)
        cnt = m - 1
        dirs = [(P[i + 1] - P[i]).normalized() for i in range(cnt)]
        N = Vector(up)
        N = (N - dirs[0] * N.dot(dirs[0])).normalized()
        fr = []
        for i in range(cnt):
            if i > 0:
                N = dirs[i - 1].rotation_difference(dirs[i]) @ N
                N = (N - dirs[i] * N.dot(dirs[i])).normalized()
            fr.append((N.copy(), dirs[i].cross(N)))
        da = 2 * pi / n
        du = 2 * r * sin(pi / n)

        def R(i, k):
            if 0 < i < m - 1:
                d1, d2 = dirs[i - 1], dirs[i]
                Nn, Bn = fr[i - 1]
                c = r * (cos(k * da) * Nn + sin(k * da) * Bn)
                t = (d1 + d2).normalized()
                return P[i] + c - d1 * (c.dot(t) / d1.dot(t))
            Nn, Bn = fr[0] if i == 0 else fr[-1]
            return P[i] + r * (cos(k * da) * Nn + sin(k * da) * Bn)

        if not isinstance(zones, (list, tuple)):
            zones = [zones] * cnt
        first, mid, last = s.isl(), s.isl(), s.isl()
        for i in range(cnt):
            isl = first if i == 0 else last if i == cnt - 1 else mid if share else s.isl()
            c = (P[i] + P[i + 1]) / 2
            v = lambda q, d=dirs[i], c=c: (q - c).dot(d)
            for k in range(n):
                q = [R(i, k), R(i, k + 1), R(i + 1, k + 1), R(i + 1, k)]
                s.face(M, q, [(k * du, v(q[0])), ((k + 1) * du, v(q[1])), ((k + 1) * du, v(q[2])), (k * du, v(q[3]))], isl, zones[i])

    def tube(s, M, path, r, n, zone, caps=(True, True), closed=False, soft=False, chunks=1):
        s.soft = soft
        P = [Vector(p) for p in path]
        m = len(P)
        cnt = m if closed else m - 1
        dirs = [(P[(i + 1) % m] - P[i]).normalized() for i in range(cnt)]
        up = Vector((0, 0, 1)) if abs(dirs[0].z) < 0.9 else Vector((1, 0, 0))
        N = (up - dirs[0] * up.dot(dirs[0])).normalized()
        fr = []
        for i in range(cnt):
            if i > 0:
                N = dirs[i - 1].rotation_difference(dirs[i]) @ N
                N = (N - dirs[i] * N.dot(dirs[i])).normalized()
            fr.append((N.copy(), dirs[i].cross(N)))
        da = 2 * pi / n
        du = 2 * r * sin(pi / n)

        def R(i, k):
            """Ring k-th point at path vertex i: the wire cross-section cut by the mitre plane of the bend."""
            i %= m
            if closed or 0 < i < m - 1:
                d1, d2 = dirs[(i - 1) % cnt], dirs[i % cnt]
                Nn, Bn = fr[(i - 1) % cnt]
                c = r * (cos(k * da) * Nn + sin(k * da) * Bn)
                t = (d1 + d2).normalized()
                return P[i] + c - d1 * (c.dot(t) / d1.dot(t))
            Nn, Bn = fr[0] if i == 0 else fr[-1]
            return P[i] + r * (cos(k * da) * Nn + sin(k * da) * Bn)

        L = [0.0]
        for i in range(cnt):
            L.append(L[-1] + (P[(i + 1) % m] - P[i]).length)
        parts = [s.isl() for _ in range(chunks)]
        for i in range(cnt):
            c = i * chunks // cnt
            v0 = L[-((-c * cnt) // chunks)]      # length at the first segment of chunk c
            for k in range(n):
                s.face(M, [R(i, k), R(i, k + 1), R(i + 1, k + 1), R(i + 1, k)],
                       [(k * du, L[i] - v0), ((k + 1) * du, L[i] - v0), ((k + 1) * du, L[i + 1] - v0), (k * du, L[i + 1] - v0)], parts[c], zone)
        if not closed and (caps[0] or caps[1]):
            ic = s.isl()
            if caps[0]:
                idx = list(range(n))[::-1]
                s.face(M, [R(0, k) for k in idx], [(r * cos(-k * da), r * sin(-k * da)) for k in idx], ic, zone)
            if caps[1]:
                s.face(M, [R(m - 1, k) for k in range(n)], [(r * cos(k * da), r * sin(k * da)) for k in range(n)], ic, zone)
        s.soft = False


def build(name, b, loc, collection, material):
    old = bpy.data.objects.get(name)
    if old:
        me_old = old.data
        bpy.data.objects.remove(old)
        if me_old.users == 0:
            bpy.data.meshes.remove(me_old)
    me = bpy.data.meshes.new(name + '.Mesh')
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    zl = bm.faces.layers.int.new('zone')
    il = bm.faces.layers.int.new('island')
    sl = bm.faces.layers.int.new('soft')
    for pts, uvs, isl, zone, soft in b.F:
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        for l, u in zip(f.loops, uvs):
            l[uvl].uv = u
        f[zl] = ZONES.index(zone)
        f[il] = isl
        f[sl] = int(soft)
        f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-5)
    for e in bm.edges:
        fs = e.link_faces
        seam = len(fs) != 2 or fs[0][il] != fs[1][il]
        if not seam:
            for v in e.verts:
                a = [l[uvl].uv for l in fs[0].loops if l.vert == v][0]
                c = [l[uvl].uv for l in fs[1].loops if l.vert == v][0]
                if (a - c).length > 1e-6:
                    seam = True
        e.seam = seam
    bm.normal_update()
    for e in bm.edges:
        fs = e.link_faces
        if len(fs) == 2:
            e.smooth = all(f[sl] for f in fs) or e.calc_face_angle() <= radians(35)
    bm.faces.layers.int.remove(sl)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    collection.objects.link(ob)
    return ob
