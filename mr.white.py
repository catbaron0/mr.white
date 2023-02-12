import sys
from pathlib import Path
import configparser
import asyncio

import discord
from discord.ext import commands

import lib.cmd as cmd
from lib.streamer import Streamer


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='-', intents=intents)
conf_path = Path(__file__).parent.absolute()

config = configparser.ConfigParser()
config.read(sys.argv[1])
discord_token = config.get("discord", "token")
tmdb_token = config.get("tmdb", "token")
openai_key = config.get("openai", "key")


py_hdl = cmd.PinyinCMD()
wiki_hdl = cmd.WikiCMD()
meme_hdl = cmd.MemeCMD()
tr_hdl = cmd.TranslateCMD()
mp3_hdl = cmd.Mp3CMD()
book_hdl = cmd.BookCMD()
movie_hdl = cmd.MovieCMD(tmdb_token)
chat_hdl = cmd.GptCMD(openai_key)


@bot.command(
    name=py_hdl.name,
    brief=py_hdl.brief,
    description=py_hdl.description,
    usage=py_hdl.usage
)
async def pinyin(ctx, *args):
    words = ' '.join(args)
    await py_hdl(ctx, words)


@bot.command(
    name=wiki_hdl.name,
    brief=wiki_hdl.brief,
    description=wiki_hdl.description,
    usage=wiki_hdl.usage
)
async def wiki(ctx, *args):
    words = ' '.join(args)
    await wiki_hdl(ctx, words)


@bot.command(
    name=meme_hdl.name,
    brief=meme_hdl.brief,
    description=meme_hdl.description,
    usage=meme_hdl.usage
)
async def meme(ctx, *args):
    meme = ' '.join(args)
    await meme_hdl(ctx, meme)


@bot.command(
    name=tr_hdl.name,
    brief=tr_hdl.brief,
    description=tr_hdl.description,
    usage=tr_hdl.usage
)
async def translate(ctx, *args):
    text = ' '.join(args)
    await tr_hdl(ctx, text)


@bot.command(
    name=mp3_hdl.name,
    brief=mp3_hdl.brief,
    description=mp3_hdl.description,
    usage=mp3_hdl.usage
)
async def mp3(ctx, *args):
    text = ' '.join(args)
    await mp3_hdl(ctx, text)


@bot.command(
    name=book_hdl.name,
    brief=book_hdl.brief,
    description=book_hdl.description,
    usage=book_hdl.usage
)
async def search_book(ctx, *args):
    text = ' '.join(args)
    await book_hdl(ctx, text)


@bot.command(
    name=movie_hdl.name,
    brief=movie_hdl.brief,
    description=movie_hdl.description,
    usage=movie_hdl.usage
)
async def search_movie(ctx, *args):
    text = ' '.join(args)
    await movie_hdl(ctx, text)


@bot.command(
    name=chat_hdl.name,
    brief=chat_hdl.brief,
    description=chat_hdl.description,
    usage=chat_hdl.usage
)
async def chat(ctx, *args):
    text = ' '.join(args)
    await chat_hdl(ctx, text)


@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))


async def main():
    await bot.add_cog(Streamer(bot, conf_path))


if __name__ == '__main__':
    asyncio.run(main())
    bot.run(discord_token)
