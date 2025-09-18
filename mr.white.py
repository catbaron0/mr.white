import sys
import asyncio
import logging

import discord
from discord.ext import commands

from workers.translator import Translator
from workers.repeater_manager import RepeaterManager
from workers.dice import roll_dice
from config.config import load_white_config
from utils.webhook_msg import process_webhook_start_rp
from utils.open_ai import gpt_intro


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("mw.white.py").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True


bot = commands.Bot(command_prefix="-", intents=intents, help_command=None)

repeater_manager = RepeaterManager(bot)
translator = Translator()

CFG = load_white_config()


@bot.command(name="rp")
async def repeater(ctx, args):
    await repeater_manager.run(ctx, args)


@bot.command(name="tr")
async def translate(ctx, *, text=""):
    if text.strip() == "cfg":
        translator.load_config()
        await ctx.message.reply("翻译配置已重新加载。")
        return
    if not text and ctx.message.reference:
        # 如果没有参数且是回复消息，则翻译被回复的消息
        replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if replied and replied.content:
            translated = await translator.translate(replied.content)
            await replied.reply(translated)
        return
    if text:
        # 如果有参数，则翻译参数内容
        translated = await translator.translate(text)
        if translated:
            await ctx.message.reply(translated)


@bot.command(name="r")
async def dice(ctx, *args):
    resp = ""
    reason = args[-1] if args else ""
    if roll_dice(reason) != []:
        reason = ""
    else:
        reason = reason + "检定"
        args = args[:-1]

    for i, arg in enumerate(args):
        results = [str(r) for r in roll_dice(arg)]
        intro = f"{reason}第 {i+1} 次结果"
        if len(args) == 1:
            intro = f"{reason}结果"
        if results:
            result_str = f"{intro}: `" + ", ".join(results) + "`"
        else:
            result_str = f"{intro}: 格式错误"
        resp += result_str + "\n"
    await ctx.message.reply(resp)


@bot.command(name="help")
async def help(ctx):
    help_msg = (
        "-rp start: 开启复读\n"
        "-rp stop: 关闭复读\n"
        "-rp restart: 重启机器人\n"
        "-rp mute: 不要复读自己的文字\n"
        "-rp unmute: 开始复读自己的文字\n"
        "-tr <文字>: 把<文字>翻译成中文\n\t如果没有参数，则翻译被回复的消息\n"
        "-intro <事物>: 简单介绍<事物>\n"
    )
    await ctx.message.reply(help_msg)


@bot.command(name="intro")
async def intro(ctx, args):
    if not args:
        answer = "-intro <事物>: 简单介绍<事物>\n"
    elif len(args) > 20:
        answer = "你看看你自己在说什么"
    else:
        async with ctx.channel.typing():
            answer = await gpt_intro(args)
    await ctx.message.reply(answer)


@bot.command(name="cfg")
async def update_cfg(ctx) -> None:
    global CFG
    CFG = load_white_config()
    await ctx.message.reply("更新配置成功！\n")


@bot.event
async def on_ready():
    logger.info(f'✅ Logged in as {bot.user}')


@bot.event
async def on_message(message):
    # 判断是否为命令消息
    if message.content and message.content.startswith(bot.command_prefix):
        cmd_name = message.content[len(str(bot.command_prefix)):].split()[0]
        if bot.get_command(cmd_name):
            await bot.process_commands(message)
            return

    # 只处理文字消息
    # 机器人的消息也会被 auto_translate 处理
    # 所以要在忽略机器人消息之前调用 auto_translat
    if message.content:
        await translator.auto_translate(message)

    if message.webhook_id:
        await process_webhook_start_rp(message, repeater_manager)

    # 忽略机器人自己的消息
    if message.author.bot:
        return

    # 让命令系统继续工作（非命令消息也要调用，防止其他自定义命令失效）
    logger.info(f"{message.author.display_name}:{message.content}")
    await bot.process_commands(message)


# @bot.event
# async def on_voice_state_update(member, before, after):
#     # Mute mumbers in the specific voice channel

#     # skip if the member joined the same channel
#     if before.channel == after.channel and before.self_mute == after.self_mute:
#         return

#     if after.channel and after.channel.id in CFG.get("muted_channels", []):
#         if not after.self_mute:
#             try:
#                 await member.edit(mute=True)
#                 print(f"{member.display_name} 加入频道，已静音")
#             except Exception as e:
#                 print(f"静音失败：{member.display_name} - {e}")
#     else:
#         # TODO: dont unmute if the member wasn't muted by this bot
#         if before.self_mute:
#             try:
#                 await member.edit(mute=False)
#                 print(f"{member.display_name} 离开频道，已解除静音")
#             except Exception as e:
#                 print(f"解除静音失败：{member.display_name} - {e}")


async def main():
    bot.add_cog(repeater_manager)


if __name__ == '__main__':
    discord_token = sys.argv[1]
    asyncio.run(main())
    bot.run(discord_token, reconnect=True)
