import re


def process_content(text: str) -> str:
    return re.sub("@\d+", "那个谁", str)    


def process_user_name(text: str) -> str:
    return text.replace(
        "𝓈𝒾𝓇𝒾𝓈", "siris"
    ).replace(
        "𝚃𝙴𝙽𝚒", "teni"
    ).replace(
        "𝕃𝕖𝕥𝕠", "leto"
    ).replace(
        "ꩇׁׅ݊ᨵׁׅյׁׅᨵׁׅ ", "mojo"
    ).replace(
        "𝘣𝘭𝘶𝘦𝘺", "bluey"
    )
