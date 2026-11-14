"""Navigator console, step 10 (pipeline/kit.md): after the ArmorPaint export put the screen pictures and the lamps into
the base colour and the emission, fill the gutters and hook the textures into the Blender material.
Adapted from Singula console_post.py. Run in the live Blender (needs navigator_bake1/2 results in the scratch dir):
    SP = '<scratch dir>'; exec(open('<this file>').read())

Screens: source/screen-left.png (star chart) and screen-right.png (orbits), rectified from the reference picture.
Lamps: the windows on the rocker caps; on switches glow (green, one amber), off ones are dark red glass.
"""
import bpy, bmesh, numpy as np
from mathutils import Vector

SRC = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/navigator-console/source'
E = SRC + '/export/navigator-console'
TEAL = 4
SCREEN_BASE = 0.35
# Where the screen really is in each rectified picture (u, v from its bottom left): the edges found by colour (the
# screen is teal, the bezel white or dark) and fitted by lines, the corners set 3 px inside. Without it a white wedge
# of the reference bezel showed in the bottom right corners (author, 14.11) and a white strip at the top left of the
# right screen.
SCREEN_QUAD = {'left': {'tl': (0.003, 0.9864), 'tr': (0.99, 0.989), 'bl': (0.003, 0.0017), 'br': (0.999, 0.0451)},
               'right': {'tl': (0.0029, 0.9564), 'tr': (0.9808, 0.989), 'bl': (0.003, 0.0017), 'br': (0.997, 0.0404)}}
# The script rewrites the ArmorPaint export in place: before running it again, export again (navigator_ap_run.sh).
d = np.load(SP + '/navigator_bake.npz')
owner, zone, pos = d['owner'], d['zone'], d['pos'].astype(np.float64)
inside = np.load(SP + '/navigator_inside.npy')
idm = np.load(SP + '/navigator_id.npy')
objs = [bpy.data.objects[n] for n in ('NavigatorConsole', 'NavigatorMonitorRight', 'NavigatorMonitorLeft')]
core = inside.copy()
for sh in ((0, 1), (0, -1), (1, 0), (-1, 0)):
    core &= np.roll(inside, sh, (0, 1))


def load(p):
    im = bpy.data.images.load(p, check_existing=False)
    im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save(arr, p):
    h, w = arr.shape[:2]
    im = bpy.data.images.new('post_tmp', w, h, alpha=False, is_data=True)
    im.pixels.foreach_set(np.concatenate([arr[..., :3], np.ones((h, w, 1), np.float32)], 2).ravel())
    im.filepath_raw = p
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def bilinear(img, u, v):
    h, w = img.shape[:2]
    x = np.clip(u * (w - 1), 0, w - 1)
    y = np.clip(v * (h - 1), 0, h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return (img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy


base = load(E + '_base.png')[..., :3].copy()
em = np.zeros_like(base)
lum = base @ np.array([0.2126, 0.7152, 0.0722])

# ---- screens: texel position -> place on the screen face of its monitor -> the rectified picture
for oi, side in ((1, 'right'), (2, 'left')):
    me = objs[oi].data
    za = me.attributes['zone'].data
    pts, n = [], Vector()
    for p in me.polygons:
        if za[p.index].value == TEAL:
            pts += [me.vertices[v].co.copy() for v in p.vertices]
            n += p.normal * p.area
    n.normalize()
    c = sum(pts, Vector()) / len(pts)
    ex = Vector((1, 0, 0))
    ey = n.cross(ex).normalized()
    us = [(q - c).dot(ex) for q in pts]
    vs = [(q - c).dot(ey) for q in pts]
    m = core & (owner == oi) & (zone == TEAL)
    rel = pos[m] - np.array(c)
    u = (rel @ np.array(ex) - min(us)) / (max(us) - min(us))
    v = (rel @ np.array(ey) - min(vs)) / (max(vs) - min(vs))
    pic = load(SRC + '/screen-%s.png' % side)[..., :3]              # rows bottom-up: v = 0 at the bottom
    q = SCREEN_QUAD[side]
    uu, vv = u[:, None], v[:, None]
    p = ((1 - uu) * (1 - vv) * np.array(q['bl']) + uu * (1 - vv) * np.array(q['br'])
         + (1 - uu) * vv * np.array(q['tl']) + uu * vv * np.array(q['tr']))
    col = bilinear(pic, p[:, 0], p[:, 1])
    keep = np.clip(lum[m] / np.median(lum[m]), 0.85, 1.05)[:, None]     # scuffs and grime of the glass stay
    base[m] = col * keep * SCREEN_BASE      # dark glass: the picture comes from the emission, not doubled by the light
    em[m] = col * keep
    print(side, 'screen texels', int(m.sum()), 'u', round(float(u.min()), 3), round(float(u.max()), 3), 'v', round(float(v.min()), 3), round(float(v.max()), 3))

# ---- lamps: windows on the rocker caps (x of their switch, mm) and their state
GREEN = ((0.60, 1.00, 0.62), (0.35, 1.00, 0.45))
AMBER = ((1.00, 0.80, 0.40), (1.00, 0.62, 0.18))
OFF = ((0.26, 0.07, 0.05), (0.0, 0.0, 0.0))
LAMPS = [(60, GREEN), (100, GREEN), (140, OFF), (180, AMBER), (460, GREEN), (500, OFF), (540, GREEN)]
m = core & (owner == 0) & np.all(idm < 0.5, -1)
lx = pos[m][:, 0] * 1000
which = np.argmin(np.abs(lx[:, None] - np.array([x for x, _ in LAMPS])[None, :]), 1)
bm_, em_ = base[m], em[m]
for k, (x, (bc, ec)) in enumerate(LAMPS):
    s = which == k
    shade = np.clip(lum[m][s] / max(np.median(lum[m][s]), 1e-4), 0.85, 1.05)[:, None]
    bm_[s] = np.array(bc) * shade
    em_[s] = np.array(ec) * shade
    print('lamp', x, int(s.sum()))
base[m], em[m] = bm_, em_
save(base, E + '_base.png')
save(em, E + '_emission.png')

# ---- gutters: grow from the island cores, the rest flat
for suffix, flat in (('_base', None), ('_orm', None), ('_nor', (0.5, 0.5, 1.0)), ('_emission', (0.0, 0.0, 0.0))):
    a = load(E + suffix + '.png')[..., :3].copy()
    img, mask = a, core.copy()
    for _ in range(24):
        for sh in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(mask, sh, (0, 1))
            fill = src & ~mask
            img[fill] = np.roll(img, sh, (0, 1))[fill]
            mask |= fill
    img[~mask] = flat if flat is not None else img[core].mean(0)
    save(img, E + suffix + '.png')
    print(suffix, 'filled', int((mask & ~core).sum()), 'flat', int((~mask).sum()))

# ---- the Blender material
mat = bpy.data.materials['NavigatorConsole']
mat.use_nodes = True
nt = mat.node_tree
for n_ in list(nt.nodes):
    if n_.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
        nt.nodes.remove(n_)
bsdf = next(n_ for n_ in nt.nodes if n_.type == 'BSDF_PRINCIPLED')


def tex(suffix, cs, y):
    name = 'NavigatorConsole' + suffix
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    im = bpy.data.images.load(E + suffix + '.png')
    im.name = name
    im.filepath = '//export/navigator-console' + suffix + '.png'
    im.colorspace_settings.name = cs
    n_ = nt.nodes.new('ShaderNodeTexImage')
    n_.image = im
    n_.location = (bsdf.location.x - 700, bsdf.location.y + y)
    return n_


tb, to, tn = tex('_base', 'sRGB', 300), tex('_orm', 'Non-Color', 0), tex('_nor', 'Non-Color', -300)
te = tex('_emission', 'sRGB', -600)
nt.links.new(te.outputs['Color'], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value = 1.0
sep = nt.nodes.new('ShaderNodeSeparateColor')
sep.location = (bsdf.location.x - 400, bsdf.location.y)
nm = nt.nodes.new('ShaderNodeNormalMap')
nm.location = (bsdf.location.x - 400, bsdf.location.y - 300)
nt.links.new(to.outputs['Color'], sep.inputs['Color'])
nt.links.new(tb.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(sep.outputs[1], bsdf.inputs['Roughness'])
nt.links.new(sep.outputs[2], bsdf.inputs['Metallic'])
nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
print('material ready')
