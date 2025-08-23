from typing import Any
from dataclasses import dataclass

from discord import Emoji, PartialEmoji, Message


@dataclass
class QueueMessage:
    msg_type: str
    message: Message | None
    user_id: int
    user_name: str
    reaction_target_user_name: str | None
    reaction_emoji: Emoji | PartialEmoji | str | None
