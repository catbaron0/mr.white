import logging
import sys
import os

import discord
from discord import app_commands, Interaction
from discord import Message
from discord.ext import commands

from workers.translator import Translator
from workers.repeater_manager import RepeaterManager
from workers.gambling.game_manager import GambleManager
from workers.dice import roll_dice
from utils.open_ai import gpt_intro
import utils.reboot as rb


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

# client = discord.Client(intents=intents)
# tree = app_commands.CommandTree(client)
client = commands.Bot(command_prefix="-", intents=intents, help_command=None)
tree = client.tree

repeater_manager = RepeaterManager(client)
translator = Translator()
gamble_manager = GambleManager()


@client.command(name="r")
async def roll(ctx, *args):
    reason = args[-1] if args else ""
    if roll_dice(reason) != []:
        reason = ""
    else:
        args = args[:-1]
        reason = f"**{reason}**"
    resp = f"{ctx.message.author.mention} 开始检定 {reason}:\n"

    for i, arg in enumerate(args):
        results = [str(r) for r in roll_dice(arg)]
        intro = f"第 {i+1} 次投掷结果："
        if len(args) == 1:
            intro = "投掷结果："
        if results:
            result_str = f"- {intro}: `" + ", ".join(results) + "`"
        else:
            result_str = f"⚠️ {intro}: 格式错误"
        resp += result_str + "\n"
    await ctx.message.reply(resp)


# -------------------------------------------
# *************** 翻译命令部分 ***************
@tree.command(name="translate", description="Translate the provided text.")
@app_commands.describe(text="要翻译的文本")
async def translate(interaction: Interaction, text: str):
    await interaction.response.defer()
    if text.strip() == "cfg":
        translator.load_config()
        await interaction.followup.send("翻译配置已重新加载。")
        return
    else:
        # 如果有参数，则翻译参数内容
        translated = await translator.translate(text)
        if translated:
            await interaction.followup.send(translated)


@tree.context_menu(name="翻译消息")
async def translate_msg(interaction: Interaction, reference: Message):
    await interaction.response.defer(ephemeral=False)

    translated = await translator.translate(reference.content)
    if not translated:
        translated = "翻译失败，请稍后重试。"
    await interaction.followup.send(translated, ephemeral=False)


# -------------------------------------------
# *************** roll dices ***************
@tree.command(name="roll", description="掷骰子。")
@app_commands.describe(dice="要掷的骰子表达式，例如 '2d6',  或者 'd10', 可以一次投掷多个骰子，用空格分隔")
@app_commands.describe(reason="检定理由，例如 '聆听', '侦查', '图书馆'")
async def dice(interaction: Interaction, dice: str, reason: str):
    await interaction.response.defer(ephemeral=False)

    user = interaction.user
    reason = f"**{reason}**" if reason else ""
    resp: str = f"{user.mention} 开始检定 {reason}:\n"

    dices = dice.split()
    for i, d in enumerate(dices):
        results = [str(r) for r in roll_dice(d)]
        resp_i = f"第 {i+1} 次投掷结果"

        # format the 1st response
        if len(dices) == 1:
            resp_i = "投掷结果"

        if results:
            result_str = f"- {resp_i}: `" + ", ".join(results) + "`"
        else:
            result_str = f"- {resp_i}: 格式错误"
        resp += result_str + "\n"
    await interaction.followup.send(resp, ephemeral=False)


# ---------------------------------------
# *************** 重启命令 ***************
@tree.command(name="reboot", description="重启机器人。重启是万能药。我也想重启啊！")
async def reboot(interaction: Interaction):
    await interaction.response.send_message("重启中...", ephemeral=False)
    rb.restart()
    await client.close()
    sys.exit(0)


# *************** 信息查询 ***************
@tree.command(name="intro", description="简单介绍某个事物。")
@app_commands.describe(item="你想知道什么？")
async def intro(interaction: Interaction, item: str):
    await interaction.response.defer(ephemeral=False, thinking=True)

    if len(item) > 20:
        answer = "你看看你自己在说什么"
    else:
        answer = await gpt_intro(item)
    await interaction.followup.send(answer, ephemeral=False)


# ----------------------------------------
# *************** 复读机命令 ***************
@tree.command(name="repeater", description="复读机命令。将语音频道重的消息复读出来。")
@app_commands.choices(cmd=[
    app_commands.Choice(name="启动", value="start"),
    app_commands.Choice(name="静音自己", value="mute"),
    app_commands.Choice(name="取消静音", value="unmute"),
    app_commands.Choice(name="停止", value="stop"),
    app_commands.Choice(name="更新配置", value="cfg"),
])
async def repeater(interaction: Interaction, cmd: str):
    await interaction.response.defer(ephemeral=True)
    try:
        await repeater_manager.run(interaction, cmd)
    except Exception as e:
        logger.error(f"❌ 复读机命令执行失败: {e}")
        response = await interaction.original_response()
        response_content = response.content if response else ""
        response_content += f"\n❌ 复读机命令执行失败: {e}"
        await interaction.followup.send(response_content, ephemeral=True)


@tree.command(name="rp", description="复读机命令。将语音频道重的消息复读出来。")
@app_commands.choices(cmd=[
    app_commands.Choice(name="启动", value="start"),
    app_commands.Choice(name="静音自己", value="mute"),
    app_commands.Choice(name="取消静音", value="unmute"),
    app_commands.Choice(name="停止", value="stop"),
    app_commands.Choice(name="更新配置", value="cfg"),
])
async def rp(interaction: Interaction, cmd: str):
    await interaction.response.defer(ephemeral=True)
    try:
        await repeater_manager.run(interaction, cmd)
    except Exception as e:
        logger.error(f"❌ 复读机命令执行失败: {e}")
        response = await interaction.original_response()
        response_content = response.content if response else ""
        response_content += f"\n❌ 复读机命令执行失败: {e}"
        await interaction.followup.send(response_content, ephemeral=True)


# ----------------------------------------
# *************** 骰子游戏 ***************
@tree.command(name="gambling", description="来自天国拯救的骰子游戏。")
async def gamble(interaction: Interaction):
    await gamble_manager.run(interaction)


# *******************************************
# *************** 运行客户端部分 ************
async def sync_commends():
    try:
        guild_id = os.getenv("DISCORD_GUILD_ID")
        assert guild_id is not None
        guild_id = int(guild_id)
    except (TypeError, ValueError):
        logger.error("❌ DISCORD_GUILD_ID 环境变量未设置或无效。请设置为有效的整数。")
        return
    guild = discord.Object(id=guild_id)
    tree.copy_global_to(guild=guild)
    synced = await tree.sync(guild=guild)
    logger.info(f"✅ 已同步 {len(synced)} 个命令")


@client.event
async def on_ready():
    await sync_commends()
    logger.info(f'✅ Logged in as {client.user}')


@client.event
async def setup_hook():
    await client.add_cog(repeater_manager)
    await client.add_cog(gamble_manager)


if __name__ == '__main__':
    discord_token = os.getenv("DISCORD_KEY")
    if discord_token:
        client.run(discord_token)
