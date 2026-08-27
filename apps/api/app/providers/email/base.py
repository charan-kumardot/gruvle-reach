from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailSendResult:
    success: bool
    provider_message_id: str = ""
    error: str = ""


class EmailProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def send(self, *, to: str, subject: str, html_body: str, text_body: str = "") -> EmailSendResult:
        ...
