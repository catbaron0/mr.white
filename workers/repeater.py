import asyncio

from discord import FFmpegOpusAudio
from discord.ext import commands

from utils.tts import tts_f
from utils.text_processing import process_content, process_user_name


class Repeater:
    def __init__(self, guild, channel):
        self.message_queue = asyncio.Queue()
        self.channel = channel
        self.guild = guild
        self.vc = guild.voice_client
        asyncio.create_task(self.read_messages())

    async def read_messages(self):
        while True:
            msg = await self.message_queue.get()
            user_name = process_user_name(msg.author.display_name)
            content = process_content(msg.content.strip())
            if content:
                if len(content) > 50: 
                    text = f"{user_name}说了很多东西你们自己看吧"
                else:
                    text = f"{user_name}说, {content}"
                print(text)

                audio_f = tts_f(text)
                options = '-vn -acodec libopus'
                source = FFmpegOpusAudio(audio_f, bitrate=256, before_options="", options=options)
                self.vc.play(source)

    async def append_message(self, message):
        if message.channel.id == self.channel.id:
            await self.message_queue.put(message)


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
            await ctx.message.reply("❌ 语音频道活跃测试...")
            return

        if guild.id in self.repeaters:
            # The bot is working
            await ctx.message.reply(f"❌ 复读机模块繁忙: {channel.name}")

        else:
            await channel.connect()
            self.repeaters[guild.id] = Repeater(ctx.guild, channel)
            await ctx.message.reply(
                "✅ 语音频道活跃测试...\n"
                f"✅ 复读机模块就位: {channel.name}"
            )

    async def stop_repeat(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.repeaters:
            vc = self.repeaters[guild_id].vc
            if vc and vc.is_connected():
                await vc.disconnect()
            del self.repeaters[guild_id]

    async def run(self, ctx, *args):
        if args and args[0] == "start":
            await self.start_repeat(ctx)
        if args and args[0] == "stop":
            await self.stop_repeat(ctx)

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
            await self.repeaters[message.guild.id].append_message(message)
