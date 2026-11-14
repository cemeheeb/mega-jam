"""Navigator console, step 6 (pipeline/kit.md): masks for ArmorPaint from navigator_bake1.py's fields.
Adapted from Singula console_bake2.py.

blender -b <source>/navigator-console.blend --python navigator_bake2.py -- <scratch dir>

Material ids (bits RGB): paint 100 (white), keys 010 (frosted), dark plastic 001 (plates, screen recess),
screen 011 (teal), mat rubber 110 (graphite), orange 101, satin steel 111 (switch bezels), lamp glass 000.
Seams (grooves in the height, measured on the Tripo mesh): only the desk band all round the front block at z = 952 mm.
The vertical panel seams of the cabinet (front x = +-604, sides y = 0 and 276 mm) were removed by the author (14.11).
"""
import bpy, numpy as np, time, sys

SP = sys.argv[sys.argv.index('--') + 1]
OUT = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/navigator-console/source/navigator-console'
RES = 2048
t0 = time.time()
d = np.load(SP + '/navigator_bake.npz')
owner, zone, pos, nrm, dist, rnd = d['owner'], d['zone'], d['pos'].astype(np.float64), d['nrm'], d['dist'], d['rnd']
objs = [bpy.data.objects[n] for n in ('NavigatorConsole', 'NavigatorMonitorRight', 'NavigatorMonitorLeft')]
X, Y, Z = pos[..., 0], pos[..., 1], pos[..., 2]
NX, NY, NZ = nrm[..., 0], nrm[..., 1], nrm[..., 2]
m_in = owner >= 0
WHITE, ALU, GRAPHITE, ORANGE, TEAL, FROSTED, GLASS, SATIN, PLASTIC = 0, 1, 2, 3, 4, 5, 6, 7, 8


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def groove(dist_abs, half, depth, flat=0.0):
    return -depth * (1 - sstep(flat, half, dist_abs))


hg = np.zeros((RES, RES))      # grooves and seams, metres
hp = np.zeros((RES, RES))      # patterns
con = owner == 0
paintlike = (zone == WHITE) | (zone == ORANGE)
SEAM = dict(half=0.0012, depth=0.0006, flat=0.0003)

# no vertical panel seams on the cabinet (front at x = +-604, sides at y = 0 and 276): the author had them removed, 14.11
# desk band: one seam round the front and the ends at z = 952 mm (not on the back face)
band = con & (zone == WHITE) & (np.abs(NZ) < 0.3) & (NY < 0.5) & (Z > 0.893) & (Z < 0.995) & ((Y < -0.40) | (np.abs(X) > 0.745))
g = groove(np.abs(Z - 0.952), **SEAM)
hg[band] = np.minimum(hg[band], g[band])
# mat: fine rubber grain, in the normal map only
mat_ = con & (zone == GRAPHITE)
hp[mat_] += (0.000015 * (np.sin(X * 2900.0 + 1.3) * np.sin(Y * 3100.0 + 0.4) + np.sin((X + Y) * 2300.0) * np.sin((Y - X) * 2700.0 + 2.1)))[mat_]

# ---- material ids
idm = np.zeros((RES, RES, 3), np.float32)
for zn, c in ((WHITE, (1, 0, 0)), (FROSTED, (0, 1, 0)), (PLASTIC, (0, 0, 1)), (TEAL, (0, 1, 1)), (GRAPHITE, (1, 1, 0)),
              (ORANGE, (1, 0, 1)), (SATIN, (1, 1, 1)), (GLASS, (0, 0, 0))):
    idm[m_in & (zone == zn)] = c

# ---- wear, cavity, height
edge = np.maximum(1 - sstep(0.0, 0.003, dist[0]), 0.6 * rnd)
cav = np.maximum(0.9 * (1 - sstep(0.0, 0.005, dist[2])), np.clip(-hg / 0.0006, 0, 1))
H = hg + hp
masks = np.stack([edge, cav, np.clip(0.5 + H / 0.002, 0, 1)], -1).astype(np.float32)

# ---- noise in world space, continuous across uv seams
world = pos.copy()
for i, o in enumerate(objs):
    m = owner == i
    W = np.array(o.matrix_world)
    world[m] = pos[m] @ W[:3, :3].T + W[:3, 3]


def vnoise(p, freq, seed):
    q = p * freq + seed
    i = np.floor(q).astype(np.int64)
    f = q - i
    u = f * f * (3 - 2 * f)

    def h(dx, dy, dz):
        n = (i[..., 0] + dx) * 73856093 ^ (i[..., 1] + dy) * 19349663 ^ (i[..., 2] + dz) * 83492791
        n = (n ^ (n >> 13)) * 1274126177
        return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0
    x0 = h(0, 0, 0) * (1 - u[..., 0]) + h(1, 0, 0) * u[..., 0]
    x1 = h(0, 1, 0) * (1 - u[..., 0]) + h(1, 1, 0) * u[..., 0]
    x2 = h(0, 0, 1) * (1 - u[..., 0]) + h(1, 0, 1) * u[..., 0]
    x3 = h(0, 1, 1) * (1 - u[..., 0]) + h(1, 1, 1) * u[..., 0]
    return (x0 * (1 - u[..., 1]) + x1 * u[..., 1]) * (1 - u[..., 2]) + (x2 * (1 - u[..., 1]) + x3 * u[..., 1]) * u[..., 2]


def fbm(p, freq, seed):
    return (vnoise(p, freq, seed) + 0.5 * vnoise(p, freq * 2.03, seed + 17.3) + 0.25 * vnoise(p, freq * 4.1, seed + 41.7)) / 1.75


noise = np.stack([fbm(world, 22.0, 3.1), fbm(world, 110.0, 9.4), fbm(world, 520.0, 5.7)], -1).astype(np.float32)

# ---- tangent space normal map from the height, gradients inside islands only
adj = (owner == np.roll(owner, -1, 1)) & m_in
step = np.linalg.norm(pos - np.roll(pos, -1, 1), axis=-1)[adj]
tm = float(np.median(step))
print('texel size mm', round(tm * 1000, 4))


def grad(axis):
    f = np.roll(H, -1, axis)
    b = np.roll(H, 1, axis)
    okf = (np.roll(owner, -1, axis) == owner)
    okb = (np.roll(owner, 1, axis) == owner)
    g = np.where(okf & okb, (f - b) / 2, np.where(okf, f - H, np.where(okb, H - b, 0)))
    return np.clip(g / tm, -2.0, 2.0)


gx, gy = grad(1), grad(0)
nm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
nm /= np.linalg.norm(nm, axis=-1, keepdims=True)
nm = (nm * 0.5 + 0.5).astype(np.float32)
nm[~m_in] = (0.5, 0.5, 1.0)


def dilate(img, mask, n):
    img = img.copy()
    mask = mask.copy()
    for _ in range(n):
        for sh in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(mask, sh, (0, 1))
            fill = src & ~mask
            img[fill] = np.roll(img, sh, (0, 1))[fill]
            mask |= fill
    return img


def save(arr, suffix):
    name = 'bake' + suffix
    im = bpy.data.images.get(name) or bpy.data.images.new(name, RES, RES, alpha=False, is_data=True)
    rgba = np.concatenate([arr, np.ones((RES, RES, 1), np.float32)], 2)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = OUT + suffix + '.png'
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


save(dilate(idm, m_in, 6), '_id')
save(dilate(masks, m_in, 12), '_masks')
save(dilate(noise, m_in, 12), '_noise')
save(dilate(nm, m_in, 12), '_relief')
np.save(SP + '/navigator_inside.npy', m_in)
np.save(SP + '/navigator_id.npy', idm)
print('seam texels', int((hg < -1e-5).sum()), 'edge mean', round(float(edge[m_in].mean()), 3), 'cav mean', round(float(cav[m_in].mean()), 3),
      'done', round(time.time() - t0, 1), 's')
