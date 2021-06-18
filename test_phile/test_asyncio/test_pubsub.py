#!/usr/bin/env python3
"""
--------------------------------
Test :mod:`phile.asyncio.pubsub`
--------------------------------
"""

# Standard library.
import asyncio
import typing
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio
import phile.asyncio.pubsub


class TestNode(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.node: phile.asyncio.pubsub.Node[int]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.node = phile.asyncio.pubsub.Node[int]()

    def test_available_exceptions(self) -> None:
        with self.assertRaises(Exception):
            raise phile.asyncio.pubsub.Node.AlreadySet()
        with self.assertRaises(Exception):
            raise phile.asyncio.pubsub.Node.EndReached()
        with self.assertRaises(Exception):
            raise phile.asyncio.pubsub.Node.NotSet()

    def test_set_should_work(self) -> None:
        self.node.set(0)

    def test_set_value_raises_if_set(self) -> None:
        self.node.set(0)
        with self.assertRaises(phile.asyncio.pubsub.Node.AlreadySet):
            self.node.set(0)

    def test_set_value_raises_if_end_set(self) -> None:
        self.node.set_end()
        with self.assertRaises(phile.asyncio.pubsub.Node.AlreadySet):
            self.node.set(0)

    def test_set_creates_next_node(self) -> None:
        self.node.set(0)
        self.assertIsInstance(
            self.node.next_node,
            phile.asyncio.pubsub.Node,
        )

    async def test_get_returns_value_set(self) -> None:
        self.node.set(0)
        value = await phile.asyncio.wait_for(self.node.get())
        self.assertEqual(value, 0)

    async def test_get_raises_if_end_set(self) -> None:
        self.node.set_end()
        with self.assertRaises(phile.asyncio.pubsub.Node.EndReached):
            await phile.asyncio.wait_for(self.node.get())

    def test_get_nowait_returns_value_set(self) -> None:
        self.node.set(0)
        value = self.node.get_nowait()
        self.assertEqual(value, 0)

    def test_get_nowait_raises_if_not_set(self) -> None:
        with self.assertRaises(phile.asyncio.pubsub.Node.NotSet):
            self.node.get_nowait()

    def test_get_nowait_raises_if_end_set(self) -> None:
        self.node.set_end()
        with self.assertRaises(phile.asyncio.pubsub.Node.EndReached):
            self.node.get_nowait()

    def test_set_end_should_work(self) -> None:
        self.assertFalse(self.node.is_end())
        self.node.set_end()

    def test_set_end_does_not_create_next_node(self) -> None:
        self.node.set_end()
        with self.assertRaises(AttributeError):
            self.node.next_node  # pylint: disable=pointless-statement

    def test_set_end_raises_if_already_set(self) -> None:
        self.node.set(0)
        with self.assertRaises(phile.asyncio.pubsub.Node.AlreadySet):
            self.node.set_end()

    def test_is_end_changes_after_set_end(self) -> None:
        self.assertFalse(self.node.is_end())
        self.node.set_end()
        self.assertTrue(self.node.is_end())

    def test_is_end_is_false_if_set(self) -> None:
        self.node.set(0)
        self.assertFalse(self.node.is_end())


class TestView(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.node: phile.asyncio.pubsub.Node[int]
        self.view: phile.asyncio.pubsub.View[int]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.node = phile.asyncio.pubsub.Node[int]()
        self.view = phile.asyncio.pubsub.View[int](next_node=self.node)

    async def test_get_returns_value(self) -> None:
        self.node.set(0)
        value = await phile.asyncio.wait_for(self.view.get())
        self.assertEqual(value, 0)

    async def test_get_propagates_end_error(self) -> None:
        self.node.set_end()
        with self.assertRaises(phile.asyncio.pubsub.Node.EndReached):
            await phile.asyncio.wait_for(self.view.get())

    async def test_get_advances_node(self) -> None:
        self.node.set(0)
        await phile.asyncio.wait_for(self.view.get())
        # Check that the next node can be set.
        self.node.next_node.set(1)
        value = await phile.asyncio.wait_for(self.view.get())
        self.assertEqual(value, 1)

    async def test_iterator_advances_until_end_reached(self) -> None:
        self.node.set(0)
        self.node.next_node.set(1)
        self.node.next_node.next_node.set_end()
        self.assertEqual([value async for value in self.view], [0, 1])


class TestQueue(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.queue: phile.asyncio.pubsub.Queue[int]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.queue = phile.asyncio.pubsub.Queue[int]()

    async def test_get_returns_put_value(self) -> None:
        awaiter = asyncio.create_task(self.queue.get())
        await asyncio.sleep(0)  # Give the task a chance to start.
        self.queue.put(1)
        value = await phile.asyncio.wait_for(awaiter)
        self.assertEqual(value, 1)

    async def test_await_raises_if_done(self) -> None:
        awaiter = asyncio.create_task(self.queue.get())
        await asyncio.sleep(0)  # Give the task a chance to start.
        self.queue.put_done()
        with self.assertRaises(phile.asyncio.pubsub.Node.EndReached):
            await phile.asyncio.wait_for(awaiter)

    async def test_is_iterator(self) -> None:

        async def fetch() -> list[int]:
            return [value async for value in self.queue]

        fetcher = asyncio.create_task(fetch())
        await asyncio.sleep(0)  # Give the task a chance to start.
        self.queue.put(0)
        self.queue.put(1)
        self.queue.put_done()
        fetched_values = await phile.asyncio.wait_for(fetcher)
        self.assertEqual(fetched_values, [0, 1])

    async def test_close_stops_queue(self) -> None:
        self.queue.close()
        with self.assertRaises(phile.asyncio.pubsub.Node.EndReached):
            await phile.asyncio.wait_for(self.queue.get())

    async def test_close_ignores_if_already_stopped(self) -> None:
        self.queue.put_done()
        self.queue.close()
        with self.assertRaises(phile.asyncio.pubsub.Node.EndReached):
            await phile.asyncio.wait_for(self.queue.get())
