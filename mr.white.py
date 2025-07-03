import sys
import re
import random
import discord
from discord.ext import commands
import asyncio

from workers.cmd import TranslateCMD
from workers.repeater import RepeaterManager

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="-", intents=intents)

tr_hdl = TranslateCMD()
repeater_manager = RepeaterManager(bot)


@bot.command(name="rp")
async def repeater(ctx, args):
    await repeater_manager.run(ctx, args)


@bot.command(name="r")
async def dice(ctx, args):
    if args.startswith("d"):
        args = "1" + args
    pattern = r'^\d+d\d+$'
    if not re.match(pattern, args):
        return
    d1, d2 = map(int, args.split('d'))
    if d1 <= 0 or d2 <= 0:
        return
    results = []
    for _ in range(d1):
        result = random.randint(1, d2)
        results.append(str(result))
    result_str = ', '.join(results)
    await ctx.message.reply(result_str)


@bot.command(name="white")
async def help(ctx):
    help_msg = (
        "-rp start: 开启复读\n"
        "-rp stop: 关闭复读\n"
    )
    await ctx.message.reply(help_msg)


@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')


async def main():
    await bot.add_cog(repeater_manager)


if __name__ == '__main__':
    discord_token = sys.argv[1]
    asyncio.run(main())
    bot.run(discord_token, reconnect=True)
