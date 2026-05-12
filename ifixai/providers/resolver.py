
from pathlib import Path
from typing import Mapping, Union

from ifixai.providers.http import HttpProvider
from ifixai.providers.langchain import LangChainProvider
from ifixai.providers.governance_fixture import GovernanceFixture
from ifixai.providers.governance_mixin import GovernanceMixin
from ifixai.providers.mock_governance import MockGovernanceProvider

try:
    from ifixai.providers.anthropic import AnthropicProvider
except ImportError:
    AnthropicProvider = None

try:
    from ifixai.providers.azure import AzureOpenAIProvider
except ImportError:
    AzureOpenAIProvider = None

try:
    from ifixai.providers.bedrock import BedrockProvider
except ImportError:
    BedrockProvider = None

try:
    from ifixai.providers.gemini import GeminiProvider
except ImportError:
    GeminiProvider = None

try:
    from ifixai.providers.huggingface import HuggingFaceProvider
except ImportError:
    HuggingFaceProvider = None

try:
    from ifixai.providers.openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None

try:
    from ifixai.providers.openrouter import OpenRouterProvider
except ImportError:
    OpenRouterProvider = None

try:
    from ifixai.providers.litellm import LiteLLMProvider
except ImportError:
    LiteLLMProvider = None


REGISTERED_PROVIDERS: tuple[str, ...] = (
    "http",
    "mock",
    "openai",
    "openrouter",
    "anthropic",
    "gemini",
    "azure",
    "bedrock",
    "huggingface",
    "langchain",
    "litellm",
)

_MOCK_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "governance" / "mock.yaml"

_PROVIDER_MAP: dict[str, type] = {
    name: cls
    for name, cls in {
        "http": HttpProvider,
        "openai": OpenAIProvider,
        "openrouter": OpenRouterProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "azure": AzureOpenAIProvider,
        "bedrock": BedrockProvider,
        "huggingface": HuggingFaceProvider,
        "langchain": LangChainProvider,
        "litellm": LiteLLMProvider,
    }.items()
    if cls is not None
}


_GOVERNED_CLASS_CACHE: dict[type, type] = {}


def wrap_with_governance(
    provider: object,
    governance: GovernanceFixture,
) -> object:
    """Compose `GovernanceMixin` onto a live provider instance.

    Synthesizes a subclass `(GovernanceMixin, OriginalCls)` per original
    class (cached) and rebinds the instance's `__class__` so every
    structural hook now reads from `governance` instead of returning
    `None`. The provider's own state (HTTP clients, credentials,
    capability flags) is preserved untouched.
    """
    if isinstance(provider, GovernanceMixin):
        provider._governance = governance
        return provider

    original_cls = type(provider)
    governed_cls = _GOVERNED_CLASS_CACHE.get(original_cls)
    if governed_cls is None:
        governed_cls = type(
            f"Governed{original_cls.__name__}",
            (GovernanceMixin, original_cls),
            {},
        )
        _GOVERNED_CLASS_CACHE[original_cls] = governed_cls
    provider.__class__ = governed_cls
    provider._governance = governance
    return provider


def resolve_provider(provider: Union[str, object]) -> object:
    if not isinstance(provider, str):
        return provider

    name = provider.lower()
    if name == "mock":
        governance = GovernanceFixture.load(str(_MOCK_FIXTURE_PATH))
        return MockGovernanceProvider(governance=governance)

    provider_class = _PROVIDER_MAP.get(name)
    if provider_class is None:
        if name in REGISTERED_PROVIDERS:
            raise ValueError(
                f"Provider '{name}' requires its SDK. "
                f"Install it with: pip install ifixai[{name}]"
            )
        raise ValueError(
            f"Unknown provider: '{name}'. Available: {list(_PROVIDER_MAP.keys())}"
        )
    return provider_class()


_PROVIDER_CREDENTIAL_ENV_VARS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "azure": ("AZURE_OPENAI_API_KEY",),
    "bedrock": ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"),
    "huggingface": ("HUGGINGFACE_API_TOKEN", "HF_TOKEN"),
    "openrouter": ("OPENROUTER_API_KEY",),
    "litellm": ("LITELLM_API_KEY",),
}

_JUDGE_PREFERENCE_ORDER: tuple[str, ...] = (
    "anthropic",
    "openai",
    "gemini",
    "openrouter",
    "azure",
    "bedrock",
    "huggingface",
)


def detect_available_credentials(environ: Mapping[str, str]) -> list[str]:
    available: list[str] = []
    for provider_name, env_vars in _PROVIDER_CREDENTIAL_ENV_VARS.items():
        if any(environ.get(var) for var in env_vars):
            available.append(provider_name)
    return available


def select_cross_provider_judge(
    sut_provider: str,
    available: list[str],
) -> str | None:
    sut_normalised = sut_provider.lower()
    for candidate in _JUDGE_PREFERENCE_ORDER:
        if candidate in available and candidate != sut_normalised:
            return candidate
    return None
