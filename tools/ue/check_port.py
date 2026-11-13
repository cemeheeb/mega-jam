"""Проверка переноса генератора забега в C++: раскладки из Unreal должны совпасть с эталонами Python.

    python3 tools/ue/check_port.py

Запускает редактор без окна с командой RunGenDump и сравнивает её JSON с tools/rungen/golden/*.json.
Перед запуском проект должен быть собран (Build.sh MegaJamEditor Mac Development).
"""

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GOLDEN = os.path.join(ROOT, "tools", "rungen", "golden")
EDITOR = "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd"
# только для симуляции игроков, в игру не переносятся
SIM_ONLY = ("p_hit", "p_fix", "max_entries")


def diff(a, b, path=""):
    """Первые расхождения двух JSON-значений."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: есть только в {'эталоне' if k in a else 'Unreal'}")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: длина {len(a)} против {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: эталон {a!r}, Unreal {b!r}"]


def main():
    files = sorted(f for f in os.listdir(GOLDEN) if f.endswith(".json"))
    seeds = [f[5:-5] for f in files if f.startswith("seed_")]
    with tempfile.TemporaryDirectory() as out:
        cmd = [EDITOR, os.path.join(ROOT, "MegaJam.uproject"), "-run=RunGenDump", f"-Seeds={','.join(seeds)}",
               f"-Out={out}", "-unattended", "-nullrhi", "-nosplash", "-nop4", "-stdout"]
        try:
            # без ввода и с пределом времени: иначе процесс может ждать клавиатуру и повиснуть
            r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=180)
        except subprocess.TimeoutExpired:
            print("команда RunGenDump не завершилась за 3 минуты")
            return 1
        if r.returncode != 0:
            print("команда RunGenDump завершилась с кодом", r.returncode)
            print("\n".join(r.stdout.splitlines()[-25:]))
            return 1
        bad = 0
        for f in files:
            golden = json.load(open(os.path.join(GOLDEN, f), encoding="utf-8"))
            if "config" in golden:
                for k in SIM_ONLY:
                    golden["config"].pop(k, None)
            got_path = os.path.join(out, f)
            if not os.path.exists(got_path):
                print(f"{f}: Unreal не выгрузил файл")
                bad += 1
                continue
            d = diff(golden, json.load(open(got_path, encoding="utf-8")))
            print(f"{f}: {'совпадает' if not d else f'расхождений {len(d)}'}")
            for line in d[:8]:
                print("   ", line)
            bad += bool(d)
    print("ИТОГ:", "перенос совпадает с эталоном" if not bad else f"не совпало файлов: {bad} из {len(files)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
