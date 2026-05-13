

import asyncio

import anthropic

from ifixai.providers.base import (
    ChatProvider,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from ifixai.core.types import ChatMessage, ProviderConfig
from ifixai.providers.schemas import MessageSplit

DEFAULT_MODEL = "claude-sonnet-4-20250514"

INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0


class AnthropicProvider(ChatProvider):

    def __init__(self) -> None:
        pass

    async def send_message(
        self,
        messages: list[ChatMessage],
        config: ProviderConfig,
    ) -> str:
        client = anthropic.AsyncAnthropic(
            api_key=config.api_key,
            base_url=config.endpoint,
            timeout=float(config.timeout),
            max_retries=0,
        )

        model = config.model or DEFAULT_MODEL
        endpoint = config.endpoint or "https://api.anthropic.com"

        split = _split_system_and_messages(messages)
        system_text = split["system_text"]
        formatted_messages = split["messages"]

        attempts = config.max_retries + 1
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(attempts):
            try:
                kwargs: dict = {
                    "model": model,
                    "max_tokens": 4096,
                    "messages": formatted_messages,
                }
                if system_text:
                    kwargs["system"] = system_text

                response = await client.messages.create(**kwargs)

                content_blocks = response.content
                if not content_blocks:
                    raise ProviderResponseError(
                        provider="anthropic",
                        endpoint=endpoint,
                        details="Empty content in response",
                    )

                text_parts = [
                    block.text
                    for block in content_blocks
                    if block.type == "text"
                ]
                if not text_parts:
                    raise ProviderResponseError(
                        provider="anthropic",
                        endpoint=endpoint,
                        details="No text blocks in response",
                    )
                return "\n".join(text_parts)

            except anthropic.AuthenticationError as exc:
                raise ProviderAuthError(
                    provider="anthropic",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except anthropic.RateLimitError as exc:
                if attempt < attempts - 1:
                    await asyncio.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER
                    continue
                raise ProviderRateLimitError(
                    provider="anthropic",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except anthropic.APIConnectionError as exc:
                raise ProviderConnectionError(
                    provider="anthropic",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except anthropic.APITimeoutError as exc:
                raise ProviderTimeoutError(
                    provider="anthropic",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except anthropic.APIError as exc:
                raise ProviderResponseError(
                    provider="anthropic",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc

        raise ProviderRateLimitError(
            provider="anthropic",
            endpoint=endpoint,
            details="Exhausted all retry attempts",
        )


def _split_system_and_messages(
    messages: list[ChatMessage],
) -> MessageSplit:
    system_text = ""
    conversation: list[dict[str, str]] = []

    for msg in messages:
        if msg.role == "system":
            system_text = msg.content
        else:
            conversation.append({"role": msg.role, "content": msg.content})

    return MessageSplit(system_text=system_text, messages=conversation)
