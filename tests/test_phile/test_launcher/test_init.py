#!/usr/bin/env python3

# Standard libraries.
import asyncio
import collections.abc
import dataclasses
import types
import typing
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio
import phile.asyncio.pubsub
import phile.capability
import phile.launcher

_T = typing.TypeVar("_T")


async def noop() -> None:
    pass


class TestType(unittest.TestCase):
    def test_members_exist(self) -> None:
        members = {
            phile.launcher.Type.SIMPLE,
            phile.launcher.Type.EXEC,
            phile.launcher.Type.FORKING,
            phile.launcher.Type.CAPABILITY,
        }
        self.assertEqual(len(members), 4)


class TestDescriptor(unittest.TestCase):
    def test_attributes(self) -> None:
        phile.launcher.Descriptor(
            after=set(),
            before=set(),
            binds_to=set(),
            capability_name="a",
            conflicts=set(),
            default_dependencies=True,
            exec_start=[noop],
            exec_stop=[noop],
            type=phile.launcher.Type.SIMPLE,
        )


class TestCapabilityNotSet(unittest.TestCase):
    def test_is_exception(self) -> None:
        with self.assertRaises(phile.launcher.CapabilityNotSet):
            raise phile.launcher.CapabilityNotSet()
        with self.assertRaises(RuntimeError):
            raise phile.launcher.CapabilityNotSet()


class TestMissingDescriptorData(unittest.TestCase):
    def test_is_exception(self) -> None:
        with self.assertRaises(phile.launcher.MissingDescriptorData):
            raise phile.launcher.MissingDescriptorData()
        with self.assertRaises(KeyError):
            raise phile.launcher.MissingDescriptorData()


class TestNameInUse(unittest.TestCase):
    def test_is_exception(self) -> None:
        with self.assertRaises(phile.launcher.NameInUse):
            raise phile.launcher.NameInUse()
        with self.assertRaises(RuntimeError):
            raise phile.launcher.NameInUse()


def make_nullary_async(
    function: collections.abc.Callable[..., _T],
    /,
    *args: typing.Any,
    **kwargs: typing.Any,
) -> collections.abc.Callable[[], collections.abc.Awaitable[_T]]:
    """
    Returns a coroutine function that calls the given function.

    Returns a nullary function. That is, it is not a coroutine object.
    To await for it, use ``await make_async(f)()``.
    """

    async def wrapper_coroutine() -> _T:
        return function(*args, **kwargs)

    return wrapper_coroutine


@dataclasses.dataclass
class Counter:
    value: int


def create_awaiter(limit: int) -> tuple[Counter, phile.launcher.Command]:
    counter = Counter(value=0)

    async def awaiter() -> None:
        for _ in range(limit):
            counter.value += 1
            await asyncio.sleep(0)

    return counter, awaiter


class TestOneToManyTwoWayDict(unittest.TestCase):
    def test_has_attribute(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        self.assertIsInstance(int_map.inverses, types.MappingProxyType)

    def test_set_item_sets(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        int_map[0] = {1}
        self.assertEqual(int_map[0], {1})

    def test_set_item_updates_inverse(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        int_map[0] = {1}
        self.assertEqual(int_map.inverses[1], {0})
        int_map[1] = {1}
        self.assertEqual(int_map.inverses[1], {0, 1})

    def test_set_item_accepts_empty_set(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        int_map[0] = set[int]()

    def test_set_item_cleans_up_previous_value_if_set(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        int_map[0] = {1}
        int_map[0] = {2}
        self.assertEqual(int_map[0], {2})

    def test_del_item_sets(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        int_map[0] = {1}
        self.assertEqual(int_map[0], {1})

    def test_del_item_updates_inverse(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        int_map[0] = {1}
        int_map[1] = {1}
        del int_map[0]
        self.assertEqual(int_map.inverses[1], {1})
        del int_map[1]
        self.assertNotIn(1, int_map.inverses)

    def test_del_item_accepts_key_with_value_of_empty_set(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        int_map[0] = set[int]()
        del int_map[0]

    def test_pop_raises(self) -> None:
        int_map = phile.launcher.OneToManyTwoWayDict[int, int]()
        with self.assertRaises(AttributeError):
            # Tests attribute access.
            int_map.pop  # pylint: disable=pointless-statement


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.launcher.Database`."""

    def setUp(self) -> None:
        super().setUp()
        self.launcher_database = phile.launcher.Database()

    def test_contains_on_empty_database(self) -> None:
        self.assertFalse(self.launcher_database.contains("not_there"))

    def test_add_with_minimal_data(self) -> None:
        self.launcher_database.add("minimal", {"exec_start": [noop]})

    def test_add_fails_if_name_already_added(self) -> None:
        name = "reused"
        self.launcher_database.add(name, {"exec_start": [noop]})
        with self.assertRaises(phile.launcher.NameInUse):
            self.launcher_database.add(name, {"exec_start": [noop]})

    def test_contains_after_add(self) -> None:
        name = "checked"
        self.launcher_database.add(name, {"exec_start": [noop]})
        self.assertTrue(self.launcher_database.contains(name))

    def test_add_fails_without_exec_start(self) -> None:
        with self.assertRaises(phile.launcher.MissingDescriptorData):
            self.launcher_database.add("no_exec_start", {})

    def test_add_updates_afters(self) -> None:
        self.launcher_database.add(
            "dependent",
            {
                "exec_start": [noop],
                "after": {"dependency"},
            },
        )
        self.assertEqual(
            self.launcher_database.after["dependent"],
            {"dependency"},
        )
        self.assertEqual(
            self.launcher_database.after.inverses["dependency"],
            {"dependent"},
        )

    def test_add_binds_to_creates_inverses(self) -> None:
        self.launcher_database.add(
            "dependent",
            {
                "exec_start": [noop],
                "binds_to": {"bind_target"},
            },
        )
        self.launcher_database.add(
            "bind_target",
            {"exec_start": [noop]},
        )
        self.assertEqual(
            self.launcher_database.binds_to["dependent"],
            {"bind_target"},
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses["bind_target"],
            {"dependent"},
        )

    def test_add_binds_to_adds_to_existing_inverses(self) -> None:
        self.launcher_database.add(
            "dependent_1",
            {
                "exec_start": [noop],
                "binds_to": {"bind_target"},
            },
        )
        self.launcher_database.add("bind_target", {"exec_start": [noop]})
        self.assertEqual(
            self.launcher_database.binds_to.inverses["bind_target"],
            {"dependent_1"},
        )
        self.launcher_database.add(
            "dependent_2",
            {
                "exec_start": [noop],
                "binds_to": {"bind_target"},
            },
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses["bind_target"],
            {"dependent_1", "dependent_2"},
        )

    def test_add__with_before_creates_inverses(self) -> None:
        self.launcher_database.add(
            "first",
            {
                "exec_start": [noop],
                "before": {"second"},
                "default_dependencies": False,
            },
        )
        self.launcher_database.add("second", {"exec_start": [noop]})
        self.assertEqual(
            self.launcher_database.before["first"],
            {"second"},
        )
        self.assertEqual(
            self.launcher_database.before.inverses["second"],
            {"first"},
        )

    def test_add__with_capability_name(self) -> None:
        self.launcher_database.add(
            "something",
            {
                "capability_name": "int",
                "exec_start": [noop],
                "type": phile.launcher.Type.CAPABILITY,
            },
        )
        self.assertEqual(
            self.launcher_database.capability_name["something"], "int"
        )

    def test_add__with_capability_name_has_default_type_capability(
        self,
    ) -> None:
        self.launcher_database.add(
            "something",
            {
                "capability_name": "int",
                "exec_start": [noop],
            },
        )
        self.assertEqual(
            self.launcher_database.capability_name["something"], "int"
        )
        self.assertEqual(
            self.launcher_database.type["something"],
            phile.launcher.Type.CAPABILITY,
        )

    def test_add__with_conflicts_creates_inverses(self) -> None:
        self.launcher_database.add(
            "something",
            {
                "exec_start": [noop],
                "conflicts": {"conflict"},
                "default_dependencies": False,
            },
        )
        self.launcher_database.add("conflict", {"exec_start": [noop]})
        self.assertEqual(
            self.launcher_database.conflicts["something"],
            {"conflict"},
        )
        self.assertEqual(
            self.launcher_database.conflicts.inverses["conflict"],
            {"something"},
        )

    def test_add__with_default_dependencies_adds_dependencies(
        self,
    ) -> None:
        database = self.launcher_database
        database.add(
            "something",
            {"exec_start": [noop], "default_dependencies": True},
        )
        self.assertEqual(
            database.default_dependencies["something"], True
        )
        self.assertEqual(
            database.conflicts["something"], {"phile_shutdown.target"}
        )
        self.assertEqual(
            database.before["something"], {"phile_shutdown.target"}
        )

        database.add(
            "else",
            {"exec_start": [noop], "default_dependencies": False},
        )
        self.assertEqual(database.default_dependencies["else"], False)
        self.assertEqual(database.conflicts["else"], set())
        self.assertEqual(database.before["else"], set())

    def test_remove__succeeds_after_add(self) -> None:
        name = "to_be_removed"
        self.launcher_database.add(name, {"exec_start": [noop]})
        self.launcher_database.remove(name)

    async def test_is_contains__is_false_after_remove(self) -> None:
        name = "unchecked"
        self.launcher_database.add(name, {"exec_start": [noop]})
        self.launcher_database.remove(name)
        self.assertFalse(self.launcher_database.contains(name))

    def test_remove__ignores_if_not_added(self) -> None:
        self.launcher_database.remove("not_added_unit")

    def test_remove__with_after_removes_from_inverses(self) -> None:
        self.launcher_database.add(
            "dependent_1",
            {
                "exec_start": [noop],
                "after": {"dependency"},
            },
        )
        self.launcher_database.add(
            "dependent_2",
            {
                "exec_start": [noop],
                "after": {"dependency"},
            },
        )
        self.launcher_database.add("dependency", {"exec_start": [noop]})
        self.assertEqual(
            self.launcher_database.after.inverses["dependency"],
            {"dependent_1", "dependent_2"},
        )
        self.launcher_database.remove("dependent_1")
        self.assertEqual(
            self.launcher_database.after.inverses["dependency"],
            {"dependent_2"},
        )

    def test_remove__with_after_removes_inverse_if_it_empties(
        self,
    ) -> None:
        self.launcher_database.add(
            "dependent",
            {
                "exec_start": [noop],
                "after": {"dependency"},
            },
        )
        self.launcher_database.add("dependency", {"exec_start": [noop]})
        self.assertEqual(
            self.launcher_database.after.inverses["dependency"],
            {"dependent"},
        )
        self.launcher_database.remove("dependent")
        self.assertNotIn(
            "bind_target", self.launcher_database.after.inverses
        )

    def test_remove_unbinds_from_inverses(self) -> None:
        self.launcher_database.add(
            "dependent_1",
            {
                "exec_start": [noop],
                "binds_to": {"bind_target"},
            },
        )
        self.launcher_database.add(
            "dependent_2",
            {
                "exec_start": [noop],
                "binds_to": {"bind_target"},
            },
        )
        self.launcher_database.add("bind_target", {"exec_start": [noop]})
        self.assertEqual(
            self.launcher_database.binds_to.inverses["bind_target"],
            {"dependent_1", "dependent_2"},
        )
        self.launcher_database.remove("dependent_1")
        self.assertEqual(
            self.launcher_database.binds_to.inverses["bind_target"],
            {"dependent_2"},
        )

    def test_remove_removes_inverses_if_it_empties(self) -> None:
        self.launcher_database.add(
            "dependent",
            {
                "exec_start": [noop],
                "binds_to": {"bind_target"},
            },
        )
        self.launcher_database.add("bind_target", {"exec_start": [noop]})
        self.assertEqual(
            self.launcher_database.binds_to.inverses["bind_target"],
            {"dependent"},
        )
        self.launcher_database.remove("dependent")
        self.assertNotIn(
            "bind_target", self.launcher_database.binds_to.inverses
        )


class TestEventType(unittest.TestCase):
    def test_members_exist(self) -> None:
        EventType = phile.launcher.EventType
        members = {
            EventType.START,
            EventType.STOP,
            EventType.ADD,
            EventType.REMOVE,
        }
        self.assertEqual(len(EventType), len(members))


class TestEvent(unittest.TestCase):
    def test_initialisation(self) -> None:
        phile.launcher.Event(
            type=phile.launcher.EventType.START,
            entry_name="test_init",
        )

    def test_members(self) -> None:
        event = phile.launcher.Event(
            type=phile.launcher.EventType.STOP,
            entry_name="test_members",
        )
        self.assertEqual(event.type, phile.launcher.EventType.STOP)
        self.assertEqual(event.entry_name, "test_members")


class TestRegistry(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_database: phile.launcher.Database
        self.launcher_registry: phile.launcher.Registry

    def setUp(self) -> None:
        super().setUp()
        self.launcher_registry = (
            launcher_registry
        ) = phile.launcher.Registry()
        self.launcher_database = launcher_registry.database

    def test_available_attributes(self) -> None:
        self.assertIsInstance(
            self.launcher_registry.event_queue,
            phile.asyncio.pubsub.Queue,
        )
        self.assertIsInstance(
            self.launcher_registry.capability_registry,
            phile.capability.Registry,
        )
        self.assertIsInstance(
            self.launcher_registry.database,
            phile.launcher.Database,
        )

    def test_init__adds_default_launchers(self) -> None:
        self.assertTrue(
            self.launcher_registry.contains("phile_shutdown.target")
        )

    def test_add_nowait__adds_launcher_as_known(self) -> None:
        entry_name = "add_nowait__adds_launcher_as_known"
        self.launcher_registry.add_nowait(
            entry_name, {"exec_start": [noop]}
        )
        self.assertTrue(self.launcher_registry.contains(entry_name))

    async def test_add__is_coroutine_version_of_add_nowait(self) -> None:
        entry_name = "add__is_coroutine_version_of_add_nowait"
        await phile.asyncio.wait_for(
            self.launcher_registry.add(
                entry_name, {"exec_start": [noop]}
            )
        )
        self.assertTrue(self.launcher_registry.contains(entry_name))

    async def test_add_nowait__emits_events(self) -> None:
        entry_name = "add_emits_events"
        view = self.launcher_registry.event_queue.__aiter__()
        self.launcher_registry.add_nowait(
            entry_name, {"exec_start": [noop]}
        )
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(
            message,
            phile.launcher.Event(
                type=phile.launcher.EventType.ADD, entry_name=entry_name
            ),
        )

    def test_remove_nowait__removes_given_launcher(self) -> None:
        entry_name = "remove_nowait__removes_given_launcher"
        self.launcher_registry.add_nowait(
            entry_name, {"exec_start": [noop]}
        )
        self.launcher_registry.remove_nowait(entry_name)
        self.assertFalse(self.launcher_registry.contains(entry_name))

    async def test_remove__is_coroutine_version_of_remove_nowait(
        self,
    ) -> None:
        entry_name = "remove__is_coroutine_version_of_remove_nowait"
        self.launcher_registry.add_nowait(
            entry_name, {"exec_start": [noop]}
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.remove(entry_name)
        )
        self.assertFalse(self.launcher_registry.contains(entry_name))

    async def test_remove_nowait__emits_events(self) -> None:
        entry_name = "remove_emits_events"
        self.launcher_registry.add_nowait(
            entry_name, {"exec_start": [noop]}
        )
        view = self.launcher_registry.event_queue.__aiter__()
        self.launcher_registry.remove_nowait(entry_name)
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(
            message,
            phile.launcher.Event(
                type=phile.launcher.EventType.REMOVE,
                entry_name=entry_name,
            ),
        )

    def test_remove_nowait__ignores_if_missing(self) -> None:
        entry_name = "remove_nowait__ignores_if_missing"
        self.launcher_registry.remove_nowait(entry_name)
        self.assertFalse(self.launcher_registry.contains(entry_name))

    async def test_start__simple_runs_exec_start(self) -> None:
        name = "simple_run"
        ran = asyncio.Event()

        async def set_and_wait() -> None:
            ran.set()
            await asyncio.Event().wait()

        self.launcher_registry.add_nowait(
            name, {"exec_start": [set_and_wait]}
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        self.assertTrue(ran.is_set())

    async def test_start__simple_runs_exec_start_without_awaiting_it(
        self,
    ) -> None:
        name = "simple_run_not_awaited"
        self.launcher_registry.add_nowait(
            name, {"exec_start": [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))

    async def test_start__exec_type_yields_once(self) -> None:
        name = "exec_run_with_exec_type"
        counter, awaiter = create_awaiter(limit=4)
        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [awaiter],
                "type": phile.launcher.Type.EXEC,
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        self.assertGreaterEqual(counter.value, 1)

    async def test_start__forking_waits_for_completion(self) -> None:
        name = "exec_forking"
        limit = 16
        counter, awaiter = create_awaiter(limit=limit)

        async def forker() -> asyncio.Task[None]:
            await awaiter()
            return asyncio.create_task(asyncio.sleep(0))

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [forker],
                "type": phile.launcher.Type.FORKING,
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        # There is not guarantee that the forker is awaited for,
        # but the limit should be sufficiently high in most cases.
        self.assertGreaterEqual(counter.value, limit)

    async def test_start__capability_waits_for_capability(self) -> None:
        async def run() -> None:
            # Test that irrelevant capability events are ignored.
            self.launcher_registry.capability_registry.set("a")
            del self.launcher_registry.capability_registry[str]
            self.launcher_registry.capability_registry.set(1)
            await asyncio.get_running_loop().create_future()

        name = "exec_capability"
        self.launcher_registry.add_nowait(
            name,
            {"exec_start": [run], "capability_name": "builtins.int"},
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))

    async def test_start__capability_warns_if_not_set(self) -> None:
        async def run() -> None:
            capability_registry = (
                self.launcher_registry.capability_registry
            )
            capability_registry.event_queue.put_done()
            await asyncio.get_running_loop().create_future()

        name = "exec_capability"
        self.launcher_registry.add_nowait(
            name,
            {"exec_start": [run], "capability_name": "builtins.int"},
        )
        with self.assertRaises(phile.launcher.CapabilityNotSet):
            await phile.asyncio.wait_for(
                self.launcher_registry.start(name)
            )

    async def test_start__returns_if_running(self) -> None:
        name = "starting_after_start"
        stop_launcher = asyncio.Event()
        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [stop_launcher.wait],
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.start(name))

    async def test_start__awaits_if_already_starting(self) -> None:
        name = "double_start"
        continue_forker = asyncio.Event()

        async def forker() -> asyncio.Task[None]:
            await continue_forker.wait()
            return asyncio.create_task(asyncio.sleep(0))

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [forker],
                "type": phile.launcher.Type.FORKING,
            },
        )
        start_1 = self.launcher_registry.start(name)
        await asyncio.sleep(0)
        start_2 = self.launcher_registry.start(name)
        await asyncio.sleep(0)
        self.assertFalse(start_1.done())
        self.assertFalse(start_2.done())
        continue_forker.set()
        await phile.asyncio.wait_for(start_2)
        await phile.asyncio.wait_for(start_1)

    async def test_is_running__is_true_after_start(self) -> None:
        name = "run_check"
        self.launcher_registry.add_nowait(
            name, {"exec_start": [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        self.assertTrue(self.launcher_registry.is_running(name))

    async def test_start__starts_binds_to(self) -> None:
        create_future = asyncio.get_running_loop().create_future
        dependency_started = create_future()
        self.launcher_registry.add_nowait(
            "dependent",
            {
                "exec_start": [create_future],
                "binds_to": {"dependency"},
            },
        )
        self.launcher_registry.add_nowait(
            "dependency",
            {
                "exec_start": [
                    make_nullary_async(dependency_started.set_result, 0),
                ],
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependent")
        )
        await phile.asyncio.wait_for(dependency_started)

    async def test_start__stops_conflicts_first(self) -> None:
        loop = asyncio.get_running_loop()
        conflict_stopped = loop.create_future()
        conflicted_stopped = loop.create_future()
        self.launcher_registry.add_nowait(
            "something",
            {
                "exec_start": [asyncio.Event().wait],
                "conflicts": {"conflict"},
            },
        )
        self.launcher_registry.add_nowait(
            "conflict",
            {
                "exec_start": [loop.create_future],
                "exec_stop": [
                    make_nullary_async(conflict_stopped.set_result, 0)
                ],
            },
        )
        self.launcher_registry.add_nowait(
            "conflicted",
            {
                "conflicts": {"something"},
                "exec_start": [loop.create_future],
                "exec_stop": [
                    make_nullary_async(conflicted_stopped.set_result, 0)
                ],
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("conflict")
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("conflicted")
        )
        self.assertTrue(self.launcher_registry.is_running("conflict"))
        self.assertTrue(self.launcher_registry.is_running("conflicted"))
        self.assertFalse(conflict_stopped.done())
        self.assertFalse(conflicted_stopped.done())
        await phile.asyncio.wait_for(
            self.launcher_registry.start("something")
        )
        await phile.asyncio.wait_for(conflict_stopped)
        await phile.asyncio.wait_for(conflicted_stopped)

    async def test_start__starts_after_dependencies(self) -> None:
        dependency_started = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()
            await asyncio.Event().wait()

        self.launcher_registry.add_nowait(
            "dependent",
            {
                "exec_start": [asyncio.Event().wait],
                "after": {"dependency"},
                "binds_to": {"dependency"},
            },
        )
        self.launcher_registry.add_nowait(
            "dependency",
            {
                "exec_start": [dependency_exec_start],
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependent")
        )
        await phile.asyncio.wait_for(dependency_started.wait())

    async def test_start__does_not_start_afters_without_binds_to(
        self,
    ) -> None:
        dependency_started = asyncio.Event()
        dependent_started = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()
            await asyncio.Event().wait()

        async def dependent_exec_start() -> None:
            dependent_started.set()
            await asyncio.Event().wait()

        self.launcher_registry.add_nowait(
            "dependency",
            {
                "exec_start": [dependency_exec_start],
            },
        )
        self.launcher_registry.add_nowait(
            "dependent",
            {
                "exec_start": [dependent_exec_start],
                "after": {"dependency"},
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependent")
        )
        await phile.asyncio.wait_for(dependent_started.wait())
        self.assertFalse(dependency_started.is_set())

    async def test_start__rewinds_if_exec_start_raises(self) -> None:
        name = "exec_start_raises"

        async def divide_by_zero() -> None:
            1 / 0  # pylint: disable=pointless-statement

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [divide_by_zero],
                "type": phile.launcher.Type.FORKING,
            },
        )
        with self.assertRaises(ZeroDivisionError):
            await phile.asyncio.wait_for(
                self.launcher_registry.start(name)
            )

    async def test_stop__cancel_main_task_if_not_done(self) -> None:
        name = "simple_stop"
        task_to_cancel = asyncio.create_task(asyncio.Event().wait())
        self.launcher_registry.add_nowait(
            name, {"exec_start": [lambda: task_to_cancel]}
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))
        self.assertTrue(task_to_cancel.cancelled())

    async def test_stop__runs_exec_stop_if_given(self) -> None:
        name = "stop_with_exec_stop"
        stop = asyncio.Event()

        async def stopper() -> None:
            stop.set()

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [stop.wait],
                "exec_stop": [stopper],
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))
        self.assertTrue(stop.is_set())

    async def test_stop__returns_if_not_running(self) -> None:
        name = "starting_after_start"
        stop_launcher = asyncio.Event()
        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [stop_launcher.wait],
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))

    async def test_stop__awaits_if_already_stopping(self) -> None:
        name = "double_stop"
        stop = asyncio.Event()
        continue_stopper = asyncio.Event()

        async def stopper() -> None:
            await continue_stopper.wait()
            stop.set()

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [stop.wait],
                "exec_stop": [stopper],
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        stop_1 = self.launcher_registry.stop(name)
        await asyncio.sleep(0)
        stop_2 = self.launcher_registry.stop(name)
        await asyncio.sleep(0)
        self.assertFalse(stop_1.done())
        self.assertFalse(stop_2.done())
        continue_stopper.set()
        await phile.asyncio.wait_for(stop_2)
        await phile.asyncio.wait_for(stop_1)

    async def test_is_running__is_false_after_stop(self) -> None:
        name = "simple_stop"
        self.launcher_registry.add_nowait(
            name, {"exec_start": [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))
        self.assertFalse(self.launcher_registry.is_running(name))

    async def test_start__awaits_if_still_stopping(self) -> None:
        name = "start_stop_start"
        started = asyncio.Event()
        stop_paused = asyncio.Event()
        stop = asyncio.Event()
        continue_stopper = asyncio.Event()

        async def starter() -> None:
            started.set()
            await stop.wait()

        async def stopper() -> None:
            stop_paused.set()
            await continue_stopper.wait()
            stop.set()

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [starter],
                "exec_stop": [stopper],
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        started.clear()
        stop_task = self.launcher_registry.stop(name)
        await asyncio.sleep(0)
        start_task = self.launcher_registry.start(name)
        await phile.asyncio.wait_for(stop_paused.wait())
        self.assertFalse(start_task.done())
        self.assertFalse(stop_task.done())
        self.assertFalse(started.is_set())
        continue_stopper.set()
        await phile.asyncio.wait_for(start_task)
        self.assertTrue(stop_task.done())
        await phile.asyncio.wait_for(stop_task)

    async def test_stop__cancels_if_still_starting(self) -> None:
        name = "start_stop"
        started = asyncio.Event()
        stop_paused = asyncio.Event()
        stop = asyncio.Event()
        continue_stopper = asyncio.Event()

        async def starter() -> None:
            started.set()
            await stop.wait()

        async def stopper() -> None:
            stop_paused.set()
            await continue_stopper.wait()
            stop.set()

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [starter],
                "exec_stop": [stopper],
                "type": phile.launcher.Type.FORKING,
            },
        )
        start_task = self.launcher_registry.start(name)
        await asyncio.sleep(0)
        stop_task = self.launcher_registry.stop(name)
        with self.assertRaises(asyncio.CancelledError):
            await phile.asyncio.wait_for(start_task)
        await phile.asyncio.wait_for(stop_task)

    async def test_stop__stops_bind_to_inverse_entries(self) -> None:
        dependent_started = asyncio.Event()
        dependent_stopped = asyncio.Event()

        async def dependent_exec_start() -> None:
            dependent_started.set()
            await asyncio.Event().wait()

        async def dependent_exec_stop() -> None:
            dependent_stopped.set()

        self.launcher_registry.add_nowait(
            "dependent",
            {
                "exec_start": [dependent_exec_start],
                "exec_stop": [dependent_exec_stop],
                "binds_to": {"dependency"},
            },
        )
        self.launcher_registry.add_nowait(
            "dependency",
            {
                "exec_start": [asyncio.Event().wait],
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependent")
        )
        await phile.asyncio.wait_for(dependent_started.wait())
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependency")
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.stop("dependency")
        )
        await phile.asyncio.wait_for(dependent_stopped.wait())

    async def test_stop__stops_after_dependents(self) -> None:
        dependency_started = asyncio.Event()
        dependency_stopped = asyncio.Event()
        dependent_stopped = asyncio.Event()
        dependent_exec_stop_continue = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()
            await asyncio.Event().wait()

        async def dependency_exec_stop() -> None:
            dependency_stopped.set()

        async def dependent_exec_stop() -> None:
            dependent_stopped.set()
            await dependent_exec_stop_continue.wait()

        self.launcher_registry.add_nowait(
            "dependent",
            {
                "exec_start": [asyncio.Event().wait],
                "exec_stop": [dependent_exec_stop],
                "after": {"dependency"},
                "binds_to": {"dependency"},
            },
        )
        self.launcher_registry.add_nowait(
            "dependency",
            {
                "exec_start": [dependency_exec_start],
                "exec_stop": [dependency_exec_stop],
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependent")
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependency")
        )
        await phile.asyncio.wait_for(dependency_started.wait())
        dependency_stop_task = self.launcher_registry.stop("dependency")
        await phile.asyncio.wait_for(dependent_stopped.wait())
        self.assertFalse(dependency_stopped.is_set())
        dependent_exec_stop_continue.set()
        await phile.asyncio.wait_for(dependency_stop_task)
        await phile.asyncio.wait_for(dependent_stopped.wait())

    async def test_stop__does_not_stop_afters_without_binds_to(
        self,
    ) -> None:
        create_future = asyncio.get_running_loop().create_future
        dependency_started = create_future()
        dependency_stopped = create_future()
        dependent_stopped = create_future()
        self.launcher_registry.add_nowait(
            "dependency",
            {
                "exec_start": [
                    make_nullary_async(
                        dependency_started.set_result, None
                    )
                ],
                "exec_stop": [
                    make_nullary_async(
                        dependency_stopped.set_result, None
                    )
                ],
            },
        )
        self.launcher_registry.add_nowait(
            "dependent",
            {
                "exec_start": [create_future],
                "exec_stop": [
                    make_nullary_async(
                        dependent_stopped.set_result, None
                    )
                ],
                "after": {"dependency"},
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependency")
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("dependent")
        )
        await phile.asyncio.wait_for(dependency_started)
        await phile.asyncio.wait_for(
            self.launcher_registry.stop("dependency")
        )
        await phile.asyncio.wait_for(dependency_stopped)
        self.assertFalse(dependent_stopped.done())

    async def test_start__emits_events(self) -> None:
        entry_name = "start_emits_events"
        self.launcher_registry.add_nowait(
            entry_name, {"exec_start": [noop]}
        )
        view = self.launcher_registry.event_queue.__aiter__()
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name)
        )
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(
            message,
            phile.launcher.Event(
                type=phile.launcher.EventType.START,
                entry_name=entry_name,
            ),
        )

    async def test_stop__emits_events(self) -> None:
        entry_name = "remove_emits_events"
        self.launcher_registry.add_nowait(
            entry_name, {"exec_start": [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name)
        )
        view = self.launcher_registry.event_queue.__aiter__()
        await phile.asyncio.wait_for(
            self.launcher_registry.stop(entry_name)
        )
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(
            message,
            phile.launcher.Event(
                type=phile.launcher.EventType.STOP, entry_name=entry_name
            ),
        )

    async def test_remove__stops_launcher(self) -> None:
        name = "to_be_stopped_when_deregistering"
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def exec_start() -> None:
            started.set()
            await asyncio.Event().wait()

        async def exec_stop() -> None:
            stopped.set()

        self.launcher_registry.add_nowait(
            name,
            {
                "exec_start": [exec_start],
                "exec_stop": [exec_stop],
            },
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(started.wait())
        await phile.asyncio.wait_for(self.launcher_registry.remove(name))
        await phile.asyncio.wait_for(stopped.wait())

    async def test_remove_nowait__raises_if_running(self) -> None:
        entry_name = "remove_nowait_raises_if_running"
        self.launcher_registry.add_nowait(
            entry_name,
            {"exec_start": [asyncio.get_running_loop().create_future]},
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name)
        )
        with self.assertRaises(RuntimeError):
            self.launcher_registry.remove_nowait(entry_name)

    async def test_start__shutdown_target_stops_launchers_by_default(
        self,
    ) -> None:
        entry_name = "shutdown_target_stops_launchers"
        self.launcher_registry.add_nowait(
            entry_name,
            {
                "default_dependencies": True,
                "exec_start": [asyncio.get_running_loop().create_future],
            },
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name)
        )
        self.assertTrue(self.launcher_registry.is_running(entry_name))
        await phile.asyncio.wait_for(
            self.launcher_registry.start("phile_shutdown.target")
        )
        self.assertFalse(self.launcher_registry.is_running(entry_name))


class UsesRegistry(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.capability_registry: phile.capability.Registry
        self.launcher_registry: phile.launcher.Registry

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.launcher_registry = (
            launcher_registry
        ) = phile.launcher.Registry()
        self.capability_registry = launcher_registry.capability_registry
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            launcher_registry.start("phile_shutdown.target"),
        )
