"""Warp a flat text raster using independent top/bottom curves, matching the exact
proportions measured from components/league-logo-horizontal/type-sample-07.png.
Each vertical column is only translated/scaled in Y -- never rotated or sheared --
so strokes that were vertical in the source (like the outer edges of A and G) stay
vertical in the output, unlike a true polar/radial arc distortion."""
import numpy as np
from PIL import Image

# Quadratic fits (in fractional x, fractional offset of word_h) measured directly from
# the reference image -- see the measurement script. top: shallow rise into the middle.
# bottom: same magnitude of curve, but CONVEX (bows up into the middle, like the top,
# rather than sagging away from it) -- flipped from the raw reference measurement per
# design direction.
TOP_COEF = np.polyfit([0, 0.25, 0.5, 0.75, 1], [-0.00434, 0.02214, 0.03241, 0.02650, 0.00434], 2)
BOT_COEF = np.polyfit([0, 0.25, 0.5, 0.75, 1], [-0.00745, -0.07059, -0.08916, -0.06316, 0.00745], 2)


def column_warp(img: Image.Image, word_h: float, segments: int = 80,
                 top_coef=TOP_COEF, bot_coef=BOT_COEF) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size

    def top_off(f):
        return np.polyval(top_coef, f) * word_h  # positive => shift UP (smaller y)

    def bot_off(f):
        return np.polyval(bot_coef, f) * word_h  # positive => shift DOWN (larger y)

    fs = np.linspace(0, 1, segments + 1)
    tops = [top_off(f) for f in fs]
    bots = [bot_off(f) for f in fs]
    pad_top = int(np.ceil(max(0, -min(tops)))) + 2
    pad_bot = int(np.ceil(max(0, max(bots)))) + 2
    out_h = h + pad_top + pad_bot

    mesh = []
    for i in range(segments):
        sx0 = int(round(i * w / segments))
        sx1 = int(round((i + 1) * w / segments))
        if sx1 <= sx0:
            continue
        f_mid = (sx0 + sx1) / 2 / w
        ty = pad_top - top_off(f_mid)
        by = pad_top + h + bot_off(f_mid)
        box = (sx0, int(round(ty)), sx1, int(round(by)))
        quad = (sx0, 0, sx0, h, sx1, h, sx1, 0)  # upper-left, lower-left, lower-right, upper-right
        mesh.append((box, quad))

    return img.transform((w, out_h), Image.MESH, mesh, resample=Image.BICUBIC)


if __name__ == "__main__":
    import sys
    src = Image.open(sys.argv[1])
    out = column_warp(src, word_h=src.size[1])
    out.save(sys.argv[2])
    print("saved", sys.argv[2], out.size)
