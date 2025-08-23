from pathlib import Path
import json


CONFIG_PATH = Path(__file__).parent


def load_config(config_file: str | Path) -> dict:
    with open(config_file, "r") as f:
        return json.load(f)


def load_trans_channel() -> dict:
    return load_config(CONFIG_PATH / "translate_channel.json")


def load_emoji_dict() -> dict:
    return load_config(CONFIG_PATH / "emoji.json")


def load_guild_config(guild_id: str) -> dict:
    return load_config(CONFIG_PATH / "guild_config.json").get(guild_id, {})


def load_white_config() -> dict:
    return load_config(CONFIG_PATH / "global.json")
