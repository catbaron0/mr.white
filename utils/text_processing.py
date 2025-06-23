import re
from pathlib import Path
from functools import partial


from  discord import Emoji, PartialEmoji


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


def process_user_name(text: str) -> str:
    return text.replace(
        "𝓈𝒾𝓇𝒾𝓈", "siris"
    ).replace(
        "𝚃𝙴𝙽𝚒", "teni"
    ).replace(
        "𝕃𝕖𝕥𝕠", "leto"
    ).replace(
        "ꩇׁׅ݊ᨵׁׅյׁׅᨵׁׅ ", "mojo"
    ).replace(
        "𝘣𝘭𝘶𝘦𝘺", "bluey"
    )
