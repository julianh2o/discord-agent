# Discord Agent Tools

This directory contains reusable, composable tools for the Discord AI Agent. Tools have well-defined inputs and outputs, making them easy to chain and integrate with the agent system.

## Architecture

### Tool Structure

Each tool is a single async function that returns a `ToolResult`:

```python
async def get_something() -> ToolResult[SomeType]:
    """Tool description."""
    try:
        # Do work
        result_data = ...
        return ToolResult.ok(result_data)
    except Exception as e:
        return ToolResult.fail(str(e))
```

**Conventions:**
- One function per file
- Function name: `{verb}_{noun}` (e.g., `get_ollama_models`, `fetch_user_data`)
- Module name: `{noun}` (e.g., `ollama_models.py`, `user_data.py`)
- Return types: Simple Python types (list, dict, str) for clear, serializable output

### ToolResult

All tool executions return a `ToolResult[TOutput]`:
- `success: bool` - Whether the tool succeeded
- `data: TOutput | None` - The output data (any Python type)
- `error: str | None` - Error message if failed

Helper methods:
- `ToolResult.ok(data)` - Create successful result
- `ToolResult.fail(error)` - Create failed result

## Available Tools

### get_ollama_models

Retrieves the list of available AI models from the Ollama instance.

**Output:** `List[str]` - Array of model IDs

**Example:**
```python
from tools.ollama_models import get_ollama_models

result = await get_ollama_models()
if result.success:
    for model_id in result.data:
        print(model_id)
    # ['qwen3:4b', 'mistral:latest', ...]
else:
    print(f"Error: {result.error}")
```

## Integration with Agent

Tools are integrated with the BAML agent system:

1. **BAML Type Definition** (`baml_src/types.baml`):
   ```baml
   class GetOllamaModelsTool {
     reason string @description("Why you need to know available models")
   }
   ```

2. **Agent Prompt** (`baml_src/agent.baml`):
   - Agent is informed about available tools
   - Can choose to use tools via `ContinueResearch` action

3. **Tool Execution** (`agent.py`):
   - `execute_tool_calls()` handles tool execution
   - Results are added to conversation memory

## Adding New Tools

To add a new tool:

1. **Create the tool file** in `tools/` (e.g., `tools/my_data.py`):
   ```python
   from typing import Dict
   from tools import ToolResult

   async def get_my_data(param: str = None) -> ToolResult[Dict]:
       """Get some data from a source."""
       try:
           # Do work
           data = {"key": "value"}
           return ToolResult.ok(data)
       except Exception as e:
           return ToolResult.fail(str(e))
   ```

2. **Add BAML type** in `baml_src/types.baml`:
   ```baml
   class MyTool {
     param string @description("...")
   }
   ```

3. **Update ContinueResearch** in `baml_src/types.baml`:
   ```baml
   class ContinueResearch {
     reasoning string
     tool_calls (FetchUrlTool | GetOllamaModelsTool | MyTool)[]
   }
   ```

4. **Update agent prompt** in `baml_src/agent.baml`:
   - Add tool to the list of available tools

5. **Update execute_tool_calls** in `agent.py`:
   - Add handler for the new tool type

6. **Regenerate BAML client**:
   ```bash
   poetry run baml-cli generate
   ```

## Testing Tools

Use the generic test script to test any tool:

```bash
# Test get_ollama_models
poetry run python test_tool.py get_ollama_models

# Generic usage
poetry run python test_tool.py <function_name>
```

Output is formatted as JSON for clarity:
```bash
$ poetry run python test_tool.py get_ollama_models
[
  "qwen3:4b",
  "mistral:latest",
  ...
]
```
