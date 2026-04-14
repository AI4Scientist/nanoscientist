"""PocketFlow nodes for the Autonomous Scientist agent."""

import os
import re
import subprocess
import uuid
from collections import Counter
from pathlib import Path

from pocketflow import Node

from .utils import (
    call_llm,
    format_skill_index,
    format_available_keys,
    load_skill_content,
    load_quality_standard,
    parse_yaml_response,
    extract_bibtex,
    dedup_bibtex,
    track_cost,
)

# ---------------------------------------------------------------------------
# Budget reserves — enough for WriteTeX + CompileTeX + one FixTeX round
# ---------------------------------------------------------------------------
BUDGET_RESERVE = 0.03  # dollars


# ---------------------------------------------------------------------------
# LaTeX skeleton — hardcoded, known-compilable with pdflatex + natbib
# ---------------------------------------------------------------------------
LATEX_SKELETON = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\graphicspath{{./figures/}}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage[numbers,sort&compress]{natbib}
\usepackage{xcolor}

\title{%% TITLE %%}
\author{Autonomous Scientist Agent}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
%% ABSTRACT %%
\end{abstract}

%% BODY %%

\bibliographystyle{unsrtnat}
\bibliography{references}

\end{document}
"""


# ===================================================================
# 1. BudgetPlanner
# ===================================================================
class BudgetPlanner(Node):
    """Analyze topic + budget → produce a prioritized research plan."""

    def prep(self, shared):
        return {
            "topic": shared["topic"],
            "budget": shared["budget_dollars"],
            "skills": format_skill_index(shared["skill_index"]),
            "quality_standard": shared.get("quality_standard", ""),
            "api_keys": format_available_keys(shared.get("api_keys", {})),
        }

    def exec(self, prep_res):
        # Extract adaptive structure section from quality standard if available
        quality_guidance = ""
        qs = prep_res["quality_standard"]
        if qs:
            # Pull Section 2.3 (adaptive structure) and Section 4 (citation quality)
            import re as _re
            adaptive = _re.search(
                r"### 2\.3 Adaptive Structure by Report Type.*?(?=\n## |\n### [^2]|\Z)",
                qs, _re.DOTALL,
            )
            citation = _re.search(
                r"## 4\. Citation Quality.*?(?=\n## [^4]|\Z)",
                qs, _re.DOTALL,
            )
            parts = []
            if adaptive:
                parts.append(adaptive.group(0).strip())
            if citation:
                parts.append(citation.group(0).strip())
            if parts:
                quality_guidance = "\n\n## Paper Quality Standard (excerpt)\n" + "\n\n".join(parts)

        # Compute approximate affordable steps and report tier
        affordable = max(1, int((prep_res["budget"] - 0.03) / 0.005))
        if prep_res["budget"] < 0.10:
            tier = "Quick Summary — 1-2 skills"
        elif prep_res["budget"] < 0.50:
            tier = "Literature Review — 3-6 skills"
        elif prep_res["budget"] < 2.00:
            tier = "Research Report — 10-20 skills"
        elif prep_res["budget"] < 5.00:
            tier = "Full Paper — 30-50 skills"
        else:
            tier = "Full Paper — 50+ skills, exhaustive coverage"

        prompt = f"""You are a research planning assistant. Produce an ordered skill execution plan for the given topic and budget.

## Topic
{prep_res["topic"]}

## Budget: ${prep_res["budget"]:.2f} (~{affordable} skill calls at $0.005 each; reserve $0.03 for report)
## Target: {tier}

## Available API Keys
{prep_res["api_keys"]}

## Available Skills
{prep_res["skills"]}

## Rules
- Only plan skills whose required API keys are available.
- Use research-lookup multiple times with different subtopic queries.
- Use literature-review, data-visualization, statistical-analysis multiple times for depth.
- Plan enough steps to use ≥70% of the budget.
{quality_guidance}

## Instructions
Produce a YAML plan. Each step: step number, skill name, short reason. Reserve $0.03 for the final report.

```yaml
domain: <one-line topic classification>
report_type: <Quick Summary | Literature Review | Research Report | Full Paper>
plan:
  - step: 1
    skill: <skill-name>
    reason: <why this step>
  - step: 2
    skill: <skill-name>
    reason: <why this step>
```"""
        text, usage = call_llm(prompt)
        # Validate YAML parsing inside exec so PocketFlow retries on failure
        parsed = parse_yaml_response(text)
        if not parsed or not isinstance(parsed.get("plan"), list) or len(parsed["plan"]) == 0:
            print(f"[BudgetPlanner] YAML parse failed or empty plan, retrying... Raw response:")
            print(text[:500])
            raise ValueError("BudgetPlanner: LLM returned invalid or empty YAML plan")
        return text, usage, parsed

    def post(self, shared, prep_res, exec_res):
        text, usage, parsed = exec_res
        track_cost(shared, "budget_planner", usage)

        shared["plan"] = parsed.get("plan", [])
        shared["domain"] = parsed.get("domain", "general")
        shared["report_type"] = parsed.get("report_type", "Literature Review")
        shared["budget_remaining"] = shared["budget_dollars"] - usage["cost"]
        shared["artifacts"] = {}
        shared["bibtex_entries"] = []
        shared["history"] = []
        shared["fix_attempts"] = 0

        # Create task directory early so all phases can persist intermediaries
        task_id = str(uuid.uuid4())
        out_dir = Path(shared.get("output_dir", "outputs")) / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "artifacts").mkdir(exist_ok=True)
        (out_dir / "figures").mkdir(exist_ok=True)
        (out_dir / "data").mkdir(exist_ok=True)
        (out_dir / "scripts").mkdir(exist_ok=True)
        shared["output_path"] = str(out_dir)

        # Persist plan
        import yaml as _yaml
        plan_data = {
            "task_id": task_id,
            "topic": shared["topic"],
            "domain": shared["domain"],
            "report_type": shared["report_type"],
            "budget_dollars": shared["budget_dollars"],
            "plan": shared["plan"],
        }
        (out_dir / "plan.yaml").write_text(
            _yaml.dump(plan_data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

        print(f"[BudgetPlanner] Task directory: {out_dir}")
        print(f"[BudgetPlanner] Domain: {shared['domain']}")
        print(f"[BudgetPlanner] Report type: {shared['report_type']}")
        print(f"[BudgetPlanner] Plan: {len(shared['plan'])} steps")
        for s in shared["plan"]:
            print(f"  {s['step']}. {s['skill']} — {s.get('reason', '')}")
        print(f"[BudgetPlanner] Budget remaining: ${shared['budget_remaining']:.4f}")
        return "execute"


# ===================================================================
# 2. DecideNext — the agent core
# ===================================================================
class DecideNext(Node):
    """Pick the next skill to execute or decide to write the report."""

    def prep(self, shared):
        # Build compact history summary
        history_lines = []
        for h in shared.get("history", []):
            history_lines.append(f"- {h['skill']}: {h['summary']} (${h['cost']:.4f})")
        history_text = "\n".join(history_lines) if history_lines else "None yet."

        # Remaining plan steps — count-based to preserve duplicate skills
        exec_counts = Counter(h["skill"] for h in shared.get("history", []))
        remaining = []
        skill_seen = Counter()
        for s in shared.get("plan", []):
            skill = s["skill"]
            skill_seen[skill] += 1
            if skill_seen[skill] > exec_counts.get(skill, 0):
                remaining.append(s)

        # Check figure status for contextual nudging
        out_dir = Path(shared.get("output_path", ""))
        figures_dir = out_dir / "figures"
        has_figures = (figures_dir.is_dir()
                       and any(f.suffix.lower() in (".png", ".pdf", ".jpg", ".jpeg")
                               for f in figures_dir.iterdir())) if figures_dir.exists() else False
        has_data = bool(shared.get("generated_files", {}))

        return {
            "topic": shared["topic"],
            "remaining_plan": remaining,
            "history": history_text,
            "budget_remaining": shared.get("budget_remaining", 0),
            "artifact_keys": list(shared.get("artifacts", {}).keys()),
            "available_skills": format_skill_index(shared["skill_index"]),
            "has_figures": has_figures,
            "has_data": has_data,
        }

    def exec(self, prep_res):
        # Force write_tex if budget is too low
        if prep_res["budget_remaining"] < BUDGET_RESERVE:
            return {"action": "write_tex", "reason": "budget exhausted"}, {"input_tokens": 0, "output_tokens": 0, "cost": 0}

        remaining_yaml = "\n".join(
            f"  - {s['skill']}: {s.get('reason', '')}"
            for s in prep_res["remaining_plan"]
        ) if prep_res["remaining_plan"] else "All planned steps completed."

        # Calculate how many more skill calls the budget can support
        cost_per_skill = 0.005  # conservative estimate
        usable_budget = prep_res["budget_remaining"] - BUDGET_RESERVE
        affordable_steps = max(0, int(usable_budget / cost_per_skill))

        # Contextual nudge: if data exists but no figures yet
        figure_nudge = ""
        if prep_res["has_data"] and not prep_res["has_figures"]:
            figure_nudge = "\n**NOTE**: Data files exist but NO figures have been generated yet. Strongly consider running data-visualization before writing.\n"

        prompt = f"""You are the decision engine of an autonomous research agent.

## Topic: {prep_res["topic"]}
## Budget remaining: ${prep_res["budget_remaining"]:.4f} (~{affordable_steps} more skill calls; reserve $0.03)
## Artifacts: {', '.join(prep_res["artifact_keys"]) if prep_res["artifact_keys"] else 'none'}
{figure_nudge}
## Completed steps
{prep_res["history"]}

## Remaining planned steps
{remaining_yaml}

## Available skills (for unplanned deepening)
{prep_res["available_skills"]}

## Rules
- If planned steps remain → execute the next one ("execute_skill").
- If plan done but ≥10 affordable calls remain → add a deepening skill ("execute_skill").
- Write the report ("write_tex") only when <10 affordable calls remain OR budget >70% used AND sufficient material exists.
- Never stop early with substantial budget remaining.

Return YAML:
```yaml
action: execute_skill OR write_tex
skill: <skill-name>
reason: <brief reason>
```"""
        text, usage = call_llm(prompt)
        parsed = parse_yaml_response(text)
        return parsed, usage

    def post(self, shared, prep_res, exec_res):
        decision, usage = exec_res
        track_cost(shared, "decide_next", usage)

        if not decision or not isinstance(decision, dict):
            print("[DecideNext] WARNING: Failed to parse LLM response, defaulting to next plan step")
            remaining = prep_res.get("remaining_plan", [])
            if remaining:
                decision = {"action": "execute_skill", "skill": remaining[0]["skill"], "reason": "parse fallback"}
            else:
                decision = {"action": "write_tex", "reason": "parse fallback — no remaining steps"}

        action = decision.get("action", "write_tex")
        reason = decision.get("reason", "")
        print(f"[DecideNext] Action: {action} — {reason}")
        print(f"[DecideNext] Budget remaining: ${shared['budget_remaining']:.4f}")

        # Persist decision log to task directory
        shared.setdefault("decisions", []).append({
            "action": action,
            "skill": decision.get("skill", ""),
            "reason": reason,
            "budget_remaining": shared["budget_remaining"],
        })
        import json as _json
        out_dir = Path(shared["output_path"])
        (out_dir / "decisions.json").write_text(
            _json.dumps(shared["decisions"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Budget guard — too low → write
        if shared["budget_remaining"] < BUDGET_RESERVE:
            print("[DecideNext] Budget guard triggered → write_tex")
            return "write_tex"

        # Pre-write quality gate — checks both budget utilization AND research completeness
        if action == "write_tex":
            total = shared.get("budget_dollars", 1)
            used_frac = 1 - (shared["budget_remaining"] / total)
            history = shared.get("history", [])
            bibtex_count = len(shared.get("bibtex_entries", []))
            report_type = shared.get("report_type", "Literature Review")

            # Minimum thresholds by report type
            thresholds = {
                "Quick Summary":    {"min_steps": 1,  "min_citations": 3},
                "Literature Review": {"min_steps": 3,  "min_citations": 8},
                "Research Report":  {"min_steps": 8,  "min_citations": 15},
                "Full Paper":       {"min_steps": 15, "min_citations": 20},
            }
            t = thresholds.get(report_type, thresholds["Literature Review"])

            # Override if budget underutilized OR research incomplete
            needs_more = (used_frac < 0.60
                          or len(history) < t["min_steps"]
                          or bibtex_count < t["min_citations"])

            if needs_more and shared["budget_remaining"] > BUDGET_RESERVE * 3:
                deepen_cycle = [
                    "research-lookup", "literature-review",
                    "statistical-analysis", "data-visualization",
                    "scientific-critical-thinking", "peer-review",
                    "hypothesis-generation", "citation-management",
                ]
                exec_counts = Counter(h["skill"] for h in history)
                valid = [s for s in deepen_cycle if s in shared.get("skill_index", {})]
                if valid:
                    best = min(valid, key=lambda s: exec_counts.get(s, 0))
                    reason_parts = []
                    if used_frac < 0.60:
                        reason_parts.append(f"budget {used_frac:.0%} used")
                    if len(history) < t["min_steps"]:
                        reason_parts.append(f"{len(history)}/{t['min_steps']} steps")
                    if bibtex_count < t["min_citations"]:
                        reason_parts.append(f"{bibtex_count}/{t['min_citations']} citations")
                    override_reason = ", ".join(reason_parts)
                    print(f"[DecideNext] Quality gate: {override_reason} "
                          f"— overriding write_tex → execute_skill ({best})")
                    shared["next_skill"] = best
                    shared["decisions"][-1]["action"] = "execute_skill"
                    shared["decisions"][-1]["skill"] = best
                    shared["decisions"][-1]["reason"] += f" [OVERRIDDEN: {override_reason}]"
                    return "execute_skill"

        if action == "execute_skill":
            shared["next_skill"] = decision.get("skill", "")
            return "execute_skill"
        return "write_tex"


# ===================================================================
# 3. ExecuteSkill
# ===================================================================
class ExecuteSkill(Node):
    """Load a skill's SKILL.md, run it via LLM, and execute any code blocks."""

    def prep(self, shared):
        skill_name = shared["next_skill"]
        # Lazy-load: read the SKILL.md and parse metadata
        skill_content, skill_metadata = load_skill_content(shared["skills_dir"], skill_name)

        # Detect code execution capability
        allowed_tools = skill_metadata.get("allowed-tools", [])
        can_execute = "Bash" in allowed_tools

        # Find available scripts for this skill
        scripts_dir = Path(shared["skills_dir"]) / skill_name / "scripts"
        available_scripts = []
        if scripts_dir.is_dir():
            available_scripts = [f.name for f in scripts_dir.iterdir()
                                 if f.suffix == ".py" and f.is_file()]

        # Condensed prior context (summaries only, not full artifacts)
        context_lines = []
        for h in shared.get("history", []):
            context_lines.append(f"### {h['skill']}\n{h['summary']}")
        prior_context = "\n\n".join(context_lines) if context_lines else "No prior research yet."

        # Collect existing generated data files for context
        generated_files = shared.get("generated_files", {})
        data_files_info = ""
        if generated_files:
            file_lines = []
            for sk, files in generated_files.items():
                for f in files:
                    file_lines.append(f"  - {f} (from {sk})")
            if file_lines:
                data_files_info = "Previously generated data files:\n" + "\n".join(file_lines)

        return {
            "skill_name": skill_name,
            "skill_content": skill_content,
            "topic": shared["topic"],
            "prior_context": prior_context,
            "can_execute": can_execute,
            "available_scripts": available_scripts,
            "scripts_dir": str(scripts_dir) if scripts_dir.is_dir() else "",
            "task_dir": shared.get("output_path", ""),
            "data_files_info": data_files_info,
        }

    def exec(self, prep_res):
        # Build code execution instructions if the skill supports it
        code_exec_block = ""
        if prep_res["can_execute"] and prep_res["task_dir"]:
            scripts_info = ""
            if prep_res["available_scripts"]:
                scripts_info = f"""
### Available Skill Scripts (in {prep_res['scripts_dir']})
These scripts are ready to use. Call them with `python {prep_res['scripts_dir']}/<script_name>`:
{chr(10).join(f'- {s}' for s in prep_res['available_scripts'])}
"""
            data_info = ""
            if prep_res["data_files_info"]:
                data_info = f"""
### Previously Generated Data
{prep_res['data_files_info']}
You can read these files in your code for further analysis or visualization.
"""

            code_exec_block = f"""

## Code Execution Available
You can include executable code to collect REAL data, generate REAL figures, or run REAL analyses.
Your working directory is: {prep_res['task_dir']}
{scripts_info}{data_info}
### How to include executable code
Place code between these markers. Supported: python, bash.

%%BEGIN CODE:python%%
# Your Python code here
# Save data to: data/  (relative path)
# Save figures to: figures/  (relative path)
%%END CODE%%

%%BEGIN CODE:bash%%
# Your bash commands here (use relative paths)
%%END CODE%%

### Code Guidelines
- Your working directory is already set to the task directory. Use RELATIVE paths only.
- Save data files (CSV, JSON) to `data/` (relative path)
- Save figure files (PNG, PDF) to `figures/` (relative path)
- Do NOT use absolute paths or repeat the task directory path in your code.
- For figures: use matplotlib with `plt.savefig('figures/filename.png')` — do NOT use `plt.show()`
- Use descriptive filenames relating to the research topic
- Available libraries: matplotlib, pandas, numpy, seaborn, requests, scipy
- API tokens available as env vars: GITHUB_TOKEN, OPENROUTER_API_KEY, PERPLEXITY_API_KEY
- Timeout: 300 seconds — keep code focused and efficient
- Print a summary of collected/generated data to stdout
- IMPORTANT: You MUST include code blocks to produce real data and figures. Do NOT just describe what code would do — actually write it so it runs.
"""

        prompt = f"""You are executing a research skill as part of an autonomous scientist agent.

## Research Topic
{prep_res["topic"]}

## Prior Research Context
{prep_res["prior_context"]}

## Skill Instructions
Follow these instructions to produce your deliverable:

---
{prep_res["skill_content"]}
---
{code_exec_block}
## Citation Quality Requirements
- Include references to real, well-known papers in the field.
- Aim for breadth: cite multiple research groups, not just one lab.
- Include foundational/seminal papers and recent work (last 5 years when possible).
- Every claim or finding you mention should be backed by a citation.
- Target at least 5-10 references per skill execution.

## Output Format
1. Produce the skill's deliverable as detailed text.
2. At the VERY END of your response, you MUST include a BibTeX section between markers:

%%BEGIN BIBTEX%%
@article{{authorYYYYkeyword,
  author = {{Last, First and Last, First}},
  title = {{Full Paper Title}},
  journal = {{Journal Name}},
  year = {{YYYY}},
  volume = {{N}},
  pages = {{1--10}}
}}
%%END BIBTEX%%

3. Each BibTeX entry MUST have: author, title, year, and venue (journal or booktitle).
4. Use realistic cite keys: author2024keyword (e.g., smith2023attention).
5. Include one entry for EVERY paper you reference in your text.
6. This section is MANDATORY — do not skip it.

Begin your work now."""
        text, usage = call_llm(prompt)
        return text, usage

    def post(self, shared, prep_res, exec_res):
        text, usage = exec_res
        skill_name = prep_res["skill_name"]
        track_cost(shared, f"execute_skill:{skill_name}", usage)

        # --- Extract and execute code blocks ---
        code_outputs = []

        if prep_res["can_execute"] and prep_res["task_dir"]:
            task_dir = Path(prep_res["task_dir"]).resolve()

            # Ensure subdirs exist
            (task_dir / "data").mkdir(exist_ok=True)
            (task_dir / "figures").mkdir(exist_ok=True)
            (task_dir / "scripts").mkdir(exist_ok=True)

            # Extract code blocks: %%BEGIN CODE:lang%% ... %%END CODE%%
            code_blocks = re.findall(
                r"%%BEGIN CODE:(\w+)%%(.*?)%%END CODE%%", text, re.DOTALL
            )

            for i, (lang, code) in enumerate(code_blocks):
                code = code.strip()
                if not code:
                    continue

                # Write script to task_dir/scripts/
                step_num = len(shared.get("history", [])) + 1
                ext = ".py" if lang == "python" else ".sh"
                script_path = task_dir / "scripts" / f"{step_num:02d}_{skill_name}_{i:02d}{ext}"
                script_path.write_text(code, encoding="utf-8")

                # Execute
                cmd = ["python", str(script_path)] if lang == "python" else ["bash", str(script_path)]
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=str(task_dir),
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=300,
                        env={**os.environ},
                    )
                    stdout = result.stdout[:3000]
                    stderr = result.stderr[:1000]
                    code_outputs.append(f"[Script {script_path.name}] exit={result.returncode}\n{stdout}")
                    if result.returncode != 0:
                        code_outputs.append(f"[STDERR] {stderr}")
                    print(f"[ExecuteSkill] Ran {script_path.name}: exit={result.returncode}")
                except subprocess.TimeoutExpired:
                    code_outputs.append(f"[Script {script_path.name}] TIMEOUT after 300s")
                    print(f"[ExecuteSkill] Script {script_path.name} timed out")
                except Exception as e:
                    code_outputs.append(f"[Script {script_path.name}] ERROR: {e}")
                    print(f"[ExecuteSkill] Script {script_path.name} failed: {e}")

            # Scan for generated files
            generated_files = []
            for subdir in ["data", "figures"]:
                scan_dir = task_dir / subdir
                if scan_dir.is_dir():
                    for f in sorted(scan_dir.iterdir()):
                        if f.is_file():
                            generated_files.append(str(f))
            if generated_files:
                shared.setdefault("generated_files", {})[skill_name] = generated_files
                for gf in generated_files:
                    print(f"[ExecuteSkill] Generated: {gf}")

        # --- Extract BibTeX ---
        bibtex_match = re.search(r"%%BEGIN BIBTEX%%(.*?)%%END BIBTEX%%", text, re.DOTALL)
        if bibtex_match:
            main_content = text[:bibtex_match.start()].strip()
            bib_block = bibtex_match.group(1).strip()
            bib_entries = re.findall(r"(@\w+\{[^@]+)", bib_block, re.DOTALL)
            bib_entries = [e.strip() for e in bib_entries if e.strip()]
        else:
            # Fallback: try fenced code blocks and raw entries
            main_content, bib_entries = extract_bibtex(text)

        # Remove code blocks from main content for cleaner artifact storage
        main_content = re.sub(
            r"%%BEGIN CODE:\w+%%.*?%%END CODE%%", "", main_content, flags=re.DOTALL
        ).strip()

        # Append code execution results to the artifact
        if code_outputs:
            main_content += "\n\n## Code Execution Results\n" + "\n".join(code_outputs)

        shared["artifacts"][skill_name] = main_content
        shared["bibtex_entries"].extend(bib_entries)

        # Create short summary for history (first 300 chars)
        summary = main_content[:300].replace("\n", " ")
        if len(main_content) > 300:
            summary += "..."
        step_num = len(shared["history"]) + 1
        shared["history"].append({
            "step": step_num,
            "skill": skill_name,
            "summary": summary,
            "cost": usage["cost"],
        })

        # Persist full artifact and BibTeX to task directory
        out_dir = Path(shared["output_path"])
        artifact_dir = out_dir / "artifacts"
        artifact_dir.mkdir(exist_ok=True)
        artifact_file = artifact_dir / f"{step_num:02d}_{skill_name}.md"
        artifact_file.write_text(main_content, encoding="utf-8")
        if bib_entries:
            bib_file = artifact_dir / f"{step_num:02d}_{skill_name}.bib"
            bib_file.write_text("\n\n".join(bib_entries) + "\n", encoding="utf-8")

        # Persist accumulated history snapshot
        import json as _json
        (out_dir / "history.json").write_text(
            _json.dumps(shared["history"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"[ExecuteSkill] Completed: {skill_name} (${usage['cost']:.4f})")
        print(f"[ExecuteSkill] Saved: {artifact_file.name}")
        print(f"[ExecuteSkill] BibTeX entries found: {len(bib_entries)}")
        print(f"[ExecuteSkill] Budget remaining: ${shared['budget_remaining']:.4f}")
        return "decide"


# ===================================================================
# 4. WriteTeX
# ===================================================================
class WriteTeX(Node):
    """Synthesize all artifacts into compilable .tex + .bib files."""

    def prep(self, shared):
        # Collect all cite keys for the LLM to reference
        cite_keys = []
        for entry in shared.get("bibtex_entries", []):
            m = re.match(r"@\w+\{([^,]+),", entry)
            if m:
                cite_keys.append(m.group(1).strip())

        # Determine which sections have content based on report type
        report_type = shared.get("report_type", "Literature Review")
        has_methods = any(
            k in shared.get("artifacts", {})
            for k in ("statistical-analysis", "method-implementation", "experimental-evaluation")
        )
        has_results = has_methods  # results typically accompany methods

        # Extract writing guidelines from quality standard
        writing_guide = ""
        qs = shared.get("quality_standard", "")
        if qs:
            # Pull sections 2.1, 3, and 6 (structure, writing rules, checklist)
            section_req = re.search(
                r"### 2\.1 Mandatory Sections.*?(?=\n### 2\.2 |\Z)",
                qs, re.DOTALL,
            )
            writing_rules = re.search(
                r"## 3\. Writing Quality Rules.*?(?=\n## 4\.|\Z)",
                qs, re.DOTALL,
            )
            checklist = re.search(
                r"## 6\. Self-Assessment Checklist.*?(?=\n## Sources|\n---|\Z)",
                qs, re.DOTALL,
            )
            parts = []
            if section_req:
                parts.append(section_req.group(0).strip())
            if writing_rules:
                parts.append(writing_rules.group(0).strip())
            if checklist:
                parts.append(checklist.group(0).strip())
            if parts:
                writing_guide = "\n\n".join(parts)

        # Scan for generated figures
        figure_files = []
        out_dir = Path(shared.get("output_path", ""))
        figures_dir = out_dir / "figures"
        if figures_dir.is_dir():
            for f in sorted(figures_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in (".png", ".pdf", ".jpg", ".jpeg"):
                    figure_files.append(f.name)

        # Scan for generated data files (for methods/results context)
        data_files = []
        data_previews = {}
        data_dir = out_dir / "data"
        if data_dir.is_dir():
            for f in sorted(data_dir.iterdir()):
                if f.is_file():
                    data_files.append(f.name)
                    # Load previews for structured data (for inline table generation)
                    if f.suffix.lower() in (".csv", ".json", ".tsv"):
                        try:
                            data_previews[f.name] = f.read_text(
                                encoding="utf-8", errors="replace"
                            )[:2000]
                        except Exception:
                            pass

        return {
            "topic": shared["topic"],
            "artifacts": shared.get("artifacts", {}),
            "cite_keys": cite_keys,
            "has_methods": has_methods or bool(data_files),
            "has_results": has_results or bool(data_files),
            "report_type": report_type,
            "writing_guide": writing_guide,
            "figure_files": figure_files,
            "data_files": data_files,
            "data_previews": data_previews,
        }

    def exec(self, prep_res):
        # Build context from artifacts
        artifact_text = ""
        for name, content in prep_res["artifacts"].items():
            artifact_text += f"\n\n### Artifact: {name}\n{content}"

        # Determine sections based on report type
        report_type = prep_res["report_type"]
        sections = ["abstract", "introduction", "background"]
        if report_type in ("Research Report", "Full Paper") and prep_res["has_methods"]:
            sections.append("methods")
        if report_type in ("Research Report", "Full Paper") and prep_res["has_results"]:
            sections.append("results")
        sections.extend(["discussion", "conclusion"])
        if report_type == "Full Paper":
            sections.append("limitations")

        cite_list = ", ".join(prep_res["cite_keys"]) if prep_res["cite_keys"] else "No citations available."

        # Lean context blocks — only include when non-empty
        extras = []
        if prep_res.get("writing_guide"):
            extras.append(f"## Quality Standard\n{prep_res['writing_guide']}")
        if prep_res.get("figure_files"):
            figs = "\n".join(f"- {f}" for f in prep_res["figure_files"])
            extras.append(
                f"## Figures (include all in body)\n{figs}\n"
                "Pattern: \\\\begin{{figure}}[htbp]\\\\centering"
                "\\\\includegraphics[width=0.8\\\\textwidth]{{figures/<name>}}"
                "\\\\caption{{...}}\\\\label{{fig:<label>}}\\\\end{{figure}}"
            )
        if prep_res.get("data_previews"):
            previews = "\n".join(
                f"### {fn}\n```\n{txt[:800]}\n```"
                for fn, txt in prep_res["data_previews"].items()
            )
            extras.append(f"## Data Previews (use for tables/results)\n{previews}")
        elif prep_res.get("data_files"):
            extras.append("## Data Files\n" + "\n".join(f"- {f}" for f in prep_res["data_files"]))
        extra_block = ("\n\n" + "\n\n".join(extras)) if extras else ""

        prompt = f"""You are writing a scientific {report_type.lower()} as compilable LaTeX.

## Topic: {prep_res["topic"]}
## Type: {report_type} | Sections: {', '.join(sections)}

## Research Artifacts
{artifact_text}

## Available BibTeX cite keys
{cite_list}{extra_block}

## Rules
- Write ONLY LaTeX body (no \\documentclass/\\usepackage/\\begin{{document}}).
- Standard commands only: \\section, \\subsection, \\textbf, \\textit, \\cite, \\ref, itemize, enumerate, equation, table, tabular, figure.
- Use \\cite{{key}} with keys listed above only. Every claim needs a citation.
- Active voice, formal tone, full prose paragraphs (no bullet points in body).
- Escape special chars: \\%, \\&, \\#, \\$.
- Abstract: 150-250 words, self-contained.
- Background: synthesize by theme, not paper-by-paper.
- Include 2-3 booktabs tables (\\toprule/\\midrule/\\bottomrule) from real artifact data.
- Every \\cite{{key}} in body MUST have a matching BibTeX entry below.

Return content between these markers:

%%BEGIN TITLE%%
<specific title, under 15 words>
%%END TITLE%%

%%BEGIN ABSTRACT%%
<150-250 word abstract>
%%END ABSTRACT%%

%%BEGIN BODY%%
\\section{{Introduction}}
...
\\section{{Conclusion}}
%%END BODY%%

%%BEGIN BIBTEX%%
@article{{key,
  author = {{Last, First}},
  title = {{Title}},
  journal = {{Venue}},
  year = {{YYYY}}
}}
%%END BIBTEX%%

Write the report now."""
        text, usage = call_llm(prompt)
        return text, usage

    def post(self, shared, prep_res, exec_res):
        text, usage = exec_res
        track_cost(shared, "write_tex", usage)

        # Extract sections from markers
        title_match = re.search(r"%%BEGIN TITLE%%(.*?)%%END TITLE%%", text, re.DOTALL)
        abstract_match = re.search(r"%%BEGIN ABSTRACT%%(.*?)%%END ABSTRACT%%", text, re.DOTALL)
        body_match = re.search(r"%%BEGIN BODY%%(.*?)%%END BODY%%", text, re.DOTALL)
        bibtex_match = re.search(r"%%BEGIN BIBTEX%%(.*?)%%END BIBTEX%%", text, re.DOTALL)

        title = title_match.group(1).strip() if title_match else prep_res["topic"]
        abstract = abstract_match.group(1).strip() if abstract_match else "Abstract not available."
        body = body_match.group(1).strip() if body_match else text.strip()

        # Extract BibTeX entries from WriteTeX output and merge with skill-collected entries
        if bibtex_match:
            bib_block = bibtex_match.group(1).strip()
            tex_bib_entries = re.findall(r"(@\w+\{[^@]+)", bib_block, re.DOTALL)
            tex_bib_entries = [e.strip() for e in tex_bib_entries if e.strip()]
            shared.setdefault("bibtex_entries", []).extend(tex_bib_entries)
            print(f"[WriteTeX] Extracted {len(tex_bib_entries)} BibTeX entries from report")

        # Assemble .tex from skeleton
        tex = LATEX_SKELETON
        tex = tex.replace("%% TITLE %%", title)
        tex = tex.replace("%% ABSTRACT %%", abstract)
        tex = tex.replace("%% BODY %%", body)

        # Deduplicate and write .bib
        bib_content = dedup_bibtex(shared.get("bibtex_entries", []))

        # Use existing task directory (created by BudgetPlanner)
        out_dir = Path(shared["output_path"])

        (out_dir / "report.tex").write_text(tex, encoding="utf-8")
        (out_dir / "references.bib").write_text(bib_content, encoding="utf-8")

        shared["tex_content"] = tex
        shared["bib_content"] = bib_content

        # --- Citation validation ---
        cite_keys_in_tex = set(re.findall(r"\\cite\{([^}]+)\}", body))
        # Expand comma-separated keys like \cite{a,b,c}
        all_cite_keys = set()
        for group in cite_keys_in_tex:
            for key in group.split(","):
                all_cite_keys.add(key.strip())

        bib_keys = set()
        for entry in shared.get("bibtex_entries", []):
            m = re.match(r"@\w+\{([^,]+),", entry)
            if m:
                bib_keys.add(m.group(1).strip())

        missing = all_cite_keys - bib_keys
        if not bib_content.strip():
            print(f"[WriteTeX] WARNING: references.bib is EMPTY — all citations will show as [?]")
        elif missing:
            print(f"[WriteTeX] WARNING: {len(missing)} cite keys missing from .bib: {', '.join(sorted(missing)[:10])}")
        else:
            print(f"[WriteTeX] Citation check passed: {len(all_cite_keys)} keys, all resolved")

        print(f"[WriteTeX] Wrote report.tex + references.bib to {out_dir}")
        print(f"[WriteTeX] Budget remaining: ${shared['budget_remaining']:.4f}")
        return "compile"


# ===================================================================
# 5. CompileTeX
# ===================================================================
class CompileTeX(Node):
    """Compile .tex + .bib → .pdf using pdflatex + bibtex."""

    def prep(self, shared):
        return shared["output_path"]

    def exec(self, out_dir):
        import shutil
        if not shutil.which("pdflatex"):
            return None, "pdflatex not found"

        cmds = [
            ["pdflatex", "-interaction=nonstopmode", "report.tex"],
            ["bibtex", "report"],
            ["pdflatex", "-interaction=nonstopmode", "report.tex"],
            ["pdflatex", "-interaction=nonstopmode", "report.tex"],
        ]
        all_output = []
        for cmd in cmds:
            result = subprocess.run(
                cmd,
                cwd=out_dir,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=60,
            )
            all_output.append(result.stdout + result.stderr)

        # Check if PDF was produced
        pdf_path = Path(out_dir) / "report.pdf"
        success = pdf_path.exists()
        return success, "\n".join(all_output)

    def post(self, shared, prep_res, exec_res):
        success, log = exec_res
        if success is None:
            print(f"[CompileTeX] pdflatex not installed — skipping PDF compilation.")
            print(f"[CompileTeX] LaTeX source ready at: {shared['output_path']}/report.tex")
            print(f"[CompileTeX] To compile manually: cd {shared['output_path']} && pdflatex report.tex && bibtex report && pdflatex report.tex && pdflatex report.tex")
            return "done"

        # Check for undefined citations even if PDF was produced
        undefined_cites = re.findall(r"Citation `([^']+)' on page", log)
        if undefined_cites:
            unique_missing = sorted(set(undefined_cites))
            print(f"[CompileTeX] WARNING: {len(unique_missing)} undefined citations: {', '.join(unique_missing[:10])}")
            shared["has_citation_warnings"] = True

        if success:
            if undefined_cites and shared.get("fix_attempts", 0) < 2:
                print(f"[CompileTeX] PDF has {len(unique_missing)} undefined citations, routing to fix...")
                shared["compile_errors"] = log
                shared["undefined_citations"] = unique_missing
                return "fix"
            elif undefined_cites:
                print(f"[CompileTeX] PDF compiled with citation warnings (fix attempts exhausted): {shared['output_path']}/report.pdf")
            else:
                print(f"[CompileTeX] PDF compiled successfully: {shared['output_path']}/report.pdf")
            return "done"
        else:
            shared["compile_errors"] = log
            print("[CompileTeX] Compilation failed, attempting fix...")
            return "fix"


# ===================================================================
# 6. FixTeX
# ===================================================================
class FixTeX(Node):
    """Fix LaTeX compilation errors or undefined citations."""

    def prep(self, shared):
        undefined_cites = shared.get("undefined_citations", [])
        return {
            "tex_content": shared["tex_content"],
            "bib_content": shared.get("bib_content", ""),
            "errors": shared.get("compile_errors", ""),
            "attempt": shared.get("fix_attempts", 0),
            "undefined_citations": undefined_cites,
            "mode": "citation" if undefined_cites else "latex_error",
        }

    def exec(self, prep_res):
        if prep_res["attempt"] >= 2:
            # Give up after 2 fix attempts
            return None, {"input_tokens": 0, "output_tokens": 0, "cost": 0}

        if prep_res["mode"] == "citation":
            # Citation fix mode: generate missing BibTeX entries
            missing_keys = prep_res["undefined_citations"]
            prompt = f"""The following BibTeX citation keys are used in a LaTeX document with \\cite{{key}} but are missing from the .bib file, causing [?] markers in the PDF.

## Missing Citation Keys
{', '.join(missing_keys)}

## Current .bib Content (for context, do NOT repeat existing entries)
{prep_res["bib_content"][:3000]}

## Instructions
1. For EACH missing key listed above, generate a plausible BibTeX entry.
2. Use the cite key EXACTLY as listed (do not rename it).
3. Use realistic metadata: real author names, real paper titles, real venues.
4. Each entry MUST have: author, title, year, and journal/booktitle.
5. Return ONLY the new BibTeX entries, nothing else. No explanation text.
6. Do not repeat entries already in the .bib file."""
            text, usage = call_llm(prompt)
            return text, usage
        else:
            # LaTeX error fix mode (original behavior)
            error_lines = []
            for line in prep_res["errors"].split("\n"):
                if line.startswith("!") or "Error" in line or "Undefined" in line:
                    error_lines.append(line)
            error_summary = "\n".join(error_lines[:30])

            prompt = f"""Fix these LaTeX compilation errors. Return the COMPLETE corrected .tex file content.

## Errors
{error_summary}

## Current .tex Content
{prep_res["tex_content"]}

## Rules
1. Do NOT change the \\documentclass or \\usepackage lines.
2. Only fix the errors in the body content.
3. Common fixes: escape special chars (%, &, #, $, _), close environments, fix undefined commands.
4. Return ONLY the complete .tex file, nothing else."""
            text, usage = call_llm(prompt)
            return text, usage

    def post(self, shared, prep_res, exec_res):
        text, usage = exec_res

        shared["fix_attempts"] = prep_res["attempt"] + 1

        if text is None:
            # Max attempts reached
            print(f"[FixTeX] Max fix attempts reached. Output may have compilation warnings.")
            return "done"

        track_cost(shared, f"fix_tex:{shared['fix_attempts']}", usage)

        # Clean up: strip markdown fences if the LLM wrapped it
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```\w*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)

        if prep_res["mode"] == "citation":
            # Citation fix: parse new entries, validate, and update .bib
            new_entries = re.findall(r"(@\w+\{[^@]+)", cleaned, re.DOTALL)
            new_entries = [e.strip() for e in new_entries if e.strip()]

            if new_entries:
                all_entries = shared.get("bibtex_entries", []) + new_entries
                combined = dedup_bibtex(all_entries)

                out_dir = Path(shared["output_path"])
                (out_dir / "references.bib").write_text(combined, encoding="utf-8")
                shared["bib_content"] = combined
                shared["bibtex_entries"] = all_entries

                print(f"[FixTeX] Added {len(new_entries)} BibTeX entries for undefined citations")

            # Clear flag so CompileTeX re-evaluates from scratch
            shared.pop("undefined_citations", None)
            print(f"[FixTeX] Citation fix applied (attempt {shared['fix_attempts']})")
            return "compile"
        else:
            # LaTeX error fix: rewrite .tex
            out_dir = Path(shared["output_path"])
            (out_dir / "report.tex").write_text(cleaned, encoding="utf-8")
            shared["tex_content"] = cleaned

            print(f"[FixTeX] Applied fix (attempt {shared['fix_attempts']})")
            return "compile"


# ===================================================================
# 7. Finisher — terminal node (no successors → flow ends cleanly)
# ===================================================================
class Finisher(Node):
    """Print cost summary and end the flow."""

    def prep(self, shared):
        return shared

    def exec(self, prep_res):
        return None

    def post(self, shared, prep_res, exec_res):
        import json as _json
        from datetime import datetime, timezone

        total = sum(entry["cost"] for entry in shared.get("cost_log", []))
        out_dir = Path(shared["output_path"])

        # Persist cost log
        (out_dir / "cost_log.json").write_text(
            _json.dumps(shared.get("cost_log", []), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Persist final summary for post-analysis
        summary = {
            "topic": shared.get("topic", ""),
            "domain": shared.get("domain", ""),
            "report_type": shared.get("report_type", ""),
            "budget_dollars": shared.get("budget_dollars", 0),
            "total_cost": round(total, 6),
            "budget_remaining": round(shared.get("budget_remaining", 0), 6),
            "steps_executed": len(shared.get("history", [])),
            "artifacts": list(shared.get("artifacts", {}).keys()),
            "bibtex_count": len(shared.get("bibtex_entries", [])),
            "fix_attempts": shared.get("fix_attempts", 0),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        (out_dir / "summary.json").write_text(
            _json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"\n{'='*50}")
        print(f"Research complete!")
        print(f"Total cost: ${total:.4f}")
        print(f"Budget used: ${total:.4f} / ${shared['budget_dollars']:.2f}")
        print(f"Output: {shared['output_path']}/")
        print(f"{'='*50}")
