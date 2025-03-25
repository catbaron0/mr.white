import re
from pathlib import Path
import json


CONFIG_PATH = Path(__file__).parent


def replace_links(text):
    # 正则匹配 URL（支持 http, https, www.）
    if text.startswith("https://tenor.com/view/"):
        return "看我表情"
    url_pattern = r"https?://[^\s]+|www\.[^\s]+"
    return re.sub(url_pattern, "看这个链接", text)


def process_content(text: str) -> str:
    text = re.sub("@\d+", "那个谁", text)
    text = process_emoji(text)
    text = replace_links(text)
    return text


def process_emoji(text: str) -> str:
    with open(CONFIG_PATH / "emoji.json", "r", encoding="utf-8") as file:
        emoji_data = json.load(file)
    for emoji, description in emoji_data.items():
        text = text.replace(emoji, description)
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


def generate_script(msg_type: str, user_name: str, content: str) -> str:
    user_name = process_user_name(user_name)
    content = process_content(content)

    if msg_type == "text" and content:
        if len(content) > 100:
            text = f"{user_name}说了很多东西你们自己看吧"
        else:
            text = f"{user_name}说, {content}"
        return text

    if msg_type == "sticker":
        return f"{user_name}发了{content}个表情包。"

    if msg_type == "enter":
        return f"{user_name} 来了。"

    if msg_type == "exit":
        return f"{user_name} 走了。"

    return ""
