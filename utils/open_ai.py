import os
import tempfile
import httpx

from openai import OpenAI, AsyncOpenAI


client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
a_client = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY_TRANSLATE"))


def gpt_tts_f(text, voice: str, ins: str, speed: float):
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
        print("TTS API 请求超时")
        return None


async def gpt_chat(prompt: str) -> str:
    """
    异步调用 OpenAI GPT API 进行对话，输入 prompt，返回 response 字符串
    """
    try:
        response = await a_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.7,
            timeout=10
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Chat API 请求失败: {e}")
        return ""


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
