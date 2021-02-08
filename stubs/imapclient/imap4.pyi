# Standard libraries.
import imaplib
import socket
import typing


class IMAP4WithTimeout(imaplib.IMAP4):

    def __init__(
        self, address: str, port: int, timeout: typing.Optional[float]
    ) -> None:
        ...

    host: str = ...
    port: int = ...
    sock: socket.socket = ...
    file: typing.Union[typing.IO[str], typing.IO[bytes]] = ...

    def open(
        self,
        host: str = ...,
        port: int = ...,
        timeout: typing.Optional[float] = ...
    ) -> None:
        ...
