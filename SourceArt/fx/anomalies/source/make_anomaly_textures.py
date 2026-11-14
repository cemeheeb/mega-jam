"""Textures of the anomalies (DESIGN.md 5.9): tileable smoke noise for M_Smoke.

    /opt/homebrew/bin/python3 -I SourceArt/fx/anomalies/source/make_anomaly_textures.py

Writes SourceArt/fx/anomalies/T_SmokeNoise.png: 512 x 512 grey, fractal value noise that tiles on both axes
(each octave is a random grid upscaled with wrap-around), contrast stretched so the material gets both clear gaps
and dense puffs. tools/ue/import_anomalies.py imports it into /Game/FX/Anomalies.
"""
import os
import random

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 512
SEED = 15


def octave(rng, cells):
    small = Image.new("L", (cells, cells))
    small.putdata([rng.randrange(256) for _ in range(cells * cells)])
    # 3 x 3 tiles, smooth upscale, centre crop: the edges match because the neighbours are the same tile
    big = Image.new("L", (cells * 3, cells * 3))
    for i in range(3):
        for j in range(3):
            big.paste(small, (i * cells, j * cells))
    big = big.resize((SIZE * 3, SIZE * 3), Image.BICUBIC)
    return big.crop((SIZE, SIZE, 2 * SIZE, 2 * SIZE))


def main():
    rng = random.Random(SEED)
    acc = None
    total = 0.0
    for cells, weight in ((4, 0.5), (8, 0.27), (16, 0.14), (32, 0.09)):
        o = octave(rng, cells).point(lambda v, w=weight: v * w)
        acc = o if acc is None else ImageChops.add(acc, o)
        total += weight
    lo, hi = acc.getextrema()
    out = acc.point(lambda v: max(0, min(255, round((v - lo) / (hi - lo) * 330 - 60))))
    out.save(os.path.join(HERE, "T_SmokeNoise.png"))
    print("T_SmokeNoise.png", out.size, "range", out.getextrema())


if __name__ == "__main__":
    main()
