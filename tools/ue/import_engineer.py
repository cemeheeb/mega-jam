"""Импорт героя в /Game/Characters/Engineer: текстуры, экземпляры материалов, SK_Engineer на скелете манекена.

    python3 tools/ue/import_engineer.py          # импортировать то, чего ещё нет; материалы и слоты — всегда
    python3 tools/ue/import_engineer.py --mesh   # после новой выгрузки: удалить SK_Engineer и импортировать заново

Файлы готовит SourceArt/characters/engineer/source/export_engineer.py. Мастер-материалы — kit_materials.py.
Импорт MCP не перезаписывает существующий ассет, поэтому текстуру после замены файла удалить в редакторе вручную.
Удаление при --mesh обнуляет меш у акторов уровней, которые на него ссылались (проверочный уровень героя
/Game/Developers/cemeheeb/Lvl_CharacterTest): после импорта вернуть им SK_Engineer и сохранить.
В игре ссылка не теряется: меш игроку ставит ARunDirector по пути из кода.
Нужен открытый редактор с проектом MegaJam.
"""

import json
import os
import sys

from uemcp import tool

AS = "editor_toolset.toolsets.asset.AssetTools"
MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SK = "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools"
TX = "editor_toolset.toolsets.texture.TextureTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "characters", "engineer")
FOLDER = "/Game/Characters/Engineer"
MESH = "SK_Engineer"
SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"  # в шаблоне это скелет, меши — SKM_Manny/Quinn_Simple

# Слот (имя материала в Blender с приставкой MI_) -> мастер и параметры.
# Цвета и шероховатость однотонных материалов — из engineer.blend (линейные, как в Blender).
TEXTURED = ["Engineer_Body", "Engineer_Head", "Engineer_Teeth"]
SOLID = {
    "Engineer_Mouth": {"Color": (0.05, 0.007, 0.007), "Roughness": 0.8},
    "Engineer_Tongue": {"Color": (0.3, 0.065, 0.06), "Roughness": 0.45},
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


def texture(name, masks=False):
    path = f"{FOLDER}/{name}"
    if not exists(path):
        call(TX, "import_file", {"folder_path": FOLDER, "asset_name": name,
                                 "source_file": os.path.join(SRC, name + ".png")})
    values = {"SRGB": False, "CompressionSettings": "TC_Masks"} if masks else {"SRGB": True, "CompressionSettings": "TC_Default"}
    call(OB, "set_properties", {"instance": ref(path), "values": json.dumps(values)})
    return ref(path)


def instance(name, parent):
    path = f"{FOLDER}/MI_{name}"
    if not exists(path):
        call(MI, "create", {"folder_path": FOLDER, "asset_name": f"MI_{name}", "parent": ref(parent)})
    return ref(path)


def main():
    call(AS, "create_folder", {"path": FOLDER})
    saved = []

    mats = {}
    for n in TEXTURED:
        base = texture(f"T_{n}_BaseColor")
        orm = texture(f"T_{n}_ORM", masks=True)
        mi = instance(n, "/Game/Materials/M_Kit")
        call(MI, "set_texture_parameter", {"instance": mi, "name": "BaseColor", "value": base})
        call(MI, "set_texture_parameter", {"instance": mi, "name": "ORM", "value": orm})
        mats[n] = mi
        saved += [f"{FOLDER}/T_{n}_BaseColor", f"{FOLDER}/T_{n}_ORM", f"{FOLDER}/MI_{n}"]
    for n, p in SOLID.items():
        mi = instance(n, "/Game/Materials/M_KitSolid")
        r, g, b = p["Color"]
        call(MI, "set_vector_parameter", {"instance": mi, "name": "Color", "value": {"r": r, "g": g, "b": b, "a": 1.0}})
        call(MI, "set_scalar_parameter", {"instance": mi, "name": "Roughness", "value": p["Roughness"]})
        mats[n] = mi
        saved.append(f"{FOLDER}/MI_{n}")

    mesh_path = f"{FOLDER}/{MESH}"
    if "--mesh" in sys.argv and exists(mesh_path):
        call(AS, "delete", {"path": mesh_path})
    if not exists(mesh_path):
        # import_file идёт через старый FbxFactory, а у него по умолчанию формы лица не грузятся,
        # а нормали пересчитываются. Других опций у инструмента нет, поэтому правим объекты настроек
        # по умолчанию; после перезапуска редактора они сбрасываются, поэтому — при каждом импорте.
        defaults = json.dumps({"bImportMorphTargets": True, "normalImportMethod": "FBXNIM_ImportNormals"})
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
        call(SK, "set_material", {"mesh": mesh, "slot_name": slot, "material": mats[slot.removeprefix("MI_")]})
    saved.append(mesh_path)

    b = call(SK, "get_bounds", {"mesh": mesh})
    print("slots", slots)
    print("morph targets", len(call(SK, "get_morph_target_names", {"mesh": mesh}) or []))
    print("height cm", round(b["boxExtent"]["z"] * 2, 1), "width cm", round(b["boxExtent"]["x"] * 2, 1))
    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
