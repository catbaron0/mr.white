import re
import random


def roll_dice(cmd) -> list[int]:
    if cmd.startswith("d"):
        cmd = "1" + cmd
    pattern = r'^\d+d\d+$'
    if not re.match(pattern, cmd):
        return []
    d1, d2 = map(int, cmd.split('d'))
    if d1 <= 0 or d2 <= 0:
        return []
    results = []
    for _ in range(d1):
        result = random.randint(1, d2)
        results.append(str(result))
    return results
