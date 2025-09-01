import asyncio
import os
from pathlib import Path
import logging

import discord
from discord import FFmpegOpusAudio, Message, User, Member, Reaction

from utils.open_ai import gpt_tts_f
from utils.tts import tts_f
from utils.text_processing import process_text_message
from utils.text_processing import emoji_to_str
from config import config
from workers.que_msg import QueueMessage


LOG = logging.getLogger(__name__)


class Repeater:
    def __init__(self, guild, voice_channel, voice_client):
        self.message_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue()
        self.voice_channel = voice_channel
        self.guild = guild
        self.vc = voice_client
        self.load_config()
        self.loop = asyncio.get_running_loop()
        self.muted_users = set()
        self.is_exiting = False
        asyncio.create_task(self.messages_to_audio())
        asyncio.create_task(self.read_messages())

    def load_config(self):
        LOG.info("Loading default_emoji")
        self.default_emoji = config.load_emoji_dict()
        LOG.info("Loading custom_emoji")
        self.config = config.load_guild_config(str(self.guild.id))

    def get_user_name(self, member: Member | User) -> str:
        user_name = member.display_name
        user_id = member.id
        return self.config["custom_username"].get(str(user_id), user_name)

    def generate_script(self, que_msg: QueueMessage) -> str:
        if que_msg.user:
            display_name = self.config["custom_username"].get(str(que_msg.user.id), que_msg.user.display_name)
        else:
            display_name = "那个谁"
        if que_msg.msg_type == "text":
            return process_text_message(
                que_msg,
                self.default_emoji,
                self.config["custom_emoji"],
                self.config["custom_username"]
            )

        if que_msg.msg_type == "sticker":
            assert que_msg.message is not None
            sticker_num = len(que_msg.message.stickers)
            return f"{display_name}发了{sticker_num}个表情包。"

        if que_msg.msg_type == "enter":
            user = que_msg.user
            LOG.info(f"{display_name} joined.")
            LOG.info(f"self_muted: {user.voice.self_mute if user and isinstance(user, Member) and user.voice else 'N/A'}")
            if user and isinstance(user, Member) and user.voice and user.voice.self_mute:
                return f"{display_name} 来了。{display_name} 你麦克风没开。"
            return f"{display_name} 来了。"

        if que_msg.msg_type == "exit":
            return f"{display_name} 走了。"

        if que_msg.msg_type == "reaction":
            emoji = emoji_to_str(
                que_msg.reaction_emoji,
                self.default_emoji,
                self.config["custom_emoji"],
            )
            if not emoji:
                emoji = "表情包"
            return f"{display_name} 用 {emoji} 回应了 {que_msg.reaction_target_user_name}。"
        return ""

    async def messages_to_audio(self):
        while True:
            que_message = await self.message_queue.get()
            text = self.generate_script(que_message)
            if not text:
                continue
            LOG.debug(f"tts text: {text}")
            # 生成音频文件
            audio_f = None
            user_id = que_message.user.id
            try:
                if self.config.get("tts_model", "default") == "gpt-tts":
                    default_voice_config = self.config["voice_config"]["default"]
                    voice_cfg = self.config["voice_config"].get(
                        str(user_id),
                        default_voice_config
                    )
                    audio_f = gpt_tts_f(text, voice_cfg)
                else:
                    audio_f = tts_f(text)
            except Exception as e:
                LOG.error(f"DEBUG tts err: {e}")

            if audio_f is None:
                LOG.error(f"tts error: {text}")
                continue
            await self.audio_queue.put(audio_f)
            LOG.debug(f"tts file: {audio_f}")

    async def play_audio(self, audio_f, cleanup=True):
        if not self.vc or not self.vc.is_connected():
            LOG.info("DEBUG voice client not connected")
            return
        while self.vc.is_playing():
            LOG.debug(f"DEBUG waiting for finish playing: {audio_f}")
            await asyncio.sleep(0.5)
        LOG.info(f"DEBUG play audio_f: {audio_f}")
        options = '-vn -acodec libopus'
        source = FFmpegOpusAudio(audio_f, bitrate=256, before_options="", options=options)
        try:
            self.vc.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._cleanup_audio_file(audio_f if cleanup else None),
                    self.loop
                )
            )
        except discord.errors.ClientException as e:
            LOG.error(f"DEBUG play err: {e}")

    async def read_messages(self):
        while True:
            audio_f = await self.audio_queue.get()
            await self.play_audio(audio_f)

    async def _cleanup_audio_file(self, audio_f):
        await asyncio.sleep(1)
        if Path(audio_f).exists():
            os.remove(audio_f)

    def is_muted(self, user_id: int) -> bool:
        """
        检查用户是否被静音
        :param user_id: 用户ID
        :return: 如果用户被静音返回True，否则返回False
        """
        return str(user_id) in self.muted_users or "all" in self.muted_users

    async def append_message(self, message: Message):
        if message.channel.id != self.voice_channel.id:
            return
        msg_type = "text"
        user_name = self.get_user_name(message.author)
        user_id = message.author.id
        if self.is_muted(user_id):
            # ignore muted users
            LOG.info(f"DEBUG user is muted: {user_name}({user_id})")
            return
        content = message.content.strip()
        if content.startswith("#") or content.startswith("#") or content.startswith("-"):
            return
        await self.message_queue.put(QueueMessage(
            msg_type=msg_type,
            message=message,
            user=message.author,
            reaction_emoji=None,
            reaction_target_user_name=None,
        ))

    async def append_member_enter_exit_channel(self, member: Member, channel, msg_type: str):
        if self.voice_channel.id != channel.id:
            return
        LOG.info(f"voice_state_update: {member.display_name} {msg_type}ed")
        await self.message_queue.put(QueueMessage(
            msg_type=msg_type,
            message=None,
            user=member,
            reaction_target_user_name=None,
            reaction_emoji=None,
        ))

    async def append_reaction_add(self, reaction: Reaction, user: Member | User):
        if reaction.message.channel.id != self.voice_channel.id:
            return
        target_user_name = self.get_user_name(reaction.message.author)
        LOG.info(f"reaction: {reaction.emoji}")
        await self.message_queue.put(QueueMessage(
            msg_type="reaction",
            message=None,
            user=user,
            reaction_target_user_name=target_user_name,
            reaction_emoji=reaction.emoji,
        ))

    async def get_members(self):
        """获取当前语音频道的所有成员"""
        if self.voice_channel and self.voice_channel.guild:
            return [member for member in self.voice_channel.members if not member.bot]
        return []
