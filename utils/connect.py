import logging

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
            reply_content = message.content + f"\n... 尝试切换到{region}节点\n"
            message = await message.edit(content=reply_content)
        LOG.error(f"Switching to {region}")
        await voice_channel.edit(rtc_region=region)

    region = voice_channel.rtc_region
    if message and region:
        reply_content = message.content + f"\n... 正在连接{region}节点\n"
        message = await message.edit(content=reply_content)
    LOG.info(f"Connecting to {region}")

    await voice_channel.edit(rtc_region=region)
    try:
        LOG.error("Connecting to voice channel")
        if voice_channel.guild.voice_client:
            await voice_channel.guild.voice_client.disconnect()
        vc = None
        for i in range(retry):
            LOG.info(f"Voice channel connection attempt {i+1}/{retry}")
            vc = await voice_channel.connect(timeout=10, reconnect=True)
            if vc and vc.is_connected():
                break
        return vc, message
    except Exception as e:
        if message:
            reply_content = message.content + "\n❌... 语音连接失败"
            message = await message.edit(content=reply_content)
        LOG.error(f"语音接失败：{e}")
        return None, message
