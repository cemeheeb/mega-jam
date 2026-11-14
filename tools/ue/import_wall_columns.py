"""Импорт колонок-шкафов стены в /Game/Environment/Common/WallColumns: текстуры, экземпляры материалов, 13 мешей.

    python3 tools/ue/import_wall_columns.py          # импортировать то, чего ещё нет; материалы и слоты — всегда
    python3 tools/ue/import_wall_columns.py --mesh   # после новой выгрузки: удалить меши и импортировать заново

Файлы готовит SourceArt/environment/common/wall-columns/source/export_wall_columns.py (из glb набора Singula).
Мастер-материалы — kit_materials.py (нужны M_Kit, M_KitSolid, M_KitGlass). Расставляет колонки по комнатам
tools/ue/build_rooms.py. Удаление при --mesh обнуляет меши в блюпринтах комнат: после него пересобрать комнаты.
Нужен открытый редактор с проектом MegaJam.
"""

import glob
import json
import os
import sys

from uemcp import tool

AS = "editor_toolset.toolsets.asset.AssetTools"
MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"
TX = "editor_toolset.toolsets.texture.TextureTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "environment", "common", "wall-columns")
FOLDER = "/Game/Environment/Common/WallColumns"
SHARED = "/Game/Materials"   # общие экземпляры нескольких наборов (pipeline/unreal.md)

# Однотонные материалы набора: значения из glb Singula (линейные). Огоньки светят сильнее, чем в glb:
# в Unreal с автоэкспозицией свечение 1 почти не видно.
SOLID = {
    "Indicator": (SHARED, {"Color": (0.115, 0.565, 0.584), "Roughness": 0.2, "EmissiveStrength": 3.0}),
    "CableRed": (FOLDER, {"Color": (0.527, 0.041, 0.024), "Roughness": 0.6}),
    "CableBlue": (FOLDER, {"Color": (0.027, 0.159, 0.521), "Roughness": 0.6}),
    "CableYellow": (FOLDER, {"Color": (0.807, 0.485, 0.014), "Roughness": 0.6}),
    "CableGreen": (FOLDER, {"Color": (0.048, 0.323, 0.068), "Roughness": 0.6}),
    "CableOrange": (FOLDER, {"Color": (0.888, 0.144, 0.015), "Roughness": 0.6}),
}
GLASS = {"ClearPlastic": (SHARED, {"Color": (0.8, 0.86, 0.88), "Opacity": 0.18, "Roughness": 0.05})}


def call(toolset, name, args):
    res = tool(toolset, name, args)
    if "ERROR" in res[:12]:
        raise RuntimeError(f"{name}: {res[:600]}")
    return json.loads(res).get("returnValue") if res.strip() else None


def ref(path):
    return {"refPath": f"{path}.{path.rsplit('/', 1)[1]}"}


def exists(path):
    return call(AS, "exists", {"path": path})


def texture(name, masks=False):
    path = f"{FOLDER}/{name}"
    if not exists(path):
        call(TX, "import_file", {"folder_path": FOLDER, "asset_name": name, "source_file": os.path.join(SRC, name + ".png")})
    values = {"SRGB": False, "CompressionSettings": "TC_Masks"} if masks else {"SRGB": True, "CompressionSettings": "TC_Default"}
    call(OB, "set_properties", {"instance": ref(path), "values": json.dumps(values)})
    return ref(path)


def instance(folder, name, parent):
    path = f"{folder}/MI_{name}"
    if not exists(path):
        call(MI, "create", {"folder_path": folder, "asset_name": f"MI_{name}", "parent": ref(parent)})
    return path


def set_params(mi, params):
    for k, v in params.items():
        if isinstance(v, tuple):
            call(MI, "set_vector_parameter", {"instance": mi, "name": k, "value": {"r": v[0], "g": v[1], "b": v[2], "a": 1.0}})
        else:
            call(MI, "set_scalar_parameter", {"instance": mi, "name": k, "value": v})


def main():
    call(AS, "create_folder", {"path": FOLDER})
    for m in ("M_Kit", "M_KitSolid", "M_KitGlass"):
        assert exists(f"/Game/Materials/{m}"), f"нет /Game/Materials/{m}: сначала tools/ue/kit_materials.py"
    saved = []

    mats = {}
    base = texture("T_WallColumns_BaseColor")
    orm = texture("T_WallColumns_ORM", masks=True)
    path = instance(FOLDER, "WallColumns", "/Game/Materials/M_Kit")
    call(MI, "set_texture_parameter", {"instance": ref(path), "name": "BaseColor", "value": base})
    call(MI, "set_texture_parameter", {"instance": ref(path), "name": "ORM", "value": orm})
    mats["MI_WallColumns"] = path
    saved += [f"{FOLDER}/T_WallColumns_BaseColor", f"{FOLDER}/T_WallColumns_ORM", path]
    for table, parent in ((SOLID, "/Game/Materials/M_KitSolid"), (GLASS, "/Game/Materials/M_KitGlass")):
        for name, (folder, params) in table.items():
            path = instance(folder, name, parent)
            set_params(ref(path), params)
            mats["MI_" + name] = path
            saved.append(path)

    # FbxFactory без опций у инструмента: нормали из файла (острые рёбра Blender), коллизия — коробки UCX из файла.
    defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
    for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
        call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})

    files = sorted(glob.glob(os.path.join(SRC, "SM_*.fbx")))
    assert len(files) == 13, files
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
        glass = "MI_ClearPlastic" in slots
        if glass and call(SM, "is_nanite_enabled", {"mesh": mesh}):
            call(SM, "set_nanite_enabled", {"mesh": mesh, "enabled": False})   # Nanite не рисует прозрачное
        b = call(SM, "get_bounds", {"mesh": mesh})
        lo, hi = (tuple(round(b[k][a], 1) for a in "xyz") for k in ("min", "max"))
        print(f"{name}: от {lo} до {hi} см, слоты {slots}, "
              f"треугольников {call(SM, 'get_triangle_count', {'mesh': mesh})}, nanite {call(SM, 'is_nanite_enabled', {'mesh': mesh})}")
        saved.append(mesh_path)

    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
