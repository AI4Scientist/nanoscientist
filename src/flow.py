"""Flow wiring for the Autonomous Scientist agent.

Pipeline:
  Initializer → PlanInitialExecutor → PlanDrivenExecutor (loop)
              → ReviewExecutor → [execute / compile]
              → CompileTeX ↔ FixTeX → Finisher

PlanDrivenExecutor executes each plan step in order (research or write).
ReviewExecutor appends revision steps to the plan tail and loops back.
LaTeX compilation happens exactly once, as the final PDF generation step.
"""

import os

from pocketflow import AsyncFlow

from .nodes import (
    Initializer,
    PlanInitialExecutor,
    PlanDrivenExecutor,
    ReviewExecutor,
    CompileTeX,
    FixTeX,
    Finisher,
)

# Default retry/wait applied to all LLM-driven nodes.
# CompileTeX uses retries=1 since it loops back via FixTeX instead.
_RETRIES = int(os.environ.get("NODE_RETRIES", "2"))
_WAIT    = int(os.environ.get("NODE_WAIT",    "3"))


def create_scientist_flow() -> AsyncFlow:
    init     = Initializer()
    planner  = PlanInitialExecutor(max_retries=_RETRIES, wait=_WAIT)
    executor = PlanDrivenExecutor(max_retries=_RETRIES,  wait=_WAIT)
    review   = ReviewExecutor(max_retries=_RETRIES,      wait=_WAIT)
    compile  = CompileTeX(max_retries=1,                 wait=0)
    fix_tex  = FixTeX(max_retries=_RETRIES,              wait=_WAIT)
    finisher = Finisher()

    init     - "research" >> planner
    planner  - "execute"  >> executor

    executor - "execute"  >> executor   # loop through plan steps
    executor - "review"   >> review

    review   - "execute"  >> executor   # revision steps appended to plan
    review   - "compile"  >> compile

    compile  - "fix"      >> fix_tex
    compile  - "done"     >> finisher
    fix_tex  - "compile"  >> compile
    fix_tex  - "done"     >> finisher

    return AsyncFlow(start=init)
