import subprocess
import tempfile
import os

import pyttsx3

def _tts_f(text: str) -> str:
    """将文本转换为语音并保存到临时文件，返回文件路径"""
    engine = pyttsx3.init(driverName='espeak')
    
    # 设置中文语音（Windows: Huihui, macOS: Ting-Ting）
    for voice in engine.getProperty("voices"):
        if "Huihui" in voice.name or "Ting-Ting" in voice.name:
            engine.setProperty("voice", voice.id)
            break

    engine.setProperty("rate", 150)  # 语速
    engine.setProperty("volume", 1.0)  # 音量

    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_path = temp_file.name
    temp_file.close()

    # 保存语音到临时文件
    engine.save_to_file(text, temp_path)
    engine.runAndWait()

    return temp_path


def tts_f(text):
    # 创建一个唯一的临时文件路径，后缀为 .aiff（macOS 支持的音频格式）
    temp_aiff_path = tempfile.mktemp(suffix='.aiff')
    temp_mp3_path = tempfile.mktemp(suffix='.mp3')

    # 使用 `say` 命令将文本转化为语音并保存到临时文件
    subprocess.run(['say', text, '-o', temp_aiff_path])

    # 使用 ffmpeg 将 .aiff 转换为 .mp3
    subprocess.run(["ffmpeg", "-y", "-i", temp_aiff_path, temp_mp3_path])  # 确保 `-y` 强制覆盖文件

    # 删除临时 .aiff 文件
    os.remove(temp_aiff_path)
    os.chmod(temp_mp3_path, 0o777)

    # 返回临时 .mp3 文件的路径
    return temp_mp3_path


if __name__ == "__main__":
    print(tts_f("test"))