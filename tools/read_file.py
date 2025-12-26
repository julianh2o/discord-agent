"""Tool for reading file contents."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: str = ""
    error: Optional[str] = None


async def read_file(file_path: str) -> ToolResult:
    """
    Read contents of a file.

    Args:
        file_path: Path to the file to read

    Returns:
        ToolResult with file contents or error
    """
    try:
        # Expand user path if needed
        expanded_path = os.path.expanduser(file_path)

        # Check if file exists
        if not os.path.exists(expanded_path):
            return ToolResult(
                success=False,
                error=f"File not found: {file_path}"
            )

        # Check if it's a file (not a directory)
        if not os.path.isfile(expanded_path):
            return ToolResult(
                success=False,
                error=f"Path is not a file: {file_path}"
            )

        # Read the file
        with open(expanded_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return ToolResult(
            success=True,
            data=content
        )

    except UnicodeDecodeError:
        return ToolResult(
            success=False,
            error=f"Cannot read file (binary or encoding issue): {file_path}"
        )
    except PermissionError:
        return ToolResult(
            success=False,
            error=f"Permission denied: {file_path}"
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Error reading file: {str(e)}"
        )
