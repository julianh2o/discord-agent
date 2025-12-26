"""Tool for executing bash commands."""
import asyncio
from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: str = ""
    error: Optional[str] = None


async def execute_bash(command: str, timeout: int = 30) -> ToolResult:
    """
    Execute a bash command.

    Args:
        command: The bash command to execute
        timeout: Maximum execution time in seconds (default: 30)

    Returns:
        ToolResult with command output or error
    """
    try:
        # Create subprocess
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Kill the process if it times out
            process.kill()
            await process.wait()
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout} seconds"
            )

        # Decode output
        stdout_text = stdout.decode('utf-8', errors='replace')
        stderr_text = stderr.decode('utf-8', errors='replace')

        # Check return code
        if process.returncode == 0:
            # Success
            output = stdout_text if stdout_text else "(no output)"
            if stderr_text:
                output += f"\n[stderr]: {stderr_text}"

            return ToolResult(
                success=True,
                data=output
            )
        else:
            # Command failed
            error_msg = f"Command failed with exit code {process.returncode}"
            if stderr_text:
                error_msg += f"\n{stderr_text}"
            if stdout_text:
                error_msg += f"\n[stdout]: {stdout_text}"

            return ToolResult(
                success=False,
                error=error_msg
            )

    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Error executing command: {str(e)}"
        )
