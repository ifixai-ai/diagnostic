import secrets


def generate_run_seed() -> int:
    return secrets.randbelow(2**31)
