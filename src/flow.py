"""Flow wiring for the Autonomous Scientist agent."""

from pocketflow import Flow

from .nodes import (
    BudgetPlanner,
    DecideNext,
    ExecuteSkill,
    WriteTeX,
    CompileTeX,
    FixTeX,
    Finisher,
)


def create_scientist_flow() -> Flow:
    """Create and wire the autonomous scientist flow.

    Flow diagram:
        BudgetPlanner → DecideNext ↔ ExecuteSkill (loop)
                         ↓
                       WriteTeX → CompileTeX ↔ FixTeX (loop)
                                    ↓
                                  (END)
    """
    planner       = BudgetPlanner(max_retries=2, wait=3)
    decide        = DecideNext(max_retries=2, wait=3)
    execute_skill = ExecuteSkill(max_retries=2, wait=5)
    write_tex     = WriteTeX(max_retries=2, wait=3)
    compile_tex   = CompileTeX(max_retries=1, wait=0)
    fix_tex       = FixTeX(max_retries=2, wait=3)
    finisher      = Finisher()

    # Agent loop
    planner - "execute"       >> decide
    decide  - "execute_skill" >> execute_skill
    decide  - "write_tex"     >> write_tex
    execute_skill - "decide"  >> decide

    # Compile & fix loop
    write_tex   - "compile" >> compile_tex
    compile_tex - "fix"     >> fix_tex
    compile_tex - "done"    >> finisher
    fix_tex     - "compile" >> compile_tex
    fix_tex     - "done"    >> finisher

    return Flow(start=planner)
