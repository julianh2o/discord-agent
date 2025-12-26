"""
Key/value store for large tool results.

Uses SHA-256 hashes as keys for content-addressable storage.
"""

import hashlib
from typing import Dict


# In-memory storage for tool results
_store: Dict[str, str] = {}


def _hash_content(content: str) -> str:
    """Generate a short SHA-256 hash for content."""
    full_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    return full_hash[:8]  # Use first 8 chars for brevity


def store_content(content: str) -> str:
    """
    Store content and return its SHA key.

    Args:
        content: The content to store

    Returns:
        SHA key (8 char hash) for retrieving the content
    """
    sha_key = _hash_content(content)
    _store[sha_key] = content
    return sha_key


def get_content(sha_key: str) -> str | None:
    """
    Retrieve content by SHA key.

    Args:
        sha_key: The SHA key to look up

    Returns:
        The stored content, or None if not found
    """
    return _store.get(sha_key)


def clear_store() -> None:
    """Clear all stored content."""
    _store.clear()


def get_store_size() -> int:
    """Get the number of items in the store."""
    return len(_store)
