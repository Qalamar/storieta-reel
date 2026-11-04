"""Muse Image paints a scene from a prompt and reference images.

Uses image generation for text-only prompts and image edits when references
are supplied as Image 1..N (style and identity references). Like every other paid call
in the pipeline, the reply is cached by its exact request and logged to the
spend ledger, so a rerun never pays twice.
"""
import base64, hashlib, io, json, os, time, urllib.request, uuid
from pathlib import Path
from PIL import Image
from .meta_api import BASE, CACHE, LEDGER

MODEL = "muse-image-1.0"
PER_IMAGE = 0.01  # USD, flat per image at the time of writing


def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    out = io.BytesIO()
    for name, value in fields:
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    for name, filename, data in files:
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                  f"Content-Type: image/png\r\n\r\n".encode())
        out.write(data + b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def request_digest(prompt, refs, size):
    h = hashlib.sha256((MODEL + size + prompt).encode())
    if not refs:
        h.update(b"/images/generations")
    for r in refs:
        h.update(Path(r).read_bytes())
    return h.hexdigest()[:24]


def paint(prompt, refs, size="1536x1024", label="scene"):
    """The painted scene as a PIL image. refs are PNG paths, in prompt order."""
    digest = request_digest(prompt, refs, size)
    os.makedirs(CACHE, exist_ok=True)
    hit = os.path.join(CACHE, f"muse-image-{digest}.json")
    if not os.path.exists(hit):
        fields = [("model", MODEL), ("size", size), ("prompt", prompt)]
        if refs:
            files = [(f"image[{i}]", os.path.basename(r), Path(r).read_bytes()) for i, r in enumerate(refs)]
            body, ctype = _multipart(fields, files)
            endpoint = "/images/edits"
        else:
            body, ctype = json.dumps(dict(fields)).encode(), "application/json"
            endpoint = "/images/generations"
        req = urllib.request.Request(f"{BASE}{endpoint}", data=body, headers={
            "Authorization": f"Bearer {os.environ['META_MODEL_API_KEY']}", "Content-Type": ctype})
        started = time.time()
        with urllib.request.urlopen(req, timeout=300) as response:
            res = json.load(response)
        Path(hit).write_text(json.dumps(res))
        with open(LEDGER, "a") as f:
            f.write(f"{time.strftime('%FT%T')}\tmuse-image\t{label}\t${PER_IMAGE:.4f}\t{time.time() - started:.1f}s\t{digest}\n")
    res = json.loads(Path(hit).read_text())
    with Image.open(io.BytesIO(base64.b64decode(res["data"][0]["b64_json"]))) as image:
        return image.convert("RGB")
