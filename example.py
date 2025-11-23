"""Example usage of MSR-Scientist mini agent."""

from agent import ResearchAgent

# Create agent (use gpt-4 or claude-3-5-sonnet-20241022)
agent = ResearchAgent(model="gpt-4")

# Conduct research
results = agent.conduct_research(
    task="Compare the performance of quicksort vs mergesort on different data sizes",
    max_hypotheses=2
)

# Print summary
print("\n" + "="*60)
print("Research Complete!")
print("="*60)
print(f"Hypotheses tested: {len(results['hypotheses'])}")
print(f"Workspace: {results['workspace']}")
print("="*60)
