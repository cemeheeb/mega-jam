"""Navigator console, step 5 (pipeline/kit.md): rasterise the atlas (owner, zone, object-space position, face normal,
roundness), then distance fields to wear and cavity edges. Adapted from Singula console_bake1.py.

blender -b <source>/navigator-console.blend --python navigator_bake1.py -- <scratch dir>
The left monitor only adds its screen: the rest of it lies on the right monitor's islands.
"""
import bpy, bmesh, numpy as np, time, math, sys
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree
from mathutils.geometry import tessellate_polygon

SP = sys.argv[sys.argv.index('--') + 1]
RES = 2048
TEAL = 4
t0 = time.time()
objs = [bpy.data.objects[n] for n in ('NavigatorConsole', 'NavigatorMonitorRight', 'NavigatorMonitorLeft')]
owner = np.full((RES, RES), -1, np.int16)
strict = np.zeros((RES, RES), bool)
key = np.full((RES, RES), -1, np.int32)        # (object, island) of the strict owner, for the overlap check
zone = np.zeros((RES, RES), np.uint8)
pos = np.zeros((RES, RES, 3), np.float32)
nrm = np.zeros((RES, RES, 3), np.float32)
compo = np.zeros((RES, RES), np.int32)
rnd = np.zeros((RES, RES), np.float32)
wear_trees, cav_dirs, trees = [], [], []
overlap = 0
for oi, o in enumerate(objs):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    uvl = bm.loops.layers.uv['UVMap']
    zl = bm.faces.layers.int['zone']
    il = bm.faces.layers.int['island']
    piece = {}
    for f in bm.faces:
        if f.index in piece:
            continue
        cid = len(set(piece.values()))
        piece[f.index] = cid
        stack = [f]
        while stack:
            g = stack.pop()
            for e_ in g.edges:
                for h in e_.link_faces:
                    if h.index not in piece:
                        piece[h.index] = cid
                        stack.append(h)

    def roundness(e_):
        fs = e_.link_faces
        if len(fs) != 2 or not e_.smooth:
            return 0.0
        ang = e_.calc_face_angle_signed()
        L = e_.calc_length()
        if ang < math.radians(8) or L < 1e-6:
            return 0.0
        R = 0.5 * (fs[0].calc_area() + fs[1].calc_area()) / L / ang
        return min(max((0.025 - R) / (0.025 - 0.006), 0.0), 1.0)

    for f in bm.faces:
        if o.name == 'NavigatorMonitorLeft' and f[zl] != TEAL:
            continue
        ls = list(f.loops)
        fr = max(roundness(e_) for e_ in f.edges)
        k_ = oi * 100000 + f[il]
        for ta, tb, tc in tessellate_polygon([[Vector((l[uvl].uv.x, l[uvl].uv.y, 0)) for l in ls]]):
            tri = (ls[ta], ls[tb], ls[tc])
            px = np.array([l[uvl].uv for l in tri], np.float64) * RES
            P = np.array([l.vert.co for l in tri], np.float64)
            d = (px[1][1] - px[2][1]) * (px[0][0] - px[2][0]) + (px[2][0] - px[1][0]) * (px[0][1] - px[2][1])
            if abs(d) < 1e-9:
                continue
            x0, y0 = np.floor(px.min(0)).astype(int) - 1
            x1, y1 = np.ceil(px.max(0)).astype(int) + 1
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, RES - 1), min(y1, RES - 1)
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            w0 = ((px[1][1] - px[2][1]) * (xs - px[2][0]) + (px[2][0] - px[1][0]) * (ys - px[2][1])) / d
            w1 = ((px[2][1] - px[0][1]) * (xs - px[2][0]) + (px[0][0] - px[2][0]) * (ys - px[2][1])) / d
            w2 = 1 - w0 - w1
            e = 0.75 / max(abs(d) ** 0.5, 1e-6)
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            near = (w0 >= -e) & (w1 >= -e) & (w2 >= -e)
            sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
            # overlap: a strict texel already taken strictly by another island (shrunk by one texel: shared edges)
            core = inside & (w0 > 0.02) & (w1 > 0.02) & (w2 > 0.02)
            overlap += int((core & strict[sl] & (key[sl] != k_) & (key[sl] >= 0)).sum())
            m = inside | (near & ~strict[sl])
            p = w0[..., None] * P[0] + w1[..., None] * P[1] + w2[..., None] * P[2]
            owner[sl][m] = oi
            zone[sl][m] = f[zl]
            pos[sl][m] = p[m]
            nrm[sl][m] = f.normal
            compo[sl][m] = piece[f.index]
            rnd[sl][m] = fr
            key[sl][inside] = k_
            strict[sl][inside] = True
    strong, weak, cav, cdir = [], [], [], []
    wear = {}
    bvh = BVHTree.FromBMesh(bm)
    bm.faces.ensure_lookup_table()

    def flush_joint(e_, fs):
        """An edge where two parts of the mesh meet flush and carry the same surface on: not a cavity, no grime line
        there (author, 14.11). Two kinds: the desk's middle piece and its ends at x = +-662 share the edge with the
        end's inner wall as a third face (two of the faces coplanar); the end's front block and its sloped back at
        y = 100 end in two open edges side by side (a coplanar face not on this edge within 0.3 mm). A real inside
        corner (the cabinet under the desk overhang) meets a face across, not in line: stays."""
        if len(fs) >= 3:
            return any(fs[i].normal.dot(fs[j].normal) > 0.99 for i in range(len(fs)) for j in range(i + 1, len(fs)))
        if len(fs) != 1:
            return False
        own = fs[0]
        for t in (0.25, 0.5, 0.75):
            p = e_.verts[0].co.lerp(e_.verts[1].co, t)
            if not any(i != own.index and bm.faces[i].normal.dot(own.normal) > 0.9
                       for _, _, i, _ in bvh.find_nearest_range(p, 0.0003)):
                return False
        return True

    joints = 0
    for e_ in bm.edges:
        fs = e_.link_faces
        a, c = e_.verts[0].co, e_.verts[1].co
        L = (c - a).length
        if L < 1e-6:
            continue
        n = max(int(L / 0.0005), 1)
        pts = [a.lerp(c, (k + 0.5) / n) for k in range(n)]
        if len(fs) != 2:
            if flush_joint(e_, fs):
                joints += 1
                continue
            cav += pts
            cdir += [(c - a) / L] * n
            continue
        ang = e_.calc_face_angle_signed()
        if e_.smooth:
            continue
        if ang < 0:
            cav += pts
            cdir += [(c - a) / L] * n
        else:
            strong += pts
            wp, wd = wear.setdefault(piece[fs[0].index], ([], []))
            wp += pts
            wd += [(c - a) / L] * n
    cav_dirs.append(cdir)
    wt = {}
    for cid, (wp, wd) in wear.items():
        t = kdtree.KDTree(len(wp))
        for i, p in enumerate(wp):
            t.insert(p, i)
        t.balance()
        wt[cid] = (t, wd)
    wear_trees.append(wt)
    kd = []
    for pts in (strong, weak, cav):
        t = kdtree.KDTree(max(len(pts), 1))
        for i, p in enumerate(pts or [Vector((99, 99, 99))]):
            t.insert(p, i)
        t.balance()
        kd.append(t)
    trees.append(kd)
    print(o.name, 'edge samples', len(strong), len(weak), len(cav), 'flush joint edges skipped', joints)
    bm.free()
print('raster', round(time.time() - t0, 1), 's, coverage', round(float((owner >= 0).mean()), 3), 'overlap texels', overlap)
dist = np.full((3, RES, RES), 0.05, np.float32)
valid = np.zeros((RES, RES), bool)
ys, xs = np.nonzero(owner[::2, ::2] >= 0)
ys *= 2
xs *= 2
ow = owner[ys, xs]
pp = pos[ys, xs]
nn = nrm[ys, xs]
cc = compo[ys, xs]
t1 = time.time()
for i in range(len(ys)):
    kd = trees[ow[i]]
    p = pp[i]
    n = Vector(nn[i])
    best = 0.05
    wt = wear_trees[ow[i]].get(int(cc[i]))
    if wt:
        for co, k, d in wt[0].find_n(p, 8):
            if abs(wt[1][k].dot(n)) < 0.5:
                best = d
                break
    dist[0, ys[i], xs[i]] = best
    dist[1, ys[i], xs[i]] = kd[1].find(p)[2]
    dirs = cav_dirs[ow[i]]
    best = 0.05
    for co, k, d in kd[2].find_n(p, 8):
        if dirs and abs(dirs[k].dot(n)) < 0.5:
            best = d
            break
    dist[2, ys[i], xs[i]] = best
valid[ys, xs] = True
print('kd', len(ys), round(time.time() - t1, 1), 's')
for it in range(4):
    acc = np.zeros_like(dist)
    cnt = np.zeros((RES, RES), np.float32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            v = np.roll(valid, (dy, dx), (0, 1)) & (np.roll(owner, (dy, dx), (0, 1)) == owner)
            acc += np.roll(dist, (dy, dx), (1, 2)) * v
            cnt += v
    new = (~valid) & (owner >= 0) & (cnt > 0)
    dist[:, new] = acc[:, new] / cnt[new]
    valid |= new
print('unfilled texels', int(((owner >= 0) & ~valid).sum()))
np.savez(SP + '/navigator_bake.npz', owner=owner, zone=zone, pos=pos, nrm=nrm, dist=dist, rnd=rnd)
print('names', [o.name for o in objs], 'total', round(time.time() - t0, 1), 's')
