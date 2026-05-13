from typing import TypedDict

from ifixai.providers.base import ChatProvider
from ifixai.core.types import ProviderConfig


class ClassifierComponents(TypedDict):
    provider: ChatProvider
    config: ProviderConfig
