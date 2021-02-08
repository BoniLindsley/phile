#!/usr/bin/env python3

# Standard libraries.
import pathlib
import tempfile
import unittest

# Internal modules.
import phile.imapclient
import phile.tray.publishers.imap_idle
from test_phile.test_imapclient import UsesIMAPClient


class TestUnseenNotifier(unittest.TestCase):
    """Test :class:`phile.tray.publishers.imap_idle.UnseenNotifier`."""

    def setUp(self) -> None:
        notify_directory = tempfile.TemporaryDirectory()
        self.addCleanup(notify_directory.cleanup)
        self.notify_path = pathlib.Path(notify_directory.name) / 'imap.n'

    def test_constructor_with_just_notify_path(self) -> None:
        phile.tray.publishers.imap_idle.UnseenNotifier(
            notification_path=self.notify_path
        )
        self.assertFalse(self.notify_path.exists())

    def test_constructor_with_select_response(self) -> None:
        select_response = {
            b"EXISTS": 2,
            b"FLAGS": (),
            b"RECENT": 0,
            b"UNSEEN": [b"2"],
        }
        phile.tray.publishers.imap_idle.UnseenNotifier(
            notification_path=self.notify_path,
            select_response=select_response
        )
        self.assertTrue(self.notify_path.exists())

    def test_add_with_unseen_messages(self) -> None:
        unseen_notifier = phile.tray.publishers.imap_idle.UnseenNotifier(
            notification_path=self.notify_path,
        )
        response_lines = [
            (1, b"RECENT"),
            (1, b"EXISTS"),
        ]
        unseen_notifier.add(response_lines)
        self.assertTrue(self.notify_path.exists())


class TestCreateIdleClient(UsesIMAPClient, unittest.TestCase):
    """
    Test :class:`phile.tray.publishers.imap_idle.create_idle_client`.
    """

    def test_creates_client_in_idle_mode(self) -> None:
        imap_client, _select_response = (
            phile.tray.publishers.imap_idle.create_idle_client(
                folder='Inboxer',
                host='create_idle_client://',
                password='super-secret',
                username='itsme',
            )
        )
        self.assertTrue(phile.imapclient.is_idle(imap_client))
