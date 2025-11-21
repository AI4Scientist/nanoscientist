# MSR-Scientist

**A minimalist self-evolving researcher agent** inspired by [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) and [live-swe-agent](https://github.com/OpenAutoCoder/live-swe-agent).

MSR-Scientist is designed to conduct autonomous research by:
- 🧪 Generating hypotheses from research tasks
- 🔬 Designing and running experiments using Python and Linux tools
- 📊 Analyzing experimental results
- 📝 Writing research papers in LaTeX and compiling to PDF
- 🔧 Self-evolving: generating new tools on-the-fly as needed

## Philosophy

Following the mini-swe-agent design principles:

- **Radical Simplicity**: ~500 lines of core code
- **Linear History**: Transparent, debuggable message flow
- **Subprocess-based**: Easy sandboxing and deployment
- **Self-evolving**: Generate tools dynamically as research needs emerge
- **No Tool Dependencies**: Just bash, Python, and PyPI libraries

## Architecture

```
msr_scientist/
├── agent.py         # Core agent with LLM integration (~100 lines)
├── executor.py      # Code execution via subprocess (~100 lines)
├── tools.py         # Dynamic tool registry (~100 lines)
├── research.py      # Research workflow orchestration (~150 lines)
├── latex_writer.py  # LaTeX paper generation (~150 lines)
└── main.py          # CLI entry point (~50 lines)
```

## Installation

```bash
# Clone the repository
git clone https://github.com/zhimin-z/MSR-Scientist.git
cd MSR-Scientist

# Install dependencies
pip install -r requirements.txt

# Optional: Install for LaTeX paper compilation
sudo apt-get install texlive-latex-base  # On Ubuntu/Debian

# Install the package
pip install -e .
```

## Quick Start

### Command Line

```bash
# Set your API key
export OPENAI_API_KEY="your-key-here"
# or
export ANTHROPIC_API_KEY="your-key-here"

# Run a research task
msr-scientist "Investigate the performance of different sorting algorithms on various data distributions"

# With options
msr-scientist \
  "Study the impact of batch size on neural network training" \
  --model gpt-4 \
  --max-hypotheses 3 \
  --workspace ./my_research
```

### Python API

```python
from msr_scientist import ResearchAgent, ResearchWorkflow

# Create agent
agent = ResearchAgent(model="gpt-4", api_key="your-key")

# Create workflow
workflow = ResearchWorkflow(agent=agent, verbose=True)

# Conduct research
results = workflow.conduct_research(
    task="Analyze the efficiency of different caching strategies",
    max_hypotheses=3,
    generate_pdf=True
)

# Access results
print(f"Paper: {results['paper_pdf']}")
print(f"Workspace: {results['workspace']}")
```

## Features

### 1. Hypothesis Generation

The agent analyzes your research task and generates testable hypotheses:

```python
hypotheses = workflow.generate_hypotheses(
    "Compare machine learning model performance on imbalanced datasets"
)
# Returns: ["Hypothesis 1...", "Hypothesis 2...", ...]
```

### 2. Experimental Code Generation

For each hypothesis, the agent designs and runs experiments:

```python
experiment = workflow.design_experiment(hypotheses[0])
results = workflow.run_experiment(experiment)
```

The agent can:
- Install PyPI packages as needed
- Write Python code to test hypotheses
- Execute code safely via subprocess
- Collect and analyze results

### 3. LaTeX Paper Generation

Generate academic papers from research results:

```python
paper = workflow.generate_paper(
    task="Your research task",
    filename="paper.tex",
    compile=True  # Compile to PDF
)
# Returns: {"tex": "path/to/paper.tex", "pdf": "path/to/paper.pdf"}
```

Papers include:
- Introduction
- Hypotheses
- Methodology
- Results
- Conclusion

### 4. Self-Evolving Tools

Generate new tools on-the-fly during research:

```python
tool_name = workflow.generate_tool_on_fly(
    "Create a function to calculate statistical significance between two distributions"
)

# Use the generated tool
tool = workflow.tool_registry.get_tool(tool_name)
result = tool(data1, data2)
```

## Examples

### Example 1: Simple Research

```python
from msr_scientist import ResearchAgent, ResearchWorkflow

agent = ResearchAgent(model="gpt-4")
workflow = ResearchWorkflow(agent=agent)

results = workflow.conduct_research(
    task="Investigate sorting algorithm performance",
    max_hypotheses=2
)
```

See [`examples/simple_research.py`](examples/simple_research.py) for a complete example.

### Example 2: Self-Evolving Tools

```python
from msr_scientist import ResearchAgent, ResearchWorkflow

agent = ResearchAgent(model="gpt-4")
workflow = ResearchWorkflow(agent=agent)

# Generate a custom tool
tool_name = workflow.generate_tool_on_fly(
    "Create a function to detect outliers in a dataset"
)

# Use the tool
tool = workflow.tool_registry.get_tool(tool_name)
outliers = tool(my_data)
```

See [`examples/self_evolving_tool.py`](examples/self_evolving_tool.py) for details.

## How It Works

### Research Workflow

```
User Task
    ↓
1. Generate Hypotheses (LLM)
    ↓
2. For each hypothesis:
   - Design Experiment (LLM)
   - Generate Python Code (LLM)
   - Install Dependencies (pip)
   - Run Experiment (subprocess)
   - Collect Results
    ↓
3. Analyze All Results (LLM)
    ↓
4. Generate LaTeX Paper (LLM + pylatex)
    ↓
5. Compile to PDF (pdflatex)
```

### Self-Evolution

When the agent needs a capability that doesn't exist:

```
Agent identifies need
    ↓
Generate tool description
    ↓
LLM writes Python function
    ↓
Dynamic loading & registration
    ↓
Tool immediately available
```

## Design Principles

Following mini-swe-agent's philosophy:

1. **Minimalism**: ~500 lines of core code
2. **Transparency**: Linear message history, no hidden state
3. **Simplicity**: Subprocess-based execution, no complex abstractions
4. **Deployability**: Works in any Python environment
5. **Hackability**: Easy to understand and modify

## Configuration

### Supported Models

- **OpenAI**: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
- **Anthropic**: `claude-3-5-sonnet-20240620`, `claude-3-opus-20240229`

### Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Limitations

As a minimalist prototype, MSR-Scientist prioritizes simplicity over robustness:

- ⚠️ No retry logic or error recovery
- ⚠️ Basic experiment parsing (may fail on complex outputs)
- ⚠️ Limited security sandboxing (use with caution)
- ⚠️ Requires manual API key configuration
- ⚠️ LaTeX compilation requires system installation

This is intentional - the goal is a hackable foundation, not a production system.

## Roadmap

Future enhancements (keeping minimalism):

- [ ] Better experiment result parsing
- [ ] Multi-modal paper generation (figures, tables)
- [ ] Experiment reproducibility tracking
- [ ] Interactive research sessions
- [ ] Docker-based sandboxing
- [ ] Tool persistence across sessions

## Comparison

### vs mini-swe-agent
- **Same**: Linear history, subprocess execution, minimalist design
- **Different**: Research-focused instead of code-focused

### vs live-swe-agent
- **Same**: Self-evolving capabilities
- **Different**: Research workflow instead of issue resolution

## Contributing

Contributions welcome! Please keep the minimalist philosophy:

- Keep core code under 500 lines
- Maintain linear message history
- Prefer subprocess over libraries
- Document design decisions

## License

MIT License - see LICENSE file

## References

- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent): Minimalist SWE agent design
- [live-swe-agent](https://github.com/OpenAutoCoder/live-swe-agent): Self-evolving agent concept

## Citation

```bibtex
@software{msr_scientist2024,
  title={MSR-Scientist: A Minimalist Self-Evolving Researcher Agent},
  author={MSR-Scientist Contributors},
  year={2024},
  url={https://github.com/zhimin-z/MSR-Scientist}
}
```
