#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCADCmd smoke test: in-process geometry, then the hooks.py entry point.
# Expects FreeCADCmd on PATH (CI: pixi run bash addons/BruceWorx/tests/run_freecad_smoke.sh).

set -euo pipefail

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cmd=${FREECAD_CMD:-FreeCADCmd}
outdir=${BW_SMOKE_DIR:-/tmp/bruceworx-hooks-smoke}
export BW_SMOKE_DIR="$outdir"

echo "BruceWorx smoke: in-process export, STEP import, tree, rename"
"$cmd" "$root/tests/freecad_smoke.py"

test -s "$outdir/box.step"
test -s "$outdir/LE-01001-A.FCStd"

echo "BruceWorx smoke: hooks.py via BW_HOOKS_ARGS"
BW_HOOKS_ARGS="list-tree --input ${outdir}/box.FCStd --output ${outdir}/cli-tree.json" \
  "$cmd" "$root/hooks.py"
python3 - "$outdir/cli-tree.json" <<'PY'
import json
import sys

tree = json.load(open(sys.argv[1], encoding="utf-8"))
if tree.get("schema") != "bruceworx.document-tree.v1" or not tree.get("tree"):
    raise SystemExit(f"cli tree json unexpected: {tree!r}")
print("cli list-tree ok", tree["tree"][0]["name"])
PY

echo "BruceWorx smoke: hooks.py via FreeCADCmd --"
preview=$("$cmd" -- "$root/hooks.py" preview --program LE \
  --config "$root/config/numbering.example.json")
printf '%s\n' "$preview" | grep -q 'LE-01001-A'
# Preview must not create or rewrite the local counter.
test ! -e "$root/config/numbering.json"

echo "BW_SMOKE CLI PASS"
