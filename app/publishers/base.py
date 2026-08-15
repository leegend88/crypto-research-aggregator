from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import Article


class BasePublisher(ABC):
    @abstractmethod
    def publish(self, article: Article) -> None:
        raise NotImplementedError

