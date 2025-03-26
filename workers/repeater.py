import asyncio
import os
from pathlib import Path

from discord import FFmpegOpusAudio, Message, User, Member, Reaction
from discord.ext import commands

from utils.open_ai import tts_f
from utils.text_processing import generate_script
from config import config


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

    def get_user_name(self, member: Member | User) -> str:
        user_name = member.display_name
        user_id = member.id
        return self.user_name_config.get(str(user_id), user_name)

    async def messages_to_audio(self):
        while True:
            if self.message_queue.empty():
                await asyncio.sleep(0.1)
                continue
            msg_type, user_id, user_name, content = await self.message_queue.get()
            text = generate_script(msg_type, user_name, content)
            if not text:
                continue
            voice_cfg = self.voice_config.get(str(user_id), self.voice_config["default"])
            voice = voice_cfg["voice"]
            ins = voice_cfg.get("ins", "沉稳的")
            speed = voice_cfg.get("speed", 4.0)
            # 生成音频文件
            await self.audio_queue.put(tts_f(text, voice, ins, speed))

    async def read_messages(self):
        while True:
            if self.vc.is_playing() or self.audio_queue.empty():
                await asyncio.sleep(0.1)
                continue
            while self.vc.is_playing():
                await asyncio.sleep(0.1)
            audio_f = await self.audio_queue.get()
            options = '-vn -acodec libopus'
            source = FFmpegOpusAudio(audio_f, bitrate=256, before_options="", options=options)
            self.vc.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.cleanup(audio_f),
                    self.loop
                )
            )
    
    async def cleanup(self, audio_f):
        await asyncio.sleep(1)
        if Path(audio_f).exists():
            os.remove(audio_f)

    async def append_message(self, message: Message):
        if message.channel.id != self.channel.id:
            return
        print(message)
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
        await self.message_queue.put(("reaction", user_id, user_name, [target_user_name, reaction.emoji]))


class RepeaterManager(commands.Cog):
    def __init__(self, bot):
        self.repeaters = {}
        self.bot = bot

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
            await ctx.message.reply(f"❌...复读模块繁忙: {channel.name}")

        else:
            await channel.connect()
            self.repeaters[guild.id] = Repeater(ctx.guild, channel)
            await ctx.message.reply(
                "✅...语音频道活跃测试...\n"
                f"✅...复读模块就位: {channel.name}"
            )

    async def stop_repeat(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.repeaters:
            vc = self.repeaters[guild_id].vc
            if vc and vc.is_connected():
                await vc.disconnect()
            del self.repeaters[guild_id]

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
        if args and args[0] == "cfg":
            await self.update_config(ctx)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            # Ignore bot messages
            return
        if not message.guild:
            # Not belong to a server
            return
        guild_id = message.guild.id
        if guild_id in self.repeaters:
            await self.repeaters[guild_id].append_message(message)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """监听用户语音状态变化"""
        print(member, before, after)

        if before.channel and after.channel and before.channel.id == after.channel.id:
            return

        if before.channel is not None:
            # 用户加入语音频道
            guild_id = before.channel.guild.id
            msg_type = "exit"
            if guild_id in self.repeaters:
                await self.repeaters[guild_id].append_member_enter_exit_channel(member, before.channel, msg_type)

        if after.channel is not None:
            # 用户加入语音频道
            msg_type = "enter"
            guild_id = after.channel.guild.id
            if guild_id in self.repeaters:
                await self.repeaters[guild_id].append_member_enter_exit_channel(member, after.channel, msg_type)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member | User):
        if user.bot or not reaction.message.guild:
            return
        guild_id = reaction.message.guild.id
        if guild_id in self.repeaters:
            await self.repeaters[guild_id].append_reaction_add(reaction, user)
