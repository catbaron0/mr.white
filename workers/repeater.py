import asyncio
import os
from pathlib import Path

import discord
from discord import FFmpegOpusAudio, Message, User, Member, Reaction

# from utils.open_ai import gpt_tts_f
from utils.tts import tts_f
from utils.text_processing import process_content
from utils.text_processing import get_custom_emoji
from config import config


class Repeater:
    def __init__(self, guild, voice_channel):
        self.message_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue()
        self.voice_channel = voice_channel
        self.guild = guild
        self.vc = guild.voice_client
        self.load_config()
        self.loop = asyncio.get_running_loop()
        self.muted_users = set()
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
            msg_type, _, user_name, content = await self.message_queue.get()
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

    def is_muted(self, user_id: str) -> bool:
        """
        检查用户是否被静音
        :param user_id: 用户ID
        :return: 如果用户被静音返回True，否则返回False
        """
        return str(user_id) in self.muted_users or "all" in self.muted_users

    async def append_message(self, message: Message):
        if message.channel.id != self.voice_channel.id:
            return
        print("DEBUG append message:", message)
        msg_type = "text"
        user_name = self.get_user_name(message.author)
        user_id = str(message.author.id)
        if self.is_muted(user_id):
            # ignore muted users
            print("DEBUG user is muted:", user_name, user_id)
            return
        content = message.content.strip()
        if content.startswith("#") or content.startswith("#") or content.startswith("-"):
            print("DEBUG ignore command message:", content)
            return
        if message.stickers:
            content = str(len(message.stickers))
            msg_type = "sticker"
        print("DEBUG append content:", content)
        await self.message_queue.put((msg_type, user_id, user_name, content))

    async def append_member_enter_exit_channel(self, member: Member, channel, msg_type: str):
        if self.voice_channel.id != channel.id:
            return
        user_name = self.get_user_name(member)
        user_id = str(member.id)
        await self.message_queue.put((msg_type, user_id, user_name, ""))

    async def append_reaction_add(self, reaction: Reaction, user: Member | User):
        if reaction.message.channel.id != self.voice_channel.id:
            return
        # if self.is_muted(str(user.id)):
        #     # ignore muted users
        #     print("DEBUG user is muted:", user.display_name, user.id)
        #     return
        user_name = self.get_user_name(user)
        target_user_name = self.get_user_name(reaction.message.author)
        user_id = str(user.id)
        print("DEBUG reaction:", reaction.emoji)
        await self.message_queue.put(("reaction", user_id, user_name, [target_user_name, reaction.emoji]))

    async def get_members(self):
        """获取当前语音频道的所有成员"""
        if self.voice_channel and self.voice_channel.guild:
            return [member for member in self.voice_channel.members if not member.bot]
        return []
