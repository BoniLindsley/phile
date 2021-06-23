#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.launcher`
--------------------------
"""

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

_T = typing.TypeVar('_T')


class TestNameInUse(unittest.TestCase):
    """Tests :func:`~phile.launcher.NameInUse`."""

    def test_check_is_runtime_error(self) -> None:
        self.assertIsInstance(phile.launcher.NameInUse(), RuntimeError)


def make_nullary_async(
    function: collections.abc.Callable[..., _T],
    /,
    *args: typing.Any,
    **kwargs: typing.Any,
) -> collections.abc.Callable[[], collections.Awaitable[_T]]:
    """
    Returns a coroutine function that calls the given function.

    Returns a nullary function. That is, it is not a coroutine object.
    To await for it, use ``await make_async(f)()``.
    """

    async def wrapper_coroutine() -> _T:
        return function(*args, **kwargs)

    return wrapper_coroutine


async def noop() -> None:
    pass


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
    """Tests :func:`~phile.launcher.OneToManyTwoWayDict`."""

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
        self.assertFalse(self.launcher_database.contains('not_there'))

    async def test_add_with_minimal_data(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'minimal', {'exec_start': [noop]}
            )
        )

    async def test_add_fails_if_name_already_added(self) -> None:
        name = 'reused'
        await phile.asyncio.wait_for(
            self.launcher_database.add(name, {'exec_start': [noop]})
        )
        with self.assertRaises(phile.launcher.NameInUse):
            await phile.asyncio.wait_for(
                self.launcher_database.add(name, {'exec_start': [noop]})
            )

    async def test_contains_after_add(self) -> None:
        name = 'checked'
        await phile.asyncio.wait_for(
            self.launcher_database.add(name, {'exec_start': [noop]})
        )
        self.assertTrue(self.launcher_database.contains(name))

    async def test_add_fails_without_exec_start(self) -> None:
        with self.assertRaises(phile.launcher.MissingDescriptorData):
            await phile.asyncio.wait_for(
                self.launcher_database.add('no_exec_start', {})
            )

    async def test_add_updates_afters(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent',
                {
                    'exec_start': [noop],
                    'after': {'dependency'},
                },
            )
        )
        self.assertEqual(
            self.launcher_database.after['dependent'],
            {'dependency'},
        )
        self.assertEqual(
            self.launcher_database.after.inverses['dependency'],
            {'dependent'},
        )

    async def test_add_binds_to_creates_inverses(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent',
                {
                    'exec_start': [noop],
                    'binds_to': {'bind_target'},
                },
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'bind_target',
                {'exec_start': [noop]},
            )
        )
        self.assertEqual(
            self.launcher_database.binds_to['dependent'],
            {'bind_target'},
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses['bind_target'],
            {'dependent'},
        )

    async def test_add_binds_to_adds_to_existing_inverses(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent_1', {
                    'exec_start': [noop],
                    'binds_to': {'bind_target'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'bind_target', {'exec_start': [noop]}
            )
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses['bind_target'],
            {'dependent_1'},
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent_2', {
                    'exec_start': [noop],
                    'binds_to': {'bind_target'},
                }
            )
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses['bind_target'],
            {'dependent_1', 'dependent_2'},
        )

    async def test_add__with_before_creates_inverses(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'first',
                {
                    'exec_start': [noop],
                    'before': {'second'},
                },
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add('second', {'exec_start': [noop]})
        )
        self.assertEqual(
            self.launcher_database.before['first'],
            {'second'},
        )
        self.assertEqual(
            self.launcher_database.before.inverses['second'],
            {'first'},
        )

    async def test_add__with_conflicts_creates_inverses(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'something',
                {
                    'exec_start': [noop],
                    'conflicts': {'conflict'},
                },
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'conflict', {'exec_start': [noop]}
            )
        )
        self.assertEqual(
            self.launcher_database.conflicts['something'],
            {'conflict'},
        )
        self.assertEqual(
            self.launcher_database.conflicts.inverses['conflict'],
            {'something'},
        )

    async def test_add__with_default_dependencies_adds_dependencies(
        self
    ) -> None:
        database = self.launcher_database
        await phile.asyncio.wait_for(
            database.add(
                'something',
                {
                    'exec_start': [noop],
                    'default_dependencies': True
                },
            )
        )
        self.assertEqual(
            database.default_dependencies['something'], True
        )
        self.assertEqual(
            database.conflicts['something'], {'phile_shutdown.target'}
        )
        self.assertEqual(
            database.before['something'], {'phile_shutdown.target'}
        )

        await phile.asyncio.wait_for(
            database.add(
                'else',
                {
                    'exec_start': [noop],
                    'default_dependencies': False
                },
            )
        )
        self.assertEqual(database.default_dependencies['else'], False)
        self.assertEqual(database.conflicts['else'], set())
        self.assertEqual(database.before['else'], set())

    async def test_remove(self) -> None:
        name = 'to_be_removed'
        await phile.asyncio.wait_for(
            self.launcher_database.add(name, {'exec_start': [noop]})
        )
        await phile.asyncio.wait_for(self.launcher_database.remove(name))

    async def test_is_contains_after_remove(self) -> None:
        name = 'unchecked'
        await phile.asyncio.wait_for(
            self.launcher_database.add(name, {'exec_start': [noop]})
        )
        await phile.asyncio.wait_for(self.launcher_database.remove(name))
        self.assertFalse(self.launcher_database.contains(name))

    async def test_remove_ignores_if_not_added(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.remove('not_added_unit')
        )

    async def test_remove_with_after_removes_from_inverses(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent_1', {
                    'exec_start': [noop],
                    'after': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent_2', {
                    'exec_start': [noop],
                    'after': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {'exec_start': [noop]}
            )
        )
        self.assertEqual(
            self.launcher_database.after.inverses['dependency'],
            {'dependent_1', 'dependent_2'},
        )
        await phile.asyncio.wait_for(
            self.launcher_database.remove('dependent_1')
        )
        self.assertEqual(
            self.launcher_database.after.inverses['dependency'],
            {'dependent_2'},
        )

    async def test_remove__with_after_removes_inverse_if_it_empties(
        self
    ) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [noop],
                    'after': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {'exec_start': [noop]}
            )
        )
        self.assertEqual(
            self.launcher_database.after.inverses['dependency'],
            {'dependent'},
        )
        await phile.asyncio.wait_for(
            self.launcher_database.remove('dependent')
        )
        self.assertNotIn(
            'bind_target', self.launcher_database.after.inverses
        )

    async def test_remove_unbinds_from_inverses(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent_1', {
                    'exec_start': [noop],
                    'binds_to': {'bind_target'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent_2', {
                    'exec_start': [noop],
                    'binds_to': {'bind_target'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'bind_target', {'exec_start': [noop]}
            )
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses['bind_target'],
            {'dependent_1', 'dependent_2'},
        )
        await phile.asyncio.wait_for(
            self.launcher_database.remove('dependent_1')
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses['bind_target'],
            {'dependent_2'},
        )

    async def test_remove_removes_inverses_if_it_empties(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [noop],
                    'binds_to': {'bind_target'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'bind_target', {'exec_start': [noop]}
            )
        )
        self.assertEqual(
            self.launcher_database.binds_to.inverses['bind_target'],
            {'dependent'},
        )
        await phile.asyncio.wait_for(
            self.launcher_database.remove('dependent')
        )
        self.assertNotIn(
            'bind_target', self.launcher_database.binds_to.inverses
        )

    async def test_add_emits_events(self) -> None:
        entry_name = 'add_emits_events'
        view = self.launcher_database.event_publishers[
            phile.launcher.Database.add].__aiter__()
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                entry_name, {'exec_start': [noop]}
            )
        )
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(message, entry_name)

    async def test_remove_emits_events(self) -> None:
        entry_name = 'remove_emits_events'
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                entry_name, {'exec_start': [noop]}
            )
        )
        view = self.launcher_database.event_publishers[
            phile.launcher.Database.remove].__aiter__()
        await phile.asyncio.wait_for(
            self.launcher_database.remove(entry_name)
        )
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(message, entry_name)


class TestRegistry(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_database: phile.launcher.Database
        self.launcher_registry: phile.launcher.Registry

    def setUp(self) -> None:
        super().setUp()
        self.launcher_registry = launcher_registry = (
            phile.launcher.Registry()
        )
        self.launcher_database = launcher_registry.database

    def test_available_attributes(self) -> None:
        self.assertEqual(
            self.launcher_registry.database,
            self.launcher_database,
        )

    async def test_start_simple_runs_exec_start(self) -> None:
        name = 'simple_run'
        ran = asyncio.Event()

        async def set_and_wait() -> None:
            ran.set()
            await asyncio.Event().wait()

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {'exec_start': [set_and_wait]}
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        self.assertTrue(ran.is_set())

    async def test_start_simple_runs_exec_start_without_awaiting_it(
        self
    ) -> None:
        name = 'simple_run_not_awaited'
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {'exec_start': [asyncio.Event().wait]}
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))

    async def test_start_exec_type_yields_once(self) -> None:
        name = 'exec_run_with_exec_type'
        counter, awaiter = create_awaiter(limit=4)
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [awaiter],
                    'type': phile.launcher.Type.EXEC,
                }
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        self.assertGreaterEqual(counter.value, 1)

    async def test_start_forking_waits_for_completion(self) -> None:
        name = 'exec_forking'
        limit = 16
        counter, awaiter = create_awaiter(limit=limit)

        async def forker() -> asyncio.Task[None]:
            await awaiter()
            return asyncio.create_task(asyncio.sleep(0))

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [forker],
                    'type': phile.launcher.Type.FORKING,
                }
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        # There is not guarantee that the forker is awaited for,
        # but the limit should be sufficiently high in most cases.
        self.assertGreaterEqual(counter.value, limit)

    async def test_start_returns_if_running(self) -> None:
        name = 'starting_after_start'
        stop_launcher = asyncio.Event()
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [stop_launcher.wait],
                }
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.start(name))

    async def test_start_awaits_if_already_starting(self) -> None:
        name = 'double_start'
        continue_forker = asyncio.Event()

        async def forker() -> asyncio.Task[None]:
            await continue_forker.wait()
            return asyncio.create_task(asyncio.sleep(0))

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [forker],
                    'type': phile.launcher.Type.FORKING,
                }
            )
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

    async def test_is_running_after_start(self) -> None:
        name = 'run_check'
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {'exec_start': [asyncio.Event().wait]}
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        self.assertTrue(self.launcher_registry.is_running(name))

    async def test_start_starts_binds_to(self) -> None:
        create_future = asyncio.get_running_loop().create_future
        dependency_started = create_future()
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [create_future],
                    'binds_to': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {
                    'exec_start': [
                        make_nullary_async(
                            dependency_started.set_result, 0
                        ),
                    ],
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependent')
        )
        await phile.asyncio.wait_for(dependency_started)

    async def test_start__stops_conflicts_first(self) -> None:
        loop = asyncio.get_running_loop()
        conflict_stopped = loop.create_future()
        conflicted_stopped = loop.create_future()

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'something', {
                    'exec_start': [asyncio.Event().wait],
                    'conflicts': {'conflict'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'conflict', {
                    'exec_start': [loop.create_future],
                    'exec_stop': [
                        make_nullary_async(
                            conflict_stopped.set_result, 0
                        )
                    ],
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'conflicted', {
                    'conflicts': {'something'},
                    'exec_start': [loop.create_future],
                    'exec_stop': [
                        make_nullary_async(
                            conflicted_stopped.set_result, 0
                        )
                    ],
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('conflict')
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('conflicted')
        )
        self.assertTrue(self.launcher_registry.is_running('conflict'))
        self.assertTrue(self.launcher_registry.is_running('conflicted'))
        self.assertFalse(conflict_stopped.done())
        self.assertFalse(conflicted_stopped.done())
        await phile.asyncio.wait_for(
            self.launcher_registry.start('something')
        )
        await phile.asyncio.wait_for(conflict_stopped)
        await phile.asyncio.wait_for(conflicted_stopped)

    async def test_start_starts_after_dependencies(self) -> None:
        dependency_started = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()
            await asyncio.Event().wait()

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [asyncio.Event().wait],
                    'after': {'dependency'},
                    'binds_to': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {
                    'exec_start': [dependency_exec_start],
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependent')
        )
        await phile.asyncio.wait_for(dependency_started.wait())

    async def test_start_does_not_start_afters_without_binds_to(
        self
    ) -> None:
        dependency_started = asyncio.Event()
        dependent_started = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()
            await asyncio.Event().wait()

        async def dependent_exec_start() -> None:
            dependent_started.set()
            await asyncio.Event().wait()

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {
                    'exec_start': [dependency_exec_start],
                }
            )
        )

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [dependent_exec_start],
                    'after': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependent')
        )
        await phile.asyncio.wait_for(dependent_started.wait())
        self.assertFalse(dependency_started.is_set())

    async def test_start_rewinds_if_exec_start_raises(self) -> None:
        name = 'exec_start_raises'

        async def divide_by_zero() -> None:
            1 / 0  # pylint: disable=pointless-statement

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [divide_by_zero],
                    'type': phile.launcher.Type.FORKING,
                }
            )
        )
        with self.assertRaises(ZeroDivisionError):
            await phile.asyncio.wait_for(
                self.launcher_registry.start(name)
            )

    async def test_stop_cancel_main_task_if_not_done(self) -> None:
        name = 'simple_stop'
        task_to_cancel = asyncio.create_task(asyncio.Event().wait())
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {'exec_start': [lambda: task_to_cancel]}
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))
        self.assertTrue(task_to_cancel.cancelled())

    async def test_stop_runs_exec_stop_if_given(self) -> None:
        name = 'stop_with_exec_stop'
        stop = asyncio.Event()

        async def stopper() -> None:
            stop.set()

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [stop.wait],
                    'exec_stop': [stopper],
                }
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))
        self.assertTrue(stop.is_set())

    async def test_stop_returns_if_not_running(self) -> None:
        name = 'starting_after_start'
        stop_launcher = asyncio.Event()
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [stop_launcher.wait],
                }
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))

    async def test_stop_awaits_if_already_stopping(self) -> None:
        name = 'double_stop'
        stop = asyncio.Event()
        continue_stopper = asyncio.Event()

        async def stopper() -> None:
            await continue_stopper.wait()
            stop.set()

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [stop.wait],
                    'exec_stop': [stopper],
                }
            )
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

    async def test_is_not_running_after_stop(self) -> None:
        name = 'simple_stop'
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {'exec_start': [asyncio.Event().wait]}
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))
        self.assertFalse(self.launcher_registry.is_running(name))

    async def test_start_awaits_if_still_stopping(self) -> None:
        name = 'start_stop_start'
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

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [starter],
                    'exec_stop': [stopper],
                }
            )
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

    async def test_stop_cancels_if_still_starting(self) -> None:
        name = 'start_stop'
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

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                name, {
                    'exec_start': [starter],
                    'exec_stop': [stopper],
                    'type': phile.launcher.Type.FORKING,
                }
            )
        )
        start_task = self.launcher_registry.start(name)
        await asyncio.sleep(0)
        stop_task = self.launcher_registry.stop(name)
        with self.assertRaises(asyncio.CancelledError):
            await phile.asyncio.wait_for(start_task)
        await phile.asyncio.wait_for(stop_task)

    async def test_stop_stops_bind_to_inverse_entries(self) -> None:
        dependent_started = asyncio.Event()
        dependent_stopped = asyncio.Event()

        async def dependent_exec_start() -> None:
            dependent_started.set()
            await asyncio.Event().wait()

        async def dependent_exec_stop() -> None:
            dependent_stopped.set()

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [dependent_exec_start],
                    'exec_stop': [dependent_exec_stop],
                    'binds_to': {'dependency'}
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {
                    'exec_start': [asyncio.Event().wait],
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependent')
        )
        await phile.asyncio.wait_for(dependent_started.wait())
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependency')
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.stop('dependency')
        )
        await phile.asyncio.wait_for(dependent_stopped.wait())

    async def test_stop_stops_after_dependents(self) -> None:
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

        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [asyncio.Event().wait],
                    'exec_stop': [dependent_exec_stop],
                    'after': {'dependency'},
                    'binds_to': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {
                    'exec_start': [dependency_exec_start],
                    'exec_stop': [dependency_exec_stop],
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependent')
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependency')
        )
        await phile.asyncio.wait_for(dependency_started.wait())
        dependency_stop_task = self.launcher_registry.stop('dependency')
        await phile.asyncio.wait_for(dependent_stopped.wait())
        self.assertFalse(dependency_stopped.is_set())
        dependent_exec_stop_continue.set()
        await phile.asyncio.wait_for(dependency_stop_task)
        await phile.asyncio.wait_for(dependent_stopped.wait())

    async def test_stop_does_not_stop_afters_without_binds_to(
        self
    ) -> None:
        create_future = asyncio.get_running_loop().create_future
        dependency_started = create_future()
        dependency_stopped = create_future()
        dependent_stopped = create_future()
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependency', {
                    'exec_start': [
                        make_nullary_async(
                            dependency_started.set_result, None
                        )
                    ],
                    'exec_stop': [
                        make_nullary_async(
                            dependency_stopped.set_result, None
                        )
                    ],
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                'dependent', {
                    'exec_start': [create_future],
                    'exec_stop': [
                        make_nullary_async(
                            dependent_stopped.set_result, None
                        )
                    ],
                    'after': {'dependency'},
                }
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependency')
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start('dependent')
        )
        await phile.asyncio.wait_for(dependency_started)
        await phile.asyncio.wait_for(
            self.launcher_registry.stop('dependency')
        )
        await phile.asyncio.wait_for(dependency_stopped)
        self.assertFalse(dependent_stopped.done())

    async def test_start_emits_events(self) -> None:
        entry_name = 'start_emits_events'
        view = self.launcher_registry.event_publishers[
            phile.launcher.Registry.start].__aiter__()
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                entry_name, {'exec_start': [noop]}
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name)
        )
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(message, entry_name)

    async def test_stop_emits_events(self) -> None:
        entry_name = 'remove_emits_events'
        await phile.asyncio.wait_for(
            self.launcher_database.add(
                entry_name, {'exec_start': [asyncio.Event().wait]}
            )
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name)
        )
        view = self.launcher_registry.event_publishers[
            phile.launcher.Registry.stop].__aiter__()
        await phile.asyncio.wait_for(
            self.launcher_registry.stop(entry_name)
        )
        message = await phile.asyncio.wait_for(view.__anext__())
        self.assertEqual(message, entry_name)

    async def test_remove_stops_launcher(self) -> None:
        name = 'to_be_stopped_when_deregistering'
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def exec_start() -> None:
            started.set()
            await asyncio.Event().wait()

        async def exec_stop() -> None:
            stopped.set()

        await phile.asyncio.wait_for(
            self.launcher_registry.database.add(
                name, {
                    'exec_start': [exec_start],
                    'exec_stop': [exec_stop],
                }
            )
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(started.wait())
        await phile.asyncio.wait_for(
            self.launcher_registry.database.remove(name)
        )
        await phile.asyncio.wait_for(stopped.wait())


class TestProvideRegistry(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.launcher.provide_registry`."""

    async def test_adds_registry(self) -> None:
        capability_registry = phile.capability.Registry()
        async with phile.launcher.provide_registry(
            capability_registry=capability_registry,
        ) as launcher_registry:
            self.assertIsInstance(
                launcher_registry,
                phile.launcher.Registry,
            )
            self.assertIn(phile.launcher.Registry, capability_registry)
        self.assertNotIn(phile.launcher.Registry, capability_registry)


class UsesRegistry(unittest.IsolatedAsyncioTestCase):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.capability_registry: phile.capability.Registry
        self.launcher_registry: phile.launcher.Registry

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.capability_registry = phile.capability.Registry()
        registry_cm = phile.launcher.provide_registry(
            capability_registry=self.capability_registry,
        )
        # pylint: disable=no-member
        # Not sure why Pylint thinks the cm is just an AsyncGenerator.
        self.launcher_registry = await registry_cm.__aenter__()
        self.addAsyncCleanup(registry_cm.__aexit__, None, None, None)
