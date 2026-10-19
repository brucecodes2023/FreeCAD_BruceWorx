#!/bin/sh
# Capture the real build on the four mock screens, on a copy of the user config.
#   capture.sh <out-dir> [light|dark] [key=value ...]
# Each key=value sets a parameter in the copy before launch, for example
#   BaseApp/Preferences/BruceWorx/UseBruceWorxBar:bool=0
# Writes <out-dir>/{start,part,sketch,asm}.png with the 3D view pasted in.
set -e
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../../../../../.." && pwd)
OUT=$1
MODE=${2:-light}
shift 2 || shift $#
mkdir -p "$OUT"
cp "$HOME/Library/Preferences/FreeCAD/v1-1/user.cfg" "$OUT/user.cfg"
# A forced light/dark capture must not follow the Mac's own appearance.
FOLLOW=""
if [ "$MODE" = "light" ] || [ "$MODE" = "dark" ]; then
    FOLLOW="BaseApp/Preferences/BruceWorx/FollowSystemAppearance:bool=0"
fi
python3 "$HERE/cfgset.py" "$OUT/user.cfg" "$MODE" $FOLLOW "$@"

BW_CAPTURE_OUT="$OUT" "$ROOT/package/bruceworx/run-freecad.sh" -u "$OUT/user.cfg" "$HERE/capture.py" \
    > "$OUT/freecad.log" 2>&1 &
pid=$!
i=0; while kill -0 $pid 2>/dev/null && [ $i -lt 90 ]; do sleep 1; i=$((i+1)); done
kill $pid 2>/dev/null || true

python3 "$HERE/compose.py" "$OUT" "$MODE"
