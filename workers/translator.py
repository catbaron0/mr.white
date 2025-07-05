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

    async def translate(self, text: str) -> str:
        if not text:
            return  # 忽略空消息
        res = await gpt_translate_to_zh(text)
        if res == text:
            return ""
        return res

    async def auto_translate(self, message):
        channel_id = message.channel.id
        text = message.content.strip()
        author_id = message.author.id
        author_is_bot = message.author.bot

        if channel_id not in self.auto_trans_channel:
            logger.info(f"skip channel: {channel_id}")
            return  # 忽略非自动翻译频道的消息
        if not text:
            logger.info("skip empty message")
            return  # 忽略空消息
        if author_is_bot and author_id not in self.auto_trans_channel[channel_id]["allow_bots"]:
            logger.info(f"skip bot message: {author_id} in channel {channel_id}")
            return  # 忽略机器人消息

        res = await gpt_translate_to_zh(text)
        if res != text:
            try:
                logger.info(f"message translated: \n{text}\n{res}")
                await message.reply(res)
            except Exception as e:
                logger.error(f"自动翻译失败: {e}")
