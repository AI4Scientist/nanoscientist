"""Research workflow orchestration: hypothesis → experiments → paper."""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json

from .agent import ResearchAgent
from .executor import Executor
from .latex_writer import LatexPaperWriter
from .tools import get_tool_registry


class ResearchWorkflow:
    """Orchestrate research workflow with self-evolving capabilities."""

    def __init__(
        self,
        agent: ResearchAgent,
        workspace: str = None,
        verbose: bool = True
    ):
        """Initialize research workflow.

        Args:
            agent: Research agent instance
            workspace: Working directory
            verbose: Print detailed output
        """
        self.agent = agent
        self.executor = Executor(workspace)
        self.latex_writer = LatexPaperWriter(self.executor.workspace)
        self.tool_registry = get_tool_registry()
        self.verbose = verbose

        # Research state
        self.hypotheses: List[str] = []
        self.experiments: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []

    def log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"[Research] {message}")

    def generate_hypotheses(self, task: str) -> List[str]:
        """Generate research hypotheses from task.

        Args:
            task: Research task description

        Returns:
            List of hypotheses
        """
        self.log("Generating hypotheses...")

        prompt = f"""Research Task: {task}

Generate 2-4 testable hypotheses for this research task.
Format your response as a JSON list of hypothesis strings.
Example: ["Hypothesis 1", "Hypothesis 2", ...]

Only output the JSON list, nothing else."""

        response = self.agent.step(prompt)

        # Parse hypotheses from response
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                self.hypotheses = json.loads(json_match.group())
            else:
                # Fallback: treat each line as hypothesis
                self.hypotheses = [
                    line.strip().lstrip("- ").lstrip("* ").lstrip("1234567890. ")
                    for line in response.split("\n")
                    if line.strip() and not line.strip().startswith("{")
                ]
        except Exception as e:
            self.log(f"Failed to parse hypotheses: {e}")
            self.hypotheses = [response]

        self.log(f"Generated {len(self.hypotheses)} hypotheses")
        for i, h in enumerate(self.hypotheses, 1):
            self.log(f"  {i}. {h}")

        return self.hypotheses

    def design_experiment(self, hypothesis: str) -> Dict[str, Any]:
        """Design experiment for a hypothesis.

        Args:
            hypothesis: Hypothesis to test

        Returns:
            Experiment design dict
        """
        self.log(f"Designing experiment for: {hypothesis[:60]}...")

        prompt = f"""Hypothesis: {hypothesis}

Design a Python experiment to test this hypothesis.
Include:
1. Required libraries (pip install commands)
2. Python code to run the experiment
3. Expected output/metrics

Format as JSON:
{{
  "libraries": ["package1", "package2"],
  "code": "python code here",
  "description": "what this experiment does"
}}

Only output the JSON, nothing else."""

        response = self.agent.step(prompt)

        # Parse experiment design
        try:
            import re
            json_match = re.search(r'\{.*?\}', response, re.DOTALL)
            if json_match:
                experiment = json.loads(json_match.group())
            else:
                # Fallback: create basic experiment
                experiment = {
                    "libraries": [],
                    "code": response,
                    "description": f"Experiment for: {hypothesis}"
                }
        except Exception as e:
            self.log(f"Failed to parse experiment: {e}")
            experiment = {
                "libraries": [],
                "code": response,
                "description": f"Experiment for: {hypothesis}"
            }

        experiment["hypothesis"] = hypothesis
        self.experiments.append(experiment)

        return experiment

    def run_experiment(self, experiment: Dict[str, Any]) -> Dict[str, Any]:
        """Run an experiment and collect results.

        Args:
            experiment: Experiment design

        Returns:
            Results dict
        """
        self.log(f"Running experiment: {experiment.get('description', 'Unknown')[:60]}...")

        # Install libraries if needed
        for lib in experiment.get("libraries", []):
            self.log(f"  Installing {lib}...")
            result = self.executor.execute_bash(f"pip install -q {lib}")
            if not result["success"]:
                self.log(f"  Warning: Failed to install {lib}")

        # Run experiment code
        code = experiment.get("code", "")
        result = self.executor.execute_python(code, timeout=60)

        # Store results
        experiment_result = {
            "hypothesis": experiment.get("hypothesis"),
            "description": experiment.get("description"),
            "success": result["success"],
            "output": result["stdout"],
            "error": result["stderr"]
        }

        self.results.append(experiment_result)
        self.log(f"  Success: {result['success']}")

        return experiment_result

    def generate_paper(
        self,
        task: str,
        filename: str = "paper.tex",
        compile: bool = True
    ) -> Dict[str, Optional[str]]:
        """Generate research paper from results.

        Args:
            task: Original research task
            filename: Output filename
            compile: Whether to compile to PDF

        Returns:
            Dict with 'tex' and 'pdf' paths
        """
        self.log("Generating research paper...")

        prompt = f"""Research Task: {task}

Hypotheses tested:
{chr(10).join(f"{i+1}. {h}" for i, h in enumerate(self.hypotheses))}

Experimental results:
{json.dumps(self.results, indent=2)}

Write a research paper in LaTeX format with:
1. Introduction (research task and motivation)
2. Hypotheses (list the hypotheses)
3. Methodology (experiments conducted)
4. Results (findings from experiments)
5. Conclusion (summary and implications)

Use proper LaTeX formatting. Output only the paper content for sections, not the full LaTeX document structure."""

        response = self.agent.step(prompt)

        # Create paper
        result = self.latex_writer.create_quick_paper(
            title=f"Research Report: {task[:50]}",
            content=response,
            filename=filename,
            compile=compile
        )

        if result["tex"]:
            self.log(f"Paper generated: {result['tex']}")
        if result["pdf"]:
            self.log(f"PDF compiled: {result['pdf']}")

        return result

    def conduct_research(
        self,
        task: str,
        max_hypotheses: int = 3,
        generate_pdf: bool = True
    ) -> Dict[str, Any]:
        """Full research workflow: hypotheses → experiments → paper.

        Args:
            task: Research task description
            max_hypotheses: Maximum hypotheses to test
            generate_pdf: Whether to generate PDF paper

        Returns:
            Research results including paper paths
        """
        self.log(f"Starting research: {task}\n")

        # 1. Generate hypotheses
        hypotheses = self.generate_hypotheses(task)
        hypotheses = hypotheses[:max_hypotheses]  # Limit number

        # 2. Design and run experiments
        for hypothesis in hypotheses:
            experiment = self.design_experiment(hypothesis)
            self.run_experiment(experiment)

        # 3. Generate paper
        paper = self.generate_paper(task, compile=generate_pdf)

        return {
            "task": task,
            "hypotheses": self.hypotheses,
            "experiments": self.experiments,
            "results": self.results,
            "paper_tex": paper.get("tex"),
            "paper_pdf": paper.get("pdf"),
            "workspace": self.executor.workspace
        }

    def generate_tool_on_fly(self, tool_description: str) -> str:
        """Generate a new tool based on description (self-evolving).

        Args:
            tool_description: Description of needed tool

        Returns:
            Generated tool name
        """
        self.log(f"Generating tool: {tool_description}")

        prompt = f"""Generate a Python function for this tool:
{tool_description}

Output only the Python function code, nothing else.
The function should be self-contained and properly documented."""

        response = self.agent.step(prompt)

        # Extract function name
        import re
        func_match = re.search(r'def\s+(\w+)\s*\(', response)
        if not func_match:
            raise ValueError("Could not find function definition in generated code")

        tool_name = func_match.group(1)

        # Register the tool
        self.tool_registry.generate_tool(tool_name, response)
        self.log(f"Tool '{tool_name}' generated and registered")

        return tool_name
