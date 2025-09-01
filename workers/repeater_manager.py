
import asyncio
from pathlib import Path
import logging

import discord
from discord import User, Member, Reaction, Message, VoiceRegion
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
        self.bot = bot

    async def restart_repeater(self, guild, voice_channel, message):
        await self.stop_repeater(guild)
        await self.start_repeater(guild, voice_channel, message)

    async def start_repeater(self, guild, voice_channel, message: None | Message = None):
        reply_content = "正在启动..."
        reply_msg: Message | None = None
        if message:
            reply_msg = await message.reply(reply_content)
        if not voice_channel:
            if reply_msg:
                reply_content = reply_msg.content + "\n❌...语音频道活跃测试，用户需要加入语音频道"
                reply_msg = await reply_msg.edit(content=reply_content)
            return

        LOG.info(f"guild.id: {guild.id}")
        if guild.id in self.repeaters and guild.voice_client and guild.voice_client.is_connected():
            # The bot is working
            if reply_msg:
                reply_content = reply_msg.content + f"\n❌...复读模块繁忙: {voice_channel.name}"
                reply_msg = await reply_msg.edit(content=reply_content)
            return

        if reply_msg:
            reply_content = reply_msg.content + "\n✅...语音频道活跃测试..."
            reply_msg = await reply_msg.edit(content=reply_content)
            reply_content = reply_msg.content + "\n✅...连接语音节点..."
            reply_msg = await reply_msg.edit(content=reply_content)

        try:
            vc, reply_msg = await connect_voice_channel(voice_channel, reply_msg)
            if not vc:
                vc, reply_msg = await connect_voice_channel(voice_channel, reply_msg, VoiceRegion.hongkong)
        except Exception as e:
            if reply_msg:
                reply_content = reply_msg.content + "\n❌...语音频道连接失败"
                reply_msg = await reply_msg.edit(content=reply_content)
            LOG.error(f"Voice channel connection error: {e}")
            return

        if vc is None or not vc.is_connected():
            if reply_msg:
                reply_content = reply_msg.content + "\n❌...语音频道连接失败"
                reply_msg = await reply_msg.edit(content=reply_content)
            LOG.error("Voice channel connection failed")
            return

        self.repeaters[guild.id] = Repeater(guild, voice_channel, vc)
        if reply_msg:
            reply_content = reply_msg.content + f"\n✅...复读模块就位: {voice_channel.name}"
            reply_msg = await reply_msg.edit(content=reply_content)

        await self.repeaters[guild.id].play_audio(AUDIO_ENTER, cleanup=False)
        await self.repeaters[guild.id].voice_channel.send(file=discord.File(IMG_ENTER))

    async def _stop_repeater(self, guild_id):
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

    async def stop_repeater(self, guild):
        await self._stop_repeater(guild.id)

    async def update_config(self, ctx):
        guild_id = ctx.guild.id
        LOG.info("更新配置文件")
        try:
            self.repeaters[guild_id].load_config()
            await ctx.message.reply("✅...配置文件已更新")
        except Exception as e:
            LOG.error(f"❌...配置文件更新失败: {e}")
            await ctx.message.reply(f"❌...配置文件更新失败: {e}")

    async def mute(self, ctx, args):
        guild_id = ctx.guild.id
        user_id = str(ctx.message.author.id)
        if len(args) > 1:
            user_id = str(args[1])
        try:
            self.repeaters[guild_id].muted_users.add(user_id)
            await ctx.message.reply("✅...用户已静音")
        except Exception as e:
            await ctx.message.reply("❌...静音失败")
            LOG.error(f"Mute error: {e}")

    async def unmute(self, ctx, args):
        guild_id = ctx.guild.id
        user_id = str(ctx.message.author.id)
        if len(args) > 1:
            user_id = str(args[1])
        try:
            if user_id == "all":
                self.repeaters[guild_id].muted_users.clear()
            else:
                self.repeaters[guild_id].muted_users.remove(user_id)
            await ctx.message.reply("✅...用户已取消静音")
        except Exception as e:
            await ctx.message.reply("❌...取消静音失败")
            LOG.error(f"DEBUG unmute error: {e}")

    async def run(self, ctx, *args):
        LOG.debug(f"CTX.message: {ctx.message}")
        if ctx.author.voice:
            voice_channel = ctx.author.voice.channel
        else:
            voice_channel = None
        if args and args[0] == "start":
            await self.start_repeater(ctx.guild, voice_channel, ctx.message)
        if args and args[0] == "stop":
            await self.stop_repeater(ctx.guild)
        if args and args[0] == "restart":
            await self.restart_repeater(ctx.guild, voice_channel, ctx.message)
        if args and args[0] == "cfg":
            await self.update_config(ctx)
        if args and args[0] == "mute":
            await self.mute(ctx, args)
        if args and args[0] == "unmute":
            await self.unmute(ctx, args)

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

    async def _update_bot_voice_state(self, member, before, after):
        '''
        If the bot is removed from the voice channel by accident,
        reconnect it to the channel
        '''
        # The member is a bot
        if member.id != self.bot.user.id:
            return

        # get possible guild_id
        guild_id = None
        if before.channel:
            guild_id = before.channel.guild.id
        elif after.channel:
            guild_id = after.channel.guild.id
        else:
            return
        if guild_id not in self.repeaters:
            return

        repeater = self.repeaters[guild_id]
        # the bot was removed from the channel if after.channel is None
        if before.channel and after.channel is None and not repeater.is_exiting:
            LOG.info("Bot was removed from voice channel, try to reconnect")
            try:
                await before.channel.connect()
                repeater.vc = before.channel.guild.voice_client
                LOG.info("Bot reconnected to voice channel")
            except Exception as e:
                LOG.error(f"Failed to reconnect bot: {e}")
        return

    async def _process_member_exiting(self, member, before, after):
        '''
        Append an exit message to the msg queue
        Automatically quit the bot if no human member is left.
        '''
        if before.channel and after.channel and before.channel.id == after.channel.id:
            return

        if before.channel is None:
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
            await self._stop_repeater(guild_id)
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

        msg_type = "enter"
        guild_id = after.channel.guild.id

        display_name = ""
        if member.display_name:
            display_name = member.display_name
        LOG.info(f"avatar on_enter({display_name}): {member.display_avatar}")

        if guild_id in self.repeaters and after.channel.id == self.repeaters[guild_id].voice_channel.id:
            await self.repeaters[guild_id].append_member_enter_exit_channel(member, after.channel, msg_type)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        await self._update_bot_voice_state(member, before, after)

        if before.channel and after.channel and before.channel.id == after.channel.id:
            return
        await self._process_member_exiting(member, before, after)
        await self._process_member_entering(member, before, after)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member | User):
        if user.bot or not reaction.message.guild:
            return
        guild_id = reaction.message.guild.id
        if guild_id in self.repeaters:
            await self.repeaters[guild_id].append_reaction_add(reaction, user)
