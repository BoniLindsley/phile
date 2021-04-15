#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.launcher`
--------------------------
"""

# Standard libraries.
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio
import phile.pubsub_event


class TestNode(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.node = phile.pubsub_event.Node[int]()

    def test_default_initialisable(self) -> None:
        self.assertIsNone(self.node.content)

    def test_init_with_content(self) -> None:
        new_content = 1
        new_node = phile.pubsub_event.Node[int](content=new_content)
        self.assertEqual(new_node.content, new_content)

    async def test_next_get_set(self) -> None:
        next_content = 2
        self.node.set_next(content=next_content)
        next_node = await phile.asyncio.wait_for(self.node.next())
        self.assertEqual(next_node.content, next_content)

    def test_set_next_raises_if_repeated(self) -> None:
        next_content = 3
        self.node.set_next(content=next_content)
        with self.assertRaises(AssertionError):
            self.node.set_next(content=next_content)

    async def test_set_to_end_causes_next_to_raise(self) -> None:
        self.node.set_to_end()
        with self.assertRaises(phile.pubsub_event.Node.EndReached):
            await phile.asyncio.wait_for(self.node.next())

    async def test_set_to_end_rasies_if_set(self) -> None:
        self.node.set_next(content=4)
        with self.assertRaises(AssertionError):
            self.node.set_to_end()


class TestNoMoreEvents(unittest.TestCase):

    def test_default_initialisable(self) -> None:
        _error = phile.pubsub_event.NoMoreEvents()


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
        with self.assertRaises(AssertionError):
            self.publisher.push(2)


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
        with self.assertRaises(phile.pubsub_event.NoMoreEvents):
            await phile.asyncio.wait_for(self.subscriber.pull())
