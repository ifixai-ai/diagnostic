import secrets


def resolve_seed(value: int | None) -> tuple[int, bool]:
    if value is None:
        return secrets.randbelow(2**31 - 1) + 1, False
    return value, True
