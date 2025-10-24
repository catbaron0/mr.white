from enum import Enum


class NewGameSignal(Enum):
    JOIN_BUTTON_CLICKED = "new_game:join_button:clicked"
    START_BUTTON_CLICKED = "new_game:start_button:clicked"


class RollSignal(Enum):
    CHOICE_CLICKED = [f"roll:choice_button_{i}:clicked" for i in range(21)]
    CHOICE_SELECTED = [f"roll:choice_button_{i}:selected" for i in range(21)]
    CHOICE_UNSELECTED = [f"roll:choice_button_{i}:unselected" for i in range(21)]
    NEXT_ROLL_BUTTON_CLICKED = "roll:next_roll:clicked"
    SCORE_SUBMITED = "roll:submit_score:clicked"
    SELECTION_UPDATED = "roll:selection|updated"
