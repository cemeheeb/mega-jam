"""Game logo for the main menu: white letters on transparency from the author's picture (white on black).

    /opt/homebrew/bin/python3 SourceArt/ui/logo/source/make_logo.py      # needs Pillow

images/logo-1.png -> T_Logo.png (RGBA). Alpha comes from brightness with levels 120..235: the generator left grey
triangles (brightness 40..110) in the chamfer corners, they drop out, the letter edges stay smooth. Letters are pure
white, the menu tints them. Cropped to the letters with a 12 px margin.
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LO, HI, MARGIN = 120, 235, 12

lum = Image.open(os.path.join(HERE, "images", "logo-1.png")).convert("L")
alpha = lum.point(lambda v: max(0, min(255, round((v - LO) * 255 / (HI - LO)))))
x0, y0, x1, y1 = alpha.getbbox()
box = (max(x0 - MARGIN, 0), max(y0 - MARGIN, 0), min(x1 + MARGIN, lum.width), min(y1 + MARGIN, lum.height))
alpha = alpha.crop(box)
out = Image.new("RGBA", alpha.size, (255, 255, 255, 0))
out.putalpha(alpha)
out.save(os.path.join(HERE, "T_Logo.png"))
print("T_Logo.png", out.size, "letters", (x1 - x0, y1 - y0))
