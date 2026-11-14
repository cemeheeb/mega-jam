"""Корабль для главного меню: меш Tripo -> SourceArt/ui/menu-ship/SM_MenuShip.fbx (в сантиметрах) и текстуры.

    /Applications/Blender.app/Contents/MacOS/Blender -b --python tools/blender/export_menu_ship.py [-- <ship.fbx>] [--textures]

--textures — только текстуры, без FBX (после правки обработки цвета).

Без аргумента берёт source/tripo/ship.fbx ассета (текстура Tripo — в папке ship.fbm рядом).
Нос корабля (конец с антеннами; на другом конце три сопла) смотрит в +X Unreal, начало координат — середина габарита,
длина — LENGTH метров. Коллизии нет: корабль только для заставки.

Текстуры (рядом с FBX):
- T_MenuShip_BaseColor.png — базовый цвет Tripo, обработанный под заставку (автор, 14.11: «сделай текстуру корабля
  более контрастной и почти черно белой, добавь шума»): насыщенность SATURATION, тона растянуты и поджаты S-кривой,
  поверх — пятна шума трёх масштабов и мелкое зерно (зерно детерминированное, NOISE_SEED);
- T_MenuShip_Emissive.png — огни: бирюзовые полосы и тёплые окна, выбранные по цвету базовой текстуры
  (оранжевая краска корпуса темнее и насыщеннее окон и не светится);
- T_MenuShip_ORM.png — однотонная: AO 1, шероховатость 0,45, металл 0,6 (корпус — крашеный металл).
"""

import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(PROJECT, "SourceArt", "ui", "menu-ship")
NAME = "MenuShip"
LENGTH = 60.0      # метров от сопел до антенн
ORM = (1.0, 0.45, 0.6)
SATURATION = 0.12      # 0 — чёрно-белый, 1 — цвет Tripo
CONTRAST = 0.7         # сила S-кривой поверх растяжки тонов, 0–1
GRIME = 0.16           # размах пятен шума (доля яркости)
GRAIN = 0.035          # мелкое зерно
NOISE_SEED = 7


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def hue_window(h, lo, hi, soft=8.0):
    return smoothstep(lo - soft, lo, h) * (1.0 - smoothstep(hi, hi + soft, h))


def upsample(grid, h, w):
    """Билинейное растяжение сетки шума до h × w."""
    gh, gw = grid.shape
    y = np.linspace(0.0, gh - 1.001, h)
    x = np.linspace(0.0, gw - 1.001, w)
    y0, x0 = y.astype(int), x.astype(int)
    fy, fx = (y - y0)[:, None], (x - x0)[None, :]
    a = grid[y0][:, x0]
    b = grid[y0][:, x0 + 1]
    c = grid[y0 + 1][:, x0]
    d = grid[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def grade(rgb):
    """Почти чёрно-белый контрастный корпус с шумом (значения в sRGB, как лежат в файле)."""
    h, w, _ = rgb.shape
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    lo, hi = np.percentile(lum, [2.0, 98.0])
    t = np.clip((lum - lo) / max(hi - lo, 1e-4), 0.0, 1.0)
    t = t + (t * t * (3.0 - 2.0 * t) - t) * CONTRAST
    rng = np.random.default_rng(NOISE_SEED)
    grime = np.zeros((h, w), dtype=np.float32)
    for cell, amp in ((64, 0.5), (20, 0.3), (6, 0.2)):          # размер пятна в текселях, вес
        grime += amp * upsample(rng.random((h // cell + 2, w // cell + 2)).astype(np.float32), h, w)
    grime = (grime - grime.mean()) / max(grime.std(), 1e-4)
    grain = rng.normal(0.0, 1.0, (h, w)).astype(np.float32)
    L = np.clip(0.04 + 0.82 * t, 0.0, 1.0) * (1.0 + GRIME * np.clip(grime, -2.5, 2.5) / 2.5) + GRAIN * grain
    out = L[..., None] + (rgb - lum[..., None]) * SATURATION
    return np.clip(out, 0.0, 1.0)


def save_png(pixels, w, h, path, srgb=True):
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    img.pixels.foreach_set(pixels.astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()


def textures(src_jpg):
    img = bpy.data.images.load(src_jpg)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    rgb = px[..., :3]
    save_png(np.dstack([grade(rgb), np.ones((h, w))]), w, h, os.path.join(OUT, f"T_{NAME}_BaseColor.png"))

    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    v = mx
    s = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    d = np.maximum(mx - mn, 1e-4)
    hue = np.where(mx == r, ((g - b) / d) % 6.0, np.where(mx == g, (b - r) / d + 2.0, (r - g) / d + 4.0)) * 60.0
    cyan = hue_window(hue, 172, 212) * smoothstep(0.35, 0.55, s) * smoothstep(0.55, 0.80, v)
    warm = (hue_window(hue, 24, 50) * smoothstep(0.18, 0.32, s) * (1.0 - smoothstep(0.60, 0.74, s))
            * smoothstep(0.55, 0.80, v))
    glow = np.clip(np.maximum(cyan, warm), 0.0, 1.0)[..., None]
    emissive = rgb * glow
    save_png(np.dstack([emissive, np.ones((h, w))]), w, h, os.path.join(OUT, f"T_{NAME}_Emissive.png"))
    print(f"  emissive: светится {float((glow > 0.5).mean()) * 100:.2f}% текселей")

    orm = np.ones((4, 4, 4), dtype=np.float32)
    orm[..., 0], orm[..., 1], orm[..., 2] = ORM
    save_png(orm, 4, 4, os.path.join(OUT, f"T_{NAME}_ORM.png"), srgb=False)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    files = [a for a in argv if not a.startswith("--")]
    src = files[0] if files else os.path.join(OUT, "source", "tripo", "ship.fbx")
    jpg = os.path.join(os.path.dirname(src), "ship.fbm", "ship_basecolor.jpg")
    if "--textures" in argv:
        textures(jpg)
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(meshes) == 1, [o.name for o in meshes]
    ob = meshes[0]
    # единицу сцены менять только после импорта (как в export_singula.py)
    bpy.context.scene.unit_settings.scale_length = 0.01
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)

    # Tripo: длинная ось — Z (после поворота импорта), нос с антеннами — +Z. Нос -> +X: поворот вокруг Y на 90°.
    ob.data.transform(Matrix.Rotation(np.pi / 2, 4, "Y"))
    pts = [v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    ob.data.transform(Matrix.Translation(-(lo + hi) / 2))
    k = LENGTH / (hi.x - lo.x)
    ob.data.transform(Matrix.Scale(k * 100.0, 4))     # метры -> сантиметры
    size = (hi - lo) * k * 100.0

    name = f"SM_{NAME}"
    ob.name = ob.data.name = name
    if ob.data.uv_layers:
        ob.data.uv_layers[0].name = "UVMap"
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials.new(f"MI_{NAME}"))
    tri = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
    if hasattr(tri, "keep_custom_normals"):
        tri.keep_custom_normals = True

    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, name + ".fbx"),
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False, use_tspace=False,
        use_custom_props=False, add_leaf_bones=False, bake_anim=False,
        path_mode="STRIP", embed_textures=False, colors_type="NONE",
    )
    print(f"  {name}.fbx: {len(ob.data.polygons)} граней, {size.x:.0f} x {size.y:.0f} x {size.z:.0f} см")

    textures(jpg)


main()
