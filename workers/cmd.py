from urllib import parse
import html
# from pypinyin import pinyin
# import wikipedia as wiki
from discord import Embed
import logging
import re
import json
import requests
import subprocess
# from lib.search_music import YoutubeMusic
from pathlib import Path
# from bs4 import BeautifulSoup as bs
# import openai


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
ch = logging.StreamHandler()
fh.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
ch.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(fh)
logger.addHandler(ch)


# class PinyinCMD:
#     def __init__(self):
#         self.name = 'py'
#         self.usage = '中文内容'
#         self.brief = 'Label pinyin to inputs Chinese.'
#         self.description = self.brief

#     @staticmethod
#     def words2pinyin(words):
#         pys = pinyin(words, heteronym=False, errors=lambda x: list(x))
#         word_py = ""
#         for i, w in enumerate(words):
#             py = '/'.join(pys[i])
#             if py == w:
#                 word_py += w
#             else:
#                 word_py += f"{w}({py})"
#         return word_py

#     async def __call__(self, ctx, words: str):
#         msg = ctx.message
#         if not words.strip() and msg.reference:
#             words = msg.reference.cached_message.content
#         reply = self.words2pinyin(words)
#         await ctx.message.reply(reply)


# class WikiCMD:
#     def __init__(self, lang="zh"):
#         self.wiki = wiki
#         self.lang = lang
#         self.wiki.set_lang(lang)

#         self.name = 'wiki'
#         self.usage = 'QUERY'
#         self.brief = 'Search for input query from wikipedia.zh'
#         self.description = self.brief

#     def generate_reply(self, item) -> str:
#         msg_text = ''
#         emb = None
#         try:
#             page = self.wiki.page(item)
#             emb = Embed(title=page.title, url=page.url, description=page.summary)
#         except wiki.PageError:
#             msg_text = f'No wikipedia page for "{item}"'
#         except wiki.DisambiguationError as e:
#             options = ", ".join(e.options)
#             ambi = f"[{item}] may refer to: \n {options}.\n" 
#             ambi += f"Here is the intro about **{e.options[0]}**:"
#             msg_text = ambi
#             page = self.wiki.page(e.options[0])
#             emb = Embed(title=page.title, url=page.url, description=page.summary)
#         return {'msg_text': msg_text, 'emb': emb}

#     async def __call__(self, ctx, query: str):
#         msg = ctx.message
#         if not query.strip() and msg.reference:
#             query = msg.reference.cached_message.content
#         msg = await ctx.message.reply('Loading ...')
#         try:
#             reply = self.generate_reply(query)
#         except Exception:
#             msg_text = f'No wikipedia page for "{query}"'
#             reply = {"msg_text": msg_text, 'emb': None}

#         reply_text = reply['msg_text']
#         reply_text = f'[{query}]:\n' + reply_text
#         reply_emb = reply['emb']
#         if reply_emb:
#             await msg.edit(content=reply_text, embed=reply_emb)
#         else:
#             await msg.edit(content=reply_text)


# class MemeCMD:
#     def __init__(self):
#         self.url = 'https://api.jikipedia.com/go/search_definitions'
#         self.headers = {'Client': 'web', 'Content-Type': 'application/json;charset=UTF-8'}
#         self.regex = re.compile('\[[^:]+:([^\]]+)\]')

#         self.name = 'meme'
#         self.usage = 'MEME'
#         self.brief = 'Explain the source and meaning of input meme.'
#         self.description = self.brief

#     async def __call__(self, ctx, meme: str):
#         msg = ctx.message
#         if not meme.strip() and msg.reference:
#             meme = msg.reference.cached_message.content
#         msg = await ctx.message.reply('Loading ...')
#         data = {"phrase": meme, "page": 1}
#         data = json.dumps(data)
#         try:
#             res = requests.post(self.url, data=data, headers=self.headers, proxies={"https": "socks5://localhost:1111"})
#         except requests.exceptions.ConnectionError:
#             logger.info("failed with proxy, try direct connection")
#             try:
#                 res = requests.post(self.url, data=data, headers=self.headers)
#             except Exception as e:
#                 reply = "查不到"
#                 logger.info(f"Failed to search meme: {e}")
#                 await msg.edit(content=reply)
#                 return
#         except Exception as e:
#             reply = "查不到"
#             logger.info(f"Failed to search meme: {e}")
#             await msg.edit(content=reply)
#             return
#         if res.status_code != 200:
#             reply = "查不到"
#             await msg.edit(content=reply)
#             return
#         res = res.json()
#         if res['size'] < 1:
#             reply = "查不到"
#             await msg.edit(content=reply)
#             return
#         term = res['data'][0]['term']['title']
#         content = res['data'][0]['content']
#         content = self.regex.sub(r'\1', content)
#         reply_text = f'[{term}]:\n' + content
#         if len(reply_text) > 200:
#             reply_text = reply_text[:200] + ' ...'
#         await msg.edit(content=reply_text)


class TranslateCMD:
    def __init__(self):
        self.active_chats = list()
        self.url = 'http://translate.google.cn/m?q=%s&tl=%s&sl=%s'

        self.name = 'tr'
        self.usage = 'SENTENCE'
        self.brief = 'Translate between Chinese and English.'
        self.description = self.brief

    @staticmethod
    def translate(text, to_language="zh-CN", text_language="auto"):
        GOOGLE_TRANSLATE_URL = 'http://translate.google.cn/m?q=%s&tl=%s&sl=%s'
        text = parse.quote(text)
        url = GOOGLE_TRANSLATE_URL % (text, to_language, text_language)
        response = requests.get(url)
        data = response.text
        expr = r'(?s)class="(?:t0|result-container)">(.*?)<'
        result = re.findall(expr, data)
        if (len(result) > 0):
            return html.unescape(result[0])

    async def __call__(self, ctx, text: str):
        msg = ctx.message
        if not text.strip() and msg.reference:
            text = msg.reference.cached_message.content
        msg = await ctx.message.reply("Loading ...")
        reply = self.translate(text).strip()
        if not reply:
            reply = "Error: 查不到"
        elif reply == text:
            reply = self.translate(text, to_language="en")
        await msg.edit(content=reply)

    async def ___call__(self, ctx, text: str):
        print(f"Get a query to translate {text}")
        msg = await ctx.message.reply("Loading ...")
        query = {
            'type': 'AUTO',
            'i': text,
            'doctype': 'json',
            'version': '2.1',
            'keyfrom': 'fanyi.web',
            'ue': 'utf-8',
            'action': 'FY_BY_CLICKBUTTON',
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


# class BookCMD:
#     def __init__(self, lang="zh"):
#         self.name = 'book'
#         self.usage = 'Title [authors]'
#         self.brief = 'Search for books.'
#         self.description = self.brief

#         self.base_url = 'https://www.goodreads.com'
#         self.url_search = self.base_url + '/search?q='

#     def generate_reply(self, query):
#         # search
#         url_search = self.url_search + query
#         emb = None
#         try:
#             print('Query ID...')
#             res_search = requests.get(url_search)
#             soup = bs(res_search.text)
#         except Exception as e:
#             print(f"Failed to search: {e}")
#             msg_text = "完了，找不到。问问猫怎么回事。"
#             return {'msg_text': msg_text, 'emb': emb}
#         try:
#             book_url = soup.tr.a["href"].split("?")[0]
#         except Exception as e:
#             print(f"Failed to search: {e}")
#             msg_text = "瞎搜啥玩儿，我没这书。"
#             return {'msg_text': msg_text, 'emb': emb}

#         # get details
#         info_url = self.base_url + book_url + "?from_search=true"
#         try:
#             res_search = requests.get(info_url)
#             soup = bs(res_search.text)
#         except Exception as e:
#             print(f"Failed to search: {e}")
#             msg_text = "完了，找不到。问问猫怎么回事。"
#             return {'msg_text': msg_text, 'emb': emb}
#         print(soup)
#         title = soup.select("#bookTitle")[0].text.strip()
#         authors = ",".join([n.text for n in soup.find_all("span", itemprop="name")])
#         desc = soup.select("#description")[0].text.strip()
#         summary = f"《{title}》\n作者: {authors})\n{desc}\n"
#         emb = Embed(title=title, url=info_url, description=summary)
#         return {'msg_text': summary, 'emb': emb}

#     async def __call__(self, ctx, query: str):
#         msg = ctx.message
#         if not query.strip() and msg.reference:
#             query = msg.reference.cached_message.content
#         msg = await ctx.message.reply('Loading ...')
#         try:
#             reply = self.generate_reply(query)
#         except Exception as e:
#             msg_text = f'No Book for "{query}"'
#             reply = {"msg_text": msg_text, 'emb': None}
#             raise e

#         reply_text = reply['msg_text']
#         reply_text = f'[{query}]:\n' + reply_text
#         reply_emb = reply['emb']
#         if reply_emb:
#             await msg.edit(content="", embed=reply_emb)
#         else:
#             await msg.edit(content=reply_text)


# class MovieCMD:
#     def __init__(self, token: str):
#         self.token = token
#         self.url_search = (
#             'https://api.themoviedb.org/3/search/multi?api_key='
#             f'{token}&language=zh-ch&page=1&include_adult=false&query='
#         )

#         self.name = 'movie'
#         self.usage = 'Title'
#         self.brief = 'Search for movies.'
#         self.description = self.brief

#     def generate_reply(self, query):
#         # search
#         url = self.url_search + query
#         emb = None
#         try:
#             res = requests.get(url).json()["results"]
#         except Exception as e:
#             print(f"Failed to seach movie: {query}", e)
#             msg_text = "出事了，快让猫过来看看怎么回事。"
#             return {'msg_text': msg_text, 'emb': emb}
#         if not res or res[0]['media_type'] not in ("movie", "tv"):
#             msg_text = "这名字你瞎编的吧，放映员说他没看过。"
#             return {'msg_text': msg_text, 'emb': emb}

#         res = res[0]
#         media_type = res['media_type']
#         if media_type == "movie":
#             mt = "电影"
#             date = res['release_date']
#             title = res['title']
#             original_title = res['original_title']

#         elif media_type == "tv":
#             mt = "剧集"
#             date = res["first_air_date"]
#             title = res["name"]
#             original_title = res["original_name"]

#         overview = res['overview']
#         if original_title != title:
#             original_title = f"《{title}》({original_title})"
#         else:
#             original_title = f"《{title}》"
#         title = f"{title}({mt})"
#         desc = title + "\n" + f"上映时间: {date}\n" + f"简介: {overview}"
#         emb = Embed(title=title, description=desc)

#         poster_path = res["poster_path"]
#         if poster_path:
#             image_url = "https://image.tmdb.org/t/p/w500" + poster_path
#             emb.set_image(url=image_url)
#         return {'msg_text': desc, 'emb': emb}

#     async def __call__(self, ctx, query: str):
#         msg = ctx.message
#         if not query.strip() and msg.reference:
#             query = msg.reference.cached_message.content
#         msg = await ctx.message.reply('Loading ...')
#         try:
#             reply = self.generate_reply(query)
#         except Exception as e:
#             msg_text = f'No Movie page for "{query}"'
#             reply = {"msg_text": msg_text, 'emb': None}
#             raise e

#         reply_text = reply['msg_text']
#         reply_text = f'[{query}]:\n' + reply_text
#         reply_emb = reply['emb']
#         if reply_emb:
#             await msg.edit(content="", embed=reply_emb)
#         else:
#             await msg.edit(content=reply_text)


# class GptCMD:
#     def __init__(self, openai_key):
#         self.bot = None
#         self.name = 'gpt'
#         self.usage = '你的问题'
#         self.brief = 'A chatGPT driven chat bot.'
#         self.description = self.brief
#         self.is_free = True
#         self.role_prompt = "Your are Mr.White, a helpful assistant. You like playing basketball, dancing and rap. You have been working with Batman for years."
#         openai.api_key = openai_key
#         self.conversation = {}

#     def add_conversation(self, author_id, role: str, content: str):
#         if author_id not in self.conversation:
#             self.conversation[author_id] = []
#         self.conversation[author_id].append({"role": role, "content": content})
#         self.conversation[author_id] = self.conversation[author_id][-0:]
#         conv = self.conversation[author_id][-0:][:]
#         conv = [{"role": "system", "content": self.role_prompt}] + conv
#         return conv


#     async def __call__(self, ctx, prompt: str):
#         words = []
#         reply = ""
#         user_id = ctx.message.author.id
#         conv = self.add_conversation(user_id, "user", prompt)
#         if not self.is_free:
#             msg = await ctx.message.reply("Thinking about last question, please try later...")
#         else:
#             msg = ctx.message
#             msg = await ctx.message.reply("Thinking...")
#         try:
#             async with ctx.typing():
#                 print("Asking bot")
#                 # response = self.bot.ask(que)
#                 response = openai.ChatCompletion.create(
#                     model="gpt-3.5-turbo",
#                     messages = conv,
#                     max_tokens=2048,
#                     stream=True
#                 )
#                 for res in response:
#                     try:
#                         words.append(res["choices"][0]["delta"]["content"])
#                     except KeyError:
#                         continue
#                     if len(words) % 5 == 0:
#                         reply = ''.join(words).strip()
#                         await msg.edit(content=reply)
#                 reply = ''.join(words).strip()
#                 self.add_conversation(user_id, "assistant", reply)
#                 await msg.edit(content=reply)
#         except Exception as e:
#             reply += f"Error: ```\n{e}\n```"
#             await msg.edit(content=reply)
#         print("reply:", reply)
