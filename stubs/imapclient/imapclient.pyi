from logging import LoggerAdapter
from six import binary_type
from typing import Any, Optional

# Standard libraries.
import collections
import imaplib
import socket
import ssl as _ssl
import types
import typing

# Internal modules.
from . import exceptions
from . import imap4
from . import tls

_T_co = typing.TypeVar('_T_co', covariant=True)

long = int
DELETED: bytes
SEEN: bytes
ANSWERED: bytes
FLAGGED: bytes
DRAFT: bytes
RECENT: bytes


class Namespace(tuple[typing.Optional[list[tuple[str, str]]]]):

    def __new__(
        cls, personal: typing.Optional[list[tuple[str, str]]],
        other: typing.Optional[list[tuple[str, str]]],
        shared: typing.Optional[list[tuple[str, str]]]
    ) -> typing.Any:
        ...

    personal: typing.Optional[list[tuple[str, str]]] = ...
    other: typing.Optional[list[tuple[str, str]]] = ...
    shared: typing.Optional[list[tuple[str, str]]] = ...


class SocketTimeout(
    collections.namedtuple('SocketTimeout', ['connect', 'read'])
):
    ...


class MailboxQuotaRoots:
    ...


class Quota:
    ...


class IMAPClient:
    Error = exceptions.IMAPClientError
    AbortError = exceptions.IMAPClientAbortError
    ReadOnlyError = exceptions.IMAPClientReadOnlyError
    host: str = ...
    port: int = ...
    ssl: bool = ...
    ssl_context: typing.Optional[_ssl.SSLContext] = ...
    stream: bool = ...
    use_uid: bool = ...
    folder_encode: bool = ...
    normalise_times: bool = ...
    _idle_tag: typing.Optional[bytes] = ...
    _imap: typing.Union[imaplib.IMAP4_stream, imap4.IMAP4WithTimeout,
                        tls.IMAP4_TLS]
    _sock: socket.socket = ...

    def __init__(
        self,
        host: str,
        port: typing.Optional[int] = ...,
        use_uid: bool = ...,
        ssl: bool = ...,
        stream: bool = ...,
        ssl_context: typing.Optional[_ssl.SSLContext] = ...,
        timeout: typing.Union[None, float, SocketTimeout] = ...
    ) -> None:
        ...

    def __enter__(self: _T_co) -> _T_co:
        ...

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> None:
        ...

    def starttls(
        self,
        ssl_context: typing.Optional[_ssl.SSLContext] = ...
    ) -> str:
        ...

    def login(self, username: str, password: str) -> bytes:
        ...

    def oauth2_login(
        self,
        user: str,
        access_token: str,
        mech: str = ...,
        vendor: typing.Optional[str] = ...
    ) -> typing.Any:
        ...

    def oauthbearer_login(
        self, identity: Any, access_token: Any
    ) -> typing.Any:
        ...

    def plain_login(
        self,
        identity: Any,
        password: Any,
        authorization_identity: Optional[Any] = ...
    ) -> typing.Any:
        ...

    def sasl_login(
        self, mech_name: Any, mech_callable: Any
    ) -> typing.Any:
        ...

    def logout(self) -> typing.Any:
        ...

    def shutdown(self) -> None:
        ...

    def enable(self, *capabilities: Any) -> typing.Any:
        ...

    def id_(self, parameters: Optional[Any] = ...) -> typing.Any:
        ...

    def capabilities(self) -> typing.Any:
        ...

    def has_capability(self, capability: Any) -> typing.Any:
        ...

    def namespace(self) -> typing.Any:
        ...

    def list_folders(
        self, directory: str = ..., pattern: str = ...
    ) -> typing.Any:
        ...

    def xlist_folders(
        self, directory: str = ..., pattern: str = ...
    ) -> typing.Any:
        ...

    def list_sub_folders(
        self, directory: str = ..., pattern: str = ...
    ) -> typing.Any:
        ...

    def find_special_folder(self, folder_flag: Any) -> typing.Any:
        ...

    def select_folder(
        self, folder: Any, readonly: bool = ...
    ) -> typing.Any:
        ...

    def unselect_folder(self) -> typing.Any:
        ...

    def noop(self) -> typing.Any:
        ...

    def idle(self) -> None:
        ...

    def idle_check(self, timeout: Optional[Any] = ...) -> typing.Any:
        ...

    def idle_done(self) -> typing.Any:
        ...

    def folder_status(
        self, folder: Any, what: Optional[Any] = ...
    ) -> typing.Any:
        ...

    def close_folder(self) -> typing.Any:
        ...

    def create_folder(self, folder: Any) -> typing.Any:
        ...

    def rename_folder(self, old_name: Any, new_name: Any) -> typing.Any:
        ...

    def delete_folder(self, folder: Any) -> typing.Any:
        ...

    def folder_exists(self, folder: Any) -> typing.Any:
        ...

    def subscribe_folder(self, folder: Any) -> typing.Any:
        ...

    def unsubscribe_folder(self, folder: Any) -> typing.Any:
        ...

    def search(
        self,
        criteria: str = ...,
        charset: Optional[Any] = ...
    ) -> typing.Any:
        ...

    def gmail_search(self, query: Any, charset: str = ...) -> typing.Any:
        ...

    def sort(
        self,
        sort_criteria: Any,
        criteria: str = ...,
        charset: str = ...
    ) -> typing.Any:
        ...

    def thread(
        self,
        algorithm: str = ...,
        criteria: str = ...,
        charset: str = ...
    ) -> typing.Any:
        ...

    def get_flags(self, messages: Any) -> typing.Any:
        ...

    def add_flags(
        self,
        messages: Any,
        flags: Any,
        silent: bool = ...
    ) -> typing.Any:
        ...

    def remove_flags(
        self,
        messages: Any,
        flags: Any,
        silent: bool = ...
    ) -> typing.Any:
        ...

    def set_flags(
        self,
        messages: Any,
        flags: Any,
        silent: bool = ...
    ) -> typing.Any:
        ...

    def get_gmail_labels(self, messages: Any) -> typing.Any:
        ...

    def add_gmail_labels(
        self,
        messages: Any,
        labels: Any,
        silent: bool = ...
    ) -> typing.Any:
        ...

    def remove_gmail_labels(
        self,
        messages: Any,
        labels: Any,
        silent: bool = ...
    ) -> typing.Any:
        ...

    def set_gmail_labels(
        self,
        messages: Any,
        labels: Any,
        silent: bool = ...
    ) -> typing.Any:
        ...

    def delete_messages(
        self, messages: Any, silent: bool = ...
    ) -> typing.Any:
        ...

    def fetch(
        self,
        messages: Any,
        data: Any,
        modifiers: Optional[Any] = ...
    ) -> typing.Any:
        ...

    def append(
        self,
        folder: Any,
        msg: Any,
        flags: Any = ...,
        msg_time: Optional[Any] = ...
    ) -> typing.Any:
        ...

    def multiappend(self, folder: Any, msgs: Any) -> typing.Any:
        ...

    def copy(self, messages: Any, folder: Any) -> typing.Any:
        ...

    def move(self, messages: Any, folder: Any) -> typing.Any:
        ...

    def expunge(self, messages: Optional[Any] = ...) -> typing.Any:
        ...

    def getacl(self, folder: Any) -> typing.Any:
        ...

    def setacl(self, folder: Any, who: Any, what: Any) -> typing.Any:
        ...

    def get_quota(self, mailbox: str = ...) -> typing.Any:
        ...

    def get_quota_root(self, mailbox: Any) -> typing.Any:
        ...

    def set_quota(self, quotas: Any) -> typing.Any:
        ...

    @property
    def welcome(self) -> typing.Any:
        ...


class _literal(bytes):
    ...


class _quoted(binary_type):

    @classmethod
    def maybe(cls, original: Any) -> typing.Any:
        ...


class _dict_bytes_normaliser:

    def __init__(self, d: Any) -> None:
        ...

    def iteritems(self) -> None:
        ...

    items: Any = ...

    def __contains__(self, ink: Any) -> typing.Any:
        ...

    def get(self, ink: Any, default: Any = ...) -> typing.Any:
        ...

    def pop(self, ink: Any, default: Any = ...) -> typing.Any:
        ...


class IMAPlibLoggerAdapter(LoggerAdapter):

    def process(self, msg: Any, kwargs: Any) -> typing.Any:
        ...
