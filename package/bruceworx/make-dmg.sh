#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# BruceWorx: build an UNSIGNED (ad-hoc codesigned at most) macOS arm64 .app/.dmg
# from a pixi/CMake install (`pixi run install-release`). INTERNAL USE ONLY:
# not notarized, Gatekeeper will warn on other machines.
#
# Usage: package/bruceworx/make-dmg.sh [PREFIX] [OUTDIR]
#   PREFIX  install prefix (default: $CONDA_PREFIX, i.e. run via `pixi run`)
#   OUTDIR  output directory (default: ./dist)
# Env: BW_VERSION (default 1.1.4-bw.1), BW_ADHOC_SIGN=1 to ad-hoc sign.
set -euo pipefail

prefix="${1:-${CONDA_PREFIX:-}}"
outdir="${2:-dist}"
version="${BW_VERSION:-1.1.4-bw.1}"
app_name="FreeCAD BruceWorx"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
    echo "error: must run on macOS arm64" >&2; exit 1
fi
if [[ -z "$prefix" || ! -x "$prefix/bin/FreeCAD" ]]; then
    echo "error: no FreeCAD install found in '${prefix}' (run 'pixi run install-release' first)" >&2
    exit 1
fi

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
app="$stage/$app_name.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"

echo "Copying install prefix $prefix -> bundle"
# The conda prefix is relocatable; copy it whole (dereference nothing, keep links).
rsync -a --exclude 'conda-meta' --exclude 'pkgs' "$prefix/" "$app/Contents/Resources/"

cat > "$app/Contents/MacOS/FreeCAD" <<'LAUNCH'
#!/bin/bash
here="$(cd "$(dirname "$0")/../Resources" && pwd)"
export PATH="$here/bin:$PATH"
exec "$here/bin/FreeCAD" "$@"
LAUNCH
chmod +x "$app/Contents/MacOS/FreeCAD"

icon="$repo/src/MacAppBundle/FreeCAD.app/Contents/Resources/freecad.icns"
[[ -f "$icon" ]] && cp "$icon" "$app/Contents/Resources/freecad.icns"

cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>${app_name}</string>
  <key>CFBundleDisplayName</key><string>${app_name}</string>
  <key>CFBundleIdentifier</key><string>com.bruceworx.freecad</string>
  <key>CFBundleExecutable</key><string>FreeCAD</string>
  <key>CFBundleIconFile</key><string>freecad.icns</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${version}</string>
  <key>CFBundleVersion</key><string>${version}</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSArchitecturePriority</key><array><string>arm64</string></array>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

if [[ "${BW_ADHOC_SIGN:-0}" == "1" ]]; then
    echo "Ad-hoc codesigning (no identity, not notarized)"
    codesign --force --deep --sign - "$app"
fi

"$app/Contents/Resources/bin/FreeCADCmd" --version || true

mkdir -p "$outdir"
dmg="$outdir/FreeCAD-BruceWorx-${version}-macOS-arm64.dmg"
ln -s /Applications "$stage/Applications"
rm -f "$dmg"
hdiutil create -volname "$app_name $version" -srcfolder "$stage" -ov -format UDZO "$dmg"
echo "Created $dmg"
