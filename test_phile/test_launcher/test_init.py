#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.launcher`
--------------------------
"""

# Standard libraries.
import asyncio
import dataclasses
import functools
import typing
import unittest
import unittest.mock

# Internal packages.
import phile.asyncio
import phile.launcher


class TestNameInUse(unittest.TestCase):
    """Tests :func:`~phile.launcher.NameInUse`."""

    def test_check_is_runtime_error(self) -> None:
        self.assertIsInstance(phile.launcher.NameInUse(), RuntimeError)


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


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.launcher.Database`."""

    def setUp(self) -> None:
        super().setUp()
        self.launcher_database = phile.launcher.Database()

    def test_contains_on_empty_database(self) -> None:
        self.assertFalse(self.launcher_database.contains('not_there'))

    def test_add_with_minimal_data(self) -> None:
        self.launcher_database.add('minimal', {'exec_start': [noop]})

    def test_add_fails_if_name_already_added(self) -> None:
        name = 'reused'
        self.launcher_database.add(name, {'exec_start': [noop]})
        with self.assertRaises(phile.launcher.NameInUse):
            self.launcher_database.add(name, {'exec_start': [noop]})

    def test_contains_after_add(self) -> None:
        name = 'checked'
        self.launcher_database.add(name, {'exec_start': [noop]})
        self.assertTrue(self.launcher_database.contains(name))

    def test_add_fails_without_exec_start(self) -> None:
        with self.assertRaises(phile.launcher.MissingDescriptorData):
            self.launcher_database.add('no_exec_start', {})

    def test_add_updates_afters(self) -> None:
        self.launcher_database.add(
            'dependent',
            {
                'exec_start': [noop],
                'after': {'dependency'},
            },
        )
        self.assertEqual(
            self.launcher_database.after['dependent'],
            {'dependency'},
        )
        self.assertEqual(
            self.launcher_database.stop_after['dependency'],
            {'dependent'},
        )

    def test_add_binds_to_creates_bound_by(self) -> None:
        self.launcher_database.add(
            'dependent',
            {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            },
        )
        self.launcher_database.add(
            'bind_target',
            {'exec_start': [noop]},
        )
        self.assertEqual(
            self.launcher_database.binds_to['dependent'],
            {'bind_target'},
        )
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent'},
        )

    def test_add_binds_to_adds_to_existing_bound_by(self) -> None:
        self.launcher_database.add(
            'dependent_1', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add('bind_target', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_1'},
        )
        self.launcher_database.add(
            'dependent_2', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_1', 'dependent_2'},
        )

    def test_remove(self) -> None:
        name = 'to_be_removed'
        self.launcher_database.add(name, {'exec_start': [noop]})
        self.launcher_database.remove(name)

    def test_is_contains_after_remove(self) -> None:
        name = 'unchecked'
        self.launcher_database.add(name, {'exec_start': [noop]})
        self.launcher_database.remove(name)
        self.assertFalse(self.launcher_database.contains(name))

    def test_remove_ignores_if_not_added(self) -> None:
        self.launcher_database.remove('not_added_unit')

    def test_remove_with_after_removes_from_stop_after(self) -> None:
        self.launcher_database.add(
            'dependent_1', {
                'exec_start': [noop],
                'after': {'dependency'},
            }
        )
        self.launcher_database.add(
            'dependent_2', {
                'exec_start': [noop],
                'after': {'dependency'},
            }
        )
        self.launcher_database.add('dependency', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.stop_after['dependency'],
            {'dependent_1', 'dependent_2'},
        )
        self.launcher_database.remove('dependent_1')
        self.assertEqual(
            self.launcher_database.stop_after['dependency'],
            {'dependent_2'},
        )

    def test_remove__with_after_removes_stop_after_if_it_empties(
        self
    ) -> None:
        self.launcher_database.add(
            'dependent', {
                'exec_start': [noop],
                'after': {'dependency'},
            }
        )
        self.launcher_database.add('dependency', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.stop_after['dependency'],
            {'dependent'},
        )
        self.launcher_database.remove('dependent')
        self.assertNotIn(
            'bind_target', self.launcher_database.stop_after
        )

    def test_remove_unbinds_from_bound_by(self) -> None:
        self.launcher_database.add(
            'dependent_1', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add(
            'dependent_2', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add('bind_target', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_1', 'dependent_2'},
        )
        self.launcher_database.remove('dependent_1')
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent_2'},
        )

    def test_remove_removes_bound_by_if_it_empties(self) -> None:
        self.launcher_database.add(
            'dependent', {
                'exec_start': [noop],
                'binds_to': {'bind_target'},
            }
        )
        self.launcher_database.add('bind_target', {'exec_start': [noop]})
        self.assertEqual(
            self.launcher_database.bound_by['bind_target'],
            {'dependent'},
        )
        self.launcher_database.remove('dependent')
        self.assertNotIn('bind_target', self.launcher_database.bound_by)

    async def test_add_emits_events(self) -> None:
        entry_name = 'add_emits_events'
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_database.event_publisher,
        )
        self.launcher_database.add(entry_name, {'exec_start': [noop]})
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.Database.Event(
                source=self.launcher_database,
                type=phile.launcher.Database.add,
                entry_name=entry_name,
            ),
        )

    async def test_remove_emits_events(self) -> None:
        entry_name = 'remove_emits_events'
        self.launcher_database.add(entry_name, {'exec_start': [noop]})
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_database.event_publisher,
        )
        self.launcher_database.remove(entry_name)
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.Database.Event(
                source=self.launcher_database,
                type=phile.launcher.Database.remove,
                entry_name=entry_name,
            ),
        )


class TestStateMachine(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.launcher.StateMachine`."""

    def setUp(self) -> None:
        super().setUp()
        self.launcher_database = phile.launcher.Database()
        self.launcher_state_machine = phile.launcher.StateMachine(
            database=self.launcher_database
        )

    async def test_start_simple_runs_exec_start(self) -> None:
        name = 'simple_run'
        ran = asyncio.Event()

        async def set_and_wait() -> None:
            ran.set()
            await asyncio.Event().wait()

        self.launcher_database.add(name, {'exec_start': [set_and_wait]})
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        self.assertTrue(ran.is_set())

    async def test_start_simple_runs_exec_start_without_awaiting_it(
        self
    ) -> None:
        name = 'simple_run_not_awaited'
        self.launcher_database.add(
            name, {'exec_start': [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )

    async def test_start_exec_type_yields_once(self) -> None:
        name = 'exec_run_with_exec_type'
        counter, awaiter = create_awaiter(limit=4)
        self.launcher_database.add(
            name, {
                'exec_start': [awaiter],
                'type': phile.launcher.Type.EXEC,
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        self.assertGreaterEqual(counter.value, 1)

    async def test_start_forking_waits_for_completion(self) -> None:
        name = 'exec_forking'
        limit = 16
        counter, awaiter = create_awaiter(limit=limit)

        async def forker() -> asyncio.Task[None]:
            await awaiter()
            return asyncio.create_task(asyncio.sleep(0))

        self.launcher_database.add(
            name, {
                'exec_start': [forker],
                'type': phile.launcher.Type.FORKING,
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        # There is not guarantee that the forker is awaited for,
        # but the limit should be sufficiently high in most cases.
        self.assertGreaterEqual(counter.value, limit)

    async def test_start_returns_if_running(self) -> None:
        name = 'starting_after_start'
        stop_launcher = asyncio.Event()
        self.launcher_database.add(
            name, {
                'exec_start': [stop_launcher.wait],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )

    async def test_start_awaits_if_already_starting(self) -> None:
        name = 'double_start'
        continue_forker = asyncio.Event()

        async def forker() -> asyncio.Task[None]:
            await continue_forker.wait()
            return asyncio.create_task(asyncio.sleep(0))

        self.launcher_database.add(
            name, {
                'exec_start': [forker],
                'type': phile.launcher.Type.FORKING,
            }
        )
        start_1 = asyncio.create_task(
            self.launcher_state_machine.start(name)
        )
        await asyncio.sleep(0)
        start_2 = asyncio.create_task(
            self.launcher_state_machine.start(name)
        )
        await asyncio.sleep(0)
        self.assertFalse(start_1.done())
        self.assertFalse(start_2.done())
        continue_forker.set()
        await phile.asyncio.wait_for(start_2)
        await phile.asyncio.wait_for(start_1)

    async def test_is_running_after_start(self) -> None:
        name = 'run_check'
        self.launcher_database.add(
            name, {'exec_start': [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        self.assertTrue(self.launcher_state_machine.is_running(name))

    async def test_start_starts_binds_to(self) -> None:
        dependency_started = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()
            await asyncio.Event().wait()

        self.launcher_database.add(
            'dependent', {
                'exec_start': [asyncio.Event().wait],
                'binds_to': {'dependency'}
            }
        )
        self.launcher_database.add(
            'dependency', {
                'exec_start': [dependency_exec_start],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependent')
        )
        await phile.asyncio.wait_for(dependency_started.wait())

    async def test_start_starts_after_dependencies(self) -> None:
        dependency_started = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()
            await asyncio.Event().wait()

        self.launcher_database.add(
            'dependent', {
                'exec_start': [asyncio.Event().wait],
                'after': {'dependency'},
                'binds_to': {'dependency'},
            }
        )
        self.launcher_database.add(
            'dependency', {
                'exec_start': [dependency_exec_start],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependent')
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

        self.launcher_database.add(
            'dependency', {
                'exec_start': [dependency_exec_start],
            }
        )

        self.launcher_database.add(
            'dependent', {
                'exec_start': [dependent_exec_start],
                'after': {'dependency'},
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependent')
        )
        await phile.asyncio.wait_for(dependent_started.wait())
        self.assertFalse(dependency_started.is_set())

    async def test_start_rewinds_if_exec_start_raises(self) -> None:
        name = 'exec_start_raises'

        async def divide_by_zero() -> None:
            1 / 0  # pylint: disable=pointless-statement

        self.launcher_database.add(
            name, {
                'exec_start': [divide_by_zero],
                'type': phile.launcher.Type.FORKING,
            }
        )
        with self.assertRaises(ZeroDivisionError):
            await phile.asyncio.wait_for(
                self.launcher_state_machine.start(name)
            )

    async def test_stop_cancel_main_task_if_not_done(self) -> None:
        name = 'simple_stop'
        task_to_cancel = asyncio.create_task(asyncio.Event().wait())
        self.launcher_database.add(
            name, {'exec_start': [lambda: task_to_cancel]}
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.stop(name)
        )
        self.assertTrue(task_to_cancel.cancelled())

    async def test_stop_runs_exec_stop_if_given(self) -> None:
        name = 'stop_with_exec_stop'
        stop = asyncio.Event()

        async def stopper() -> None:
            stop.set()

        self.launcher_database.add(
            name, {
                'exec_start': [stop.wait],
                'exec_stop': [stopper],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.stop(name)
        )
        self.assertTrue(stop.is_set())

    async def test_stop_returns_if_not_running(self) -> None:
        name = 'starting_after_start'
        stop_launcher = asyncio.Event()
        self.launcher_database.add(
            name, {
                'exec_start': [stop_launcher.wait],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.stop(name)
        )

    async def test_stop_awaits_if_already_stopping(self) -> None:
        name = 'double_stop'
        stop = asyncio.Event()
        continue_stopper = asyncio.Event()

        async def stopper() -> None:
            await continue_stopper.wait()
            stop.set()

        self.launcher_database.add(
            name, {
                'exec_start': [stop.wait],
                'exec_stop': [stopper],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        stop_1 = asyncio.create_task(
            self.launcher_state_machine.stop(name)
        )
        await asyncio.sleep(0)
        stop_2 = asyncio.create_task(
            self.launcher_state_machine.stop(name)
        )
        await asyncio.sleep(0)
        self.assertFalse(stop_1.done())
        self.assertFalse(stop_2.done())
        continue_stopper.set()
        await phile.asyncio.wait_for(stop_2)
        await phile.asyncio.wait_for(stop_1)

    async def test_is_not_running_after_stop(self) -> None:
        name = 'simple_stop'
        self.launcher_database.add(
            name, {'exec_start': [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.stop(name)
        )
        self.assertFalse(self.launcher_state_machine.is_running(name))

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

        self.launcher_database.add(
            name, {
                'exec_start': [starter],
                'exec_stop': [stopper],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(name)
        )
        started.clear()
        stop_task = asyncio.create_task(
            self.launcher_state_machine.stop(name)
        )
        await asyncio.sleep(0)
        start_task = asyncio.create_task(
            self.launcher_state_machine.start(name)
        )
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

        self.launcher_database.add(
            name, {
                'exec_start': [starter],
                'exec_stop': [stopper],
                'type': phile.launcher.Type.FORKING,
            }
        )
        start_task = asyncio.create_task(
            self.launcher_state_machine.start(name)
        )
        await asyncio.sleep(0)
        stop_task = asyncio.create_task(
            self.launcher_state_machine.stop(name)
        )
        with self.assertRaises(asyncio.CancelledError):
            await phile.asyncio.wait_for(start_task)
        await phile.asyncio.wait_for(stop_task)

    async def test_stop_stops_bound_by_entries(self) -> None:
        dependent_started = asyncio.Event()
        dependent_stopped = asyncio.Event()

        async def dependent_exec_start() -> None:
            dependent_started.set()
            await asyncio.Event().wait()

        async def dependent_exec_stop() -> None:
            dependent_stopped.set()

        self.launcher_database.add(
            'dependent', {
                'exec_start': [dependent_exec_start],
                'exec_stop': [dependent_exec_stop],
                'binds_to': {'dependency'}
            }
        )
        self.launcher_database.add(
            'dependency', {
                'exec_start': [asyncio.Event().wait],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependent')
        )
        await phile.asyncio.wait_for(dependent_started.wait())
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependency')
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.stop('dependency')
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

        self.launcher_database.add(
            'dependent', {
                'exec_start': [asyncio.Event().wait],
                'exec_stop': [dependent_exec_stop],
                'after': {'dependency'},
                'binds_to': {'dependency'},
            }
        )
        self.launcher_database.add(
            'dependency', {
                'exec_start': [dependency_exec_start],
                'exec_stop': [dependency_exec_stop],
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependent')
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependency')
        )
        await phile.asyncio.wait_for(dependency_started.wait())
        dependency_stop_task = asyncio.create_task(
            self.launcher_state_machine.stop('dependency')
        )
        await phile.asyncio.wait_for(dependent_stopped.wait())
        self.assertFalse(dependency_stopped.is_set())
        dependent_exec_stop_continue.set()
        await phile.asyncio.wait_for(dependency_stop_task)
        await phile.asyncio.wait_for(dependent_stopped.wait())

    async def test_stop_does_not_stop_afters_without_binds_to(
        self
    ) -> None:
        dependency_started = asyncio.Event()
        dependency_stopped = asyncio.Event()
        dependent_stopped = asyncio.Event()

        async def dependency_exec_start() -> None:
            dependency_started.set()

        async def dependency_exec_stop() -> None:
            dependency_stopped.set()

        async def dependent_exec_stop() -> None:
            dependent_stopped.set()

        self.launcher_database.add(
            'dependency', {
                'exec_start': [dependency_exec_start],
                'exec_stop': [dependency_exec_stop],
            }
        )
        self.launcher_database.add(
            'dependent', {
                'exec_start': [asyncio.Event().wait],
                'exec_stop': [dependent_exec_stop],
                'after': {'dependency'},
            }
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependency')
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start('dependent')
        )
        await phile.asyncio.wait_for(dependency_started.wait())
        await phile.asyncio.wait_for(
            self.launcher_state_machine.stop('dependency')
        )
        await phile.asyncio.wait_for(dependency_stopped.wait())
        self.assertFalse(dependent_stopped.is_set())

    async def test_start_emits_events(self) -> None:
        entry_name = 'start_emits_events'
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_state_machine.event_publisher,
        )
        self.launcher_database.add(entry_name, {'exec_start': [noop]})
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(entry_name)
        )
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.StateMachine.Event(
                source=self.launcher_state_machine,
                type=phile.launcher.StateMachine.start,
                entry_name=entry_name,
            ),
        )

    async def test_stop_emits_events(self) -> None:
        entry_name = 'remove_emits_events'
        self.launcher_database.add(
            entry_name, {'exec_start': [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.start(entry_name)
        )
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_state_machine.event_publisher,
        )
        await phile.asyncio.wait_for(
            self.launcher_state_machine.stop(entry_name)
        )
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.StateMachine.Event(
                source=self.launcher_state_machine,
                type=phile.launcher.StateMachine.stop,
                entry_name=entry_name,
            ),
        )


class TestRegistry(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.launcher.Registry`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_registry: phile.launcher.Registry

    async def asyncSetUp(self) -> None:
        super().setUp()
        self.launcher_registry = phile.launcher.Registry()

    def test_register_adds_to_database(self) -> None:
        name = 'register_to_registry'
        self.launcher_registry.register(name, {'exec_start': [noop]})
        self.assertTrue(self.launcher_registry.is_registered(name))

    async def test_deregister_removes_from_database(self) -> None:
        name = 'deregister_from_registry'
        self.launcher_registry.register(name, {'exec_start': [noop]})
        self.assertTrue(self.launcher_registry.is_registered(name))
        await phile.asyncio.wait_for(
            self.launcher_registry.deregister(name)
        )
        self.assertFalse(self.launcher_registry.is_registered(name))

    async def test_deregister_stops_launcher(self) -> None:
        name = 'to_be_stopped_when_deregistering'
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def exec_start() -> None:
            started.set()
            await asyncio.Event().wait()

        async def exec_stop() -> None:
            stopped.set()

        self.launcher_registry.register(
            name, {
                'exec_start': [exec_start],
                'exec_stop': [exec_stop],
            }
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(started.wait())
        await self.launcher_registry.deregister(name)
        await phile.asyncio.wait_for(stopped.wait())

    async def test_start_calls_exec_run(self) -> None:
        name = 'registry_start'
        queue = asyncio.Queue[int]()
        self.launcher_registry.register(
            name, {'exec_start': [functools.partial(queue.put, 1)]}
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(queue.get())

    async def test_stop_calls_exec_stop(self) -> None:
        name = 'registry_stop'
        queue = asyncio.Queue[int]()
        self.launcher_registry.register(
            name, {
                'exec_start': [asyncio.Event().wait],
                'exec_stop': [functools.partial(queue.put, 1)]
            }
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        await phile.asyncio.wait_for(self.launcher_registry.stop(name))
        await phile.asyncio.wait_for(queue.get())

    async def test_is_running_after_start(self) -> None:
        name = 'registry_is_running'
        self.launcher_registry.register(
            name, {'exec_start': [asyncio.Event().wait]}
        )
        await phile.asyncio.wait_for(self.launcher_registry.start(name))
        self.assertTrue(self.launcher_registry.is_running(name))

    async def test_register_emits_events(self) -> None:
        entry_name = 'register_emits_events'
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_registry.event_publisher,
        )
        self.launcher_registry.register(
            entry_name, {'exec_start': [noop]}
        )
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.Registry.Event(
                source=self.launcher_registry,
                type=phile.launcher.Registry.register,
                entry_name=entry_name,
            ),
        )

    async def test_deregister_emits_events(self) -> None:
        entry_name = 'deregister_emits_events'
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_registry.event_publisher,
        )
        self.launcher_registry.register(
            entry_name, {'exec_start': [noop]}
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.deregister(entry_name)
        )
        # Discard the register event.
        event = await phile.asyncio.wait_for(subscriber.pull())
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.Registry.Event(
                source=self.launcher_registry,
                type=phile.launcher.Registry.deregister,
                entry_name=entry_name,
            ),
        )

    async def test_start_emits_events(self) -> None:
        entry_name = 'start_emits_events'
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_registry.event_publisher,
        )
        self.launcher_registry.register(
            entry_name, {'exec_start': [noop]}
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name),
        )
        # Discard the register event.
        event = await phile.asyncio.wait_for(subscriber.pull())
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.Registry.Event(
                source=self.launcher_registry,
                type=phile.launcher.Registry.start,
                entry_name=entry_name,
            ),
        )

    async def test_stop_emits_events(self) -> None:
        entry_name = 'start_emits_events'
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self.launcher_registry.event_publisher,
        )
        self.launcher_registry.register(
            entry_name, {'exec_start': [noop]}
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start(entry_name),
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.stop(entry_name),
        )
        # Discard the register and start events.
        event = await phile.asyncio.wait_for(subscriber.pull())
        event = await phile.asyncio.wait_for(subscriber.pull())
        event = await phile.asyncio.wait_for(subscriber.pull())
        self.assertEqual(
            event,
            phile.launcher.Registry.Event(
                source=self.launcher_registry,
                type=phile.launcher.Registry.stop,
                entry_name=entry_name,
            ),
        )
