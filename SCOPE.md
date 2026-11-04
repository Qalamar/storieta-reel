# Scope and provenance

Storieta is an existing illustrated-fiction product. This repository is a standalone demonstration of the Meta model workflow used for the reels project.

## Included implementation

- Muse Wonder selects a sentence, scene description, and characters from a passage.
- Muse Image generates the scene, optionally using reference images.
- SAM 3.1 returns figure masks; Muse Wonder matches numbered masks to the cast.
- Muse Image generates a background plate; the demo exports PNG layers.
- A standalone browser player loads exported manifests, animates depth, switches scenes, and exposes layer controls and a scene wall.
- Local caching, cost estimates, and mocked integration tests support the workflow.

## Existing product and presentation assets

The Storieta application, catalog, reader, deployment, export formats, and full reel player are outside this repository. Recordings show the product experience and are not evidence that every visible product feature was created during the hackathon. Some recordings use earlier iterations of the workflow and may differ from a fresh run of this demo. The three bundled sample scenes are archived artwork and layers from that earlier workflow, not newly generated evidence for the current model pipeline. Only the image layers and small presentation manifest are included; production scripts and data formats are excluded.

The new standalone player is a demonstration adapter added during repository preparation. It should not be represented as the original production player or as proof of when a feature was built.

## Repository history

This repository was reduced from a larger project extract and its Git history was replaced for publication. The new initial commit records packaging, not the original development date. The standalone extraction and later fixes must be distinguished from the work completed during the event in the submission description.
