#!/usr/bin/env python3
"""
Test script for the audio transcription and agent response pipeline.
Usage: poetry run python test_pipeline.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import whisper

from baml_client import b, types

load_dotenv()

AUDIO_FILE = "testing/audio/how_to_cake.mp3"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # Options: tiny, base, small, medium, large


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using local Whisper model."""
    audio_file = Path(audio_path)
    if not audio_file.exists():
        return f"Error: Audio file not found at {audio_path}"

    try:
        print(f"Loading Whisper model '{WHISPER_MODEL}'... (this may take a moment on first run)")
        model = whisper.load_model(WHISPER_MODEL)

        print(f"Transcribing audio...")
        result = model.transcribe(str(audio_file))

        return result["text"].strip()
    except Exception as e:
        return f"Error transcribing audio: {str(e)}"


async def get_agent_response(user_message: str) -> str:
    """Get a response from the agent for a user message."""
    messages = [
        types.Message(role="user", content=user_message)
    ]

    try:
        result = await b.AgentStep(messages)

        if isinstance(result, types.FinalResponse):
            return result.response
        elif isinstance(result, types.AskUser):
            return f"Agent wants to ask: {result.question}\nOptions: {result.options}"
        elif isinstance(result, types.ContinueResearch):
            return f"Agent wants to research more with tools: {result.tool_calls}"
        else:
            return f"Unknown response type: {type(result)}"
    except Exception as e:
        return f"Error from agent: {str(e)}"


async def main():
    """Run the test pipeline."""
    print("=" * 60)
    print("AUDIO TRANSCRIPTION AND AGENT PIPELINE TEST")
    print("=" * 60)
    print()

    # Step 1: Transcribe audio
    print(f"📁 Audio file: {AUDIO_FILE}")
    print(f"🎤 Using local Whisper model: {WHISPER_MODEL}")
    print()

    transcription = transcribe_audio(AUDIO_FILE)

    print("=" * 60)
    print("TRANSCRIPTION RESULT:")
    print("=" * 60)
    print(transcription)
    print()

    if transcription.startswith("Error"):
        print("❌ Transcription failed. Stopping here.")
        return

    # Step 2: Send to agent
    print("=" * 60)
    print("SENDING TO AGENT:")
    print("=" * 60)
    print(f"User message: {transcription}")
    print()

    response = await get_agent_response(transcription)

    print("=" * 60)
    print("AGENT RESPONSE:")
    print("=" * 60)
    print(response)
    print()


if __name__ == "__main__":
    asyncio.run(main())
