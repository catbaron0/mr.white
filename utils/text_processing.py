import re
from pathlib import Path
from functools import partial

from discord import Emoji, PartialEmoji, Message

from workers.que_msg import QueueMessage


CONFIG_PATH = Path(__file__).parent


def replace_links(text):
    # 正则匹配 URL（支持 http, https, www.）
    if text.startswith("https://tenor.com/view/"):
        return "看我表情"
    url_pattern = r"https?://[^\s]+|www\.[^\s]+"
    return re.sub(url_pattern, "看这个链接", text)


def process_text_message(que_msg: QueueMessage, default_emoji: dict, custom_emoji: dict, custom_user: dict) -> str:
    message = que_msg.message
    if message is None:
        return ""
    text = str(message.content)

    # remove hidden style
    text = re.sub(r"\|\|.*?\|\|", "", text)

    # get mentions
    mentions = message.mentions
    id_to_name = {
        str(user.id): custom_user.get(str(user.id), user.display_name) for user in mentions
    }

    def _replacer(match):
        user_id = match.group(1)
        return f"{id_to_name.get(user_id, f'那个谁')}"
    text = re.sub(r"<@!?(?P<id>\d+)>", _replacer, text)

    text = process_emoji(text, default_emoji, custom_emoji)
    text = replace_links(text)
    text = number_to_chinese(text)

    image_count = sum(
        1 for attachment in message.attachments
        if attachment.content_type and attachment.content_type.startswith("image/")
    )
    if image_count > 0:
        if image_count == 1:
            image_count = ""
        if image_count == 2:
            image_count = "两"
        text += f"\n看这{image_count}张图"

    user_name = f"{que_msg.user_name}"
    if message.reference and message.reference.resolved and isinstance(message.reference.resolved, Message):
        target_user = message.reference.resolved.author
        target_username = custom_user.get(str(target_user.id), target_user.display_name)
        user_name = f"{que_msg.user_name}回复{target_username}"

    if len(text) > 100:
        return f"{user_name}说了很多东西你们自己看吧"
    else:
        return f"{user_name}说, {text}"


def emoji_to_str(emoji: Emoji | PartialEmoji | str | None, default_emoji_dict, custom_emoji_dict) -> str:
    if not emoji:
        return ""
    if isinstance(emoji, str):
        return default_emoji_dict.get(emoji) or custom_emoji_dict.get(emoji, "一个表情")
    return default_emoji_dict.get(emoji.name) or custom_emoji_dict.get(emoji.name, "一个表情")


def _replace_emoji(match, emoji_dict: dict):
    emoji_name = match.group(1)
    return emoji_dict.get(emoji_name, "一个表情")


def process_emoji(text: str, emoji_dict: dict, custom_emoji_dict: dict) -> str:
    # process custom emoji
    text = re.sub(r"<[a-z]?:(.+):\d+>", partial(_replace_emoji, emoji_dict=custom_emoji_dict), text)

    # process emoji
    pattern = "|".join(map(re.escape, emoji_dict.keys()))
    text = re.sub(pattern, lambda match: emoji_dict.get(match.group(0), "emoji"), text)

    return text


def number_to_chinese(text: str) -> str:
    """
    匹配文本中的数字（整数和小数），将每一位数字转换为汉字，小数点转换为「点」。
    例：123.45 -> 一二三点四五
    """
    num_map = {
        '0': '零', '1': '一', '2': '二', '3': '三', '4': '四', '5': '五',
        '6': '六', '7': '七', '8': '八', '9': '九', '.': '点'
    }

    def repl(match):
        return ''.join(num_map.get(ch, ch) for ch in match.group(0))
    # 匹配整数和小数
    return re.sub(r'\d+\.\d+|\d+', repl, text)
