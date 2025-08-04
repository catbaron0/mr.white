import logging

from utils.open_ai import gpt_translate_to_zh
from config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
ch = logging.StreamHandler()
fh.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
ch.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(fh)
logger.addHandler(ch)


class Translator:
    def __init__(self):
        self.load_config()

    def load_config(self):
        self.auto_trans_channel = config.load_trans_channel()

    async def translate(self, text: str) -> str | None:
        if not text:
            return  # 忽略空消息
        res = await gpt_translate_to_zh(text)
        if res == text:
            return ""
        return res

    async def auto_translate(self, message):
        channel_id = str(message.channel.id)
        author_id = str(message.author.id)
        if channel_id not in self.auto_trans_channel:
            return
        if author_id not in self.auto_trans_channel[channel_id]["author_id"]:
            return

        text = message.content.strip()
        if not text:
            logger.info("skip empty message")
            return  # 忽略空消息
        res = await gpt_translate_to_zh(text)
        if res != text:
            try:
                logger.info(f"message translated: \n{text}\n{res}")
                await message.reply(res)
            except Exception as e:
                logger.error(f"自动翻译失败: {e}")
