import re
from pathlib import Path
from functools import partial

from discord import Emoji, PartialEmoji


CONFIG_PATH = Path(__file__).parent


def replace_links(text):
    # 正则匹配 URL（支持 http, https, www.）
    if text.startswith("https://tenor.com/view/"):
        return "看我表情"
    url_pattern = r"https?://[^\s]+|www\.[^\s]+"
    return re.sub(url_pattern, "看这个链接", text)


def process_content(text: str, emoji_dict: dict, custom_emoji_dict: dict) -> str:
    print("DEBUG process emoji:", text)
    text = str(text)

    text = re.sub("@\d+", "那个谁", text)
    text = process_emoji(text, emoji_dict, custom_emoji_dict)
    text = replace_links(text)
    text = number_to_chinese(text)
    return text


def get_custom_emoji(emoji, custom_emoji_dict) -> str:
    if isinstance(emoji, str):
        return emoji
    return custom_emoji_dict.get(emoji.name, "一个表情")


def translate_emoji(emoji: str, emoji_dict: dict, custom_emoji_dict) -> str:
    if isinstance(emoji, Emoji) or isinstance(emoji, PartialEmoji):
        return get_custom_emoji(emoji, custom_emoji_dict)
    return emoji_dict.get(emoji, " emoji ")


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
