#!/usr/bin/env python3

# Standard libraries.
import unittest

# Internal packages.
import phile.asyncio
import phile.capability


class TestEventType(unittest.TestCase):
    def test_members_exist(self) -> None:
        members = {
            phile.capability.EventType.DEL,
            phile.capability.EventType.SET,
        }
        self.assertEqual(len(members), 2)


class TestEvent(unittest.TestCase):
    def test_initialisation(self) -> None:
        phile.capability.Event(
            type=phile.capability.EventType.DEL,
            capability=int,
        )

    def test_members(self) -> None:
        event = phile.capability.Event(
            type=phile.capability.EventType.SET,
            capability=str,
        )
        self.assertEqual(event.type, phile.capability.EventType.SET)
        self.assertEqual(event.capability, str)


class TestAlreadyEnabled(unittest.TestCase):
    def test_check_is_runtime_error(self) -> None:
        self.assertIsInstance(
            phile.capability.AlreadyEnabled(), RuntimeError
        )


class TestRegistry(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.capability_registry = phile.capability.Registry()

    def test_getitem_non_existent(self) -> None:
        self.assertIsNone(self.capability_registry.get(int))

    def test_getitem_setitem(self) -> None:
        self.capability_registry[int] = 1
        self.assertEqual(self.capability_registry[int], 1)

    async def test_setitem__emits_events(self) -> None:
        event_view = self.capability_registry.event_queue.__aiter__()
        self.capability_registry[int] = 0
        self.assertIn(int, self.capability_registry)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.capability.Event(
                type=phile.capability.EventType.SET,
                capability=int,
            ),
        )

    def test_set(self) -> None:
        self.capability_registry.set(2)
        self.assertEqual(self.capability_registry[int], 2)

    async def test_delitem__removes_item(self) -> None:
        self.capability_registry[int] = 0
        event_view = self.capability_registry.event_queue.__aiter__()
        del self.capability_registry[int]

    async def test_delitem__emits_events(self) -> None:
        self.capability_registry[int] = 0
        event_view = self.capability_registry.event_queue.__aiter__()
        del self.capability_registry[int]
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.capability.Event(
                type=phile.capability.EventType.DEL,
                capability=int,
            ),
        )

    async def test_pop__removes_and_return_item(self) -> None:
        self.capability_registry[int] = 0
        popped_value = self.capability_registry.pop(int)
        self.assertEqual(popped_value, 0)
        self.assertNotIn(int, self.capability_registry)

    async def test_pop__raises_if_item_missing(self) -> None:
        with self.assertRaises(KeyError):
            popped_value = self.capability_registry.pop(int)

    async def test_pop__returns_default_if_item_missing(self) -> None:
        popped_value = self.capability_registry.pop(int, 1)
        self.assertEqual(popped_value, 1)

    async def test_pop__emits_events(self) -> None:
        self.capability_registry[int] = 0
        event_view = self.capability_registry.event_queue.__aiter__()
        self.capability_registry.pop(int)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.capability.Event(
                type=phile.capability.EventType.DEL,
                capability=int,
            ),
        )

    async def test_pop__does_not_emit_event_if_missing(self) -> None:
        event_view = self.capability_registry.event_queue.__aiter__()
        self.capability_registry.pop(int, 1)
        self.capability_registry.event_queue.put_done()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_pop__does_not_emit_event_if_missing_and_no_default(
        self,
    ) -> None:
        event_view = self.capability_registry.event_queue.__aiter__()
        with self.assertRaises(KeyError):
            self.capability_registry.pop(int)
        self.capability_registry.event_queue.put_done()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    def test_provide_returns_context_manager_for_clean_up(self) -> None:
        with self.capability_registry.provide(1):
            self.assertIn(int, self.capability_registry)
            self.assertEqual(self.capability_registry[int], 1)
        self.assertNotIn(int, self.capability_registry)

    def test_provide_allows_specified_capability(self) -> None:
        value = phile.capability.AlreadyEnabled()
        with self.capability_registry.provide(value, RuntimeError):
            self.assertIn(RuntimeError, self.capability_registry)
            self.assertEqual(
                self.capability_registry[RuntimeError], value
            )
        self.assertNotIn(RuntimeError, self.capability_registry)

    def test_provide_raises_if_already_provided(self) -> None:
        self.capability_registry[int] = 0
        with self.assertRaises(phile.capability.AlreadyEnabled):
            with self.capability_registry.provide(1):
                pass
        self.assertEqual(self.capability_registry[int], 0)

    async def test_provide__emits_events(self) -> None:
        event_view = self.capability_registry.event_queue.__aiter__()
        with self.capability_registry.provide(1):
            event = await phile.asyncio.wait_for(event_view.__anext__())
            self.assertEqual(
                event,
                phile.capability.Event(
                    type=phile.capability.EventType.SET,
                    capability=int,
                ),
            )
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.capability.Event(
                type=phile.capability.EventType.DEL,
                capability=int,
            ),
        )
