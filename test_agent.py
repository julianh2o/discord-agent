#!/usr/bin/env python3
"""
Test harness for the agent with pre-populated conversation context from JSON.
Usage: poetry run python test_agent.py <test_case_file.json>
"""

import asyncio
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

from agent import run_agent_loop, get_channel_memory
from baml_client import types

load_dotenv()


def load_test_case(json_path: str) -> dict:
    """Load a test case from a JSON file."""
    test_file = Path(json_path)
    if not test_file.exists():
        print(f"❌ Error: Test file not found at {json_path}")
        sys.exit(1)

    try:
        with open(test_file, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading test case: {e}")
        sys.exit(1)


def populate_channel_memory(channel_id: int, messages: list[dict]) -> None:
    """Populate channel memory with pre-existing messages."""
    memory = get_channel_memory(channel_id)
    memory.clear()  # Start fresh

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "user":
            memory.add_user_message(content)
        elif role == "assistant":
            memory.add_assistant_message(content)
        elif role == "tool":
            memory.add_tool_result(content)
        elif role == "error":
            memory.add_error(content)


async def run_test(test_case: dict) -> None:
    """Run a single test case."""
    test_name = test_case.get("name", "Unnamed Test")
    description = test_case.get("description", "")
    initial_messages = test_case.get("initial_messages", [])
    user_query = test_case.get("user_query", "")

    print("=" * 70)
    print(f"TEST: {test_name}")
    print("=" * 70)
    if description:
        print(f"Description: {description}")
        print()

    # Use a test channel ID
    test_channel_id = 999999

    # Populate initial context if any
    if initial_messages:
        print("📝 Pre-populating conversation context:")
        print("-" * 70)
        for msg in initial_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            print(f"  [{role.upper()}]: {content[:100]}{'...' if len(content) > 100 else ''}")
        print()
        populate_channel_memory(test_channel_id, initial_messages)

    # Run the agent with the user query
    print("🤖 User query:")
    print("-" * 70)
    print(f"  {user_query}")
    print()

    print("🔄 Running agent loop...")
    print("-" * 70)
    print()

    result = await run_agent_loop(test_channel_id, user_query)

    # Display results
    print("=" * 70)
    print("AGENT RESULT:")
    print("=" * 70)

    if result.response:
        print("✅ Final Response:")
        print("-" * 70)
        print(result.response)
        print()

    elif result.ask_user:
        print("❓ Agent asks:")
        print("-" * 70)
        print(f"Question: {result.ask_user.question}")
        print(f"Options: {result.ask_user.options}")
        print()

    elif result.error:
        print("❌ Error:")
        print("-" * 70)
        print(result.error)
        print()

    # Show conversation history
    memory = get_channel_memory(test_channel_id)
    messages = memory.get_messages()

    print("=" * 70)
    print(f"CONVERSATION HISTORY ({len(messages)} messages):")
    print("=" * 70)
    for i, msg in enumerate(messages, 1):
        role_label = msg.role.upper()
        content_preview = msg.content[:150].replace('\n', ' ')
        if len(msg.content) > 150:
            content_preview += "..."
        print(f"{i}. [{role_label}]: {content_preview}")
    print()


async def main():
    """Main test runner."""
    if len(sys.argv) < 2:
        print("Usage: poetry run python test_agent.py <test_case_file.json>")
        print()
        print("Example test cases:")
        print("  poetry run python test_agent.py test_cases/golden_retriever.json")
        sys.exit(1)

    test_file = sys.argv[1]
    test_case = load_test_case(test_file)

    await run_test(test_case)


if __name__ == "__main__":
    asyncio.run(main())
