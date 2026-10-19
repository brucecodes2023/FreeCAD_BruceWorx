"""Paste the 3D renders into the window grabs: compose.py <out-dir> <light|dark|keep>.

A Qt window grab shows the 3D view's background but not the model, so capture.py
also renders the view. The render with the real background ("-3dbg") is pasted
everywhere except where a floating panel covers the view; translucent things such
as grid lines only look right that way. Older captures without it fall back to the
transparent render ("-3d").
"""

import json
import os
import sys

from PIL import Image, ImageDraw

out, mode = sys.argv[1], sys.argv[2]
# Areas macOS paints itself (unified title bar) come out transparent in a Qt grab.
chrome = (40, 40, 43, 255) if mode == "dark" else (236, 236, 236, 255)
for name in ("start", "part", "sketch", "asm"):
    shot = os.path.join(out, name + ".png")
    if not os.path.exists(shot):
        print("missing", name)
        continue
    grab = Image.open(shot).convert("RGBA")
    im = Image.alpha_composite(Image.new("RGBA", grab.size, chrome), grab)
    meta = json.load(open(os.path.join(out, name + ".json")))
    geo = meta.get("view")
    with_bg = os.path.join(out, name + "-3dbg.png")
    bare = os.path.join(out, name + "-3d.png")
    if geo and (os.path.exists(with_bg) or os.path.exists(bare)):
        x, y, w, h = (int(geo[k]) for k in ("x", "y", "w", "h"))
        if os.path.exists(with_bg):
            model = Image.open(with_bg).convert("RGBA").resize((w, h))
            mask = Image.new("L", (w, h), 255)
        else:
            model = Image.open(bare).convert("RGBA").resize((w, h))
            mask = model.getchannel("A")
        for px, py, pw, ph in meta.get("panels", []):
            ImageDraw.Draw(mask).rectangle((px - x, py - y, px - x + pw, py - y + ph), fill=0)
        region = im.crop((x, y, x + w, y + h))
        region.paste(model, (0, 0), mask)
        im.paste(region, (x, y))
    im.convert("RGB").save(os.path.join(out, name + "-full.png"))
    print("wrote", name + "-full.png", im.size)
