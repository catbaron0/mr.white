from typing import Dict, Optional
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

sign_single_loop = "🔂"
sign_list_loop= "🔄"
sign_next = "⏭"
sign_play = "▶️"
sign_like = '❤️ 🧡 💛 💚 💙 💜 🤎 🖤 🤍 💟 ❣️ 💕 💞 💗 💘 💝 🥰'
sign_dislike = '💔'
sign_no = '❌'

# signs_np = (sign_like[0], sign_dislike, sign_next, sign_single_loop)
signs_np = (sign_like[0], sign_next, sign_single_loop)

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
    loop: int = 1
    volume: float = 0.3

    async def update_info(self, loop):
        to_run = partial(ytdl.extract_info, url=self.web_url, download=False)
        try:
            res = await loop.run_in_executor(None, to_run)
        except Exception as e:
            logger.error(f"Failed to update info of url: {self.web_url}\n{e}")
        self.url = res['url']
        self.duration = res['duration']

    def get_desc(self, playing: bool) -> str:
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


class MusicList:
    def __init__(self, maxlen: int = None, fn: Path = None):
        self.dq = deque(maxlen=maxlen)
        self.fn = fn

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

    def __init__(self, ctx, config_path: Path):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.cog = ctx.cog
        self.config_path = config_path

        self.next_event = asyncio.Event()

        self.msg_np = None
        self.msg_pl = None
        self.volume = .5
        self.current = None
        self.loop = False

        f_random_list = self.config_path / f"random.{ctx.guild.id}"
        self.random_list = MusicList(maxlen=500, fn=f_random_list)
        self.random_list.load()
        f_play_list = self.config_path / f"play.{ctx.guild.id}"
        self.playlist = MusicList(fn=f_play_list)
        self.playlist.load()
        logger.debug(f"Len(random_list): {len(self.random_list)}")
        self.start()
        self.is_exit = False

    def start(self):
        self.bot.loop.create_task(self.player_loop())
        self.is_exit = False

    async def next(self):
        vc = self.guild.voice_client
        if not vc.is_playing():
            return
        else:
            vc.stop()

    async def stop(self):
        self.is_exit = True
        await self.next()
        vc = self.guild.voice_client
        if vc and vc.is_connected():
            await vc.disconnect()


    async def get_music(self):
        '''
        Try to get a musisc from self.playlist.
        If self.playlist is empty, try self.random_list instead.
        Sleep 1 second if failed to get any music.
        '''
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
            logger.debug(f"Current: {self.current}...")
            logger.debug("Updating url...")
            try:
                await music.update_info(self.bot.loop)
            except Exception as e:
                title = "Error"
                desc = f"There was an error reading this source url. \n{music.title}.\n{e}"
                embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
                await self.channel.send(embed=embed)
                # Read next music
                continue
            logger.debug("Updated url...")

            # Generate the source to play
            try:
                options = '-vn -sn'
                # source = FFmpegPCMAudio(
                source = FFmpegOpusAudio(
                    music.url, bitrate=256, before_options='-copyts -err_detect ignore_err', options=options
                )
            except Exception as e:
                logger.debug(f"Failed to generate FFmpegOpusAUdio:{e}")
                continue

            # Print the musci to play
            logger.debug(f"Now playing {music}...")
            embed = discord.Embed(
                title="Now playing",
                description=music.get_desc(True),
                color=discord.Color.green()
            )
            self.msg_np = await self.channel.send(embed=embed)
            # await self.msg_np.add_reaction("💔")
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
                        desc = "I'm not playing."
                        embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
                        self.msg_np = await self.channel.send(embed=embed)
                    await self.next_event.wait()
                    if self.current and self.current.loop > 1:
                        logger.debug("Reduce loop!")
                        self.current.loop -= 1
                    source.cleanup()
            except asyncio.TimeoutError:
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

    def get_player(self, ctx):
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            logger.debug("Trying to create a player")
            player = MusicPlayer(ctx, self.config_path)
            self.players[ctx.guild.id] = player
            logger.debug("Created a player")
        return player

    async def check_vc(self, message) -> Dict:
        guild_id = message.guild.id
        if str(guild_id) != '808893235103531039':
            logger.debug(f"guild id {guild_id}")
            state = False
            info = "You need to play streamer commands in Catbaron's Server."
            return {'state': state, 'info': info}

        voice = message.author.voice
        if not voice:
            state = False
            info = "You need to join a VC to run this command."
            return {'state': state, 'info': info}
        vc = voice.channel
        logger.debug("Get player for cmd_check")
        player = self.players.get(guild_id, None)
        if not player:
            state = False
            info = "I'm not playing."
            return {'state': state, 'info': info}
        p_vc = player.guild.voice_client
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
        brief='Stop the player.'
    )
    async def cmd_stop(self, ctx, *args):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        await player.stop()
        # vc = ctx.voice_client
        # if vc and vc.is_connected():
        #     await vc.disconnect()
        del self.players[ctx.guild.id]

    @commands.command(
        name='start',
        aliases=['s'],
        brief='Start the player.'
    )
    async def cmd_start(self, ctx):
        self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        self.get_player(ctx)


    @commands.command(
        name='del',
        brief='Delete a song (remove from playlist and delete from random list)',
    )
    async def cmd_del(self, ctx, pos: int = 0):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
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
                # Remove player.current
                loop = player.loop
                player.loop = False
                player.current.loop = 0
                await self.cmd_next(ctx)
                player.loop = loop
            else:
                music = player.playlist[pos - 1]
                player.random_list.remove(music)
                player.playlist.remove(music)
            embed = discord.Embed(
                title="Well done!",
                description=f"The music is deleted: {music.title}",
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
        brief='Add a song to the playlist through keywords or youtube url'
    )
    async def cmd_add(self, ctx, *args):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
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
            if music not in player.random_list:
                _music = Music(requester=None, title=item['title'], web_url=item['web_url'])
                player.random_list.put(_music)
            else:
                logger.debug(f"It's in the list {music}")
            if music in player.playlist:
                title = "Warning"
                desc =  "This music is already in the playlist: {music.title}."
                embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
                await ctx.message.reply(embed=embed)
            else:
                new_music.append(music.title)
                player.playlist.put(music)
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
            await self.cmd_next(ctx)

    @commands.command(
        name='reload',
        aliases=['rl'],
        brief="Reload random playlist."
    )
    async def cmd_rl(self, ctx):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        player.random_list.load()
        title = "Well done!"
        desc = f"{len(player.random_list)} music loaed to random playlist."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await ctx.message.reply(embed=embed)

    @commands.command(
        name='playlist',
        guild='808893235103531039',
        aliases=['pl', 'q'],
        brief="Show the playlist."
    )
    async def cmd_pl(self, ctx, pl: str = None):
        player = self.get_player(ctx)
        if not pl or pl == 'playlist':
            playlist = player.playlist
        elif pl == 'random':
            playlist = player.random_list
        music = player.current
        if not music:
            title = "Error"
            desc = "Failed to run command: I'm not playing."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return
        desc = [music.get_desc(playing=True)]
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
        brief="Restart the player. Plaeas use it when the player is freezing."
    )
    async def cmd_restart(self, ctx):
        self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        await self.cmd_stop(ctx)
        await asyncio.sleep(1)
        await self.cmd_start(ctx)

    @commands.command(
        name='current',
        aliases=['np', 'cur', 'playing'],
        brief="Show the current music."
    )
    async def cmd_np(self, ctx):
        player = self.get_player(ctx)
        if ctx.guild.id not in self.players:
            title = "Error"
            desc = "Failed to run command: I'm not playing."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)
            return
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
        guild='808893235103531039',
        aliases=['rp', 'replay'],
        brief="repeat the current music for up to 10 times."
    )
    async def cmd_repeat(self, ctx, times: int):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_replay")
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
        guild='808893235103531039',
        aliases=['lp'],
        usage="on/off",
        brief="Set the switch of loop on the playlist."
    )
    async def cmd_toggle_loop_list(self, ctx, switch):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_loop")
        if switch == 'on':
            player.loop = True
            title = "Well done!"
            desc = "Start to loop on the playlist."
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
            await ctx.message.reply(embed=embed)
        elif switch == 'off':
            player.current.loop = False
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
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        player.stop()
        # vc = ctx.voice_client
        # if not vc.is_playing():
        #     return
        # else:
        #     vc.stop()

    @commands.command(
        name='pick',
        guild='808893235103531039',
        aliases=['pk'],
        brief="Pick a music to the top of playlist."
    )
    async def cmd_pick(self, ctx, pos: int):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_pick")
        if 0 < pos <= len(player.playlist):
            music = player.playlist.pop(pos - 1)
            player.playlist.put(music)
            title = "Well done!"
            desc = f"One music is picked: {music.title}"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.green()
            )
            await ctx.message.reply(embed=embed)
        else:
            title = "Error"
            desc = "Failed to run command !Invalid argument: pos!"
            embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
            await ctx.message.reply(embed=embed)

    @commands.command(
        name='remove',
        guild='808893235103531039',
        aliases=['rm'],
        brief="Remove a music from the playlist."
    )
    async def cmd_rm(self, ctx, pos: int):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_rm")

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


    @commands.command(
        name='clear',
        guild='808893235103531039',
        aliases=['cl', 'empty'],
        brief="Remove all the musics."
    )
    async def cmd_clear(self, ctx):
        player = self.get_player(ctx)
        check = await self.check_vc(ctx.message)
        if not check['state']:
            embed = discord.Embed(
                    title="Error",
                    description=f"Failed to run command: {check['info']}",
                    color=discord.Color.red()
            )
            await ctx.message.reply(embed=embed)
            return
        logger.debug("Get player for cmd_clear")
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
        check = await self.check_vc(reaction.message)
        if not check['state']:
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
        check = await self.check_vc(reaction.message)
        if not check['state']:
            return
        if user == msg.author:
            logger.debug("The reaction is sent by me!")
            return
        if msg != player.msg_np:
            logger.debug("Not the np_msg!")
            return
        if reaction.emoji == sign_single_loop:
            player.current.loop = 0
