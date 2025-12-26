"""
Tool for retrieving available models from Ollama.
"""

import os
import aiohttp
from typing import List
from tools import ToolResult


async def get_ollama_models() -> ToolResult[List[str]]:
    """
    Get list of available AI models from Ollama.

    Returns:
        ToolResult containing a list of model IDs (e.g., ['qwen3:4b', 'mistral:latest'])
    """
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    try:
        # Build API URL - handle both /v1 and non-/v1 endpoints
        if "/v1" in ollama_url:
            api_url = f"{ollama_url}/models"
        else:
            api_url = f"{ollama_url}/api/tags"

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return ToolResult.fail(f"HTTP {response.status}")

                data = await response.json()

                # Parse response - format differs between /v1 and non-/v1
                if "data" in data:  # OpenAI-compatible /v1 format
                    raw_models = data["data"]
                elif "models" in data:  # Ollama native format
                    raw_models = data["models"]
                else:
                    return ToolResult.fail(f"Unexpected response format")

                # Extract model IDs
                model_ids = []
                for raw_model in raw_models:
                    model_id = raw_model.get("id") or raw_model.get("name")
                    if model_id:
                        model_ids.append(model_id)

                return ToolResult.ok(model_ids)

    except aiohttp.ClientError as e:
        return ToolResult.fail(f"Network error: {str(e)}")
    except Exception as e:
        return ToolResult.fail(f"Error: {str(e)}")
