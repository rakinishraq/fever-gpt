# bot.py
import os
import discord
from discord.ext import commands
from config import *
from sys import exc_info
from openai import AsyncOpenAI
import yaml
import importlib.util
import subprocess
import re
from pprint import pprint

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
COMMANDS = ["prompt", "model", "context_size"]
channel_data = {}

def load_data():
    global channel_data
    if not os.path.exists(DATA):
        with open(DATA, 'w') as f:
            yaml.dump({}, f)
    with open(DATA, 'r') as f:
        channel_data = yaml.safe_load(f)

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

    # handle reset
    if setting == "reset":
        await ctx.send("Defaults applied to this channel.\nPrompt: %s\nModel: %s\nContext size: %s" % DEFAULT)
        return
    # handle invalid prompts
    elif setting not in COMMANDS:
        await ctx.send("Invalid setting. Use %s/reset." % '/'.join(COMMANDS))
        return

    # handle prompt/model/context_size
    index = COMMANDS.index(setting)
    if not new_value:
        current_value = channel_data.get(ctx.channel.id, DEFAULT)[index]
        await ctx.send(f"Current channel {setting}: {current_value}")
    else:
        # error-check model
        if setting == "model" and new_value not in valid_models:
            await ctx.send("Warning: this model wasn't recognized but will be applied. "
                           f"Recognized models:\n`{', '.join(valid_models)}`")
        # error-check context_size
        if setting == "context_size":
            try:
                new_value = int(new_value)
                if new_value < 0:
                    raise ValueError
            except ValueError:
                await ctx.send("Context size must be a non-negative integer.")
                return

        if ctx.channel.id not in channel_data:
            channel_data[ctx.channel.id] = DEFAULT
        channel_data[ctx.channel.id][index] = new_value
        with open(DATA, "w") as f:
            yaml.dump(channel_data, f)
        await ctx.send(f"{setting.capitalize()} for this channel changed to: {new_value} -<@{ctx.author.id}>")
    
    await ctx.message.delete()


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
    if CHANNELS:
        # lock to approved channels and their threads
        if isinstance(message.channel, discord.channel.Thread):
            if not message.channel.parent.id in CHANNELS:
                return
        # lock to text channels if approved category
        elif not message.channel.id in CHANNELS:
            return

    # lock to approved user
    if USER_ID and not message.author.id in USER_ID:
        await send("Grant system not implemented yet. "+message.author.id)
        return
    
    load_data()

    # process slash commands
    if message.content.startswith("/"):
        await client.process_commands(message)
        return

    print(f"Processing message: {message.content} in {message.channel.id}.")

    # get channel settings
    system_prompt, model, context_size = channel_data.get(message.channel.id, DEFAULT)
    # remove --flags
    msg = message.content.replace('--plugins', '').replace('--fallback', '')

    # add context messages
    history = []
    async for hMsg in message.channel.history():
        m = hMsg.content
        # Exclude messages from users that start with "/setting"
        if hMsg.author != client.user and not m.startswith("/setting"):
            history.append("USER: "+m)
        # Only append messages from the bot that start with "~ "
        elif hMsg.author == client.user and m.startswith("~ "):
            history.append("GPT: "+m)
        if len(history) > context_size: break
    msg = '\n'.join(reversed(history[1:])) + '\n' + msg
    msg = '\n'.join(reversed(history))

    # dry-run
    if NO_GPT:
        await send(f"Test mode enabled (no GPT API calls).\n**Prompt:** {system_prompt}\n**Model:** {model}\n**Context Size:** {context_size}\n**Message:**\n>>> {msg}")
        return

    async with message.channel.typing():
        # use scanner if attachment/file link found [SCANNER MODE]
        has_link = re.search(r'http\S+', message.content) is not None
        if (message.attachments or has_link):
            if not SCANNER_PATH:
                await message.channel.send("Scanner not provided.")
                return
            
            if message.attachments:
                file_url = message.attachments[0].url
            elif has_link:
                # find link in msg
                link_match = re.search(r'http\S+', message.content)
                file_url = link_match.group()
                # remove link from message
                message.content = re.sub(r'http\S+', '', message.content).strip()

            # update env with user changes during runtime
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = API_KEY
            print(SCANNER_PATH, file_url, f"'{message.content}'")
            result = subprocess.run(["powershell", "-File", SCANNER_PATH, file_url, f"'{message.content}'"],
                                    capture_output=True, text=True, env=env)
            print(result.stdout)
            
            # get summary            
            txt = result.stdout.strip().splitlines()[3]+".overall_summary.txt"
            with open(txt) as txt:
                txt = txt.read()
            
            # debug send summary
            for line in txt.splitlines():
                if line:
                    send(summary := line)

        # plugins mode default for gpt4, --plugins override for gpt3 [PLUGIN MODE]
        if BACKEND_PATH and "--fallback" not in message.content:
            system = channel_data.get(message.channel.id, DEFAULT)
            if BACKEND_IMPORTED:
                backend.FEVER = system
                if "gpt-4" in model or "--plugins" in message.content:
                    try:
                        await send("~ "+backend.run(msg))
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
        await send("~ " + response.choices[0].message.content)


if __name__ == "__main__":
    client.run(TOKEN)