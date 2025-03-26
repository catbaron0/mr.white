import os
import tempfile

from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_TTS_KEY"))


def tts_f(text, voice: str, ins: str, speed: float):
    temp_mp3_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    response = client.audio.speech.create(
      model="gpt-4o-mini-tts",
      voice=voice.lower(),
      input=text,
      speed=speed,
      instructions=ins
    )
    response.stream_to_file(temp_mp3_path.name)
    return temp_mp3_path.name
