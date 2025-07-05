import sys
import re
import random
import discord
from discord.ext import commands
import asyncio

from workers.translator import Translator
from workers.repeater import RepeaterManager

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="-", intents=intents)

repeater_manager = RepeaterManager(bot)
translator = Translator()


@bot.command(name="rp")
async def repeater(ctx, args):
    await repeater_manager.run(ctx, args)


@bot.command(name="tr")
async def translate(ctx, args=""):
    if args == "cfg":
        translator.load_config()
        await ctx.message.reply("翻译配置已重新加载。")
        return
    if not args and ctx.message.reference:
        # 如果没有参数且是回复消息，则翻译被回复的消息
        replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if replied and replied.content:
            translated = await translator.translate(replied.content)
            await replied.reply(translated)
        return
    if args:
        # 如果有参数，则翻译参数内容
        translated = await translator.translate(args)
        if translated:
            await ctx.message.reply(translated)


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


@bot.event
async def on_message(message):
    # 判断是否为命令消息
    if message.content and message.content.startswith(bot.command_prefix):
        cmd_name = message.content[len(bot.command_prefix):].split()[0]
        if bot.get_command(cmd_name):
            await bot.process_commands(message)
            return

    # 只处理文字消息
    # 机器人的消息也会被 auto_translate 处理
    # 所以要在忽略机器人消息之前调用 auto_translat
    if message.content:
        await translator.auto_translate(message)

    # 忽略机器人自己的消息
    if message.author.bot:
        return

    # 让命令系统继续工作（非命令消息也要调用，防止其他自定义命令失效）
    await bot.process_commands(message)


async def main():
    await bot.add_cog(repeater_manager)


if __name__ == '__main__':
    discord_token = sys.argv[1]
    asyncio.run(main())
    bot.run(discord_token, reconnect=True)
