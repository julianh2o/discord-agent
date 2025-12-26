import asyncio
from dataclasses import dataclass, field
from typing import Union
import aiohttp
from bs4 import BeautifulSoup
import os
from tavily import TavilyClient

from baml_client import b, types
from tools.ollama_models import get_ollama_models
from tools.stored_content import get_stored_content
from tools.kv_store import store_content
from tools.read_file import read_file
from tools.write_file import write_file
from tools.bash_command import execute_bash

# Import types for convenience
Message = types.Message
GatherInformation = types.GatherInformation
AskUser = types.AskUser
PerformAction = types.PerformAction
FinalAnswer = types.FinalAnswer
GetOllamaModelsTool = types.GetOllamaModelsTool
TavilySearchTool = types.TavilySearchTool


MAX_ITERATIONS = 5
MAX_CONTENT_LENGTH = 4000  # Limit fetched content to avoid token limits
MAX_CONTEXT_LENGTH = 2000  # Max length before storing in KV store


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

    def add_error(self, content: str) -> None:
        self.messages.append(Message(role="error", content=content))
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


async def tavily_search(query: str) -> str:
    """Perform a web search using Tavily API."""
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: TAVILY_API_KEY environment variable not set"

        # Tavily client is synchronous, run in executor
        loop = asyncio.get_event_loop()

        def _search():
            client = TavilyClient(api_key=api_key)
            response = client.search(query=query, max_results=5)
            return response

        response = await loop.run_in_executor(None, _search)

        # Format results
        if not response or "results" not in response:
            return "No results found"

        results = response["results"]
        if not results:
            return "No results found"

        # Build formatted response
        formatted_results = []
        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content = result.get("content", "")

            formatted_results.append(f"{i}. {title}\n   URL: {url}\n   {content}\n")

        output = "\n".join(formatted_results)

        # Truncate if too long
        if len(output) > MAX_CONTENT_LENGTH:
            output = output[:MAX_CONTENT_LENGTH] + "\n... (results truncated)"

        return output

    except Exception as e:
        return f"Error performing Tavily search: {str(e)}"


def maybe_store_large_content(content: str, prefix: str = "") -> str:
    """
    Check if content is large, store it if needed, and return appropriate message.

    Args:
        content: The content to check
        prefix: Prefix to add before the content/truncation message

    Returns:
        Either the original content or a truncated version with SHA reference
    """
    if len(content) <= MAX_CONTEXT_LENGTH:
        return f"{prefix}{content}" if prefix else content

    # Store full content and return truncated version with SHA
    sha_key = store_content(content)
    preview_length = MAX_CONTEXT_LENGTH - 200  # Leave room for the SHA message
    truncated = content[:preview_length]

    result = f"{prefix}{truncated}\n\n[Content truncated - {len(content)} chars total]\n"
    result += f"[Full content stored: SHA={sha_key}]\n"
    result += f"[Use GetStoredContentTool with SHA '{sha_key}' to access full content]"

    return result


async def execute_action_tools(tool_calls: list) -> tuple[list[str], list[str]]:
    """
    Execute PerformAction tool calls (ReadFile, WriteFile, Bash).
    Only called after user approval.

    Returns:
        Tuple of (successful_results, errors)
    """
    results = []
    errors = []

    for tool_call in tool_calls:
        # Check tool type and execute accordingly
        if hasattr(tool_call, 'file_path') and hasattr(tool_call, 'content'):  # WriteFileTool
            file_path = tool_call.file_path
            content = tool_call.content
            reason = tool_call.reason
            tool_result = await write_file(file_path, content)

            if tool_result.success:
                result = f"WriteFile ({reason}): {tool_result.data}"
                results.append(result)
            else:
                errors.append(f"WriteFile failed ({reason}): {tool_result.error}")

        elif hasattr(tool_call, 'file_path'):  # ReadFileTool
            file_path = tool_call.file_path
            reason = tool_call.reason
            tool_result = await read_file(file_path)

            if tool_result.success:
                # Store large content and truncate if needed
                prefix = f"ReadFile ({reason}, path={file_path}):\n"
                result = maybe_store_large_content(tool_result.data, prefix)
                results.append(result)
            else:
                errors.append(f"ReadFile failed ({reason}): {tool_result.error}")

        elif hasattr(tool_call, 'command'):  # BashTool
            command = tool_call.command
            reason = tool_call.reason
            tool_result = await execute_bash(command)

            if tool_result.success:
                # Store large content and truncate if needed
                prefix = f"Bash ({reason}, command='{command}'):\n"
                result = maybe_store_large_content(tool_result.data, prefix)
                results.append(result)
            else:
                errors.append(f"Bash failed ({reason}): {tool_result.error}")

    return results, errors


async def execute_tool_calls(tool_calls: list) -> tuple[list[str], list[str]]:
    """
    Execute a list of tool calls and return results.

    Returns:
        Tuple of (successful_results, errors)
    """
    results = []
    errors = []

    for tool_call in tool_calls:
        # Check tool type and execute accordingly
        if hasattr(tool_call, 'url'):  # FetchUrlTool
            url = tool_call.url
            reason = tool_call.reason
            content = await fetch_url(url)

            # Check if fetch_url returned an error
            if content.startswith("Error"):
                errors.append(f"Failed to fetch {url} ({reason}): {content}")
            else:
                # Store large content and truncate if needed
                prefix = f"Fetched {url} ({reason}):\n"
                result = maybe_store_large_content(content, prefix)
                results.append(result)

        elif hasattr(tool_call, 'query') and hasattr(tool_call, 'reason'):  # TavilySearchTool
            query = tool_call.query
            reason = tool_call.reason
            search_results = await tavily_search(query)

            # Check if tavily_search returned an error
            if search_results.startswith("Error"):
                errors.append(f"Tavily search failed for '{query}' ({reason}): {search_results}")
            else:
                # Store large content and truncate if needed
                prefix = f"Tavily search results for '{query}' ({reason}):\n"
                result = maybe_store_large_content(search_results, prefix)
                results.append(result)

        elif hasattr(tool_call, 'sha_key'):  # GetStoredContentTool
            sha_key = tool_call.sha_key
            reason = getattr(tool_call, 'reason', 'Retrieving stored content')
            tool_result = await get_stored_content(sha_key)

            if tool_result.success:
                # Retrieved content might also be large, so check again
                prefix = f"Retrieved stored content ({reason}, SHA={sha_key}):\n"
                result = maybe_store_large_content(tool_result.data, prefix)
                results.append(result)
            else:
                errors.append(f"Tool error (get_stored_content): {tool_result.error}")

        elif hasattr(tool_call, 'reason') and not hasattr(tool_call, 'url'):  # GetOllamaModelsTool
            reason = tool_call.reason
            tool_result = await get_ollama_models()

            if tool_result.success:
                models_list = "\n".join([f"- {model_id}" for model_id in tool_result.data])
                result = f"Available Ollama models ({reason}):\n{models_list}\n\nTotal: {len(tool_result.data)} models"
                results.append(result)
            else:
                errors.append(f"Tool error (get_ollama_models): {tool_result.error}")

    return results, errors


@dataclass
class AgentResult:
    """Result from the agent loop."""
    response: str | None = None
    ask_user: AskUser | None = None
    perform_action: PerformAction | None = None
    error: str | None = None


async def run_agent_loop(channel_id: int, user_input: str) -> AgentResult:
    """
    Run the agent loop for a user message.

    Returns an AgentResult with either:
    - A final response to send
    - An AskUser object with a question and options
    - A PerformAction object describing an action to perform
    - An error message
    """
    memory = get_channel_memory(channel_id)
    memory.add_user_message(user_input)

    for iteration in range(MAX_ITERATIONS):
        try:
            messages = memory.get_messages()
            result = await b.AgentStep(messages)

            if isinstance(result, FinalAnswer):
                memory.add_assistant_message(result.response)
                return AgentResult(response=result.response)

            elif isinstance(result, AskUser):
                # Don't add to memory yet - will add after user responds
                return AgentResult(ask_user=result)

            elif isinstance(result, PerformAction):
                # Return action to bot for handling
                return AgentResult(perform_action=result)

            elif isinstance(result, GatherInformation):
                # Execute tool calls
                if result.tool_calls:
                    tool_results, tool_errors = await execute_tool_calls(result.tool_calls)

                    # Add successful results to memory
                    for tool_result in tool_results:
                        memory.add_tool_result(tool_result)

                    # Add errors to memory so orchestrator can see and handle them
                    for error in tool_errors:
                        memory.add_error(error)
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


async def continue_after_tool_approval(channel_id: int, perform_action: PerformAction, approved: bool) -> AgentResult:
    """
    Continue the agent loop after user approves or denies tool execution.

    Args:
        channel_id: The Discord channel ID
        perform_action: The PerformAction object with tools to execute
        approved: Whether the user approved the tool execution

    Returns:
        AgentResult with the next step
    """
    memory = get_channel_memory(channel_id)

    if approved:
        # Execute the approved tools
        tool_results, tool_errors = await execute_action_tools(perform_action.tool_calls)

        # Add successful results to memory
        for tool_result in tool_results:
            memory.add_tool_result(tool_result)

        # Add errors to memory so orchestrator can see and handle them
        for error in tool_errors:
            memory.add_error(error)
    else:
        # User denied the tool execution
        memory.add_user_message("[User denied tool execution]")

    # Continue the agent loop
    return await run_agent_loop_internal(channel_id)


async def run_agent_loop_internal(channel_id: int) -> AgentResult:
    """Internal agent loop without adding initial user message."""
    memory = get_channel_memory(channel_id)

    for iteration in range(MAX_ITERATIONS):
        try:
            messages = memory.get_messages()
            result = await b.AgentStep(messages)

            if isinstance(result, FinalAnswer):
                memory.add_assistant_message(result.response)
                return AgentResult(response=result.response)

            elif isinstance(result, AskUser):
                return AgentResult(ask_user=result)

            elif isinstance(result, PerformAction):
                return AgentResult(perform_action=result)

            elif isinstance(result, GatherInformation):
                if result.tool_calls:
                    tool_results, tool_errors = await execute_tool_calls(result.tool_calls)

                    # Add successful results to memory
                    for tool_result in tool_results:
                        memory.add_tool_result(tool_result)

                    # Add errors to memory so orchestrator can see and handle them
                    for error in tool_errors:
                        memory.add_error(error)
                else:
                    memory.add_tool_result("No tools were called. Please provide a response.")

        except Exception as e:
            return AgentResult(error=f"Agent error: {str(e)}")

    return AgentResult(error="Max iterations reached. Please try a different question.")
