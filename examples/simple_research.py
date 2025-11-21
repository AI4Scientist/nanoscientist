"""Simple example of using MSR-Scientist for research."""

import os
from msr_scientist import ResearchAgent, ResearchWorkflow


def main():
    """Run a simple research task."""
    # Set up API key (use environment variable or set directly)
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    # Create research agent
    # Use "gpt-4" for OpenAI or "claude-3-5-sonnet-20241022" for Anthropic
    agent = ResearchAgent(model="gpt-4", api_key=api_key)

    # Create research workflow
    workflow = ResearchWorkflow(agent=agent, verbose=True)

    # Define research task
    task = """
    Investigate the performance characteristics of different sorting algorithms
    on various data distributions (random, sorted, reverse-sorted).
    Generate empirical data and analyze which algorithm performs best under which conditions.
    """

    # Conduct research
    results = workflow.conduct_research(
        task=task,
        max_hypotheses=2,  # Test 2 hypotheses
        generate_pdf=True   # Generate PDF paper
    )

    # Print results
    print("\n" + "="*60)
    print("Research Results")
    print("="*60)

    print(f"\nHypotheses: {len(results['hypotheses'])}")
    for i, h in enumerate(results['hypotheses'], 1):
        print(f"  {i}. {h}")

    print(f"\nExperiments: {len(results['experiments'])}")
    for i, exp in enumerate(results['experiments'], 1):
        print(f"  {i}. {exp.get('description', 'N/A')[:70]}...")

    print(f"\nPaper generated: {results.get('paper_tex')}")
    print(f"PDF compiled: {results.get('paper_pdf')}")

    print(f"\nWorkspace: {results['workspace']}")


if __name__ == "__main__":
    main()
