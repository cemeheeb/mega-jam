"""Импорт серверной стойки в /Game/Environment/Computer/ServerRack: однотонные материалы зон и меш.

    python3 tools/ue/import_server_rack.py          # импортировать то, чего ещё нет; материалы и слоты — всегда
    python3 tools/ue/import_server_rack.py --mesh   # после новой выгрузки: удалить меш и импортировать заново

Файлы готовит SourceArt/environment/computer/server-rack/source/export_server_rack.py: SM_ServerRack.fbx со слотом
на зону (MI_ServerRack<Зона>) и zones.json с цветами зон из blend (линейные). Текстур пока нет (15.11): модель на
шаге 2 pipeline/kit.md, автор попросил поставить её в игру, как спальную капсулу (import_sleep_capsule.py). Зоны —
экземпляры M_KitSolid; шероховатость, металл и свечение — из таблицы ниже. Когда будут текстуры, меш выгружается
заново с одним слотом, а этот скрипт заменяется обычным импортом набора (import_kit.py).
Коллизия — коробки UCX из файла: корпус, крышка, ящики с ручками.
Удаление при --mesh обнуляет меш в блюпринте вычислительного центра: после него пересобрать его
(python3 tools/ue/build_rooms.py Computer).
Нужен открытый редактор с проектом MegaJam, не в Play.
"""

import json
import os
import sys

from import_wall_columns import call, exists, instance, ref, set_params

AS = "editor_toolset.toolsets.asset.AssetTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "environment", "computer", "server-rack")
FOLDER = "/Game/Environment/Computer/ServerRack"
NAME = "SM_ServerRack"

# зона -> параметры M_KitSolid сверх цвета: краска корпуса и полосы, графитовый пластик ящиков и ручек,
# перфорированный металл решёток, светящиеся полосы рядов и огоньки статуса. Полосам свой цвет, глубже цвета
# осмотра из blend: светлая бирюза при свете комнаты выходила почти белой (снимок 15.11), насыщенная читается
SURFACE = {
    "ServerRackWhite": {"Roughness": 0.42},
    "ServerRackOrange": {"Roughness": 0.4},
    "ServerRackPlastic": {"Roughness": 0.5},
    "ServerRackGrille": {"Roughness": 0.55, "Metallic": 0.6},
    "ServerRackTeal": {"Color": (0.02, 0.3, 0.34), "Roughness": 0.3, "EmissiveStrength": 2.0},
    "ServerRackGlass": {"Roughness": 0.2, "EmissiveStrength": 2.0},
}


def main():
    res = call("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    if res is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res!r}). Остановите игру и запустите снова.")
    assert exists("/Game/Materials/M_KitSolid"), "нет /Game/Materials/M_KitSolid: сначала tools/ue/kit_materials.py"
    with open(os.path.join(SRC, "zones.json")) as f:
        colours = json.load(f)
    call(AS, "create_folder", {"path": FOLDER})
    saved, mats = [], {}
    for name, colour in colours.items():
        path = instance(FOLDER, name, "/Game/Materials/M_KitSolid")
        set_params(ref(path), {"Color": tuple(colour), **SURFACE[name]})
        mats["MI_" + name] = path
        saved.append(path)

    # FbxFactory без опций у инструмента: нормали из файла (острые рёбра Blender), коллизия — только UCX из файла
    defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
    for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
        call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})

    mesh_path = f"{FOLDER}/{NAME}"
    if "--mesh" in sys.argv and exists(mesh_path):
        call(AS, "delete", {"path": mesh_path})
    if not exists(mesh_path):
        call(SM, "import_file", {"folder_path": FOLDER, "asset_name": NAME, "source_file": os.path.join(SRC, NAME + ".fbx"),
                                 "import_materials": False, "import_textures": False, "combine_meshes": True})
    mesh = ref(mesh_path)
    slots = call(SM, "get_material_slots", {"mesh": mesh})
    assert slots and all(s in mats for s in slots), (slots, list(mats))
    for slot in slots:
        call(SM, "set_material", {"mesh": mesh, "slot_name": slot, "material": ref(mats[slot])})
    b = call(SM, "get_bounds", {"mesh": mesh})
    lo, hi = (tuple(round(b[k][a], 1) for a in "xyz") for k in ("min", "max"))
    print(f"{NAME}: от {lo} до {hi} см, слоты {slots}, треугольников {call(SM, 'get_triangle_count', {'mesh': mesh})}")
    saved.append(mesh_path)
    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
