#!/bin/sh
# Launch a build-tree FreeCAD with fontconfig kept outside iCloud.
# The repo lives under Documents, and Coin blocks the UI thread while
# fontconfig reads those files the first time a sketch draws axis labels.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
MODE=release
if [ "$1" = "release" ] || [ "$1" = "debug" ]; then
    MODE=$1
    shift
fi
BIN="$ROOT/build/$MODE/bin/FreeCAD"
CACHE="${HOME}/Library/Caches/freecad-bruceworx"
mkdir -p "$CACHE/fontconfig"
CONF="$CACHE/fonts.conf"
if [ ! -f "$CONF" ]; then
    cat > "$CONF" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>/System/Library/Fonts</dir>
  <dir>/System/Library/Fonts/Supplemental</dir>
  <dir>/Library/Fonts</dir>
  <dir>~/Library/Fonts</dir>
  <cachedir>$CACHE/fontconfig</cachedir>
</fontconfig>
EOF
fi
export FONTCONFIG_FILE="$CONF"
exec "$BIN" "$@"
