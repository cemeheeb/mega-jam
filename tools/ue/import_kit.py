"""Импорт ассетов конвейера kit (pipeline/kit.md) в /Game/Environment/...: текстуры, экземпляр материала, меши.

    python3 tools/ue/import_kit.py                          # все ассеты: импортировать то, чего ещё нет; материалы — всегда
    python3 tools/ue/import_kit.py bridge/navigator-console # один ассет
    python3 tools/ue/import_kit.py --mesh ...               # после новой выгрузки: удалить меши и импортировать заново
    python3 tools/ue/import_kit.py --tex ...                # после новой выгрузки текстур: удалить их и импортировать заново

Файлы готовит скрипт ассета source/export_<ассет>.py (SourceArt/environment/<ассет>/SM_*.fbx, T_*.png).
Отличие от import_singula.py: зелёный канал нормалей перевёрнут при выгрузке (DirectX), Flip Green выключен.
Мастер-материал — M_Kit (kit_materials.py). Удаление при --mesh обнуляет меши у акторов уровней и в блюпринтах
комнат: после него пересобрать комнаты (build_rooms.py). Нужен открытый редактор с проектом MegaJam, не в Play.
"""

import glob
import json
import os
import sys

from uemcp import tool

AP = "EditorToolset.EditorAppToolset"
AS = "editor_toolset.toolsets.asset.AssetTools"
MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"
TX = "editor_toolset.toolsets.texture.TextureTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "environment")

# ассет -> {материал: сила свечения карты Emissive}. Материал — префикс текстур T_<материал>_*.png в папке ассета,
# экземпляр — MI_<материал>; без записи свечение не задаётся. С автоэкспозицией свечение 1 почти не видно,
# экраны консоли — как огоньки наборов Singula. Сгоревшая консоль (SM_NavigatorConsole_Burned) — свой материал.
SETS = {
    "bridge/navigator-console": {"NavigatorConsole": 3.0},
}
TEXTURE = {   # суффикс -> (параметр M_Kit, свойства текстуры)
    "BaseColor": ("BaseColor", {"SRGB": True, "CompressionSettings": "TC_Default"}),
    "ORM": ("ORM", {"SRGB": False, "CompressionSettings": "TC_Masks"}),
    "Normal": ("Normal", {"SRGB": False, "CompressionSettings": "TC_Normalmap", "bFlipGreenChannel": False}),
    "Emissive": ("Emissive", {"SRGB": True, "CompressionSettings": "TC_Default"}),
}


def call(toolset, name, args):
    res = tool(toolset, name, args)
    if "ERROR" in res[:12]:
        raise RuntimeError(f"{name}: {res[:600]}")
    return json.loads(res).get("returnValue") if res.strip() else None


def ref(path):
    return {"refPath": f"{path}.{path.rsplit('/', 1)[1]}"}


def exists(path):
    return call(AS, "exists", {"path": path})


def camel(word):
    return "".join(w.capitalize() for w in word.split("-"))


def folder_of(set_path):
    return "/Game/Environment/" + "/".join(camel(p) for p in set_path.split("/"))


def material(src, folder, name, glow, saved):
    """MI_<name> из M_Kit с текстурами T_<name>_*.png, которые есть в папке ассета."""
    mi = f"{folder}/MI_{name}"
    if not exists(mi):
        call(MI, "create", {"folder_path": folder, "asset_name": f"MI_{name}", "parent": ref("/Game/Materials/M_Kit")})
    for suffix, (param, props) in TEXTURE.items():
        tex = f"T_{name}_{suffix}"
        png = os.path.join(src, tex + ".png")
        if not os.path.exists(png):
            continue
        path = f"{folder}/{tex}"
        if "--tex" in sys.argv and exists(path):
            call(AS, "delete", {"path": path})
        if not exists(path):
            call(TX, "import_file", {"folder_path": folder, "asset_name": tex, "source_file": png})
        call(OB, "set_properties", {"instance": ref(path), "values": json.dumps(props)})
        call(MI, "set_texture_parameter", {"instance": ref(mi), "name": param, "value": ref(path)})
        saved.append(path)
    if glow is not None:
        call(MI, "set_scalar_parameter", {"instance": ref(mi), "name": "EmissiveStrength", "value": glow})
    saved.append(mi)
    return mi


def import_set(set_path, glows):
    src = os.path.join(SRC, set_path)
    folder = folder_of(set_path)
    call(AS, "create_folder", {"path": folder})
    saved = []
    names = sorted(os.path.basename(p)[2:-len("_BaseColor.png")] for p in glob.glob(os.path.join(src, "T_*_BaseColor.png")))
    mis = {f"MI_{n}": material(src, folder, n, glows.get(n), saved) for n in names}

    files = sorted(glob.glob(os.path.join(src, "SM_*.fbx")))
    assert files, src
    for fbx in files:
        mesh_name = os.path.splitext(os.path.basename(fbx))[0]
        mesh_path = f"{folder}/{mesh_name}"
        if "--mesh" in sys.argv and exists(mesh_path):
            call(AS, "delete", {"path": mesh_path})
        if not exists(mesh_path):
            call(SM, "import_file", {"folder_path": folder, "asset_name": mesh_name, "source_file": fbx,
                                     "import_materials": False, "import_textures": False, "combine_meshes": True})
        mesh = ref(mesh_path)
        slots = call(SM, "get_material_slots", {"mesh": mesh})
        assert slots and all(s in mis for s in slots), (mesh_name, slots, list(mis))
        for slot in slots:
            call(SM, "set_material", {"mesh": mesh, "slot_name": slot, "material": ref(mis[slot])})
        b = call(SM, "get_bounds", {"mesh": mesh})
        lo, hi = (tuple(round(b[k][a], 1) for a in "xyz") for k in ("min", "max"))
        print(f"  {mesh_name}: от {lo} до {hi} см, треугольников {call(SM, 'get_triangle_count', {'mesh': mesh})}, "
              f"nanite {call(SM, 'is_nanite_enabled', {'mesh': mesh})}")
        saved.append(mesh_path)
    print("saved", set_path, call(AS, "save_assets", {"asset_paths": saved}))


def main():
    # в Play инструменты ассетов не работают, а отвечают без ошибки (exists — «нет»): create встанет на модальном окне
    res = tool(AP, "IsPIERunning", {})
    try:
        playing = json.loads(res).get("returnValue")
    except ValueError:
        playing = None
    if playing is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res[:120]!r}). Остановите игру и запустите импорт снова.")
    assert exists("/Game/Materials/M_Kit"), "нет /Game/Materials/M_Kit: сначала tools/ue/kit_materials.py"
    # FbxFactory без опций у инструмента: нормали из файла, коллизия — коробки UCX из файла
    defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
    for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
        call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for set_path in (args or list(SETS)):
        print("set", set_path, "->", folder_of(set_path))
        import_set(set_path, SETS[set_path])


if __name__ == "__main__":
    main()
