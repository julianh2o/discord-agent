"""
Tool for retrieving stored content by SHA key.
"""

from tools import ToolResult
from tools.kv_store import get_content


async def get_stored_content(sha_key: str) -> ToolResult[str]:
    """
    Retrieve previously stored content by its SHA key.

    Args:
        sha_key: The 8-character SHA key from a previous tool result

    Returns:
        ToolResult containing the full content or an error
    """
    try:
        content = get_content(sha_key)

        if content is None:
            return ToolResult.fail(f"No content found for SHA key: {sha_key}")

        return ToolResult.ok(content)

    except Exception as e:
        return ToolResult.fail(f"Error retrieving content: {str(e)}")
