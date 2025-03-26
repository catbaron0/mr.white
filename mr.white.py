import sys
import discord
from discord.ext import commands
import asyncio

from workers.cmd import TranslateCMD
from workers.repeater import RepeaterManager

intents = discord.Intents.default()
intents.message_content = True  # 启用消息内容意图

bot = commands.Bot(command_prefix="-", intents=intents)

tr_hdl = TranslateCMD()
repeater_manager = RepeaterManager(bot)


@bot.command(name="rp")
async def repeater(ctx, args):
    await repeater_manager.run(ctx, args)


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
    bot.run(discord_token)