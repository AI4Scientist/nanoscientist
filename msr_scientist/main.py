"""Main entry point for MSR-Scientist agent."""

import argparse
import os
from pathlib import Path

from .agent import ResearchAgent
from .research import ResearchWorkflow


def main():
    """Run MSR-Scientist from command line."""
    parser = argparse.ArgumentParser(
        description="MSR-Scientist: Self-evolving minimalist researcher agent"
    )
    parser.add_argument(
        "task",
        type=str,
        help="Research task description"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4",
        help="LLM model to use (default: gpt-4)"
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Workspace directory (default: temp dir)"
    )
    parser.add_argument(
        "--max-hypotheses",
        type=int,
        default=3,
        help="Maximum hypotheses to test (default: 3)"
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF compilation"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for LLM provider"
    )

    args = parser.parse_args()

    # Create agent
    agent = ResearchAgent(model=args.model, api_key=args.api_key)

    # Create workflow
    workflow = ResearchWorkflow(
        agent=agent,
        workspace=args.workspace,
        verbose=True
    )

    # Conduct research
    results = workflow.conduct_research(
        task=args.task,
        max_hypotheses=args.max_hypotheses,
        generate_pdf=not args.no_pdf
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Research Complete!")
    print("=" * 60)
    print(f"\nTask: {results['task']}")
    print(f"\nHypotheses tested: {len(results['hypotheses'])}")
    print(f"Experiments run: {len(results['experiments'])}")
    print(f"\nWorkspace: {results['workspace']}")

    if results.get('paper_tex'):
        print(f"Paper (LaTeX): {results['paper_tex']}")
    if results.get('paper_pdf'):
        print(f"Paper (PDF): {results['paper_pdf']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
