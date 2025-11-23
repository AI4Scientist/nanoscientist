"""MSR-Scientist: Minimalist self-evolving researcher agent (~200 lines)."""

import os
import subprocess
import tempfile
import json
import re
from pathlib import Path


class ResearchAgent:
    """Mini researcher agent with hypothesis → experiments → paper workflow."""

    def __init__(self, model="gpt-4", api_key=None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.messages = []
        self.workspace = tempfile.mkdtemp(prefix="msr_")

    def _call_llm(self, prompt):
        """Call LLM and return response."""
        self.messages.append({"role": "user", "content": prompt})

        if "claude" in self.model.lower():
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system="You are a research scientist. Generate hypotheses, design experiments, analyze results, and write papers.",
                messages=self.messages
            )
            content = response.content[0].text
        else:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a research scientist."}] + self.messages
            )
            content = response.choices[0].message.content

        self.messages.append({"role": "assistant", "content": content})
        return content

    def _exec(self, code, timeout=60):
        """Execute Python code and return output."""
        script = Path(self.workspace) / "exp.py"
        script.write_text(code)
        try:
            result = subprocess.run(
                ["python", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.workspace
            )
            return {"output": result.stdout, "error": result.stderr, "success": result.returncode == 0}
        except subprocess.TimeoutExpired:
            return {"output": "", "error": "Timeout", "success": False}

    def generate_hypotheses(self, task):
        """Generate research hypotheses."""
        prompt = f"""Research Task: {task}

Generate 2-3 testable hypotheses as a JSON array.
Output ONLY the JSON array, nothing else.
Example: ["Hypothesis 1", "Hypothesis 2"]"""

        response = self._call_llm(prompt)
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        return json.loads(match.group()) if match else [response]

    def design_experiment(self, hypothesis):
        """Design experiment for hypothesis."""
        prompt = f"""Hypothesis: {hypothesis}

Design a Python experiment to test this. Output as JSON:
{{
  "code": "import numpy as np\\nprint('result')",
  "packages": ["numpy"],
  "description": "What this tests"
}}

Output ONLY JSON."""

        response = self._call_llm(prompt)
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        return json.loads(match.group()) if match else {"code": response, "packages": [], "description": hypothesis}

    def run_experiment(self, experiment):
        """Run experiment and collect results."""
        # Install packages
        for pkg in experiment.get("packages", []):
            subprocess.run(["pip", "install", "-q", pkg], cwd=self.workspace)

        # Run code
        result = self._exec(experiment["code"])
        return {
            "description": experiment.get("description"),
            "output": result["output"],
            "error": result["error"],
            "success": result["success"]
        }

    def generate_paper(self, task, hypotheses, results):
        """Generate LaTeX paper."""
        prompt = f"""Research Task: {task}

Hypotheses:
{chr(10).join(f'{i+1}. {h}' for i, h in enumerate(hypotheses))}

Results:
{json.dumps(results, indent=2)}

Write a research paper in LaTeX with these sections:
1. Introduction
2. Hypotheses
3. Methodology
4. Results
5. Conclusion

Output ONLY the complete LaTeX document starting with \\documentclass."""

        latex = self._call_llm(prompt)

        # Extract LaTeX if wrapped in code blocks
        match = re.search(r'\\documentclass.*\\end\{document\}', latex, re.DOTALL)
        if match:
            latex = match.group()

        # Save
        tex_file = Path(self.workspace) / "paper.tex"
        tex_file.write_text(latex)

        # Try to compile
        try:
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "paper.tex"],
                cwd=self.workspace,
                capture_output=True,
                timeout=60
            )
            pdf_file = Path(self.workspace) / "paper.pdf"
            if pdf_file.exists():
                return str(tex_file), str(pdf_file)
        except:
            pass

        return str(tex_file), None

    def conduct_research(self, task, max_hypotheses=2):
        """Full research workflow."""
        print(f"[Research] Task: {task}\n")

        # 1. Generate hypotheses
        print("[Research] Generating hypotheses...")
        hypotheses = self.generate_hypotheses(task)[:max_hypotheses]
        for i, h in enumerate(hypotheses, 1):
            print(f"  {i}. {h[:80]}...")

        # 2. Run experiments
        print(f"\n[Research] Running {len(hypotheses)} experiments...")
        results = []
        for i, hyp in enumerate(hypotheses, 1):
            print(f"  Experiment {i}/{len(hypotheses)}...")
            exp = self.design_experiment(hyp)
            res = self.run_experiment(exp)
            results.append(res)
            print(f"    → {'✓' if res['success'] else '✗'} {res.get('description', '')[:60]}")

        # 3. Generate paper
        print("\n[Research] Generating paper...")
        tex, pdf = self.generate_paper(task, hypotheses, results)
        print(f"  LaTeX: {tex}")
        if pdf:
            print(f"  PDF: {pdf}")

        return {
            "task": task,
            "hypotheses": hypotheses,
            "results": results,
            "paper_tex": tex,
            "paper_pdf": pdf,
            "workspace": self.workspace
        }

    def generate_tool(self, description):
        """Self-evolving: generate a tool on-the-fly."""
        prompt = f"""Generate a Python function for: {description}

Output ONLY the Python function code, nothing else."""

        code = self._call_llm(prompt)

        # Extract function
        match = re.search(r'def\s+(\w+)', code)
        if not match:
            raise ValueError("No function found")

        func_name = match.group(1)

        # Save and import
        tool_file = Path(self.workspace) / f"tool_{func_name}.py"
        tool_file.write_text(code)

        import importlib.util
        spec = importlib.util.spec_from_file_location(func_name, tool_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return getattr(module, func_name)
