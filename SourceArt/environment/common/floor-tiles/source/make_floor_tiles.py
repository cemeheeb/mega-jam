"""Floor tiles: BaseColor and ORM for Unreal from the author's Nano Banana picture (asset.yml).

    /opt/homebrew/bin/python3 -I SourceArt/environment/common/floor-tiles/source/make_floor_tiles.py [picture]

With a picture argument it is first copied to images/floor-tiles-1.<real extension> (Nano Banana's .png files are
sometimes WebP inside); without one the copy in images/ is used. Writes into the asset folder:
- T_FloorTiles_BaseColor.png: the picture, 1024 x 1024 RGB (one 75 x 75 cm panel, the seam on the frame edge);
- T_FloorTiles_ORM.png: AO 1; roughness 0.85 on the rubber and 0.35 on the aluminium rim and screws; metallic 1 on
  the metal. Metal = the light pixels (the rubber is graphite, the rim warm light grey), softened by a 1 px blur.
The short path of asset.yml: no height and normal maps yet (steps 1-3 there), the panel reads from 3 m without them.
tools/ue/import_floor_tiles.py imports both into /Game/Environment/Common/FloorTiles.
"""
import glob
import os
import shutil
import sys

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(HERE, "images")
METAL_LO, METAL_HI = 95, 140          # brightness (0..255) where rubber turns into metal


def main():
    os.makedirs(IMAGES, exist_ok=True)
    if len(sys.argv) > 1:
        src = os.path.expanduser(sys.argv[1])
        fmt = Image.open(src).format
        for old in glob.glob(os.path.join(IMAGES, "floor-tiles-1.*")):
            os.remove(old)
        path = os.path.join(IMAGES, "floor-tiles-1." + {"JPEG": "jpg"}.get(fmt, fmt.lower()))
        shutil.copyfile(src, path)
    else:
        path = sorted(glob.glob(os.path.join(IMAGES, "floor-tiles-1.*")))[0]
    base = Image.open(path).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    base.save(os.path.join(HERE, "T_FloorTiles_BaseColor.png"))
    lum = base.convert("L").filter(ImageFilter.GaussianBlur(1))
    metal = lum.point(lambda v: 0 if v <= METAL_LO else 255 if v >= METAL_HI else round((v - METAL_LO) * 255 / (METAL_HI - METAL_LO)))
    rough = metal.point(lambda m: round(255 * (0.85 + (0.35 - 0.85) * m / 255)))
    ao = Image.new("L", base.size, 255)
    Image.merge("RGB", (ao, rough, metal)).save(os.path.join(HERE, "T_FloorTiles_ORM.png"))
    share = sum(n for v, n in enumerate(metal.histogram()) if v > 127) / (1024 * 1024)
    print(f"{os.path.basename(path)} -> T_FloorTiles_BaseColor.png, T_FloorTiles_ORM.png (metal {share:.1%} of the panel)")


if __name__ == "__main__":
    main()
