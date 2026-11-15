"""Импорт мертвеца на скелете манекена: /Game/Characters/DeadMan/SK_DeadManRig (вступительная сцена у зеркала, 16.11).

    python3 tools/ue/import_dead_man_rig.py          # импортировать, если ещё нет; материалы слотов — всегда
    python3 tools/ue/import_dead_man_rig.py --mesh   # после новой выгрузки: удалить и импортировать заново

Файл готовит tools/blender/characters/dead_man_rigged.py. Материалы — уже имеющиеся MI_DeadMan_Body и MI_DeadMan_Head
(import_dead_man.py). Сделано по образцу import_old_enemy.py. Нужен открытый редактор с проектом MegaJam, не в Play.
"""
import json
import os
import sys

from import_old_enemy import AS, OB, SK, SKELETON, call, ensure_not_playing, exists, ref

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "characters", "dead-man")
FOLDER = "/Game/Characters/DeadMan"
MESH = "SK_DeadManRig"


def main():
    ensure_not_playing()
    mesh_path = f"{FOLDER}/{MESH}"
    if "--mesh" in sys.argv and exists(mesh_path):
        call(AS, "delete", {"path": mesh_path})
    if not exists(mesh_path):
        defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals"})
        for cdo in ("/Script/UnrealEd.Default__FbxSkeletalMeshImportData",
                    "/Script/UnrealEd.Default__FbxImportUI:SkeletalMeshImportData"):
            call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})
        call(SK, "import_file", {"folder_path": FOLDER, "asset_name": MESH,
                                 "source_file": os.path.join(SRC, MESH + ".fbx"), "skeleton": ref(SKELETON),
                                 "import_materials": False, "import_textures": False,
                                 "import_animations": False, "create_physics_asset": False})
    mesh = ref(mesh_path)
    slots = call(SK, "get_material_slots", {"mesh": mesh})
    for slot in slots:
        mi = f"{FOLDER}/{slot}"
        assert exists(mi), f"нет материала {mi}"
        call(SK, "set_material", {"mesh": mesh, "slot_name": slot, "material": ref(mi)})
    b = call(SK, "get_bounds", {"mesh": mesh})
    print(mesh_path, "слоты", slots, "габарит", b)
    print("saved", call(AS, "save_assets", {"asset_paths": [mesh_path]}))


if __name__ == "__main__":
    main()
