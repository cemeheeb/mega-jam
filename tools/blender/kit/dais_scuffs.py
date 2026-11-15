"""Bridge dais, step 6b (after dais_bake2.py): the scuffs map for ArmorPaint from the wear textures of Singula
(SourceArt/environment/common). Copied from navigator_scuffs.py.

    blender -b --factory-startup --python dais_scuffs.py -- <scratch dir>

Writes source/bridge-dais_scuffs.png, 2048, data:
- R  where the dais gets worn, only the author's zone (15.11: the passage from the south): the orange edge and the trim
     where the feet step up (-X, |y| < 0.26 m, fading to 0.42 m), the white plates along the way to the couch (more
     towards the edge), the outer frame ring there, kicks low on the south side wall (below 90 mm); the rubber ring
     round the couch everywhere a little (0.4) and fully on the south half where one stands to get in. Nothing on the
     mounting plate (under the couch). The zone keeps inside the south islands (135-225 degrees on the top, 140.6-230.6
     on the side): the masters of the shared islands lie east and stay clean;
- G  fine scratches (common/fine-scratches), laid twice in metres, the second turned a quarter, the brighter of the two;
- B  weathering (common/weathering): rubbed streaks (dim) and chips (bright blobs), laid once.
The top is laid by x and y, the side by the arc round the axis (from the south, so no break in the zone) and z.
"""
import sys
import time

import bpy
import numpy as np

SP = sys.argv[sys.argv.index('--') + 1]
ROOT = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment'
OUT = ROOT + '/bridge/bridge-dais/source/bridge-dais_scuffs.png'
SCRATCHES = ROOT + '/common/fine-scratches/fine-scratches.png'    # the swatch is about 1 m
WEATHERING = ROOT + '/common/weathering/weathering.png'            # the swatch is about 1 m
SCRATCH_TILES = (0.6, 0.75)     # metres a tile: scratches 2-10 cm
WEATHER_TILE = 1.0              # streaks about 20 cm, chips 5-20 mm; big features: repeated, not in turned cells
RES = 2048
t0 = time.time()

d = np.load(SP + '/dais_bake.npz')
owner, pos, nrm = d['owner'], d['pos'].astype(np.float64), d['nrm'].astype(np.float64)
inside = owner >= 0
step_len = np.linalg.norm(pos - np.roll(pos, -1, 1), axis=-1)
adj = (d['isl'] == np.roll(d['isl'], -1, 1)) & inside
ppm = 1.0 / float(np.median(step_len[adj]))
print('texels a metre', round(ppm))


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[..., 0].astype(np.float64)


def overlay(grey, tile, ppm):
    """The grey map reduced by boxes of 2^n while its pixel stays at least twice finer than the texel."""
    factor = 1
    while grey.shape[0] / (tile * factor * 2) >= 2 * ppm and grey.shape[0] % (factor * 2) == 0:
        factor *= 2
    h, w = grey.shape
    return grey.reshape(h // factor, factor, w // factor, factor).mean((1, 3))


def wrapped(img, x, y):
    """Bilinear, the map repeated both ways; x, y in tiles."""
    h, w = img.shape
    x, y = x * w - 0.5, y * h - 0.5
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - xi, y - yi
    xa, xb, ya, yb = xi % w, (xi + 1) % w, yi % h, (yi + 1) % h
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy) + img[yb, xa] * (1 - fx) * fy
            + img[yb, xb] * fx * fy)


def cell_random(cu, cv, seed):
    return np.modf(np.abs(np.sin(cu * 127.1 + cv * 311.7 + seed * 74.7) * 43758.5453))[0]


def bombed(img, u, v, seed):
    """The map in cells of one tile, each with its own random shift and quarter turn; two grids half a cell apart,
    blended by a tent from the middle of their cells, hide the borders. u, v in tiles."""
    total, weight = np.zeros_like(u), np.zeros_like(u)
    for half in (0.0, 0.5):
        cu, fu = np.divmod(u + half, 1.0)
        cv, fv = np.divmod(v + half, 1.0)
        turn = np.floor(cell_random(cu, cv, seed + half) * 4)
        x = np.select([turn == 0, turn == 1, turn == 2], [fu, fv, 1 - fu], 1 - fv)
        y = np.select([turn == 0, turn == 1, turn == 2], [fv, 1 - fu, 1 - fv], fu)
        w = (1 - np.abs(2 * fu - 1)) * (1 - np.abs(2 * fv - 1)) + 1e-4
        total += w * wrapped(img, x + cell_random(cu, cv, seed + 1.3 + half), y + cell_random(cu, cv, seed + 2.9 + half))
        weight += w
    return total / weight


def laid(img, u, v, tile, seed, ppm):
    """The map over the whole texel: the mean of 3 x 3 points a third of a texel apart."""
    step = 1 / (3 * ppm)
    total = np.zeros_like(u)
    for du in (-step, 0.0, step):
        for dv in (-step, 0.0, step):
            total += bombed(img, (u + du) / tile, (v + dv) / tile, seed)
    return total / 9


def tiled(img, u, v, tile, ppm):
    """The map simply repeated (it is seamless), over the whole texel like laid()."""
    step = 1 / (3 * ppm)
    total = np.zeros_like(u)
    for du in (-step, 0.0, step):
        for dv in (-step, 0.0, step):
            total += wrapped(img, (u + du) / tile, (v + dv) / tile)
    return total / 9


def spread(values, low, high):
    a, b = np.percentile(values, (low, high))
    return np.clip((values - a) / max(b - a, 1e-6), 0, 1)


# ---- in-plane coordinates: the top by x and y, the side by the arc from the south and z
where, facing = pos[inside], nrm[inside]
flat = np.abs(facing[:, 2]) >= 0.7
arc = 1.2 * np.arctan2(-where[:, 1], -where[:, 0])
along = np.where(flat, where[:, 0], arc)
across = np.where(flat, where[:, 1], where[:, 2])
plane = np.where(flat, 0.0, 0.37)

scr, wea = load(SCRATCHES), load(WEATHERING)
ta, tb = SCRATCH_TILES
first = spread(laid(overlay(scr, ta, ppm), along, -across, ta, 3.7, ppm), 60, 99.5)
second = spread(laid(overlay(scr, tb, ppm), across + 0.37, along + 0.61, tb, 8.2, ppm), 60, 99.5)
scratches = np.maximum(first, 0.85 * second)
weathering = tiled(overlay(wea, WEATHER_TILE, ppm), along + plane, -across + 1.3 * plane, WEATHER_TILE, ppm)
print('scratches and weathering', round(time.time() - t0, 1), 's')
print('weathering', round(time.time() - t0, 1), 's, percentiles 50/90/99/99.9',
      [round(float(x), 3) for x in np.percentile(weathering, (50, 90, 99, 99.9))])

# ---- where the dais gets worn (object space, metres; south is -X)
X, Y, Z = pos[..., 0], pos[..., 1], pos[..., 2]
zone = d['zone']
RXY = np.hypot(X, Y)
south_angle = np.degrees(np.abs(np.arctan2(-Y, -X)))          # 0 at due south
southward = (X < 0) & (1 - sstep(30.0, 42.0, south_angle) > 0)
path = (1 - sstep(0.26, 0.42, np.abs(Y))) * (1 - sstep(30.0, 42.0, south_angle)) * southward
is_top = nrm[..., 2] >= 0.7
edge_ring = (RXY > 1.165) & (Z > 0.1)                          # trim and rounded orange edge: the feet step up here
plates = is_top & (zone == 0)
frame = is_top & (zone == 7) & (RXY > 0.615) & (RXY < 0.635)
wall = (~is_top) & (RXY > 1.15) & (Z < 0.1)
touch = np.zeros((RES, RES))
touch = np.where(edge_ring, path, touch)
touch = np.where(plates, path * (0.45 + 0.35 * sstep(0.75, 1.15, -X)), touch)
touch = np.where(frame, 0.6 * path, touch)
touch = np.where(wall, 0.8 * (1 - sstep(0.22, 0.40, np.abs(Y))) * (X < 0) * (1 - sstep(0.03, 0.09, Z)), touch)
rubber = (zone == 8)
touch = np.where(rubber, 0.4 + 0.6 * (1 - sstep(0.2, 0.45, np.abs(Y))) * (X < 0), touch)
touch[~inside] = 0

out = np.zeros((RES, RES, 3))
out[..., 0] = np.clip(touch, 0, 1)
out[inside, 1] = scratches
out[inside, 2] = weathering
out[~inside] = 0
mask = inside.copy()
for _ in range(12):
    for sh in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        grow = np.roll(mask, sh, (0, 1)) & ~mask
        out[grow] = np.roll(out, sh, (0, 1))[grow]
        mask |= grow
im = bpy.data.images.new('scuffs', RES, RES, alpha=False, is_data=True)
im.pixels.foreach_set(np.concatenate([out, np.ones((RES, RES, 1))], 2).astype(np.float32).ravel())
im.filepath_raw = OUT
im.file_format = 'PNG'
im.save()
print('touch mean', round(float(touch[inside].mean()), 3), 'east masters max', round(float(touch[inside & (X > 0.05) & (zone != 8)].max()), 3), '> 0.5:', int((touch[inside] > 0.5).sum()),
      'scratch > 0.3:', round(float((scratches > 0.3).mean()), 4), 'done', round(time.time() - t0, 1), 's')
