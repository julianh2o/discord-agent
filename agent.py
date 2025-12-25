import asyncio
from dataclasses import dataclass, field
from typing import Union
import aiohttp
from bs4 import BeautifulSoup

from baml_client import b, types

# Import types for convenience
Message = types.Message
ContinueResearch = types.ContinueResearch
FinalResponse = types.FinalResponse
AskUser = types.AskUser


MAX_ITERATIONS = 5
MAX_CONTENT_LENGTH = 4000  # Limit fetched content to avoid token limits


@dataclass
class ChannelMemory:
    """Stores conversation history for a Discord channel."""
    messages: list[Message] = field(default_factory=list)
    max_messages: int = 20  # Keep last N messages to avoid context overflow

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(Message(role="assistant", content=content))
        self._trim()

    def add_tool_result(self, content: str) -> None:
        self.messages.append(Message(role="tool", content=content))
        self._trim()

    def _trim(self) -> None:
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_messages(self) -> list[Message]:
        return self.messages.copy()

    def clear(self) -> None:
        self.messages.clear()


# Global channel memory store
channel_memories: dict[int, ChannelMemory] = {}


def get_channel_memory(channel_id: int) -> ChannelMemory:
    """Get or create memory for a channel."""
    if channel_id not in channel_memories:
        channel_memories[channel_id] = ChannelMemory()
    return channel_memories[channel_id]


async def fetch_url(url: str) -> str:
    """Fetch content from a URL and extract text."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; DiscordBot/1.0)"
            }
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return f"Error fetching URL: HTTP {response.status}"

                content_type = response.headers.get("Content-Type", "")

                if "text/html" in content_type:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Remove script and style elements
                    for element in soup(["script", "style", "nav", "header", "footer"]):
                        element.decompose()

                    # Get text content
                    text = soup.get_text(separator="\n", strip=True)

                    # Clean up whitespace
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    text = "\n".join(lines)

                elif "application/json" in content_type:
                    text = await response.text()

                elif "text/" in content_type:
                    text = await response.text()

                else:
                    return f"Unsupported content type: {content_type}"

                # Truncate if too long
                if len(text) > MAX_CONTENT_LENGTH:
                    text = text[:MAX_CONTENT_LENGTH] + "\n... (content truncated)"

                return text

    except asyncio.TimeoutError:
        return "Error: Request timed out"
    except aiohttp.ClientError as e:
        return f"Error fetching URL: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


async def execute_tool_calls(tool_calls: list) -> list[str]:
    """Execute a list of tool calls and return results."""
    results = []

    for tool_call in tool_calls:
        # Currently only FetchUrlTool is supported
        url = tool_call.url
        reason = tool_call.reason

        content = await fetch_url(url)
        result = f"Fetched {url} ({reason}):\n{content}"
        results.append(result)

    return results


@dataclass
class AgentResult:
    """Result from the agent loop."""
    response: str | None = None
    ask_user: AskUser | None = None
    error: str | None = None


async def run_agent_loop(channel_id: int, user_input: str) -> AgentResult:
    """
    Run the agent loop for a user message.

    Returns an AgentResult with either:
    - A final response to send
    - An AskUser object with a question and options
    - An error message
    """
    memory = get_channel_memory(channel_id)
    memory.add_user_message(user_input)

    for iteration in range(MAX_ITERATIONS):
        try:
            messages = memory.get_messages()
            result = await b.AgentStep(messages)

            if isinstance(result, FinalResponse):
                memory.add_assistant_message(result.response)
                return AgentResult(response=result.response)

            elif isinstance(result, AskUser):
                # Don't add to memory yet - will add after user responds
                return AgentResult(ask_user=result)

            elif isinstance(result, ContinueResearch):
                # Execute tool calls
                if result.tool_calls:
                    tool_results = await execute_tool_calls(result.tool_calls)
                    for tool_result in tool_results:
                        memory.add_tool_result(tool_result)
                else:
                    # No tool calls but wants to continue - force a response
                    memory.add_tool_result("No tools were called. Please provide a response.")

        except Exception as e:
            return AgentResult(error=f"Agent error: {str(e)}")

    # Max iterations reached
    return AgentResult(error="I've done extensive research but couldn't formulate a complete answer. Please try rephrasing your question.")


async def continue_after_user_choice(channel_id: int, choice: str) -> AgentResult:
    """Continue the agent loop after user makes a choice from options."""
    memory = get_channel_memory(channel_id)
    memory.add_user_message(f"I choose: {choice}")

    return await run_agent_loop_internal(channel_id)


async def run_agent_loop_internal(channel_id: int) -> AgentResult:
    """Internal agent loop without adding initial user message."""
    memory = get_channel_memory(channel_id)

    for iteration in range(MAX_ITERATIONS):
        try:
            messages = memory.get_messages()
            result = await b.AgentStep(messages)

            if isinstance(result, FinalResponse):
                memory.add_assistant_message(result.response)
                return AgentResult(response=result.response)

            elif isinstance(result, AskUser):
                return AgentResult(ask_user=result)

            elif isinstance(result, ContinueResearch):
                if result.tool_calls:
                    tool_results = await execute_tool_calls(result.tool_calls)
                    for tool_result in tool_results:
                        memory.add_tool_result(tool_result)
                else:
                    memory.add_tool_result("No tools were called. Please provide a response.")

        except Exception as e:
            return AgentResult(error=f"Agent error: {str(e)}")

    return AgentResult(error="Max iterations reached. Please try a different question.")
