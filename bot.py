import os
import asyncio
import aiohttp
import discord
from discord.ext import commands
from discord import ui
from dotenv import load_dotenv

from agent import run_agent_loop, continue_after_user_choice, get_channel_memory

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:9000")
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


async def handle_agent_result(channel, original_message, result):
    """Handle the result from the agent loop."""
    if result.error:
        await channel.send(f"Error: {result.error}")

    elif result.response:
        await send_response(channel, result.response)

    elif result.ask_user:
        # Create button view for options
        view = OptionsView(result.ask_user.options)
        await channel.send(result.ask_user.question, view=view)


async def transcribe_audio(audio_data: bytes, filename: str) -> str:
    """Send audio to Whisper API and return the transcription."""
    url = f"{WHISPER_URL}/asr"

    # Prepare multipart form data
    form_data = aiohttp.FormData()
    form_data.add_field(
        'audio_file',
        audio_data,
        filename=filename,
        content_type='audio/ogg'
    )

    # Common parameters for Whisper ASR APIs
    form_data.add_field('task', 'transcribe')
    form_data.add_field('output', 'json')

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data, timeout=aiohttp.ClientTimeout(total=120)) as response:
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        data = await response.json()
                        # Handle different response formats
                        if isinstance(data, dict):
                            return data.get("text", data.get("transcription", str(data)))
                        return str(data)
                    else:
                        # Plain text response
                        return await response.text()
                else:
                    error_text = await response.text()
                    return f"Error from Whisper (status {response.status}): {error_text}"
    except asyncio.TimeoutError:
        return "Transcription timed out."
    except aiohttp.ClientError as e:
        return f"Connection error to Whisper: {str(e)}"
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
    print(f"Whisper API at: {WHISPER_URL}")
    print("Agent mode: ENABLED (BAML structured responses)")
    if allowed_channels:
        print(f"Listening in channels: {allowed_channels}")
    else:
        print("Warning: No ALLOWED_CHANNEL_IDS set. Bot will respond in ALL channels!")


async def send_response(channel, response: str):
    """Send a response to a channel, splitting into chunks if necessary."""
    if len(response) <= 2000:
        await channel.send(response)
    else:
        chunks = [response[i:i+1990] for i in range(0, len(response), 1990)]
        for chunk in chunks:
            await channel.send(chunk)


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
