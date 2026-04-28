"""Flow wiring for the Autonomous Scientist agent.

Pipeline:
  Initializer
    → LiteratureReviewLoop  (terminates on quality gate or budget)
    → ExperimentationLoop   (terminates on quality gate or budget)
    → WritingLoop           (terminates on quality gate or budget)
    → CompilingLoop (CompileTeX ↔ FixTeX)
    → Finisher
"""

import os

from pocketflow import AsyncFlow

from .nodes import (
    Initializer,
    LiteratureReviewLoop,
    ExperimentationLoop,
    WritingLoop,
    CompileTeX,
    FixTeX,
    Finisher,
)

_RETRIES = int(os.environ.get("NODE_RETRIES", "2"))
_WAIT    = int(os.environ.get("NODE_WAIT",    "3"))


def create_scientist_flow() -> AsyncFlow:
    init       = Initializer()
    literature = LiteratureReviewLoop(max_retries=_RETRIES, wait=_WAIT)
    experiment = ExperimentationLoop(max_retries=_RETRIES,  wait=_WAIT)
    writing    = WritingLoop(max_retries=_RETRIES,          wait=_WAIT)
    compile    = CompileTeX(max_retries=1,                  wait=0)
    fix_tex    = FixTeX(max_retries=_RETRIES,               wait=_WAIT)
    finisher   = Finisher()

    init       - "literature" >> literature
    literature - "experiment" >> experiment
    experiment - "write"      >> writing
    writing    - "compile"    >> compile

    compile    - "fix"        >> fix_tex
    compile    - "done"       >> finisher
    fix_tex    - "compile"    >> compile
    fix_tex    - "done"       >> finisher

    return AsyncFlow(start=init)
