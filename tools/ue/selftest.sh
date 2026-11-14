#!/bin/zsh
# Самопроверка игры без окна: ведущий забега сам проходит сценарий (ARunDirector::TickSelfTest)
# и пишет строки «Run:» в журнал. Первый аргумент — зерно, по умолчанию 42.
# Второй аргумент — вид угрозы 1–8: тогда проверяется опасная комната с этой угрозой
# (1 разряды, 2 радиация, 3 гравитация, 4 замедление, 5 робот, 6 крысы, 7 эхо, 8 человек).
# Аномалии 1–4 и 7: войти, постоять, вернуться. Противники 5, 6, 8: уйти, дождаться преследователя, добить ключом.
ROOT="${0:A:h:h:h}"
# Второй аргумент win — полный забег по шпаргалке до победы.
EXTRA=""
if [[ "$2" == "win" ]]; then EXTRA="-RunWin"; elif [[ -n "$2" ]]; then EXTRA="-RunThreat=$2"; fi
LOG=$(mktemp -t megajam-selftest)
"/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" "$ROOT/MegaJam.uproject" /Game/Game/Maps/Lvl_Game \
  -game -nullrhi -unattended -nosound -nosplash -RunSelfTest -RunSeed=${1:-42} $EXTRA -stdout -FullStdOutLogOutput > "$LOG" 2>&1 &
PID=$!
for i in {1..60}; do sleep 3; kill -0 $PID 2>/dev/null || break; done
kill $PID 2>/dev/null
grep -E "LogRun" "$LOG" | sed 's/^\[[^]]*\]\[[ 0-9]*\]//'
rm -f "$LOG"
