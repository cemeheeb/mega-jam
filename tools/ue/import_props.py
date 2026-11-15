"""Импорт моделей Tripo для заглушек игры (15.11): текстуры, экземпляр материала и меши карточки Студии.

    python3 tools/ue/import_props.py                  # все карточки из списка PROPS: то, чего ещё нет
    python3 tools/ue/import_props.py coolant-valve    # только названные (по имени папки карточки)
    python3 tools/ue/import_props.py --mesh           # после новой выгрузки: удалить меши и импортировать заново
    python3 tools/ue/import_props.py --tex            # то же для текстур

Файлы готовит tools/blender/props/tripo_props.py: в папке карточки SourceArt/<карточка> лежат SM_*.fbx
(сантиметры), T_<Материал>_BaseColor.png и T_<Материал>_ORM.png. Папка в игре — как показывает Студия:
/Game/<путь карточки в ПаскальКейс> (items/coolant-valve -> /Game/Items/CoolantValve). Материал — MI_<Материал>
из M_Kit; все меши карточки получают его в свой слот. Коллизия — только выпуклые UCX из файла (створка шлюза,
мебель второй партии).
Нужен открытый редактор с проектом MegaJam, не в Play.
"""

import glob
import os
import re
import sys

from import_kit import material
from import_wall_columns import AS, OB, SM, call, exists, ref

import json

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART = os.path.join(PROJECT, "SourceArt")

PROPS = [
    "items/coolant-valve",
    "items/circuit-board",
    "environment/common/space-suit-helmet",
    "environment/common/space-suit",
    "environment/common/fungus-clusters",
    "environment/common/airlock-door",
    "characters/maintenance-robot",
    "items/sealant-can", "items/voice-recorder", "items/rubber-duck", "items/ration-tin", "items/pressure-gauge",
    "items/power-cell", "items/pipe-wrench", "items/duct-tape", "items/paper-note", "items/gyroscope", "items/fuse",
    "items/family-photo", "items/dog-tag", "items/data-cartridge",
    # вторая партия (15.11): мебель комнат вместо серых коробок build_rooms.py
    "environment/engine/warp-core", "environment/living/space-toilet", "environment/common/dining-set",
    "environment/cargo/cargo-crates", "environment/medbay/medbay-kit",
    "environment/medbay/diagnostic-capsule",
    # третья партия (15.11, ночь): последние серые коробки мебели
    "environment/medbay/medical-bed", "environment/cargo/cargo-shelf", "environment/common/control-cabinet",
    "environment/common/storage-tank", "environment/lab/cage-rack", "environment/living/crew-locker",
    "environment/mess/food-dispenser", "environment/engine/core-pylon",
    # карта капитана (15.11, вечер): не Tripo, модель и текстуры — tools/blender/props/captains_card.py
    "items/captains-card",
]

# сила свечения (EmissiveStrength) у карточек с картой T_*_Emissive.png: колонна ядра светит, индикатор унитаза тлеет
GLOW = {"environment/engine/warp-core": 4.0, "environment/living/space-toilet": 2.0,
        "environment/medbay/diagnostic-capsule": 1.5, "items/captains-card": 2.0,
        "environment/common/control-cabinet": 2.0, "environment/mess/food-dispenser": 1.5}


def pascal(name):
    return "".join(w[0].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", name) if w)


def import_card(card, saved):
    src = os.path.join(ART, card)
    folder = "/Game/" + "/".join(pascal(p) for p in card.split("/"))
    call(AS, "create_folder", {"path": folder})
    bases = sorted(glob.glob(os.path.join(src, "T_*_BaseColor.png")))
    assert len(bases) == 1, f"{card}: ожидалась одна текстура T_*_BaseColor.png, найдено {len(bases)}"
    mat = os.path.basename(bases[0])[2:-len("_BaseColor.png")]
    mi = material(src, folder, mat, GLOW.get(card), saved)
    for fbx in sorted(glob.glob(os.path.join(src, "SM_*.fbx"))):
        name = os.path.splitext(os.path.basename(fbx))[0]
        mesh_path = f"{folder}/{name}"
        if "--mesh" in sys.argv and exists(mesh_path):
            call(AS, "delete", {"path": mesh_path})
        if not exists(mesh_path):
            call(SM, "import_file", {"folder_path": folder, "asset_name": name, "source_file": fbx,
                                     "import_materials": False, "import_textures": False, "combine_meshes": True})
        mesh = ref(mesh_path)
        slots = call(SM, "get_material_slots", {"mesh": mesh})
        for slot in slots:
            call(SM, "set_material", {"mesh": mesh, "slot_name": slot, "material": ref(mi)})
        b = call(SM, "get_bounds", {"mesh": mesh})
        lo, hi = (tuple(round(b[k][a], 1) for a in "xyz") for k in ("min", "max"))
        print(f"{mesh_path}: от {lo} до {hi} см, слоты {slots}, "
              f"треугольников {call(SM, 'get_triangle_count', {'mesh': mesh})}, nanite {call(SM, 'is_nanite_enabled', {'mesh': mesh})}")
        saved.append(mesh_path)


def main():
    res = call("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    if res is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res!r}). Остановите игру и запустите снова.")
    assert exists("/Game/Materials/M_Kit"), "нет /Game/Materials/M_Kit: сначала tools/ue/kit_materials.py"
    # FbxFactory без опций у инструмента: нормали из файла, коллизия — только коробки UCX из файла
    defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
    for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
        call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    saved = []
    for card in PROPS:
        if not names or card.split("/")[-1] in names:
            import_card(card, saved)
    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
