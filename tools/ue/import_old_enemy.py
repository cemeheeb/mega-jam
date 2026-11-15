"""Импорт старика в /Game/Characters/OldEnemy: текстуры, MI_OldEnemy_Body/Head, SK_OldEnemy на скелете манекена.

    python3 tools/ue/import_old_enemy.py          # импортировать то, чего ещё нет; материалы и слоты — всегда
    python3 tools/ue/import_old_enemy.py --mesh   # после новой выгрузки: удалить SK_OldEnemy и импортировать заново

Файлы готовит SourceArt/characters/old-enemy/source/export_old_enemy.py. Мастер-материал — M_Kit (kit_materials.py).
Сделано по образцу import_engineer.py: меш встаёт на скелет SK_Mannequin, анимации манекена играют на нём без перенастройки.
Импорт MCP не перезаписывает существующий ассет, поэтому текстуру после замены файла удалить в редакторе вручную.
Нужен открытый редактор с проектом MegaJam, не в режиме Play.
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
SRC = os.path.join(PROJECT, "SourceArt", "characters", "old-enemy")
FOLDER = "/Game/Characters/OldEnemy"
MESH = "SK_OldEnemy"
SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"  # в шаблоне это скелет, меши — SKM_Manny/Quinn_Simple
TEXTURED = ["OldEnemy_Body", "OldEnemy_Head"]


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
    ensure_not_playing()
    assert exists("/Game/Materials/M_Kit"), "нет /Game/Materials/M_Kit: сначала tools/ue/kit_materials.py"
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

    mesh_path = f"{FOLDER}/{MESH}"
    if "--mesh" in sys.argv and exists(mesh_path):
        call(AS, "delete", {"path": mesh_path})
    if not exists(mesh_path):
        # FbxFactory без опций у инструмента: нормали из файла (настройки по умолчанию сбрасываются
        # после перезапуска редактора, поэтому — при каждом импорте), см. import_engineer.py.
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
        call(SK, "set_material", {"mesh": mesh, "slot_name": slot, "material": mats[slot.removeprefix("MI_")]})
    saved.append(mesh_path)

    b = call(SK, "get_bounds", {"mesh": mesh})
    print("slots", slots)
    print("bones", len(call(SK, "get_bone_names", {"mesh": mesh}) or []))
    print("height cm", round(b["boxExtent"]["z"] * 2, 1), "width cm", round(b["boxExtent"]["x"] * 2, 1),
          "depth cm", round(b["boxExtent"]["y"] * 2, 1))
    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
