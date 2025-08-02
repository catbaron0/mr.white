
import asyncio
from pathlib import Path

import discord
from discord import User, Member, Reaction, Message
from discord.ext import commands

from workers.repeater import Repeater
# from utils.open_ai import gpt_tts_f

AUDIO_ENTER = Path(__file__).parent.parent / "data" / "kita.mp3"
IMG_ENTER = Path(__file__).parent.parent / "data" / "kita.png"


class RepeaterManager(commands.Cog):
    def __init__(self, bot):
        self.repeaters: dict[int, Repeater]= {}
        self.stop_locks = {}  # NEW: 防止并发 stop
        self.bot = bot

    async def restart_repeater(self, guild, voice_channel, message):
        await self.stop_repeater(guild)
        await self.start_repeater(guild, voice_channel, message)

    async def start_repeater(self, guild, voice_channel, message: None | Message = None):
        reply_content = "正在启动...\n"
        reply_msg: Message | None = None
        if message:
            reply_msg = await message.reply(reply_content)
        if not voice_channel:
            if reply_msg:
                reply_content += "❌...语音频道活跃测试..."
                await reply_msg.edit(content=reply_content)
            return

        if guild.id in self.repeaters:
            # The bot is working
            if reply_msg:
                reply_content += f"❌...复读模块繁忙: {voice_channel.name}"
                await reply_msg.edit(content=reply_content)
            return

        else:
            if reply_msg:
                reply_content += "✅...语音频道活跃测试...\n"
                await reply_msg.edit(content=reply_content)
            await voice_channel.connect()
            self.repeaters[guild.id] = Repeater(guild, voice_channel)
            if reply_msg:
                reply_content += f"✅...复读模块就位: {voice_channel.name}"
                await reply_msg.edit(content=reply_content)
            await self.repeaters[guild.id].play_audio(AUDIO_ENTER, cleanup=False)
            await self.repeaters[guild.id].voice_channel.send(file=discord.File(IMG_ENTER))

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

    async def stop_repeater(self, guild):
        await self._stop_repeat(guild.id)

    async def update_config(self, ctx):
        guild_id = ctx.guild.id
        print("更新配置文件")
        try:
            self.repeaters[guild_id].load_config()
            await ctx.message.reply("✅...配置文件已更新")
        except Exception as e:
            await ctx.message.reply(f"❌...配置文件更新失败: {e}")

    async def mute(self, ctx, args):
        guild_id = ctx.guild.id
        user_id = str(ctx.message.author.id)
        if len(args) > 1:
            user_id = str(args[1])
        try:
            self.repeaters[guild_id].muted_users.add(user_id)
            await ctx.message.reply("✅...用户已静音")
            print(self.repeaters[guild_id].muted_users)
        except Exception as e:
            await ctx.message.reply("❌...静音失败")
            print("DEBUG mute error:", e)

    async def unmute(self, ctx, args):
        guild_id = ctx.guild.id
        user_id = str(ctx.message.author.id)
        if len(args) > 1:
            user_id = str(args[1])
        try:
            if user_id == "all":
                self.repeaters[guild_id].muted_users = {}
            else:
                self.repeaters[guild_id].muted_users.remove(user_id)
            print(self.repeaters[guild_id].muted_users)
            await ctx.message.reply("✅...用户已取消静音")
        except Exception as e:
            await ctx.message.reply("❌...取消静音失败")
            print("DEBUG unmute error:", e)

    async def run(self, ctx, *args):
        print("DEBUG: CTX.message", ctx.message)
        if args and args[0] == "start":
            await self.start_repeater(ctx.guild, ctx.author.voice.channel, ctx.message)
        if args and args[0] == "stop":
            await self.stop_repeater(ctx.guild)
        if args and args[0] == "restart":
            await self.restart_repeater(ctx.guild, ctx.author.voice.channel, ctx.message)
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

        # 检查机器人自己是否被移出语音频道
        if member.id == self.bot.user.id:
            guild_id = None
            if before.channel:
                guild_id = before.channel.guild.id
            elif after.channel:
                guild_id = after.channel.guild.id
            else:
                guild_id = None
            if guild_id in self.repeaters:
                repeater = self.repeaters[guild_id]
                # 如果after.channel为None，说明bot被移出频道
                if before.channel and after.channel is None:
                    print("DEBUG bot was removed from voice channel, try to reconnect")
                    try:
                        await before.channel.connect()
                        repeater.vc = before.channel.guild.voice_client
                        print("DEBUG bot reconnected to voice channel")
                    except Exception as e:
                        print(f"DEBUG failed to reconnect bot: {e}")
            return

        if before.channel and after.channel and before.channel.id == after.channel.id:
            return

        if before.channel is not None:
            # 用户离开语音频道
            guild_id = before.channel.guild.id
            msg_type = "exit"
            if guild_id in self.repeaters and before.channel.id == self.repeaters[guild_id].voice_channel.id:
                member_count = len(before.channel.members)
                print(f"DEBUG member exit, {member_count} members left")
                # 过滤掉机器人，只统计人类成员
            non_bot_members = [m for m in before.channel.members if not m.bot]
            if len(non_bot_members) == 0:
                # 频道中已经没有人类用户了
                print("DEBUG no human members left, disconnecting channel")
                await self._stop_repeat(guild_id)
            else:
                if guild_id in self.repeaters and before.channel.id == self.repeaters[guild_id].voice_channel.id:
                    await self.repeaters[guild_id].append_member_enter_exit_channel(member, before.channel, msg_type)

        if after.channel is not None:
            # 用户加入语音频道
            msg_type = "enter"
            guild_id = after.channel.guild.id
            print("DEBUG avatar on_enter:", member.display_avatar)
            if guild_id in self.repeaters and after.channel.id == self.repeaters[guild_id].voice_channel.id:
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