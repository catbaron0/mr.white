from pathlib import Path
import json


CONFIG_PATH = Path(__file__).parent


def load_config(config_file: str | Path) -> dict:
    with open(config_file, "r") as f:
        return json.load(f)


def load_username_config() -> dict:
    return load_config(CONFIG_PATH / "username.json")


def load_voices_config() -> dict:
    return load_config(CONFIG_PATH / "voices.json")


if __name__ == "__main__":
    print(load_voices_config())