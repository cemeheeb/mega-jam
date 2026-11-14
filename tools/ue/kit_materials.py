"""Мастер-материалы проекта в /Game/Materials (pipeline/unreal.md, «Мастер-материал M_Kit»).

    python3 tools/ue/kit_materials.py

M_Kit — текстурный (BaseColor, ORM, Normal, Emissive), M_KitSolid — однотонный, M_KitGlass — прозрачный
(первым понадобился колонкам стены: оргстекло ниши и стойки). Скрипт создаёт только те мастер-материалы,
которых ещё нет; готовые не трогает (см. main).
Нужен открытый редактор с проектом MegaJam.
"""

import json
import os
import struct
import zlib

from uemcp import tool

AS = "editor_toolset.toolsets.asset.AssetTools"
MT = "editor_toolset.toolsets.material.MaterialTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
TX = "editor_toolset.toolsets.texture.TextureTools"

FOLDER = "/Game/Materials"
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ORM = "T_Kit_DefaultORM"  # однотонная ORM для значения по умолчанию: AO 1, шероховатость 0,5, металл 0


def call(toolset, name, args):
    res = tool(toolset, name, args)
    if "ERROR" in res[:12]:
        raise RuntimeError(f"{name}: {res[:600]}")
    return json.loads(res).get("returnValue") if res.strip() else None


def ref(path):
    return {"refPath": f"{path}.{path.rsplit('/', 1)[1]}"}


def png_rgb(path, w, h, rgb):
    """Маленький PNG 8 бит RGB одного цвета без сторонних библиотек."""
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def set_props(obj, values):
    call(OB, "set_properties", {"instance": obj, "values": json.dumps(values)})


def ensure_default_orm():
    path = f"{FOLDER}/{DEFAULT_ORM}"
    if not call(AS, "exists", {"path": path}):
        src = os.path.join(PROJECT, "Saved", "KitDefaults", DEFAULT_ORM + ".png")
        png_rgb(src, 4, 4, (255, 128, 0))
        call(TX, "import_file", {"folder_path": FOLDER, "asset_name": DEFAULT_ORM, "source_file": src})
    set_props(ref(path), {"SRGB": False, "CompressionSettings": "TC_Masks"})
    return ref(path)


def fresh_material(name):
    """Пустой граф: создать материал или убрать все узлы у существующего."""
    path = f"{FOLDER}/{name}"
    if call(AS, "exists", {"path": path}):
        m = ref(path)
        for e in call(MT, "get_expressions", {"material_or_function": m}) or []:
            call(MT, "delete_expression", {"material_or_function": m, "expression": e})
        return m
    return call(MT, "create_material", {"folder_path": FOLDER, "asset_name": name})


def add(m, cls, x, y, **props):
    e = call(MT, "add_expression", {"material_or_function": m,
                                    "expression_class": {"refPath": f"/Script/Engine.MaterialExpression{cls}"},
                                    "x": x, "y": y})
    if props:
        set_props(e, props)
    return e


def out(e, pin, prop):
    call(MT, "connect_to_output", {"expression": e, "output_name": pin, "material_property": prop})


def link(a, pin, b, inp):
    call(MT, "connect_expressions", {"from_expression": a, "from_output_name": pin, "to_expression": b, "to_input_name": inp})


USAGE = {"bUsedWithSkeletalMesh": True, "bUsedWithMorphTargets": True}


def build_kit(default_orm):
    m = fresh_material("M_Kit")
    base = add(m, "TextureSampleParameter2D", -700, -300, parameterName="BaseColor", samplerType="SAMPLERTYPE_Color",
               texture={"refPath": "/Engine/EngineResources/DefaultTexture.DefaultTexture"}, sortPriority=0)
    orm = add(m, "TextureSampleParameter2D", -700, 0, parameterName="ORM", samplerType="SAMPLERTYPE_Masks",
              texture=default_orm, sortPriority=1)
    nor = add(m, "TextureSampleParameter2D", -700, 300, parameterName="Normal", samplerType="SAMPLERTYPE_Normal",
              texture={"refPath": "/Engine/EngineMaterials/FlatNormal.FlatNormal"}, sortPriority=2)
    emi = add(m, "TextureSampleParameter2D", -700, 600, parameterName="Emissive", samplerType="SAMPLERTYPE_Color",
              texture={"refPath": "/Engine/EngineResources/Black.Black"}, sortPriority=3)
    strength = add(m, "ScalarParameter", -700, 900, parameterName="EmissiveStrength", defaultValue=1.0, sortPriority=4)
    mul = add(m, "Multiply", -300, 650)
    out(base, "RGB", "MP_BaseColor")
    out(base, "A", "MP_OpacityMask")
    out(orm, "R", "MP_AmbientOcclusion")
    out(orm, "G", "MP_Roughness")
    out(orm, "B", "MP_Metallic")
    out(nor, "RGB", "MP_Normal")
    link(emi, "RGB", mul, "A")
    link(strength, "", mul, "B")
    out(mul, "", "MP_EmissiveColor")
    set_props(m, {"twoSided": True, "blendMode": "BLEND_Opaque", **USAGE})
    call(MT, "recompile", {"material_or_function": m})
    return m


def build_kit_solid():
    m = fresh_material("M_KitSolid")
    color = add(m, "VectorParameter", -700, -200, parameterName="Color",
                defaultValue={"r": 0.5, "g": 0.5, "b": 0.5, "a": 1.0}, sortPriority=0)
    rough = add(m, "ScalarParameter", -700, 100, parameterName="Roughness", defaultValue=0.5, sortPriority=1)
    metal = add(m, "ScalarParameter", -700, 250, parameterName="Metallic", defaultValue=0.0, sortPriority=2)
    strength = add(m, "ScalarParameter", -700, 400, parameterName="EmissiveStrength", defaultValue=0.0, sortPriority=3)
    mul = add(m, "Multiply", -300, 350)
    out(color, "RGB", "MP_BaseColor")
    out(rough, "", "MP_Roughness")
    out(metal, "", "MP_Metallic")
    link(color, "RGB", mul, "A")
    link(strength, "", mul, "B")
    out(mul, "", "MP_EmissiveColor")
    set_props(m, {"blendMode": "BLEND_Opaque", **USAGE})
    call(MT, "recompile", {"material_or_function": m})
    return m


def build_kit_glass():
    """Оргстекло и линзы (pipeline/unreal.md): прозрачный, без текстур. Nanite такие меши не рисует."""
    m = fresh_material("M_KitGlass")
    color = add(m, "VectorParameter", -700, -200, parameterName="Color",
                defaultValue={"r": 0.8, "g": 0.86, "b": 0.88, "a": 1.0}, sortPriority=0)
    opacity = add(m, "ScalarParameter", -700, 100, parameterName="Opacity", defaultValue=0.2, sortPriority=1)
    rough = add(m, "ScalarParameter", -700, 250, parameterName="Roughness", defaultValue=0.05, sortPriority=2)
    strength = add(m, "ScalarParameter", -700, 400, parameterName="EmissiveStrength", defaultValue=0.0, sortPriority=3)
    mul = add(m, "Multiply", -300, 350)
    out(color, "RGB", "MP_BaseColor")
    out(opacity, "", "MP_Opacity")
    out(rough, "", "MP_Roughness")
    link(color, "RGB", mul, "A")
    link(strength, "", mul, "B")
    out(mul, "", "MP_EmissiveColor")
    set_props(m, {"twoSided": True, "blendMode": "BLEND_Translucent",
                  "translucencyLightingMode": "TLM_SurfacePerPixelLighting"})
    call(MT, "recompile", {"material_or_function": m})
    return m


def main():
    call(AS, "create_folder", {"path": FOLDER})
    orm = ensure_default_orm()
    # Только недостающие: пересборка графа загруженного материала (delete_expression) роняет редактор
    # на проверке !IsRooted (14.11.2026, M_Kit со ссылками из экземпляров героя). Поменять граф готового
    # мастера — удалить его в редакторе и запустить скрипт заново, затем переназначить родителя экземплярам.
    for name, build in (("M_Kit", lambda: build_kit(orm)), ("M_KitSolid", build_kit_solid), ("M_KitGlass", build_kit_glass)):
        if call(AS, "exists", {"path": f"{FOLDER}/{name}"}):
            print("есть, не трогаю:", name)
        else:
            build()
    for n in ("M_Kit", "M_KitSolid", "M_KitGlass"):
        call(MT, "layout_expressions", {"material_or_function": ref(f"{FOLDER}/{n}")})
    paths = [f"{FOLDER}/{n}" for n in (DEFAULT_ORM, "M_Kit", "M_KitSolid", "M_KitGlass")]
    print("saved", call(AS, "save_assets", {"asset_paths": paths}), paths)


if __name__ == "__main__":
    main()
