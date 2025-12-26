"""Tool for writing file contents."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: str = ""
    error: Optional[str] = None


async def write_file(file_path: str, content: str) -> ToolResult:
    """
    Write content to a file.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file

    Returns:
        ToolResult with success status or error
    """
    try:
        # Expand user path if needed
        expanded_path = os.path.expanduser(file_path)

        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(expanded_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        # Write the file
        with open(expanded_path, 'w', encoding='utf-8') as f:
            f.write(content)

        file_size = len(content)
        return ToolResult(
            success=True,
            data=f"Successfully wrote {file_size} characters to {file_path}"
        )

    except PermissionError:
        return ToolResult(
            success=False,
            error=f"Permission denied: {file_path}"
        )
    except IsADirectoryError:
        return ToolResult(
            success=False,
            error=f"Path is a directory, not a file: {file_path}"
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Error writing file: {str(e)}"
        )
