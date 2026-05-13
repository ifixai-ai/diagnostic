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

DEFAULT_MODEL = "openai/gpt-4o"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(ChatProvider):

    async def send_message(
        self,
        messages: list[ChatMessage],
        config: ProviderConfig,
    ) -> str:
        base_url = config.endpoint or DEFAULT_BASE_URL
        model = config.model or DEFAULT_MODEL
        formatted = [{"role": m.role, "content": m.content} for m in messages]

        async with openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=base_url,
            timeout=float(config.timeout),
            max_retries=config.max_retries,
        ) as client:
            try:
                create_kwargs: dict = {
                    "model": model,
                    "messages": formatted,  # type: ignore[arg-type]
                }
                if config.max_tokens is not None:
                    create_kwargs["max_tokens"] = config.max_tokens
                response = await client.chat.completions.create(**create_kwargs)
                choices = response.choices
                if not choices:
                    raise ProviderResponseError(
                        provider="openrouter",
                        endpoint=base_url,
                        details=f"No choices in response (id={response.id})",
                    )
                choice = choices[0]
                finish_reason = choice.finish_reason or "unknown"
                if choice.message is None:
                    raise ProviderResponseError(
                        provider="openrouter",
                        endpoint=base_url,
                        details=f"Missing message in choice (finish_reason={finish_reason})",
                    )
                content = choice.message.content
                if not content:
                    raise ProviderResponseError(
                        provider="openrouter",
                        endpoint=base_url,
                        details=f"Empty content in response (finish_reason={finish_reason})",
                    )
                return content
            except openai.AuthenticationError as exc:
                raise ProviderAuthError(
                    provider="openrouter", endpoint=base_url, details=str(exc)
                ) from exc
            except openai.RateLimitError as exc:
                raise ProviderRateLimitError(
                    provider="openrouter", endpoint=base_url, details=str(exc)
                ) from exc
            except openai.APITimeoutError as exc:
                raise ProviderTimeoutError(
                    provider="openrouter", endpoint=base_url, details=str(exc)
                ) from exc
            except openai.APIConnectionError as exc:
                raise ProviderConnectionError(
                    provider="openrouter", endpoint=base_url, details=str(exc)
                ) from exc
            except openai.APIError as exc:
                raise ProviderResponseError(
                    provider="openrouter", endpoint=base_url, details=str(exc)
                ) from exc
