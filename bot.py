# bot.py
import os
import discord
from discord.ext import commands
from config import *
from sys import exc_info
from openai import AsyncOpenAI
import json
import importlib.util
import subprocess

openai = AsyncOpenAI(api_key=API_KEY)
if BACKEND_PATH and BACKEND_IMPORTED:
    try:
        spec = importlib.util.spec_from_file_location("module.name", BACKEND_PATH)
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
    except Exception as e:
        print(f"Backend not loaded ({e}).")
        BACKEND_PATH = ""

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)

global channel_data
with open(CHANNELS, 'a+') as f:
    channel_data = json.load(f) if f.read() else {}

valid_models = [
    'text-curie-001', 'text-babbage-001', 'text-ada-001', 'text-davinci-003', 'text-davinci-002', 'code-davinci-002',
    'davinci', 'curie', 'babbage', 'ada', 'babbage-002', 'davinci-002', 'gpt-3.5-turbo', 'gpt-3.5-turbo-1106',
    'gpt-3.5-turbo-16k', 'gpt-3.5-turbo-instruct', 'gpt-3.5-turbo-0613', 'gpt-3.5-turbo-16k-0613', 'gpt-3.5-turbo-0301',
    'text-moderation-latest', 'text-embedding-ada-002', 'gpt-4-1106-preview', 'gpt-4-32k', 'gpt-4-0613', 'gpt-4-32k-0613',
    'gpt-4-0314', 'gpt-4-32k-0314', 'gpt-4'
]

@client.command(name="shutdown", brief="Shut ChatGPT down", help="Shut ChatGPT down.",
        description="Open the Pod bay doors, please, HAL.")
async def shutdown(ctx):
    await ctx.send(f"I'm afraid I can't do that, {ctx.author.mention}.")


@client.command(name="setting", brief="Change the system prompt and/or model for this channel",
        help="Usage: /setting prompt [new_prompt] or /setting model [new_model] or /setting reset.")
async def setting(ctx, setting=None, *, new_value=None):
    if not setting:
        await ctx.send("Usage: `/setting prompt [new_prompt]` or `/setting model [new_model]` or `/setting reset`")
        return

    if setting == "reset":
        await ctx.send("Defaults applied to this channel.\nModel: %s\nPrompt: %s"%DEFAULT)
        return
    elif setting not in ("prompt", "model"):
        await ctx.send("Invalid setting. Use prompt/model/reset.")
        return

    index = 0 if setting == "prompt" else 1
    if not new_value:
        current_value = channel_data.get(ctx.channel.id, DEFAULT)[index]
        await ctx.send(f"Current channel {setting}: {current_value}")
    else:
        if setting == "model" and new_value not in valid_models:
            await ctx.send("Warning: this model wasn't recognized but will be applied. "
                           f"Recognized models:\n`{', '.join(valid_models)}`")

        if ctx.channel.id not in channel_data:
            channel_data[ctx.channel.id] = DEFAULT
        channel_data[ctx.channel.id][index] = new_value
        with open(CHANNELS, "w") as f:
            json.dump(channel_data, f)
        await ctx.send(f"{setting.capitalize()} for this channel changed to: {new_value}")


@client.event
async def on_error(event, *args, **kwargs):
    with open(ERRORS, 'a+') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {exc_info()}\n')
        raise


@client.event
async def on_ready():
    print(f'{client.user.name} is online.')
    await client.change_presence(activity=discord.Game(name="with human lives"))


@client.event
async def on_message(message):
    send = message.channel.send

    # ignore system messages
    if message.type != discord.MessageType.default:
        return
    # process slash commands
    elif message.content.startswith("/"):
        await client.process_commands(message)
        return
    # prevent self-reply loop
    elif message.author == client.user:
        return
    
    if GUILD:
        # check if DM user is in any approved guild
        if isinstance(message.channel, discord.channel.DMChannel):
            for guild_id in GUILD:
                if client.get_guild(guild_id).get_member(message.author.id):
                    break
            else:
                return
    if CATEGORY:
        # lock to threads in approved category
        if isinstance(message.channel, discord.channel.Thread):
            if not message.channel.parent.category_id in CATEGORY:
                return
        # lock to text channels if approved category
        elif not message.channel.category_id in CATEGORY:
            return

    # lock to approved user
    if USER_ID and not message.author.id in USER_ID:
        await send("Grant system not implemented yet. "+message.author.id)
        return

    system_prompt, model = channel_data.get(message.channel.id, DEFAULT)
    
    # dry-run
    if NO_GPT:
        await send("Test mode enabled (no GPT API calls). Model: "+model)
        return


    async with message.channel.typing():
        # use scanner if attachment found
        if (message.attachments or message.content.startswith("http")):
            if not SCANNER_PATH:
                await message.channel.send("Scanner not provided.")
                return
            
            file_url = message.content
            if message.attachments:
                file_url = message.attachments[0].url

            # update env with user changes during runtime
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = API_KEY
            result = subprocess.run(["powershell", "-File", SCANNER_PATH, file_url],
                                    capture_output=True, text=True, env=env)
            
            txt = result.stdout.splitlines()[-2].split()[-1]
            with open(txt) as txt:
                for line in txt.read().splitlines():
                    if line:
                        await message.channel.send(line)
            return

        msg = message.content.replace('--plugins', '').replace('--fallback', '')
        # plugins mode default for gpt4, --plugins override for gpt3
        if BACKEND_PATH and "--fallback" not in message.content:
            system = channel_data.get(message.channel.id, DEFAULT)
            if BACKEND_IMPORTED:
                backend.FEVER = system
                if "gpt-4" in model or "--plugins" in message.content:
                    try:
                        await send(backend.run(msg))
                        if backend.references:
                            await send("\n\n**References:**")
                            await send(backend.show_references())
                        return
                    except Exception as e:
                        await send(f"`Error: {str(e)}`\nRetrying without plugin:")
                return

            result = subprocess.run(["powershell", "-File", BACKEND_PATH,
                                     f"'{msg}'", f"'{system[0]}'", f"'{system[1]}"],
                                    capture_output=True, text=True)
            if (result := result.stdout.strip()) != "FALLBACK":
                await message.channel.send(result)
                return
            await message.channel.send("Retrying with fallback:")

            

        # fallback
        response = await openai.chat.completions.create(
        model=model,
        messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg},
            ]
        )
        await send(response.choices[0].message.content)


if __name__ == "__main__":
    client.run(TOKEN)