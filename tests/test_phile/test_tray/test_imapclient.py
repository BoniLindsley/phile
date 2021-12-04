#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections
import contextlib
import datetime
import functools
import pathlib
import socket
import tempfile
import typing
import unittest

# External dependencies.
import imapclient
import keyring.backend
import keyring.credentials
import watchdog.events

# Internal modules.
import phile.asyncio
import phile.configuration
import phile.imapclient
import phile.tray.imapclient
import phile.watchdog.asyncio
from test_phile.test_configuration.test_init import (
    PreparesEntries as PreparesConfiguration,
)
import test_phile.test_imapclient
from test_phile.test_imapclient import (
    PreparesIMAPClient,
    PreparesIMAP4,
    UsesIMAPClient,
)
from test_phile.test_keyring import PreparesKeyring


class TestUnseenNotifier(unittest.TestCase):
    """Test :class:`phile.tray.imapclient.UnseenNotifier`."""

    def setUp(self) -> None:
        notify_directory = tempfile.TemporaryDirectory()
        self.addCleanup(notify_directory.cleanup)
        self.notify_path = pathlib.Path(notify_directory.name) / "imap.n"

    def test_constructor_with_just_notify_path(self) -> None:
        phile.tray.imapclient.UnseenNotifier(
            notify_path=self.notify_path
        )
        self.assertFalse(self.notify_path.exists())

    def test_constructor_with_select_response(self) -> None:
        select_response = {
            b"EXISTS": 2,
            b"FLAGS": (),
            b"RECENT": 0,
            b"UNSEEN": [b"2"],
        }
        phile.tray.imapclient.UnseenNotifier(
            notify_path=self.notify_path, select_response=select_response
        )
        self.assertTrue(self.notify_path.exists())

    def test_add_with_unseen_messages(self) -> None:
        unseen_notifier = phile.tray.imapclient.UnseenNotifier(
            notify_path=self.notify_path,
        )
        response_lines = [
            (1, b"RECENT"),
            (1, b"EXISTS"),
        ]
        unseen_notifier.add(response_lines)
        self.assertTrue(self.notify_path.exists())


class TestMissingCredential(unittest.TestCase):
    def test_is_exception(self) -> None:
        with self.assertRaises(phile.tray.imapclient.MissingCredential):
            raise phile.tray.imapclient.MissingCredential()
        with self.assertRaises(Exception):
            raise phile.tray.imapclient.MissingCredential()


class TestLoadConfiguration(
    PreparesConfiguration,
    PreparesKeyring,
    unittest.IsolatedAsyncioTestCase,
):
    configuration: phile.configuration.Entries

    def setUp(self) -> None:
        super().setUp()
        self.configuration = phile.configuration.load()
        self.configuration.imap = phile.configuration.ImapEntries(
            folder="f",
            host="h",
            password="config_pass",
            username="config_user",
        )
        keyring.set_password("imap", "keyring_user", "keyring_pass")
        keyring.set_password("imap", "config_user", "pass")

    async def load_configuration(
        self,
    ) -> phile.configuration.ImapEntries:
        return await phile.asyncio.wait_for(
            phile.tray.imapclient.load_configuration(
                configuration=self.configuration,
                keyring_backend=keyring.get_keyring(),
            )
        )

    async def test_uses_given_configuration(self) -> None:
        keyring.delete_password("imap", "u")
        imap_configuration = await self.load_configuration()
        self.assertEqual(
            imap_configuration,
            phile.configuration.ImapEntries(
                folder="f",
                host="h",
                password="config_pass",
                username="config_user",
            ),
        )

    async def test_uses_keyring_if_password_missing(self) -> None:
        assert self.configuration.imap is not None
        self.configuration.imap.password = None
        imap_configuration = await self.load_configuration()
        self.assertEqual(
            imap_configuration,
            phile.configuration.ImapEntries(
                folder="f",
                host="h",
                password="pass",
                username="config_user",
            ),
        )

    async def test_uses_keyring_if_username_and_password_missing(
        self,
    ) -> None:
        assert self.configuration.imap is not None
        self.configuration.imap.username = None
        self.configuration.imap.password = None
        imap_configuration = await self.load_configuration()
        self.assertEqual(
            imap_configuration,
            phile.configuration.ImapEntries(
                folder="f",
                host="h",
                password="keyring_pass",
                username="keyring_user",
            ),
        )

    async def test_raises_if_username_is_unknown(self) -> None:
        assert self.configuration.imap is not None
        self.configuration.imap.username = "unknown_user"
        self.configuration.imap.password = None
        with unittest.mock.patch.object(
            phile.keyring.MemoryKeyring,
            "get_credential",
            side_effect=phile.tray.imapclient.MissingCredential(),
        ):
            with self.assertRaises(
                phile.tray.imapclient.MissingCredential
            ):
                await self.load_configuration()

    async def test_raises_if_missing_imap_configuration(self) -> None:
        self.configuration.imap = None
        with self.assertRaises(phile.tray.imapclient.MissingCredential):
            await self.load_configuration()

    async def test_raises_if_missing_password(self) -> None:
        assert self.configuration.imap is not None
        self.configuration.imap.password = None
        keyring.delete_password("imap", "config_user")
        with self.assertRaises(phile.tray.imapclient.MissingCredential):
            await self.load_configuration()

    async def test_raises_if_has_password_without_username(self) -> None:
        assert self.configuration.imap is not None
        self.configuration.imap.username = None
        with self.assertRaises(phile.tray.imapclient.MissingCredential):
            await self.load_configuration()


class TestCreateClient(PreparesIMAPClient, unittest.TestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.imap_configuration: phile.configuration.ImapEntries

    def setUp(self) -> None:
        super().setUp()
        self.imap_configuration = phile.configuration.ImapEntries(
            folder="f",
            host="h",
            idle_refresh_timeout=datetime.timedelta(),
            password="keyring_pass",
            username="keyring_user",
        )

    def test_creates_client_in_idle_mode(self) -> None:
        phile.tray.imapclient.create_client(
            imap_configuration=self.imap_configuration,
        )


class TestIdle(PreparesIMAPClient, unittest.TestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.imap_client: imapclient.IMAPClient
        self.responses: (
            collections.abc.Iterator[list[phile.imapclient.ResponseLine]]
        )
        self.stop_reader: socket.socket
        self.stop_writer: socket.socket

    def setUp(self) -> None:
        super().setUp()
        self.imap_client = imapclient.IMAPClient(host="h")
        self.stop_reader, self.stop_writer = socket.socketpair()
        self.addCleanup(self.stop_reader.close)
        self.addCleanup(self.stop_writer.close)
        self.responses = iter(
            phile.tray.imapclient.idle(
                imap_client=self.imap_client,
                stop_socket=self.stop_reader,
                refresh_timeout=datetime.timedelta(),
            )
        )

    def is_idle(self) -> bool:
        return phile.imapclient.is_idle(self.imap_client)

    def assert_is_idle_soon(self, iteration_limit: int = 4) -> None:
        for response in self.responses:
            del response
            if self.is_idle():
                return
            iteration_limit -= 1
            if iteration_limit <= 0:
                break
        raise self.failureException("Did not become idle.")

    def assert_not_idle_soon(self, iteration_limit: int = 4) -> None:
        for response in self.responses:
            del response
            if not self.is_idle():
                return
            iteration_limit -= 1
            if iteration_limit <= 0:
                break
        raise self.failureException("Did not stop idle.")

    def assert_stops_soon(self, iteration_limit: int = 4) -> None:
        for response in self.responses:
            del response
            iteration_limit -= 1
            if iteration_limit <= 0:
                raise self.failureException("Did not stop.")

    def test_stops_if_stop_socket_has_data(self) -> None:
        self.stop_writer.sendall(b"\0")
        self.assertTrue(not self.is_idle())
        self.assert_not_idle_soon()
        self.assert_stops_soon()

    def test_yields_responses_until_stop(self) -> None:
        self.imap_client._imap._server_socket.sendall(b"\0")
        patcher = unittest.mock.patch(
            "test_phile.test_imapclient.IMAPClientMock.idle_check",
            return_value=[(1, b"EXISTS")],
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.assert_is_idle_soon()  # IDLE check response.
        self.assert_is_idle_soon()  # IDLE check response.
        self.stop_writer.sendall(b"\0")
        self.assert_not_idle_soon()  # Exit IDLE state.
        self.assert_stops_soon()

    def test_gives_up_if_empty_response_returned(self) -> None:
        self.imap_client._imap._server_socket.sendall(b"\0")
        patcher = unittest.mock.patch(
            "test_phile.test_imapclient.IMAPClientMock.idle_check",
            return_value=[(1, b"EXISTS")],
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.assert_is_idle_soon()
        patcher = unittest.mock.patch(
            "test_phile.test_imapclient.IMAPClientMock.idle_check",
            return_value=[],
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.assert_not_idle_soon()
        self.assert_stops_soon()

    def test_refreshes_idle_state_if_timeout(self) -> None:
        self.assert_not_idle_soon()  # Exit IDLE state from timeout.
        self.stop_writer.sendall(b"\0")
        self.assert_not_idle_soon()  # Exit IDLE state.
        self.assert_stops_soon()


class TestEventType(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

    def test_available_attributes(self) -> None:
        self.assertIsInstance(
            phile.tray.imapclient.EventType.ADD,
            phile.tray.imapclient.EventType,
        )
        self.assertIsInstance(
            phile.tray.imapclient.EventType.SELECT,
            phile.tray.imapclient.EventType,
        )


class TestEvent(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

    def test_add_event(self) -> None:
        event = phile.tray.imapclient.Event(
            type=phile.tray.imapclient.EventType.ADD,
            add_response=[],
        )
        self.assertEqual(
            event["type"],
            phile.tray.imapclient.EventType.ADD,
        )
        self.assertEqual(event["add_response"], [])

    def test_select_event(self) -> None:
        event = phile.tray.imapclient.Event(
            type=phile.tray.imapclient.EventType.SELECT,
            select_response={},
        )
        self.assertEqual(
            event["type"],
            phile.tray.imapclient.EventType.SELECT,
        )
        self.assertEqual(event["select_response"], {})


class TestReadFromServer(UsesIMAPClient, unittest.TestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.imap_configuration: phile.configuration.ImapEntries
        self.events: collections.abc.Iterator[
            phile.tray.imapclient.Event
        ]
        self.stop_reader: socket.socket
        self.stop_writer: socket.socket

    def setUp(self) -> None:
        super().setUp()
        self.imap_configuration = phile.configuration.ImapEntries(
            folder="f",
            host="h",
            idle_refresh_timeout=datetime.timedelta(),
            maximum_reconnect_delay=datetime.timedelta(),
            password="keyring_pass",
            username="keyring_user",
        )
        self.stop_reader, self.stop_writer = socket.socketpair()
        self.addCleanup(self.stop_reader.close)
        self.addCleanup(self.stop_writer.close)
        self.events = iter(
            phile.tray.imapclient.read_from_server(
                imap_configuration=self.imap_configuration,
                stop_socket=self.stop_reader,
            )
        )

    def assert_returns_event_type_soon(
        self,
        expected_event_type: phile.tray.imapclient.EventType,
        iteration_limit: int = 4,
    ) -> None:
        received_events: list[phile.tray.imapclient.Event] = []
        for event in self.events:
            received_events.append(event)
            if event["type"] == expected_event_type:
                return
            iteration_limit -= 1
            if iteration_limit <= 0:
                break
        raise self.failureException(
            "Expected event type:\n  {}\n"
            "Received:\n  {}".format(
                expected_event_type, received_events
            )
        )

    def assert_stops_soon(self, iteration_limit: int = 4) -> None:
        received_events: list[phile.tray.imapclient.Event] = []
        for event in self.events:
            received_events.append(event)
            iteration_limit -= 1
            if iteration_limit <= 0:
                raise self.failureException(
                    "Expected to stop. Not stopped.\n"
                    "Received:\n  {}".format(received_events)
                )

    def test_stops_if_stop_socket_has_data(self) -> None:
        self.stop_writer.sendall(b"\0")
        self.assert_stops_soon()

    def test_refreshes_idle_state_if_timeout(self) -> None:
        self.assert_returns_event_type_soon(
            phile.tray.imapclient.EventType.ADD  # First connect.
        )
        self.stop_writer.sendall(b"\0")
        self.assert_returns_event_type_soon(
            phile.tray.imapclient.EventType.ADD  # Refresh idle state.
        )

    def test_reconnects_after_disconnect(self) -> None:
        self.assert_returns_event_type_soon(
            phile.tray.imapclient.EventType.ADD  # First connect.
        )
        self.imap_clients[0].shutdown()
        self.assert_returns_event_type_soon(
            phile.tray.imapclient.EventType.ADD  # Reconnect.
        )


class TestRun(
    PreparesConfiguration,
    PreparesKeyring,
    UsesIMAPClient,
    unittest.IsolatedAsyncioTestCase,
):
    configuration: phile.configuration.Entries
    file_event_view: phile.watchdog.asyncio.EventView
    notify_directory: pathlib.Path
    notify_path: pathlib.Path
    observer: phile.watchdog.asyncio.BaseObserver

    def setUp(self) -> None:
        super().setUp()
        self.configuration = phile.configuration.load()
        self.configuration.imap = phile.configuration.ImapEntries(
            folder="f",
            host="h",
            idle_refresh_timeout=datetime.timedelta(),
            password="config_pass",
            username="config_user",
        )
        self.notify_directory = (
            self.configuration.state_directory_path
            / self.configuration.notify_directory
        )
        self.notify_directory.mkdir()
        self.notify_path = self.notify_directory / (
            "20-imap-idle" + self.configuration.notify_suffix
        )

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.observer = observer = phile.watchdog.asyncio.Observer()
        self.file_event_view = await phile.asyncio.wait_for(
            observer.schedule(self.notify_directory)
        )
        self.addAsyncCleanup(
            observer.unschedule, str(self.notify_directory)
        )

    async def wait_for_new_imap_client(self) -> None:
        existing_client_count = len(self.imap_clients)
        while existing_client_count == len(self.imap_clients):
            await asyncio.sleep(0)

    async def test_creates_client(self) -> None:
        runner = asyncio.create_task(
            phile.tray.imapclient.run(
                configuration=self.configuration,
                keyring_backend=keyring.get_keyring(),
            )
        )
        await phile.asyncio.wait_for(self.wait_for_new_imap_client())

    async def test_creates_notify_file_when_mail_exists(self) -> None:
        patcher = unittest.mock.patch(
            "test_phile.test_imapclient.IMAPClientMock.select_folder",
            return_value={
                b"EXISTS": 2,
                b"FLAGS": (),
                b"RECENT": 0,
                b"UNSEEN": [b"2"],
            },
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        del patcher
        patcher = unittest.mock.patch(
            "test_phile.test_imapclient.IMAPClientMock.idle_check",
            side_effect=[OSError],
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        del patcher
        runner = asyncio.create_task(
            phile.tray.imapclient.run(
                configuration=self.configuration,
                keyring_backend=keyring.get_keyring(),
            )
        )
        await phile.asyncio.wait_for(self.wait_for_new_imap_client())
        self.imap_clients[0]._imap._server_socket.sendall(b"\0")
        async for event in self.file_event_view:
            expected_event = watchdog.events.FileCreatedEvent(
                str(self.notify_path)
            )
            if event == expected_event:
                return

    async def test_creates_notify_file_when_mail_arrives(self) -> None:
        patcher = unittest.mock.patch(
            "test_phile.test_imapclient.IMAPClientMock.idle_check",
            side_effect=[[(1, b"EXISTS")], OSError],
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        runner = asyncio.create_task(
            phile.tray.imapclient.run(
                configuration=self.configuration,
                keyring_backend=keyring.get_keyring(),
            )
        )
        await phile.asyncio.wait_for(self.wait_for_new_imap_client())
        self.imap_clients[0]._imap._server_socket.sendall(b"\0")
        async for event in self.file_event_view:
            expected_event = watchdog.events.FileCreatedEvent(
                str(self.notify_path)
            )
            if event == expected_event:
                return

    async def test_exits_gracefully_on_cancel(self) -> None:
        runner = asyncio.create_task(
            phile.tray.imapclient.run(
                configuration=self.configuration,
                keyring_backend=keyring.get_keyring(),
            )
        )
        await phile.asyncio.wait_for(self.wait_for_new_imap_client())
        runner.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await runner

    async def test_logs_keyring_error(self) -> None:
        assert self.configuration.imap is not None
        self.configuration.imap.password = None
        with self.assertLogs(phile.tray.imapclient.__name__) as logs:
            await phile.asyncio.wait_for(
                phile.tray.imapclient.run(
                    configuration=self.configuration,
                    keyring_backend=keyring.get_keyring(),
                )
            )
            self.assertEqual(
                logs.output,
                [
                    "WARNING:phile.tray.imapclient:"
                    "Unable to load imap password."
                ],
            )

    async def test_propagates_exception_from_connect_error(self) -> None:
        patcher = unittest.mock.patch(
            "test_phile.test_imapclient.IMAPClientMock",
            side_effect=[OSError],
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        with self.assertRaises(OSError):
            await phile.asyncio.wait_for(
                phile.tray.imapclient.run(
                    configuration=self.configuration,
                    keyring_backend=keyring.get_keyring(),
                )
            )
