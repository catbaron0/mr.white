import re

from discord import Message, Member

from workers.repeater_manager import RepeaterManager


async def process_webhook_start_rp(message: Message, repeater_manager: RepeaterManager):
    # join @user_name
    pattern = r"^join\s+<@!?(\d+)>$"
    if not re.match(pattern, message.content.strip()):
        return
    if not message.mentions:
        return
    user = message.mentions[0]
    assert isinstance(user, Member)
    guild = message.guild
    try:
        voice_channel = user.voice.channel
    except Exception as e:
        print(f"DEBUG: {e}")
        return
    await repeater_manager.start_repeater(guild, voice_channel, None)
