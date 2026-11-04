"""Small image helpers for the standalone scene demo."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

MIN_CONF, MIN_SHARE = 0.5, 0.004
COLOURS = [(230, 57, 70), (42, 157, 143), (69, 123, 157), (244, 162, 97)]


def iou(a, b):
    union = (a | b).sum()
    return float((a & b).sum() / union) if union else 0.0


def solid(mask):
    return ndimage.binary_dilation(mask, iterations=2)


def soft(mask):
    return ndimage.gaussian_filter(mask.astype(np.float32), sigma=0.7)


def marked_page(img, panels, found):
    """The page with each SAM instance outlined and numbered, for Wonder to read."""
    rgb = np.asarray(img.convert("RGB")).copy()
    for k, (x0, y0, x1, y1) in enumerate(panels):
        for mark, m in found[k]:
            edge = m & ~ndimage.binary_erosion(m, iterations=3)
            rgb[y0:y1, x0:x1][edge] = COLOURS[mark % len(COLOURS)]
    out = Image.fromarray(rgb)
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=max(18, img.width // 34))
    for k, (x0, y0, x1, y1) in enumerate(panels):
        for mark, m in found[k]:
            ys, xs = np.nonzero(m)
            # label on the figure's upper body, where it cannot be mistaken for a neighbour
            cy = int(np.percentile(ys, 25))
            row = xs[np.abs(ys - cy) < 6]
            cx = int(np.median(row)) if row.size else int(xs.mean())
            label = str(mark)
            l, t, r, b = draw.textbbox((0, 0), label, font=font)
            bx, by = x0 + cx - (r - l) // 2, y0 + cy - (b - t) // 2
            draw.rounded_rectangle((bx - 6, by - 4, bx + r - l + 6, by + b - t + 8), radius=6,
                                   fill=COLOURS[mark % len(COLOURS)], outline=(255, 255, 255), width=2)
            draw.text((bx - l, by - t), label, fill=(255, 255, 255), font=font)
    return out
