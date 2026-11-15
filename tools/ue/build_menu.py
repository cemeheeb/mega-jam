"""Главное меню: корабль, материал неба с чёрной дырой и уровень Lvl_Menu с ведущим AMenuDirector.

    python3 tools/ue/build_menu.py            # всё: корабль (если его нет), материал, уровень
    python3 tools/ue/build_menu.py --shader   # только обновить код шейдера в M_BlackHole (tools/ue/shaders/BlackHole.hlsl)
    python3 tools/ue/build_menu.py --mesh     # корабль после новой выгрузки: удалить SM_MenuShip и импортировать заново
    python3 tools/ue/build_menu.py --textures # текстуры корабля после новой выгрузки: заменить T_MenuShip_*
    python3 tools/ue/build_menu.py --lens     # только материал линзы M_MenuLens (хроматическая аберрация вокруг курсора)

Файлы корабля готовит tools/blender/export_menu_ship.py (SourceArt/ui/menu-ship). Ассеты — в /Game/Game/Menu,
уровень — /Game/Game/Maps/Lvl_Menu (папка /Game/Game упаковывается целиком). Поведение — в C++ (Source/MegaJam/Menu).
Нужен открытый редактор с проектом MegaJam, не в режиме Play. В конце открыт тот уровень, что был до запуска.
"""

import json
import os
import sys

from uemcp import tool
from build_rooms import ensure_not_playing

AS = "editor_toolset.toolsets.asset.AssetTools"
MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
MT = "editor_toolset.toolsets.material.MaterialTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SC = "editor_toolset.toolsets.scene.SceneTools"
AC = "editor_toolset.toolsets.actor.ActorTools"
SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"
TX = "editor_toolset.toolsets.texture.TextureTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "ui", "menu-ship")
SHADER = os.path.join(PROJECT, "tools", "ue", "shaders", "BlackHole.hlsl")
FOLDER = "/Game/Game/Menu"
MATERIAL = f"{FOLDER}/M_BlackHole"
LENS = f"{FOLDER}/M_MenuLens"
LEVEL = "/Game/Game/Maps/Lvl_Menu"
SHIP_GLOW = 6.0       # сила свечения огней корабля (карта Emissive)
TEMPLATE_ACTORS = ("Floor", "DirectionalLight", "Light Source", "SkyAtmosphere", "SkyLight", "ExponentialHeightFog",
                   "VolumetricCloud", "SkySphere", "SM_SkySphere", "SphereReflectionCapture", "PostProcessVolume")
TEXTURES = {
    "BaseColor": ("BaseColor", {"SRGB": True, "CompressionSettings": "TC_Default"}),
    "ORM": ("ORM", {"SRGB": False, "CompressionSettings": "TC_Masks"}),
    "Emissive": ("Emissive", {"SRGB": True, "CompressionSettings": "TC_Default"}),
}
# входы узла Custom -> что к ним подключено (параметры по умолчанию совпадают со свойствами AMenuDirector)
PARAMS = {
    "Hole": (0.986, 0.156, 0.052, 30.0),
    "Disk": (7.0, -11.0, 3.0, 13.0),
    "Look": (3.0, 1.0, 1.0, 4600.0),
}


def call(toolset, name, args):
    res = tool(toolset, name, args)
    if "ERROR" in res[:12]:
        raise RuntimeError(f"{name}: {res[:800]}")
    return json.loads(res).get("returnValue") if res.strip() else None


def ref(path):
    return {"refPath": f"{path}.{path.rsplit('/', 1)[1]}"}


def exists(path):
    return call(AS, "exists", {"path": path})


def set_props(obj, values):
    call(OB, "set_properties", {"instance": obj, "values": json.dumps(values)})


def import_ship(remesh):
    call(AS, "create_folder", {"path": FOLDER})
    mi = f"{FOLDER}/MI_MenuShip"
    if not exists(mi):
        call(MI, "create", {"folder_path": FOLDER, "asset_name": "MI_MenuShip", "parent": ref("/Game/Materials/M_Kit")})
    saved = []
    for suffix, (param, props) in TEXTURES.items():
        tex = f"T_MenuShip_{suffix}"
        path = f"{FOLDER}/{tex}"
        if not exists(path):
            call(TX, "import_file", {"folder_path": FOLDER, "asset_name": tex, "source_file": os.path.join(SRC, tex + ".png")})
        set_props(ref(path), props)
        call(MI, "set_texture_parameter", {"instance": ref(mi), "name": param, "value": ref(path)})
        saved.append(path)
    call(MI, "set_scalar_parameter", {"instance": ref(mi), "name": "EmissiveStrength", "value": SHIP_GLOW})
    saved.append(mi)

    mesh_path = f"{FOLDER}/SM_MenuShip"
    if remesh and exists(mesh_path):
        call(AS, "delete", {"path": mesh_path})
    if not exists(mesh_path):
        defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
        for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                    "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
            call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})
        call(SM, "import_file", {"folder_path": FOLDER, "asset_name": "SM_MenuShip",
                                 "source_file": os.path.join(SRC, "SM_MenuShip.fbx"),
                                 "import_materials": False, "import_textures": False, "combine_meshes": True})
    mesh = ref(mesh_path)
    slots = call(SM, "get_material_slots", {"mesh": mesh})
    call(SM, "set_material", {"mesh": mesh, "slot_name": slots[0], "material": ref(mi)})
    b = call(SM, "get_bounds", {"mesh": mesh})
    print("  SM_MenuShip:", {k: {a: round(b[k][a]) for a in "xyz"} for k in ("min", "max")},
          "треугольников", call(SM, "get_triangle_count", {"mesh": mesh}))
    saved.append(mesh_path)
    call(AS, "save_assets", {"asset_paths": saved})


def replace_textures():
    """Повторного импорта у инструментов нет: материал на время смотрит на текстуру движка, старая удаляется
    (на неё больше никто не ссылается), новая импортируется под тем же именем и возвращается в материал."""
    mi = f"{FOLDER}/MI_MenuShip"
    placeholder = {"refPath": "/Engine/EngineResources/DefaultTexture.DefaultTexture"}
    for suffix, (param, props) in TEXTURES.items():
        path = f"{FOLDER}/T_MenuShip_{suffix}"
        call(MI, "set_texture_parameter", {"instance": ref(mi), "name": param, "value": placeholder})
        call(AS, "save_assets", {"asset_paths": [mi]})
        if exists(path):
            call(AS, "delete", {"path": path})
            assert not exists(path), f"не удалилась {path}"
        call(TX, "import_file", {"folder_path": FOLDER, "asset_name": f"T_MenuShip_{suffix}",
                                 "source_file": os.path.join(SRC, f"T_MenuShip_{suffix}.png")})
        set_props(ref(path), props)
        call(MI, "set_texture_parameter", {"instance": ref(mi), "name": param, "value": ref(path)})
        call(AS, "save_assets", {"asset_paths": [path, mi]})
        print("  заменена", path)


def shader_code():
    with open(SHADER, encoding="utf-8") as f:
        return f.read()


def add(m, cls, x, y, **props):
    e = call(MT, "add_expression", {"material_or_function": m,
                                    "expression_class": {"refPath": f"/Script/Engine.MaterialExpression{cls}"},
                                    "x": x, "y": y})
    if props:
        set_props(e, props)
    return e


def link(a, pin, b, inp):
    call(MT, "connect_expressions", {"from_expression": a, "from_output_name": pin, "to_expression": b, "to_input_name": inp})


def custom_node(m):
    for e in call(MT, "get_expressions", {"material_or_function": m}) or []:
        if "MaterialExpressionCustom" in e["refPath"]:
            return e
    return None


def build_material():
    """Граф строится один раз; потом меняется только код узла Custom (удалять узлы у загруженного материала опасно)."""
    call(AS, "create_folder", {"path": FOLDER})
    if exists(MATERIAL):
        m = ref(MATERIAL)
        node = custom_node(m)
        assert node, "в M_BlackHole нет узла Custom"
        set_props(node, {"Code": shader_code()})
    else:
        m = call(MT, "create_material", {"folder_path": FOLDER, "asset_name": "M_BlackHole"})
        node = add(m, "Custom", 0, 0, Code=shader_code(), OutputType="CMOT_Float3", Description="BlackHole")
        # массив входов растёт по одному элементу, прежние передаются в точности как их отдаёт редактор:
        # сразу и размер, и элементы инструмент не меняет
        for k, name in enumerate(["InDir", "InTime", "InHole", "InDisk", "InLook"]):
            cur = json.loads(call(OB, "get_properties", {"instance": node, "properties": ["Inputs"]}))["Inputs"]
            if k < len(cur):
                cur[k]["inputName"] = name
            else:
                cur.append({**cur[0], "inputName": name})
            set_props(node, {"Inputs": cur})
        cam = add(m, "CameraVectorWS", -600, -300)
        neg = add(m, "Multiply", -350, -300, ConstB=-1.0)
        link(cam, "", neg, "A")
        link(neg, "", node, "InDir")
        link(add(m, "Time", -600, -150), "", node, "InTime")
        for i, (name, (r, g, b, a)) in enumerate(PARAMS.items()):
            p = add(m, "VectorParameter", -600, i * 160, ParameterName=name,
                    DefaultValue={"R": r, "G": g, "B": b, "A": a})
            outs = call(MT, "get_expression_output_names", {"expression": p})
            if "RGBA" in outs:
                link(p, "RGBA", node, f"In{name}")
            else:
                app = add(m, "AppendVector", -350, i * 160)
                link(p, "", app, "A")
                link(p, "A", app, "B")
                link(app, "", node, f"In{name}")
        call(MT, "connect_to_output", {"expression": node, "output_name": "", "material_property": "MP_EmissiveColor"})
        set_props(m, {"ShadingModel": "MSM_Unlit", "TwoSided": True, "BlendMode": "BLEND_Opaque"})
    # мерцание звёзд и вращение диска — анимация пикселей без векторов движения: без флажка TSR гасит её как мерцание
    set_props(m, {"bHasPixelAnimation": True})
    print("  входы Custom:", call(MT, "get_expression_input_names", {"expression": node}))
    call(MT, "recompile", {"material_or_function": m})
    call(AS, "save_assets", {"asset_paths": [MATERIAL]})


LENS_CODE = """
// UV — точка экрана, Lens.xy — середина линзы (доли экрана), Lens.z — сила, Lens.w — ширина экрана в его высотах.
// Сдвиг растёт от нуля под линзой и упирается в предел Lens.z * Radius высот экрана: дальний текст остаётся читаемым.
float2 d = UV - Lens.xy;
float len = length(d * float2(Lens.w, 1.0)) / max(Radius, 0.01);
return d * (Lens.z / sqrt(1.0 + len * len));
"""


def build_lens():
    """Линза меню (просьба автора 15.11): хроматическая аберрация, которая идёт за мышью. Постобработка после
    тонального отображения: красный канал кадра берётся ближе к середине линзы, синий — дальше, зелёный на месте.
    Сдвиг считает узел Custom (LENS_CODE); та же формула — AMenuDirector::LensShift для слоя меню (AMenuHUD).
    Параметры Lens и Radius каждый кадр ставит AMenuDirector. Граф строится один раз, потом меняется только код."""
    call(AS, "create_folder", {"path": FOLDER})
    if exists(LENS):
        node = custom_node(ref(LENS))
        assert node, "в M_MenuLens нет узла Custom"
        set_props(node, {"Code": LENS_CODE})
        call(MT, "recompile", {"material_or_function": ref(LENS)})
        call(AS, "save_assets", {"asset_paths": [LENS]})
        print("  M_MenuLens: обновлён код узла Custom")
        return
    m = call(MT, "create_material", {"folder_path": FOLDER, "asset_name": "M_MenuLens"})
    uv = add(m, "ScreenPosition", -1300, 0)
    lens = add(m, "VectorParameter", -1300, 250, ParameterName="Lens", DefaultValue={"R": 0.5, "G": 0.5, "B": 0.0035, "A": 1.78})
    lens4 = add(m, "AppendVector", -1050, 250)
    link(lens, "RGB", lens4, "A")
    link(lens, "A", lens4, "B")
    radius = add(m, "ScalarParameter", -1300, 500, ParameterName="Radius", DefaultValue=0.7)
    node = add(m, "Custom", -800, 150, Code=LENS_CODE, OutputType="CMOT_Float2", Description="LensShift")
    for k, name in enumerate(["UV", "Lens", "Radius"]):
        cur = json.loads(call(OB, "get_properties", {"instance": node, "properties": ["Inputs"]}))["Inputs"]
        if k < len(cur):
            cur[k]["inputName"] = name
        else:
            cur.append({**cur[0], "inputName": name})
        set_props(node, {"Inputs": cur})
    link(uv, "ViewportUV", node, "UV")
    link(lens4, "", node, "Lens")
    link(radius, "", node, "Radius")
    uv_r = add(m, "Subtract", -450, -200)
    link(uv, "ViewportUV", uv_r, "A")
    link(node, "", uv_r, "B")
    uv_b = add(m, "Add", -450, 400)
    link(uv, "ViewportUV", uv_b, "A")
    link(node, "", uv_b, "B")
    parts = []
    for k, (coords, mask) in enumerate(((uv_r, "R"), (None, "G"), (uv_b, "B"))):
        tex = add(m, "SceneTexture", -200, -200 + k * 300, SceneTextureId="PPI_PostProcessInput0", bFiltered=True)
        if coords:
            link(coords, "", tex, call(MT, "get_expression_input_names", {"expression": tex})[0])
        one = add(m, "ComponentMask", 100, -200 + k * 300, R=mask == "R", G=mask == "G", B=mask == "B", A=False)
        link(tex, "Color", one, "")
        parts.append(one)
    rg = add(m, "AppendVector", 350, -50)
    link(parts[0], "", rg, "A")
    link(parts[1], "", rg, "B")
    rgb = add(m, "AppendVector", 550, 50)
    link(rg, "", rgb, "A")
    link(parts[2], "", rgb, "B")
    call(MT, "connect_to_output", {"expression": rgb, "output_name": "", "material_property": "MP_EmissiveColor"})
    set_props(m, {"MaterialDomain": "MD_PostProcess", "BlendableLocation": "BL_SceneColorAfterTonemapping"})
    print("  входы Custom:", call(MT, "get_expression_input_names", {"expression": node}))
    call(MT, "recompile", {"material_or_function": m})
    call(AS, "save_assets", {"asset_paths": [LENS]})
    print("  собран", LENS)


def labels():
    out = []
    for a in call(SC, "find_actors", {"name": "", "tag": "", "collision_channels": []}) or []:
        out.append((call(AC, "get_label", {"actor": a}), a))
    return out


def build_level():
    if not exists(LEVEL):
        call(AS, "duplicate", {"path": "/Engine/Maps/Templates/Template_Default", "new_path": LEVEL})
        call(AS, "save_assets", {"asset_paths": [LEVEL]})
    if call(SC, "get_current_level", {}) != LEVEL:
        call(SC, "load_level", {"level_path": LEVEL})
    # из шаблона уходят пол, солнце, атмосфера, облака, туман и небесный свет: небо и свет даёт ведущий меню.
    # Служебные акторы (World Settings, объём физики и т. п.) не трогать.
    present = labels()
    print("  на уровне:", ", ".join(l for l, _ in present))
    for label, actor in present:
        if label.startswith(TEMPLATE_ACTORS):
            print("  убран", label)
            call(SC, "remove_from_scene", {"actor": actor})
    if not [l for l, _ in labels() if l.startswith("MenuDirector")]:
        call(SC, "add_to_scene_from_class", {"actor_type": {"refPath": "/Script/MegaJam.MenuDirector"}, "name": "MenuDirector",
                                             "xform": {"location": {"x": 0, "y": 0, "z": 0}}})
    ws = [a for l, a in labels() if l.startswith("WorldSettings")][0]
    set_props(ws, {"DefaultGameMode": "/Script/MegaJam.MenuGameMode"})
    print("  режим игры уровня:", call(OB, "get_properties", {"instance": ws, "properties": ["DefaultGameMode"]}))
    call(AS, "save_assets", {"asset_paths": [LEVEL]})


def main():
    ensure_not_playing()
    start_level = call(SC, "get_current_level", {})
    if "--shader" in sys.argv:
        build_material()
        return
    if "--textures" in sys.argv:
        replace_textures()
        return
    if "--lens" in sys.argv:
        build_lens()
        return
    if not exists(f"{FOLDER}/SM_MenuShip") or "--mesh" in sys.argv:
        import_ship("--mesh" in sys.argv)
    build_material()
    build_lens()
    build_level()
    if start_level and start_level != LEVEL:
        call(SC, "load_level", {"level_path": start_level})
    print("готово:", MATERIAL, LEVEL)


if __name__ == "__main__":
    main()
