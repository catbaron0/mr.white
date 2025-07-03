from urllib import parse
import html
import logging
import re
import requests


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
ch = logging.StreamHandler()
fh.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
ch.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(fh)
logger.addHandler(ch)


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

