import re
from pathlib import Path
from functools import partial

from discord import Emoji, PartialEmoji, Message

from workers.que_msg import QueueMessage
from utils.open_ai import gpt_summary, describe_image


CONFIG_PATH = Path(__file__).parent


def _replace_links(text):
    # 正则匹配 URL（支持 http, https, www.）
    if text.startswith("https://tenor.com/view/"):
        return "看我表情"
    url_pattern = r"https?://[^\s]+|www\.[^\s]+"
    return re.sub(url_pattern, "看这个链接", text)


def _process_punctuation(text: str) -> str:
    puncts = {
        "?": "问号",
        "!": "感叹号",
        ".": "点",
        "…": "点点点",
        "？": "问号",
        "！": "感叹号",
        "。": "点",
    }

    num_map = {
        1: "一个", 2: "两个", 3: "三个", 4: "四个", 5: "五个",
        6: "六个", 7: "七个", 8: "八个", 9: "九个", 10: "十个"
    }

    # 匹配前导标点
    match = re.match(r'^[.。!！?？…]+', text)
    if not match:
        return text

    leading = match.group()

    # 分组统计连续相同标点
    groups = []
    prev = leading[0]
    count = 1
    for ch in leading[1:]:
        if ch == prev:
            count += 1
        else:
            groups.append((prev, count))
            prev = ch
            count = 1
    groups.append((prev, count))

    # 生成中文描述
    parts = []
    for ch, count in groups:
        count_text = num_map.get(count, f"{count}个")
        punct = puncts.get(ch, ch)
        if not punct:
            continue
        parts.append(count_text + punct)
    replaced = "".join(parts)

    # 拼接剩余部分
    return replaced + text[len(leading):]


def _process_channel_mention(content, guild, emoji_dict) -> str:
    def repl(match):
        channel_id = int(match.group(1))
        channel = guild.get_channel(channel_id)
        if channel:
            channel_name = "".join(["" if c in emoji_dict else c for c in channel.name])
            channel_name = channel_name.strip("-")
            if channel_name != "":
                return f"{channel_name}频道"
        # return match.group(0)  # 找不到频道就保留原样
        return "这个频道"

    content = re.sub(r"<#(\d+)>", repl, content)
    return re.sub("频道\s*频道", "频道", content)


def _process_user_mention(content, mentions, custom_user) -> str:
    id_to_name = {
        str(user.id): custom_user.get(str(user.id), user.display_name) for user in mentions
    }

    def _replacer(match):
        user_id = match.group(1)
        return f"{id_to_name.get(user_id, f'那个谁')}"
    content = re.sub(r"<@!?(?P<id>\d+)>", _replacer, content)
    return content


def _replace_emoji(match, emoji_dict: dict):
    emoji_name = match.group(1)
    return emoji_dict.get(emoji_name, "一个表情")


def _process_emoji(text: str, emoji_dict: dict, custom_emoji_dict: dict) -> str:
    # process custom emoji
    text = re.sub(r"<[a-z]?:(.+):\d+>", partial(_replace_emoji, emoji_dict=custom_emoji_dict), text)

    # process emoji
    pattern = "|".join(map(re.escape, emoji_dict.keys()))
    text = re.sub(pattern, lambda match: emoji_dict.get(match.group(0), "emoji"), text)

    return text


def _number_to_chinese(s: str) -> str:
    """
    匹配文本中的数字（整数和小数），将每一位数字转换为汉字，小数点转换为「点」。
    例：123.45 -> 一二三点四五
    """
    num_map = {'0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
               '5': '五', '6': '六', '7': '七', '8': '八', '9': '九', '.': '点'}

    # 转换百分数
    s = re.sub(r'(\d+(?:\.\d+)?)%', r'百分之\1', s)

    # 匹配三位及以上整数，不用 \b，改用负向前后查找，避免影响中文
    def replace_long_integer(match):
        num = match.group(1)
        return ''.join(num_map[ch] for ch in num)

    s = re.sub(r'(?<!\d)(\d{4,})(?!\d)', replace_long_integer, s)

    return s


def _replace_special_tokens(text) -> str:
    # process AI
    pattern = r'(?<![A-Za-z])[Aa][Ii](?![A-Za-z])'
    text = re.sub(pattern, ' A I ', text)
    # process NS
    pattern = r'(?<![A-Za-z])[Nn][Ss](?![A-Za-z])'
    text = re.sub(pattern, ' N S ', text)
    return text


async def process_text_message(que_msg: QueueMessage, default_emoji: dict, custom_emoji: dict, custom_user: dict) -> str:
    message = que_msg.message
    if message is None:
        return ""
    text = str(message.content)

    # remove hidden style
    text = re.sub(r"\|\|.*?\|\|", "", text)

    # get mentions
    text = _process_user_mention(text, message.mentions, custom_user)

    # get channel mentions
    if message.guild:
        text = _process_channel_mention(text, message.guild, default_emoji)

    text = _process_emoji(text, default_emoji, custom_emoji)
    text = _replace_links(text)
    text = _number_to_chinese(text)
    text = _process_punctuation(text)
    text = _replace_special_tokens(text)

    attachments = message.attachments
    url = ""
    image_attatchments = []
    for att in attachments:
        if att.content_type and att.content_type.startswith("image/"):
            image_attatchments.append(att)
        if not url and att.url:
            url = att.url
    image_count = len(image_attatchments)

    if image_count > 0:
        if image_count == 1:
            image_count = ""
        if image_count == 2:
            image_count = "两"
        text += f"\n看这{image_count}张图。\n"

    # if url:
    #     try:
    #         desc = await describe_image(url)
    #         if desc:
    #             text += f"{desc}"
    #     except Exception as e:
    #         print(f"[describe_image] Failed to process {url}: {e}")

    user_name = custom_user.get(str(que_msg.user.id), que_msg.user.display_name)
    if message.reference and message.reference.resolved and isinstance(message.reference.resolved, Message):
        target_user = message.reference.resolved.author
        target_username = custom_user.get(str(target_user.id), target_user.display_name)
        user_name = f"{user_name}回复{target_username}"

    if len(text) > 100:
        desc = await gpt_summary(text)
        if desc:
            return f"{user_name} 说了很长一段话, {desc}"
        else:
            return f"{user_name} 说了很多东西你们自己看吧"
    else:
        return f"{user_name} 说, {text}"


def emoji_to_str(emoji: Emoji | PartialEmoji | str | None, default_emoji_dict, custom_emoji_dict) -> str:
    if not emoji:
        return ""
    if isinstance(emoji, str):
        return default_emoji_dict.get(emoji) or custom_emoji_dict.get(emoji, "一个表情")
    return default_emoji_dict.get(emoji.name) or custom_emoji_dict.get(emoji.name, "一个表情")
