"""Code execution via subprocess, inspired by mini-swe-agent."""

import subprocess
import tempfile
import os
from typing import Dict, Any
from pathlib import Path


class Executor:
    """Execute bash commands and Python code via subprocess."""

    def __init__(self, workspace: str = None):
        """Initialize executor with workspace directory.

        Args:
            workspace: Working directory for experiments (default: temp dir)
        """
        self.workspace = workspace or tempfile.mkdtemp(prefix="msr_scientist_")
        os.makedirs(self.workspace, exist_ok=True)

    def execute_bash(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute bash command.

        Args:
            command: Bash command to execute
            timeout: Timeout in seconds

        Returns:
            Dict with stdout, stderr, returncode
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "returncode": -1,
                "success": False
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "success": False
            }

    def execute_python(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute Python code.

        Args:
            code: Python code to execute
            timeout: Timeout in seconds

        Returns:
            Dict with stdout, stderr, returncode
        """
        # Write code to temp file
        script_path = Path(self.workspace) / "temp_script.py"
        with open(script_path, "w") as f:
            f.write(code)

        # Execute via subprocess
        return self.execute_bash(f"python {script_path}", timeout=timeout)

    def save_file(self, filename: str, content: str) -> str:
        """Save file to workspace.

        Args:
            filename: File name
            content: File content

        Returns:
            Full path to saved file
        """
        filepath = Path(self.workspace) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        return str(filepath)

    def read_file(self, filename: str) -> str:
        """Read file from workspace.

        Args:
            filename: File name

        Returns:
            File content
        """
        filepath = Path(self.workspace) / filename
        with open(filepath, "r") as f:
            return f.read()

    def cleanup(self):
        """Clean up workspace."""
        import shutil
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)
