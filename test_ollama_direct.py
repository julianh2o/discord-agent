#!/usr/bin/env python3
"""Direct Ollama API test without BAML"""

import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen:14b")


async def test_ollama():
    """Test Ollama API directly"""
    url = f"{OLLAMA_URL}/api/chat"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "user", "content": "Say hello in JSON format like: {\"greeting\": \"hello\"}"}
        ],
        "stream": False
    }

    print(f"Testing Ollama at: {OLLAMA_URL}")
    print(f"Model: {OLLAMA_MODEL}")
    print(f"Request payload: {json.dumps(payload, indent=2)}")
    print()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                print(f"Response status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print(f"Response: {json.dumps(data, indent=2)}")
                    print()

                    if "message" in data and "content" in data["message"]:
                        content = data["message"]["content"]
                        print(f"Message content: {content}")
                else:
                    error_text = await response.text()
                    print(f"Error: {error_text}")
    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    asyncio.run(test_ollama())
