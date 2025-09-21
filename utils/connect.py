import logging
import asyncio

import discord
from discord import Message, VoiceChannel, VoiceClient, VoiceRegion


LOG = logging.getLogger(__name__)


async def connect_voice_channel(
    voice_channel: VoiceChannel,
    message: Message | None,
    region: VoiceRegion | None = None,
    retry: int = 3
) -> tuple[VoiceClient | None, Message | None]:

    vc: VoiceClient | None = None
    if region and voice_channel.rtc_region != region:
        if message:
            reply_content = message.content + f"\n... 尝试切换到 {region} 节点\n"
            message = await message.edit(content=reply_content)
        LOG.warning(f"Switching voice channel region to {region}")
        await voice_channel.edit(rtc_region=region)

    if voice_channel.guild.voice_client:
        await voice_channel.guild.voice_client.disconnect()
        await asyncio.sleep(1.0)
    LOG.info(f"Voice channel connection attempt 0/{retry}")
    vc = await voice_channel.connect(timeout=10, reconnect=True)
    if vc and vc.is_connected():
        LOG.info("Voice channel connected successfully")
        return vc, message

    for i in range(retry):
        try:
            if voice_channel.guild.voice_client:
                await voice_channel.guild.voice_client.disconnect()
                await asyncio.sleep(1.0)
            LOG.info(f"Voice channel connection attempt {i+1}/{retry}")
            vc = await voice_channel.connect(timeout=10, reconnect=True)
            if vc and vc.is_connected():
                LOG.info("Voice channel connected successfully")
                return vc, message
        except Exception as e:
            LOG.error(f"连接失败 (第 {i+1} 次)：{e}")
            await asyncio.sleep(1)

    if message:
        reply_content = message.content + "\n❌... 语音连接失败"
        message = await message.edit(content=reply_content)
    return None, message