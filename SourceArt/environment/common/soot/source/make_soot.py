"""Soot decal masks for burned rooms (DESIGN.md §14, «выгоревшие комнаты»).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python SourceArt/environment/common/soot/source/make_soot.py

Writes T_Soot_A/B/C/D.png (1024, grey mask in RGB, 1 = full soot) into the asset folder. A, B and C have no up or
down, so a decal may be turned and mirrored freely: A — a smudge with a ragged edge, B — vertical streaks,
C — torn patches with specks. They fade to 0 well before the border: the decal box edge never shows.
D is the smoke stain under the ceiling and has a top (the top of the image): solid along the top edge and across
the whole width, so neighbouring wall columns join into one band; below it a ragged edge and drips running down,
fading to 0 before the bottom. Fixed seeds: the same files every run.
"""
import os

import bpy
import numpy as np

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = 1024
y, x = np.mgrid[0:RES, 0:RES].astype(np.float64)
u, v = x / RES * 2 - 1, y / RES * 2 - 1          # -1..1


def vnoise(px, py, freq, seed):
    qx, qy = px * freq + seed * 17.13, py * freq + seed * 5.71
    ix, iy = np.floor(qx).astype(np.int64), np.floor(qy).astype(np.int64)
    fx, fy = qx - ix, qy - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)

    def h(dx, dy):
        n = (ix + dx) * 73856093 ^ (iy + dy) * 19349663 ^ int(seed * 1000) * 83492791
        n = (n ^ (n >> 13)) * 1274126177
        return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0
    a = h(0, 0) * (1 - sx) + h(1, 0) * sx
    b = h(0, 1) * (1 - sx) + h(1, 1) * sx
    return a * (1 - sy) + b * sy


def fbm(px, py, freq, seed, octaves=5):
    s, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        s = s + amp * vnoise(px, py, freq * 2.03 ** o, seed + o * 3.3)
        tot += amp
        amp *= 0.5
    return s / tot


def sstep(a, b, t):
    t = np.clip((t - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def border():
    return sstep(1.0, 0.82, np.abs(u)) * sstep(1.0, 0.82, np.abs(v))


def smudge():
    warp = fbm(u, v, 2.2, 1) - 0.5
    r = np.sqrt(u ** 2 + v ** 2) + warp * 0.55
    core = 1 - sstep(0.15, 0.78, r)
    grain = fbm(u, v, 9.0, 2)
    m = core * (0.55 + 0.6 * grain)
    m = m * sstep(0.18, 0.45, fbm(u, v, 4.0, 3) + core * 0.5)
    return np.clip(m, 0, 1) * border()


def streaks():
    # tall, narrow strands: fast along x, slow along y; an ellipse taller than wide, same at top and bottom
    strands = fbm(u * 1.0, v * 0.12, 7.0, 4)
    body = 1 - sstep(0.25, 0.95, np.sqrt((u / 0.75) ** 2 + (v / 1.0) ** 2) + (fbm(u, v, 2.0, 5) - 0.5) * 0.5)
    m = body * sstep(0.35, 0.75, strands) * (0.6 + 0.5 * fbm(u, v, 12.0, 6))
    return np.clip(m * 1.25, 0, 1) * border()


def patches():
    blobs = sstep(0.48, 0.62, fbm(u, v, 3.2, 7))
    falloff = 1 - sstep(0.35, 0.95, np.sqrt(u ** 2 + v ** 2) + (fbm(u, v, 1.7, 8) - 0.5) * 0.6)
    specks = sstep(0.88, 0.93, vnoise(u, v, 90.0, 9)) * sstep(0.45, 0.8, falloff) * sstep(0.4, 0.6, fbm(u, v, 3.0, 11))
    m = (blobs * (0.5 + 0.6 * fbm(u, v, 10.0, 10)) + specks * 0.7) * falloff
    return np.clip(m, 0, 1) * border()


def smoke():
    # Blender rows go bottom-up: v = +1 is the top of the saved image
    d = (1 - v) / 2                                   # 0 at the top, 1 at the bottom
    edge = 0.28 + 0.30 * fbm(u, v * 0.15, 2.6, 12)    # where the solid band breaks up
    band = 1 - sstep(edge - 0.12, edge + 0.10, d + (fbm(u, v, 6.0, 13) - 0.5) * 0.18)
    strands = fbm(u, v * 0.10, 8.0, 14)
    drips = sstep(0.52, 0.78, strands) * (1 - sstep(edge, edge + 0.45 + 0.2 * fbm(u, 0 * v, 3.0, 15), d))
    m = np.maximum(band, drips * 0.85) * (0.78 + 0.30 * fbm(u, v, 11.0, 16))
    m = np.minimum(m, 1) * sstep(1.0, 0.84, d) * sstep(1.0, 0.97, np.abs(u))
    return np.clip(m, 0, 1)


def save(mask, name):
    rgba = np.empty((RES, RES, 4), np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = mask
    rgba[..., 3] = 1
    im = bpy.data.images.new(name, RES, RES, alpha=False, is_data=True)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = os.path.join(OUT, name + ".png")
    im.file_format = "PNG"
    im.save()
    print(name, "mean", round(float(mask.mean()), 3), "max", round(float(mask.max()), 3),
          "edge max", round(float(max(mask[0].max(), mask[-1].max(), mask[:, 0].max(), mask[:, -1].max())), 4))


save(smudge(), "T_Soot_A")
save(streaks(), "T_Soot_B")
save(patches(), "T_Soot_C")
save(smoke(), "T_Soot_D")
