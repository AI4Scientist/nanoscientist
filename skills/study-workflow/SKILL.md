---
name: study-workflow
description: Generates a publication-quality research workflow diagram (two swim-lanes: Research and Writing) as a PNG file using gpt-image-2 (OpenRouter). Falls back to matplotlib if the API key is unavailable. Called internally by the pipeline to visualize the study plan.
required-keys: [OPENROUTER_API_KEY]
allowed-tools: Bash
---

This skill generates a visually rich research workflow diagram using `openai/gpt-5.4-image-2`
via OpenRouter. It is called internally by `_generate_workflow_diagram_async` in `src/nodes.py`
and writes `workflow.png` to the `figures/` subdirectory of the current output directory.

If `OPENROUTER_API_KEY` is not set or the API call fails, it falls back to a plain matplotlib diagram.
