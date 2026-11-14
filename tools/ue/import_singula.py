"""Импорт наборов реквизита из Singula в /Game/Environment/...: текстуры, экземпляр материала набора, меши.

    python3 tools/ue/import_singula.py                 # все наборы: импортировать то, чего ещё нет; материалы — всегда
    python3 tools/ue/import_singula.py common/lamps    # один набор
    python3 tools/ue/import_singula.py --mesh ...      # после новой выгрузки: удалить меши набора и импортировать заново

Файлы готовит tools/blender/export_singula.py (SourceArt/environment/<набор>/SM_*.fbx, T_*.png).
Колонки стены — свой импорт (import_wall_columns.py). Мастер-материал — M_Kit (kit_materials.py).
Удаление при --mesh обнуляет меши в блюпринтах комнат: после него пересобрать комнаты (build_rooms.py).
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
SRC = os.path.join(PROJECT, "SourceArt", "environment")

# набор -> сила свечения карты Emissive (у наборов без неё не задаётся). В Unreal с автоэкспозицией
# свечение 1 почти не видно, как и у огоньков колонок.
SETS = {
    "common/safety-equipment": None,
    "common/lamps": 6.0,
    "common/ventilation": None,
    "common/flexible-duct": None,
    "common/handrails": None,
    "common/door-hatch-controls": 3.0,
    "bridge/acceleration-couch": None,
    "bridge/command-console-parts": 3.0,
    "bridge/control-console-parts": 3.0,
    "bridge/crew-items": None,
    "welding-gun": None,
}
TEXTURE = {   # суффикс -> (параметр M_Kit, свойства текстуры)
    "BaseColor": ("BaseColor", {"SRGB": True, "CompressionSettings": "TC_Default"}),
    "ORM": ("ORM", {"SRGB": False, "CompressionSettings": "TC_Masks"}),
    # нормали Singula — для OpenGL (пресет godot ArmorPaint): зелёный канал перевернуть
    "Normal": ("Normal", {"SRGB": False, "CompressionSettings": "TC_Normalmap", "bFlipGreenChannel": True}),
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


def import_set(set_path, glow, remesh):
    src = os.path.join(SRC, set_path)
    folder = folder_of(set_path)
    name = camel(os.path.basename(set_path))
    call(AS, "create_folder", {"path": folder})
    saved = []

    mi = f"{folder}/MI_{name}"
    if not exists(mi):
        call(MI, "create", {"folder_path": folder, "asset_name": f"MI_{name}", "parent": ref("/Game/Materials/M_Kit")})
    for suffix, (param, props) in TEXTURE.items():
        tex = f"T_{name}_{suffix}"
        png = os.path.join(src, tex + ".png")
        if not os.path.exists(png):
            continue
        path = f"{folder}/{tex}"
        if not exists(path):
            call(TX, "import_file", {"folder_path": folder, "asset_name": tex, "source_file": png})
        call(OB, "set_properties", {"instance": ref(path), "values": json.dumps(props)})
        call(MI, "set_texture_parameter", {"instance": ref(mi), "name": param, "value": ref(path)})
        saved.append(path)
    if glow is not None:
        call(MI, "set_scalar_parameter", {"instance": ref(mi), "name": "EmissiveStrength", "value": glow})
    saved.append(mi)

    files = sorted(glob.glob(os.path.join(src, "SM_*.fbx")))
    assert files, src
    for fbx in files:
        mesh_name = os.path.splitext(os.path.basename(fbx))[0]
        mesh_path = f"{folder}/{mesh_name}"
        if remesh and exists(mesh_path):
            call(AS, "delete", {"path": mesh_path})
        if not exists(mesh_path):
            call(SM, "import_file", {"folder_path": folder, "asset_name": mesh_name, "source_file": fbx,
                                     "import_materials": False, "import_textures": False, "combine_meshes": True})
        mesh = ref(mesh_path)
        slots = call(SM, "get_material_slots", {"mesh": mesh})
        assert slots == [f"MI_{name}"], (mesh_name, slots)
        call(SM, "set_material", {"mesh": mesh, "slot_name": slots[0], "material": ref(mi)})
        b = call(SM, "get_bounds", {"mesh": mesh})
        lo, hi = (tuple(round(b[k][a], 1) for a in "xyz") for k in ("min", "max"))
        print(f"  {mesh_name}: от {lo} до {hi} см, треугольников {call(SM, 'get_triangle_count', {'mesh': mesh})}")
        saved.append(mesh_path)
    print("saved", set_path, call(AS, "save_assets", {"asset_paths": saved}))


def main():
    assert exists("/Game/Materials/M_Kit"), "нет /Game/Materials/M_Kit: сначала tools/ue/kit_materials.py"
    # FbxFactory без опций у инструмента: нормали из файла, коллизия — коробки UCX из файла
    defaults = json.dumps({"normalImportMethod": "FBXNIM_ImportNormals", "bAutoGenerateCollision": False})
    for cdo in ("/Script/UnrealEd.Default__FbxStaticMeshImportData",
                "/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData"):
        call(OB, "set_properties", {"instance": {"refPath": cdo}, "values": defaults})
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for set_path in (args or list(SETS)):
        print("set", set_path, "->", folder_of(set_path))
        import_set(set_path, SETS[set_path], "--mesh" in sys.argv)


if __name__ == "__main__":
    main()
