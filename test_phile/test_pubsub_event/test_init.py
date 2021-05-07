#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.launcher`
--------------------------
"""

# Standard libraries.
import asyncio
import unittest

# Internal packages.
import phile.asyncio
import phile.pubsub_event


class TestNoMoreMessages(unittest.TestCase):

    def test_default_initialisable(self) -> None:
        _error = phile.pubsub_event.NoMoreMessages()


class TestPublisher(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.publisher = phile.pubsub_event.Publisher[int]()

    def test_default_initialisable(self) -> None:
        """Test done in :meth:`setUp`."""

    def test_push_available(self) -> None:
        """Functionality tested to be tested in Subscriber."""
        self.publisher.push(1)

    def test_stop_available(self) -> None:
        """Functionality tested to be tested in Subscriber."""
        self.publisher.stop()

    def test_push_after_stop_raises(self) -> None:
        self.publisher.stop()
        with self.assertRaises(asyncio.InvalidStateError):
            self.publisher.push(2)

    def test_double_stop_is_fine(self) -> None:
        self.publisher.stop()
        self.publisher.stop()


class TestSubscriber(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.publisher = phile.pubsub_event.Publisher[int]()
        self.subscriber = phile.pubsub_event.Subscriber[int](
            publisher=self.publisher,
        )

    def test_initialise_with_publisher(self) -> None:
        "Test done in :meth:`setUp`."

    async def test_pull_gets_data(self) -> None:
        next_content = 1
        self.publisher.push(next_content)
        pulled_content = await phile.asyncio.wait_for(
            self.subscriber.pull()
        )
        self.assertEqual(pulled_content, next_content)

    async def test_pull_raises_if_no_more_content(self) -> None:
        self.publisher.stop()
        with self.assertRaises(phile.pubsub_event.NoMoreMessages):
            await phile.asyncio.wait_for(self.subscriber.pull())

    async def test_cancelling_pull_does_not_cancel_node(self) -> None:
        pull_task = asyncio.create_task(self.subscriber.pull())
        pull_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pull_task
        self.publisher.push(1)
