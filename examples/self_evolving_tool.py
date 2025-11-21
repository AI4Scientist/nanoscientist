"""Example of self-evolving tool generation capability."""

import os
from msr_scientist import ResearchAgent, ResearchWorkflow


def main():
    """Demonstrate dynamic tool generation."""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    # Create research agent and workflow
    agent = ResearchAgent(model="gpt-4", api_key=api_key)
    workflow = ResearchWorkflow(agent=agent, verbose=True)

    # Example: Generate a tool on-the-fly
    print("Generating a custom statistical analysis tool...")

    tool_name = workflow.generate_tool_on_fly(
        """Create a function called 'analyze_distribution' that takes a list of numbers
        and returns a dictionary with mean, median, std deviation, and outliers (values > 2 std from mean)."""
    )

    print(f"\nGenerated tool: {tool_name}")

    # Use the generated tool
    tool = workflow.tool_registry.get_tool(tool_name)
    data = [1, 2, 3, 4, 5, 100]  # 100 is an outlier

    try:
        result = tool(data)
        print(f"\nTool result: {result}")
    except Exception as e:
        print(f"\nTool execution error: {e}")
        print("(This is expected in a demo - the tool may need dependencies)")

    # List all tools
    print(f"\nAll registered tools: {workflow.tool_registry.list_tools()}")


if __name__ == "__main__":
    main()
