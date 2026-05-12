from typing import TypedDict


class MessageSplit(TypedDict):
    system_text: str
    messages: list[dict[str, str]]


class GeminiMessages(TypedDict):
    system_instruction: str
    contents: list[dict]


class ConversePayload(TypedDict):
    system_prompts: list[dict]
    messages: list[dict]
