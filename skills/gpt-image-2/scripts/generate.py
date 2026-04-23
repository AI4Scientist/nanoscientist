#!/usr/bin/env python3
"""Image generation via openai/gpt-image-2 on OpenRouter."""
import argparse
import base64
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI


def _client() -> OpenAI:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("error: OPENROUTER_API_KEY not set.", file=sys.stderr)
        sys.exit(2)
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


def _auto_path(prompt: str, fmt: str, out_dir: Path) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower())[:40].strip("-")
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{ts}-{slug}.{fmt}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate images via openai/gpt-image-2 on OpenRouter")
    ap.add_argument("-p", "--prompt", required=True, help="Text prompt")
    ap.add_argument("-f", "--file", help="Output path (auto-named if omitted)")
    ap.add_argument("-n", "--n", type=int, default=1, help="Number of images")
    ap.add_argument("--model", default="openai/gpt-5.4-image-2", help="Model ID on OpenRouter")
    ap.add_argument("--size", default="1024x1024", help="Image size (e.g. 1024x1024, 1024x1536)")
    ap.add_argument("--quality", default="high", choices=["auto", "low", "medium", "high"])
    ap.add_argument("--format", dest="fmt", default="png", choices=["png", "jpeg", "webp"])
    ap.add_argument("--moderation", default=None, choices=["auto", "low"])
    args = ap.parse_args()

    client = _client()

    kwargs: dict = dict(
        model=args.model,
        prompt=args.prompt,
        n=args.n,
        size=args.size,
        quality=args.quality,
        response_format="b64_json",
        output_format=args.fmt,
    )
    if args.moderation:
        kwargs["moderation"] = args.moderation

    try:
        response = client.images.generate(**kwargs)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    cwd = Path.cwd()
    out_dir = cwd / "fig" if (cwd / "fig").exists() else cwd

    paths: list[str] = []
    for idx, item in enumerate(response.data):
        if args.file:
            dest = Path(args.file)
            if args.n > 1:
                dest = dest.with_stem(f"{dest.stem}_{idx}")
        else:
            dest = _auto_path(args.prompt, args.fmt, out_dir)
            if args.n > 1:
                dest = dest.with_stem(f"{dest.stem}_{idx}")

        if item.b64_json:
            dest.write_bytes(base64.b64decode(item.b64_json))
        elif item.url:
            import urllib.request
            urllib.request.urlretrieve(item.url, dest)
        else:
            print(f"error: no image data in response: {item}", file=sys.stderr)
            sys.exit(1)

        print(dest)
        paths.append(str(dest))

    sys.exit(0)


if __name__ == "__main__":
    main()
