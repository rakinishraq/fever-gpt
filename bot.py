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


prompts_file = "prompts.txt"
global channel_prompts
if os.path.exists(prompts_file):
    with open(prompts_file, "r") as f:
        channel_prompts = json.load(f)


@client.command(name="shutdown", brief="Shut ChatGPT down", help="Shut ChatGPT down.",
        description="Open the Pod bay doors, please, HAL.")
async def shutdown(ctx):
    await ctx.send(f"I'm afraid I can't do that, {ctx.author.mention}.")


@client.command(name="prompt", brief="Change the system prompt for this channel",
        help="Usage: /prompt [new_prompt]. Replace [new_prompt] with your desired system prompt.")
async def change_prompt(ctx, *, new_prompt=None):
    if new_prompt is None:
        current_prompt = channel_prompts.get(ctx.channel.id, DEFAULT)
        await ctx.send(f"Current prompt: {current_prompt}")
    else:
        channel_prompts[ctx.channel.id] = new_prompt
        with open(prompts_file, "w") as f:
            json.dump(channel_prompts, f)
        await ctx.send(f"System prompt for this channel changed to: {new_prompt}")


@client.event
async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {exc_info()}\n')
        else:
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
    elif message.channel.category_id != 1171050881626681364:
        return
    elif message.author.id != 748021473070940163:
        await message.channel.send("GPT grants not implemented for non-owner users yet.")
        return

    system_prompt = channel_prompts.get(message.channel.id, DEFAULT)

    response = openai.ChatCompletion.create(
      model=MODEL,
      messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.content},
        ]
    )

    # Send the generated response
    await message.channel.send(response['choices'][0]['message']['content'])


if __name__ == "__main__":
    openai.api_key = API_KEY
    client.run(TOKEN)