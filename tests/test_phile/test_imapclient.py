#!/usr/bin/env python3

# Standard library.
import asyncio
import datetime
import imaplib
import socket
import ssl as _ssl
import types
import typing
import unittest
import unittest.mock

# External dependencies.
import imapclient

# Internal modules.
import phile.imapclient

_T_co = typing.TypeVar("_T_co", covariant=True)


class IMAP4Mock:

    abort = Exception
    error = Exception

    def __init__(
        self,
        host: str,
        port: int = 143,
        timeout: typing.Union[  # Stop formatting moving this.
            None, float, imapclient.SocketTimeout
        ] = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        del (host,)
        del port
        del timeout
        self.sock, self._server_socket = socket.socketpair()
        self.tagged_commands: (
            dict[bytes, typing.Optional[list[bytes]]]
        ) = {}

    def __del__(self) -> None:
        self.shutdown()
        getattr(super(), "__del__", lambda _: None)(self)

    def shutdown(self) -> None:
        try:
            self.sock.close()
        finally:
            self._server_socket.close()


class IMAPClientMock(unittest.mock.MagicMock):
    def __init__(
        self,
        host: str,
        port: typing.Optional[int] = None,
        use_uid: bool = True,
        ssl: bool = True,
        stream: bool = False,
        ssl_context: typing.Optional[_ssl.SSLContext] = None,
        timeout: typing.Union[  # Stop formatting moving this.
            None, float, imapclient.SocketTimeout
        ] = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if stream:
            assert port is None
            assert not ssl
        assert not stream, "Unable to mock it."
        if not stream and port is None:
            port = 993 if ssl else 143
        if ssl:
            assert port != 143
        self.host = host
        self.port = port
        self.ssl = ssl
        self.ssl_context = ssl_context
        self.stream = stream
        self.use_uid = use_uid
        self.folder_encode = True
        self.normalise_times = True
        if not isinstance(timeout, imapclient.SocketTimeout):
            timeout = imapclient.SocketTimeout(timeout, timeout)
        self._timeout = timeout
        self._starttls_done = False
        self._cached_capabilities = None
        self._idle_tag: typing.Optional[bytes] = None
        self._imap = self._create_IMAP4()
        self._set_read_timeout()

    def __enter__(self: _T_co) -> _T_co:
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
    ) -> None:
        self.shutdown()

    def login(self, username: str, password: str) -> bytes:
        del password
        del username
        return b""

    def _create_IMAP4(  # pylint: disable=invalid-name
        self,
    ) -> imaplib.IMAP4:
        assert isinstance(self.port, int)
        return imaplib.IMAP4(
            self.host, self.port, getattr(self._timeout, "connect", None)
        )

    def _set_read_timeout(self) -> None:
        if self._timeout is not None:
            self._sock.settimeout(self._timeout.read)

    @property
    def _sock(self) -> socket.socket:
        return self._imap.sock

    def idle(self) -> None:
        if self._idle_tag is None:
            self._idle_tag = b""
        assert isinstance(self._idle_tag, bytes)
        self._imap.tagged_commands[self._idle_tag] = []

    def idle_check(
        self, timeout: typing.Optional[float] = None
    ) -> list[typing.Any]:
        if self._sock.fileno() == -1:
            raise OSError()
        del timeout
        return []

    def idle_done(self) -> typing.Any:
        if self._sock.fileno() == -1:
            raise OSError()
        assert self._idle_tag is not None
        self._imap.tagged_commands.pop(self._idle_tag)
        return [None, [(0, b"")]]

    def logout(self) -> bytes:
        if self._sock.fileno() == -1:
            raise OSError()
        self.shutdown()
        return b""

    def shutdown(self) -> None:
        self._imap.shutdown()

    def select_folder(
        self, folder: str, readonly: bool = False
    ) -> phile.imapclient.SelectResponse:
        del folder
        del readonly
        select_response = {
            b"EXISTS": 0,
            b"FLAGS": tuple(),
            b"RECENT": 0,
        }
        return select_response


class PreparesIMAP4(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        patcher = unittest.mock.patch("imaplib.IMAP4", new=IMAP4Mock)
        self.addCleanup(patcher.stop)
        patcher.start()


class PreparesIMAPClient(PreparesIMAP4, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        patcher = unittest.mock.patch(
            "imapclient.IMAPClient", new=IMAPClientMock
        )
        self.addCleanup(patcher.stop)
        patcher.start()


class UsesIMAPClient(
    PreparesIMAPClient,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.imap_clients: list[IMAPClientMock]

    def setUp(self) -> None:
        super().setUp()
        self.imap_clients = imap_clients = []

        def create_imap_client(
            *args: typing.Any, **kwargs: typing.Any
        ) -> IMAPClientMock:
            new_client = IMAPClientMock(*args, **kwargs)
            imap_clients.append(new_client)
            return new_client

        patcher = unittest.mock.patch(
            "imapclient.IMAPClient", new=create_imap_client
        )
        self.addCleanup(patcher.stop)
        patcher.start()


class TestGetSocket(PreparesIMAPClient, unittest.TestCase):
    def test_retrieves_implementation_socket(self) -> None:
        imap_client = imapclient.IMAPClient(host="get_socket://")
        self.addCleanup(imap_client.shutdown)
        self.assertEqual(
            phile.imapclient.get_socket(imap_client),
            imap_client._imap.sock,  # pylint: disable=protected-access
        )


class TestIsIdle(PreparesIMAPClient, unittest.TestCase):
    def test_before_and_after_idle_state(self) -> None:
        imap_client = imapclient.IMAPClient(host="is_idle://")
        self.addCleanup(imap_client.shutdown)
        is_idle = phile.imapclient.is_idle
        self.assertFalse(is_idle(imap_client))
        imap_client.idle()
        self.assertTrue(is_idle(imap_client))
        imap_client.idle_done()
        self.assertFalse(is_idle(imap_client))


class TestFlagTracker(unittest.TestCase):
    def test_constructor_default(self) -> None:
        flag_tracker = phile.imapclient.FlagTracker()
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 0,
                "unknown": 0,
                "unseen": 0,
            },
        )

    def test_constructor_with_smallest_response(self) -> None:
        # This test constructs an :py:class:`~imap_notifier.IdleChecker`
        # using the smallest response as specified by the documentation
        # of :py:meth:`~imapclient.IMAPClient.select_folder`.
        # The response must contain the following keys:

        #   * `b'EXISTS'`,
        #   * `b'FLAGS'` and
        #   * `b'RECENT'`.

        # No messages in folder.
        select_response = {b"EXISTS": 0, b"FLAGS": (), b"RECENT": 0}
        flag_tracker = phile.imapclient.FlagTracker(select_response)

        self.assertDictEqual(
            flag_tracker.message_counts,
            {"total": 0, "unknown": 0, "unseen": 0},
        )

    def test_constructor_with_documentation_response(self) -> None:
        # This test constructs a tracker
        # using the example response from the documentation
        # of :py:meth:`~imapclient.IMAPClient.select_folder`.

        # Three messages in folder, with no unread.
        select_response = {
            b"EXISTS": 3,
            b"FLAGS": (
                b"\\Answered",
                b"\\Flagged",
                b"\\Deleted",
            ),
            b"RECENT": 0,
            b"PERMANENTFLAGS": (
                b"\\Answered",
                b"\\Flagged",
                b"\\Deleted",
            ),
            b"READ-WRITE": True,
            b"UIDNEXT": 11,
            b"UIDVALIDITY": 1239278212,
        }
        flag_tracker = phile.imapclient.FlagTracker(select_response)

        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 3,
                "unknown": 0,
                "unseen": 0,
            },
        )

    def test_create_using_response_with_unseen_messages(self) -> None:
        # The response
        # from :py:meth:`~imapclient.IMAPClient.select_folder`
        # can contain an entry indicating which messages are unread
        # in the selected folder.
        # This test whether that entry is respected.

        # Two messages in the folder, and second is unread.
        select_response = {
            b"EXISTS": 2,
            b"FLAGS": (),
            b"RECENT": 0,
            b"UNSEEN": [b"2"],
        }
        flag_tracker = phile.imapclient.FlagTracker(select_response)

        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 2,
                "unknown": 0,
                "unseen": 1,
            },
        )

    def test_select_empty_folder_after_non_empty_folder(self) -> None:
        # Two messages in the folder, and second is unread.
        select_response = {
            b"EXISTS": 2,
            b"FLAGS": (),
            b"RECENT": 0,
            b"UNSEEN": [b"2"],
        }
        flag_tracker = phile.imapclient.FlagTracker(select_response)

        # Reset it to zero messages.
        select_response = {
            b"EXISTS": 0,
            b"FLAGS": (),
            b"RECENT": 0,
        }
        flag_tracker.select(select_response)

        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 0,
                "unknown": 0,
                "unseen": 0,
            },
        )

    def test_add_with_untagged_expunge_response(self) -> None:
        # Two messages, second unseen.
        select_response = {
            b"EXISTS": 2,
            b"FLAGS": (),
            b"RECENT": 0,
            b"UNSEEN": [b"2"],
        }
        flag_tracker = phile.imapclient.FlagTracker(select_response)
        # The second message has been removed.
        flag_tracker.add([(2, b"EXPUNGE")])

        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 1,
                "unknown": 0,
                "unseen": 0,
            },
        )

    def test_fetch_can_flag_as_seen(self) -> None:
        select_response = {
            b"EXISTS": 3,
            b"FLAGS": (),
            b"RECENT": 0,
            b"UNSEEN": [b"1", b"2"],
        }
        flag_tracker = phile.imapclient.FlagTracker(select_response)
        flag_tracker.add([(2, b"FETCH", (b"FLAGS", (b"\\Seen")))])
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 3,
                "unknown": 0,
                "unseen": 1,
            },
        )

    def test_fetch_can_flag_as_unseen(self) -> None:
        select_response = {
            b"EXISTS": 3,
            b"FLAGS": (),
            b"RECENT": 0,
            b"UNSEEN": [b"1"],
        }
        flag_tracker = phile.imapclient.FlagTracker(select_response)
        flag_tracker.add([(2, b"FETCH", (b"FLAGS", ()))])
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 3,
                "unknown": 0,
                "unseen": 2,
            },
        )

    def test_fetch_does_nothing_without_flags(self) -> None:
        flag_tracker = phile.imapclient.FlagTracker()
        flag_tracker.add([(2, b"FETCH", ())])
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 0,
                "unknown": 0,
                "unseen": 0,
            },
        )

    def test_add__using_a_real_example(self) -> None:
        # This test uses an example response from real usage.
        # The selected folder contains three messages with one unread.
        # The unread message is moved out of the folder.
        # An empty response is then given as a special case.
        # After that, the message is moved back in, and marked as read.

        select_response = {
            b"PERMANENTFLAGS": (
                b"\\Seen",
                b"\\Answered",
                b"\\Flagged",
                b"\\Deleted",
                b"\\Draft",
                b"$MDNSent",
            ),
            b"EXISTS": 3,
            b"RECENT": 0,
            b"FLAGS": (
                b"\\Seen",
                b"\\Answered",
                b"\\Flagged",
                b"\\Deleted",
                b"\\Draft",
                b"$MDNSent",
            ),
            b"UNSEEN": [b"2"],
            b"UIDVALIDITY": 14,
            b"UIDNEXT": 16358,
            b"READ-WRITE": True,
        }
        flag_tracker = phile.imapclient.FlagTracker(select_response)
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 3,
                "unknown": 0,
                "unseen": 1,
            },
        )

        flag_tracker.add([])
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 3,
                "unknown": 0,
                "unseen": 1,
            },
        )

        flag_tracker.add([(2, b"EXPUNGE"), (2, b"EXISTS")])
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 2,
                "unknown": 0,
                "unseen": 0,
            },
        )

        flag_tracker.add([])
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 2,
                "unknown": 0,
                "unseen": 0,
            },
        )

        flag_tracker.add([(1, b"RECENT"), (3, b"EXISTS")])
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 3,
                "unknown": 1,
                "unseen": 0,
            },
        )

        flag_tracker.add(
            [(3, b"FETCH", (b"FLAGS", (b"\\Seen", b"\\Recent")))]
        )
        self.assertDictEqual(
            flag_tracker.message_counts,
            {
                "total": 3,
                "unknown": 0,
                "unseen": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
