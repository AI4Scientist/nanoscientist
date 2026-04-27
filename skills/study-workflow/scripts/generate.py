#!/usr/bin/env python3
"""Generate a research workflow diagram via gpt-image-2 (OpenRouter).

Usage:
    python generate.py --output PATH --research-steps JSON_LIST --write-steps JSON_LIST --topic TITLE
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _build_prompt(topic: str, research_steps: list[str], write_steps: list[str]) -> str:
    r_bullets = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(research_steps))
    w_bullets = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(write_steps))

    return (
        f'Create a clean, publication-quality research workflow diagram for the topic: "{topic}". '
        "Style: academic infographic on a white background, bold sans-serif typography, "
        "flat design with subtle drop shadows, color-coded swim-lanes. "
        "Layout: two horizontal swim-lanes separated by a thin divider. "
        "Top lane labeled \"Research\" in deep blue (#2C5F8A), containing these numbered steps as rounded rectangles: "
        f"{r_bullets}. "
        "Bottom lane labeled \"Writing\" in forest green (#3A6E3A), containing these numbered steps as rounded rectangles: "
        f"{w_bullets}. "
        "Connect boxes within each lane with solid directional arrows. "
        "Add a vertical dashed arrow from the center of the Research lane down to the Writing lane to show knowledge transfer. "
        "Use deep blue (#4A90D9) fills with white text for Research boxes, "
        "forest green (#5BA55B) fills with white text for Writing boxes. "
        "Place the topic title centered above both lanes in bold dark gray. "
        "No extra decorations, no gradients, no clip art. Aspect ratio 3:2, landscape orientation. "
        "The result should look like a figure from a top-tier ML/NLP conference paper."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate research workflow diagram via gpt-image-2")
    ap.add_argument("--output", required=True, help="Output PNG path")
    ap.add_argument("--research-steps", required=True, help="JSON array of research step labels")
    ap.add_argument("--write-steps", required=True, help="JSON array of writing step labels")
    ap.add_argument("--topic", default="Research Workflow", help="Diagram title")
    args = ap.parse_args()

    try:
        research_steps = json.loads(args.research_steps)
        write_steps = json.loads(args.write_steps)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON — {e}", file=sys.stderr)
        sys.exit(1)

    if not research_steps:
        research_steps = ["Literature Survey", "Data Collection", "Analysis"]
    if not write_steps:
        write_steps = ["Introduction", "Methods", "Results", "Conclusion"]

    prompt = _build_prompt(args.topic, research_steps, write_steps)

    project_root = Path(__file__).resolve().parents[3]
    gpt_script = project_root / "skills" / "gpt-image-2" / "scripts" / "generate.py"

    # Load .env so OPENROUTER_API_KEY is available if not already set
    env_file = project_root / ".env"
    env = dict(os.environ)
    if env_file.exists() and "OPENROUTER_API_KEY" not in env:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable, str(gpt_script),
            "-p", prompt,
            "-f", args.output,
            "--size", "1536x1024",
            "--quality", "high",
        ],
        capture_output=True, text=True, errors="replace",
        timeout=120,
        env=env,
    )

    if result.returncode == 0 and Path(args.output).exists():
        print(args.output)
        sys.exit(0)

    print(f"[workflow] gpt-image-2 failed (exit={result.returncode}): {result.stderr[:500]}",
          file=sys.stderr)
    sys.exit(result.returncode or 1)


if __name__ == "__main__":
    main()
