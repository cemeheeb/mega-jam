#!/bin/zsh
# Пробная упаковка игры под Mac и прогон упакованной сборки самопроверкой — репетиция сборки под Windows
# (с Mac под Windows не собрать: DESIGN.md, план на 15.11, блок 1).
#
#   tools/ue/package_mac.sh          упаковать (около минуты) и пройти забег до победы в упакованной игре
#
# Что ловит: ассеты, которые код грузит по пути и которые не попали в сборку (уровни — MapsToCook, папки —
# DirectoriesToAlwaysCook в Config/DefaultGame.ini), шрифты из Content/Fonts, звук из /Game/Audio.
# В выводе: итог забега и чего в сборке не нашлось. Отсутствующие /Game/Audio/S_* — это ещё не сгенерированные звуки.
# Сборка ложится в Saved/StagedBuilds/Mac (в репозиторий не идёт).
set -e
cd "$(dirname "$0")/../.."
LOG=Saved/Logs/package_mac.log
mkdir -p Saved/Logs
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun -project="$PWD/MegaJam.uproject" \
  -platform=Mac -clientconfig=Development -build -cook -stage -pak -nop4 -utf8output -unattended -nosplash > $LOG 2>&1 \
  || { grep -a -E "error|Error" $LOG | tail -20; echo "упаковка не прошла, журнал: $LOG"; exit 1; }
grep -a -E "Packages Cooked:|BUILD SUCCESSFUL" $LOG | tail -2
RUN=Saved/Logs/packaged_run.log
"$PWD/Saved/StagedBuilds/Mac/MegaJam.app/Contents/MacOS/MegaJam" /Game/Game/Maps/Lvl_Game -RunSelfTest -RunWin -RunSeed=42 \
  -windowed -ResX=1280 -ResY=720 -log -stdout -FullStdOutLogOutput > $RUN 2>&1 &
PID=$!
for i in $(seq 1 60); do /bin/sleep 3; grep -a -q "test done" $RUN && break; kill -0 $PID 2>/dev/null || break; done
/bin/sleep 2; kill $PID 2>/dev/null || true
grep -a -E "Run: (WON|test done)|LogLoad: Error" $RUN | sed 's/^\[[^]]*\]\[[ 0-9]*\]//' | cut -c1-140
echo "не нашлось в сборке:"
grep -a "SkipPackage" $RUN | sed -E 's/.*SkipPackage: ([^ ]+).*/  \1/' | sort -u
