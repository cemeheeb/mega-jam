"""Volume noise for the ray-marched smoke M_SmokeVolume (DESIGN.md 5.9, smoke like a CS2 smoke grenade).

    /Applications/Blender.app/Contents/Resources/*/python/bin/python3.13 -I SourceArt/fx/anomalies/source/make_smoke_volume.py

Needs numpy only (Blender's Python has it; the PNG is written by hand). Writes SourceArt/fx/anomalies/T_SmokeVolume.png:
a 64 x 64 x 64 volume that tiles on all three axes, stored as an 8 x 8 atlas of z slices. Every slice is a 66 px
tile: 64 px plus a 1 px wrapped border, so bilinear filtering stays inside the tile and the noise still tiles.
528 x 528 RGB, no mips, uncompressed in Unreal (tools/ue/import_anomalies.py).
  R - the puffs: inverted Worley noise in three octaves mixed with smooth value noise (cauliflower shapes);
  G - detail for eroding the edges: finer inverted Worley noise, other seed;
  B - unused.
"""
import os
import struct
import zlib

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = 64
GRID = 8
TILE = N + 2
SEED = 2026


def worley(rng, cells):
    """Inverted tileable Worley noise: 1 at a feature point, 0 far from all of them."""
    pts = rng.random((cells, cells, cells, 3))
    g = (np.arange(N) + 0.5) / N * cells
    p = np.stack(np.meshgrid(g, g, g, indexing="ij"), axis=-1)          # voxel centres in cell units
    base = np.floor(p).astype(int)
    best = np.full((N, N, N), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = base + (dx, dy, dz)
                w = c % cells
                f = c + pts[w[..., 0], w[..., 1], w[..., 2]]
                best = np.minimum(best, np.linalg.norm(p - f, axis=-1))
    return np.clip(1.0 - best, 0.0, 1.0)


def value(rng, cells):
    """Tileable smooth value noise: random lattice, smoothstep interpolation with wrap-around."""
    lat = rng.random((cells, cells, cells))
    g = (np.arange(N) + 0.5) / N * cells
    i = np.floor(g).astype(int)
    f = g - i
    f = f * f * (3.0 - 2.0 * f)
    out = np.zeros((N, N, N))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                wx = (f if dx else 1.0 - f)[:, None, None]
                wy = (f if dy else 1.0 - f)[None, :, None]
                wz = (f if dz else 1.0 - f)[None, None, :]
                out += wx * wy * wz * lat[np.ix_((i + dx) % cells, (i + dy) % cells, (i + dz) % cells)]
    return out


def stretch(v, lo=1.0, hi=99.0):
    a, b = np.percentile(v, lo), np.percentile(v, hi)
    return np.clip((v - a) / (b - a), 0.0, 1.0)


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    rng = np.random.default_rng(SEED)
    puffs = 0.55 * worley(rng, 3) + 0.3 * worley(rng, 6) + 0.15 * worley(rng, 12)
    soft = 0.65 * value(rng, 4) + 0.35 * value(rng, 8)
    r = stretch(0.72 * stretch(puffs) + 0.28 * stretch(soft))
    g = stretch(0.6 * worley(rng, 5) + 0.4 * worley(rng, 10))
    vol = np.stack([r, g, np.zeros_like(r)], axis=-1)                    # [x, y, z, channel]
    atlas = np.zeros((GRID * TILE, GRID * TILE, 3))
    for z in range(N):
        sl = np.transpose(vol[:, :, z, :], (1, 0, 2))                    # rows are y, columns are x
        sl = np.pad(sl, ((1, 1), (1, 1), (0, 0)), mode="wrap")
        ty, tx = divmod(z, GRID)
        atlas[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = sl
    out = os.path.join(HERE, "T_SmokeVolume.png")
    write_png(out, np.round(atlas * 255.0).astype(np.uint8))
    print("T_SmokeVolume.png", atlas.shape[1], "x", atlas.shape[0], "R mean %.2f G mean %.2f" % (r.mean(), g.mean()))


if __name__ == "__main__":
    main()
