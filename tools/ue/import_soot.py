"""Копоть выгоревших комнат: маски, материал декали M_SootDecal и экземпляры MI_Soot_A/B/C (DESIGN.md §14).

    python3 tools/ue/import_soot.py [--master]

Маски A–D делает SourceArt/environment/common/soot/source/make_soot.py, Band<N> и Plume<N> (дымовые следы из картинок
автора) — make_soot_from_images.py там же; импортируются все T_Soot_*.png папки. M_SootDecal (/Game/Materials) — отложенная
декаль, Translucent: цвет копоти, шероховатость, непрозрачность = маска × Opacity × угол. Угол: декаль проецируется
сквозь всю свою коробку и на поверхностях вдоль оси проекции (верх мебели под боковой декалью, бока колонок под
полосой) тянется полосами; там она гаснет. Нормаль поверхности берётся из производных положения пикселя (у декали
DBuffer нет нормали сцены), ось проекции — параметр Axis, его ставит ARunRoom::AddSoot. Экземпляры — в
/Game/Environment/Common/Soot, по одному на маску; ARunRoom (выгоревшая комната) берёт их по пути и делает
динамический экземпляр со своей Opacity, Axis и MirrorU (зеркало картинки). Материал создаётся, только если его нет; с ключом --master граф
собирается заново на месте (экземпляры остаются).
Нужен открытый редактор с проектом MegaJam, не в Play.
"""

import glob
import json
import os
import sys

from kit_materials import AS, MT, TX, add, call, fresh_material, link, out, ref, set_props
from uemcp import tool

MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "environment", "common", "soot")
FOLDER = "/Game/Environment/Common/Soot"
MASTER = "/Game/Materials/M_SootDecal"
# все маски папки: A–D делает make_soot.py, Band<N> и Plume<N> — make_soot_from_images.py из картинок автора
MASKS = sorted(os.path.basename(p)[len("T_Soot_"):-4] for p in glob.glob(os.path.join(SRC, "T_Soot_*.png")))


def build_master(default_mask):
    m = fresh_material("M_SootDecal")
    mask = add(m, "TextureSampleParameter2D", -700, 0, parameterName="Soot", samplerType="SAMPLERTYPE_Masks",
               texture=default_mask, sortPriority=0)
    opacity = add(m, "ScalarParameter", -700, 300, parameterName="Opacity", defaultValue=0.85, sortPriority=1)
    color = add(m, "VectorParameter", -700, -300, parameterName="Color",
                defaultValue={"r": 0.012, "g": 0.011, "b": 0.010, "a": 1.0}, sortPriority=2)
    rough = add(m, "ScalarParameter", -700, 450, parameterName="Roughness", defaultValue=0.95, sortPriority=3)
    axis = add(m, "VectorParameter", -700, 900, parameterName="Axis",
               defaultValue={"r": 1.0, "g": 0.0, "b": 0.0, "a": 0.0}, sortPriority=4)
    # зеркало по горизонтали: u -> |MirrorU − u| (0 — как есть, 1 — 1 − u); ставит ARunRoom::AddSoot по зерну
    mirror = add(m, "ScalarParameter", -1500, 0, parameterName="MirrorU", defaultValue=0.0, sortPriority=5)
    uv = add(m, "TextureCoordinate", -1500, 150)
    u = add(m, "ComponentMask", -1300, 100, R=True, G=False, B=False, A=False)
    v = add(m, "ComponentMask", -1300, 200, R=False, G=True, B=False, A=False)
    link(uv, "", u, "")
    link(uv, "", v, "")
    du = add(m, "Subtract", -1150, 50)
    link(mirror, "", du, "A")
    link(u, "", du, "B")
    au = add(m, "Abs", -1000, 50)
    link(du, "", au, "")
    uv2 = add(m, "AppendVector", -850, 100)
    link(au, "", uv2, "A")
    link(v, "", uv2, "B")
    link(uv2, "", mask, "UVs")
    mul = add(m, "Multiply", -300, 150)
    link(mask, "R", mul, "A")
    link(opacity, "", mul, "B")
    # нормаль поверхности под пикселем: cross(ddx, ddy) положения (относительно камеры — без потери точности)
    wp = add(m, "WorldPosition", -1300, 650, WorldPositionShaderOffset="WPT_CameraRelative")
    dx = add(m, "DDX", -1100, 600)
    dy = add(m, "DDY", -1100, 700)
    link(wp, "", dx, "Value")
    link(wp, "", dy, "Value")
    cross = add(m, "CrossProduct", -950, 650)
    link(dx, "", cross, "A")
    link(dy, "", cross, "B")
    normal = add(m, "Normalize", -800, 650)
    link(cross, "", normal, "VectorInput")
    dot = add(m, "DotProduct", -500, 700)
    link(normal, "", dot, "A")
    link(axis, "RGB", dot, "B")
    face = add(m, "Abs", -350, 700)
    link(dot, "", face, "")
    # |cos| 0,3 -> 0, 0,6 -> 1: поверхность под углом больше ~72° к оси проекции копоти не получает, до ~53° — вся
    ramp = add(m, "ConstantBiasScale", -200, 700, Bias=-0.3, Scale=1.0 / 0.3)
    link(face, "", ramp, "")
    clamp = add(m, "Saturate", -50, 700)
    link(ramp, "", clamp, "")
    fade = add(m, "Multiply", 100, 300)
    link(mul, "", fade, "A")
    link(clamp, "", fade, "B")
    out(fade, "", "MP_Opacity")
    out(color, "RGB", "MP_BaseColor")
    out(rough, "", "MP_Roughness")
    set_props(m, {"materialDomain": "MD_DeferredDecal", "blendMode": "BLEND_Translucent"})
    call(MT, "recompile", {"material_or_function": m})
    call(MT, "layout_expressions", {"material_or_function": m})
    return m


def main():
    res = tool("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    try:
        playing = json.loads(res).get("returnValue")
    except ValueError:
        playing = None
    if playing is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res[:120]!r}). Остановите игру и запустите снова.")
    call(AS, "create_folder", {"path": FOLDER})
    saved = []
    masks = {}
    for k in MASKS:
        name = f"T_Soot_{k}"
        path = f"{FOLDER}/{name}"
        if not call(AS, "exists", {"path": path}):
            call(TX, "import_file", {"folder_path": FOLDER, "asset_name": name, "source_file": os.path.join(SRC, name + ".png")})
        set_props(ref(path), {"SRGB": False, "CompressionSettings": "TC_Masks"})
        masks[k] = ref(path)
        saved.append(path)
    if call(AS, "exists", {"path": MASTER}) and "--master" not in sys.argv:
        print("есть, не трогаю:", MASTER)
    else:
        build_master(masks["A"])
    saved.append(MASTER)
    for k in MASKS:
        path = f"{FOLDER}/MI_Soot_{k}"
        if not call(AS, "exists", {"path": path}):
            call(MI, "create", {"folder_path": FOLDER, "asset_name": f"MI_Soot_{k}", "parent": ref(MASTER)})
        call(MI, "set_texture_parameter", {"instance": ref(path), "name": "Soot", "value": masks[k]})
        saved.append(path)
    print("saved", call(AS, "save_assets", {"asset_paths": saved}), saved)


if __name__ == "__main__":
    main()
