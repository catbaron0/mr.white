import re
import logging

from discord import Message, Member

from workers.repeater_manager import RepeaterManager
LOG = logging.getLogger(__name__)


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
        assert user.voice is not None
        voice_channel = user.voice.channel
    except Exception as e:
        LOG.error(e)
        return
    await repeater_manager.start_repeater(guild, voice_channel, None)
