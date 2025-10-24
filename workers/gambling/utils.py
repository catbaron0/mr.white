DICE_FACE_COUNT = 6


def score_1_or_5(roll: list[int], num: int) -> list[dict]:
    base_scores = 100 if num == 1 else 50
    results = []
    count = roll.count(num)

    if count >= 1:
        score = base_scores
        results.append({"score": score, "remove": [num]})
    if count >= 3:
        score = base_scores * 10
        results.append({"score": score, "remove": [num] * 3})
    if count >= 4:
        score = base_scores * 20
        results.append({"score": score, "remove": [num] * 4})
    if count >= 5:
        score = base_scores * 40
        results.append({"score": score, "remove": [num] * 5})
    if count >= 6:
        score = base_scores * 80
        results.append({"score": score, "remove": [num] * 6})
    return results


def score_2_to_6(roll: list[int], num: int) -> list[dict]:
    results = []
    count = roll.count(num)

    if count >= 3:
        score = num * 100
        results.append({"score": score, "remove": [num] * 3})
    if count >= 4:
        score = num * 200
        results.append({"score": score, "remove": [num] * 4})
    if count == 5:
        score = num * 400
        results.append({"score": score, "remove": [num] * 5})
    if count == 6:
        score = num * 800
        results.append({"score": score, "remove": [num] * 6})
    return results


def score_straights(roll: list[int]) -> list[dict]:
    results = []
    unique_roll = set(roll)

    # 检查顺子12345
    if all(num in unique_roll for num in range(1, DICE_FACE_COUNT)):
        results.append({"score": 500, "remove": [1, 2, 3, 4, 5]})

    # 检查顺子23456
    if all(num in unique_roll for num in range(2, DICE_FACE_COUNT + 1)):
        results.append({"score": 750, "remove": [2, 3, 4, 5, 6]})

    # 检查大顺子123456
    if all(num in unique_roll for num in range(1, DICE_FACE_COUNT + 1)):
        results.append({"score": 1500, "remove": [1, 2, 3, 4, 5, 6]})

    return results


def compute_score(roll: list[int]) -> list[dict]:
    results = []

    results += score_1_or_5(roll, 1)
    results += score_1_or_5(roll, 5)
    for num in [2, 3, 4, 6]:
        results += score_2_to_6(roll, num)
    results += score_straights(roll)
    for i in range(len(results)):
        results[i]["is_selected"] = False
    return results
