import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum

from ifixai.core.types import (
    AuditRecord,
    ChatMessage,
    ConfigurationVersion,
    GroundingReport,
    OverrideReceipt,
    Permission,
    ProviderCapabilities,
    ProviderConfig,
    RetrievedSource,
    Role,
    RoutingDecision,
    ToolInfo,
    ToolInvocationResult,
)


class ProviderCapability(str, Enum):
    TOOL_CALLING = "tool_calling"
    RETRIEVAL = "retrieval"
    AUDIT_TRAIL = "audit_trail"
    ROUTING = "routing"
    GROUNDING = "grounding"
    AUTHORIZATION = "authorization"
    GOVERNANCE_ARCHITECTURE = "governance_architecture"
    OVERRIDE_MECHANISM = "override_mechanism"
    RATE_LIMIT_OBSERVABILITY = "rate_limit_observability"
    CONFIGURATION_VERSIONING = "configuration_versioning"

_logger = logging.getLogger(__name__)

_CAPABILITY_INSPECTION_EXPECTED_ERRORS: tuple[type[BaseException], ...] = (
    NotImplementedError,
    AttributeError,
    ConnectionError,
    OSError,
    asyncio.TimeoutError,
    ValueError,
    TypeError,
    RuntimeError,
)


class ProviderError(Exception):

    def __init__(
        self,
        provider: str = "",
        endpoint: str = "",
        details: str = "",
    ) -> None:
        self.provider = provider
        self.endpoint = endpoint
        self.details = details
        super().__init__(
            f"[{provider}] {details} (endpoint: {endpoint})"
        )

class ProviderConnectionError(ProviderError):
    pass

class ProviderAuthError(ProviderError):
    pass

class ProviderRateLimitError(ProviderError):
    pass

class ProviderTimeoutError(ProviderError):
    pass

class ProviderResponseError(ProviderError):
    pass

class ChatProvider(ABC):
    surfaces_rate_limit_errors: bool = True

    @abstractmethod
    async def send_message(
        self,
        messages: list[ChatMessage],
        config: ProviderConfig,
    ) -> str:
        ...

    async def list_tools(
        self,
        config: ProviderConfig,
    ) -> list[ToolInfo] | None:
        return None

    async def invoke_tool(
        self,
        tool_id: str,
        user_role: str,
        params: dict,
        config: ProviderConfig,
    ) -> ToolInvocationResult | None:
        return None

    async def retrieve_sources(
        self,
        query: str,
        config: ProviderConfig,
    ) -> list[RetrievedSource] | None:
        return None

    async def get_audit_trail(
        self,
        request_id: str,
        config: ProviderConfig,
    ) -> list[AuditRecord] | None:
        return None

    async def get_routing_decision(
        self,
        config: ProviderConfig,
    ) -> RoutingDecision | None:
        return None

    async def get_grounding_report(
        self,
        config: ProviderConfig,
    ) -> GroundingReport | None:
        return None

    async def authorize_tool(
        self,
        tool_id: str,
        user_role: str,
        config: ProviderConfig,
    ) -> ToolInvocationResult | None:
        return None

    async def get_governance_architecture(
        self,
        config: ProviderConfig,
    ) -> dict | None:
        return None

    async def apply_override(
        self,
        request_id: str,
        config: ProviderConfig,
        intent: str | None = None,
    ) -> OverrideReceipt | None:
        return None

    async def get_configuration_version(
        self,
        config: ProviderConfig,
    ) -> ConfigurationVersion | None:
        return None

    async def get_roles(
        self,
        config: ProviderConfig,
    ) -> list[Role] | None:
        return None

    async def get_permission_matrix(
        self,
        config: ProviderConfig,
    ) -> list[Permission] | None:
        return None

_CAPABILITY_PROBE_TIMEOUT: float = 5.0


async def _probe_capability(coro: object, provider_name: str, name: str) -> object:
    try:
        return await asyncio.wait_for(coro, timeout=_CAPABILITY_PROBE_TIMEOUT)  # type: ignore[arg-type]
    except (asyncio.TimeoutError, *_CAPABILITY_INSPECTION_EXPECTED_ERRORS):
        _logger.exception("Capability probe %s failed for %s", name, provider_name)
        return None


async def detect_capabilities(
    provider: ChatProvider,
    config: ProviderConfig,
) -> ProviderCapabilities:
    provider_name = type(provider).__name__
    p = lambda coro, name: _probe_capability(coro, provider_name, name)  # noqa: E731

    caps = {
        "has_tool_calling": await p(provider.list_tools(config), "list_tools") is not None,
        "has_retrieval": await p(provider.retrieve_sources("test", config), "retrieve_sources") is not None,
        "has_audit_trail": await p(provider.get_audit_trail("test", config), "get_audit_trail") is not None,
        "has_routing": await p(provider.get_routing_decision(config), "get_routing_decision") is not None,
        "has_grounding": await p(provider.get_grounding_report(config), "get_grounding_report") is not None,
        "has_authorization": await p(provider.authorize_tool("_test", "_test", config), "authorize_tool") is not None,
        "has_governance_architecture": await p(provider.get_governance_architecture(config), "get_governance_architecture") is not None,
        "has_override_mechanism": await p(provider.apply_override("_capability_inspection", config), "apply_override") is not None,
        "has_configuration_versioning": await p(provider.get_configuration_version(config), "get_configuration_version") is not None,
        "has_rate_limit_observability": bool(getattr(provider, "surfaces_rate_limit_errors", False)),
    }

    return ProviderCapabilities(**caps)
