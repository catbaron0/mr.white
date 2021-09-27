'''
@author catbaron
@date 2021/9/25
This module is designed as a streamer to play youtube-music to a voice channel at Discord.
The source is extracted by youtube-dl, and the key-word based search is done by pafy.
'''
# TODO : Test cmd_add
from functools import wraps

from typing import Dict, Optional, List
from discord import User, FFmpegOpusAudio
from discord.ext import commands
import discord
from async_timeout import timeout
import asyncio
import logging
from functools import partial
import youtube_dl
from dataclasses import dataclass
import pafy
from pathlib import Path
import random
from collections import deque


# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
ch = logging.StreamHandler()
fh.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
ch.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(fh)
logger.addHandler(ch)

# Set up logger
ffmpegopts = {
    'before_options': '-nostdin',
    'options': '-vn -ignore_unknown -sn'
}

# Set up youtube-dl and pafy
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
key_2 = 'AIzaSyCwRtNtJFfKTm_'
key_1 = 's5a8YmRTN1gpdMCiUCFg'
pafy.set_api_key(key_2 + key_1)


# Global variables of reactions
sign_single_loop = "🔂"
sign_list_loop= "🔄"
sign_next = "⏭"
sign_play = "▶️"
sign_like = '❤️ 🧡 💛 💚 💙 💜 🤎 🖤 🤍 💟 ❣️ 💕 💞 💗 💘 💝 🥰'
sign_dislike = '💔'
sign_no = '❌'

# signs_np = (sign_like[0], sign_dislike, sign_next, sign_single_loop)
signs_np = (sign_like[0], sign_next, sign_single_loop)

def info_keywords(key_words: str) -> Dict[str, str]:
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
        duration = item['snippet']['duration']
        video_id = item['id']['videoId']
        url = 'https://www.youtube.com/watch?v=' + video_id
        return {'web_url': url, 'title': title, 'duration': duration}


async def info_url(web_url: str, loop) -> List[Dict[str, str]]:
    '''
    Take a youtube url and extract basic inforamtion.
    Different to info_keywords(), the input web_url may be a playlist.
    Hence this function return a list of items, with each item being
    a dict('web_url':str, 'title': str).
    '''
    items = list()
    to_run = partial(ytdl.extract_info, url=web_url, download=False)
    try:
        logger.debug("Extract web url!")
        res = await loop.run_in_executor(None, to_run)
    except Exception as e:
        logger.error(f"Failed to fetch playlist url: {web_url}\n{e}")
        return None
    if 'entries' in res:
        # res get the key of 'entries' if it's a playlist
        res = res['entries']
    else:
        res = [res]
    for r in res:
        web_url = r['webpage_url']
        title = r['title']
        duration = r['duration']
        items.append({'web_url': web_url, 'title': title, 'duration': duration})
    return items


# A class for music
@dataclass
class Music:
    title: str
    web_url: str
    requester: User = None
    url: str = None
    duration: int = None
    loop: int = 1
    volume: float = 0.3

    async def update_info(self, loop):
        # The real url may be expired, so we need to update it before we play the music.
        to_run = partial(ytdl.extract_info, url=self.web_url, download=False)
        try:
            res = await loop.run_in_executor(None, to_run)
        except Exception as e:
            logger.error(f"Failed to update info of url: {self.web_url}\n{e}")
        self.url = res['url']
        # The duration can be None if we load the music from a file, so we update it here as well.
        self.duration = res['duration']

    def get_desc(self, playing: bool) -> str:
        # Genenrate str to display as the content of  Discord message.
        user = self.requester if self.requester else "Random"
        head = ""
        if self.loop > 1:
            head = f"{sign_single_loop}(x{self.loop}) " + head
        if playing:
            head = sign_play + " " + head
        return f"[{head}({self.duration_str}) {self.title}]({self.web_url}) [{user}]"


    @property
    def duration_str(self) -> Optional[int]:
        if self.duration:
            m = self.duration // 60
            s = self.duration % 60
            return f"{m:02d}:{s:02d}"
        else:
            return "Unknown"

    def __str__(self):
        if self.requester:
            return f"Music(name={self.title}, user={self.requester.name}, loop={self.loop})"
        else:
            return f"Music(name={self.title}, user=Random, loop={self.loop})"

    def __repr__(self):
        if self.requester:
            return f"Music(name={self.title}, user={self.requester.name}, loop={self.loop})"
        else:
            return f"Music(name={self.title}, user=Random, loop={self.loop})"

    def __eq__(self, other):
        return self.web_url == other.web_url

    def __lt__(self, other):
        return self.name < other.name


# Manage the musics with a MusicList class
# Currently the playlist and random list is saved to file.
# It will be initialized by loading from a file.
# Whenever the music list is changed (put/get), the content will be saved to a file.
# TODO: to manage the playlist with DB
class MusicList:
    def __init__(self, maxlen: int = None, fn: Path = None):
        self.dq = deque(maxlen=maxlen)
        self.fn = fn
        if fn:
            self.load()

    def put(self, music):
        self.dq.append(music)
        self.save()

    def get(self):
        return self.dq.popleft()

    def remove(self, music):
        logger.debug(f"Before removal! {len(self)}")
        self.dq.remove(music)
        logger.debug(f"After removal! {len(self)}")
        self.save()

    def pop(self, i):
        music = self.dq[i]
        self.remove(music)
        return music

    def sample(self):
        return random.sample(self.dq, 1)[0]

    def save(self):
        if not self.fn:
            return
        with open(self.fn, 'w') as f:
            for music in self.dq:
                f.write(f"{music.title}\t{music.web_url}\n")
        logger.debug(f"List saved to {self.fn}")

    def clear(self):
        self.dq.clear()

    def load(self):
        fn = self.fn
        if not fn.exists():
            fn.touch()
            return
        logger.debug(f"Loading from {self.fn}")
        self.dq.clear()
        with open(fn, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                title, web_url = line.strip().split('\t')
                music = Music(title=title, web_url=web_url)
                self.dq.append(music)
        logger.debug(f"The music list is updated!: {len(self.dq)}")

    def __len__(self):
        return len(self.dq)

    def __getitem__(self, idx):
        return list(self.dq)[idx]


class MusicPlayer:
    __slots__ = (
        'bot', 'guild', 'channel', 'cog', 'playlist', 'next_event', 'f_random_list', 'random_list',
        'current', 'msg_np', 'volume', 'msg_pl', 'loop', 'config_path', 'vc', 'is_exit', 'vc'
    )

    def __init__(self, ctx, config_path: Path, start=True):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.config_path = config_path
        self.cog = ctx.cog

        self.next_event = asyncio.Event()

        # The last message showing the playing music / playlist
        self.msg_np = None
        self.msg_pl = None
        self.volume = .5
        # Current  music being played
        self.current = None
        # Loop the playlist
        self.loop = False

        f_random_list = self.config_path / f"random.{ctx.guild.id}"
        self.random_list = MusicList(maxlen=500, fn=f_random_list)
        f_play_list = self.config_path / f"play.{ctx.guild.id}"
        self.playlist = MusicList(fn=f_play_list)
        logger.debug(f"Len(random_list): {len(self.random_list)}")
        self.is_exit = None

        if start:
            logger.debug("I'm starting")
            self.start()

    def start(self):
        # Run the main loop.
        if self.is_exit is None:
            self.bot.loop.create_task(self.player_loop())
            self.is_exit = False

    async def next(self):
        # To play next music, just stop current voice_client,
        # and the main player_loop to take over then.
        logger.info("player.next")
        vc = self.guild.voice_client
        if not vc.is_playing():
            logger.debug("vs not playing")
            return
        else:
            logger.debug("stop vs")
            vc.stop()

    async def stop(self):
        # Stop the player.
        self.is_exit = True
        await self.next()
        vc = self.guild.voice_client
        if vc and vc.is_connected():
            await vc.disconnect()


    async def get_music(self):
        # Try to get a musisc from playlist or random list..
        # Retry after sleeping for 1 second if failed on both the two lists.
        while True:
            if self.current and  self.current.loop > 1:
                # For single loop
                return self.current
            if self.playlist:
                music = self.playlist.get()
                logger.debug(f"Get a music from the playlist: {music} ...")
                self.playlist.save()
                return music
            elif self.random_list:
                music = self.random_list.sample()
                logger.debug(f"Get a music from the random list: {music}...")
                return music

            logger.debug(f"Len(random_list): {len(self.random_list)}")
            logger.debug("Nothing to play ...")
            await asyncio.sleep(1)


    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next_event.clear()
            # Get a music
            # Send a message to Discord if timeout
            try:
                async with timeout(10):
                    music = await self.get_music()
            except asyncio.TimeoutError:
                logger.debug("I'm leaving")
                title = "Warning"
                desc = "I'm leaving because there nothing to do."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await self.channel.send(embed=embed)
                return self.destroy(self.guild)

            # Fetch the real url
            logger.debug("Updating url...")
            try:
                async with timeout(10):
                    await music.update_info(self.bot.loop)
            except Exception as e:
                title = "Error"
                desc = f"There was an error reading this source url. \n*{music.title}*.\n{e}"
                embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
                await self.channel.send(embed=embed)
                # Read next music if failed to extact information for this music
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

            # Display the musci to play
            logger.debug(f"Now playing {music}...")
            embed = discord.Embed(
                title="Now playing",
                description=music.get_desc(True),
                color=discord.Color.green()
            )
            self.msg_np = await self.channel.send(embed=embed)
            for sign in signs_np:
                await self.msg_np.add_reaction(sign)
            self.current = music


            # Play the music
            try:
                if music.duration:
                    time = 10 + music.duration
                else:
                    time = 300
                async with timeout(time):
                    if self.guild.voice_client and self.guild.voice_client.is_connected:
                        self.guild.voice_client.play(
                            source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next_event.set())
                        )
                    else:
                        # In case of -next command but the vc is disconnected.
                        title = "Error"
                        desc = "I'm not connected to a voice client."
                        embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
                        self.msg_np = await self.channel.send(embed=embed)

                    # The event loop will wait here until the music is finished.
                    await self.next_event.wait()
                    if self.current and self.current.loop > 1:
                        self.current.loop -= 1
                    source.cleanup()
            except asyncio.TimeoutError:
                # It cost too much time to play the music
                # There maybe something wrong happened to the ffmpeg client.
                logger.debug(f"Failed to play the music:{music}")
                embed = discord.Embed(
                        title="Error",
                        description="Failed to play: Timeout. Skip to next music.",
                        color=discord.Color.red()
                )
                await self.channel.send(embed=embed)
                continue

            if self.loop and self.current.loop == 1:
                self.playlist.put(music)
            if self.is_exit:
                break

    def destroy(self, guild):
        return self.bot.loop.create_task(self.cog.cleanup(guild))


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

    def get_player(self, ctx, start = True):
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            # Generate a player if it does not exist
            logger.debug(f"Trying to create a player, start={start}")
            player = MusicPlayer(ctx, self.config_path, start=start)
            self.players[ctx.guild.id] = player
            logger.debug("Created a player")
        return player

    def check_cmd(func):
        @wraps(func)
        async def wrapper(self, ctx, *args):
            start = False
            player = self.get_player(ctx, start)
            if await self.check_vc(ctx.message):
                player.start()
                return await func(self, ctx, *args)
            else:
                return
        return wrapper

    async def check_vc(self, message, reply=True) -> bool:
        # Check if the user has the permission to run a command

        # Currently this bot can only be run at my own server
        # for the sake of performance.
        guild_id = message.guild.id

        voice = message.author.voice
        vc = None
        if voice:
            vc = voice.channel

        player = self.players.get(guild_id, None)
        p_vc = player.guild.voice_client

        if str(guild_id) != '808893235103531039':
            logger.debug(f"guild id {guild_id}")
            success = False
            info = "You need to play streamer commands in Catbaron's Server."

        # The user need to join in a voice channel
        elif not voice:
            success = False
            info = "You need to join a VC to run this command."

        # We need a player to react to commands.
        elif not player:
            success = False
            info = "I'm not playing."

        # The user should be in the same channel as the bot.
        elif p_vc and p_vc.channel != vc:
            success = False
            info = "The bot has joined another VC!"
        else:
            if not p_vc:
                await vc.connect()
            success = True
            info = "OK"
        if not success:
            if reply:
                embed = discord.Embed(
                        title="Error",
                        description=f"Failed to run command: {info}",
                        color=discord.Color.red()
                )
                await message.reply(embed=embed)
            return False

        return success

    @commands.command(name='stop', aliases=['quit'], usage="-stop", brief='Stop the player.')
    @check_cmd
    async def cmd_stop(self, ctx, *args):
        player = self.get_player(ctx)
        await player.stop()
        del self.players[ctx.guild.id]

    @commands.command(name='start', aliases=['s'], usage="-s", brief='Start the player.')
    @check_cmd
    async def cmd_start(self, ctx):
        # if not await self.check_vc(ctx.message):
        #     return
        # else:
        #     self.get_player(ctx).start()
        self.get_player(ctx).start()

    @commands.command(
        name='del',
        usage="-del 2",
        brief='Delete a song (remove from playlist and delete from random list)',
    )
    @check_cmd
    async def cmd_del(self, ctx, pos: int = 0):
        player = self.get_player(ctx)
        if pos > len(player.playlist):
            embed = discord.Embed(
                title="Error",
                description="Failed to run command: Invalid argument: `pos`!",
                color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)

        try:
            if pos == 0:
                music = player.current
                # Remove it from random_list
                player.random_list.remove(music)

                # Remove player.current by runing `next` command
                # As long as the player.loop is false,
                # current music will be dropped after being played.
                loop = player.loop
                player.loop = False
                player.current.loop = 0
                logger.debug("Next()")
                await player.next()
                player.loop = loop
            else:
                music = player.playlist[pos - 1]
                player.random_list.remove(music)
                player.playlist.remove(music)
            embed = discord.Embed(
                title="Well done!",
                description=f"The music is deleted: *{music.title}*",
                color=discord.Color.green()
            )
        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"Failed to run command: {e}",
                color=discord.Color.red()
            )
        await ctx.message.reply(embed=embed)


    @commands.command(
        name='add',
        aliases=['play', 'p'],
        usage=['-add 周杰伦 双节棍'],
        brief='Add a song to the playlist through keywords or youtube url'
    )
    @check_cmd
    async def cmd_add(self, ctx, *args):
        player = self.get_player(ctx)
        requester = ctx.message.author
        query = ' '.join(args)
        if not query.strip():
            title = "Error"
            desc = "Keywords or Youtube URL is expected!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            logger.debug("Keywords or Youtube URL is expected!")
            return

        if query.startswith('http://') or query.startswith('https://') or query.startswith('www.'):
            logger.debug("Got an url!")
            items = await info_url(query, ctx.bot.loop)
        else:
            logger.debug("Got an keyword query!")
            item = info_keywords(query)
            if item:
                items = [item]
        if not items:
            # Failed to find any source
            title = "Error"
            desc = "Failed to add a song to the playlist!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return

        # Generate musci and add it to lists.
        new_music = list()
        for item in items:
            music = Music(
                    requester=requester, title=item['title'],
                    web_url=item['web_url'], duration=item['duration']
            )
            if music in player.random_list:
                logger.debug(f"It's in the list {music}")
            else:
                # TODO: to test
                # _music = Music(requester=None, title=item['title'], web_url=item['web_url'])
                player.random_list.put(music)
            if music in player.playlist:
                title = "Warning"
                desc =  "This music is already in the playlist: *{music.title}*."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await ctx.message.reply(embed=embed)
            else:
                new_music.append(music.title)
                player.playlist.put(music)

        # Display the resutls of appending
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
        if not player.current.requester:
            await player.next()

    @commands.command(name='reload', aliases=['rl'], usage="-rl", brief="Reload random playlist.")
    @check_cmd
    async def cmd_reload(self, ctx):
        player = self.get_player(ctx)
        player.random_list.load()
        title = "Well done!"
        desc = f"{len(player.random_list)} music loaed to random playlist."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await ctx.message.reply(embed=embed)

    @commands.command(
            name='playlist', aliases=['pl', 'q'],
            usage="-pl [random|playlist]", brief="Show the playlist."
    )
    async def cmd_pl(self, ctx, pl: str = None):
        player = self.get_player(ctx)
        if not pl or pl == 'playlist':
            playlist = player.playlist
        elif pl == 'random':
            playlist = player.random_list
        music = player.current
        if music:
            desc = [music.get_desc(playing=True)]
        else:
            desc = list()
        if playlist:
            len_pl = min(len(playlist), 15)
            desc.append(f"=========== {len_pl}/{len(playlist)} ===========")
            for i, music in enumerate(playlist[:15]):
                desc_i = music.get_desc(playing=False)
                desc.append(f"{i+1:<3d} {desc_i}")
        title = "Playlist"
        if player.loop:
            title = sign_list_loop + " " + title
        embed = discord.Embed(title=title, description='\n'.join(desc), color=discord.Color.green())
        player.msg_np = await ctx.channel.send(embed=embed)

    @commands.command(
        name='restart',
        aliases=['rs'],
        usage="-rs",
        brief="Restart the player. Plaeas use it when the player is freezing."
    )
    @check_cmd
    async def cmd_restart(self, ctx):
        await self.cmd_stop(ctx)
        await asyncio.sleep(1)
        await self.cmd_start(ctx)

    @commands.command(
        name='current',
        aliases=['np', 'cur', 'playing'],
        usage="-np",
        brief="Show the current music."
    )
    async def cmd_np(self, ctx):
        player = self.get_player(ctx)
        music = player.current
        if not music:
            title = "Error"
            desc = "Failed to run command: I'm not playing."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return
        desc = music.get_desc(playing=True)
        embed = discord.Embed(title="Now playing", description=desc, color=discord.Color.green())
        player.msg_np = await ctx.channel.send(embed=embed)
        for sign in signs_np:
            await player.msg_np.add_reaction(sign)


    @commands.command(
        name='repeat',
        aliases=['rp', 'replay'],
        usage="-rp",
        brief="repeat the current music for up to 10 times."
    )
    @check_cmd
    async def cmd_repeat(self, ctx, times: int):
        player = self.get_player(ctx)
        if not player.current:
            title = "Error"
            desc = "Failed to run command: I'm not playing!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
        if times > 10:
            player.current.loop = 10
            title = "Well done!"
            desc = "This music will be played for 10 times."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        elif times >= 1:
            player.current.loop = times
            title = "Well done!"
            desc = f"This music will be played for {times} times."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        else:
            title = "Well done"
            desc = "Reply mode is canceled."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)

    @commands.command(
        name='loop',
        aliases=['lp'],
        usage="-loop on/off",
        brief="Set the switch of loop on the playlist."
    )
    @check_cmd
    async def cmd_toggle_loop_list(self, ctx, switch):
        player = self.get_player(ctx)
        if switch == 'on':
            player.loop = True
            title = "Well done!"
            desc = "Start to loop on the playlist."
            color = discord.Color.green()
        elif switch == 'off':
            player.current.loop = False
            title = "Well done!"
            desc = "Stop loopping on the playlist."
            color = discord.Color.green()
        else:
            title = "Error"
            desc = "The switch arguments need to be on/off."
            color = discord.Color.red()
        embed = discord.Embed(title=title, description=desc, color=color)
        await ctx.message.reply(embed=embed)

    @commands.command(
        name='next',
        aliases=['n', 'skip'],
        usage="-n",
        brief="Play next music."
    )
    @check_cmd
    async def cmd_next(self, ctx):
        await self.get_player(ctx).next()

    @commands.command(
        name='pick',
        aliases=['pk'],
        brief="Pick a music to the top of playlist."
    )
    @check_cmd
    async def cmd_pick(self, ctx, pos: int):
        player = self.get_player(ctx)
        if 0 < pos <= len(player.playlist):
            music = player.playlist.pop(pos - 1)
            player.playlist.put(music)
            title = "Well done!"
            desc = f"One music is picked: *{music.title}*"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        else:
            title = "Error"
            desc = "Failed to run command !Invalid argument: pos!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)

    @commands.command(
            name='remove',
            aliases=['rm'],
            usage="-rm 4",
            brief="Remove a music from the playlist."
    )
    @check_cmd
    async def cmd_rm(self, ctx, pos: int):
        player = self.get_player(ctx)
        if 0 < pos <= len(player.playlist):
            rm = player.playlist.pop(pos - 1)
            title = "Well done!"
            desc = f"Music removied: {rm.title}."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        else:
            title = "Error"
            desc = "Failed to run command! Invalid argument: `pos`!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
        await ctx.message.reply(embed=embed)

    @commands.command(name='clear', aliases=['cl', 'empty'], usage="-cl", brief="Remove all the musics.")
    @check_cmd
    async def cmd_clear(self, ctx):
        player = self.get_player(ctx)

        player.playlist.clear()

        title = "Well done!"
        desc = "The playlist is cleared."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await ctx.message.reply(embed=embed)
        return

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        msg = reaction.message
        player = self.players[msg.guild.id]
        logger.debug(f'A reaction is added: {reaction}')
        if not  await self.check_vc(reaction.message, reply=False):
            return
        if user == msg.author:
            logger.debug("The reaction is sent by me!")
            return
        if msg != player.msg_np:
            logger.debug("Not the np_msg!")
            return
        if reaction.emoji in sign_like:
            title = "YEAH!"
            users = await reaction.users().flatten()
            users = ["@" + u.name for u in users if u != msg.author and u != user]
            desc = f"{user.mention} loves this music!"
            if len(users) > 0:
                # besides mr.white and you
                desc += "  Those people all love this music!: \n\n > "
                desc += ", ".join(users)
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await reaction.message.channel.send(embed=embed)
        if reaction.emoji == sign_next:
            await player.next()
        if reaction.emoji == sign_dislike:
            music = player.current
            # Remove it from random_list
            player.random_list.remove(music)
            # Remove player.current
            loop = player.loop
            player.loop = False
            player.current.loop = 0
            await player.next()
            player.loop = loop
        if reaction.emoji == sign_single_loop:
            player.current.loop = 10

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        msg = reaction.message
        player = self.players[msg.guild.id]
        logger.debug(f'A reaction is added: {reaction}')
        if not self.check_vc(reaction.message, reply=False):
            return
        if user == msg.author:
            logger.debug("The reaction is sent by me!")
            return
        if msg != player.msg_np:
            logger.debug("Not the np_msg!")
            return
        if reaction.emoji == sign_single_loop:
            player.current.loop = 0
