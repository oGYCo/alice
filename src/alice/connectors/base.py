from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas.content import RawContentSchema
from ..schemas.source import SourceConfigSchema


class BaseConnector(ABC):
    @abstractmethod
    async def fetch(self, config: SourceConfigSchema) -> list[RawContentSchema]:
        raise NotImplementedError
