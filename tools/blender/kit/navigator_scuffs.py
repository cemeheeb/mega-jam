"""Navigator console, step 6b (after navigator_bake2.py): the scuffs map for ArmorPaint, from the wear textures of
Singula (copied to SourceArt/environment/common), as in its wall-columns and sliding-door bakes.

    blender -b --factory-startup --python navigator_scuffs.py -- <scratch dir>

Writes source/navigator-console_scuffs.png, 2048, data:
- R  where the console gets worn, only the zones the author marked: the switch panel (the slope with the plates and
     the white margin round them, down to the mat) and the desk front (the strip before the mat, the rounded lip, the
     top of the front face; more in the middle); 0 everywhere else. On the mat R is its polish instead: an oval on the
     front half (centre x 30, y -385 mm: at the front edge of the mat, half axes 400 x 180 mm), 1 in the middle,
     smoothly 0 at the rim;
- G  fine scratches (common/fine-scratches, hairlines in all directions, some in parallel groups): laid twice in metres,
     the second laying turned a quarter and at another tile, the brighter of the two;
- B  weathering (common/weathering): rubbed streaks (dim) and paint chips (bright blobs), laid once.
Each texture is laid on every face by its main axis (a front by x and z, a side by y and z, a top by x and y) and read
over the whole texel (3 x 3 points). The scratches go in cells of a tile with a random shift and quarter turn each, so
that they do not repeat in a grid; the weathering has features as big as a cell (turned cells show as squares), so it
is simply repeated (the map is seamless), shifted per plane. Positions are in the space of each object (the console
stands at the origin).
"""
import sys
import time

import bpy
import numpy as np

SP = sys.argv[sys.argv.index('--') + 1]
ROOT = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment'
OUT = ROOT + '/bridge/navigator-console/source/navigator-console_scuffs.png'
SCRATCHES = ROOT + '/common/fine-scratches/fine-scratches.png'    # the swatch is about 1 m
WEATHERING = ROOT + '/common/weathering/weathering.png'            # the swatch is about 1 m
SCRATCH_TILES = (0.6, 0.75)     # metres a tile: scratches 2-10 cm
WEATHER_TILE = 1.0              # streaks about 20 cm, chips 5-20 mm; big features: repeated, not in turned cells
RES = 2048
t0 = time.time()

PANEL_SCALE = 0.4               # on the panel (plates, keys, switches) both maps 2.5 times finer (author, 14.11);
                                # its islands have 2.5 times the texel density (PANEL_UV in navigator_build.py)

d = np.load(SP + '/navigator_bake.npz')
owner, pos, nrm = d['owner'], d['pos'].astype(np.float64), d['nrm'].astype(np.float64)
inside = owner >= 0
# the panel: dark plastic plates, keys and rocker caps, satin bezels, lamp glass on the slope of the console
panel_t = inside & (owner == 0) & np.isin(d['zone'], (5, 6, 7, 8)) & (pos[..., 1] > 0.085) & (pos[..., 2] > 0.995)
step_len = np.linalg.norm(pos - np.roll(pos, -1, 1), axis=-1)
adj = (owner == np.roll(owner, -1, 1)) & inside
ppm = 1.0 / float(np.median(step_len[adj & ~panel_t]))
ppm_panel = 1.0 / float(np.median(step_len[adj & panel_t & np.roll(panel_t, -1, 1)]))
print('texels a metre', round(ppm), 'on the panel', round(ppm_panel))


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


# ---- in-plane coordinates by the main axis of the face, separate per object
where, facing = pos[inside], np.abs(nrm[inside])
own = owner[inside].astype(np.float64)
front = (facing[:, 1] >= facing[:, 0]) & (facing[:, 1] >= facing[:, 2])
side = ~front & (facing[:, 0] >= facing[:, 2])
along = np.where(front, where[:, 0], where[:, 1]) + 3.1 * own
across = np.where(front | side, where[:, 2], where[:, 0]) + 1.7 * own

scr, wea = load(SCRATCHES), load(WEATHERING)
plane = np.where(front, 0.0, np.where(side, 0.37, 0.71))
scratches, weathering = np.zeros(len(along)), np.zeros(len(along))
for sel, scale, p in ((~panel_t[inside], 1.0, ppm), (panel_t[inside], PANEL_SCALE, ppm_panel)):
    a_, c_, pl = along[sel], across[sel], plane[sel]
    ta, tb = (t * scale for t in SCRATCH_TILES)
    first = spread(laid(overlay(scr, ta, p), a_, -c_, ta, 3.7, p), 60, 99.5)
    second = spread(laid(overlay(scr, tb, p), c_ + 0.37, a_ + 0.61, tb, 8.2, p), 60, 99.5)
    scratches[sel] = np.maximum(first, 0.85 * second)
    tw = WEATHER_TILE * scale
    weathering[sel] = tiled(overlay(wea, tw, p), a_ + pl, -c_ + 1.3 * pl, tw, p)
print('scratches and weathering', round(time.time() - t0, 1), 's')
print('weathering', round(time.time() - t0, 1), 's, percentiles 50/90/99/99.9',
      [round(float(x), 3) for x in np.percentile(weathering, (50, 90, 99, 99.9))])

# ---- where the console gets worn: only the two zones the author marked (console space, metres), nothing elsewhere
X, Y, Z = pos[..., 0], pos[..., 1], pos[..., 2]
con = (owner == 0) & (d['zone'] != 2)          # not the mat (graphite)
# the switch panel: the slope with the key and switch plates and the white margin round them, down to the mat edge;
# s along the slope from the start of its straight part (y 133, z 1003 mm), the plates lie at s 20-96 mm
s = (Y - 0.133) * 0.8 + (Z - 1.003) * 0.6
panel = sstep(-0.040, -0.028, s) * (1 - sstep(0.112, 0.126, s)) * (1 - sstep(0.615, 0.65, np.abs(X)))
panel = np.where((Y > 0.085) & (Y < 0.25) & (Z > 0.995), panel, 0.0)
# the desk front: the white strip before the mat, the rounded lip and the top of the front face, more in the middle
lip = (1 - sstep(0.68, 0.74, np.abs(X))) * sstep(0.952, 0.968, Z) * (0.75 + 0.25 * (1 - sstep(0.2, 0.6, np.abs(X))))
lip = np.where(Y < -0.385, lip, 0.0)
touch = np.where(con, np.maximum(panel, lip), 0.0)
# the mat: polished by the forearms in an oval on its front half (the author's zone), glossy in the middle and matte
# towards the rim, smooth all the way; on the mat R means only this
mat = (owner == 0) & (d['zone'] == 2)
r = np.sqrt(((X - 0.03) / 0.40) ** 2 + ((Y + 0.385) / 0.18) ** 2)     # centred on the front edge (author, 14.11)
touch = np.where(mat, 1 - sstep(0.0, 1.0, r), touch)

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
print('touch mean', round(float(touch[inside].mean()), 3), '> 0.5:', int((touch[inside] > 0.5).sum()),
      'scratch > 0.3:', round(float((scratches > 0.3).mean()), 4), 'done', round(time.time() - t0, 1), 's')
