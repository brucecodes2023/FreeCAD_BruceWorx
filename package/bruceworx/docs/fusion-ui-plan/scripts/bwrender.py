"""Shared headless renderer for the roadmap figures.

Z-buffer rasteriser (numpy + PIL, 3x supersampled) over FreeCAD shape
tessellations. Imported by the render_*.py scripts, which run in FreeCADCmd.
"""

import math
import os

import FreeCAD as App
from PIL import Image

V = App.Vector
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fig")
os.makedirs(OUT, exist_ok=True)

SS = 3
BG = (246, 247, 250)
EDGE = (40, 44, 52)
LIGHT = V(0.35, -0.55, 0.75).normalize()

COL_BASE = (176, 186, 200)
COL_SEED = (233, 120, 50)
COL_INST = (70, 130, 220)
COL_GHOST = (220, 223, 230)


class Cam:
    def __init__(self, az=-50.0, el=30.0):
        a, e = math.radians(az), math.radians(el)
        self.f = V(math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)) * -1
        up = V(0, 0, 1)
        self.r = self.f.cross(up).normalize()
        self.u = self.r.cross(self.f).normalize()

    def proj(self, p):
        return (p.dot(self.r), p.dot(self.u), p.dot(self.f))


def shade(col, n, alpha=1.0):
    k = 0.45 + 0.55 * abs(n.dot(LIGHT))
    c = tuple(min(255, int(ch * k)) for ch in col)
    if alpha < 1.0:
        c = tuple(int(ch * alpha + bg * (1 - alpha)) for ch, bg in zip(c, BG))
    return c


def collect(items, cam, tol=0.05):
    """items: list of (shape, colour, alpha, draw_edges). Returns primitives."""
    prims = []
    for shape, col, alpha, edges in items:
        for face in shape.Faces:
            pts, tris = face.tessellate(tol)
            for a, b, c in tris:
                pa, pb, pc = pts[a], pts[b], pts[c]
                n = (pb - pa).cross(pc - pa)
                if n.Length < 1e-12:
                    continue
                n.normalize()
                pr = [cam.proj(p) for p in (pa, pb, pc)]
                depth = max(q[2] for q in pr) * 0.3 + sum(q[2] for q in pr) / 3 * 0.7
                prims.append(("tri", depth, [(q[0], q[1]) for q in pr], shade(col, n, alpha), [q[2] for q in pr]))
        if not edges:
            continue
        for face in shape.Faces:
            for e in face.Edges:
                try:
                    if e.isSeam(face):
                        continue
                except Exception:
                    pass
                ps = e.discretize(Deflection=tol)
                for p, q in zip(ps, ps[1:]):
                    a, b = cam.proj(p), cam.proj(q)
                    ecol = EDGE if alpha >= 1 else (170, 175, 185)
                    prims.append(("seg", (a[2] + b[2]) / 2, [(a[0], a[1]), (b[0], b[1])], ecol, [a[2], b[2]]))
    return prims


def render(name, items, size=(1400, 900), az=-50.0, el=30.0, bias=0.004, margin=0.08):
    """Z-buffer rasteriser: exact visibility, edges depth-tested with a small bias."""
    import numpy as np

    cam = Cam(az, el)
    prims = collect(items, cam)
    allpts = np.array([p for pr in prims for p in pr[2]])
    W, H = size[0] * SS, size[1] * SS
    xmin, ymin = allpts.min(0)
    xmax, ymax = allpts.max(0)
    s = min(W * (1 - 2 * margin) / max(xmax - xmin, 1e-9), H * (1 - 2 * margin) / max(ymax - ymin, 1e-9))
    cx, cy = (xmax + xmin) / 2, (ymax + ymin) / 2
    zs = [d for pr in prims for d in pr[4]]
    zspan = max(zs) - min(zs)
    img = np.empty((H, W, 3), np.float32)
    img[:] = BG
    zbuf = np.full((H, W), np.inf, np.float32)

    def scr(p):
        return W / 2 + (p[0] - cx) * s, H / 2 - (p[1] - cy) * s

    for kind, _, pts, col, z in prims:
        if kind != "tri":
            continue
        (x0, y0), (x1, y1), (x2, y2) = [scr(p) for p in pts]
        bx0, bx1 = int(max(min(x0, x1, x2), 0)), int(min(max(x0, x1, x2) + 1, W - 1))
        by0, by1 = int(max(min(y0, y1, y2), 0)), int(min(max(y0, y1, y2) + 1, H - 1))
        if bx1 < bx0 or by1 < by0:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        X, Y = np.meshgrid(np.arange(bx0, bx1 + 1) + 0.5, np.arange(by0, by1 + 1) + 0.5)
        w0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
        w1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not m.any():
            continue
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        sub = zbuf[by0:by1 + 1, bx0:bx1 + 1]
        m &= zz < sub
        sub[m] = zz[m]
        img[by0:by1 + 1, bx0:bx1 + 1][m] = col

    r = max(1, int(0.8 * SS))
    eb = bias * zspan
    for kind, _, pts, col, z in prims:
        if kind != "seg":
            continue
        (xa, ya), (xb, yb) = scr(pts[0]), scr(pts[1])
        n = int(max(abs(xb - xa), abs(yb - ya)) * 2) + 2
        t = np.linspace(0, 1, n)
        xs = (xa + (xb - xa) * t).astype(int)
        ys = (ya + (yb - ya) * t).astype(int)
        zz = z[0] + (z[1] - z[0]) * t
        ok = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
        xs, ys, zz = xs[ok], ys[ok], zz[ok]
        vis = zz <= zbuf[ys, xs] + eb
        xs, ys = xs[vis], ys[vis]
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    img[np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)] = col

    out = Image.fromarray(img.clip(0, 255).astype(np.uint8)).resize(size, Image.LANCZOS)
    path = os.path.join(OUT, name + ".png")
    out.save(path)
    print("wrote", path)
