

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

DEFAULT_API_VERSION = "2024-10-21"


class AzureOpenAIProvider(ChatProvider):

    def __init__(
        self,
        api_version: str = DEFAULT_API_VERSION,
        azure_ad_token: str | None = None,
    ) -> None:
        self.api_version = api_version
        self.azure_ad_token = azure_ad_token

    async def send_message(
        self,
        messages: list[ChatMessage],
        config: ProviderConfig,
    ) -> str:
        if not config.endpoint:
            raise ProviderConnectionError(
                provider="azure",
                endpoint="",
                details=(
                    "Azure endpoint is required. "
                    "Set config.endpoint to your Azure OpenAI resource URL."
                ),
            )

        if not config.model:
            raise ProviderResponseError(
                provider="azure",
                endpoint=config.endpoint,
                details=(
                    "Azure deployment name (model) is required. "
                    "Set config.model to your Azure OpenAI deployment name."
                ),
            )

        client_kwargs: dict = {
            "azure_endpoint": config.endpoint,
            "api_version": self.api_version,
            "timeout": float(config.timeout),
            "max_retries": config.max_retries,
        }

        if self.azure_ad_token:
            client_kwargs["azure_ad_token"] = self.azure_ad_token
        else:
            client_kwargs["api_key"] = config.api_key

        client = openai.AsyncAzureOpenAI(**client_kwargs)

        formatted_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        try:
            response = await client.chat.completions.create(
                model=config.model,
                messages=formatted_messages,  # type: ignore[arg-type]
            )

            content = response.choices[0].message.content
            if not content:
                raise ProviderResponseError(
                    provider="azure",
                    endpoint=config.endpoint,
                    details="Empty content in response",
                )
            return content

        except openai.AuthenticationError as exc:
            raise ProviderAuthError(
                provider="azure",
                endpoint=config.endpoint,
                details=str(exc),
            ) from exc
        except openai.RateLimitError as exc:
            raise ProviderRateLimitError(
                provider="azure",
                endpoint=config.endpoint,
                details=str(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            raise ProviderConnectionError(
                provider="azure",
                endpoint=config.endpoint,
                details=str(exc),
            ) from exc
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(
                provider="azure",
                endpoint=config.endpoint,
                details=str(exc),
            ) from exc
        except openai.APIError as exc:
            raise ProviderResponseError(
                provider="azure",
                endpoint=config.endpoint,
                details=str(exc),
            ) from exc
