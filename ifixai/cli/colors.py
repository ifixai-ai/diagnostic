from ifixai._version import VERSION as __version__


class Style:

    RESET = "\033[0m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"

def colored(text: str, color: str) -> str:
    return f"{color}{text}{Style.RESET}"

def bold(text: str) -> str:
    return colored(text, Style.BOLD)

def dim(text: str) -> str:
    return colored(text, Style.DIM)

def success(text: str) -> str:
    return colored(text, Style.BRIGHT_GREEN)

def error(text: str) -> str:
    return colored(text, Style.BRIGHT_RED)

def warning(text: str) -> str:
    return colored(text, Style.BRIGHT_YELLOW)

def info(text: str) -> str:
    return colored(text, Style.BRIGHT_CYAN)

def accent(text: str) -> str:
    return colored(text, Style.BRIGHT_MAGENTA)

def header(text: str) -> str:
    return colored(text, Style.BOLD + Style.BRIGHT_WHITE)

def print_banner():
    version_line = f"v{__version__}".ljust(57)
    banner = f"""
{Style.BRIGHT_CYAN}{Style.BOLD}
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   ██╗███████╗██╗██╗  ██╗ █████╗ ██╗                           ║
    ║   ██║██╔════╝██║╚██╗██╔╝██╔══██╗██║                           ║
    ║   ██║█████╗  ██║ ╚███╔╝ ███████║██║                           ║
    ║   ██║██╔══╝  ██║ ██╔██╗ ██╔══██║██║                           ║
    ║   ██║██║     ██║██╔╝ ██╗██║  ██║██║                           ║
    ║   ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝                           ║
    ║                                                               ║
    ║   {Style.BRIGHT_WHITE}Open-source AI governance diagnostics{Style.BRIGHT_CYAN}                     ║
    ║   {Style.DIM}{Style.CYAN}{version_line}{Style.RESET}{Style.BRIGHT_CYAN}{Style.BOLD} ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
{Style.RESET}"""
    print(banner)

def print_separator(char: str = "─", width: int = 65):
    print(f"  {Style.DIM}{char * width}{Style.RESET}")

def print_section_header(title: str):
    width = 65
    print()
    print(f"  {Style.BRIGHT_CYAN}{'─' * width}{Style.RESET}")
    print(f"  {Style.BOLD}{Style.BRIGHT_WHITE}  {title}{Style.RESET}")
    print(f"  {Style.BRIGHT_CYAN}{'─' * width}{Style.RESET}")
    print()

def print_menu_option(number: str, title: str, description: str):
    print(f"    {Style.BRIGHT_CYAN}{Style.BOLD}[{number}]{Style.RESET}  {Style.BOLD}{Style.WHITE}{title}{Style.RESET}")
    print(f"         {Style.DIM}{description}{Style.RESET}")
    print()

def print_status(label: str, value: str, color: str = Style.BRIGHT_GREEN):
    print(f"    {Style.DIM}{label}:{Style.RESET} {color}{value}{Style.RESET}")

def print_progress_bar(current: int, total: int, width: int = 40, label: str = ""):
    filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = (current / total * 100) if total > 0 else 0
    label_text = f" {label}" if label else ""
    print(
        f"\r    {Style.BRIGHT_CYAN}{bar}{Style.RESET} "
        f"{Style.BOLD}{pct:5.1f}%{Style.RESET}{label_text}",
        end="",
        flush=True,
    )
    if current >= total:
        print()  # newline when done

def print_result_badge(passing: bool) -> str:
    if passing:
        return f"{Style.BG_GREEN}{Style.BOLD}{Style.BLACK} PASS {Style.RESET}"
    else:
        return f"{Style.BG_RED}{Style.BOLD}{Style.WHITE} FAIL {Style.RESET}"

def print_score_bar(score: float, width: int = 30):
    filled = int(width * score)
    if score >= 0.9:
        color = Style.BRIGHT_GREEN
    elif score >= 0.7:
        color = Style.BRIGHT_YELLOW
    else:
        color = Style.BRIGHT_RED
    bar = "█" * filled + "░" * (width - filled)
    return f"{color}{bar}{Style.RESET} {Style.BOLD}{score:.1%}{Style.RESET}"

def prompt(text: str, default: str = "") -> str:
    default_hint = f" {Style.DIM}[{default}]{Style.RESET}" if default else ""
    try:
        value = input(f"    {Style.BRIGHT_CYAN}▸{Style.RESET} {text}{default_hint}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return value.strip() or default

def prompt_choice(text: str, choices: list[str], default: int = 1) -> int:
    for i, choice in enumerate(choices, 1):
        marker = f"{Style.BRIGHT_CYAN}●{Style.RESET}" if i == default else f"{Style.DIM}○{Style.RESET}"
        print(f"    {marker} {Style.BOLD}[{i}]{Style.RESET} {choice}")
    print()
    while True:
        raw = prompt(text, str(default))
        try:
            val = int(raw)
            if 1 <= val <= len(choices):
                return val
        except ValueError:
            pass
        print(f"    {Style.BRIGHT_RED}Please enter a number between 1 and {len(choices)}{Style.RESET}")

def prompt_yes_no(text: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = prompt(f"{text} ({hint})", "y" if default else "n")
    return raw.lower() in ("y", "yes", "1", "true")
