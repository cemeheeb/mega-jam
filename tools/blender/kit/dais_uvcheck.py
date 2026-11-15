"""Bridge dais, step 4 (pipeline/kit.md): check the packed atlas. Run in the live Blender:
    SP = '<scratch dir>'; exec(open(<this file>).read())
Stretch from the singular values of every triangle's uv -> 3D Jacobian, coverage, overlap of different islands
(shared copies are skipped: they lie on their master by design), the smallest gap, and uv.png (2048, zone colours,
dark seams) in the scratch dir.
"""
import bpy, bmesh, numpy as np
from mathutils.geometry import tessellate_polygon
from mathutils import Vector

RES = 2048
COL = {0: (236, 234, 228), 1: (185, 188, 192), 2: (46, 50, 54), 3: (242, 106, 33), 4: (95, 198, 201),
       5: (215, 218, 222), 7: (120, 124, 130), 8: (70, 74, 80)}
me = bpy.data.objects['BridgeDais'].data
bm = bmesh.new()
bm.from_mesh(me)
uvl = bm.loops.layers.uv['UVMap']
zl, il, shl = (bm.faces.layers.int[n] for n in ('zone', 'island', 'shared'))
img = np.zeros((RES, RES, 3), np.uint8)
img[:] = (70, 20, 90)
key = np.full((RES, RES), -1, np.int32)
overlap = 0
sig, areas = [], []
for f in bm.faces:
    if f[shl]:
        continue
    ls = list(f.loops)
    for ta, tb, tc in tessellate_polygon([[Vector((l[uvl].uv.x, l[uvl].uv.y, 0)) for l in ls]]):
        tri = (ls[ta], ls[tb], ls[tc])
        U = np.array([l[uvl].uv for l in tri], np.float64)
        X = np.array([l.vert.co for l in tri], np.float64)
        du = np.array([U[1] - U[0], U[2] - U[0]]).T
        dx = np.array([X[1] - X[0], X[2] - X[0]]).T
        if abs(np.linalg.det(du)) < 1e-14:
            continue
        J = dx @ np.linalg.inv(du)
        s = np.linalg.svd(J, compute_uv=False)
        sig.append(s)
        areas.append(0.5 * np.linalg.norm(np.cross(X[1] - X[0], X[2] - X[0])))
        px = U * RES
        d = (px[1][1] - px[2][1]) * (px[0][0] - px[2][0]) + (px[2][0] - px[1][0]) * (px[0][1] - px[2][1])
        if abs(d) < 1e-9:
            continue
        x0, y0 = np.maximum(np.floor(px.min(0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(px.max(0)).astype(int), RES - 1)
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((px[1][1] - px[2][1]) * (xs - px[2][0]) + (px[2][0] - px[1][0]) * (ys - px[2][1])) / d
        w1 = ((px[2][1] - px[0][1]) * (xs - px[2][0]) + (px[0][0] - px[2][0]) * (ys - px[2][1])) / d
        w2 = 1 - w0 - w1
        inside = (w0 > 0.02) & (w1 > 0.02) & (w2 > 0.02)
        sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        overlap += int((inside & (key[sl] >= 0) & (key[sl] != f[il])).sum())
        key[sl][inside] = f[il]
        img[sl][inside] = COL.get(f[zl], (255, 0, 255))
sig = np.array(sig)
areas = np.array(areas)
scale = float(np.median(sig[:, 0]))
st = np.maximum(np.abs(sig[:, 0] / scale - 1), np.abs(sig[:, 1] / scale - 1))
print('m per uv', round(scale, 4), 'px/m 1024', round(1024 / scale), '2048', round(2048 / scale))
for lim in (0.001, 0.01, 0.05, 0.15):
    print('stretch >', lim, round(float(areas[st > lim].sum() / areas.sum()), 4))
print('worst stretch', round(float(st.max()), 4), 'coverage', round(float((key >= 0).mean()), 3), 'overlap texels', overlap)
gap = None
occ = key >= 0
for r in range(1, 40):
    for sh in ((0, r), (r, 0), (r, r), (r, -r)):
        a = np.roll(key, sh, (0, 1))
        if ((a >= 0) & occ & (a != key)).any():
            gap = r
            break
    if gap:
        break
print('smallest gap px', gap, 'islands', len(set(key[occ].ravel().tolist())))
# seams dark
for e in bm.edges:
    if e.seam:
        for l in e.link_loops:
            if l.face[shl]:
                continue
            a, c = l[uvl].uv, l.link_loop_next[uvl].uv
            n = int(max(abs(a.x - c.x), abs(a.y - c.y)) * RES) + 2
            for t in np.linspace(0, 1, n):
                x, y = int((a.x + (c.x - a.x) * t) * RES), int((a.y + (c.y - a.y) * t) * RES)
                if 0 <= x < RES and 0 <= y < RES:
                    img[y, x] = (20, 20, 20)
bm.free()
im = bpy.data.images.new('uvcheck', RES, RES, alpha=False)
im.pixels.foreach_set(np.concatenate([img / 255.0, np.ones((RES, RES, 1))], 2).astype(np.float32).ravel())
im.filepath_raw = SP + '/uv.png'
im.file_format = 'PNG'
im.save()
bpy.data.images.remove(im)
print('uv.png written')
