"""
Tools module for the Discord AI Agent.

Tools are reusable, composable functions with well-defined inputs and outputs
that can be called by the AI agent or chained together.
"""

from typing import TypeVar, Generic, Protocol, Any
from dataclasses import dataclass

# Import tool functions
from .read_file import read_file
from .write_file import write_file
from .bash_command import execute_bash

# Input and output type variables
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


@dataclass
class ToolResult(Generic[TOutput]):
    """Standardized tool execution result."""
    success: bool
    data: TOutput | None = None
    error: str | None = None

    @classmethod
    def ok(cls, data: TOutput) -> "ToolResult[TOutput]":
        """Create a successful result."""
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, error: str) -> "ToolResult[TOutput]":
        """Create a failed result."""
        return cls(success=False, data=None, error=error)


class Tool(Protocol[TInput, TOutput]):
    """Protocol for all tools."""

    async def execute(self, input_data: TInput) -> ToolResult[TOutput]:
        """Execute the tool with the given input."""
        ...

    @property
    def name(self) -> str:
        """Tool name for registration and logging."""
        ...

    @property
    def description(self) -> str:
        """Tool description for AI agent."""
        ...
