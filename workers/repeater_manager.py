
import asyncio
from pathlib import Path
import logging

import discord
from discord import Interaction
from discord import User, Member, Reaction
from discord.ext import commands

from workers.repeater import Repeater
from utils.connect import connect_voice_channel

AUDIO_ENTER = Path(__file__).parent.parent / "data" / "kita.mp3"
IMG_ENTER = Path(__file__).parent.parent / "data" / "kita.png"

LOG = logging.getLogger(__name__)


class RepeaterManager(commands.Cog):
    def __init__(self, bot):
        self.repeaters: dict[int, Repeater] = {}
        self.stop_locks = {}  # NEW: 防止并发 stop

        # Cog needs bot reference to register listeners
        self.bot = bot


    async def _start_repeater(self, guild,  user_voice_channel):
        try:
            vc = None
            for i in range(3):
                vc = await connect_voice_channel(user_voice_channel)
                if vc and vc.is_connected():
                    break
                LOG.error(f"Voice channel connection error: retry {i+1}/3")
                # await interaction.edit_original_response(content=response_content)
                await asyncio.sleep(1.0)
        except Exception as e:
            # response_content += f"\n❌...语音频道连接错误 {e}"
            # await interaction.edit_original_response(content=response_content)
            LOG.error(f"Voice channel connection error: {e}")
            return

        if not (vc and vc.is_connected()):
            # response_content += "\n❌...语音频道连接失败"
            # await interaction.edit_original_response(content=response_content)
            LOG.error("Voice channel connection failed")
            return

        self.repeaters[guild.id] = Repeater(guild, user_voice_channel, vc)
        # response_content += f"\n✅...复读模块就位: {user_voice_channel.name}"
        # await interaction.edit_original_response(content=response_content)

        await self.repeaters[guild.id].play_audio(AUDIO_ENTER, cleanup=False)
        await self.repeaters[guild.id].voice_channel.send(file=discord.File(IMG_ENTER))

    async def start_repeater(self, interaction: Interaction):
        assert interaction.guild is not None
        assert interaction.user is not None
        assert isinstance(interaction.user, Member)

        response_content = "正在启动..."
        await interaction.followup.send(response_content)

        if interaction.user.voice:
            user_voice_channel = interaction.user.voice.channel
        else:
            user_voice_channel = None

        if not user_voice_channel:
            response_content += "\n❌...语音频道活跃测试，用户需要加入语音频道"
            await interaction.edit_original_response(content=response_content)
            return
        else:
            response_content += "\n✅...语音频道活跃测试..."
            await interaction.edit_original_response(content=response_content)

        guild = interaction.guild
        if guild.id in self.repeaters and guild.voice_client and guild.voice_client.channel:
            # The bot is working
            voice_channel_name = guild.voice_client.channel.name  # type: ignore
            response_content += f"\n❌...复读模块繁忙: {voice_channel_name}"
            await interaction.edit_original_response(content=response_content)
            return
        else:
            response_content += "\n✅...连接语音节点..."
            await interaction.edit_original_response(content=response_content)

        await self._start_repeater(guild, user_voice_channel)
        # try:
        #     vc = None
        #     for i in range(3):
        #         vc = await connect_voice_channel(user_voice_channel)
        #         if vc and vc.is_connected():
        #             break
        #         response_content += f"\n❌...第 {i+1} 次连接失败，正在重试..."
        #         await interaction.edit_original_response(content=response_content)
        #         await asyncio.sleep(1.0)
        # except Exception as e:
        #     response_content += f"\n❌...语音频道连接错误 {e}"
        #     await interaction.edit_original_response(content=response_content)
        #     LOG.error(f"Voice channel connection error: {e}")
        #     return

        # if not (vc and vc.is_connected()):
        #     response_content += "\n❌...语音频道连接失败"
        #     await interaction.edit_original_response(content=response_content)
        #     LOG.error("Voice channel connection failed")
        #     return

        # self.repeaters[guild.id] = Repeater(guild, user_voice_channel, vc)
        # response_content += f"\n✅...复读模块就位: {user_voice_channel.name}"
        # await interaction.edit_original_response(content=response_content)

        # await self.repeaters[guild.id].play_audio(AUDIO_ENTER, cleanup=False)
        # await self.repeaters[guild.id].voice_channel.send(file=discord.File(IMG_ENTER))

    async def stop_repeater(self, guild_id):
        if guild_id not in self.stop_locks:
            self.stop_locks[guild_id] = asyncio.Lock()

        async with self.stop_locks[guild_id]:
            repeater = self.repeaters.get(guild_id)
            if not repeater:
                LOG.info(f"Repeater already stopped for guild {guild_id}")
                return
            repeater.is_exiting = True

            vc = repeater.vc
            if vc and vc.is_connected():
                LOG.info(f"Disconnecting vc: {guild_id}")
                await vc.disconnect(force=True)
                await asyncio.sleep(1)
            vc = repeater.guild.voice_client
            if vc and vc.is_connected():
                LOG.info(f"Disconnecting voice_client: {guild_id}")
                await vc.disconnect(force=True)
                await asyncio.sleep(1)

            LOG.info(f"Stop repeat for guild {guild_id}")
            if guild_id in self.repeaters:
                del self.repeaters[guild_id]

        if guild_id in self.stop_locks:
            del self.stop_locks[guild_id]

    async def update_config(self, interaction: Interaction):
        if not interaction.guild:
            return
        guild = interaction.guild
        LOG.info("更新配置文件")
        try:
            self.repeaters[guild.id].load_config()
            await interaction.followup.send("✅...配置文件已更新")
        except Exception as e:
            LOG.error(f"❌...配置文件更新失败: {e}")
            await interaction.followup.send(f"❌...配置文件更新失败 {e}")

    async def mute(self, interaction: Interaction):
        if not interaction.guild:
            return
        guild = interaction.guild
        user = interaction.user
        try:
            self.repeaters[guild.id].muted_users.add(user.id)
            muted_users = self.repeaters[guild.id].muted_users
            logging.info(f"Mute user: {muted_users}")
            await interaction.followup.send(f"✅...{user.mention} 已被静音")
        except Exception as e:
            await interaction.followup.send(f"❌...{user.mention} 静音失败: {e}")
            LOG.error(f"Mute error: {e}")

    async def unmute(self, interaction):
        if not interaction.guild:
            return
        guild = interaction.guild
        user = interaction.user
        try:
            self.repeaters[guild.id].muted_users.remove(user.id)
            await interaction.followup.send(f"✅...{user.mention} 已解除静音")
        except Exception as e:
            await interaction.followup.send(f"❌...{user.mention} 解除静音失败: {e}")
            LOG.error(f"DEBUG unmute error: {e}")

    async def run(self, interaction: Interaction, cmd: str):
        if cmd == "start":
            await self.start_repeater(interaction)
        if cmd == "stop" and interaction.guild:
            await self.stop_repeater(interaction.guild.id)
        if cmd == "mute":
            await self.mute(interaction)
        if cmd == "unmute":
            await self.unmute(interaction)
        if cmd == "cfg":
            await self.update_config(interaction)

    async def _process_member_exiting(self, member, before, after):
        '''
        Append an exit message to the msg queue
        Automatically quit the bot if no human member is left.
        '''
        if before.channel and after.channel and before.channel.id == after.channel.id:
            return

        if before.channel is None:
            return
        if member.bot:
            return

        guild_id = before.channel.guild.id
        msg_type = "exit"
        member_count = len(before.channel.members)
        # count non-bot memebers
        non_bot_members_count = sum([1 for m in before.channel.members if not m.bot])
        if guild_id not in self.repeaters:
            return

        if before.channel.id == self.repeaters[guild_id].voice_channel.id:
            LOG.info(f"{member.display_name} exited, {member_count} members, {non_bot_members_count} non-bot members")

        if non_bot_members_count == 0 and before.channel.id == self.repeaters[guild_id].voice_channel.id:
            LOG.info(f"{non_bot_members_count} human members left, disconnecting channel")
            await self.stop_repeater(guild_id)
        else:
            if guild_id in self.repeaters and before.channel.id == self.repeaters[guild_id].voice_channel.id:
                await self.repeaters[guild_id].append_member_enter_exit_channel(member, before.channel, msg_type)



    async def _process_member_entering(self, member, before, after):
        '''
        Append an enter message to the msg queue
        '''
        if before.channel and after.channel and before.channel.id == after.channel.id:
            return
        if after.channel is None:
            return
        if member.bot:
            return

        msg_type = "enter"
        guild_id = after.channel.guild.id

        display_name = ""
        if member.display_name:
            display_name = member.display_name
        LOG.info(f"avatar on_enter({display_name}): {member.display_avatar}")

        if guild_id in self.repeaters and after.channel.id == self.repeaters[guild_id].voice_channel.id:
            await self.repeaters[guild_id].append_member_enter_exit_channel(member, after.channel, msg_type)
        if guild_id not in self.repeaters:
            await self._start_repeater(after.channel.guild, after.channel)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel and after.channel and before.channel.id == after.channel.id:
            return
        await self._process_member_exiting(member, before, after)
        await self._process_member_entering(member, before, after)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member | User):
        if user.bot or not reaction.message.guild or reaction.message.author.bot:
            return
        guild_id = reaction.message.guild.id
        if guild_id in self.repeaters:
            await self.repeaters[guild_id].append_reaction_add(reaction, user)

    @commands.Cog.listener()
    async def on_message(self, message):
        logging.debug(f"on_message: {message.content}")
        if message.author.bot:
            # Ignore bot messages
            return
        if not message.guild:
            # Not belong to a server
            return
        guild_id = message.guild.id
        if guild_id in self.repeaters:
            await self.repeaters[guild_id].append_message(message)
