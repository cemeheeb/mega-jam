"""Выгрузка каталога предметов, шаблонов записок и чисел баланса в C++ для игры.

    python3 tools/rungen/export_cpp.py

Пишет Source/MegaJam/Run/RunGenData.inl. Запускать после любой правки content.py или config.py,
затем пересобрать проект и прогнать tools/ue/check_port.py.
"""

import os
from dataclasses import fields

import content as C
from config import DEFAULT

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "Source", "MegaJam", "Run", "RunGenData.inl")
GAME_FIELDS = ("items_in_run", "health", "p_guess",
               "filler_min", "filler_max", "extras", "dummy_weight", "extra_weight", "p_extra_note", "p_guess_note")


def cstr(s: str) -> str:
    s.encode("ascii")  # тексты игры — латиница; иначе нужна другая запись литералов
    return 'TEXT("' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '")'


def main():
    lines = ["// Сгенерировано tools/rungen/export_cpp.py из content.py и config.py. Не править руками.", ""]
    for f in fields(DEFAULT):
        if f.name in GAME_FIELDS:
            v = getattr(DEFAULT, f.name)
            lines.append(f"#define RUNGEN_DEFAULT_{f.name.upper()} {v!r}")
    lines += ["", "static const FRunItemDef GRunCatalog[] = {"]
    for it in C.CATALOG:
        lines.append(f"\t{{ {cstr(it.name)}, {cstr(it.noun)}, {cstr(it.category)} }},")
    lines += ["};", "", f"static const TCHAR* const GRunNotebookName = {cstr(C.NOTEBOOK_NAME)};",
              f"static const TCHAR* const GRunWeaponName = {cstr(C.WEAPON_NAME)};", ""]
    kinds = sorted(C.TEMPLATES)
    assert kinds == list(range(len(kinds)))
    for k in kinds:
        lines.append(f"static const TCHAR* const GRunTemplates{k}[] = {{")
        lines += [f"\t{cstr(t)}," for t in C.TEMPLATES[k]]
        lines.append("};")
    lines += ["", "static const FRunTemplateList GRunTemplates[] = {"]
    lines += [f"\t{{ GRunTemplates{k}, {len(C.TEMPLATES[k])} }}," for k in kinds]
    lines += ["};", "", "static const TCHAR* const GRunNoteKindNames[] = {"]
    lines += [f"\t{cstr(n)}," for n in C.NOTE_KIND_NAMES]
    lines += ["};", ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("written", os.path.normpath(OUT), "-", len(C.CATALOG), "items,", sum(len(v) for v in C.TEMPLATES.values()), "templates")


if __name__ == "__main__":
    main()
