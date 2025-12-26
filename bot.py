import os
import asyncio
import aiohttp
import discord
from discord.ext import commands
from discord import ui
from dotenv import load_dotenv
import whisper
import tempfile

from agent import run_agent_loop, continue_after_user_choice, continue_after_tool_approval, get_channel_memory
from baml_client import b, types

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
ALLOWED_CHANNEL_IDS = os.getenv("ALLOWED_CHANNEL_IDS", "")

# Parse allowed channel IDs from comma-separated string
allowed_channels = set()
if ALLOWED_CHANNEL_IDS:
    allowed_channels = {int(cid.strip()) for cid in ALLOWED_CHANNEL_IDS.split(",") if cid.strip()}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


class OptionButton(ui.Button):
    """A button representing a user choice."""

    def __init__(self, label: str, option_index: int):
        # Use different button styles for variety
        styles = [
            discord.ButtonStyle.primary,
            discord.ButtonStyle.secondary,
            discord.ButtonStyle.success,
            discord.ButtonStyle.primary,
        ]
        super().__init__(
            label=label[:80],  # Discord button label limit
            style=styles[option_index % len(styles)],
            custom_id=f"option_{option_index}"
        )
        self.option_label = label

    async def callback(self, interaction: discord.Interaction):
        # Disable all buttons after selection
        for item in self.view.children:
            item.disabled = True

        await interaction.response.edit_message(view=self.view)

        # Show typing indicator and process choice
        async with interaction.channel.typing():
            result = await continue_after_user_choice(
                interaction.channel.id,
                self.option_label
            )

        # Handle the result
        await handle_agent_result(interaction.channel, interaction.message, result)


class OptionsView(ui.View):
    """A view containing option buttons for user choices."""

    def __init__(self, options: list[str], timeout: float = 300):
        super().__init__(timeout=timeout)

        for i, option in enumerate(options[:4]):  # Max 4 options
            self.add_item(OptionButton(option, i))

    async def on_timeout(self):
        # Disable all buttons on timeout
        for item in self.children:
            item.disabled = True


class ApprovalButton(ui.Button):
    """A button for approving or denying tool execution."""

    def __init__(self, label: str, approved: bool, perform_action: types.PerformAction):
        style = discord.ButtonStyle.success if approved else discord.ButtonStyle.danger
        super().__init__(
            label=label,
            style=style,
            custom_id=f"approval_{approved}"
        )
        self.approved = approved
        self.perform_action = perform_action

    async def callback(self, interaction: discord.Interaction):
        # Disable all buttons after selection
        for item in self.view.children:
            item.disabled = True

        await interaction.response.edit_message(view=self.view)

        # Show typing indicator and process approval
        async with interaction.channel.typing():
            result = await continue_after_tool_approval(
                interaction.channel.id,
                self.perform_action,
                self.approved
            )

        # Handle the result
        await handle_agent_result(interaction.channel, interaction.message, result)


class ApprovalView(ui.View):
    """A view containing approval buttons for tool execution."""

    def __init__(self, perform_action: types.PerformAction, timeout: float = 300):
        super().__init__(timeout=timeout)

        # Add approve button (labeled "1")
        self.add_item(ApprovalButton("✓ Approve (1)", True, perform_action))

        # Add deny button (labeled "ESC")
        self.add_item(ApprovalButton("✗ Deny (ESC)", False, perform_action))

    async def on_timeout(self):
        # Disable all buttons on timeout
        for item in self.children:
            item.disabled = True


def format_tool_calls_for_approval(tool_calls: list) -> str:
    """Format tool calls for user approval message."""
    lines = []
    for i, tool_call in enumerate(tool_calls, 1):
        if hasattr(tool_call, 'file_path') and hasattr(tool_call, 'content'):  # WriteFileTool
            content_preview = tool_call.content[:100] + "..." if len(tool_call.content) > 100 else tool_call.content
            lines.append(f"{i}. **Write File**: `{tool_call.file_path}`")
            lines.append(f"   Reason: {tool_call.reason}")
            lines.append(f"   Content: ```\n{content_preview}\n```")
        elif hasattr(tool_call, 'file_path'):  # ReadFileTool
            lines.append(f"{i}. **Read File**: `{tool_call.file_path}`")
            lines.append(f"   Reason: {tool_call.reason}")
        elif hasattr(tool_call, 'command'):  # BashTool
            lines.append(f"{i}. **Run Command**: `{tool_call.command}`")
            lines.append(f"   Reason: {tool_call.reason}")
    return "\n".join(lines)


async def handle_agent_result(channel, original_message, result):
    """Handle the result from the agent loop."""
    if result.error:
        error_msg = f"Error: {result.error}"
        # Summarize if too long
        error_msg = await maybe_summarize_text(error_msg, 1900)
        await channel.send(error_msg)

    elif result.response:
        await send_response(channel, result.response)

    elif result.ask_user:
        # Create button view for options
        view = OptionsView(result.ask_user.options)
        await channel.send(result.ask_user.question, view=view)

    elif result.perform_action:
        # Handle PerformAction - show approval UI
        reasoning = result.perform_action.reasoning
        tools_formatted = format_tool_calls_for_approval(result.perform_action.tool_calls)

        approval_msg = f"**🔧 Tool Approval Required**\n\n"
        approval_msg += f"**Reasoning:** {reasoning}\n\n"
        approval_msg += f"**Proposed Actions:**\n{tools_formatted}\n\n"
        approval_msg += "Click **✓ Approve** to execute or **✗ Deny** to cancel."

        # Create approval view
        view = ApprovalView(result.perform_action)
        await channel.send(approval_msg, view=view)


async def transcribe_audio(audio_data: bytes, filename: str) -> str:
    """Transcribe audio using local Whisper model."""
    try:
        # Write audio data to temporary file
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1], delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        try:
            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: whisper.load_model(WHISPER_MODEL).transcribe(temp_path))
            return result["text"].strip()
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as e:
        return f"Error transcribing audio: {str(e)}"


async def download_attachment(url: str) -> bytes:
    """Download an attachment from Discord."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            raise Exception(f"Failed to download attachment: status {response.status}")


@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")
    print(f"Connected to Ollama at: {OLLAMA_URL}")
    print(f"Using model: {OLLAMA_MODEL}")
    print(f"Whisper model: {WHISPER_MODEL} (local)")
    print("Agent mode: ENABLED (BAML structured responses)")
    if allowed_channels:
        print(f"Listening in channels: {allowed_channels}")
    else:
        print("Warning: No ALLOWED_CHANNEL_IDS set. Bot will respond in ALL channels!")


async def maybe_summarize_text(text: str, max_length: int = 1900) -> str:
    """Summarize text if it exceeds the maximum length using BAML."""
    if len(text) <= max_length:
        return text

    # Calculate target length with some margin
    target_length = int(max_length * 0.9)  # 90% of max to have margin

    try:
        # Use BAML to summarize
        summarized = await b.SummarizeText(text, target_length)

        # If summarization still exceeds max, truncate
        if len(summarized) > max_length:
            summarized = summarized[:max_length - 3] + "..."

        return summarized
    except Exception as e:
        # Fallback to simple truncation if summarization fails
        print(f"Summarization failed: {e}")
        return text[:max_length - 3] + "..."


async def send_response(channel, response: str):
    """Send a response to a channel, summarizing if necessary."""
    # Discord limit is 2000 chars, use 1900 to be safe
    if len(response) <= 1900:
        await channel.send(response)
    else:
        # Try to summarize instead of chunking
        summarized = await maybe_summarize_text(response, 1900)
        await channel.send(summarized)


def is_voice_message(message: discord.Message) -> bool:
    """Check if the message contains a voice message attachment."""
    if message.flags.voice:
        return True
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith('audio/'):
            return True
    return False


async def get_voice_attachment(message: discord.Message) -> discord.Attachment | None:
    """Get the voice/audio attachment from a message."""
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith('audio/'):
            return attachment
    return None


async def process_user_input(message: discord.Message, user_input: str):
    """Process user input through the agent loop."""
    async with message.channel.typing():
        result = await run_agent_loop(message.channel.id, user_input)

    await handle_agent_result(message.channel, message, result)


@bot.event
async def on_message(message: discord.Message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Ignore messages from other bots
    if message.author.bot:
        return

    # Check if we should respond in this channel
    if allowed_channels and message.channel.id not in allowed_channels:
        return

    # Check for voice message
    if is_voice_message(message):
        attachment = await get_voice_attachment(message)
        if attachment:
            async with message.channel.typing():
                try:
                    # Download the voice message
                    audio_data = await download_attachment(attachment.url)

                    # Transcribe the audio
                    transcription = await transcribe_audio(audio_data, attachment.filename)

                    if transcription.startswith("Error") or transcription.startswith("Transcription timed out"):
                        await message.reply(f"Failed to transcribe voice message: {transcription}")
                        return

                    # Show transcription and process through agent
                    await message.reply(f"**Transcription:** {transcription}")

                except Exception as e:
                    await message.reply(f"Error processing voice message: {str(e)}")
                    return

            # Process the transcription through the agent
            await process_user_input(message, transcription)
            return

    # Get the message content for text messages
    content = message.content.strip()
    if not content:
        return

    # Process through the agent loop
    await process_user_input(message, content)


# Command to clear channel memory
@bot.command(name="clear")
async def clear_memory(ctx):
    """Clear the conversation history for this channel."""
    memory = get_channel_memory(ctx.channel.id)
    memory.clear()
    await ctx.send("Conversation history cleared.")


def main():
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set!")
        print("Please create a .env file with your Discord bot token.")
        return

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
