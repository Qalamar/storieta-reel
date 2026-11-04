"""Combine generated scene manifests: python -m reel.playlist <output.json> <reel.json>..."""
import json
import os
import sys
from pathlib import Path


def combine(output, inputs):
    output = Path(output).resolve()
    scenes = []
    provenance = []
    for source in inputs:
        source = Path(source).resolve()
        manifest = json.loads(source.read_text())
        if manifest.get('version') != 1 or not manifest.get('scenes'):
            raise ValueError(f'Invalid scene manifest: {source}')
        for scene in manifest['scenes']:
            scene = {**scene, 'layers': [dict(layer) for layer in scene['layers']]}
            for key in ('image', 'background', 'marked'):
                if scene.get(key):
                    path = (source.parent / scene[key]).resolve()
                    if not path.is_file():
                        raise FileNotFoundError(path)
                    scene[key] = Path(os.path.relpath(path, output.parent)).as_posix()
            for layer in scene['layers']:
                path = (source.parent / layer['src']).resolve()
                if not path.is_file():
                    raise FileNotFoundError(path)
                layer['src'] = Path(os.path.relpath(path, output.parent)).as_posix()
            scenes.append(scene)
        if manifest.get('provenance') and manifest['provenance'] not in provenance:
            provenance.append(manifest['provenance'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'version': 1, 'title': 'Scene collection', 'provenance': ' '.join(provenance), 'scenes': scenes}, indent=2) + '\n')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    combine(sys.argv[1], sys.argv[2:])
