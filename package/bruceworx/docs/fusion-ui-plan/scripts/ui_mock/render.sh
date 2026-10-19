#!/bin/sh
# Rebuild the UI design mock (chapter 92) from FreeCAD's own icons and renders.
#   render.sh            HTML only (reuses the 3D renders in the work folder)
#   render.sh --views    also re-render the 3D views; opens FreeCAD for ~15 s
# Needs: a build in build/release, Python 3 with Pillow, and Playwright's
# chrome-headless-shell (npx playwright install chromium-headless-shell).
set -e
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../../../../../.." && pwd)
FIG="$HERE/../../fig"
WORK="${BW_MOCK_WORK:-${TMPDIR:-/tmp}/bw-ui-mock}"
mkdir -p "$WORK/icons" "$WORK/thumbs" "$WORK/out"
cp "$HERE/mock.html" "$WORK/"

# Icons: every icons/<name>.svg the mock asks for, found in the source tree.
grep -oE '"(!?)[A-Za-z_-]+[*]?"' "$HERE/mock.html" | tr -d '"!*' | sort -u | while read -r n; do
    f=$(find "$ROOT/src" -name "$n.svg" -not -path "*/build/*" | head -1)
    if [ -n "$f" ]; then cp "$f" "$WORK/icons/"; fi
done

# Example thumbnails for the Start page.
for f in AssemblyExample EngineBlock FEMExample PartDesignExample; do
    unzip -p "$ROOT/data/examples/$f.FCStd" thumbnails/Thumbnail.png > "$WORK/thumbs/$f.png"
done

if [ "$1" = "--views" ] || [ ! -f "$WORK/view-part.png" ]; then
    # Run on a copy of the user config so nothing the session saves touches the real one.
    cp "$HOME/Library/Preferences/FreeCAD/v1-1/user.cfg" "$WORK/user.cfg" 2>/dev/null || true
    BW_MOCK_OUT="$WORK" "$ROOT/package/bruceworx/run-freecad.sh" -u "$WORK/user.cfg" "$HERE/views.py" &
    pid=$!
    i=0; while kill -0 $pid 2>/dev/null && [ $i -lt 60 ]; do sleep 1; i=$((i+1)); done
    kill $pid 2>/dev/null || true
fi
python3 - "$WORK" <<'PY'
import sys
from PIL import Image
w = sys.argv[1]
for n in ("view-part", "view-hinge"):
    im = Image.open(f"{w}/{n}.png").convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    iw, ih = im.size
    pad = int(max(iw, ih) * .08)
    W, H = iw + 2 * pad, ih + 2 * pad
    W, H = (int(H * 1.6), H) if W / H < 1.6 else (W, int(W / 1.6))
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c.alpha_composite(im, ((W - iw) // 2, (H - ih) // 2))
    c.resize((480, 300), Image.LANCZOS).save(f"{w}/thumbs/{n}.png")
PY

CH=$(ls -d "$HOME"/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell | tail -1)
shot() {
    "$CH" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=2 --window-size=1600,1000 \
        --virtual-time-budget=2000 --screenshot="$WORK/out/$1.png" "file://$WORK/mock.html?$2" >/dev/null 2>&1
}
for s in part asm sketch start; do
    for t in light dark; do shot "$s-$t" "screen=$s&theme=$t"; done
done
shot part-notes "screen=part&theme=light&notes=1"
shot plates "screen=plates&theme=dark"

# Figures for the PDF: 2400 px wide.
python3 - "$WORK/out" "$FIG" <<'PY'
import sys, os
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
for f in sorted(os.listdir(src)):
    Image.open(os.path.join(src, f)).convert("RGB").resize((2400, 1500), Image.LANCZOS) \
        .save(os.path.join(dst, "ui_mock_" + f), optimize=True)
    print("fig/ui_mock_" + f)
PY
