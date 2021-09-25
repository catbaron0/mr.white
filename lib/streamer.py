from typing import Dict, Optional
from discord import User, FFmpegOpusAudio, Reaction
from discord.ext import commands
import discord
# from async_timeout import timeout
import asyncio
import logging
from functools import partial
# from discord.player import FFmpegPCMAudio
import youtube_dl
from dataclasses import dataclass
import pafy
from pathlib import Path
from queue import Queue
import random

# from discord import Embed
# from discord.ext.commands import Bot, Cog
# from discord_slash import cog_ext


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
ch = logging.StreamHandler()
fh.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
ch.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(fh)
logger.addHandler(ch)

ffmpegopts = {
    'before_options': '-nostdin',
    'options': '-vn -ignore_unknown -sn'
}

ytdlopts = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'simulate': True,
    'source_address': '0.0.0.0',  # ipv6 addresses cause issues sometimes
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }]
}
ytdl = youtube_dl.YoutubeDL(ytdlopts)
pafy.set_api_key('AIzaSyCwRtNtJFfKTm_s5a8YmRTN1gpdMCiUCFg')


def info_keywords(key_words: str) -> str:
    '''
    Search key_words in Youtube and return the url.
    '''
    qs = {
        'q': key_words,
        'maxResults': 10,
        'safeSearch': "none",
        'part': 'id,snippet',
        'type': 'video',
        'videoDuration': 'any'
    }
    try:
        items = pafy.call_gdata('search', qs)['items']
    except pafy.GdataError as e:
        logger.error(f"Failed with key words: {key_words}\n{e}")
        return None
    if items:
        item = items[0]
        title = item['snippet']['title']
        video_id = item['id']['videoId']
        url = 'https://www.youtube.com/watch?v=' + video_id
        return {'web_url': url, 'title': title}


def info_url(web_url: str):
    items = list()
    try:
        res = ytdl.extract_info(web_url)
    except Exception as e:
        logger.error(f"Failed to fetch playlist url: {web_url}\n{e}")
        return None
    if 'entries' in res:
        res = res['entries']
    else:
        res = [res]
    for r in res:
        web_url = r['webpage_url']
        title = r['title']
        items.append({'web_url': web_url, 'title': title})
    return items


async def extract_stream_url(web_url: str, loop) -> Optional[str]:
    '''
    Extract the real url from the web_url.
    '''
    to_run = partial(ytdl.extract_info, url=web_url)
    try:
        res = await loop.run_in_executor(None, to_run)
        # res = await ytdl.extract_info(web_url)
    except Exception as e:
        logger.error(f"Failed to extract url: {web_url}\n{e}")
        return None
    # return {'title': res['title'], 'url': res['url']}
    return res['url']


@dataclass
class Music:
    title: str
    web_url: str
    requester: User = None
    url: str = None
    duration = None

    async def update_url(self, loop):
        self.url = await extract_stream_url(self.web_url, loop)

    def __str__(self):
        if self.requester:
            return f"Song(name={self.title}, user={self.requester.name})"
        else:
            return f"Song(name={self.title}, user=None)"

    def __repr__(self):
        if self.requester:
            return f"Song(name={self.title}, user={self.requester.name})"
        else:
            return f"Song(name={self.title}, user=None)"

    def __eq__(self, other):
        return self.web_url == other.web_url

    def __lt__(self, other):
        return self.name < other.name


class MusicPlayer:
    __slots__ = (
        'bot', '_guild', '_channel', '_cog', 'queue', 'next', 'f_music_list', 'music_list',
        'current', 'msg_np', 'volume', 'msg_pl', 'loop_list', 'loop_single',
    )

    def __init__(self, ctx, f_music_list: Path):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        # self.queue = asyncio.Queue()
        self.queue = list()
        self.next = asyncio.Event()

        self.msg_np = None
        self.msg_pl = None
        self.volume = .5
        self.current = None
        self.loop_list = False
        self.loop_single = 0

        self.f_music_list = f_music_list
        self.music_list = Queue(100)
        self.load_music_list()

        self.bot.loop.create_task(self.player_loop())

    def load_music_list(self):
        if not self.f_music_list.exists():
            return
        with open(self.f_music_list, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                title, web_url = line.strip().split('\t')
                music = Music(title=title, web_url=web_url)
                self.music_list.put(music)

    def save_music_list(self):
        with open(self.f_music_list, 'w') as f:
            for music in self.music_list.queue:
                f.write(f"{music.title}\t{music.web_url}\n")

    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()
            try:
                sleep = 0
                if not (self.loop_single > 0 and self.current):
                    while sleep < 100:
                        logger.debug("Loopging ...")
                        if self.queue:
                            logger.debug("Play music in the queue ...")
                            sleep = 0
                            music = self.queue.pop(0)
                            break
                        elif not self.music_list.empty():
                            logger.debug("Play music in the random queue ...")
                            music = random.sample(self.music_list.queue, 1)[0]
                            sleep = 0
                            break
                        else:
                            logger.debug("Nothing to play ...")
                            # await time.sleep(1)
                            await asyncio.sleep(1)
                            sleep += 1
                            continue
                    else:
                        logger.debug("Slept 100 times. Leaving ...")
                        return
                else:
                    music = self.current
                    # async with timeout(5):
                    #     # Music(requester, web_url, title)
                    #     music = await self.queue.get()
                    #     logger.debug(f"Got a song: {music}")
                    #     # await self.queue.put(music)
                    #     # self.queue.append(music)
            except asyncio.TimeoutError:
                logger.debug("I'm leaving")
                await self._channel.send("I'm leaving because there nothing to do.")
                return self.destroy(self._guild)
            # Fetch the real url
            logger.debug("Updating url...")
            try:
                await music.update_url(self.bot.loop)
            except Exception as e:
                await self._channel.send(f"There was an error processing this song. \n{music.title}.\n{e}")
            logger.debug("Updated url...")
            self.current = music
            try:
                options = '-vn -sn'
                source = FFmpegOpusAudio(
                    music.url, bitrate=256, before_options='-copyts -err_detect ignore_err', options=options
                )
            except Exception as e:
                logger.debug(e)
            logger.debug("Now playing ...")
            if self._guild.voice_client and self._guild.voice_client.is_connected:
                self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set()))
            else:
                self.msg_np = await self._channel.send("I'm not playing.")

            if not music:
                continue
            user = music.requester if music.requester else "Random"
            embed = discord.Embed(
                title="Now playing",
                description=f"[{music.title}]({music.web_url}) [{user}]",
                color=discord.Color.green()
            )

            if self._guild.voice_client and self._guild.voice_client.is_connected:
                # It may be stopped by command
                if self.msg_np:
                    await self.msg_np.delete()
                self.msg_np = await self._channel.send(embed=embed)
                # await self.msg_np.add_reaction('\N{THUMBS UP SIGN}')
                await self.msg_np.add_reaction('❤️')

            await self.next.wait()
            logger.info(f"loop_list and loop_single: {self.loop_list} and {self.loop_single}")
            if self.loop_list and self.loop_single == 0:
                self.queue.append(music)
            if self.loop_single > 0:
                self.loop_single -= 1
            source.cleanup()
            self.current = None

    def destroy(self, guild):
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Streamer(commands.Cog):
    __slots__ = ('bot', 'players')

    def __init__(self, bot, config_path):
        self.bot = bot
        self.players = {}
        self.config_path = Path(config_path)
        if not self.config_path:
            self.config_path.mkdir(parents=True, exist_ok=True)


    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass
        try:
            del self.players[guild.id]
        except KeyError:
            pass

    def get_player(self, ctx):
        try:
            logger.debug("Trying to get player")
            player = self.players[ctx.guild.id]
        except KeyError:
            logger.debug("Trying to create a player")
            f_music_list = self.config_path / f"music.{ctx.guild.id}"
            player = MusicPlayer(ctx, f_music_list)
            self.players[ctx.guild.id] = player
        return player

    async def check_vc(self, ctx) -> Dict:
        voice = ctx.message.author.voice
        if not voice:
            state = False
            info = "You need to join a VC to run this command."
            return {'state': state, 'info': info}
        vc = voice.channel
        player = self.get_player(ctx)
        p_vc = player._guild.voice_client
        if p_vc and p_vc.channel != vc:
            state = False
            info = "The bot has joined another VC!"
            return {'state': state, 'info': info}
        if not p_vc:
            await vc.connect()
        state = True
        info = "OK"
        return {'state': state, 'info': info}

    @commands.command(
        name='stop',
        aliases=['quit'],
        guild='808893235103531039',
        brief='Stop playing.'
    )
    async def cmd_stop(self, ctx, *args):
        vc = ctx.voice_client
        if vc and vc.is_connected():
            await vc.disconnect()
            del self.players[ctx.guild.id]

    @commands.command(
        name='add',
        aliases=['play', 'p'],
        guild='808893235103531039',
        brief='Add a song to the playlist through keywords or youtube url'
    )
    async def cmd_add(self, ctx, *args):
        check = await self.check_vc(ctx)
        if not check['state']:
            await ctx.message.reply(check['info'])
            return
        msg = ctx.message
        requester = ctx.message.author
        query = ' '.join(args)
        player = self.get_player(ctx)

        async with ctx.typing():
            if query.startswith('http://') or query.startswith('https://') or query.startswith('www.'):
                logger.debug("Got an url!")
                items = info_url(query)
            else:
                logger.debug("Got an keyword query!")
                items = info_keywords(query)
                if items:
                    items = [items]
            if not items:
                await msg.reply("Failed to add a song to the playlist!")
                return
            new_music = list()
            for item in items:
                music = Music(requester=requester, title=item['title'], web_url=item['web_url'])
                # await player.queue.put(music)
                if music not in player.music_list.queue:
                    player.music_list.put(music)
                    player.save_music_list()
                else:
                    logger.debug(f"It's in the list {music}")
                if music in player.queue:
                    await msg.reply(f"This music is already in the playlist: {music.title}.")
                else:
                    new_music.append(music.title)
                    player.queue.append(music)
            if len(new_music) == 1:
                await msg.reply(f"Queued a music: {new_music[0]}.")
            elif len(new_music) > 1:
                await msg.reply(f"Queued {len(new_music)} musics.")

    @commands.command(
        name='pl',
        guild='808893235103531039',
        aliases=['playlist', 'q'],
        brief="Print the playlist."
    )
    async def cmd_pl(self, ctx):
        player = self.get_player(ctx)
        playlist = player.queue
        music = player.current
        if not music:
            await ctx.message.reply("I'm not playing.")
            return
        user = music.requester if music.requester else "Random"
        desc = [f"▶️ [{music.title}]({music.web_url}) [{user}]"]
        for i, music in enumerate(playlist[:15]):
            user = music.requester if music.requester else "Random"
            desc.append(f"{i+1:<3d} [{music.title}]({music.web_url}) [{user}]")

        embed = discord.Embed(title="Playlist", description='\n'.join(desc), color=discord.Color.green())
        self.msg_pl = await ctx.channel.send(embed=embed)

    @commands.command(
        name='playing',
        guild='808893235103531039',
        aliases=['np', 'current', 'cur'],
        brief="Show the current music."
    )
    async def cmd_np(self, ctx):
        if ctx.guild.id not in self.players:
            await ctx.message.reply("I'm not playing.")
            return
        player = self.get_player(ctx)
        music = player.current
        if not music:
            await ctx.message.reply("I'm not playing.")
            return
        user = music.requester if music.requester else "Random"
        desc = f"[{music.title}]({music.web_url}) [{user}]"
        embed = discord.Embed(title="Now playing", description=desc, color=discord.Color.green())
        async with ctx.typing():
            player.msg_np = await ctx.channel.send(embed=embed)
            await player.msg_np.add_reaction('❤️')


    @commands.command(
        name='replay',
        guild='808893235103531039',
        aliases=['rp'],
        brief="Set switch to on to repeat the current music for 10 times."
    )
    async def cmd_replay(self, ctx, switch):
        check = await self.check_vc(ctx)
        if not check['state']:
            await ctx.message.reply(check['info'])
            return
        player = self.get_player(ctx)
        async with ctx.typing():
            if switch == 'on':
                player.loop_single = 10
                await ctx.message.reply("This music will be repeated 10 times.")
            elif switch == 'off':
                player.loop_single = 0
                await ctx.message.reply("Reply mode is canceled.")
            else:
                await ctx.message.reply("The switch arguments need to be on/off.")

    @commands.command(
        name='loop',
        guild='808893235103531039',
        aliases=['lp'],
        brief="Toggle the loop on the playlist. "
    )
    async def cmd_toggle_loop_list(self, ctx, switch):
        check = await self.check_vc(ctx)
        if not check['state']:
            await ctx.message.reply(check['info'])
            return
        player = self.get_player(ctx)
        async with ctx.typing():
            if switch == 'on':
                player.loop_list = True
                await ctx.message.reply("Start to loop on the playlist.")
            elif switch == 'off':
                player.loop_single = False
                await ctx.message.reply("Stop loopping on the playlist.")
            else:
                await ctx.message.reply("The switch arguments need to be on/off.")

    @commands.command(
        name='next',
        guild='808893235103531039',
        aliases=['n', 'skip'],
        brief="Play next music."
    )
    async def cmd_next(self, ctx):
        check = await self.check_vc(ctx)
        if not check['state']:
            await ctx.message.reply(check['info'])
            return
        vc = ctx.voice_client
        if not vc.is_playing():
            return
        else:
            vc.stop()

    @commands.command(
        name='pick',
        guild='808893235103531039',
        aliases=['pk'],
        brief="Pick a music."
    )
    async def cmd_pick(self, ctx, pos: int):
        check = await self.check_vc(ctx)
        if not check['state']:
            await ctx.message.reply(check['info'])
            return
        player = self.get_player(ctx)
        async with ctx.typing():
            if 0 < pos <= len(player.queue):
                music = player.queue.pop(pos - 1)
                player.queue.insert(0, player.queue.pop(pos - 1))
                await ctx.message.reply(f"One music is picked: {music.title}")
            else:
                await ctx.message.reply("Invalid pos!")

    @commands.command(
        name='remove',
        guild='808893235103531039',
        aliases=['rm'],
        brief="Remove a music from the playlist."
    )
    async def cmd_rm(self, ctx, pos: int):
        check = await self.check_vc(ctx)
        if not check['state']:
            await ctx.message.reply(check['info'])
            return
        player = self.get_player(ctx)
        async with ctx.typing():
            if pos == 0:
                player.queue = list()
                await ctx.message.reply("Playlist cleared")
                return
            if 0 < pos < len(player.queue):
                rm = player.queue.pop(pos - 1)
                embed = discord.Embed(title="Music Removied", description=f'{rm.title}')
                await ctx.message.reply(embed=embed)
            else:
                await ctx.message.reply("Invalid pos!")


    @commands.command(
        name='clear',
        guild='808893235103531039',
        aliases=['cl', 'empty'],
        brief="Remove all the musics."
    )
    async def cmd_clear(self, ctx):
        player = self.get_player(ctx)
        async with ctx.typing():
            player.queue = list()
            await ctx.message.reply("Playlist cleared")
        return
