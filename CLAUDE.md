# Discord Agent Project

## Overview
A Discord bot that relays messages (text and voice) to a Llama AI instance via an agentic loop. Uses BAML for structured agent communication with tool use capabilities.

## Architecture

### Components
- **Discord Bot** (`bot.py`): Handles Discord messages, voice memos, and button interactions
- **Agent Module** (`agent.py`): Agentic loop with tool execution and channel memory
- **BAML Definitions** (`baml_src/`): Type-safe LLM function definitions
- **Ollama Integration**: Local Llama instance for LLM responses
- **Whisper Integration**: Transcribes voice messages via remote Whisper API

### Agent Flow
```
User Message → Add to Channel Memory
                    ↓
              AgentStep(messages)
                    ↓
         ┌─────────┴─────────┐
         ↓                   ↓                   ↓
   ContinueResearch    FinalResponse         AskUser
         ↓                   ↓                   ↓
   Execute URL fetch   Send response      Send buttons
   Add results           Done            Wait for click
   Loop again                            Add choice
                                         Loop again
```

### BAML Types

**Agent Actions** (union type - agent chooses one):
- `ContinueResearch`: Fetch URLs for more information
- `FinalResponse`: Send final answer to user
- `AskUser`: Ask clarifying question with button options

**Tools**:
- `FetchUrlTool`: Fetch and extract text content from URLs

## Configuration

### Environment Variables
- `DISCORD_TOKEN` - Discord bot token (required)
- `OLLAMA_URL` - Ollama API URL (default: http://localhost:11434)
- `OLLAMA_MODEL` - Model name (default: llama2)
- `WHISPER_URL` - Whisper ASR API URL (default: http://localhost:9000)
- `ALLOWED_CHANNEL_IDS` - Comma-separated channel IDs to respond in

## File Structure
```
discord-agent/
├── bot.py              # Discord bot with button UI
├── agent.py            # Agent loop and tool execution
├── pyproject.toml      # Poetry dependencies and config
├── requirements.txt    # Python dependencies (legacy)
├── .env.example        # Environment template
├── CLAUDE.md           # This file
├── baml_src/           # BAML definitions
│   ├── generators.baml # Code generation config
│   ├── clients.baml    # Ollama client config
│   ├── types.baml      # Message, tool, action types
│   └── agent.baml      # AgentStep function
└── baml_client/        # Auto-generated (do not edit)
```

## Development

### Setup
```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Generate BAML client (run after any .baml changes)
poetry run baml-cli generate

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings
```

### Running
```bash
# Run with Poetry
poetry run python bot.py

# Or activate the virtual environment and run directly
poetry shell
python bot.py
```

### Commands
- `!clear` - Clear conversation history for the channel

## Key Implementation Details

### Channel Memory
- Per-channel conversation history stored in `agent.py`
- Last 20 messages kept to avoid context overflow
- Cleared with `!clear` command

### Agent Loop
- Max 5 iterations to prevent infinite loops
- Typing indicator shown while processing
- Tool results added to conversation context

### Discord Buttons
- Used for `AskUser` clarification options
- Max 4 options (Discord limit)
- 5 minute timeout, buttons disabled after selection

### URL Fetching
- HTML content parsed with BeautifulSoup
- Scripts, styles, nav, header, footer removed
- Content truncated to 4000 chars to avoid token limits
