from pypinyin import pinyin
import wikipedia as wiki
from discord import Embed
import logging
import re
import json
import requests
import subprocess
from lib.search_music import YoutubeMusic
from pathlib import Path


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
ch = logging.StreamHandler()
fh.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
ch.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(fh)
logger.addHandler(ch)



class PinyinCMD:
    def __init__(self):
        self.name = 'py'
        self.usage = '中文内容'
        self.brief = 'Label pinyin to inputs Chinese.'
        self.description = self.brief

    @staticmethod
    def words2pinyin(words):
        pys = pinyin(words, heteronym=False, errors=lambda x: list(x))
        word_py = ""
        for i, w in enumerate(words):
            py = '/'.join(pys[i])
            if py == w:
                word_py += w
            else:
                word_py += f"{w}({py})"
        return word_py

    async def __call__(self, ctx, words: str):
        reply = self.words2pinyin(words)
        await ctx.message.reply(reply)


class WikiCMD:
    def __init__(self, lang="zh"):
        self.wiki = wiki
        self.lang = lang
        self.wiki.set_lang(lang)

        self.name = 'wiki'
        self.usage = 'QUERY'
        self.brief = 'Search for input query from wikipedia.zh'
        self.description = self.brief

    def generate_reply(self, item) -> str:
        msg_text = ''
        emb = None
        try:
            page = self.wiki.page(item)
            emb = Embed(title=page.title, url=page.url, description=page.summary)
        except wiki.PageError:
            msg_text = f'No wikipedia page for "{item}"'
        except wiki.DisambiguationError as e:
            options = ", ".join(e.options)
            ambi = f"[{item}] may refer to: \n {options}.\n" 
            ambi += f"Here is the intro about **{e.options[0]}**:"
            msg_text = ambi
            page = self.wiki.page(e.options[0])
            emb = Embed(title=page.title, url=page.url, description=page.summary)
        return {'msg_text': msg_text, 'emb': emb}

    async def __call__(self, ctx, query: str):
        msg = await ctx.message.reply('Loading ...')
        reply = self.generate_reply(query)
        reply_text = reply['msg_text']
        reply_text = f'[{query}]:\n' + reply_text
        reply_emb = reply['emb']
        if reply_emb:
            await msg.edit(content=reply_text, embed=reply_emb)
        else:
            await msg.edit(content=reply_text)


class MemeCMD:
    def __init__(self):
        self.url = 'https://api.jikipedia.com/go/search_definitions'
        self.headers = {'Client': 'web', 'Content-Type': 'application/json;charset=UTF-8'}
        self.regex = re.compile('\[[^:]+:([^\]]+)\]')

        self.name = 'meme'
        self.usage = 'MEME'
        self.brief = 'Explain the source and meaning of input meme.'
        self.description = self.brief

    async def __call__(self, ctx, meme: str):
        msg = await ctx.message.reply('Loading ...')
        data = {"phrase": meme, "page":1}
        data = json.dumps(data)
        try:
            res = requests.post(self.url, data=data, headers=self.headers, proxies={"https": "socks5://localhost:1111"})
        except requests.exceptions.ConnectionError:
            logger.info("failed with proxy, try direct connection")
            try:
                res = requests.post(self.url, data=data, headers=self.headers)
            except Exception as e:
                reply = "查不到"
                logger.info(f"Failed to search meme: {e}")
                await msg.edit(content=reply)
                return
        except Exception as e:
            reply = "查不到"
            logger.info(f"Failed to search meme: {e}")
            await msg.edit(content=reply)
            return
        if res.status_code != 200:
            reply = "查不到"
            await msg.edit(content=reply)
            return
        res = res.json()
        if res['size'] < 1:
            reply = "查不到"
            await msg.edit(content=reply)
            return
        term = res['data'][0]['term']['title']
        content = res['data'][0]['content']
        content = self.regex.sub(r'\1', content)
        reply_text = f'[{term}]:\n' + content
        if len(reply_text) > 200:
            reply_text = reply_text[:200]+' ...'
        await msg.edit(content=reply_text)


class TranslateCMD:
    def __init__(self):
        self.active_chats = list()
        self.url = 'http://fanyi.youdao.com/translate?smartresult=dict&smartresult=rule&smartresult=ugc&sessionFrom=null'

        self.name = 'tr'
        self.usage = 'SENTENCE'
        self.brief = 'Translate between Chinese and English.'
        self.description = self.brief

    async def __call__(self, ctx, text: str):
        msg = await ctx.message.reply("Loading ...")
        query = {
            'type': 'AUTO',
            'i': text,
            'doctype': 'json',
            'version': '2.1',
            'keyfrom': 'fanyi.web',
            'ue': 'utf-8',
            'action':'FY_BY_CLICKBUTTON',
            'typoResult': 'true'
        }
        try:
            reply = ""
            res = requests.post(self.url, data=query)
            results = res.json()['translateResult'][0]
            for r in results:
                reply += f"{r['tgt']}\n"
        except Exception:
            reply = "查不到"
        await msg.edit(content=reply)


class Mp3CMD:
    def __init__(self):
        self.ytm = YoutubeMusic('~/www/music', 'mp4', 10)
        self.url = 'https://catbaron.com/music/'

        self.name = 'mp3'
        self.usage = 'KEY WORDS'
        self.brief = 'Search for and download mp3 according key words.'
        self.description = "Search and download mp3. The key words should be the song's name (and the singer)"

    async def __call__(self, ctx, key_words: str):
        reply_msg = await ctx.message.reply('等我找找...')

        items = self.ytm.search(key_words.strip().replace('\n', ' '))
        title = self.ytm.download(items)
        if not title:
            reply_txt = "对不住，找不到"
            await reply_msg.edit(content=reply_txt)
            return

        await reply_msg.edit(content="找到了，正在转码，稍候个两分钟...")
        title_stem = Path(title).stem
        target = Path(title).parent / (title_stem + ".mp3")
        cmd_info = [
            "ffmpeg", "-n", "-i", str(title), "-acodec", "libmp3lame", "-ab", "256k", str(target)
        ]
        print(" ".join(cmd_info))
        process = subprocess.Popen(
            cmd_info,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        title = target
        fname = Path(title).name
        local_link = f"https://catbaron.com/music/{fname}"


        await reply_msg.edit(content='在传了，等我两分钟...')
        cmd_info = ['transfer', 'cat', str(title)]
        process = subprocess.Popen(
            cmd_info,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(" ".join(cmd_info))
        stdout, stderr = process.communicate()
        print(f"stdout: {stdout}\n")
        output_text = stdout.decode('utf-8').strip().split('\n')
        print(f"output_text: {output_text}\n")
        stdout = output_text[1].split(": ")[1]
        print(f"reply: {stdout}\n")
        stdout.replace('Download Link', '\n下载链接')
        stdout += f'\n备用: {local_link}'
        await reply_msg.edit(content=stdout)

