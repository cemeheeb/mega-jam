#!/bin/sh
# Navigator console, steps 8-9 (pipeline/kit.md): build the ArmorPaint project from the mesh and masks, export textures.
# Usage: navigator_ap_run.sh <scratch dir for logs>
SP=${1:?scratch dir}
KIT=$(cd "$(dirname "$0")" && pwd)
SRC=/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/navigator-console/source
AP=/Users/cemeheeb/Projects/armorpaint/paint/build/clt/ArmorPaint.app/Contents/MacOS/ArmorPaint
python3 "$KIT/navigator_gen_build.py" || exit 1
rm -f "$SRC/navigator-console.arm"
"$AP" "$SRC/navigator-console.fbx" --background --script "$SRC/navigator-console.build.c" > "$SP/navigator_ap_build.log" 2>&1 & PID=$!
for i in $(seq 1 150); do kill -0 $PID 2>/dev/null || break; sleep 1; done; kill $PID 2>/dev/null && echo BUILD KILLED
tail -3 "$SP/navigator_ap_build.log"
mkdir -p "$SRC/export"
"$AP" "$SRC/navigator-console.arm" --background --export-textures png godot "$SRC/export" > "$SP/navigator_ap_export.log" 2>&1 & PID=$!
for i in $(seq 1 150); do kill -0 $PID 2>/dev/null || break; sleep 1; done; kill $PID 2>/dev/null && echo EXPORT KILLED
tail -1 "$SP/navigator_ap_export.log"; ls -la "$SRC/export"
