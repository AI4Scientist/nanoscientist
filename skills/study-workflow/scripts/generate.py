#!/usr/bin/env python3
"""Generate a research workflow diagram via the OpenRouter image API.

Usage:
    python generate.py --output PATH --draft TEXT
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path


def _build_prompt(draft: str) -> str:
    return f"""You are a scientific visualization expert producing publication-quality academic figures. Read the paper draft below and generate a study workflow diagram in the style of top-tier AI/ML conference papers (NeurIPS, ACL, CVPR, ICLR).

---

PAPER DRAFT:
{draft}

---

## Visual Style Reference

Match this exact visual language — the kind seen in papers like SkillShield, LightGBM routing studies, and SWE-bench analyses:

**Stage columns:**
- 3–5 vertical stage columns arranged left-to-right across a wide landscape canvas
- Each column has a bold colored header with a circled stage number badge (①②③...)
- Column header uses a distinct accent color (blue, orange, green, purple — one per stage)
- Column body is a rounded rectangle panel with light tint matching the header color
- Inside each panel: 1–2 labeled sub-sections with their own mini-panels or grouped content

**Icons:**
- Use recognizable flat/outline icons appropriate to the content: database cylinders for data, gears for processing, shield for safety, brain/robot for AI reasoning, bar chart for evaluation, tree for models, magnifying glass for analysis
- Place icons above or left of text labels inside panels
- Icons should be simple, consistent stroke width, not decorative

**Typography:**
- Stage title: bold, ~16pt, colored to match the stage accent
- Sub-section title: bold italic, ~11pt, accent color
- Body text: regular weight, ~9–10pt, dark gray
- Metric callouts: bold inline (e.g. "171 harnesses × 707 issues", "p = 0.0007", "20.4% improvement")
- Use the paper's exact terminology everywhere

**Arrows:**
- Thick solid arrows (same color as source stage) for main pipeline flow between columns
- Thin dashed arrows for secondary/feedback connections within a column
- Arrow tips are clean, filled triangles

**Color system — functional mapping:**
- Blue: data collection, inputs, corpus
- Orange: temporal analysis, processing, adaptation
- Green: model/evaluation, routing, core system
- Purple: analysis, output, results, importance
- Each stage owns one color; use it for header, border, icons, and accent text within that column

**Layout rules:**
- The diagram must be WIDE and HORIZONTAL — columns arranged left-to-right across a wide landscape canvas, NOT stacked vertically
- Equal-width columns with consistent gaps (~20px)
- Columns are tall relative to their width but the overall figure is much wider than it is tall
- No wasted whitespace at edges
- Strict grid alignment — no floating elements

**Absolute prohibitions:**
- No footer, caption, attribution, model name, watermark, or any text outside the diagram frame
- No gradients, drop shadows heavier than 2px, glow effects
- No full sentences — phrases and metric values only
- No generic placeholder labels

The output must be a single image: the diagram only, nothing else."""


def _load_env(project_root: Path) -> None:
    env_file = project_root / ".env"
    if env_file.exists() and "OPENROUTER_API_KEY" not in os.environ:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate research workflow diagram via OpenRouter image API")
    ap.add_argument("--output", required=True, help="Output PNG path")
    ap.add_argument("--draft", required=True, help="Full paper draft text")
    args = ap.parse_args()

    if not args.draft.strip():
        print("error: --draft is empty", file=sys.stderr)
        sys.exit(1)

    project_root = Path(__file__).resolve().parents[3]
    _load_env(project_root)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("error: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    prompt = _build_prompt(args.draft)

    import urllib.request
    payload = json.dumps({
        "model": "openai/dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1792x1024",
        "quality": "hd",
        "style": "natural",
        "response_format": "b64_json",
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/images/generations",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"error: API request failed — {e}", file=sys.stderr)
        sys.exit(1)

    try:
        b64 = data["data"][0]["b64_json"]
        if not b64:
            print(f"error: no image data in response — {str(data)[:300]}", file=sys.stderr)
            sys.exit(1)
    except (KeyError, IndexError) as e:
        print(f"error: unexpected response shape — {e}: {str(data)[:300]}", file=sys.stderr)
        sys.exit(1)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    print(args.output)


if __name__ == "__main__":
    main()
