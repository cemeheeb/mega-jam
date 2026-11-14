"""Burned wall columns: take the baked soot off the Tripo base colour (замечание автора 15.11).

    /opt/homebrew/bin/python3 -I SourceArt/environment/common/wall-columns/source/clean_burned_textures.py

Runs after export_wall_columns_burned.py and writes over its T_WallColumn<Module>Burned<N>_BaseColor.png, reading the
untouched Tripo texture from tripo-burned/. Next to intact columns the burned models looked dirty all over; the soot
of a burned room now comes from the decals over the whole wall (ARunRoom::ApplyBurn), the model keeps its damage.
Frequency split on the brightness: detail = L / blur(L) keeps panel lines, cracks, drawers and burnt bits; the large
soot clouds (blur scale, RADIUS) keep only KEEP of their darkness, very dark large areas (holes) keep all of it.
The result is tinted to the warm off-white of the intact columns; saturated pixels (wires) keep their colour.
"""
import os

from PIL import Image, ImageFilter, ImageMath

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
TEXTURES = [   # (module, version, Tripo file) as in export_wall_columns_burned.py
    ("Rack", "", "burned_rack"),
    ("Drawers", "", "burned_drawers"),
    ("Vent", "", "burned_vent"),
    ("Header", "", "burned_header_2"),
    ("Header", "2", "burned_header"),
]
PAINT = (236, 233, 226)        # sRGB, close to the intact columns
RADIUS = 28                    # px of 2048: soot clouds are larger, panel lines and cracks smaller
KEEP = 0.3


def quantile(im, q):
    h = im.convert("L").histogram()
    n, acc = sum(h), 0
    for v, c in enumerate(h):
        acc += c
        if acc >= q * n:
            return v
    return 255


def lum(a, top):
    L, B, lo, hi = a["L"], a["B"], a["min"], a["max"]
    detail = lo(L / (B + 4.0), 1.25)                 # 1 = flat paint, cracks and edges below 1
    low = lo(B / top, 1.0)
    hole = hi(lo((0.25 - low) / 0.15, 1.0), 0.0)     # 1 where the large area is very dark
    keep = KEEP + (1.0 - KEEP) * hole
    return lo(detail * (1.0 - keep * (1.0 - low)) * 255.0, 255.0)


def clean(src):
    L = src.convert("L")
    B = L.filter(ImageFilter.GaussianBlur(RADIUS))
    top = max(quantile(B, 0.92), 1)
    y = ImageMath.lambda_eval(lambda a: lum(a, top), L=L.convert("F"), B=B.convert("F"))
    base = Image.merge("RGB", [ImageMath.lambda_eval(lambda a: a["y"] * (c / 255.0), y=y).convert("L") for c in PAINT])
    mask = src.convert("HSV").split()[1].point(lambda s: 255 if s > 100 else 0).filter(ImageFilter.GaussianBlur(1.5))
    return Image.composite(src.point(lambda v: min(255, round(v * 1.4))), base, mask)


for module, version, tripo in TEXTURES:
    src = Image.open(os.path.join(HERE, "tripo-burned", module, f"{tripo}.fbm", f"{tripo}_basecolor.jpg")).convert("RGB")
    out = os.path.join(OUT, f"T_WallColumn{module}Burned{version}_BaseColor.png")
    clean(src).save(out)
    print(os.path.basename(out), src.size)
