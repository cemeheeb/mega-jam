"""Импорт мертвеца в /Game/Characters/DeadMan: текстуры, MI_DeadMan_Body/Head, по статичному мешу на каждую позу.

    python3 tools/ue/import_dead_man.py          # импортировать то, чего ещё нет; материалы и слоты — всегда
    python3 tools/ue/import_dead_man.py --mesh   # после новой выгрузки: удалить меши и импортировать заново
    python3 tools/ue/import_dead_man.py --mesh SM_DeadMan_Floor3   # заново только названные позы

Файлы готовит SourceArt/characters/dead-man/source/export_dead_man.py: SM_DeadMan_<Поза>.fbx в сантиметрах,
начало координат — опора позы (SourceArt/characters/dead-man/asset.yml): пол под тазом, стена или край стола
в −Y Unreal (+Y Blender). Мастер-материалы — kit_materials.py. Коллизии у тел нет: игрок проходит сквозь них.
Нужен открытый редактор с проектом MegaJam, не в режиме Play.
"""

import glob
import json
import os
import sys

from import_kit import material
from uemcp import tool

AS = "editor_toolset.toolsets.asset.AssetTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "characters", "dead-man")
FOLDER = "/Game/Characters/DeadMan"
POSES = 15


def call(toolset, name, args):
    res = tool(toolset, name, args)
    if "ERROR" in res[:12]:
        raise RuntimeError(f"{name}: {res[:600]}")
    return json.loads(res).get("returnValue") if res.strip() else None


def ref(path):
    return {"refPath": f"{path}.{path.rsplit('/', 1)[1]}"}


def exists(path):
    return call(AS, "exists", {"path": path})


def ensure_not_playing():
    res = tool("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    try:
        playing = json.loads(res).get("returnValue")
    except ValueError:
        playing = None
    if playing is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res[:120]!r}). Остановите игру и запустите импорт снова.")


def main():
    ensure_not_playing()
    assert exists("/Game/Materials/M_Kit"), "нет /Game/Materials/M_Kit: сначала tools/ue/kit_materials.py"
    call(AS, "create_folder", {"path": FOLDER})
    saved = []
    mats = {f"MI_{n}": material(SRC, FOLDER, n, None, saved) for n in ("DeadMan_Body", "DeadMan_Head")}

    # FbxFactory без опций у инструмента: нормали из файла; без автоколлизии (UCX в файлах нет — коллизии не будет).
    defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
    for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
        call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})

    files = sorted(glob.glob(os.path.join(SRC, "SM_DeadMan_*.fbx")))
    assert len(files) == POSES, files
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    for fbx in files:
        name = os.path.splitext(os.path.basename(fbx))[0]
        if only and name not in only:
            continue
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
        b = call(SM, "get_bounds", {"mesh": mesh})
        lo, hi = (tuple(round(b[k][a]) for a in "xyz") for k in ("min", "max"))
        print(f"{name}: от {lo} до {hi} см, слоты {slots}, треугольников {call(SM, 'get_triangle_count', {'mesh': mesh})}")
        saved.append(mesh_path)

    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
