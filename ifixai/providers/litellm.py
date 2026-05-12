"""LiteLLM provider for iFixAi.

Routes to 100+ LLM providers (OpenAI, Anthropic, Google, Azure, Bedrock,
Ollama, etc.) via the litellm SDK. No proxy server needed.

Install: pip install ifixai[litellm]

See https://docs.litellm.ai/docs/providers for all supported models.
"""

import litellm as _litellm

from ifixai.core.types import ChatMessage, ProviderConfig
from ifixai.providers.base import (
    ChatProvider,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)

DEFAULT_MODEL = "openai/gpt-4o"


class LiteLLMProvider(ChatProvider):
    def __init__(self) -> None:
        pass

    async def send_message(
        self,
        messages: list[ChatMessage],
        config: ProviderConfig,
    ) -> str:
        model = config.model or DEFAULT_MODEL
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        params = {
            "model": model,
            "messages": formatted_messages,
            "drop_params": True,
            "timeout": float(config.timeout),
        }
        if config.api_key:
            params["api_key"] = config.api_key
        if config.endpoint:
            params["api_base"] = config.endpoint

        try:
            response = await _litellm.acompletion(**params)

            content = response.choices[0].message.content
            if not content:
                raise ProviderResponseError(
                    provider="litellm",
                    endpoint=config.endpoint or "default",
                    details="Empty content in response",
                )
            return content

        except ProviderResponseError:
            raise
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                provider="litellm",
                endpoint=config.endpoint or "default",
                details=str(exc),
            ) from exc
        except ConnectionError as exc:
            raise ProviderConnectionError(
                provider="litellm",
                endpoint=config.endpoint or "default",
                details=str(exc),
            ) from exc
        except Exception as exc:
            raise ProviderResponseError(
                provider="litellm",
                endpoint=config.endpoint or "default",
                details=str(exc),
            ) from exc
