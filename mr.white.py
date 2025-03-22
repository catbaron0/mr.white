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


# @bot.event
# async def on_message(message):
#     print(message)

# 使用普通命令装饰器
@bot.command(name="hello")
async def hello(ctx):
    print("hello command triggered")
    await ctx.send("你好！👋")


@bot.command(name="bye")
async def bye(ctx):
    print("bye command triggered")
    await ctx.send("再见！👋")

@bot.command(name="rp")
async def repeater(ctx, args):
    print("rp command triggered")
    await repeater_manager.run(ctx, args)


@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')


async def main():
    await bot.add_cog(repeater_manager)


if __name__ == '__main__':
    discord_token = sys.argv[1]
    asyncio.run(main())
    bot.run(discord_token)