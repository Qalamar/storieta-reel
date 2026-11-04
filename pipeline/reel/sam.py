"""SAM 3.1 per-figure masks for one panel.

Each Wonder phrase is one SAM call on the panel crop. Masks come back
box-local in Meta's arithmetic-coded one_bit format; meta-sam-parser decodes
them, which is pure Python and slow (about 4 s per 100k pixels), so decoded
rasters are cached next to the raw response.
"""
import hashlib, os
import numpy as np
import meta_sam_parser as msp
from .meta_api import CACHE, SAM_PER_CALL, cached, data_url

MODEL = "sam-3.1"


def _text(res):
    return "".join(c.get("text", "") for o in res.get("output", []) for c in o.get("content", []))


def segment(crop, phrase, label):
    body = {"model": MODEL,
            "input": [{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": phrase},
                {"type": "input_image", "image_url": data_url(crop, "PNG")}]}],
            "metadata": {"mask_encoding": "one_bit", "include_confidence": "true"}}
    res = cached("sam", "/responses", body, lambda r: SAM_PER_CALL, label, timeout=60)
    return _text(res)


def _decode_one(args):
    payload, width, height = args
    mask = msp.SegmentationMask(encoding="one_bit", payload=payload, width=width, height=height)
    return np.frombuffer(msp.decode_mask_to_raster(mask), np.uint8).reshape(height, width).astype(bool)


def instances(text, size, pool=None):
    """[(confidence, full-crop bool mask)] for every instance in a SAM reply."""
    parser = msp.image_segmentation_format().create_parser()
    parser.push(text)
    records = [r for r in parser.finish(msp.CompletedOutcome()).result.records if r.kind == "mask"]
    out = []
    jobs = []
    for r in records:
        key = hashlib.sha256(r.mask.payload.encode()).hexdigest()[:24]
        path = os.path.join(CACHE, f"mask-{key}.npy")
        jobs.append((r, path))
    todo = [(r.mask.payload, r.mask.width, r.mask.height) for r, path in jobs if not os.path.exists(path)]
    decoded = iter((pool.map if pool else map)(_decode_one, todo))
    w, h = size
    for r, path in jobs:
        if os.path.exists(path):
            local = np.load(path)
        else:
            local = next(decoded)
            np.save(path, local)
        full = np.zeros((h, w), bool)
        b = r.bounds
        x0, y0 = int(b.left), int(b.top)
        x1, y1 = min(w, x0 + local.shape[1]), min(h, y0 + local.shape[0])
        full[y0:y1, x0:x1] = local[: y1 - y0, : x1 - x0]
        out.append((r.confidence or 0.0, full))
    return out
