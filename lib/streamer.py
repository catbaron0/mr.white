'''
@author catbaron
@date 2021/9/25
This module is designed as a streamer to play youtube-music to a voice channel at Discord.
The source is extracted by youtube-dl, and the key-word based search is done by pafy.
'''
from functools import wraps
import html

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
# from collections import deque


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
    'cookiefile': 'youtube.com_cookies.txt',
    'noplaylist': False,
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
sign_pause = "⏸️"
sign_like = '❤️ 🧡 💛 💚 💙 💜 🤎 🖤 🤍 💟 ❣️ 💕 💞 💗 💘 💝 🥰'
sign_dislike = '💔'
sign_no = '❌'

signs_np = (sign_like[0], sign_play, sign_pause,  sign_next, sign_single_loop, sign_no)

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
        video_id = item['id']['videoId']
        url = 'https://www.youtube.com/watch?v=' + video_id
        duration = pafy.new(url).length
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
    if not res:
        logger.error(f"Failed to fetch playlist url: {web_url}")
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
    likes: list = None
    progress: int = 0

    def is_skipable(self, user):
        if user == self.requester:
            return True
        if self.likes and len(self.likes) == 1 and self.likes[0] == user:
            return True
        if not self.likes or len(self.likes) == 0:
            return True
        return False

    @property
    def protectors(self):
        protectors = list()
        if self.requester:
            protectors.append(self.requester)
        if self.likes:
            protectors += self.likes
        return protectors

    async def update_info(self, loop):
        # The real url may be expired, so we need to update it before we play the music.
        to_run = partial(ytdl.extract_info, url=self.web_url, download=False)
        try:
            for i in range(10):
                res = await loop.run_in_executor(None, to_run)
                if res:
                    self.url = res['url']
                    # The duration can be None if we load the music from a file,
                    # so we update it here as well.
                    self.duration = res['duration']
                    logger.debug(f"Got res for {self}")
                    return
                asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to update info of url: {self.web_url}\n{e}")

    @property
    def progress_bar(self) -> str:
        if not self.duration:
            return
        bar_len = 12
        bar = ['━'] * bar_len
        # bar = ['━'] * bar_len
        # bar = '"●━━━━━━─────── 5:20"'
        progress = round(self.progress / self.duration * bar_len)
        # bar[: progress] = [''] * progress
        if progress >= bar_len:
            progress = bar_len - 1
        bar[progress] = '●'
        return ''.join(bar)

    def get_desc(self, playing: bool) -> str:
        # Genenrate str to display as the content of  Discord message.
        user = "@" + self.requester.name if self.requester else "Random"
        head = ""
        if self.loop > 1:
            head = f"{sign_single_loop}(x{self.loop}) " + head
        if playing:
            head = sign_play + " " + head
        desc =  f"[{head}({self.duration_str}) {self.title}]({self.web_url}) [{user}]"
        # bar = self.progress_bar
        # if bar and playing:
        #     desc += "\n---------------------------------------- \n"
        #     desc += bar + f"  {self.progress_str} \n"
        #     desc += "---------------------------------------- \n"
        return desc

    @property
    def progress_str(self):
        if self.duration:
            m = self.progress // 60
            s = self.progress % 60
            return f"{m:02d}:{s:02d}"
        else:
            return "Unknown"

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
        if not maxlen:
            maxlen = float('inf')
        self.maxlen = maxlen
        # self.dq = deque(maxlen=maxlen)
        self.dq = list()
        self.fn = fn
        if fn:
            self.load()

    def put(self, music, left=False):
        if left and len(self) > 0:
            self.dq.insert(1, music)
            if len(self.dq) >= self.maxlen:
                self.dq.pop()
        else:
            self.dq.append(music)
            if len(self.dq) >= self.maxlen:
                self.dq.pop(0)
        self.save()

    def get(self):
        return self.dq.pop(0)

    def remove(self, music):
        logger.debug(f"Before removal! {len(self)}")
        for i in range(len(self.dq)):
            if self.dq[i] == music:
                self.dq.pop(i)
                break
        logger.debug(f"After removal! {len(self)}")
        self.save()

    def pop(self, i = 0):
        # music = self.dq[i]
        # self.remove(music)
        # return music
        return self.dq.pop(i)

    def sample(self):
        return random.sample(self.dq, 1)[0]

    def save(self):
        if not self.fn:
            return
        with open(self.fn, 'w') as f:
            for music in self.dq:
                if music:
                    f.write(f"{music.title}\t{music.web_url}\t{music.duration}\n")
        logger.debug(f"List saved to {self.fn}")

    def clear(self):
        self.dq = list()

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
                try:
                    title, web_url, duration = line.strip().split('\t')
                except Exception:
                    title, web_url = line.strip().split('\t')
                    duration = 'None'
                if duration == "None":
                    duration = None
                else:
                    duration = int(duration)
                music = Music(title=title, web_url=web_url, duration=duration)
                self.dq.append(music)
        logger.debug(f"The music list is updated!: {len(self.dq)}")

    def __len__(self):
        return len(self.dq)

    def __getitem__(self, idx):
        return self.dq[idx]


class MusicPlayer:
    __slots__ = (
        'bot', 'guild', 'channel', 'cog', 'playlist', 'next_event', 'f_randomlist',
        'randomlist', 'marathon', 'current', 'msg_np', 'volume', 'msg_likes',
        'msg_pl', 'loop', 'config_path', 'vc', 'is_exit', 'vc', 'undead'
    )

    def __init__(self, ctx, config_path: Path, start=True):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.config_path = config_path
        self.cog = ctx.cog
        self.undead = True
        self.marathon = 0

        self.next_event = asyncio.Event()

        # The last message showing the playing music / playlist
        self.msg_np = None
        self.msg_pl = None
        self.msg_likes = None
        self.volume = .5
        # Current  music being played
        self.current = None
        # Loop the playlist
        self.loop = False

        f_randomlist = self.config_path / f"random.{ctx.guild.id}"
        self.randomlist = MusicList(maxlen=500, fn=f_randomlist)
        f_play_list = self.config_path / f"play.{ctx.guild.id}"
        self.playlist = MusicList(fn=f_play_list)
        logger.debug(f"Len(randomlist): {len(self.randomlist)}")
        self.is_exit = None

        if start:
            logger.debug("I'm starting")
            self.start()

    def pause(self):
        vc = self.guild.voice_client
        if not vc or not vc.is_connected() or not vc.is_playing():
            return False
        if vc.is_paused():
            return False
        vc.pause()
        return True

    def resume(self):
        vc = self.guild.voice_client
        if not vc or not vc.is_connected():
            logger.debug("vc is not connect")
            return False
        if not vc.is_paused():
            logger.debug("vc is not paused")
            return False
        vc.resume()
        return True


    def start(self):
        # Run the main loop.
        if self.is_exit is None:
            self.bot.loop.create_task(self.player_loop())
            self.is_exit = False

    def is_empty(self):
        vc = self.guild.voice_client.channel
        n_mem = len(vc.voice_states)
        print(vc.members)
        return n_mem == 1

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

        self.playlist.put(self.current, left=True)
        self.is_exit = True
        await self.next()
        vc = self.guild.voice_client
        if vc and vc.is_connected():
            await vc.disconnect()
        self.destroy(self.guild)

    async def del_music(self, pos: int):
        music = self.playlist[pos]
        logger.debug("Del from randomlist")
        self.randomlist.remove(music)
        if pos > 0:
            logger.debug("Del from playlist")
            self.playlist.remove(music)
        else:
            # Remove player.current by runing `next` command
            # As long as the player.loop is false,
            # current music will be dropped after being played.
            loop = self.loop
            self.loop = False
            self.current.loop = 0
            await self.next()
            self.loop = loop
        return music


    async def get_music(self):
        # Try to get a musisc from playlist or random list..
        # Retry after sleeping for 1 second if failed on both the two lists.
        while True:
            if self.current and  self.current.loop > 1:
                # For single loop
                return self.current
            if self.playlist:
                music = self.playlist[0]
                logger.debug(f"Get a music from the playlist: {music} ...")
                self.playlist.save()
                return music
            elif self.undead and self.randomlist:
                music = self.randomlist.sample()
                self.playlist.put(music)
                music = self.playlist[0]
                logger.debug(f"Get a music from the random list: {music}...")
                return music

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
                desc = "I'm leaving because there is nothing to do."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await self.channel.send(embed=embed)
                self.playlist.pop(0)
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
                self.playlist.pop(0)
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
                self.playlist.pop(0)
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
            self.msg_likes = None
            self.current = music


            # Play the music
            try:
                if music.duration:
                    overtime = 10 + music.duration
                else:
                    overtime = 300
                async with timeout(overtime):
                    if self.guild.voice_client and self.guild.voice_client.is_playing():
                        self.guild.voice_client.stop()
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
                    else:
                        self.playlist.pop(0)
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
                self.playlist.pop(0)
                continue

            if self.loop and self.current.loop == 1:
                self.current.requester = None
                self.current.likes = list()
                self.playlist.put(self.current)

            if self.is_empty():
                logger.debug("I'm leaving")
                title = "Warning"
                desc = "I'm leaving because there is nobody here."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await self.channel.send(embed=embed)
                break
            if self.is_exit:
                break
        await self.stop()

    def destroy(self, guild):
        return self.bot.loop.create_task(self.cog.cleanup(guild))


class Streamer(commands.Cog, name="Player"):
    '''
    暂时开放其他服务起使用观察一下对我自己网络的影响。
    其他服务器随时会变成不可用状态。
    '''
    __slots__ = ('bot', 'players', 'qualified_name', 'description')

    def __init__(self, bot, config_path):
        self.qualified_name = "Player"
        self.description = "暂时开放其他服务起使用观察一下对我自己网络的影响。\n"
        self.description += "其他服务器随时会变成不可用状态。"
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

    def check_requester(func):
        @wraps(func)
        async def wrapper(self, ctx, *args):
            start = False
            player = self.get_player(ctx, start)
            if not ctx.author.id != 'catbaron#8242':
                title = "Warning"
                info = "This command is limited to @catbaron"
                color = discord.ui.Color.orange()
                embed = discord.Embed(title=title, description=info, color=color)
                await ctx.message.reply(embed=embed)
                return
            else:
                player.start()
                return await func(self, ctx, *args)
        return wrapper

    def check_cmd(func):
        @wraps(func)
        async def wrapper(self, ctx, *args):
            start = False
            player = self.get_player(ctx, start)
            if await self.check_vc(ctx.message):
                player.start()
                ret = await func(self, ctx, *args)
                player.channel = ctx.channel
                return ret
            else:
                return
        return wrapper

    async def check_user(self, user, player):
        voice = user.voice
        vc = voice.channel if voice else None
        p_vc = player.guild.voice_client

        # The user need to join in a voice channel
        if not voice or not player:
            success = False
            info = "You need to join a VC to run this command."
            success = False
            return {"success": success, "info": info}

        # The user should be in the same channel as the bot.
        if p_vc and p_vc.channel != vc:
            success = False
            info = "The bot has joined another VC!"
        # The user should be in the same channel as the bot.
        elif p_vc and p_vc.channel != vc:
            success = False
            info = "The bot has joined another VC!"
        else:
            if not p_vc:
                await vc.connect()
            success = True
            info = "OK"
        return {"success": success, "info": info}


    async def check_vc(self, message, reply=True) -> bool:
        # Check if the user has the permission to run a command
        guild_id = message.guild.id
        user = message.author
        player = self.players.get(guild_id, None)
        res = await self.check_user(user, player)
        if not res['success']:
            if reply:
                embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {res['info']}",
                    color=discord.Color.red()
                )
                await message.reply(embed=embed)
            return False
        return res['success']

    @commands.command(name='stop', aliases=['quit'], usage="-stop", brief='Stop the player.')
    @check_cmd
    async def cmd_stop(self, ctx, *args):
        player = self.get_player(ctx)
        await player.stop()
        del self.players[ctx.guild.id]

    @commands.command(name='start', aliases=['s'], usage="-s", brief='Start the player.')
    @check_cmd
    async def cmd_start(self, ctx):
        embed = discord.Embed(
            title="Warning",
            description="Okay okay, I AM working! Just stop calling me!",
            color=discord.Color.green()
        )
        await ctx.message.reply(embed=embed)
        self.get_player(ctx).start()

    @commands.command(
        name='del',
        usage="-del 2",
        brief='Delete a song (remove from playlist and delete from random list)',
    )
    @check_cmd
    async def cmd_del(self, ctx, pos: int = 0):
        logger.debug(f"cmd_del command from: {ctx.author.id}")
        logger.debug(f"cmd_del command from: {ctx.author}")
        logger.debug(f"guild.owner: {ctx.guild.owner}")
        if ctx.author != ctx.guild.owner and str(ctx.author.id) != "299779237760598017":
            embed = discord.Embed(
                title="Error",
                description="This command is limited to the owner of this Server.",
                color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return

        player = self.get_player(ctx)
        if pos >= len(player.playlist):
            embed = discord.Embed(
                title="Error",
                description = f"Failed to run command ! `pos` should be `0 <= pos <= {len(player.playlist) - 1}`",
                color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)

        try:
            music = await player.del_music(pos)
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
        title = "Processing"
        desc = ""
        color = discord.Color.blue()
        embed = discord.Embed(title=title, description=desc, color=color)
        reply = await ctx.message.reply(embed=embed)

        if query.startswith('http://') or query.startswith('https://') or query.startswith('www.'):
            logger.debug("Got an url!")

            title = "Processing"
            desc = "An URL is submitted. I'm extracting information from it...."
            color = discord.Color.blue()
            embed = discord.Embed(title=title, description=desc, color=color)
            await reply.edit(embed=embed)
            if "music.youtube.com" in query and "playlist" in query:
                query = query.replace("music.youtube.com", "www.youtube.com")
                logger.debug(f"Updted the query to :{query}")
            try:
                async with timeout(10):
                    items = await info_url(query, ctx.bot.loop)
            except asyncio.TimeoutError:
                title = "Error"
                desc = "Failed to extract info from this url: Time out"
                embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
                await reply.edit(embed=embed)
                return
        else:
            logger.debug(f"Got an keyword query: {query}")

            title = "Processing"
            desc = f"I'm searching music for the key words `{query}`"
            color = discord.Color.blue()
            embed = discord.Embed(title=title, description=desc, color=color)
            await reply.edit(embed=embed)

            item = info_keywords(html.escape(query.replace("’", "'")))
            if item:
                items = [item]
        if not items:
            # Failed to find any source
            title = "Error"
            desc = "Failed to add a song to the playlist!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await reply.edit(embed=embed)
            return

        # Generate musci and add it to lists.
        new_music = list()
        for item in items:
            music = Music(
                    requester=requester, title=item['title'],
                    web_url=item['web_url'], duration=item['duration']
            )
            if music in player.randomlist:
                logger.debug(f"It's in the list {music}")
            else:
                _music = Music(requester=None, title=item['title'], web_url=item['web_url'])
                if _music not in player.randomlist:
                    player.randomlist.put(_music)
            if music in player.playlist:
                title = "Warning"
                desc =  f"This music is already in the playlist: *{music.title}*."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await reply.edit(embed=embed)
            else:
                new_music.append(music.title)
                player.playlist.put(music)

        # Display the resutls of appending
        if len(new_music) == 1:
            logger.debug(f"Queued a music: {new_music[0]}.")
            title = "Well done!"
            desc = f"Queued a music: {new_music[0]}."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await reply.edit(embed=embed)
        elif len(new_music) > 1:
            logger.debug(f"Queued {len(new_music)} musics.")
            title = "Well done!"
            desc = f"Queued {len(new_music)} musics."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await reply.edit(embed=embed)
        # if not player.current.requester:
        #     await player.next()

    # @commands.command(
    #         name='marathon', aliases=['mth'], usage="-mth <num> (num<50)",
    #         brief="The player will not stop until it plays enough music."
    # )
    # @check_cmd
    # async def cmd_marathon(self, ctx, num: int):
    #     player = self.get_player()
    #     if num > 50:
    #         num = 50
    #     if num > 0:
    #         num = 0
    #     player.marathon = num
    #     title = "Well done!"
    #     desc = f"The player will play {num} music before it stops."
    #     embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
    #     await ctx.message.reply(embed=embed)


    @commands.command(name='pause', usage="-pause", brief="Pause.")
    @check_cmd
    async def cmd_pause(self, ctx):
        player = self.get_player(ctx)
        if player.pause():
            title = "Well done!"
            desc = f"I'm paused!"
            color = discord.Color.green()
        else:
            title = "Error"
            desc = f"You can't pause me for now!"
            color = discord.Color.red()
        embed = discord.Embed(title=title, description=desc, color=color)
        await ctx.message.reply(embed=embed)

    @commands.command(name='resume', usage="-resume", brief="Resume.")
    @check_cmd
    async def cmd_resume(self, ctx):
        player = self.get_player(ctx)
        if player.resume():
            title = "Well done!"
            desc = f"I'm resumed!"
            color = discord.Color.green()
        else:
            title = "Error"
            desc = f"You can't resume me for now!"
            color = discord.Color.red()
        embed = discord.Embed(title=title, description=desc, color=color)
        await ctx.message.reply(embed=embed)

    @commands.command(name='reload', aliases=['rl'], usage="-rl", brief="Reload random playlist.")
    @check_cmd
    async def cmd_reload(self, ctx):
        player = self.get_player(ctx)
        player.randomlist.load()
        title = "Well done!"
        desc = f"{len(player.randomlist)} music loaed to random playlist."
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
            playlist = player.randomlist
        music = player.current
        desc = list()
        if music:
            # await self.cmd_np(ctx)
            desc.append(music.get_desc(playing=True))
        if len(playlist) >= 1:
            len_pl = min(len(playlist), 20)
            for i, music in enumerate(playlist[1: 21]):
                desc_i = music.get_desc(playing=False)
                desc.append(f"{i+1:<3d} {desc_i}")
        title = f"Playlist ({len_pl}/{len(playlist)})"
        if player.loop:
            title = sign_list_loop + " " + title
        embed = discord.Embed(title=title, description='\n'.join(desc), color=discord.Color.green())
        player.msg_pl = await ctx.channel.send(embed=embed)
        #TODO: add reactions

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
        aliases=['np', 'cur', 'playing', 'now'],
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
        player.msg_likes = None


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
        logger.debug(f"cmd: {ctx.command.name}")
        player = self.get_player(ctx)
        music = player.current
        if not music:
            player.start()
            return
        if not music.is_skipable(ctx.author):
            protectors = list()
            protectors = ["@" + u.name for u in music.protectors]
            logger.debug(f"Protectors: {protectors}")
            title = "Warning"
            desc = "This music is pretected by someone: \n > "
            desc += ', '.join(protectors) + '\n'
            desc += '\n Try `-n!` if you insist to skip this music.'
            color = discord.Color.orange()
            embed = discord.Embed(title=title, description=desc, color=color)
            await ctx.message.reply(embed=embed)
            return
        await self.cmd_next_f(ctx)

    @commands.command(
        name='next!',
        aliases=['n!', 'skip!'],
        usage="-n!",
        brief="Force to play next music."
    )
    @check_cmd
    async def cmd_next_f(self, ctx):
        logger.debug(f"cmd: {ctx.command.name}")
        player = self.get_player(ctx)
        music = player.current
        if not music:
            player.start()
        else:
            await player.next()
            return

    @commands.command(
        name='random',
        aliases=['rd'],
        brief="Randomly pick a musci from randomlist."
    )
    @check_cmd
    async def cmd_random(self, ctx):
        player = self.get_player(ctx)
        player.playlist
        if player.randomlist:
            music = player.randomlist.sample()
            music.requester = ctx.author
            player.playlist.put(music)
            logger.debug(f"Get a music from the random list: {music}...")
            title = "Well done!"
            desc = f"Queued a music: {music.title}"
            color = discord.Color.green()
        else:
            title = "Error"
            desc = "Your random list is empty!"
            color = discord.Color.red()
        embed = discord.Embed(title=title, description=desc, color=color)
        await ctx.message.reply(embed=embed)

    @commands.command(
        name='update-random',
        aliases=['ur'],
        brief="Update duration of music in  random list."
    )
    @check_cmd
    @check_requester
    async def cmd_ur(self, ctx):
        player = self.get_player(ctx)
        randomlist = player.randomlist
        updated = 0
        for music in randomlist:
            if not music.duration:
                updated += 1
                logger.info(f"Updating {music}")
                await asyncio.sleep(2)
                await music.update_info(ctx.bot.loop)
                randomlist.save()
        title = "Well done!"
        desc = f"{updated} music is upated."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await ctx.message.reply(embed=embed)


    @commands.command(
        name='keep',
        aliases=['kp'],
        brief="Keep this player alive. Limited to catbaron."
    )
    @check_cmd
    @check_requester
    async def cmd_keep(self, ctx):
        player = self.get_player(ctx)
        player.undead = True
        title = "Well done!"
        desc = "Okay. I'm undead now."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await ctx.message.reply(embed=embed)

    @commands.command(
        name='pick',
        aliases=['pk'],
        brief="Pick a music to the top of playlist."
    )
    @check_cmd
    async def cmd_pick(self, ctx, pos: int):
        player = self.get_player(ctx)
        if 0 <  pos < len(player.playlist):
            music = player.playlist.pop(pos)
            player.playlist.put(music, left=True)
            title = "Well done!"
            desc = f"One music is picked: *{music.title}*"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        else:
            title = "Error"
            desc = f"Failed to run command ! `pos` should be `0 < pos <= {len(player.playlist) - 1}`"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)

    @commands.command(
        name='remove!',
        aliases=['rm!'],
        usage="-rm! 4",
        brief="Force to remove a music from the playlist."
    )
    @check_cmd
    async def cmd_rm_f(self, ctx, pos: int):
        player = self.get_player(ctx)
        if pos == 0:
            return await self.cmd_next_f(ctx)
        if not 0 < pos < len(player.playlist):
            title = "Error"
            desc = f"Failed to run command ! `pos` should be `0 <= pos <= {len(player.playlist) - 1}`"
            color = discord.Color.red()
            embed = discord.Embed(title=title, description=desc, color=color)
            await ctx.message.reply(embed=embed)
            return

        music = player.playlist.pop(pos)
        title = "Well done!"
        desc = f"Music removied: {music.title}."
        color = discord.Color.green()
        embed = discord.Embed(title=title, description=desc, color=color)
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
        if pos == 0:
            return await self.cmd_next(ctx)
        if not 0 < pos < len(player.playlist):
            title = "Error"
            desc = f"Failed to run command ! `pos` should be `0 <= pos <= {len(player.playlist) - 1}`",
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return

        music = player.playlist[pos]
        if music.is_skipable(ctx.author):
            await self.cmd_rm_f(ctx, pos)
        else:
            protectors = ["@" + u.name for u in music.protectors]
            logger.debug(f"Protectors: {protectors}")
            title = "Warning"
            desc = "This music is pretected by someone: \n > "
            desc += ', '.join(protectors)
            desc += '\n Try `-rm!` if you insist to remove this music.'
            color = discord.Color.orange()
            embed = discord.Embed(title=title, description=desc, color=color)
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
        res = await self.check_user(user, player)
        if not res['success']:
            return

        if user == msg.author:
            logger.debug("The reaction is sent by me!")
            return
        if msg != player.msg_np:
            logger.debug("Not the np_msg!")
            return
        if reaction.emoji in sign_like:
            title = "YEAH!"
            if player.current.likes is None:
                player.current.likes = list()
            if user not in player.current.likes:
                player.current.likes.append(user)
            users = ["@" + u.name for u in player.current.likes if u != msg.author]
            desc = f"{user.mention} loves this music!"
            if len(users) > 1:
                # besides mr.white and you
                desc += "  Those people all love this music: \n\n > "
                desc += ", ".join(users)
            embed = discord.Embed(title=title, description=desc, color=discord.Color.purple())
            if not player.msg_likes:
                player.msg_likes = await msg.channel.send(embed=embed)
            else:
                await player.msg_likes.edit(embed=embed)
        if reaction.emoji == sign_next:
            if player.current.is_skipable(user):
                await player.next()
            else:
                protectors = ["@" + u.name for u in player.current.protectors]
                title = "Warning"
                desc = "This music is pretected by someone: \n > "
                desc += ', '.join(protectors)
                desc += '\n Try `-n!` if you insist to remove this music.'
                color = discord.Color.orange()
                embed = discord.Embed(title=title, description=desc, color=color)
                await msg.channel.send(embed=embed)
        if reaction.emoji == sign_no:
            if user != msg.guild.owner and str(user.id) != "299779237760598017":
                embed = discord.Embed(
                    title="Error",
                    description="This command is limited to the owner of this Server.",
                    color=discord.Color.red()
                )
                await msg.channel.send(embed=embed)
            else:
                await player.del_music(0)

        if reaction.emoji == sign_dislike:
            music = player.current
            # Remove it from randomlist
            player.randomlist.remove(music)
            # Remove player.current
            loop = player.loop
            player.loop = False
            player.current.loop = 0
            await player.next()
            player.loop = loop
        if reaction.emoji == sign_single_loop:
            player.current.loop = 10
        if reaction.emoji == sign_play:
            player.resume()
        if reaction.emoji == sign_pause:
            player.pause()

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
