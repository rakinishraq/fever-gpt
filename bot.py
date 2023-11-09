# bot.py
import os
import discord
from discord.ext import commands
from config import *
from sys import exc_info
import openai
import json
import importlib.util

if BACKEND_PATH:
    spec = importlib.util.spec_from_file_location("module.name", BACKEND_PATH)
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)

global channel_data
with open(CHANNELS, 'a+') as f:
    channel_data = json.load(f) if f.read() else {}


@client.command(name="shutdown", brief="Shut ChatGPT down", help="Shut ChatGPT down.",
        description="Open the Pod bay doors, please, HAL.")
async def shutdown(ctx):
    await ctx.send(f"I'm afraid I can't do that, {ctx.author.mention}.")


@client.command(name="setting", brief="Change the system prompt and/or model for this channel",
        help="Usage: /setting prompt [new_prompt] or /setting model [new_model] or /setting reset.")
async def setting(ctx, setting, *, new_value=None):
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

    # process slash commands
    if message.content.startswith("/"):
        await client.process_commands(message)
        return
    # prevent self-reply loop
    elif message.author == client.user:
        return
    elif GUILD:
        # check if DM user is in any approved guild
        if isinstance(message.channel, discord.channel.DMChannel):
            for guild_id in GUILD:
                if client.get_guild(guild_id).get_member(message.author.id):
                    break
            else:
                return
    elif CATEGORY:
        # lock to threads in approved category
        if isinstance(message.channel, discord.channel.Thread):
            if not message.channel.parent.category_id in CATEGORY:
                return
        # lock to text channels if approved category
        elif not message.channel.category_id in CATEGORY:
            return
    # lock to approved user
    if USER_ID and not message.author.id in USER_ID:
        await send("GPT grants not implemented for non-owner users yet. "+message.author.id)
        return

    system_prompt, model = channel_data.get(message.channel.id, DEFAULT)

    if NO_GPT:
        await send("Test mode enabled (no GPT API calls). Model: "+model)
        return

    async with message.channel.typing():
        msg = message.content.replace('--plugins', '').replace('--fallback', '')
        # plugins mode default for gpt4, --plugins override for gpt3
        if BACKEND_PATH and "--fallback" not in message.content:
            backend.MARKDOWN_MODS = channel_data.get(message.channel.id, DEFAULT)
            if "gpt-4" in model or "--plugins" in message.content:
                try:
                    await send(backend.run(msg))
                    if backend.references:
                        await send("\n\n**References:**")
                        await send(backend.show_references())
                    return
                except Exception as e:
                    await send(f"`Error: {str(e)}`\nRetrying without plugin:")

        # fallback
        response = openai.ChatCompletion.create(
        model=model,
        messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg},
            ]
        )
        await send(response['choices'][0]['message']['content'])


if __name__ == "__main__":
    openai.api_key = API_KEY
    client.run(TOKEN)