"""Skin of the dead man's arms matched to the head (SourceArt/characters/dead-man/source/dead-man.blend).

The author's request (15.11): even out the skin colour, the head is the reference. Tripo gave the body darker brown
forearms and hands than the pale face. This script recolours only the body texture, in Lab: the arm skin gets the mean
and the spread of the head's skin. The Tripo jpg stays as it is; the result is a new PNG next to the asset card,
and the material DeadMan_Body is pointed to it.

Where the skin is: body faces of the forearms and hands, from the sleeve's cuff on. The cuff ends at about 0.18 of the
forearm + hand length from the elbow (measured on the texture: the coverall is sat ~0.62, val ~0.48; the skin
sat ~0.44, val ~0.35), so the weight rises over T0..T1 along the arm and is also faded out on saturated texels,
in case a bit of the orange cuff got in. The weight is grown a few texels past the UV islands, so mip maps do not
bring back a dark seam.

Run in that blend with the rig in rest pose (it reads the mesh at rest).
"""
import bpy
import numpy as np

S = 2048
T0, T1 = 0.13, 0.22                 # along the forearm + hand from the elbow: the cuff ends, the skin begins
SAT_KEEP = (0.52, 0.60)             # texels this saturated are coverall, they fade out of the mask
HEAD_SKIN = dict(hue=(0.03, 0.13), sat=(0.28, 0.55))   # the head texture's skin (hair and beard are grey)
GROW = 6                            # texels past the islands
OUT = '//../T_DeadMan_Body_BaseColor.png'

ob = bpy.data.objects['DeadMan']
rig = bpy.data.objects['rig']
me = ob.data


def pixels(name):
    im = bpy.data.images[name]
    a = np.empty(S * S * 4, np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(S, S, 4)


def raster(polys, vw=None):
    """Weight per texel of the faces' UVs: vw per vertex, interpolated (or 1), the max where islands overlap."""
    out = np.zeros((S, S), np.float32)
    uv = np.zeros((len(me.loops), 2))
    me.uv_layers.active.data.foreach_get('uv', uv.ravel())
    for p in polys:
        L = list(p.loop_indices)
        V = list(p.vertices)
        for k in range(1, len(L) - 1):
            t = uv[[L[0], L[k], L[k + 1]]] * S
            w = np.ones(3) if vw is None else vw[[V[0], V[k], V[k + 1]]]
            if w.max() <= 0:
                continue
            x0, y0 = np.maximum(np.floor(t.min(0)).astype(int), 0)
            x1, y1 = np.minimum(np.ceil(t.max(0)).astype(int), S - 1)
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = t
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-12:
                continue
            l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
            l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
            l3 = 1 - l1 - l2
            inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
            val = np.clip(l1 * w[0] + l2 * w[1] + l3 * w[2], 0, 1) * inside
            sub = out[y0:y1 + 1, x0:x1 + 1]
            np.maximum(sub, val, out=sub)
    return out


def srgb_to_lab(c):
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_to_srgb(lab):
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], -1)
    xyz = np.where(f > 0.206893, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    M = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    c = np.clip(xyz @ M.T, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def hsv(c):
    mx = c.max(-1)
    mn = c.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    return h, s, mx


def arm_weights():
    """Per vertex: 0 on the sleeve, 1 on the skin, along each forearm + hand from the elbow."""
    co = np.array([v.co for v in me.vertices]) @ np.array(ob.matrix_world)[:3, :3].T + np.array(ob.matrix_world.translation)
    w = np.zeros(len(co))
    for side, sign in (('L', 1), ('R', -1)):
        e = np.array(rig.matrix_world @ rig.data.bones['DEF-forearm.' + side].head_local)
        tip = np.array(rig.matrix_world @ rig.data.bones['DEF-hand.' + side].tail_local)
        ax = tip - e
        L = np.linalg.norm(ax)
        ax /= L
        r = co - e
        t = r @ ax / L
        radial = np.linalg.norm(r - np.outer(r @ ax, ax), axis=1)
        near = (radial < 0.12) & (t < 1.3) & (np.sign(co[:, 0]) == sign)
        u = np.clip((t - T0) / (T1 - T0), 0, 1)
        w = np.maximum(w, np.where(near, u * u * (3 - 2 * u), 0))
    return w


def grow(w, cover, n):
    """Spread the weight n texels into texels no face covers (the gutters between islands)."""
    w = w.copy()
    for _ in range(n):
        m = w.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            np.maximum(m, np.roll(np.roll(w, dy, 0), dx, 1), out=m)
        w = np.where(cover, w, m)
    return w


def run():
    mats = [m.name for m in me.materials]
    bi, hi = mats.index('DeadMan_Body'), mats.index('DeadMan_Head')
    body = [p for p in me.polygons if p.material_index == bi]
    head = [p for p in me.polygons if p.material_index == hi]

    B = pixels('dead_man_body_basecolor')
    H = pixels('dead_man_head_basecolor')[..., :3]
    vw = arm_weights()
    arm = [p for p in body if vw[list(p.vertices)].max() > 0]
    W = raster(arm, vw)
    _, sat, _ = hsv(B[..., :3])
    W *= np.clip((SAT_KEEP[1] - sat) / (SAT_KEEP[1] - SAT_KEEP[0]), 0, 1)
    cover = raster(body) > 0
    W = grow(W, cover, GROW)

    hm = raster(head) > 0
    hh, hs, _ = hsv(H)
    skin_h = hm & (hh > HEAD_SKIN['hue'][0]) & (hh < HEAD_SKIN['hue'][1]) & (hs > HEAD_SKIN['sat'][0]) & (hs < HEAD_SKIN['sat'][1])
    skin_b = W > 0.9
    lab_h = srgb_to_lab(H[skin_h])
    lab_b = srgb_to_lab(B[..., :3][skin_b])
    mh, sh = lab_h.mean(0), lab_h.std(0)
    mb, sb = lab_b.mean(0), lab_b.std(0)
    k = np.clip(sh / np.maximum(sb, 1e-3), 0.7, 1.4)       # keep the body's own detail, within reason

    sel = W > 0
    lab = srgb_to_lab(B[..., :3][sel])
    rgb = lab_to_srgb((lab - mb) * k + mh)
    out = B.copy()
    w = W[sel][:, None]
    out[..., :3][sel] = B[..., :3][sel] * (1 - w) + rgb * w

    name = 'T_DeadMan_Body_BaseColor'
    im = bpy.data.images.get(name) or bpy.data.images.new(name, S, S, alpha=False)
    im.scale(S, S)
    im.pixels.foreach_set(out.ravel())
    im.filepath_raw = OUT
    im.file_format = 'PNG'
    im.save()
    im.colorspace_settings.name = 'sRGB'

    mat = bpy.data.materials['DeadMan_Body']
    tex = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
    tex.image = im
    return dict(head_lab=mh.round(1).tolist(), head_std=sh.round(1).tolist(), arm_lab=mb.round(1).tolist(),
                arm_std=sb.round(1).tolist(), k=k.round(2).tolist(), texels=int(sel.sum()), skin_texels=int(skin_b.sum()))


if __name__ == '__main__':
    print(run())
