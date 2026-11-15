"""Материал зеркала каюты: M_Mirror — без освещения, свечение = картинка камеры зеркала × Gain.

    python3 tools/ue/make_mirror_material.py [--force]

Картинку (рендер-таргет камеры, параметр Tex) подставляет ARunCabin: камера стоит в отражённой точке камеры игрока,
её кадр ложится ровно на стекло (Source/MegaJam/Run/RunCabin.cpp). Gain — яркость отражения.
Нужен открытый редактор с проектом MegaJam, не в Play. --force — пересоздать материал.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from uemcp import tool  # noqa: E402
from build_rooms import call, ensure_not_playing, AS, OB  # noqa: E402

MT = "editor_toolset.toolsets.material.MaterialTools"
FOLDER = "/Game/Game/Materials"
NAME = "M_Mirror"
PATH = f"{FOLDER}/{NAME}"


def main():
    ensure_not_playing()
    if call(AS, "exists", {"path": PATH}):
        if "--force" not in sys.argv:
            print("уже есть:", PATH)
            return
        call(AS, "delete", {"path": PATH})
    mat = call(MT, "create_material", {"folder_path": FOLDER, "asset_name": NAME})
    call(OB, "set_properties", {"instance": mat, "values": json.dumps({"ShadingModel": "MSM_Unlit"})})

    def add(cls, x, y, props):
        e = call(MT, "add_expression", {"material_or_function": mat, "expression_class": {"refPath": f"/Script/Engine.{cls}"},
                                        "x": x, "y": y})
        call(OB, "set_properties", {"instance": e, "values": json.dumps(props)})
        return e

    tex = add("MaterialExpressionTextureSampleParameter2D", -500, 0, {
        "ParameterName": "Tex", "Texture": {"refPath": "/Engine/EngineResources/DefaultTexture.DefaultTexture"}})
    gain = add("MaterialExpressionScalarParameter", -500, 250, {"ParameterName": "Gain", "DefaultValue": 1.0})
    mul = add("MaterialExpressionMultiply", -200, 100, {})
    call(MT, "connect_expressions", {"from_expression": tex, "from_output_name": "RGB", "to_expression": mul, "to_input_name": "A"})
    call(MT, "connect_expressions", {"from_expression": gain, "from_output_name": "", "to_expression": mul, "to_input_name": "B"})
    call(MT, "connect_to_output", {"expression": mul, "output_name": "", "material_property": "MP_EmissiveColor"})
    call(MT, "recompile", {"material_or_function": mat})
    call(AS, "save_assets", {"asset_paths": [PATH]})
    print("собран:", PATH)


if __name__ == "__main__":
    main()
