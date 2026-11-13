#!/bin/zsh
# Сборка C++-модуля игры для редактора на Mac.
# Если редактор открыт, сборщик кладёт новую библиотеку рядом под именем с номером
# (libUnrealEditor-MegaJam-0001.dylib). Здесь она сразу подменяет основную, чтобы запуск
# без окна (check_port.py, selftest.sh) брал свежий код. Открытый редактор увидит его после перезапуска.
set -e
ROOT="${0:A:h:h:h}"
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" MegaJamEditor Mac Development \
  -project="$ROOT/MegaJam.uproject" 2>&1 | grep -E "error|warning: |Undefined|Result|Total execution" || true
cd "$ROOT/Binaries/Mac"
NEWEST=$(ls -t libUnrealEditor-MegaJam*.dylib | head -1)
if [[ "$NEWEST" != "libUnrealEditor-MegaJam.dylib" ]]; then
  cp "$NEWEST" .promote.tmp && mv .promote.tmp libUnrealEditor-MegaJam.dylib
  rm -f libUnrealEditor-MegaJam-0*.dylib
  # список модулей тоже указывает на имя с номером — вернуть основное
  sed -i '' -E 's/libUnrealEditor-MegaJam-[0-9]+\.dylib/libUnrealEditor-MegaJam.dylib/' UnrealEditor.modules
  echo "подменена основная библиотека: $NEWEST"
fi
