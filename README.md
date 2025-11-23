# MSR-Scientist

**Ultra-minimal self-evolving researcher agent** (~200 lines, 1 file)

Inspired by [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) and [live-swe-agent](https://github.com/OpenAutoCoder/live-swe-agent).

## What it does

- 🧪 Generates testable hypotheses from research tasks
- 🔬 Designs and runs Python experiments
- 📝 Writes LaTeX research papers (compiles to PDF)
- 🔧 Self-evolving: generates tools on-the-fly

## Installation

```bash
pip install -r requirements.txt

# Optional: for PDF compilation
sudo apt-get install texlive-latex-base
```

## Usage

```python
from agent import ResearchAgent

agent = ResearchAgent(model="gpt-4")

results = agent.conduct_research(
    task="Your research question here",
    max_hypotheses=2
)

print(f"Paper: {results['paper_pdf']}")
```

Or run the example:

```bash
export OPENAI_API_KEY="sk-..."
python example.py
```

## Architecture

**Single file: `agent.py` (~200 lines)**

```python
class ResearchAgent:
    generate_hypotheses(task)      # Generate hypotheses from task
    design_experiment(hypothesis)   # Design experiment code
    run_experiment(experiment)      # Execute via subprocess
    generate_paper(...)             # Create LaTeX paper
    conduct_research(task)          # Full workflow
    generate_tool(description)      # Self-evolving tools
```

## Design Philosophy

Following mini-swe-agent:
- **Radical minimalism**: 1 file, ~200 lines
- **Linear history**: Simple message list
- **Subprocess execution**: No persistent state
- **Self-evolving**: Generate tools at runtime

## Workflow

```
Task → Hypotheses → Experiments → Results → Paper
```

All in ~200 lines.

## Example Output

```
[Research] Task: Compare sorting algorithms
[Research] Generating hypotheses...
  1. Quicksort is faster on random data
  2. Mergesort is more stable

[Research] Running 2 experiments...
  Experiment 1/2...
    ✓ Quicksort benchmark completed
  Experiment 2/2...
    ✓ Mergesort benchmark completed

[Research] Generating paper...
  LaTeX: /tmp/msr_xxx/paper.tex
  PDF: /tmp/msr_xxx/paper.pdf
```

## Supported Models

- OpenAI: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
- Anthropic: `claude-3-5-sonnet-20241022`

## License

MIT
