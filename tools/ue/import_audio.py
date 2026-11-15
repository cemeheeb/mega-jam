"""Импорт звука и музыки в /Game/Audio: каждый S_<Имя>.wav из карточек Студии SourceArt/audio/** -> /Game/Audio/S_<Имя>.

Запуск без окна; открытый редактор не мешает (он сам увидит новые файлы):

    "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" "$PWD/MegaJam.uproject" \\
        -run=pythonscript -script="$PWD/tools/ue/import_audio.py" \\
        -unattended -nosplash -nullrhi -nosound -stdout -FullStdOutLogOutput

WAV делает Студия кнопкой «В игру» у дубля (48 кГц, 16 бит). Петля — поле loop: true в asset.yml карточки:
у такой волны включается Looping. Файл новее ассета — импортируется заново, иначе пропускается.
Все звуки лежат в одной папке, без подпапок: код игры находит их по имени (RunAudio::Find, «DoorOpen» ->
/Game/Audio/S_DoorOpen). Папка упаковывается целиком (Config/DefaultGame.ini). Строки результата — «Audio:».
"""

import glob
import os
import re

import unreal

ROOT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "SourceArt", "audio")
DST = "/Game/Audio"


def log(msg):
    unreal.log("Audio: " + msg)


def main():
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    files = sorted(glob.glob(os.path.join(ROOT, "**", "S_*.wav"), recursive=True))
    log("found %d wav under %s" % (len(files), ROOT))
    done = 0
    for wav in files:
        name = os.path.splitext(os.path.basename(wav))[0]
        path = "%s/%s" % (DST, name)
        card = os.path.join(os.path.dirname(wav), "asset.yml")
        loop = False
        if os.path.exists(card):
            with open(card, encoding="utf-8") as f:
                loop = re.search(r"^loop:\s*true\s*$", f.read(), re.M) is not None
        fresh = True
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            disk = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), "Audio", name + ".uasset")
            fresh = not os.path.exists(disk) or os.path.getmtime(wav) > os.path.getmtime(disk)
        if fresh:
            task = unreal.AssetImportTask()
            task.filename = wav
            task.destination_path = DST
            task.destination_name = name
            task.automated = True
            task.replace_existing = True
            task.save = True
            tools.import_asset_tasks([task])
        wave = unreal.load_asset(path)
        if not wave:
            log("FAILED %s" % path)
            continue
        if wave.get_editor_property("looping") != loop:
            wave.set_editor_property("looping", loop)
            unreal.EditorAssetLibrary.save_loaded_asset(wave, False)
        log("%s %s: %.1f s, loop %s" % ("imported" if fresh else "kept", path, wave.get_editor_property("duration"), loop))
        done += 1
    log("done %d of %d" % (done, len(files)))


main()
