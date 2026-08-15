from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import Article


class BaseCollector(ABC):
    @abstractmethod
    def collect(self) -> list[Article]:
        raise NotImplementedError

