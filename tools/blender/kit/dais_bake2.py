"""Bridge dais, step 6 (pipeline/kit.md): masks for ArmorPaint from dais_bake1.py's fields. Copied from navigator_bake2.py.

blender -b <source>/bridge-dais.blend --python dais_bake2.py -- <scratch dir>

Material ids (bits RGB): paint 100 (white plates), metal 010 (light aluminium wall, trim, panel pockets), dark 001
(graphite plinth, slot walls, niche backs), lens 011 (teal light strip), rubber 110 (anti-slip tiles), orange 101
(edge stripe), satin 111 (steel frames, bars), brushed 000 (mounting plate, light steel screws and bolts).
Seams (grooves in the height), as in the picture: the plate joints every 45 degrees from the frame ring out over the
trim and the rounded edge and down the side (above the panels, above and below the niches), and the round joints at
the trim (r 1170), the frame (r 632) and the mounting plate (r 327). Each seam has a soft shadow on both sides in the
cavity (the rules: panel seams get a soft dark AO line in the base colour).
Patterns (height only): anti-slip pebbles on the rubber (jittered 6 mm cells, raised 0.3 mm with narrow gaps; the
Studio rubber-floor is ribbed, the picture is pebbled), concentric brushing on the mounting plate.
"""
import bpy, numpy as np, time, sys

SP = sys.argv[sys.argv.index('--') + 1]
OUT = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/bridge-dais/source/bridge-dais'
RES = 2048
t0 = time.time()
d = np.load(SP + '/dais_bake.npz')
owner, zone, pos, nrm, dist, rnd = d['owner'], d['zone'], d['pos'].astype(np.float64), d['nrm'], d['dist'], d['rnd']
objs = [bpy.data.objects['BridgeDais']]
X, Y, Z = pos[..., 0], pos[..., 1], pos[..., 2]
NX, NY, NZ = nrm[..., 0], nrm[..., 1], nrm[..., 2]
m_in = owner >= 0
WHITE, ALU, GRAPHITE, ORANGE, TEAL, FROSTED, GLASS, SATIN, PLASTIC = 0, 1, 2, 3, 4, 5, 6, 7, 8
RXY = np.hypot(X, Y)
PHI = np.arctan2(Y, X)
top = m_in & (NZ > 0.7)
side = m_in & (np.abs(NZ) <= 0.7)


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def groove(dist_abs, half, depth, flat=0.0):
    return -depth * (1 - sstep(flat, half, dist_abs))


SEAM = dict(half=0.0018, depth=0.0007, flat=0.0004)
hg = np.zeros((RES, RES))      # grooves and seams, metres
hp = np.zeros((RES, RES))      # patterns
ds = np.full((RES, RES), 1.0)  # distance to the nearest seam line, for its soft shadow

# radial plate joints every 45 degrees: distance to the line through the axis at angle k * 45
k = np.round(PHI / (np.pi / 4))
d_rad = RXY * np.abs(np.sin(PHI - k * np.pi / 4))
even = (k.astype(np.int64) % 2) == 0           # 0, 90, 180, 270: a panel below; 45, 135..: a niche below
on_top = top & (RXY > 0.632 - 0.0005)
on_side = side & (RXY > 1.17) & np.where(even, Z > 0.080, (Z > 0.082) | (Z < 0.028))
rad = (on_top | on_side) & (d_rad < 0.01)
hg[rad] = np.minimum(hg[rad], groove(d_rad, **SEAM)[rad])
ds[rad] = np.minimum(ds[rad], d_rad[rad])
# round joints on the top
for rj in (1.170, 0.632, 0.327):
    dr = np.abs(RXY - rj)
    m = top & (dr < 0.01)
    hg[m] = np.minimum(hg[m], groove(dr, **SEAM)[m])
    ds[m] = np.minimum(ds[m], dr[m])

# anti-slip pebbles on the rubber tiles: jittered cells, F2 - F1 gives the narrow gaps between the pebbles
rub = m_in & (zone == PLASTIC)
CELL = 0.006
px, py = X[rub] / CELL, Y[rub] / CELL
cx, cy = np.floor(px), np.floor(py)
F1 = np.full(px.shape, 9.0)
F2 = np.full(px.shape, 9.0)


def h01(a, b, s):
    return np.modf(np.abs(np.sin(a * 127.1 + b * 311.7 + s * 74.7) * 43758.5453))[0]


for oy in (-1, 0, 1):
    for ox in (-1, 0, 1):
        gx, gy = cx + ox, cy + oy
        fx = gx + 0.15 + 0.7 * h01(gx, gy, 1.0)
        fy = gy + 0.15 + 0.7 * h01(gx, gy, 2.0)
        dd = np.hypot(px - fx, py - fy)
        F2 = np.where(dd < F1, F1, np.minimum(F2, dd))
        F1 = np.minimum(F1, dd)
edge_c = (F2 - F1) * CELL                              # metres to the gap between two pebbles
hp[rub] += 0.0003 * sstep(0.0002, 0.0014, edge_c) * (1 - 0.25 * np.clip(F1, 0, 1) ** 2)
# concentric brushing on the mounting plate: periods of 2.7 mm and more (2.3 texels and up, no aliasing)
pl = m_in & (zone == FROSTED) & (RXY < 0.33)           # the plate, not the screws
r_ = RXY[pl] * 1000
hp[pl] += 0.00003 * (np.sin(r_ * 2 * np.pi / 2.7 + 0.7) + 0.6 * np.sin(r_ * 2 * np.pi / 4.1 + 1.9)
                     + 0.4 * np.sin(r_ * 2 * np.pi / 6.3 + 4.2)) / 2.0

# ---- material ids
idm = np.zeros((RES, RES, 3), np.float32)
for zn, c in ((WHITE, (1, 0, 0)), (ALU, (0, 1, 0)), (GRAPHITE, (0, 0, 1)), (TEAL, (0, 1, 1)), (PLASTIC, (1, 1, 0)),
              (ORANGE, (1, 0, 1)), (SATIN, (1, 1, 1)), (FROSTED, (0, 0, 0))):
    idm[m_in & (zone == zn)] = c

# ---- wear, cavity, height
edge = np.maximum(1 - sstep(0.0, 0.003, dist[0]), 0.6 * rnd)
seam_shadow = 0.3 * (1 - sstep(0.0005, 0.005, ds))
cav = np.maximum(np.maximum(0.9 * (1 - sstep(0.0, 0.005, dist[2])), np.clip(-hg / 0.0006, 0, 1)), seam_shadow)
H = hg + hp
masks = np.stack([edge, cav, np.clip(0.5 + H / 0.002, 0, 1)], -1).astype(np.float32)

# ---- noise in world space: still written so that the asset numbers in ArmorPaint stay as in kit.md; not used
world = pos.copy()


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

# ---- tangent space normal map from the height, gradients inside islands only (one object: island borders by isl)
isl = d['isl']
adj = (isl == np.roll(isl, -1, 1)) & m_in
step = np.linalg.norm(pos - np.roll(pos, -1, 1), axis=-1)[adj]
tm = float(np.median(step))
print('texel size mm', round(tm * 1000, 4))


def grad(axis):
    f = np.roll(H, -1, axis)
    b = np.roll(H, 1, axis)
    okf = (np.roll(isl, -1, axis) == isl) & m_in
    okb = (np.roll(isl, 1, axis) == isl) & m_in
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
np.save(SP + '/dais_inside.npy', m_in)
np.save(SP + '/dais_id.npy', idm)
print('seam texels', int((hg < -1e-5).sum()), 'pebble texels', int(rub.sum()), 'edge mean', round(float(edge[m_in].mean()), 3),
      'cav mean', round(float(cav[m_in].mean()), 3), 'done', round(time.time() - t0, 1), 's')
