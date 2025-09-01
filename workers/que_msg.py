from typing import Any
from dataclasses import dataclass

from discord import Emoji, PartialEmoji, Message, Member, User


@dataclass
class QueueMessage:
    msg_type: str
    message: Message | None
    user: Member | User
    reaction_target_user_name: str | None
    reaction_emoji: Emoji | PartialEmoji | str | None
