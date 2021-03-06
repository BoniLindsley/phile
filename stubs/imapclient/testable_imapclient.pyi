from .imapclient import IMAPClient as IMAPClient
from mock import Mock
from typing import Any

class TestableIMAPClient(IMAPClient):
    def __init__(self) -> None: ...

class MockIMAP4(Mock):
    use_uid: bool = ...
    sent: bytes = ...
    tagged_commands: Any = ...
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def send(self, data: Any) -> None: ...
