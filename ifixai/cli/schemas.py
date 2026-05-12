from typing import TypedDict


class EvalModeResolution(TypedDict):
    mode: str
    auto_selected_judge: str | None


class InteractiveConfig(TypedDict):
    provider: str
    api_key: str
    endpoint: str | None
    model: str | None
