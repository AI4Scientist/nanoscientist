# mini-researcher-agent

**An autonomous research agent using [smolagents](https://github.com/huggingface/smolagents) that conducts end-to-end research projects.**

```
RESEARCH → EXECUTE → REPORT
```

## Features

- **Deep web research** - Tavily/Perplexity-powered literature search with citation extraction
- **Autonomous experimentation** - Docker-ready workspace with mini-swe-agent execution
- **Academic paper generation** - ACM Conference template with proper BibTeX citations
- **Markdown-first workflow** - All intermediate files use markdown for transparency

## Installation

```bash
# Install dependencies with uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
uv run install-tectonic

# Or use the quick setup script
./setup.sh
```

**Configure API keys** - Create a `.env` file:
```bash
# Required (pick based on your model provider)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
HF_TOKEN=your_huggingface_token

# Search API (one required)
TAVILY_API_KEY=your_tavily_key
# or PERPLEXITY_API_KEY=your_perplexity_key
```

## Quick Start

```bash
python src/main.py "Compare sorting algorithms and analyze performance"
```

The agent autonomously:
1. Researches the topic and generates a proposal with citations
2. Implements experiments in a Docker-ready workspace
3. Generates an ACM-formatted PDF report

## Pipeline

### Stage 1: Research & Planning
- Web search with Tavily or Perplexity
- Generates `research_proposal.md` containing:
  - Hypotheses, methodology, metrics
  - Citations in `[@ref]` format
  - Background context from literature

### Stage 2: Execute & Analyze
- Parses proposal and sets up workspace with:
  - `Dockerfile` for reproducible environment
  - `requirements.txt` with needed packages
  - `main.py` entry point
- Executes experiments using mini-swe-agent
- Generates `workspace/README.md` describing artifacts

### Stage 3: Report Generation
- Reads proposal and workspace artifacts
- Converts `[@ref]` citations to LaTeX `\cite{ref}`
- Uses ACM Conference Proceedings template
- Outputs professional PDF via Tectonic

## Architecture

```
mini-researcher-agent/
├── src/
│   ├── main.py            # Orchestrator with smolagents CodeAgent
│   ├── research_plan.py   # Stage 1: Web research & proposal generation
│   ├── execute_analyze.py # Stage 2: Experiment implementation
│   ├── report_write.py    # Stage 3: PDF report generation
│   └── config.py          # Centralized configuration
├── research_template/     # ACM Conference template
├── research_outputs/      # Generated task outputs
│   └── task_<id>/
│       ├── research_proposal.md
│       ├── workspace/
│       │   ├── Dockerfile
│       │   ├── requirements.txt
│       │   ├── main.py
│       │   ├── README.md
│       │   └── *.png, *.csv, ...
│       └── report/
│           ├── main.tex
│           ├── reference.bib
│           └── main.pdf
└── docs/plans/            # Design documents
```

## Configuration

Environment variables for model selection:

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_MODEL` | Main orchestrator model | claude-haiku |
| `STAGE1_MODEL` | Research phase model | claude-haiku |
| `STAGE1_MAX_LOOPS` | Research iterations | 3 |
| `STAGE1_SEARCH_API` | Search API (tavily/perplexity) | tavily |
| `STAGE2_MODEL` | Execution phase model | claude-haiku |
| `STAGE2_STEP_LIMIT` | Max coding steps | 50 |
| `STAGE2_COST_LIMIT` | Max cost in USD | 2.0 |
| `STAGE3_MODEL` | Report phase model | claude-haiku |

## Requirements

- Python 3.10+
- LLM API key (OpenAI, Anthropic, or HuggingFace)
- Tavily or Perplexity API for web search
- Tectonic (auto-installed for PDF compilation)

## License

Apache-2.0

## Inspired By

- [mini-swe-agent](https://github.com/princeton-nlp/SWE-agent)
- [smolagents](https://github.com/huggingface/smolagents)
