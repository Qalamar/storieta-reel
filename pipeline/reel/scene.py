"""A layered scene: Muse Wonder selects a passage's moment, Muse Image paints
it, SAM 3.1 outlines every figure, Wonder casts from the numbered outlines,
and Muse Image paints the room behind them. The result is the layers a
reader's scene or a reel panel moves: the room, each cast figure, and the
cast together.

usage: python -m reel.scene <out dir> <brief.json>
brief.json: {"prompt": "...", "refs": ["ref1.png", ...], "size": "1536x1024",
             "shot": "what the scene shows", "characters": ["Holmes", "Watson"]}
or, to start from an existing illustration, {"image": "scene.png", "shot": ..., "characters": ...}.
With "passage" (a text file) and "book", Muse Wonder selects the moment before
painting and writes reading.json. An optional prompt supplies visual guidance.
"""
import json, os, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reel import layers  # noqa: E402
from reel.muse_image import paint  # noqa: E402
from reel.plate import plate  # noqa: E402
from reel.sam import instances, segment  # noqa: E402
from reel.wonder import direct, problems, read  # noqa: E402


def main(out, brief_path):
    brief = json.loads(Path(brief_path).read_text())
    base_dir = os.path.dirname(os.path.abspath(brief_path))
    refs = [os.path.join(base_dir, r) for r in brief.get("refs", [])]
    os.makedirs(out, exist_ok=True)
    label = os.path.basename(os.path.normpath(out))

    # Select the moment before painting, so the image and casting use one brief.
    prompt = brief.get("prompt", "")
    if brief.get("passage"):
        with open(os.path.join(base_dir, brief["passage"])) as f:
            text = f.read().strip()
        moment = read(brief.get("book", ""), text, f"{label} read")
        with open(os.path.join(out, "reading.json"), "w") as f:
            json.dump(moment, f, indent=1)
        brief = {**brief, **moment}
        prompt = (f"Illustrate this moment from {brief.get('book') or 'the passage'}:\n"
                  f"{moment['sentence']}\n\nScene: {moment['shot']}\n"
                  f"Characters: {', '.join(moment['characters'])}.\n"
                  f"Visual guidance: {prompt or 'Use a painterly storybook style.'}\n"
                  "Depict the selected moment. No text, captions or speech balloons.")

    # A brief either has Muse Image paint the scene or names an existing one.
    if brief.get("image"):
        with Image.open(os.path.join(base_dir, brief["image"])) as source:
            img = source.convert("RGB")
    else:
        img = paint(prompt, refs, brief.get("size", "1536x1024"), label)
    img.save(os.path.join(out, "scene.png"))
    W, H = img.size
    rgb = np.asarray(img)

    # SAM 3.1: one plain concept for every figure.
    found = []
    for conf, m in sorted(instances(segment(img, "person", f"{label} person"), img.size), key=lambda f: -f[0]):
        if conf < layers.MIN_CONF or m.mean() < layers.MIN_SHARE or any(layers.iou(m, k) > 0.6 for _, k in found):
            continue
        found.append((len(found) + 1, m))
    marks = [mk for mk, _ in found]
    marked = layers.marked_page(img, [[0, 0, W, H]], {0: found})
    marked.save(os.path.join(out, "marked.jpg"), quality=88)

    # Muse Wonder casts by number, with one corrective turn if it misplaces a mark.
    plan, _ = direct(marked, brief.get("shot", ""), brief.get("characters", []), marks, f"{label} cast")
    issues = problems(plan, marks)
    if issues:
        plan, _ = direct(marked, brief.get("shot", ""), brief.get("characters", []), marks, f"{label} cast retry", feedback="\n".join(issues))
    remaining = problems(plan, marks)
    if remaining:
        raise RuntimeError("Invalid casting: " + "; ".join(remaining))
    Path(out, "casting.json").write_text(json.dumps(plan, indent=1))
    cast = {f["mark"]: f for f in plan["figures"]}

    # Layers: each cast figure, the cast together, and the room behind them.
    union = np.zeros((H, W), bool)
    meta = []
    for mk, m in found:
        solid = layers.solid(m)
        if mk in cast:
            alpha = (layers.soft(solid) * 255).astype(np.uint8)
            c = np.dstack([rgb, alpha])
            Image.fromarray(c).save(os.path.join(out, f"cast-{mk}.png"), optimize=True)
            union |= solid
        edge = m & ~ndimage.binary_erosion(m, iterations=4)
        e = np.zeros((H, W, 4), np.uint8)
        e[edge] = (*layers.COLOURS[mk % len(layers.COLOURS)], 255)
        Image.fromarray(e).save(os.path.join(out, f"edge-{mk}.png"), optimize=True)
        ys, xs = np.nonzero(m)
        meta.append({"mark": mk, "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                     "cast": cast.get(mk), "colour": "#%02x%02x%02x" % layers.COLOURS[mk % len(layers.COLOURS)]})
    alpha = (layers.soft(union) * 255).astype(np.uint8)
    Image.fromarray(np.dstack([rgb, alpha])).save(os.path.join(out, "cast.png"), optimize=True)
    pl = plate(img, f"{label} plate")
    if pl is not None:
        near = ndimage.binary_dilation(union, iterations=6)
        room = rgb.copy()
        room[near] = np.asarray(pl)[near]
        Image.fromarray(room).save(os.path.join(out, "room.png"), optimize=True)
    Path(out, "marks.json").write_text(json.dumps({"w": W, "h": H, "marks": meta}, indent=1))
    # The standalone player consumes only this small, portable manifest.
    playable = {
        "title": brief.get("title") or brief.get("book") or label,
        "book": brief.get("book", ""), "caption": brief.get("shot", ""),
        "sentence": brief.get("sentence", ""), "width": W, "height": H,
        "image": "scene.png", "background": "room.png" if pl is not None else "scene.png",
        "marked": "marked.jpg",
        "layers": [{"name": item["cast"]["name"], "src": f"cast-{item['mark']}.png"}
                   for item in meta if item["cast"]] if pl is not None else [],
    }
    Path(out, "reel.json").write_text(json.dumps({
        "version": 1, "title": playable["title"],
        "provenance": "Generated with the Meta scene pipeline." if not brief.get("image") else
                      "Provided illustration, segmented and layered with the Meta scene pipeline.",
        "scenes": [playable],
    }, indent=2))
    print(f"{len(found)} figures, {len(cast)} cast, plate {'yes' if pl is not None else 'refused'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
