"""Импорт панелей потолка в /Game/Environment/Common/CeilingTiles: однотонные материалы зон и четыре меша.

    python3 tools/ue/import_ceiling_tiles.py          # импортировать то, чего ещё нет; материалы и слоты — всегда
    python3 tools/ue/import_ceiling_tiles.py --mesh   # после новой выгрузки: удалить меши и импортировать заново

Файлы готовит SourceArt/environment/common/ceiling-tiles/source/export_ceiling_tiles.py: SM_CeilingTile, ...Light,
...Vent, ...Hatch, у каждого слот на зону (MI_Ceiling<Зона>). Текстур нет: потолок видно с 3 м, зоны — экземпляры
M_KitSolid со значениями палитры зон материала CeilingTiles в blend (линейные). Матовый плафон светит.
Коллизии у панелей нет: её даёт коробка потолка комнаты над ними. Раскладка по комнатам — tools/ue/build_rooms.py
(ceiling_tiles). Удаление при --mesh обнуляет меши в блюпринтах комнат: после него пересобрать комнаты.
Нужен открытый редактор с проектом MegaJam, не в Play.
"""

import glob
import json
import os
import sys

from import_wall_columns import call, exists, instance, ref, set_params

AS = "editor_toolset.toolsets.asset.AssetTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "environment", "common", "ceiling-tiles")
FOLDER = "/Game/Environment/Common/CeilingTiles"

# зона -> параметры M_KitSolid: цвет, шероховатость и металл из палитры blend; свечение плафона подобрано по кадру
# (с автоэкспозицией свечение 1 почти не отличается от белой краски)
ZONES = {
    "CeilingWhite": {"Color": (0.839, 0.823, 0.776), "Roughness": 0.42},
    "CeilingAluminium": {"Color": (0.485, 0.503, 0.527), "Roughness": 0.32, "Metallic": 1.0},
    "CeilingGraphite": {"Color": (0.027, 0.032, 0.037), "Roughness": 0.55},
    "CeilingOrange": {"Color": (0.888, 0.144, 0.015), "Roughness": 0.4},
    "CeilingFrosted": {"Color": (0.905, 0.922, 0.93), "Roughness": 0.5, "EmissiveStrength": 6.0},
}


def main():
    res = call("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    if res is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res!r}). Остановите игру и запустите снова.")
    assert exists("/Game/Materials/M_KitSolid"), "нет /Game/Materials/M_KitSolid: сначала tools/ue/kit_materials.py"
    call(AS, "create_folder", {"path": FOLDER})
    saved, mats = [], {}
    for name, params in ZONES.items():
        path = instance(FOLDER, name, "/Game/Materials/M_KitSolid")
        set_params(ref(path), params)
        mats["MI_" + name] = path
        saved.append(path)

    # FbxFactory без опций у инструмента: нормали из файла (острые рёбра Blender), коллизии нет.
    defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
    for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
        call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})

    files = sorted(glob.glob(os.path.join(SRC, "SM_CeilingTile*.fbx")))
    assert len(files) == 4, files
    for fbx in files:
        name = os.path.splitext(os.path.basename(fbx))[0]
        mesh_path = f"{FOLDER}/{name}"
        if "--mesh" in sys.argv and exists(mesh_path):
            call(AS, "delete", {"path": mesh_path})
        if not exists(mesh_path):
            call(SM, "import_file", {"folder_path": FOLDER, "asset_name": name, "source_file": fbx,
                                     "import_materials": False, "import_textures": False, "combine_meshes": True})
        mesh = ref(mesh_path)
        slots = call(SM, "get_material_slots", {"mesh": mesh})
        for slot in slots:
            call(SM, "set_material", {"mesh": mesh, "slot_name": slot, "material": ref(mats[slot])})
        # 120 панелей на комнату по 3–5 тыс. треугольников: Nanite (материалы непрозрачные)
        if not call(SM, "is_nanite_enabled", {"mesh": mesh}):
            call(SM, "set_nanite_enabled", {"mesh": mesh, "enabled": True})
        b = call(SM, "get_bounds", {"mesh": mesh})
        lo, hi = (tuple(round(b[k][a], 1) for a in "xyz") for k in ("min", "max"))
        print(f"{name}: от {lo} до {hi} см, слоты {slots}, "
              f"треугольников {call(SM, 'get_triangle_count', {'mesh': mesh})}, nanite {call(SM, 'is_nanite_enabled', {'mesh': mesh})}")
        saved.append(mesh_path)

    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
