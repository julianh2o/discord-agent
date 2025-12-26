#!/usr/bin/env python3
"""
Generic tool tester.

Usage:
    python test_tool.py <function_name>

Example:
    python test_tool.py get_ollama_models
"""

import sys
import asyncio
import importlib
import json
from dotenv import load_dotenv


def infer_module_name(func_name: str) -> str:
    """Infer module name from function name."""
    # Remove common prefixes
    for prefix in ['get_', 'fetch_', 'list_', 'create_', 'update_', 'delete_']:
        if func_name.startswith(prefix):
            return func_name[len(prefix):]
    return func_name


async def test_tool(func_name: str):
    """Test a tool by function name."""
    try:
        # Infer module name from function name
        module_name = infer_module_name(func_name)

        # Import the tool module
        module = importlib.import_module(f"tools.{module_name}")

        # Get the function
        tool_func = getattr(module, func_name)

        # Execute the tool
        result = await tool_func()

        # Display results
        if result.success:
            # Format output as JSON array
            output = result.data
            if isinstance(output, list):
                print(json.dumps(output, indent=2))
            else:
                print(json.dumps(output, indent=2))
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)

    except ModuleNotFoundError:
        print(f"Error: Module 'tools.{module_name}' not found", file=sys.stderr)
        sys.exit(1)
    except AttributeError:
        print(f"Error: Function '{func_name}' not found in tools.{module_name}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_tool.py <function_name>")
        print("Example: python test_tool.py get_ollama_models")
        sys.exit(1)

    load_dotenv()
    func_name = sys.argv[1]
    asyncio.run(test_tool(func_name))


if __name__ == "__main__":
    main()
