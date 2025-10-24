import logging
import asyncio

from discord import VoiceClient


LOG = logging.getLogger(__name__)


async def connect_voice_channel(voice_channel) -> VoiceClient | None:
    vc: VoiceClient | None = None

    if voice_channel.guild.voice_client:
        await voice_channel.guild.voice_client.disconnect(force=True)
        await asyncio.sleep(1.0)

    vc = await voice_channel.connect(timeout=10, reconnect=True)
    if vc and vc.is_connected():
        LOG.info("Voice channel connected successfully")
        return vc

    return None
