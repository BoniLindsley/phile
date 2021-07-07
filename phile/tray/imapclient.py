#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import datetime
import enum
import imaplib
import logging
import pathlib
import select
import socket
import typing

# External dependencies.
import imapclient
import keyring

# Internal modules.
import phile.asyncio.pubsub
import phile.configuration
import phile.imapclient
import phile.notify

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)
"""Logger whose name is the module name."""


class UnseenNotifier(phile.imapclient.FlagTracker):
    """Create a notification to indicate unread emails."""

    def __init__(
        self, *args: typing.Any, notify_path: pathlib.Path,
        **kwargs: typing.Any
    ):
        self._notify_path = notify_path
        _logger.info("Using notification path: %s", self._notify_path)
        super().__init__(*args, **kwargs)
        # Ensure any existing notification file is cleared
        # if there are no new messages.
        self.update_notify_file()

    def select(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().select(*args, **kwargs)
        self.update_notify_file()

    def add(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().add(*args, **kwargs)
        self.update_notify_file()

    def update_notify_file(self) -> None:
        message_counts = self.message_counts
        unknown_count = message_counts['unknown']
        unseen_count = message_counts['unseen']
        _logger.debug("Message status: %s", message_counts)
        if unknown_count or unseen_count:
            _logger.debug("Creating notification file.")
            self._notify_path.write_text(
                "There are {} + {} unseen messages.".format(
                    unseen_count, unknown_count
                )
            )
        else:
            try:
                _logger.debug("Removing notification file.")
                self._notify_path.unlink()
            except FileNotFoundError:
                _logger.debug("Notification file not found. Ignoring.")


class MissingCredential(Exception):
    pass


async def load_configuration(
    configuration: phile.configuration.Entries,
    keyring_backend: keyring.backend.KeyringBackend,
) -> phile.configuration.ImapEntries:
    imap_configuration = configuration.imap
    if imap_configuration is None:
        raise MissingCredential(
            'Unable to find imap credentials in configuration'
        )
    imap_configuration = imap_configuration.copy()
    del configuration
    if imap_configuration.password is not None:
        if imap_configuration.username is None:
            raise MissingCredential('Unable to find imap username.')
    else:
        credential = await asyncio.to_thread(
            keyring_backend.get_credential,
            'imap',
            imap_configuration.username,
        )
        if credential is None:
            raise MissingCredential('Unable to load imap password.')
        imap_configuration.password = credential.password
        imap_configuration.username = credential.username
    return imap_configuration


def create_client(
    imap_configuration: phile.configuration.ImapEntries,
) -> tuple[imapclient.IMAPClient, phile.imapclient.SelectResponse]:
    assert imap_configuration.username is not None
    assert imap_configuration.password is not None
    _logger.info('Connecting to %s', imap_configuration.host)
    imap_client = imapclient.IMAPClient(
        host=imap_configuration.host,
        timeout=imap_configuration.connect_timeout.total_seconds(),
    )
    _logger.info('Logging in to %s', imap_configuration.username)
    response = imap_client.login(
        imap_configuration.username,
        imap_configuration.password,
    )
    _logger.debug('Login response: %s', response.decode())
    _logger.info('Selecting folder: %s', imap_configuration.folder)
    select_response = imap_client.select_folder(
        imap_configuration.folder
    )
    return imap_client, select_response


def idle(
    imap_client: imapclient.IMAPClient,
    stop_socket: socket.socket,
    refresh_timeout: datetime.timedelta,
) -> collections.abc.Iterator[list[phile.imapclient.ResponseLine]]:
    _logger.debug("Starting IDLE wait loop.")
    imap_socket = phile.imapclient.get_socket(imap_client)
    while True:
        refresh_time = datetime.datetime.now() + refresh_timeout
        assert not phile.imapclient.is_idle(imap_client)
        _logger.debug("Entering IDLE state.")
        imap_client.idle()
        try:
            rlist = [imap_socket]
            while rlist:
                timeout = refresh_time - datetime.datetime.now()
                rlist, wlist, xlist = select.select(
                    [imap_socket, stop_socket],
                    [],
                    [],
                    max(timeout.total_seconds(), 0),
                )
                del timeout
                del wlist
                del xlist
                if imap_socket in rlist:
                    idle_response = imap_client.idle_check(timeout=0)
                    _logger.debug("IDLE response: %s", idle_response)
                    # If no data is returned, the conenction is closed.
                    # Try to stop. idle_done will likely error.
                    if not idle_response:
                        return
                    yield idle_response
                    del idle_response
                if stop_socket in rlist:
                    return
        finally:
            _logger.debug("Exiting IDLE state.")
            done_response = imap_client.idle_done()
            _logger.debug("IDLE done response: %s", done_response)
            yield done_response[1]
            del done_response


class EventType(enum.IntEnum):
    ADD = enum.auto()
    SELECT = enum.auto()


class Event(typing.TypedDict, total=False):
    type: EventType
    add_response: list[phile.imapclient.ResponseLine]
    select_response: phile.imapclient.SelectResponse


def read_from_server(
    *,
    imap_configuration: phile.configuration.ImapEntries,
    stop_socket: socket.socket,
) -> collections.abc.Iterator[Event]:
    idle_refresh_timeout = imap_configuration.idle_refresh_timeout
    maximum_reconnect_delay = imap_configuration.maximum_reconnect_delay
    minimum_reconnect_delay = imap_configuration.minimum_reconnect_delay
    # First connect does not need a delay.
    reconnect_delay = datetime.timedelta(seconds=0)
    while True:
        # Reset the database before waiting.
        yield Event(
            type=EventType.SELECT,
            select_response={
                b"EXISTS": 0,
                b"FLAGS": tuple(),
                b"RECENT": 0,
            },
        )
        _logger.info("Connecting in %s.", reconnect_delay)
        rlist, wlist, xlist = select.select([
            stop_socket
        ], [], [], reconnect_delay.total_seconds())
        if rlist:
            _logger.info("Received stop request. Not connecting.")
            break
        del rlist
        del wlist
        del xlist
        _logger.debug("Creating an IMAP client to connect with.")
        imap_client, select_response = create_client(
            imap_configuration=imap_configuration,
        )
        try:
            yield Event(
                type=EventType.SELECT,
                select_response=select_response,
            )
            del select_response
            # Now that the connection has been successful,
            # reset the reconnection delay.
            reconnect_delay = datetime.timedelta(seconds=0)
            for response_lines in idle(
                imap_client=imap_client,
                refresh_timeout=idle_refresh_timeout,
                stop_socket=stop_socket,
            ):
                yield Event(
                    type=EventType.ADD,
                    add_response=response_lines,
                )
        # Connection and socket errors are subclasses of `OSError`.
        # There are no finer grain parent class
        # that catches all socket errors.
        # Listing all socket errors individually is not a good idea,
        # so a blanket catch of `OSError` is done here instead.
        except (
            imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError
        ) as error:
            _logger.info(error)
            # Double the delay.
            reconnect_delay *= 2
            reconnect_delay = max(
                reconnect_delay, minimum_reconnect_delay
            )
            reconnect_delay = min(
                reconnect_delay, maximum_reconnect_delay
            )
        finally:
            # Always logout before returning to try to clean up
            # on a best effort basis.
            _logger.debug("Logging out from IMAP client.")
            try:
                imap_client.logout()
            # Some servers immediately close the socket
            # when it receives a `BYE` request.
            # This means attempting to close the socket
            # would raise an exception.
            # Since a disconnection is the goal here anyway,
            # catch the exception and continue.
            except (imaplib.IMAP4.error, OSError):
                _logger.info("IMAP socket was not closed properly.")


async def run(
    configuration: phile.configuration.Entries,
    keyring_backend: keyring.backend.KeyringBackend,
) -> None:
    event_queue = phile.asyncio.pubsub.Queue[Event]()
    imap_configuration = await load_configuration(
        configuration=configuration,
        keyring_backend=keyring_backend,
    )
    loop = asyncio.get_running_loop()
    stop_reader, stop_writer = await loop.run_in_executor(
        None, socket.socketpair
    )
    try:

        def handle_event() -> None:
            try:
                for event in read_from_server(
                    imap_configuration=imap_configuration,
                    stop_socket=stop_reader,
                ):
                    loop.call_soon_threadsafe(event_queue.put, event)
            finally:
                loop.call_soon_threadsafe(event_queue.put_done)

        worker_thread = phile.asyncio.Thread(target=handle_event)
        notify_directory = (
            configuration.state_directory_path /
            configuration.notify_directory
        )
        notify_directory.mkdir(parents=True, exist_ok=True)
        imap_response_handler = UnseenNotifier(
            notify_path=(notify_directory / "20-imap-idle.notify")
        )
        del notify_directory
        event_reader = event_queue.__aiter__()
        worker_thread.start()
        try:
            # A branching path going from `async for` to `finally`
            # is reported as missing by `coverage.py`.
            # But it should be covered by one of the tests already.
            # Specifically, propagation of connection error.
            # So ignoring this branch report for now,
            async for event in event_reader:  # pragma: no branch
                event_type = event['type']
                if event_type == EventType.ADD:
                    await loop.run_in_executor(
                        None,
                        imap_response_handler.add,
                        event['add_response'],
                    )
                elif event_type == EventType.SELECT:
                    await loop.run_in_executor(
                        None,
                        imap_response_handler.select,
                        event['select_response'],
                    )
                else:  # pragma: no cover  # Defensive.
                    assert False, 'Unreadable.'
        finally:
            _logger.info("Sending stop request. To not connect.")
            stop_writer.sendall(b'\0')
            await worker_thread.async_join()
    finally:
        try:
            stop_reader.close()
        finally:
            stop_writer.close()
