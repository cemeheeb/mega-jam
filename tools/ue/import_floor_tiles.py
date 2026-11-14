"""Плитка пола: текстуры, материал M_FloorTiles и экземпляр MI_FloorTiles (SourceArt/environment/common/floor-tiles).

    python3 tools/ue/import_floor_tiles.py            # импортировать то, чего нет; параметры экземпляра — всегда
    python3 tools/ue/import_floor_tiles.py --tex      # после новой выгрузки текстур: удалить их и импортировать заново
    python3 tools/ue/import_floor_tiles.py --master   # собрать граф M_FloorTiles заново на месте

Текстуры делает SourceArt/environment/common/floor-tiles/source/make_floor_tiles.py: одна панель 75 × 75 см на
картинку. Пол комнаты — коробка без нужной развёртки, поэтому M_FloorTiles (/Game/Materials) берёт координаты
текстуры из мира: (положение пикселя − положение актёра) / TileSize по X и Y. Точка привязки — центр комнаты:
видимая часть пола 9 × 7,5 м — ровно 12 × 10 плиток, так что швы идут от лица колонок и продолжают швы потолка;
пол тамбура (тот же актёр) шириной 6 плиток начинается в 7 / 6 плитках от центра, его швы тоже ложатся на края.
Пол ставит на комнаты ARunRoom::BeginPlay (по имени компонента: Floor и <сторона>_Airlock_Floor), а
build_rooms.py красит им пол при следующей пересборке.
Нужен открытый редактор с проектом MegaJam, не в Play.
"""

import json
import os
import sys

from kit_materials import AS, MT, TX, add, call, fresh_material, link, out, ref, set_props

MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "environment", "common", "floor-tiles")
FOLDER = "/Game/Environment/Common/FloorTiles"
MASTER = "/Game/Materials/M_FloorTiles"
INSTANCE = f"{FOLDER}/MI_FloorTiles"
TILE = 75.0


def build_master(base, orm):
    m = fresh_material("M_FloorTiles")
    wp = add(m, "WorldPosition", -1500, 0)
    op = add(m, "ActorPositionWS", -1500, 150)
    rel = add(m, "Subtract", -1300, 50)
    link(wp, "", rel, "A")
    link(op, "", rel, "B")
    xy = add(m, "ComponentMask", -1150, 50, R=True, G=True, B=False, A=False)
    link(rel, "", xy, "")
    size = add(m, "ScalarParameter", -1150, 200, parameterName="TileSize", defaultValue=TILE, sortPriority=2)
    uv = add(m, "Divide", -1000, 100)
    link(xy, "", uv, "A")
    link(size, "", uv, "B")
    tb = add(m, "TextureSampleParameter2D", -700, -150, parameterName="BaseColor", samplerType="SAMPLERTYPE_Color",
             texture=base, sortPriority=0)
    to = add(m, "TextureSampleParameter2D", -700, 200, parameterName="ORM", samplerType="SAMPLERTYPE_Masks",
             texture=orm, sortPriority=1)
    link(uv, "", tb, "UVs")
    link(uv, "", to, "UVs")
    out(tb, "RGB", "MP_BaseColor")
    out(to, "R", "MP_AmbientOcclusion")
    out(to, "G", "MP_Roughness")
    out(to, "B", "MP_Metallic")
    set_props(m, {"blendMode": "BLEND_Opaque"})
    call(MT, "recompile", {"material_or_function": m})
    call(MT, "layout_expressions", {"material_or_function": m})
    return m


def texture(name, masks):
    path = f"{FOLDER}/{name}"
    if "--tex" in sys.argv and call(AS, "exists", {"path": path}):
        call(AS, "delete", {"path": path})
    if not call(AS, "exists", {"path": path}):
        call(TX, "import_file", {"folder_path": FOLDER, "asset_name": name, "source_file": os.path.join(SRC, name + ".png")})
    props = {"SRGB": False, "CompressionSettings": "TC_Masks"} if masks else {"SRGB": True, "CompressionSettings": "TC_Default"}
    set_props(ref(path), props)
    return ref(path), path


def main():
    res = call("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    if res is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res!r}). Остановите игру и запустите снова.")
    call(AS, "create_folder", {"path": FOLDER})
    base, base_path = texture("T_FloorTiles_BaseColor", False)
    orm, orm_path = texture("T_FloorTiles_ORM", True)
    if "--master" in sys.argv or not call(AS, "exists", {"path": MASTER}):
        build_master(base, orm)
    if not call(AS, "exists", {"path": INSTANCE}):
        call(MI, "create", {"folder_path": FOLDER, "asset_name": "MI_FloorTiles", "parent": ref(MASTER)})
    mi = ref(INSTANCE)
    call(MI, "set_texture_parameter", {"instance": mi, "name": "BaseColor", "value": base})
    call(MI, "set_texture_parameter", {"instance": mi, "name": "ORM", "value": orm})
    call(MI, "set_scalar_parameter", {"instance": mi, "name": "TileSize", "value": TILE})
    print("saved", call(AS, "save_assets", {"asset_paths": [base_path, orm_path, MASTER, INSTANCE]}))


if __name__ == "__main__":
    main()
