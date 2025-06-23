import asyncio
import os
from pathlib import Path

import discord
from discord import FFmpegOpusAudio, Message, User, Member, Reaction
from discord.ext import commands

# from utils.open_ai import gpt_tts_f
from utils.tts import tts_f
from utils.text_processing import process_content, process_user_name
# from utils.text_processing import  translate_emoji
from utils.text_processing import get_custom_emoji
from config import config

AUDIO_ENTER = Path(__file__).parent.parent / "data" / "kita.mp3"
IMG_ENTER = Path(__file__).parent.parent / "data" / "kita.png"


class Repeater:
    def __init__(self, guild, channel):
        self.message_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue()
        self.channel = channel
        self.guild = guild
        self.vc = guild.voice_client
        self.load_config()
        self.loop = asyncio.get_running_loop()
        asyncio.create_task(self.messages_to_audio())
        asyncio.create_task(self.read_messages())

    def load_config(self):
        self.voice_config = config.load_voices_config()
        self.user_name_config = config.load_username_config()
        self.emoji_dict = config.load_emoji_dict()
        self.custom_emoji_dict = config.load_custom_emoji_dict(str(self.guild.id))

    def get_user_name(self, member: Member | User) -> str:
        user_name = member.display_name
        user_id = member.id
        return self.user_name_config.get(str(user_id), user_name)

    def generate_script(self, msg_type: str, user_name: str, content: str | list[str]) -> str:
        user_name = process_user_name(user_name)
        if isinstance(content, str):
            content = process_content(content, self.emoji_dict, self.custom_emoji_dict)

        if msg_type == "text" and content:
            if len(content) > 100:
                text = f"{user_name}说了很多东西你们自己看吧"
            else:
                text = f"{user_name}说, {content}"
            return text

        if msg_type == "sticker":
            return f"{user_name}发了{content}个表情包。"

        if msg_type == "enter":
            return f"{user_name} 来了。"

        if msg_type == "exit":
            return f"{user_name} 走了。"

        if msg_type == "reaction" and isinstance(content, list):
            target_user_name, emoji = content
            emoji = get_custom_emoji(emoji, self.custom_emoji_dict)
            if not emoji:
                emoji = "表情包"
            return f"{user_name} 用 {emoji} 回应了 {target_user_name}。"
        return ""

    async def messages_to_audio(self):
        while True:
            msg_type, user_id, user_name, content = await self.message_queue.get()
            text = self.generate_script(msg_type, user_name, content)
            if not text:
                continue
            print("DEBUG tts text:", text)
            # 生成音频文件
            # try:
            # voice = voice_cfg["voice"]
            # ins = voice_cfg.get("ins", "沉稳的")
            # speed = voice_cfg.get("speed", 4.0)
            # voice_cfg = self.voice_config.get(str(user_id), self.voice_config["default"])
            #     audio_f = gpt_tts_f(text, voice, ins, speed)
            # except Exception as e:
            # print("DEBUG tts err:", e)
            audio_f = tts_f(text)
            if audio_f is None:
                print("DEBUG tts error:", text)
                continue
            await self.audio_queue.put(audio_f)
            print("DEBUG tts:", audio_f)

    async def play_audio(self, audio_f, cleanup=True):
        if not self.vc or not self.vc.is_connected():
            print("DEBUG voice client not connected")
            return
        while self.vc.is_playing():
            print("DEBUG waiting for finish playing:", audio_f)
            await asyncio.sleep(0.5)
        print("DEBUG play audio_f:", audio_f)
        options = '-vn -acodec libopus'
        source = FFmpegOpusAudio(audio_f, bitrate=256, before_options="", options=options)
        print("DEBUG play:", audio_f)
        try:
            self.vc.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._cleanup_audio_file(audio_f if cleanup else None),
                    self.loop
                )
            )
        except discord.errors.ClientException as e:
            print("DEBUG play err:", e)

    async def read_messages(self):
        while True:
            audio_f = await self.audio_queue.get()
            await self.play_audio(audio_f)

    async def _cleanup_audio_file(self, audio_f):
        await asyncio.sleep(1)
        if Path(audio_f).exists():
            os.remove(audio_f)

    async def append_message(self, message: Message):
        if message.channel.id != self.channel.id:
            return
        print("DEBUG append message:", message)
        msg_type = "text"
        user_name = self.get_user_name(message.author)
        user_id = str(message.author.id)
        content = message.content
        if message.stickers:
            content = str(len(message.stickers))
            msg_type = "sticker"
        await self.message_queue.put((msg_type, user_id, user_name, content))

    async def append_member_enter_exit_channel(self, member: Member, channel, msg_type: str):
        if self.channel.id != channel.id:
            return
        user_name = self.get_user_name(member)
        user_id = str(member.id)
        await self.message_queue.put((msg_type, user_id, user_name, ""))

    async def append_reaction_add(self, reaction: Reaction, user: Member | User):
        if reaction.message.channel.id != self.channel.id:
            return
        user_name = self.get_user_name(user)
        target_user_name = self.get_user_name(reaction.message.author)
        user_id = str(user.id)
        print("DEBUG reaction:", reaction.emoji)
        await self.message_queue.put(("reaction", user_id, user_name, [target_user_name, reaction.emoji]))

    async def get_members(self):
        """获取当前语音频道的所有成员"""
        if self.channel and self.channel.guild:
            return [member for member in self.channel.members if not member.bot]
        return []


class RepeaterManager(commands.Cog):
    def __init__(self, bot):
        self.repeaters = {}
        self.stop_locks = {}  # NEW: 防止并发 stop
        self.bot = bot

    async def restart_repeat(self, ctx):
        await self.stop_repeat(ctx)
        await self.start_repeat(ctx)

    async def start_repeat(self, ctx):
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            channel = None
        guild = ctx.guild
        if not channel:
            await ctx.message.reply("❌...语音频道活跃测试...")
            return

        if guild.id in self.repeaters:
            # The bot is working
            self.repeaters[guild.id].channel.disconnect()
            await ctx.message.reply(f"❌...复读模块繁忙: {channel.name}")

        else:
            await ctx.message.reply(
                "✅...语音频道活跃测试...\n"
            )
            await channel.connect()
            self.repeaters[guild.id] = Repeater(ctx.guild, channel)
            await ctx.message.reply(
                f"✅...复读模块就位: {channel.name}"
            )
            await self.repeaters[guild.id].play_audio(AUDIO_ENTER, cleanup=False)
            await self.repeaters[guild.id].channel.send(file=discord.File(IMG_ENTER))

    async def _stop_repeat(self, guild_id):
        if guild_id not in self.stop_locks:
            self.stop_locks[guild_id] = asyncio.Lock()

        async with self.stop_locks[guild_id]:
            repeater = self.repeaters.get(guild_id)
            if not repeater:
                print(f"DEBUG repeater already stopped for guild {guild_id}")
                return

            vc = repeater.vc
            if vc and vc.is_connected():
                await vc.disconnect()

            print(f"DEBUG stop repeat for guild {guild_id}")
            del self.repeaters[guild_id]

        del self.stop_locks[guild_id]

    async def stop_repeat(self, ctx):
        guild_id = ctx.guild.id
        await self._stop_repeat(guild_id)

    async def update_config(self, ctx):
        guild_id = ctx.guild.id
        print("更新配置文件")
        try:
            self.repeaters[guild_id].load_config()
            await ctx.message.reply("✅...配置文件已更新")
        except Exception as e:
            await ctx.message.reply(f"❌...配置文件更新失败: {e}")

    async def run(self, ctx, *args):
        if args and args[0] == "start":
            await self.start_repeat(ctx)
        if args and args[0] == "stop":
            await self.stop_repeat(ctx)
        if args and args[0] == "restart":
            await self.restart_repeat(ctx)
        if args and args[0] == "cfg":
            await self.update_config(ctx)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            # Ignore bot messages
            return
        try:
            print("DEBUG avatar on message:", message.author.display_name)
            print("DEBUG avatar on message:", message.author.display_avatar)
        except Exception as e:
            print("DEBUG avatar err:", e)
        if not message.guild:
            # Not belong to a server
            return
        print("DEBUG guild:", message.guild)
        guild_id = message.guild.id
        if guild_id in self.repeaters:
            print("DEBUG message:", message.content)
            await self.repeaters[guild_id].append_message(message)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """监听用户语音状态变化"""
        print(member, before, after)

        if before.channel and after.channel and before.channel.id == after.channel.id:
            return

        if before.channel is not None:
            # 用户离开语音频道
            guild_id = before.channel.guild.id
            msg_type = "exit"
            if guild_id in self.repeaters and before.channel.id == self.repeaters[guild_id].channel.id:
                member_count = len(before.channel.members)
                print(f"DEBUG member exit, {member_count} members left")
                # 过滤掉机器人，只统计人类成员
            non_bot_members = [m for m in before.channel.members if not m.bot]
            if len(non_bot_members) == 0:
                # 频道中已经没有人类用户了
                print("DEBUG no human members left, disconnecting channel")
                await self._stop_repeat(guild_id)
            else:
                if guild_id in self.repeaters and before.channel.id == self.repeaters[guild_id].channel.id:
                    await self.repeaters[guild_id].append_member_enter_exit_channel(member, before.channel, msg_type)

        if after.channel is not None:
            # 用户加入语音频道
            msg_type = "enter"
            guild_id = after.channel.guild.id
            print("DEBUG avatar on_enter:", member.display_avatar)
            if guild_id in self.repeaters and after.channel.id == self.repeaters[guild_id].channel.id:
                await self.repeaters[guild_id].append_member_enter_exit_channel(member, after.channel, msg_type)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member | User):
        if user.bot or not reaction.message.guild:
            return
        guild_id = reaction.message.guild.id
        try:
            print("DEBUG avatar on_reaction_add:", user.display_avatar)
        except Exception as e:
            print("DEBUG avatar err:", e)
        if guild_id in self.repeaters:
            await self.repeaters[guild_id].append_reaction_add(reaction, user)
