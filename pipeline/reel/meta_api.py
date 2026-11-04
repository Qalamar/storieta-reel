"""Meta Model API calls with a once-only cache and a spend ledger.

Every paid response is stored under work/cache keyed by a hash of the exact
request, so a rerun of the pipeline never bills the same call twice. A failed
request, or a billed reply that fails `ok` (a truncated answer), is logged but
not cached, so it can be retried.
"""
import base64, hashlib, io, json, os, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "work", "cache")
LEDGER = os.path.join(ROOT, "work", "spend.log")
BASE = "https://api.meta.ai/v1"

# USD. SAM bills per image per prompt; Wonder per token.
SAM_PER_CALL = 2.5 / 1000
WONDER_IN, WONDER_OUT = 4 / 1e6, 20 / 1e6


def data_url(img, fmt="WEBP", quality=90):
    buf = io.BytesIO()
    img.save(buf, fmt, quality=quality)
    return f"data:image/{fmt.lower()};base64,{base64.b64encode(buf.getvalue()).decode()}"


def _post(path, body, timeout, label):
    """POST with at most two retries, only on a 5xx, which returns no result.
    Each retry is written to the ledger, since a server error might still bill."""
    key = os.environ["META_MODEL_API_KEY"]
    for attempt in range(3):
        req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except urllib.error.HTTPError as e:
            detail = f"{path} {e.code}: {e.read().decode()[:300]}"
            if e.code < 500 or attempt == 2:
                raise RuntimeError(detail) from None
            with open(LEDGER, "a") as f:
                f.write(f"{time.strftime('%FT%T')}\tretry\t{label}\t$0.0000\t{detail[:80]}\t-\n")
            time.sleep(10 * (attempt + 1))


def cached(kind, path, body, cost_of, label, timeout=300, ok=lambda res: True):
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:24]
    os.makedirs(CACHE, exist_ok=True)
    hit = os.path.join(CACHE, f"{kind}-{digest}.json")
    if os.path.exists(hit):
        return json.load(open(hit))
    started = time.time()
    res = _post(path, body, timeout, label)
    good = ok(res)
    if good:
        json.dump(res, open(hit, "w"))
    with open(LEDGER, "a") as f:
        f.write(f"{time.strftime('%FT%T')}\t{kind}\t{label}\t${cost_of(res):.4f}\t{time.time() - started:.1f}s\t{digest}{'' if good else '\tUNUSABLE'}\n")
    if not good:
        raise RuntimeError(f"{kind} {label}: unusable reply, not cached")
    return res


def spent():
    if not os.path.exists(LEDGER):
        return 0.0
    return sum(float(line.split("\t")[3].lstrip("$")) for line in open(LEDGER) if line.strip())
