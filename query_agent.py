#!/usr/bin/env python3
"""
Simple CLI for querying the agent with automatic tool execution loop.
Runs the agent until it either provides a final response or needs user input.

Usage:
  poetry run python query_agent.py "What is the weather in San Francisco?"
  poetry run python query_agent.py --interactive "Tell me about golden retrievers"
"""

import asyncio
import sys
from dotenv import load_dotenv

from agent import run_agent_loop, get_channel_memory, continue_after_user_choice

load_dotenv()

# Use a consistent channel ID for CLI queries
CLI_CHANNEL_ID = 888888


async def query_agent_once(query: str) -> None:
    """Run a single query through the agent and display the result."""
    print(f"Query: {query}")
    print("=" * 70)
    print()

    result = await run_agent_loop(CLI_CHANNEL_ID, query)

    if result.response:
        print("Response:")
        print("-" * 70)
        print(result.response)
        print()

    elif result.ask_user:
        print("Agent needs clarification:")
        print("-" * 70)
        print(f"Question: {result.ask_user.question}")
        print(f"\nOptions:")
        for i, option in enumerate(result.ask_user.options, 1):
            print(f"  {i}. {option}")
        print("\nUse --interactive mode to continue the conversation.")
        print()

    elif result.error:
        print("Error:")
        print("-" * 70)
        print(result.error)
        print()


async def query_agent_interactive(initial_query: str) -> None:
    """Run an interactive session with the agent."""
    print(f"Initial Query: {initial_query}")
    print("=" * 70)
    print()

    result = await run_agent_loop(CLI_CHANNEL_ID, initial_query)

    while True:
        if result.response:
            print("Response:")
            print("-" * 70)
            print(result.response)
            print()

            # Ask if user wants to continue
            print("\nContinue conversation? (yes/no): ", end="", flush=True)
            continue_choice = input().strip().lower()

            if continue_choice not in ["yes", "y"]:
                break

            print("\nYour message: ", end="", flush=True)
            user_input = input().strip()

            if not user_input:
                break

            print()
            result = await run_agent_loop(CLI_CHANNEL_ID, user_input)

        elif result.ask_user:
            print("Agent asks:")
            print("-" * 70)
            print(f"{result.ask_user.question}")
            print(f"\nOptions:")
            for i, option in enumerate(result.ask_user.options, 1):
                print(f"  {i}. {option}")
            print()

            # Get user's choice
            while True:
                print("Your choice (number or custom text): ", end="", flush=True)
                choice_input = input().strip()

                if not choice_input:
                    print("Please provide an input.")
                    continue

                # Check if it's a number selection
                try:
                    choice_num = int(choice_input)
                    if 1 <= choice_num <= len(result.ask_user.options):
                        choice = result.ask_user.options[choice_num - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(result.ask_user.options)}, or custom text.")
                except ValueError:
                    # User provided custom text
                    choice = choice_input
                    break

            print()
            result = await continue_after_user_choice(CLI_CHANNEL_ID, choice)

        elif result.error:
            print("Error:")
            print("-" * 70)
            print(result.error)
            print()
            break


async def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  poetry run python query_agent.py \"Your question here\"")
        print("  poetry run python query_agent.py --interactive \"Your question here\"")
        print()
        print("Examples:")
        print("  poetry run python query_agent.py \"What are the available Ollama models?\"")
        print("  poetry run python query_agent.py --interactive \"Tell me about golden retrievers\"")
        sys.exit(1)

    # Check for interactive mode
    interactive = False
    query_start_idx = 1

    if sys.argv[1] in ["--interactive", "-i"]:
        interactive = True
        query_start_idx = 2

    if len(sys.argv) <= query_start_idx:
        print("Error: Please provide a query string.")
        sys.exit(1)

    # Join all remaining arguments as the query
    query = " ".join(sys.argv[query_start_idx:])

    # Clear any previous conversation in this channel
    memory = get_channel_memory(CLI_CHANNEL_ID)
    memory.clear()

    if interactive:
        await query_agent_interactive(query)
    else:
        await query_agent_once(query)


if __name__ == "__main__":
    asyncio.run(main())
