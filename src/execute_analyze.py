"""execute_analyze.py - Stage 2: Execute & Analyze module

Wrapper around mini-swe-agent for code implementation and execution.
Reads research_proposal.md, sets up Docker workspace, executes experiments,
and generates workspace/README.md describing artifacts.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from minisweagent.agents.default import DefaultAgent
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.environments.local import LocalEnvironment


# Default Dockerfile template
DOCKERFILE_TEMPLATE = """FROM python:3.11-slim

WORKDIR /workspace

# Install dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy workspace contents
COPY . .

CMD ["python", "main.py"]
"""

# Default requirements (base packages)
DEFAULT_REQUIREMENTS = ["numpy", "pandas", "matplotlib"]


def parse_proposal_markdown(proposal_path: Path) -> Dict[str, Any]:
    """Parse research_proposal.md to extract plan information.

    Args:
        proposal_path: Path to research_proposal.md

    Returns:
        Dictionary with parsed plan data
    """
    content = proposal_path.read_text(encoding='utf-8')

    # Extract YAML frontmatter
    frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    metadata = {}
    if frontmatter_match:
        for line in frontmatter_match.group(1).split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

    # Extract title
    title_match = re.search(r'^# Research Proposal: (.+)$', content, re.MULTILINE)
    task = title_match.group(1) if title_match else "Research implementation"

    # Extract hypotheses
    hypotheses = []
    hypo_section = re.search(r'## Hypotheses\n+(.*?)(?=\n##|\n---|\Z)', content, re.DOTALL)
    if hypo_section:
        hypotheses = re.findall(r'^\d+\.\s+(.+)$', hypo_section.group(1), re.MULTILINE)

    # Extract methodology
    methodology = {"approach": "", "steps": [], "tools_needed": []}
    method_section = re.search(r'## Methodology\n+(.*?)(?=\n##|\n---|\Z)', content, re.DOTALL)
    if method_section:
        method_content = method_section.group(1)

        # Extract approach
        approach_match = re.search(r'\*\*Approach:\*\*\s*(.+?)(?=\n\*\*|\n\n|\Z)', method_content, re.DOTALL)
        if approach_match:
            methodology["approach"] = approach_match.group(1).strip()

        # Extract steps
        steps_section = re.search(r'\*\*Steps:\*\*\n+(.*?)(?=\n\*\*|\n\n\*\*|\Z)', method_content, re.DOTALL)
        if steps_section:
            methodology["steps"] = re.findall(r'^\d+\.\s+(.+)$', steps_section.group(1), re.MULTILINE)

        # Extract tools needed
        tools_section = re.search(r'\*\*Tools Needed:\*\*\n+(.*?)(?=\n##|\n\n##|\Z)', method_content, re.DOTALL)
        if tools_section:
            methodology["tools_needed"] = re.findall(r'^-\s+(.+)$', tools_section.group(1), re.MULTILINE)

    # Extract metrics
    metrics = {"primary": "", "secondary": []}
    metrics_section = re.search(r'## Metrics\n+(.*?)(?=\n##|\n---|\Z)', content, re.DOTALL)
    if metrics_section:
        metrics_content = metrics_section.group(1)

        primary_match = re.search(r'\*\*Primary:\*\*\s*(.+?)(?=\n|\Z)', metrics_content)
        if primary_match:
            metrics["primary"] = primary_match.group(1).strip()

        secondary_section = re.search(r'\*\*Secondary:\*\*\n+(.*?)(?=\n##|\n\n##|\Z)', metrics_content, re.DOTALL)
        if secondary_section:
            metrics["secondary"] = re.findall(r'^-\s+(.+)$', secondary_section.group(1), re.MULTILINE)

    # Extract citations for reference
    citations = []
    citations_section = re.search(r'## Citations\n+(.*?)(?=\n---|\Z)', content, re.DOTALL)
    if citations_section:
        # Parse citation lines: - **ref1**: Author (Year). "Title". ...
        citation_pattern = r'-\s+\*\*(\w+)\*\*:\s*(.+?)(?=\n-|\n\n|\Z)'
        for match in re.finditer(citation_pattern, citations_section.group(1), re.DOTALL):
            citations.append({
                "key": match.group(1),
                "text": match.group(2).strip()
            })

    # Extract background context
    background = ""
    bg_section = re.search(r'## Background Context\n+(.*?)(?=\n---|\Z)', content, re.DOTALL)
    if bg_section:
        background = bg_section.group(1).strip()

    return {
        "metadata": metadata,
        "task": task,
        "hypotheses": hypotheses,
        "methodology": methodology,
        "metrics": metrics,
        "citations": citations,
        "background": background
    }


def setup_workspace(workspace_path: Path, tools_needed: List[str]) -> None:
    """Setup workspace with Dockerfile, requirements.txt, and main.py.

    Args:
        workspace_path: Path to workspace directory
        tools_needed: List of Python packages from the proposal
    """
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Write Dockerfile
    dockerfile_path = workspace_path / "Dockerfile"
    dockerfile_path.write_text(DOCKERFILE_TEMPLATE, encoding='utf-8')

    # Write requirements.txt
    requirements = list(set(DEFAULT_REQUIREMENTS + tools_needed))
    requirements_path = workspace_path / "requirements.txt"
    requirements_path.write_text('\n'.join(requirements) + '\n', encoding='utf-8')

    # Write empty main.py
    main_py_path = workspace_path / "main.py"
    main_py_path.write_text('"""Main experiment script - implement your experiments here."""\n\n', encoding='utf-8')

    print(f"✓ Workspace setup complete: {workspace_path}")
    print(f"  - Dockerfile")
    print(f"  - requirements.txt ({len(requirements)} packages)")
    print(f"  - main.py (placeholder)")


def proposal_to_task_prompt(plan: Dict[str, Any]) -> str:
    """Convert parsed proposal to a natural language task for mini-swe-agent.

    Args:
        plan: Parsed proposal dictionary

    Returns:
        Natural language task description
    """
    hypotheses = plan.get("hypotheses", [])
    methodology = plan.get("methodology", {})
    approach = methodology.get("approach", "")
    steps = methodology.get("steps", [])
    tools_needed = methodology.get("tools_needed", [])
    metrics = plan.get("metrics", {})
    primary_metric = metrics.get("primary", "")
    secondary_metrics = metrics.get("secondary", [])
    background = plan.get("background", "")

    task_prompt = f"""Implement the following research plan:

RESEARCH TASK:
{plan.get("task", "Research implementation")}

BACKGROUND CONTEXT:
{background[:2000] if background else "See research proposal for details."}

HYPOTHESES TO TEST:
{chr(10).join(f"- {h}" for h in hypotheses)}

METHODOLOGY:
{approach}

IMPLEMENTATION STEPS:
{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(steps))}

REQUIRED TOOLS/PACKAGES (already in requirements.txt):
{chr(10).join(f"- {t}" for t in tools_needed) if tools_needed else "- numpy, pandas, matplotlib (defaults)"}

SUCCESS METRICS:
- Primary: {primary_metric}
{chr(10).join(f"- {m}" for m in secondary_metrics)}

REQUIREMENTS:
1. Implement all experiments in the current workspace
2. Use main.py as the entry point
3. Save any output files (figures, data, results) in the workspace
4. Generate visualizations where appropriate (save as PNG files)
5. Ensure all code is well-documented and runnable
6. Include proper error handling

When done, create a README.md describing:
- What scripts were created and their purpose
- What output files/artifacts were generated
- How to run the experiments
"""
    return task_prompt


def generate_readme(workspace_path: Path, result_text: str) -> str:
    """Generate README.md describing workspace artifacts.

    Args:
        workspace_path: Path to workspace directory
        result_text: Result text from agent execution

    Returns:
        Path to generated README.md
    """
    # Scan workspace for artifacts
    code_files = list(workspace_path.glob("*.py"))
    figure_files = list(workspace_path.glob("*.png")) + list(workspace_path.glob("*.jpg"))
    data_files = list(workspace_path.glob("*.json")) + list(workspace_path.glob("*.csv")) + list(workspace_path.glob("*.txt"))

    # Filter out setup files from code_files for description
    code_files = [f for f in code_files if f.name not in ['main.py'] or f.stat().st_size > 100]

    readme_content = """# Workspace Artifacts

This directory contains the implementation and results from Stage 2 (Execute & Analyze).

## Scripts

"""
    for f in code_files:
        readme_content += f"- `{f.name}`: "
        # Try to extract docstring or first comment
        try:
            content = f.read_text(encoding='utf-8')
            docstring_match = re.search(r'^"""(.+?)"""', content, re.DOTALL)
            if docstring_match:
                desc = docstring_match.group(1).strip().split('\n')[0]
                readme_content += desc
            else:
                readme_content += "Python script"
        except Exception:
            readme_content += "Python script"
        readme_content += "\n"

    if figure_files:
        readme_content += "\n## Figures\n\n"
        for f in figure_files:
            readme_content += f"- `{f.name}`: Generated visualization\n"

    if data_files:
        readme_content += "\n## Data Files\n\n"
        for f in data_files:
            readme_content += f"- `{f.name}`: "
            if f.suffix == '.json':
                readme_content += "JSON data"
            elif f.suffix == '.csv':
                readme_content += "CSV data"
            else:
                readme_content += "Text output"
            readme_content += "\n"

    readme_content += """
## Usage

To reproduce the experiments:

```bash
# Install dependencies
pip install -r requirements.txt

# Run main experiment
python main.py
```

## Docker

To run in an isolated environment:

```bash
docker build -t research-experiment .
docker run research-experiment
```
"""

    readme_path = workspace_path / "README.md"
    readme_path.write_text(readme_content, encoding='utf-8')

    return str(readme_path)


def run_implementation(
    proposal_file: str,
    workspace: str,
    model_name: str = "anthropic/claude-haiku-4-5-20251001",
    step_limit: int = 50,
    cost_limit: float = 2.0
) -> Dict[str, Any]:
    """Execute the implementation using mini-swe-agent.

    Args:
        proposal_file: Path to research_proposal.md
        workspace: Directory for code execution
        model_name: LLM model to use for mini-swe-agent
        step_limit: Maximum number of agent steps
        cost_limit: Maximum cost in USD

    Returns:
        Dictionary with execution results and metadata
    """
    # Load and parse research proposal
    proposal_path = Path(proposal_file)
    if not proposal_path.exists():
        raise FileNotFoundError(f"Proposal file not found: {proposal_file}")

    plan = parse_proposal_markdown(proposal_path)

    # Setup workspace with Docker files
    workspace_path = Path(workspace)
    tools_needed = plan.get("methodology", {}).get("tools_needed", [])
    setup_workspace(workspace_path, tools_needed)

    # Convert proposal to task
    task = proposal_to_task_prompt(plan)

    # Initialize mini-swe-agent
    agent = DefaultAgent(
        LitellmModel(model_name=model_name),
        LocalEnvironment(cwd=str(workspace_path)),
        step_limit=step_limit,
        cost_limit=cost_limit,
    )

    # Execute
    try:
        exit_status, result_text = agent.run(task)
    except Exception as e:
        return {
            "success": False,
            "exit_status": "Error",
            "error": str(e),
            "result_text": "",
            "workspace": str(workspace_path),
            "message_count": 0,
            "cost_usd": 0.0
        }

    # Generate README.md describing artifacts
    readme_path = generate_readme(workspace_path, result_text)
    print(f"✓ Generated {readme_path}")

    # Collect workspace info
    code_files = list(workspace_path.glob("*.py"))
    figure_files = list(workspace_path.glob("*.png")) + list(workspace_path.glob("*.jpg"))

    results = {
        "success": exit_status == "Submitted",
        "exit_status": exit_status,
        "result_text": result_text,
        "workspace": str(workspace_path),
        "readme_path": readme_path,
        "message_count": len(agent.messages) if hasattr(agent, 'messages') else 0,
        "cost_usd": getattr(agent.model, 'cost', 0.0) if hasattr(agent, 'model') else 0.0,
        "artifacts": {
            "code_files": [f.name for f in code_files],
            "figures": [f.name for f in figure_files]
        }
    }

    return results


def validate_results(results: Dict) -> tuple[bool, str]:
    """Validate execution results.

    Args:
        results: Results dictionary from run_implementation()

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not results.get("success", False):
        return False, f"Execution failed: {results.get('error', results.get('exit_status', 'Unknown error'))}"

    if results.get("exit_status") != "Submitted":
        return False, f"Agent did not complete successfully: {results.get('exit_status')}"

    # Check workspace has README
    workspace = Path(results.get("workspace", "."))
    readme = workspace / "README.md"
    if not readme.exists():
        return False, "No README.md generated in workspace"

    # Check workspace has code files beyond the placeholder
    code_files = list(workspace.glob("*.py"))
    if len(code_files) <= 1:  # Only main.py placeholder
        return False, "No implementation code generated"

    return True, "Valid"


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python execute_analyze.py <proposal_file> <workspace>")
        sys.exit(1)

    proposal_file = sys.argv[1]
    workspace = sys.argv[2]

    print(f"Running implementation from proposal: {proposal_file}")
    print(f"Workspace: {workspace}")

    results = run_implementation(proposal_file, workspace)

    print(f"\n{'='*60}")
    print(f"Execution Status: {results['exit_status']}")
    print(f"Success: {results['success']}")
    print(f"Cost: ${results.get('cost_usd', 0):.4f}")
    print(f"Messages: {results.get('message_count', 0)}")
    print(f"\nArtifacts:")
    for artifact_type, files in results.get("artifacts", {}).items():
        print(f"  {artifact_type}: {files}")
    print(f"{'='*60}\n")

    # Validate
    is_valid, msg = validate_results(results)
    if is_valid:
        print("✓ Results validated successfully")
    else:
        print(f"✗ Validation failed: {msg}")
