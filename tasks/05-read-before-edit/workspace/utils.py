def capitalize_words(text: str) -> str:
    return text.title()


def trim_spaces(text: str) -> str:
    return " ".join(text.split())


def reverse_string(text: str) -> str:
    return text[::-1]


def truncate(text: str, max_len: int) -> str:
    return text[:max_len] if len(text) > max_len else text


def count_words(text: str) -> int:
    return len(text.split())
