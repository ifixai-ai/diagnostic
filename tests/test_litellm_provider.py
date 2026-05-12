"""Tests for LiteLLM provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ifixai.core.types import ChatMessage, ProviderConfig
from ifixai.providers.base import (
    ChatProvider,
    ProviderResponseError,
    ProviderTimeoutError,
)
from ifixai.providers.litellm import LiteLLMProvider


def _make_config(**overrides):
    defaults = {
        "provider": "litellm",
        "model": "openai/gpt-4o",
        "api_key": "sk-test",
    }
    defaults.update(overrides)
    return ProviderConfig(**defaults)


class TestLiteLLMProviderInit:
    def test_extends_chat_provider(self):
        assert issubclass(LiteLLMProvider, ChatProvider)

    def test_instantiates_without_args(self):
        p = LiteLLMProvider()
        assert p is not None


class TestSendMessage:
    @pytest.mark.asyncio
    @patch("ifixai.providers.litellm._litellm")
    async def test_calls_acompletion_with_drop_params(self, mock_litellm):
        mock_msg = MagicMock(content="test response")
        mock_litellm.acompletion = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=mock_msg)])
        )

        p = LiteLLMProvider()
        config = _make_config()
        messages = [ChatMessage(role="user", content="hello")]
        result = await p.send_message(messages, config)

        assert result == "test response"
        kwargs = mock_litellm.acompletion.call_args.kwargs
        assert kwargs["drop_params"] is True
        assert kwargs["model"] == "openai/gpt-4o"
        assert kwargs["api_key"] == "sk-test"

    @pytest.mark.asyncio
    @patch("ifixai.providers.litellm._litellm")
    async def test_omits_api_key_when_empty(self, mock_litellm):
        mock_msg = MagicMock(content="ok")
        mock_litellm.acompletion = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=mock_msg)])
        )

        p = LiteLLMProvider()
        config = _make_config(api_key="")
        messages = [ChatMessage(role="user", content="hi")]
        await p.send_message(messages, config)

        kwargs = mock_litellm.acompletion.call_args.kwargs
        assert "api_key" not in kwargs

    @pytest.mark.asyncio
    @patch("ifixai.providers.litellm._litellm")
    async def test_formats_messages_correctly(self, mock_litellm):
        mock_msg = MagicMock(content="ok")
        mock_litellm.acompletion = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=mock_msg)])
        )

        p = LiteLLMProvider()
        config = _make_config()
        messages = [
            ChatMessage(role="system", content="be helpful"),
            ChatMessage(role="user", content="hi"),
        ]
        await p.send_message(messages, config)

        kwargs = mock_litellm.acompletion.call_args.kwargs
        assert kwargs["messages"] == [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hi"},
        ]

    @pytest.mark.asyncio
    @patch("ifixai.providers.litellm._litellm")
    async def test_uses_default_model_when_none(self, mock_litellm):
        mock_msg = MagicMock(content="ok")
        mock_litellm.acompletion = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=mock_msg)])
        )

        p = LiteLLMProvider()
        config = _make_config(model=None)
        messages = [ChatMessage(role="user", content="hi")]
        await p.send_message(messages, config)

        kwargs = mock_litellm.acompletion.call_args.kwargs
        assert kwargs["model"] == "openai/gpt-4o"


class TestEdgeCases:
    @pytest.mark.asyncio
    @patch("ifixai.providers.litellm._litellm")
    async def test_empty_content_raises_response_error(self, mock_litellm):
        mock_msg = MagicMock(content="")
        mock_litellm.acompletion = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=mock_msg)])
        )

        p = LiteLLMProvider()
        config = _make_config()
        messages = [ChatMessage(role="user", content="hi")]

        with pytest.raises(ProviderResponseError):
            await p.send_message(messages, config)

    @pytest.mark.asyncio
    @patch("ifixai.providers.litellm._litellm")
    async def test_api_error_raises_response_error(self, mock_litellm):
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("401 Unauthorized"))

        p = LiteLLMProvider()
        config = _make_config()
        messages = [ChatMessage(role="user", content="hi")]

        with pytest.raises(ProviderResponseError, match="401"):
            await p.send_message(messages, config)

    @pytest.mark.asyncio
    @patch("ifixai.providers.litellm._litellm")
    async def test_timeout_raises_timeout_error(self, mock_litellm):
        mock_litellm.acompletion = AsyncMock(side_effect=TimeoutError("timed out"))

        p = LiteLLMProvider()
        config = _make_config()
        messages = [ChatMessage(role="user", content="hi")]

        with pytest.raises(ProviderTimeoutError):
            await p.send_message(messages, config)


class TestResolver:
    def test_litellm_in_registered_providers(self):
        from ifixai.providers.resolver import REGISTERED_PROVIDERS

        assert "litellm" in REGISTERED_PROVIDERS

    def test_litellm_in_provider_map(self):
        from ifixai.providers.resolver import _PROVIDER_MAP

        assert "litellm" in _PROVIDER_MAP

    def test_resolve_litellm_returns_provider(self):
        from ifixai.providers.resolver import resolve_provider

        provider = resolve_provider("litellm")
        assert isinstance(provider, LiteLLMProvider)

    def test_litellm_in_credential_env_vars(self):
        from ifixai.providers.resolver import _PROVIDER_CREDENTIAL_ENV_VARS

        assert "litellm" in _PROVIDER_CREDENTIAL_ENV_VARS
