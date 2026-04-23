#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai>=1.55",
#     "python-dotenv>=1.0",
# ]
# ///
"""PEP 723 skill shim — delegates to src/gpt_image_cli/cli.py.

This file exists so the skill can be invoked the canonical way:

    uv run $CLAUDE_PLUGIN_ROOT/skills/gpt-image/scripts/generate.py -p "…"

The real implementation lives in `src/gpt_image_cli/cli.py` at the repo root,
so the same code can be installed as a CLI via:

    uvx --from git+https://github.com/wuyoscar/gpt_image_2_skill gpt-image -p "…"

Keep the dependency list in sync with `pyproject.toml`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from gpt_image_cli.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
