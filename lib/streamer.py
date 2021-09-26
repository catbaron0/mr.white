from typing import Dict
from discord import User, FFmpegOpusAudio
from discord.ext import commands
import discord
from async_timeout import timeout
import asyncio
import logging
from functools import partial
# from discord.player import FFmpegPCMAudio
import youtube_dl
from dataclasses import dataclass
import pafy
from pathlib import Path
import random
from collections import deque


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


async def info_url(web_url: str, loop):
    items = list()
    to_run = partial(ytdl.extract_info, url=web_url, download=False)
    try:
        logger.debug("Extract web url!")
        # res = ytdl.extract_info(web_url)
        res = await loop.run_in_executor(None, to_run)
        logger.debug("Extracted web url!")
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


# async def extract_info(web_url: str, loop) -> Optional[str]:
#     '''
#     Extract the real url from the web_url.
#     '''
#     to_run = partial(ytdl.extract_info, url=web_url, download=False)
#     try:
#         res = await loop.run_in_executor(None, to_run)
#     except Exception as e:
#         logger.error(f"Failed to extract url: {web_url}\n{e}")
#         return None
#     return res['url']


@dataclass
class Music:
    title: str
    web_url: str
    requester: User = None
    url: str = None
    duration = None

    async def update_info(self, loop):
        to_run = partial(ytdl.extract_info, url=self.web_url, download=False)
        try:
            res = await loop.run_in_executor(None, to_run)
        except Exception as e:
            logger.error(f"Failed to update info of url: {self.web_url}\n{e}")
        self.url = res['url']
        self.duration = res['duration']

    @property
    def duration_str(self):
        if self.duration:
            m = self.duration // 60
            s = self.duration % 60
            return f"{m:02d}:{s:02d}"
        else:
            return "Unknown"

    def __str__(self):
        if self.requester:
            return f"Music(name={self.title}, user={self.requester.name})"
        else:
            return f"Music(name={self.title}, user=None)"

    def __repr__(self):
        if self.requester:
            return f"Music(name={self.title}, user={self.requester.name})"
        else:
            return f"Music(name={self.title}, user=None)"

    def __eq__(self, other):
        return self.web_url == other.web_url

    def __lt__(self, other):
        return self.name < other.name


class MusicPlayer:
    __slots__ = (
        'bot', '_guild', '_channel', '_cog', 'queue', 'next', 'f_random_list', 'random_list',
        'current', 'msg_np', 'volume', 'msg_pl', 'loop_list', 'loop_single',
    )

    def __init__(self, ctx, f_random_list: Path):
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

        self.f_random_list = f_random_list
        self.random_list = self.load_list_from_file(self.f_random_list)
        logger.debug(f"Len(random_list): {len(self.random_list)}")

        self.bot.loop.create_task(self.player_loop())

    def load_list_from_file(self, fn):
        if not self.f_random_list.exists():
            logger.debug("File does not exist!")
            return
        logger.debug(f"Loading from {self.f_random_list}")
        ml = deque(maxlen=100)
        with open(self.f_random_list, 'r') as f:
            for line in f:
                # logger.debug("Test empty lines")
                if not line.strip():
                    continue
                # logger.debug("Obtain title and web_url")
                title, web_url = line.strip().split('\t')
                # logger.debug(f"Music(title={title}, web_url={web_url})")
                music = Music(title=title, web_url=web_url)
                # logger.debug("Put music.")
                ml.append(music)
        logger.debug(f"The music list is updated!: {len(ml)}")
        return ml

    def save_random_list(self):
        with open(self.f_random_list, 'w') as f:
            for music in self.random_list:
                f.write(f"{music.title}\t{music.web_url}\n")

    async def get_music(self):
        '''
        Try to get a musisc from self.playlist.
        If self.playlist is empty, try self.random_list instead.
        Sleep 1 second if failed to get any music.
        '''
        while True:
            if self.loop_single > 0 and self.current:
                # For single loop
                return self.current
            if self.queue:
                music = self.queue.pop(0)
                logger.debug(f"Get a music from the queue: {music} ...")
                return music
            elif self.random_list:
                music = random.sample(self.random_list, 1)[0]
                logger.debug(f"Get a music from the random queue: {music}...")
                return music

            logger.debug(f"Len(random_list): {len(self.random_list)}")
            logger.debug("Nothing to play ...")
            await asyncio.sleep(1)


    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()
            # Get a music
            try:
                async with timeout(10):
                    music = await self.get_music()
            except asyncio.TimeoutError:
                logger.debug("I'm leaving")
                title = "Warning"
                desc = "I'm leaving because there nothing to do."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await self._channel.send(embed=embed)
                return self.destroy(self._guild)

            # Fetch the real url
            logger.debug("Updating url...")
            try:
                await music.update_info(self.bot.loop)
            except Exception as e:
                title = "Error"
                desc = f"There was an error reading this source url. \n{music.title}.\n{e}"
                embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
                await self._channel.send(embed=embed)
                # Read next music
                continue
            logger.debug("Updated url...")

            # Generate the source to play
            try:
                options = '-vn -sn'
                source = FFmpegOpusAudio(
                    music.url, bitrate=256, before_options='-copyts -err_detect ignore_err', options=options
                )
            except Exception as e:
                logger.debug(f"Failed to generate FFmpegOpusAUdio:{e}")
                continue

            # Print the musci to play
            logger.debug(f"Now playing {music}...")
            user = music.requester if music.requester else "Random"
            embed = discord.Embed(
                title="Now playing",
                description=f"[({music.duration_str}) {music.title}]({music.web_url}) [{user}]",
                color=discord.Color.green()
            )
            self.msg_np = await self._channel.send(embed=embed)
            await self.msg_np.add_reaction('❤️')
            self.current = music

            # Play the music
            if self.loop_single > 0:
                self.loop_single -= 1
            try:
                if music.duration:
                    time = 10 + music.duration
                else:
                    time = 300
                async with timeout(time):
                    if self._guild.voice_client and self._guild.voice_client.is_connected:
                        self._guild.voice_client.play(
                            source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set())
                        )
                    else:
                        # In case of -next command but the vc is disconnected.
                        title = "Error"
                        desc = "I'm not playing."
                        embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
                        self.msg_np = await self._channel.send(embed=embed)
                    await self.next.wait()
                    source.cleanup()
            except asyncio.TimeoutError:
                logger.debug(f"Failed to play the music:{music}")
                embed = discord.Embed(
                        title="Error",
                        description="Failed to play: Timeout. Skip to next music.",
                        color=discord.Color.red()
                )
                await self._channel.send(embed=embed)
                continue

            if self.loop_list and self.loop_single == 0:
                self.queue.append(music)

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
            logger.debug("Got a player")
        except KeyError:
            logger.debug("Trying to create a player")
            f_random_list = self.config_path / f"music.{ctx.guild.id}"
            player = MusicPlayer(ctx, f_random_list)
            self.players[ctx.guild.id] = player
            logger.debug("Created a player")
        return player

    async def check_vc(self, ctx) -> Dict:
        guild_id = ctx.guild.id
        if str(guild_id) != '808893235103531039':
            logger.debug(f"guild id {guild_id}")
            state = False
            info = "You need to play streamer commands in Catbaron's Server."
            return {'state': state, 'info': info}

        voice = ctx.message.author.voice
        if not voice:
            state = False
            info = "You need to join a VC to run this command."
            return {'state': state, 'info': info}
        vc = voice.channel
        logger.debug("Get player for cmd_check")
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
            embed = discord.Embed(
                    title="Error",
                    description="Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        requester = ctx.message.author
        query = ' '.join(args)
        if not query.strip():
            title = "Error"
            desc = "Keywords or Youtube URL is expected!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            logger.debug("Keywords or Youtube URL is expected!")
            return
        logger.debug("Get player for cmd_add")
        player = self.get_player(ctx)

        if query.startswith('http://') or query.startswith('https://') or query.startswith('www.'):
            logger.debug("Got an url!")
            items = await  info_url(query, ctx.bot.loop)
        else:
            logger.debug("Got an keyword query!")
            items = info_keywords(query)
            if items:
                items = [items]
        if not items:
            title = "Error"
            desc = "Failed to add a song to the playlist!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return
        new_music = list()
        for item in items:
            music = Music(requester=requester, title=item['title'], web_url=item['web_url'])
            # await player.queue.put(music)
            if music not in player.random_list:
                _music = Music(requester=None, title=item['title'], web_url=item['web_url'])
                player.random_list.append(_music)
                player.save_random_list()
            else:
                logger.debug(f"It's in the list {music}")
            if music in player.queue:
                title = "Warning"
                desc =  "This music is already in the playlist: {music.title}."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await ctx.message.reply(embed=embed)
            else:
                new_music.append(music.title)
                player.queue.append(music)
        if len(new_music) == 1:
            logger.debug(f"Queued a music: {new_music[0]}.")
            title = "Well done!"
            desc = f"Queued a music: {new_music[0]}."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        elif len(new_music) > 1:
            logger.debug(f"Queued {len(new_music)} musics.")
            title = "Well done!"
            desc = f"Queued {len(new_music)} musics."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)

    @commands.command(
        name='rl',
        aliases=['reload'],
        brief="Reload random playlist."
    )
    async def cmd_rl(self, ctx):
        i = 0
        for player in self.players.values():
            player.random_list = player.load_list_from_file(player.f_random_list)
            i += 1
        title = "Well done!"
        desc = f"{i} player reloaded."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await ctx.message.reply(embed=embed)

    @commands.command(
        name='pl',
        guild='808893235103531039',
        aliases=['playlist', 'q'],
        brief="Print the playlist."
    )
    async def cmd_pl(self, ctx):
        logger.debug("Get player for cmd_pl")
        player = self.get_player(ctx)
        playlist = player.queue
        music = player.current
        if not music:
            title = "Error"
            desc = "Failed to run command: I'm not playing."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return
        user = music.requester if music.requester else "Random"
        desc = [f"▶️ [({music.duration_str}) {music.title}]({music.web_url}) [{user}]\n------"]
        for i, music in enumerate(playlist[:15]):
            user = music.requester if music.requester else "Random"
            desc.append(f"{i+1:<3d} [({music.duration_str}) {music.title}]({music.web_url}) [{user}]")

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
            title = "Error"
            desc = "Failed to run command: I'm not playing."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_np")
        player = self.get_player(ctx)
        music = player.current
        if not music:
            title = "Error"
            desc = "Failed to run command: I'm not playing."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return
        user = music.requester if music.requester else "Random"
        desc = f"[({music.duration_str}) {music.title}]({music.web_url}) [{user}]"
        embed = discord.Embed(title="Now playing", description=desc, color=discord.Color.green())
        player.msg_np = await ctx.channel.send(embed=embed)
        await player.msg_np.add_reaction('❤️')


    @commands.command(
        name='replay',
        guild='808893235103531039',
        aliases=['rp'],
        brief="Set switch to on to repeat the current music for 10 times."
    )
    async def cmd_replay(self, ctx, times: int):
        check = await self.check_vc(ctx)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description="Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_replay")
        player = self.get_player(ctx)
        if times >= 10:
            player.loop_single = 10
            title = "Well done!"
            desc = "This music will be repeated 10 times."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        elif times > 0:
            player.loop_single = times
            title = "Well done!"
            desc = f"This music will be repeated {times} times."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        else:
            title = "Well done"
            desc = "Reply mode is canceled."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)

    @commands.command(
        name='loop',
        guild='808893235103531039',
        aliases=['lp'],
        brief="Toggle the loop on the playlist. "
    )
    async def cmd_toggle_loop_list(self, ctx, switch):
        check = await self.check_vc(ctx)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description="Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_loop")
        player = self.get_player(ctx)
        if switch == 'on':
            player.loop_list = True
            title = "Well done!"
            desc = "Start to loop on the playlist."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        elif switch == 'off':
            player.loop_single = False
            title = "Well done!"
            desc = "Stop loopping on the playlist."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        else:
            title = "Error"
            desc = "The switch arguments need to be on/off."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)

    @commands.command(
        name='next',
        guild='808893235103531039',
        aliases=['n', 'skip'],
        brief="Play next music."
    )
    async def cmd_next(self, ctx):
        check = await self.check_vc(ctx)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description="Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
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
            embed = discord.Embed(
                    title="Error",
                    description="Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_pick")
        player = self.get_player(ctx)
        if 0 < pos <= len(player.queue):
            music = player.queue.pop(pos - 1)
            player.queue.insert(0, player.queue.pop(pos - 1))
            title = "Well done!"
            desc = f"One music is picked: {music.title}"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green()
            )
            await ctx.message.reply(embed=embed)
        else:
            title = "Error"
            desc = "Failed to run command !Invalid pos!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)

    @commands.command(
        name='remove',
        guild='808893235103531039',
        aliases=['rm'],
        brief="Remove a music from the playlist."
    )
    async def cmd_rm(self, ctx, pos: int):
        check = await self.check_vc(ctx)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description="Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_rm")
        player = self.get_player(ctx)

        if pos == 0:
            player.queue = list()
            title = "Well done!"
            desc = "Playlist cleared."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
            return
        if 0 < pos < len(player.queue):
            rm = player.queue.pop(pos - 1)
            title = "Well done!"
            desc = f"Music removied: {rm.title}."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        else:
            title = "Error"
            desc = "Failed to run command! Invalid pos!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)


    @commands.command(
        name='clear',
        guild='808893235103531039',
        aliases=['cl', 'empty'],
        brief="Remove all the musics."
    )
    async def cmd_clear(self, ctx):
        check = await self.check_vc(ctx)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_clear")
        player = self.get_player(ctx)
        player.queue = list()
        title = "Well done!"
        desc = "Playlist cleared."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await ctx.message.reply(embed=embed)
        return
