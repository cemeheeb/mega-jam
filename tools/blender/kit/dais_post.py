"""Bridge dais, step 10 (pipeline/kit.md): after the ArmorPaint export put the light of the teal strips into the base
colour and the emission, fill the gutters and hook the textures into the Blender material. Copied from navigator_post.py.
Run in the live Blender (needs dais_bake1/2 results in the scratch dir):
    SP = '<scratch dir>'; exec(open('<this file>').read())
The script rewrites the ArmorPaint export in place: before running it again, export again (dais_ap_run.sh).

Light strips (id 011, lens): ArmorPaint exports the emission black, so it is written here: a muted teal light, the glass
itself darker in the base colour (the light comes from the emission, not doubled by the lamps). In Blender the
emission strength is EMIT_STRENGTH; in Unreal the material instance takes the same texture (EmissiveStrength).
"""
import bpy, numpy as np

SRC = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/bridge-dais/source'
E = SRC + '/export/bridge-dais'
LIGHT = np.array((0.42, 0.93, 0.96))      # file values (sRGB): muted teal, a little whiter than the glass
GLASS_BASE = 0.45
EMIT_STRENGTH = 2.5
inside = np.load(SP + '/dais_inside.npy')
idm = np.load(SP + '/dais_id.npy')
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


base = load(E + '_base.png')[..., :3].copy()
orm = load(E + '_orm.png')[..., :3]
em = np.zeros_like(base)
bits = idm >= 0.5
names = {(1, 0, 0): 'paint', (0, 1, 0): 'metal', (0, 0, 1): 'dark', (0, 1, 1): 'lens', (1, 1, 0): 'rubber',
         (1, 0, 1): 'orange', (1, 1, 1): 'satin', (0, 0, 0): 'brushed'}
for code, name in names.items():
    m = core & np.all(bits == np.array(code, bool), -1)
    if m.any():
        print(name, int(m.sum()), 'base', np.round(np.median(base[m], 0), 3), 'rough', round(float(np.median(orm[m][:, 1])), 3),
              'metal', round(float(np.median(orm[m][:, 2])), 2))
# ---- light strips
lens = core & np.all(bits == np.array((0, 1, 1), bool), -1)
lum = base @ np.array([0.2126, 0.7152, 0.0722])
keep = np.clip(lum[lens] / np.median(lum[lens]), 0.85, 1.05)[:, None]      # grime of the glass stays
em[lens] = LIGHT * keep
base[lens] = LIGHT * keep * GLASS_BASE
print('lens texels', int(lens.sum()))
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
mat = bpy.data.materials['BridgeDais']
mat.use_nodes = True
nt = mat.node_tree
for n_ in list(nt.nodes):
    if n_.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
        nt.nodes.remove(n_)
bsdf = next(n_ for n_ in nt.nodes if n_.type == 'BSDF_PRINCIPLED')


def tex(suffix, cs, y):
    name = 'BridgeDais' + suffix
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    im = bpy.data.images.load(E + suffix + '.png')
    im.name = name
    im.filepath = '//export/bridge-dais' + suffix + '.png'
    im.colorspace_settings.name = cs
    n_ = nt.nodes.new('ShaderNodeTexImage')
    n_.image = im
    n_.location = (bsdf.location.x - 700, bsdf.location.y + y)
    return n_


tb, to, tn = tex('_base', 'sRGB', 300), tex('_orm', 'Non-Color', 0), tex('_nor', 'Non-Color', -300)
te = tex('_emission', 'sRGB', -600)
nt.links.new(te.outputs['Color'], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value = EMIT_STRENGTH
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
