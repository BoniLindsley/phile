#!/usr/bin/env python3

# Standard library.
import typing
import unittest

# Internal packages.
import phile.data


class TestBisectable(unittest.TestCase):
    class BisectableClass:
        def __eq__(self, other: object) -> bool:
            return NotImplemented

        def __lt__(self, other: object) -> bool:
            return NotImplemented

    def test_can_be_satisfied_by_classes(self) -> None:
        _: phile.data.Bisectable = self.BisectableClass()

    def test_can_be_satisfied_by_int(self) -> None:
        _: phile.data.Bisectable = 31

    def test_can_be_satisfied_by_str(self) -> None:
        _: phile.data.Bisectable = "bisectable"


class TestEventType(unittest.TestCase):
    def test_members_exist(self) -> None:
        members = {
            phile.data.EventType.INSERT,
            phile.data.EventType.DISCARD,
            phile.data.EventType.SET,
        }
        self.assertEqual(len(members), 3)


class TestEvent(unittest.TestCase):
    def test_initialisation(self) -> None:
        phile.data.Event[str, int](
            type=phile.data.EventType.DISCARD,
            index=1,
            key="key",
            value=11,
            current_keys=["no_key"],
            current_values=[10],
        )

    def test_members(self) -> None:
        event = phile.data.Event[str, int](
            type=phile.data.EventType.SET,
            index=0,
            key="key",
            value=11,
            current_keys=["key"],
            current_values=[11],
        )
        self.assertEqual(event.type, phile.data.EventType.SET)
        self.assertEqual(event.index, 0)
        self.assertEqual(event.key, "key")
        self.assertEqual(event.value, 11)
        self.assertEqual(event.current_keys, ["key"])
        self.assertEqual(event.current_values, [11])


class TestRegistry(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.registry: phile.data.Registry[int, str]

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.registry = phile.data.Registry[int, str]()
        self.addCleanup(self.registry.close)

    def test_init__without_arguments(self) -> None:
        self.assertIsInstance(self.registry, phile.data.Registry)

    def test_has_attributes(self) -> None:
        self.assertIsInstance(
            self.registry.event_queue, phile.asyncio.pubsub.Queue
        )
        self.assertEqual(
            self.registry.current_keys,
            list[int](),
        )
        self.assertEqual(
            self.registry.current_values,
            list[str](),
        )

    def test_invariants(self) -> None:
        current_keys = self.registry.current_keys
        current_values = self.registry.current_values
        self.assertEqual(len(current_keys), len(current_values))
        self.assertEqual(current_keys, sorted(current_keys))

    def test_set__new_value_inserts(self) -> None:
        self.registry.set(13, "thirteen")
        self.assertEqual(self.registry.current_keys, [13])
        self.assertEqual(self.registry.current_values, ["thirteen"])
        self.test_invariants()

    async def test_set__new_value_emits_insert_event(self) -> None:
        event_view = self.registry.event_queue.__aiter__()
        self.registry.set(14, "fourteen")
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.data.Event[int, str](
                type=phile.data.EventType.INSERT,
                index=0,
                key=14,
                value="fourteen",
                current_keys=[14],
                current_values=["fourteen"],
            ),
        )

    def test_set__larger_value_inserts_after(self) -> None:
        self.registry.set(15, "fifteen")
        self.registry.set(80, "eighty")
        self.assertEqual(self.registry.current_keys, [15, 80])
        self.assertEqual(
            self.registry.current_values, ["fifteen", "eighty"]
        )
        self.test_invariants()

    def test_set__smaller_value_inserts_before(self) -> None:
        self.registry.set(16, "sixteen")
        self.registry.set(0, "zero")
        self.assertEqual(self.registry.current_keys, [0, 16])
        self.assertEqual(
            self.registry.current_values, ["zero", "sixteen"]
        )
        self.test_invariants()

    async def test_set__larger_value_emits_insert_event(self) -> None:
        self.registry.set(17, "seventeen")
        event_view = self.registry.event_queue.__aiter__()
        self.registry.set(19, "nineteen")
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.data.Event[int, str](
                type=phile.data.EventType.INSERT,
                index=1,
                key=19,
                value="nineteen",
                current_keys=[17, 19],
                current_values=["seventeen", "nineteen"],
            ),
        )

    async def test_set__smaller_value_emits_insert_event(self) -> None:
        self.registry.set(18, "eighteen")
        event_view = self.registry.event_queue.__aiter__()
        self.registry.set(8, "eight")
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.data.Event[int, str](
                type=phile.data.EventType.INSERT,
                index=0,
                key=8,
                value="eight",
                current_keys=[8, 18],
                current_values=["eight", "eighteen"],
            ),
        )

    def test_set__with_known_key_replaces_value(self) -> None:
        self.registry.set(20, "twenty")
        self.registry.set(20, "20")
        self.assertEqual(self.registry.current_keys, [20])
        self.assertEqual(self.registry.current_values, ["20"])
        self.test_invariants()

    async def test_set__ignores_known_key_with_same_value(self) -> None:
        self.registry.set(22, "twenty-two")
        self.registry.set(22, "twenty-two")
        self.assertEqual(self.registry.current_keys, [22])
        self.test_invariants()

    async def test_set__with_known_key_emits_set_event(self) -> None:
        self.registry.set(21, "twenty-one")
        event_view = self.registry.event_queue.__aiter__()
        self.registry.set(21, "21")
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.data.Event[int, str](
                type=phile.data.EventType.SET,
                index=0,
                key=21,
                value="21",
                current_keys=[21],
                current_values=["21"],
            ),
        )

    async def test_set__with_same_key_and_value_does_not_emit_event(
        self,
    ) -> None:
        self.registry.set(22, "twenty-two")
        event_view = self.registry.event_queue.__aiter__()
        self.registry.set(22, "twenty-two")
        # Test that no event was emitted by doing something
        # that would emit another event.
        self.registry.set(22, "22")
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.data.Event[int, str](
                type=phile.data.EventType.SET,
                index=0,
                key=22,
                value="22",
                current_keys=[22],
                current_values=["22"],
            ),
        )

    def test_discard__removes_value_with_known_key(self) -> None:
        self.registry.set(23, "twenty-three")
        self.registry.set(24, "twenty-four")
        self.registry.discard(23)
        self.assertEqual(self.registry.current_keys, [24])
        self.assertEqual(self.registry.current_values, ["twenty-four"])
        self.test_invariants()

    def test_discard__clears_if_last_value(self) -> None:
        self.registry.set(25, "twenty-five")
        self.registry.discard(25)
        self.assertEqual(self.registry.current_keys, [])
        self.assertEqual(self.registry.current_values, [])
        self.test_invariants()

    def test_discard__ignores_unknown_value(self) -> None:
        self.registry.set(26, "twenty-six")
        self.registry.discard(27)
        self.assertEqual(self.registry.current_keys, [26])
        self.assertEqual(self.registry.current_values, ["twenty-six"])
        self.test_invariants()

    def test_discard__ignores_unknown_value_ignored_even_if_not_last_key(
        self,
    ) -> None:
        # For branch coverage.
        self.registry.set(29, "twenty-nine")
        self.registry.discard(28)
        self.assertEqual(self.registry.current_keys, [29])
        self.assertEqual(self.registry.current_values, ["twenty-nine"])
        self.test_invariants()

    async def test_discard__with_known_key_emits_discard_event(
        self,
    ) -> None:
        self.registry.set(30, "thirty")
        event_view = self.registry.event_queue.__aiter__()
        self.registry.discard(30)
        event = await phile.asyncio.wait_for(event_view.__anext__())
        self.assertEqual(
            event,
            phile.data.Event[int, str](
                type=phile.data.EventType.DISCARD,
                index=0,
                key=30,
                value="thirty",
                current_keys=[],
                current_values=[],
            ),
        )

    async def test_close__ends_event_queue(self) -> None:
        self.registry.close()
        event_view = self.registry.event_queue.__aiter__()
        with self.assertRaises(StopAsyncIteration):
            await phile.asyncio.wait_for(event_view.__anext__())

    async def test_close__causes_set_warn_later(self) -> None:
        self.registry.close()
        with self.assertWarns(UserWarning):
            self.registry.set(40, "forty")
