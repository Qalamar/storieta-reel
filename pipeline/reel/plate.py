"""Muse Image background plate: the same panel with its figures painted out."""
import hashlib, io, os
from PIL import Image
from .meta_api import CACHE
from .muse_image import paint

PROMPT = ("Remove every person and every animal from this comic panel. Paint the background that would be "
          "behind them, continuing the floor, walls, sky, fields and objects with the same painting style, "
          "lighting and perspective. Keep everything else exactly as it is: the panel border, "
          "buildings, furniture and props that nobody is holding. Do not add anything new.")


def plate(crop: Image.Image, label, prompt=PROMPT):
    """Upload a crop directly to Meta; paint caches and logs the exact request."""
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    raw = buf.getvalue()
    digest = hashlib.sha256(raw).hexdigest()[:24]
    os.makedirs(CACHE, exist_ok=True)
    source = os.path.join(CACHE, f"plate-input-{digest}.png")
    if not os.path.exists(source):
        with open(source, "wb") as f:
            f.write(raw)
    # Meta's size parameter sets the aspect ratio; resize its output to the crop.
    result = paint(prompt, [source], size=f"{crop.width}x{crop.height}", label=label)
    return result.convert("RGB").resize(crop.size, Image.LANCZOS)
