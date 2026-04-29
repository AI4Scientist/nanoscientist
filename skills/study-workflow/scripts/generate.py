#!/usr/bin/env python3
"""Generate a research workflow diagram via the OpenRouter image API.

Usage:
    python generate.py --output PATH --draft TEXT
"""
import argparse
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _build_prompt(draft: str) -> str:
    return f"""You are a scientific visualization expert. Read the paper draft below and produce a publication-quality workflow figure in the style of top-tier AI/ML conference papers (NeurIPS, ACL, CVPR, ICLR).

---

PAPER DRAFT:
{draft}

---

## Global Layout Constraints (STRICT)

- The figure must span fully from the left edge to the right edge of the canvas
- Use the full horizontal width; do NOT compress into a centered block
- All stages must be arranged in a single horizontal row (left → right)
- Maintain generous vertical whitespace above and below (top/bottom margins ≥10%)
- Vertically center all content; no element may touch top/bottom margins
- Keep inter-stage spacing uniform and visually balanced

---

## Stage Panel Design

- Each stage is a rounded rectangle with:
  - **solid border (MANDATORY; never dashed)**
  - light tinted background (low saturation)
  - distinct accent color per stage (blue / orange / green / purple / teal)

- Header (top of each panel):
  - Format: "Stage X  TITLE"
  - Title in ALL CAPS, bold
  - Accent color applied to title and border
  - Optional count in parentheses allowed (e.g., "(56)") — but NO explanations of what it means

- Subtitle (1 short line under header):
  - concise phrase (≤8 words)
  - no full sentences

---

## Internal Structure (Within Each Stage)

Each stage must follow a **3-tier hierarchy**:

1. **Step Row (horizontal mini-boxes)**
   - Small rounded boxes labeled A, B, C...
   - Each contains a short phrase only
   - Solid borders only

2. **Strategy Blocks (main content boxes)**
   - Larger rounded rectangles below steps
   - Bullet-style entries with:
     - short label
     - optional numeric value
     - optional small icon (inline, right-aligned)

3. **NO verbose text**
   - Use phrases only
   - No explanatory sentences
   - No annotations like “numbers indicate …”

---

## Arrows & Flow Semantics

- Primary pipeline flow:
  - Thick **solid horizontal arrows** between stages
  - Positioned at vertical centerline

- Secondary relations (if needed):
  - Thin **dashed arrows**
  - ONLY for intra-stage or vertical linking
  - NEVER use dashed borders for boxes

---

## Legend (Bottom Row — STRICT FORMAT)

- Place a **single horizontal legend bar centered at the bottom**
- Must contain exactly three items:
  - Offline / Local
  - External / Online
  - Live / Production

- Layout:
  - Icons + labels arranged horizontally
  - Even spacing across width
  - Minimal, clean styling

- DO NOT include:
  - Any explanatory sentences
  - Any notes about counts or percentages

---

## Explicitly Forbidden Elements

- ❌ No dashed borders on any boxes
- ❌ No percentage callouts (e.g., "41.1% issues")
- ❌ No explanatory footnotes (e.g., "numbers in parentheses indicate...")
- ❌ No outer frame or enclosing border
- ❌ No title outside the panels
- ❌ No watermark or attribution
- ❌ No gradients, shadows, or glow effects

---

## Typography & Rendering

- Use crisp, high-resolution vector-like rendering
- Strong hierarchy:
  - Stage title: bold, largest
  - Step labels: medium bold
  - Content: regular
- Align text and icons cleanly; avoid clutter
- Ensure consistent spacing across all panels

---

## Output Requirement

- Output the **figure only**
- No captions, no explanations, no surrounding text
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate research workflow diagram via OpenRouter image API")
    ap.add_argument("--output", required=True, help="Output PNG path")
    ap.add_argument("--draft", required=True, help="Full paper draft text")
    args = ap.parse_args()

    if not args.draft.strip():
        print("error: --draft is empty", file=sys.stderr)
        sys.exit(1)

    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env", override=True)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("error: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    prompt = _build_prompt(args.draft)

    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-5.4-image-2",
            messages=[{"role": "user", "content": prompt}],
            extra_body={"modalities": ["image"], "image_config": {"aspect_ratio": "21:9", "image_size": "2K"}},
        )
    except Exception as e:
        print(f"error: API request failed — {e}", file=sys.stderr)
        sys.exit(1)

    try:
        msg = completion.choices[0].message
        images = getattr(msg, "images", None) or (msg.model_extra or {}).get("images") or []
        if not images:
            print(f"error: no image in response — {str(completion)[:300]}", file=sys.stderr)
            sys.exit(1)
        data_url = images[0]["image_url"]["url"]
        b64 = data_url.split(",", 1)[1]
    except (AttributeError, IndexError, ValueError) as e:
        print(f"error: unexpected response shape — {e}: {str(completion)[:300]}", file=sys.stderr)
        sys.exit(1)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))

    try:
        import numpy as np
        from PIL import Image
        from scipy import ndimage

        img = Image.open(out).convert("RGB")

        def content_bbox(img, white_thresh=240, min_area_ratio=0.0005):
            arr = np.array(img)
            non_white = np.any(arr < white_thresh, axis=-1)
            labeled, num = ndimage.label(non_white)
            if num == 0:
                return img
            h, w = non_white.shape
            min_area = h * w * min_area_ratio
            slices = ndimage.find_objects(labeled)
            boxes = []
            for i, slc in enumerate(slices):
                if slc is None:
                    continue
                region = (labeled[slc] == (i + 1))
                if region.sum() < min_area:
                    continue
                y0, y1 = slc[0].start, slc[0].stop
                x0, x1 = slc[1].start, slc[1].stop
                boxes.append((x0, y0, x1, y1))
            if not boxes:
                return img
            x0 = min(b[0] for b in boxes)
            y0 = min(b[1] for b in boxes)
            x1 = max(b[2] for b in boxes)
            y1 = max(b[3] for b in boxes)
            margin = int(0.08 * min(w, h))
            x0 = max(0, x0 - margin)
            y0 = max(0, y0 - margin)
            x1 = min(w, x1 + margin)
            y1 = min(h, y1 + margin)
            return img.crop((x0, y0, x1, y1))

        def add_padding(img):
            w, h = img.size
            pad = int(0.08 * min(w, h))
            new = Image.new("RGB", (w + pad * 2, h + pad * 2), (255, 255, 255))
            new.paste(img, (pad, pad))
            return new, pad

        def safe_crop_to_ratio(img, target=3.0, min_margin=40):
            w, h = img.size
            if w / h > target:
                new_w = int(h * target)
                left = (w - new_w) // 2
                return img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target)
                if h - new_h < 2 * min_margin:
                    return img
                top = (h - new_h) // 2
                return img.crop((0, top, w, top + new_h))

        img = content_bbox(img)
        img, pad = add_padding(img)
        img = safe_crop_to_ratio(img, 3.0, pad // 2)

        img.save(out)
    except Exception:
        pass  # if PIL/numpy/scipy unavailable, keep original

    print(args.output)


if __name__ == "__main__":
    main()
