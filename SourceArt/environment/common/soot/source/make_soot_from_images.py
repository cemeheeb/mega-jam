"""Soot masks from the author's Nano Banana pictures (DESIGN.md §14, «выгоревшие комнаты»).

    /opt/homebrew/bin/python3 SourceArt/environment/common/soot/source/make_soot_from_images.py band ~/Downloads/image_1-1.png ...
    /opt/homebrew/bin/python3 SourceArt/environment/common/soot/source/make_soot_from_images.py plume ~/Downloads/image_2-1.png ...
    /opt/homebrew/bin/python3 SourceArt/environment/common/soot/source/make_soot_from_images.py wall ~/Downloads/image_3-1.png ...

The pictures are black soot on a white wall, straight on (prompts in ../asset.yml). Each one becomes
T_Soot_<Kind><N>.png in the asset folder (grey mask in RGB, 1 = full soot) and its source is kept as
source/images/<kind>-<N>.<real extension> (Nano Banana's .png files are sometimes WebP inside). Numbering starts at 1 every run, so a run replaces the whole kind.
- the white of the wall is measured on the bottom rows (they are clean in both kinds) and becomes 0;
  the densest soot (97th percentile) becomes 1;
- the mask is 1024 wide and keeps the picture's proportions, height rounded to a power of two (Nano Banana gives
  1024 x 1024 squares: the decal boxes in ARunRoom::ApplyBurn are close to square, so the smoke is not squashed);
- band (under the ceiling): the top rows are forced solid so neighbouring decals along a wall join into one line
  under the ceiling; the sides and the bottom fade to 0, so overlapping decals blend;
- plume (a tongue of smoke over a burnt column): the sides fade to 0 and only the last rows at the bottom,
  because the narrow scorched base of the plume is there; the top stays as drawn (it reaches the ceiling).
- wall (the whole wall of a burned room, 21:9, prompt in ../../soot-wall/asset.yml): soot reaches the bottom edge, so
  the white is the lightest pixels of the picture (1st percentile of the soot), not the bottom rows; 2048 wide (one
  decal covers a 9 m wall); a 0.1 haze everywhere (no clean patches); only the sides fade a little, so the soot meets the corners.
ARunRoom::ApplyBurn picks Band1..N, Plume1..N and Wall1..N by the burn seed; tools/ue/import_soot.py imports them.
"""
import os
import shutil
import sys

from PIL import Image, ImageChops, ImageOps

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
KINDS = {"band": "Band", "plume": "Plume", "wall": "Wall"}
WALL_HAZE = 26          # wall: least soot anywhere, 0.1 (the lightest patches of the picture would read as clean)


def ramp(n, start, end):
    """0..255 over [start, end) of n samples (shares of n), 255 after; reversed if start > end."""
    out = []
    for i in range(n):
        t = (i + 0.5) / n
        if start < end:
            k = (t - start) / (end - start)
        else:
            k = (start - t) / (start - end)
        k = min(max(k, 0.0), 1.0)
        out.append(round(255 * k * k * (3 - 2 * k)))
    return out


def gradient(size, xs=None, ys=None):
    w, h = size
    im = Image.new("L", size, 255)
    if xs is not None:
        row = Image.new("L", (w, 1))
        row.putdata(xs)
        im = ImageChops.multiply(im, row.resize(size, Image.NEAREST))
    if ys is not None:
        col = Image.new("L", (1, h))
        col.putdata(ys)
        im = ImageChops.multiply(im, col.resize(size, Image.NEAREST))
    return im


def percentile(im, q):
    hist = im.histogram()
    total, acc = sum(hist), 0
    for v, n in enumerate(hist):
        acc += n
        if acc >= q * total:
            return v
    return 255


def convert(path, kind):
    src = Image.open(path).convert("L")
    w = 2048 if kind == "wall" else 1024
    h = min((512, 1024, 2048), key=lambda p: abs(p - w * src.height / src.width))
    size = (w, h)
    soot = ImageOps.invert(src).resize(size, Image.LANCZOS)
    if kind == "wall":
        wall = percentile(soot, 0.01)
        lo = min(wall + 8, 200)
    else:
        wall = percentile(soot.crop((0, int(h * 0.88), w, h)), 0.5)
        lo = min(wall + 14, 200)
    hi = max(lo + 60, percentile(soot, 0.97))
    mask = soot.point([0 if v <= lo else 255 if v >= hi else round((v - lo) / (hi - lo) * 255) for v in range(256)])
    sides = [min(a, b) for a, b in zip(ramp(w, 0.0, 0.08), ramp(w, 1.0, 0.92))]
    if kind == "band":
        mask = ImageChops.lighter(mask, gradient(size, ys=ramp(h, 0.09, 0.03)))      # solid along the top edge
        mask = ImageChops.multiply(mask, gradient(size, xs=sides, ys=ramp(h, 1.0, 0.86)))
    elif kind == "wall":
        mask = ImageChops.lighter(mask, Image.new("L", size, WALL_HAZE))     # чистых мест на стене нет (автор, 15.11)
        mask = ImageChops.multiply(mask, gradient(size, xs=[min(a, b) for a, b in zip(ramp(w, 0.0, 0.03), ramp(w, 1.0, 0.97))]))
    else:
        mask = ImageChops.multiply(mask, gradient(size, xs=[min(a, b) for a, b in zip(ramp(w, 0.0, 0.12), ramp(w, 1.0, 0.88))],
                                                  ys=ramp(h, 1.0, 0.96)))
    return mask, (wall, lo, hi)


def main():
    kind, paths = sys.argv[1], [os.path.expanduser(p) for p in sys.argv[2:]]
    assert kind in KINDS and paths, __doc__
    name = KINDS[kind]
    os.makedirs(SRC, exist_ok=True)
    for i, path in enumerate(paths, 1):
        mask, levels = convert(path, kind)
        out = os.path.join(OUT, f"T_Soot_{name}{i}.png")
        Image.merge("RGB", (mask, mask, mask)).save(out)
        ext = {"JPEG": "jpg"}.get(Image.open(path).format, Image.open(path).format.lower())
        shutil.copyfile(path, os.path.join(SRC, f"{kind}-{i}.{ext}"))
        stat = mask.histogram()
        mean = sum(v * n for v, n in enumerate(stat)) / sum(stat) / 255
        print(f"{os.path.basename(out)} <- {os.path.basename(path)}: wall/lo/hi {levels}, mean {mean:.3f}")


if __name__ == "__main__":
    main()
