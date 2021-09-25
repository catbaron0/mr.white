# from discord import Intents, Client
# from discord.ext.commands import Bot
# from discord_slash import SlashCommand
# from discord_slash.utils.manage_components import create_button, create_actionrow
# from discord_slash.model import ButtonStyle
# from discord import Client, Intents, Embed
# from discord_slash import SlashCommand, SlashContext

import lib.cmd as cmd
from discord.ext import commands
from lib.streamer import Streamer
import sys


# bot = Bot(intents=Intents.default(), self_bot=True, command_prefix='/')
# slash = SlashCommand(bot)
# bot.load_extension("lib.streamer")
# @bot.command(name="btn")
# async def buttons(ctx, arg):
#     buttons = [
#         create_button(style=ButtonStyle.green, label="��"),
#         create_button(style=ButtonStyle.blue, label="⏸️")
#     ]
#     action_row = create_actionrow(*buttons)
#     await ctx.send("test", components=[action_row])


bot = commands.Bot(command_prefix='/')


py_hdl = cmd.PinyinCMD()
@bot.command(
    name=py_hdl.name,
    brief=py_hdl.brief,
    description=py_hdl.description,
    usage=py_hdl.usage
)
async def pinyin(ctx, *args):
    words = ' '.join(args)
    await py_hdl(ctx, words)

wiki_hdl = cmd.WikiCMD()
@bot.command(
    name=wiki_hdl.name,
    brief=wiki_hdl.brief,
    description=wiki_hdl.description,
    usage=wiki_hdl.usage
)
async def wiki(ctx, *args):
    words = ' '.join(args)
    await wiki_hdl(ctx, words)

meme_hdl = cmd.MemeCMD()
@bot.command(
    name=meme_hdl.name,
    brief=meme_hdl.brief,
    description=meme_hdl.description,
    usage=meme_hdl.usage
)
async def meme(ctx, *args):
    meme = ' '.join(args)
    await meme_hdl(ctx, meme)

tr_hdl = cmd.TranslateCMD()
@bot.command(
    name=tr_hdl.name,
    brief=tr_hdl.brief,
    description=tr_hdl.description,
    usage=tr_hdl.usage
)
async def translate(ctx, *args):
    text = ' '.join(args)
    await tr_hdl(ctx, text)

mp3_hdl = cmd.Mp3CMD()
@bot.command(
    name=mp3_hdl.name,
    brief=mp3_hdl.brief,
    description=mp3_hdl.description,
    usage=mp3_hdl.usage
)
async def mp3(ctx, *args):
    text = ' '.join(args)
    await mp3_hdl(ctx, text)

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))

@bot.event
async def on_message(message):
    msg_txt = message.content
    if msg_txt.startswith('-'):
        reply = "Are you tring yo run a command?\n"
        reply += "Pleash try to use / instead."
        await message.reply(reply)
    await bot.process_commands(message)

bot.add_cog(Streamer(bot))

bot.run(sys.argv[1])
