import openai

from ifixai.providers.base import (
    ChatProvider,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from ifixai.core.types import ChatMessage, ProviderConfig

DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(ChatProvider):

    def __init__(self) -> None:
        pass

    async def send_message(
        self,
        messages: list[ChatMessage],
        config: ProviderConfig,
    ) -> str:
        model = config.model or DEFAULT_MODEL
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        endpoint = config.endpoint or "https://api.openai.com/v1"

        async with openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.endpoint,
            timeout=float(config.timeout),
            max_retries=config.max_retries,
        ) as client:
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=formatted_messages,  # type: ignore[arg-type]
                )

                choices = response.choices
                if not choices:
                    raise ProviderResponseError(
                        provider="openai",
                        endpoint=endpoint,
                        details=f"No choices in response (id={response.id})",
                    )
                choice = choices[0]
                finish_reason = choice.finish_reason or "unknown"
                if choice.message is None:
                    raise ProviderResponseError(
                        provider="openai",
                        endpoint=endpoint,
                        details=f"Missing message in choice (finish_reason={finish_reason})",
                    )
                content = choice.message.content
                if not content:
                    raise ProviderResponseError(
                        provider="openai",
                        endpoint=endpoint,
                        details=f"Empty content in response (finish_reason={finish_reason})",
                    )
                return content

            except openai.AuthenticationError as exc:
                raise ProviderAuthError(
                    provider="openai",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except openai.RateLimitError as exc:
                raise ProviderRateLimitError(
                    provider="openai",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except openai.APIConnectionError as exc:
                raise ProviderConnectionError(
                    provider="openai",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except openai.APITimeoutError as exc:
                raise ProviderTimeoutError(
                    provider="openai",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
            except openai.APIError as exc:
                raise ProviderResponseError(
                    provider="openai",
                    endpoint=endpoint,
                    details=str(exc),
                ) from exc
