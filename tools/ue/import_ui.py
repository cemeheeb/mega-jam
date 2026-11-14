"""Импорт картинок интерфейса в /Game/UI: лист блокнота для режима чтения.

    python3 tools/ue/import_ui.py

Источник — PNG рядом с карточкой (SourceArt/ui/<карточка>/T_*.png, получен из images/*.webp через sips).
Текстуры рисует экранный интерфейс (ARunHUD) по пути; папка /Game/UI упаковывается целиком (Config/DefaultGame.ini).
Нужен открытый редактор с проектом MegaJam.
"""

import json
import os

from uemcp import tool

AS = "editor_toolset.toolsets.asset.AssetTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
TX = "editor_toolset.toolsets.texture.TextureTools"

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER = "/Game/UI"
TEXTURES = {"T_NotebookPage": "SourceArt/ui/notebook-page/T_NotebookPage.png"}
# картинка экрана: без мипов и стриминга (размер не степень двойки), группа UI
PROPS = {"SRGB": True, "CompressionSettings": "TC_Default", "LODGroup": "TEXTUREGROUP_UI",
         "MipGenSettings": "TMGS_NoMipmaps", "NeverStream": True}


def call(toolset, name, args):
    res = tool(toolset, name, args)
    if "ERROR" in res[:12]:
        raise RuntimeError(f"{name}: {res[:600]}")
    return json.loads(res).get("returnValue") if res.strip() else None


def main():
    call(AS, "create_folder", {"path": FOLDER})
    saved = []
    for name, src in TEXTURES.items():
        path = f"{FOLDER}/{name}"
        if not call(AS, "exists", {"path": path}):
            call(TX, "import_file", {"folder_path": FOLDER, "asset_name": name, "source_file": os.path.join(PROJECT, src)})
        call(OB, "set_properties", {"instance": {"refPath": f"{path}.{name}"}, "values": json.dumps(PROPS)})
        saved.append(path)
    call(AS, "save_assets", {"asset_paths": saved})
    print("импортировано:", ", ".join(saved))


if __name__ == "__main__":
    main()
