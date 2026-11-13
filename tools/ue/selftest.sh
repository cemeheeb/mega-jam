#!/bin/zsh
# Самопроверка игры без окна: ведущий забега сам проходит сценарий (ARunDirector::TickSelfTest)
# и пишет строки «Run:» в журнал. Аргумент — зерно, по умолчанию 42.
ROOT="${0:A:h:h:h}"
LOG=$(mktemp -t megajam-selftest)
"/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" "$ROOT/MegaJam.uproject" /Game/Game/Maps/Lvl_Game \
  -game -nullrhi -unattended -nosound -nosplash -RunSelfTest -RunSeed=${1:-42} -stdout -FullStdOutLogOutput > "$LOG" 2>&1 &
PID=$!
for i in {1..60}; do sleep 3; kill -0 $PID 2>/dev/null || break; done
kill $PID 2>/dev/null
grep -E "LogRun" "$LOG" | sed 's/^\[[^]]*\]\[[ 0-9]*\]//'
rm -f "$LOG"
