#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import datetime
import imaplib
import logging
import socket
import typing

# External dependencies.
import imapclient

# Internal modules.
import phile.asyncio

_logger = logging.getLogger(__name__)

ExistsResponse = tuple[int, typing.Literal[b'EXISTS']]
ExpungeResponse = tuple[int, typing.Literal[b'EXPUNGE']]
FetchResponse = tuple[int, typing.Literal[b'FETCH'], tuple[typing.Any]]
ResponseLine = typing.Union[
    # Cannot seem to use a union of responses types.
    # mypy casts b'EXPUNGE' to bytes when evaluating a tuple
    # and is unable to match it to the response types.
    tuple[int, bytes],
    tuple[int, bytes, typing.Any],
]
ResponseHandler = typing.Union[
    # This needs to be expanded as necessary.
    collections.abc.Callable[[ExistsResponse], typing.Any],
    collections.abc.Callable[[ExpungeResponse], typing.Any],
    collections.abc.Callable[[FetchResponse], typing.Any],
]
SelectResponse = dict[bytes, typing.Any]


def get_socket(imap_client: imapclient.IMAPClient) -> socket.socket:
    """
    Return the socket used by an :class:`~imapclient.IMAPClient`.

    .. admonition:: Implementation detail

       The :mod:`imapclient` module,
       which is at version 2.1.0 at the time of writing,
       does not provide an API to retrieve the socket.
       This function wraps the access
       in case of changes to implementation.
    """
    return imap_client._sock


def is_idle(imap_client: imapclient.IMAPClient) -> bool:
    idle_tag = imap_client._idle_tag
    return ((idle_tag is not None)
            and (idle_tag in imap_client._imap.tagged_commands))


default_refresh_timeout = datetime.timedelta(minutes=28)


async def idle_responses(
    imap_client: imapclient.IMAPClient,
    refresh_timeout: datetime.timedelta = default_refresh_timeout,
) -> collections.abc.AsyncIterator[list[bytes]]:
    """
    Yield responses from an :class:`~imapclient.IMAPClient` in IDLE mode.

    :type imap_client: imapclient.IMAPClient
    :param imap_client: A client in IDLE mode.
        This loop wait for IDLE responses from this client.
    :type refresh_timeout: datetime.timedelta
    :param refresh_timeout:
        Duration to stay in IDLE state for
        before restarting IDLE state in the same connection.
    :raises ConnectionResetError:
        If the underlying socket of `imap_client` seems to be closed.
    :returns: This async iterator does not close normally.
        It can be stopped by cancelling its wrapping task.

    .. admonition:: Raison d'être:

        In the current implementation, an :class:`~imapclient.IMAPClient`
        can wait for IDLE messages after it enters IDLE mode.
        The :class:`~imapclient.IMAPClient` can either wait for messages
        with a given `timeout`, of possibly zero seconds,
        or wait indefinitely.
        This means that, to make it possible to exit IDLE mode early,
        the :class:`~imapclient.IMAPClient` needs to

          1. Check exit condition in a busy loop with a low `timeout`; or
          2. Send a `DONE` message to the server in a different thread,
             since, according to the IMAP specification,
             the client should not be sending anything else
             before this function returns.
             However, :class:`~imapclient.IMAPClient`
             is not officially thread-safe.
             And due to the way :meth:`~imapclient.IMAPClient.idle_check`
             is implemented,
             the server response for the `DONE` message
             would trigger an exception to be raised.
             In particular, this may cause any data
             being processed by :meth:`~imapclient.IMAPClient.idle_check`
             to be lost
             (though it may be possible to retrieve them from the stack,
             and to recover the response to `DONE` by mocking); or
          3. Forcibly drop the connection and reconnect.

        This coroutine provides a way
        to fetch messages in a cleaner way.

    .. admonition:: Implementation detail (Important for Windows)

       This coroutine currently waits on sockets
       using :meth:`~asyncio.loop.add_reader`
       of :func:`asyncio.get_running_loop`,
       and also :meth:`~asyncio.loop.remove_reader` for clean-up.
       These methods are not supported by
       :class:`~asyncio.ProactorEventLoop`
       according to :ref:`python:asyncio-platform-support`.
       This means the event loop used to run this coroutine
       cannot be a :class:`~asyncio.ProactorEventLoop`.

       At the time of writing (with Python on version 3.8),
       :class:`~asyncio.ProactorEventLoop` is the default event loop
       used in :mod:`asyncio` on Windows.
       This may be side-stepped
       by using :func:`asyncio.set_event_loop`
       together with a :class:`~asyncio.SelectorEventLoop`.
    """
    assert is_idle(imap_client)
    timeout_task: (asyncio.Task[typing.Any]) = asyncio.create_task(
        asyncio.sleep(0)
    )
    readable_check_task = timeout_task
    done: set[asyncio.Future[typing.Any]] = {timeout_task}
    try:
        while True:
            if readable_check_task in done:
                readable_check_task.cancel()
                readable_check_task = asyncio.create_task(
                    phile.asyncio.readable(get_socket(imap_client))
                )
            if timeout_task in done:
                timeout_task.cancel()
                timeout_task = asyncio.create_task(
                    asyncio.sleep(refresh_timeout.total_seconds())
                )
            done, pending = await asyncio.wait(
                (timeout_task, readable_check_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if readable_check_task in done:
                idle_response = imap_client.idle_check(timeout=0)
                _logger.debug("IDLE response: %s", idle_response)
                yield idle_response
                if not idle_response:
                    raise ConnectionResetError(
                        "IMAP4 socket seems to be closed."
                    )
            if timeout_task in done:
                _logger.debug("Exiting IDLE state.")
                try:
                    done_response = imap_client.idle_done()
                except imaplib.IMAP4.abort as e:
                    raise ConnectionResetError(
                        "IMAP4 socket is closed."
                    ) from e
                _logger.debug("IDLE done response: %s", done_response)
                yield done_response[1]
                _logger.debug("Entering IDLE state.")
                imap_client.idle()
    finally:
        readable_check_task.cancel()
        timeout_task.cancel()


class FlagTracker:
    """
    Remember unseen flags for IMAP messages as update occurs.

    .. admonition:: Implementation detail

       Uses a crude implementation to get the job done.
       In particular, this becomes infeasibly inefficient
       if the selected folder has a large number of messages.
    """

    def __init__(
        self,
        select_response: typing.Optional[SelectResponse] = None
    ) -> None:

        self._response_handlers: dict[bytes, ResponseHandler] = {
            b"EXISTS": self._add_exists,
            b"EXPUNGE": self._add_expunge,
            b"FETCH": self._add_fetch,
        }
        """A dictionary of callbacks to process response lines."""
        self._message_count = 0
        """Number of messages in the selected folder."""
        self._unknown_message_ids = set[int]()
        """A list of IDs of messages without a `b'\\Seen'` flag."""
        self._unseen_message_ids = set[int]()
        """A list of IDs of messages whose seen status is unknown."""

        if select_response is not None:
            self.select(select_response)

    def select(self, select_response: SelectResponse) -> None:
        """
        Change database to conform to data given by a select response.
        """

        self._message_count = select_response[b"EXISTS"]
        self._unknown_message_ids.clear()
        self._unseen_message_ids.clear()
        self._unseen_message_ids.update({
            int(encoded_id.decode())
            for encoded_id in select_response.get(b'UNSEEN', [])
        })
        """A list of IDs of messages whose seen status is unknown."""

    def add(self, untagged_response: list[ResponseLine]) -> None:
        """
        Update database according changes given by `untagged_response`.

        :type untagged_response: list
        :param untagged_response:
            A :class:`list` of response lines, each converted to a tuple
            by :class:`~imapclient.IMAPClient`.`
        """

        # Example of `response_line`: `(1, b"FETCH", (b"FLAGS", ()))`
        handlers = self._response_handlers
        for response_line in untagged_response:
            handler = handlers.get(
                response_line[1], self._add_unhandled_response
            )
            handler(response_line)  # type: ignore[arg-type]

    @property
    def message_counts(self) -> dict[str, int]:
        """
        A :class:`dict` counting different types of messages.

        :return:
            A :class:`dict` of :class:`int`.
              * The `"total"` key stores the number of messages
                in the selected folder.
              * The `"unknown"` key stores the number of messages
                whose unseen state is unknown.
              * The `"unseen"` key stores the number of messages
                that are unseen.

        Every message has a, possibly empty, set of flags
        associated to it.
        Of particular interest is the `b'\\SEEN'`
        for determining whether a message is unread.
        However, due to the way IMAP IDLE protocol provide information,
        it is not always possible to determine the flags
        of a message that was sent or moved to a folder,
        without first exiting IDLE mode.

        The `"unknown"` key lets the user know
        whether there are any such messages.
        The flags of those messages are usually sent again
        when their flags, including unread status, are changed.
        """

        return {
            "total": self._message_count,
            "unknown": len(self._unknown_message_ids),
            "unseen": len(self._unseen_message_ids),
        }

    def _add_exists(self, response_line: ExistsResponse) -> None:
        """
        Update the messages count.

        :type response_line: tuple
        :param response_line:
            An untagged `EXISTS` response line from
            say `SELECT`, `NOOP` or `IDLE` commands,
            converted to a tuple by :class:`~imapclient.IMAPClient`.
            An example is `( 2, b"EXISTS")`.

            Entry `0` is the number of messages in the selected folder.
            Entry `1` indicates that it is a `EXISTS` response.
            So it must be `b'EXISTS'`.
        """

        assert response_line[1] == b'EXISTS'
        new_message_count = response_line[0]
        old_message_count = self._message_count
        for message_id in self._unseen_message_ids:
            # Defensive check.
            assert message_id <= new_message_count  # pragma: no cover

        unknown_message_ids = self._unknown_message_ids
        if old_message_count < new_message_count:
            # Add the message ID from just beyond the old count
            # to the new message count.
            # The response line does not provide enough information
            # on whether new messages are unseen.
            unknown_message_ids.update(
                range(new_message_count, old_message_count, -1)
            )
        self._message_count = new_message_count

    def _add_expunge(self, response_line: ExpungeResponse) -> None:
        """
        Remove a message from the database.

        :type response_line: tuple
        :param response_line:
            An untagged `EXPUNGE` response line from
            say `SELECT`, `NOOP` or `IDLE` commands,
            converted to a tuple by :class:`~imapclient.IMAPClient`.
            An example is `( 2, b"EXPUNGE")`.

            Entry `0` is the ID of message to remove.
            Entry `1` indicates that it is a `EXPUNGE` response.
            So it must be `b'EXPUNGE'`.
        """

        assert response_line[1] == b'EXPUNGE'
        message_id_to_remove = response_line[0]
        assert message_id_to_remove <= self._message_count

        # Update the unseen message list.
        self._unseen_message_ids = {
            # Expunge shifts all IDs greater than the given ID down by 1,
            # to fill the gap missing from the expunge.
            id if (id < message_id_to_remove) else (id - 1)
            for id in self._unseen_message_ids
            # Expunge removes the given ID from the list if it exists.
            if id != message_id_to_remove
        }
        # Update the unknown-status message list as well
        self._unknown_message_ids = {
            # Expunge shifts all IDs greater than the given ID down by 1,
            # to fill the gap missing from the expunge.
            id if (id < message_id_to_remove) else (id - 1)
            for id in self._unseen_message_ids
            # Expunge removes the given ID from the list if it exists.
            if id != message_id_to_remove
        }
        # There is now one less message.
        self._message_count -= 1

    def _add_fetch(self, response_line: FetchResponse) -> None:
        """
        Update database using changes given by `response_line`.

        :type response_line: tuple
        :param response_line:
            An untagged `FETCH` response line from
            say `SELECT`, `NOOP` or `IDLE` commands,
            converted to a tuple by :class:`~imapclient.IMAPClient`.
            An example is `( 1, b"FETCH", ( b"FLAGS", (b"\\Seen", )))`.

            Entry `0` is the message ID whose flags to be changed.
            Entry `1` indicates that it is a `FETCH` response.
            So it must be `b'FETCH'`.
            Entry `2` is itself a tuple,
            iterating between data name and data value for the name.
            The tuple represents data about the message
            whose ID is given in entry `0`.
            Of concern to this function is only the `b'FLAGS'` entry.
        """

        assert response_line[1] == b'FETCH'
        message_id = response_line[0]
        response_data = response_line[2]

        # This function is only concerned with `b'FLAGS'` data.
        # Search for all of them, though we expect only one.
        response_data_size = len(response_data)
        flag_name_indices = [
            index for index, value in enumerate(response_data)
            # Data names only appear with even indicies.
            if index % 2 == 0
            # Only find data about flags.
            and value == b'FLAGS'
            # Index at the end does not make
            # If entry `index` gives a data name,
            # then entry `index + 1` must exist to contain its value,
            # as promised by the IMAP specification.
            # But it may be missing because of disconnect.
            # Check that this does not go past the end of the tuple.
            and index + 1 < response_data_size
        ]
        # If there are no `b'FLAGS'` data, there is nothing to do.
        if len(flag_name_indices) == 0:
            return

        # Process every `b'FLAGS'` data found.
        for flag_index in flag_name_indices:
            # There should be entry `flag_index  + 1` in `response_data`
            # by IMAP specification.
            flag_tuple = response_data[flag_index + 1]
            # Search for the `b'\\Seen'` flag.
            # The message is unseen if the flag is missing.
            # If the mssage is seen, remove its ID from the unseen list.
            # Otherwise, make sure the ID is in the list.
            if b'\\Seen' in flag_tuple:
                self._unseen_message_ids.discard(message_id)
            else:
                self._unseen_message_ids.add(message_id)
            # The unseen status is now known.
            self._unknown_message_ids.discard(message_id)

    def _add_unhandled_response(
        self, response_line: ResponseLine
    ) -> None:
        """Ignores the given response."""
