import os
import tempfile
import httpx
import logging
import asyncio

from openai import OpenAI, AsyncOpenAI


client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
a_client = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY_TRANSLATE"))
LOG = logging.getLogger(__name__)


def gpt_tts_f(text, voice_cfg):
    voice = voice_cfg["voice"]
    ins = voice_cfg.get("ins", "沉稳的")
    speed = voice_cfg.get("speed", 2.0)
    temp_mp3_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        response = client.audio.speech.create(
          model="gpt-4o-mini-tts",
          voice=voice.lower(),
          input=text,
          speed=speed,
          instructions=ins
        )
        response.stream_to_file(temp_mp3_path.name)
        return temp_mp3_path.name
    except httpx.TimeoutException:
        LOG.error("TTS API 请求超时")
        return None


async def gpt_chat(prompt: str) -> str:
    """
    异步调用 OpenAI GPT API 进行对话，输入 prompt，返回 response 字符串
    """
    try:
        response = await a_client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            timeout=10
        )
        return response.output_text.strip()
    except Exception as e:
        LOG.error(f"Chat API 请求失败: {e}")
        return ""


async def describe_image(url: str) -> str:
    """
    输入图片 URL，返回图片的简短描述。
    """
    response = await a_client.chat.completions.create(
        model="gpt-4o-mini",  # 也可用 gpt-4o
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请用一句中文简要描述这张图片。"},
                    {"type": "image_url", "image_url": {"url": url}}
                ],
            }
        ],
    )
    return response.choices[0].message.content.strip()


async def gpt_summary(prompt: str) -> str:
    command = "先说这段文字看起来像是什么题材，然简短地总结一下。\n"
    command += "题材描述：这好像是一首诗/应该是出自一本书的节选/好像是一段歌词/看起来像是政府报告。\n" 
    command += "不需要格式化输出，语言要自然并且尽量简短。\n" 
    command += "文字如下：\n\n"
    command += prompt
    return await gpt_chat(command)


async def gpt_translate_to_zh(text: str) -> str:
    """
    异步调用 OpenAI GPT API 进行推文翻译，输入 text，返回翻译后的字符串
    """
    prompt = (
        "请将下面的内容翻译为中文。\n"
        "注意：\n"
        "1. 保持原文的格式\n"
        "2. 只输出翻译后的内容\n\n"
        "原文:\n"
    )
    prompt += text
    return await gpt_chat(prompt)


async def gpt_intro(text: str) -> str:
    """
    异步调用 OpenAI GPT API 进行推文翻译，输入 text，返回翻译后的字符串
    """
    prompt = (
        f"什么是 [{text}]。\n"
        "介绍要适当的简洁易懂\n"
        "不要提示后续对话\n"
    )
    return await gpt_chat(prompt)

