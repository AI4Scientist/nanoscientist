"""Dynamic tool registry and generator for self-evolving capabilities."""

import importlib.util
import sys
from typing import Dict, Callable, Any
from pathlib import Path
import tempfile


class ToolRegistry:
    """Registry for dynamically generated tools."""

    def __init__(self):
        """Initialize empty tool registry."""
        self.tools: Dict[str, Callable] = {}
        self.tool_code: Dict[str, str] = {}

    def register_tool(self, name: str, func: Callable, code: str = None):
        """Register a tool.

        Args:
            name: Tool name
            func: Tool function
            code: Source code (for self-evolving tools)
        """
        self.tools[name] = func
        if code:
            self.tool_code[name] = code

    def get_tool(self, name: str) -> Callable:
        """Get tool by name.

        Args:
            name: Tool name

        Returns:
            Tool function

        Raises:
            KeyError: If tool not found
        """
        return self.tools[name]

    def has_tool(self, name: str) -> bool:
        """Check if tool exists.

        Args:
            name: Tool name

        Returns:
            True if tool exists
        """
        return name in self.tools

    def list_tools(self) -> list:
        """List all registered tools.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

    def generate_tool(self, name: str, code: str) -> Callable:
        """Generate and register a new tool from code.

        Args:
            name: Tool name
            code: Python code defining the tool function

        Returns:
            The generated tool function
        """
        # Write code to temp file
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        )
        temp_file.write(code)
        temp_file.close()

        # Load module
        spec = importlib.util.spec_from_file_location(
            f"dynamic_tool_{name}", temp_file.name
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"dynamic_tool_{name}"] = module
        spec.loader.exec_module(module)

        # Extract the tool function (assume it has the same name as the tool)
        tool_func = getattr(module, name, None)
        if tool_func is None:
            # Try to find any function in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and not attr_name.startswith("_"):
                    tool_func = attr
                    break

        if tool_func is None:
            raise ValueError(f"No callable function found in generated tool code")

        # Register the tool
        self.register_tool(name, tool_func, code)

        # Clean up temp file
        Path(temp_file.name).unlink()

        return tool_func


# Global tool registry
_global_registry = ToolRegistry()


def register_tool(name: str, code: str = None):
    """Decorator to register a tool.

    Args:
        name: Tool name
        code: Source code (optional)
    """
    def decorator(func: Callable):
        _global_registry.register_tool(name, func, code)
        return func
    return decorator


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry.

    Returns:
        Global tool registry
    """
    return _global_registry
