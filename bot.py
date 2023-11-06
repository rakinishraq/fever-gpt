# bot.py
import os
import discord
from discord.ext import commands
from config import *
from sys import exc_info
import openai
import json

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)


global channel_prompts
with open(CHANNELS, 'a+') as f:
    channel_prompts = json.load(f)


@client.command(name="shutdown", brief="Shut ChatGPT down", help="Shut ChatGPT down.",
        description="Open the Pod bay doors, please, HAL.")
async def shutdown(ctx):
    await ctx.send(f"I'm afraid I can't do that, {ctx.author.mention}.")


@client.command(name="prompt", brief="Change the system prompt for this channel",
        help="Usage: /prompt [new_prompt]. Replace [new_prompt] with your desired system prompt.")
async def change_prompt(ctx, *, new_prompt=None):
    if not new_prompt:
        current_prompt = channel_prompts.get(ctx.channel.id, DEFAULT)
        await ctx.send(f"Current prompt: {current_prompt}")
    else:
        channel_prompts[ctx.channel.id] = new_prompt
        with open(CHANNELS, "w") as f:
            json.dump(channel_prompts, f)
        await ctx.send(f"System prompt for this channel changed to: {new_prompt}")


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

    guild = discord.utils.get(client.guilds, name=GUILD)
    if not guild:
        return


@client.event
async def on_message(message):
    if message.content.startswith("/"):
        await client.process_commands(message)
        return
    elif message.author == client.user:
        return
    elif isinstance(message.channel, discord.channel.DMChannel):
        pass
    elif message.channel.category_id != 1171050881626681364:
        return
    
    if message.author.id != 748021473070940163:
        await message.channel.send("GPT grants not implemented for non-owner users yet.")
        return

    system_prompt = channel_prompts.get(message.channel.id, DEFAULT)

    if NO_GPT:
        await message.channel.send("Test mode enabled (no GPT API calls).")
        return

    response = openai.ChatCompletion.create(
      model=MODEL,
      messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.content},
        ]
    )

    await message.channel.send(response['choices'][0]['message']['content'])


if __name__ == "__main__":
    openai.api_key = API_KEY
    client.run(TOKEN)