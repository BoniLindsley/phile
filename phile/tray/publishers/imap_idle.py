#!/usr/bin/env python3

# Standard libraries.
import asyncio
import contextlib
import datetime
import logging
import pathlib
import sys
import typing

# External dependencies.
import imapclient
import keyring

# Internal modules.
import phile
import phile.imapclient
import phile.notify

logger = logging.getLogger(__name__)


class UnseenNotifier(phile.imapclient.FlagTracker):
    """Create a notification to indicate unread emails."""

    def __init__(
        self, *args: typing.Any, notification_path: pathlib.Path,
        **kwargs: typing.Any
    ):
        self._notification_path = notification_path
        logger.info(
            "Using notification path: %s", self._notification_path
        )
        super().__init__(*args, **kwargs)
        # Ensure any existing notification file is cleared
        # if there are no new messages.
        self.update_notification_file()

    def select(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().select(*args, **kwargs)
        self.update_notification_file()

    def add(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().add(*args, **kwargs)
        self.update_notification_file()

    def update_notification_file(self) -> None:
        message_counts = self.message_counts
        unknown_count = message_counts['unknown']
        unseen_count = message_counts['unseen']
        logger.debug("Message status: %s", message_counts)
        if unknown_count or unseen_count:
            logger.debug("Creating notification file.")
            self._notification_path.write_text(
                "There are {} + {} unseen messages.".format(
                    unseen_count, unknown_count
                )
            )
        else:
            try:
                logger.debug("Removing notification file.")
                self._notification_path.unlink()
            except FileNotFoundError:
                logger.debug("Notification file not found. Ignoring.")


default_socket_timeout = datetime.timedelta(minutes=1)


def create_idle_client(
    *,
    folder: str,
    host: str,
    password: str,
    socket_timeout: datetime.timedelta = default_socket_timeout,
    username: str,
) -> tuple[imapclient.IMAPClient, phile.imapclient.SelectResponse]:
    logger.info('Connecting to %s', host)
    imap_client = imapclient.IMAPClient(
        host=host, timeout=socket_timeout.total_seconds()
    )
    logger.info('Logging in to %s', username)
    # Try not to keep a reference to the password alive.
    response = imap_client.login(username, password)
    logger.debug('Login response: %s', response.decode())
    logger.info('Selecting folder: %s', folder)
    select_response = imap_client.select_folder(folder)
    imap_client.idle()
    return imap_client, select_response


async def run(
    capabilities: phile.Capabilities
) -> None:  # pragma: no cover
    configuration = capabilities[phile.Configuration]
    keyring_backend = capabilities[
        # Use of abstract type as key is intended.
        keyring.backend.KeyringBackend  # type: ignore[misc]
    ]
    try:
        connection_configuration = configuration.data['imap']
        """
        Details to use for connecting to the IMAP server.

        Must contain `folder`, `host` and `username` keys.
        """
    except KeyError as parent_error:
        raise RuntimeError(
            'Unable to find imap credentials'
        ) from parent_error

    connection_configuration['password'] = keyring_backend.get_password(
        'imap', connection_configuration['username']
    )
    refresh_timeout = datetime.timedelta(minutes=24)
    """Time to wait between refreshing IDLE status."""
    minimum_reconnect_delay = datetime.timedelta(seconds=15)
    maximum_reconnect_delay = datetime.timedelta(minutes=16)
    notification_path = (
        configuration.notification_directory
    ) / "20-imap-idle.notify"

    # First reconnect does not need a delay.
    reconnect_delay = datetime.timedelta(seconds=0)
    while True:
        try:
            logger.info("Connecting in %s.", reconnect_delay)
            await asyncio.sleep(reconnect_delay.total_seconds())

            logger.debug("Creating an IMAP client to connect with.")
            imap_client, select_response = create_idle_client(
                **connection_configuration
            )
            imap_response_handler = UnseenNotifier(
                select_response=select_response,
                notification_path=notification_path
            )
            del select_response

            # Now that the connection has been successful,
            # reset the reconnection delay.
            reconnect_delay = datetime.timedelta(seconds=0)

            logger.debug("Starting an IDLE wait loop.")
            async for response in (
                phile.imapclient.idle_responses(
                    imap_client=imap_client,
                    refresh_timeout=refresh_timeout
                )
            ):
                imap_response_handler.add(response)
        except asyncio.CancelledError:
            # If the notifier is asked to cancel,
            # then logout before returning to try to clean up
            # on a best effort basis.
            logger.debug("Logging out from IMAP client.")
            # Some servers immediately close the socket
            # when it receives a `BYE` request.
            # This means attempting to close the socket
            # would raise an exception.
            # Since a disconnection is the goal here anyway,
            # catch the exception and continue.
            try:
                imap_client.logout()
            except OSError:
                logger.info("IMAP socket was not closed properly.")
            # Cacnelled error should not be suppressed.
            # The caller is expected to handle it appropriately.
            raise
        # Connection and socket errors are subclasses of `OSError`.
        # There are no finer grain parent class
        # that catches all socket errors.
        # Listing all socket errors individually is not a good idea,
        # so a blanket catch of `OSError` is done here instead.
        except OSError as e:
            logger.info(e)
            # Double the delay.
            reconnect_delay *= 2
            reconnect_delay = max(
                reconnect_delay, minimum_reconnect_delay
            )
            reconnect_delay = min(
                reconnect_delay, maximum_reconnect_delay
            )
        finally:
            notification_path.unlink(missing_ok=True)


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    KeyringBackend = keyring.backend.KeyringBackend
    capabilities[KeyringBackend] = (  # type: ignore[misc]
        # Don't reformat -- causes linebreak at [ ].
        keyring.get_keyring()
    )
    await run(capabilities=capabilities)
    return 0


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
