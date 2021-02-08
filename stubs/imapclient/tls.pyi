# Standard libraries.
import imaplib
import typing


def wrap_socket(
    sock: typing.Any, ssl_context: typing.Any, host: typing.Any
) -> typing.Any:
    ...


class IMAP4_TLS(imaplib.IMAP4):
    ssl_context: typing.Any = ...

    def __init__(
        self,
        host: typing.Any,
        port: typing.Any,
        ssl_context: typing.Any,
        timeout: typing.Optional[typing.Any] = ...
    ) -> None:
        ...

    host: typing.Any = ...
    port: typing.Any = ...
    sock: typing.Any = ...
    file: typing.Any = ...

    def open(  # type: ignore[override]
        self,
        host: str,
        port: int = ...,
        timeout: typing.Optional[float] = ...
    ) -> None:
        ...

    def read(self, size: typing.Any) -> typing.Any:
        ...

    def readline(self) -> typing.Any:
        ...

    def send(self, data: typing.Any) -> None:
        ...

    def shutdown(self) -> None:
        ...
