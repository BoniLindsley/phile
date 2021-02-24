#!/usr/bin/env python3
"""
--------------------------
Test :mod:`phile.triggers`
--------------------------
"""

# Standard library.
import collections.abc
import os
import pathlib
import tempfile
import typing
import unittest
import unittest.mock

# External dependencies.
import portalocker  # type: ignore[import]

# Internal packages.
import phile
import phile.trigger


def noop_nullary() -> None:
    pass


class TestNullaryCallable(unittest.TestCase):
    """Tests :data:`~phile.trigger.NullaryCallable`."""

    def test_compatible_lambda(self) -> None:
        _: phile.trigger.NullaryCallable = lambda: None

    def test_compatible_function(self) -> None:

        def constant_function() -> int:
            return 1

        _: phile.trigger.NullaryCallable = constant_function

    def test_noop_function(self) -> None:
        _: phile.trigger.NullaryCallable = noop_nullary


class TestPidLock(unittest.TestCase):
    """Tests :class:`~phile.trigger.PidLock`."""

    def setUp(self) -> None:
        """Create a directory to store the lock file."""
        self.pid_lock_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.pid_lock_directory.cleanup)
        self.pid_lock_path = pathlib.Path(
            self.pid_lock_directory.name
        ) / 'pid'
        self.pid_lock = phile.trigger.PidLock(self.pid_lock_path)

    def test_setup_and_teardown(self) -> None:
        """Ensure :meth:`setUp` and :meth:`tearDown` is working."""

    def test_acquire_and_release_and_locked(self) -> None:
        """Basic usage of acquiring and then releasing."""
        self.assertFalse(self.pid_lock.locked())
        self.pid_lock.acquire()
        self.assertTrue(self.pid_lock.locked())
        self.assertEqual(
            self.pid_lock_path.read_text(), str(os.getpid())
        )
        self.pid_lock.release()
        self.assertFalse(self.pid_lock.locked())
        self.assertEqual(self.pid_lock_path.read_text(), '')

    def test_acquire_twice(self) -> None:
        """Acquiring twice warns."""
        self.pid_lock.acquire()
        self.addCleanup(self.pid_lock.release)
        with self.assertRaises(portalocker.LockException):
            self.pid_lock.acquire()

    def test_double_acquire(self) -> None:
        """Acquiring a PID that was acquired by someone else warns."""
        self.pid_lock.acquire()
        self.addCleanup(self.pid_lock.release)
        new_pid_lock = phile.trigger.PidLock(self.pid_lock_path)
        with self.assertRaises(portalocker.LockException):
            new_pid_lock.acquire()

    def test_release_unacquired(self) -> None:
        """Releasing unacquired PID is okay."""
        self.pid_lock.release()

    def test_finaliser_when_unlocked(self) -> None:
        """Finaliser should succeed if not locked."""
        self.pid_lock.__del__()

    def test_finaliser_when_locked(self) -> None:
        """Finaliser should warn if locked."""
        self.pid_lock.acquire()
        self.addCleanup(self.pid_lock.release)
        with self.assertWarns(UserWarning):
            self.pid_lock.__del__()
        self.assertFalse(self.pid_lock.locked())


class TestEntryPoint(unittest.TestCase):
    """Tests :func:`~phile.trigger.EntryPoint`."""

    def setUp(self) -> None:
        """Create a directory to use as a trigger directory."""
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.user_state_directory = pathlib.Path(
            user_state_directory.name
        )
        self.configuration = phile.Configuration(
            user_state_directory=self.user_state_directory,
        )
        self.trigger_directory_name = 'tr'
        self.trigger_directory = (
            self.configuration.trigger_root / self.trigger_directory_name
        )
        self.entry_point = phile.trigger.EntryPoint(
            configuration=self.configuration,
            trigger_directory=pathlib.Path(self.trigger_directory_name),
        )
        self.trigger_name = 'thing'
        self.trigger_path = self.trigger_directory / (
            self.trigger_name + self.configuration.trigger_suffix
        )

    def test_relative_trigger_directory(self) -> None:
        """
        Provides
        :attr:`phile.trigger.EntryPoint.trigger_directory`
        to determined the managed directory.
        """
        self.assertEqual(
            self.entry_point.trigger_directory, self.trigger_directory
        )

    def test_absolute_trigger_directory(self) -> None:
        """Provided trigger directory can be absolute."""
        trigger_directory = (
            self.configuration.user_state_directory / 'ttgg'
        )
        entry_point = phile.trigger.EntryPoint(
            configuration=self.configuration,
            trigger_directory=trigger_directory,
        )
        self.assertEqual(
            entry_point.trigger_directory, trigger_directory
        )

    def test_bind_and_unbind_and_is_bound(self) -> None:
        """
        Basic usage of :meth:`~phile.trigger.EntryPoint.bind`
        and :meth:`~phile.trigger.EntryPoint.unbind`,
        and :meth:`~phile.trigger.EntryPoint.is_bound`,
        """
        self.assertTrue(not self.entry_point.is_bound())
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.assertTrue(self.entry_point.is_bound())
        self.entry_point.unbind()
        self.assertTrue(not self.entry_point.is_bound())

    def test_unbind_without_bind(self) -> None:
        """
        Ignore :meth:`~phile.trigger.EntryPoint.unbind` calls
        if not already bound.
        """
        self.entry_point.unbind()
        self.assertTrue(not self.entry_point.is_bound())

    def test_two_instances_binding_same_trigger_directory(self) -> None:
        """
        Two instances :meth:`~phile.trigger.EntryPoint.bind`-ing
        the same ``trigger_directory`` should fail.
        """
        # Bind once.
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        # Bind a second time.
        extra_entry_point = phile.trigger.EntryPoint(
            configuration=self.configuration,
            trigger_directory=pathlib.Path(self.trigger_directory_name),
        )
        with self.assertRaises(portalocker.LockException):
            extra_entry_point.bind()

    def test_bind_in_context_manager(self) -> None:
        entry_point = self.entry_point
        with entry_point as entry_point_context:
            self.assertEqual(entry_point_context, entry_point)
            self.assertTrue(entry_point.is_bound())
        self.assertTrue(not entry_point.is_bound())

    def test_get_trigger_path(self) -> None:
        """Fetch the trigger path of a given name."""
        trigger_path = self.entry_point.get_trigger_path(
            self.trigger_name
        )
        self.assertEqual(trigger_path, self.trigger_path)

    def test_check_path_checks_directory(self) -> None:
        """A trigger file path must be in trigger directory."""
        invalid_path = self.user_state_directory / 'ttgg'
        self.assertTrue(self.entry_point.check_path(self.trigger_path))
        self.assertTrue(not self.entry_point.check_path(invalid_path))

    def test_check_path_checks_suffix(self) -> None:
        """A trigger file path must be in trigger directory."""
        invalid_path = self.trigger_directory / (
            'a' + self.configuration.trigger_suffix + '_not'
        )
        self.assertTrue(self.entry_point.check_path(self.trigger_path))
        self.assertTrue(not self.entry_point.check_path(invalid_path))

    def test_add_trigger_checks_for_callback(self) -> None:
        """Adding trigger makes sure the trigger has a callback."""
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        with self.assertRaises(AssertionError):
            self.entry_point.add_trigger(self.trigger_name)

    def test_add_and_remove_trigger(self) -> None:
        """Adding and removing trigger creates and deletes files."""
        self.entry_point.callback_map = {self.trigger_name: noop_nullary}
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.add_trigger(self.trigger_name)
        self.assertTrue(self.trigger_path.is_file())
        self.entry_point.remove_trigger(self.trigger_name)
        self.assertTrue(not self.trigger_path.exists())

    def test_remove_non_existent_trigger(self) -> None:
        """Removing a non-existent trigger is fine."""
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.remove_trigger(self.trigger_name)
        self.assertTrue(not self.trigger_path.exists())

    def test_add_and_remove_trigger_without_binding(self) -> None:
        """Manipulating triggers without binding raises an exception."""
        with self.assertRaises(ResourceWarning):
            self.entry_point.add_trigger(self.trigger_name)
        with self.assertRaises(ResourceWarning):
            self.entry_point.remove_trigger(self.trigger_name)

    def test_add_trigger_on_init(self) -> None:
        """Triggers can be added in initialiser if also binding."""
        entry_point = phile.trigger.EntryPoint(
            available_triggers={'red', 'yellow'},
            bind=True,
            callback_map={
                'red': noop_nullary,
                'yellow': noop_nullary
            },
            configuration=self.configuration,
            trigger_directory=pathlib.Path(self.trigger_directory_name),
        )
        self.addCleanup(entry_point.unbind)
        self.assertTrue(entry_point.get_trigger_path('red').is_file())
        self.assertTrue(entry_point.get_trigger_path('yellow').is_file())

    def test_activate_trigger_if_deleted(self) -> None:
        """Activation is based on path."""
        trigger_callback = unittest.mock.Mock()
        self.entry_point.callback_map = {
            self.trigger_name: trigger_callback
        }
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.add_trigger(self.trigger_name)
        self.trigger_path.unlink()
        self.entry_point.activate_trigger(self.trigger_path)
        trigger_callback.assert_called_once_with()

    def test_activate_trigger_fails_if_not_deleted(self) -> None:
        """Activation checks that the trigger path is deleted."""
        trigger_callback = unittest.mock.Mock()
        self.entry_point.callback_map = {
            self.trigger_name: trigger_callback
        }
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.add_trigger(self.trigger_name)
        self.entry_point.activate_trigger(self.trigger_path)
        trigger_callback.assert_not_called()

    def test_activate_trigger_fails_if_trigger_not_available(
        self
    ) -> None:
        """Activation checks that the trigger path is available."""
        trigger_callback = unittest.mock.Mock()
        self.entry_point.callback_map = {
            self.trigger_name: trigger_callback
        }
        self.entry_point.activate_trigger(self.trigger_path)
        trigger_callback.assert_not_called()

    def test_activate_trigger_fails_without_callback(self) -> None:
        """Activation checks that the trigger has a callback."""
        self.entry_point.callback_map = {self.trigger_name: noop_nullary}
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.add_trigger(self.trigger_name)
        self.trigger_path.unlink()
        self.entry_point.callback_map = {}
        self.entry_point.activate_trigger(self.trigger_path)

    def test_unbind_removes_triggers(self) -> None:
        """Unbinding cleans up any remaining triggers."""
        self.entry_point.callback_map = {self.trigger_name: noop_nullary}
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.add_trigger(self.trigger_name)
        self.assertTrue(self.trigger_path.is_file())
        self.entry_point.unbind()
        self.assertTrue(not self.trigger_path.exists())


class TestRegistry(unittest.TestCase):
    """Tests :func:`~phile.trigger.Registry`."""

    def setUp(self) -> None:
        self.registry = phile.trigger.Registry()

    def test_available_exceptions(self) -> None:
        with self.assertRaises(ValueError):
            raise phile.trigger.Registry.AlreadyBound()
        with self.assertRaises(ValueError):
            raise phile.trigger.Registry.NotBound()
        with self.assertRaises(ValueError):
            raise phile.trigger.Registry.NotShown()

    def test_event_handler_type(self) -> None:

        def handler(
            method: collections.abc.Callable[..., typing.Any],
            registry: phile.trigger.Registry, name: str
        ) -> None:
            del method
            del registry
            del name

        callback: phile.trigger.Registry.EventHandler = handler
        callback(phile.trigger.Registry.bind, self.registry, 'quit')

    def test_default_initialisable(self) -> None:
        isinstance(self.registry.event_callback_map, list)

    def test_bind_binds(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.assertTrue(not self.registry.is_bound(name))
        self.registry.bind(name, callback)
        self.assertTrue(self.registry.is_bound(name))

    def test_binding_same_callback_twice_is_okay(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.assertTrue(self.registry.is_bound(name))
        self.registry.bind(name, callback)
        self.assertTrue(self.registry.is_bound(name))

    def test_double_bind_raises(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.assertTrue(self.registry.is_bound(name))
        fail_callback = unittest.mock.Mock()
        with self.assertRaises(phile.trigger.Registry.AlreadyBound):
            self.registry.bind(name, fail_callback)

    def test_unbind_after_bind(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.assertTrue(self.registry.is_bound(name))
        self.registry.unbind(name)
        self.assertTrue(not self.registry.is_bound(name))

    def test_unbind_unbound_is_okay(self) -> None:
        name = 'increase'
        self.assertTrue(not self.registry.is_bound(name))
        self.registry.unbind(name)

    def test_show_shows(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.assertTrue(not self.registry.is_shown(name))
        self.registry.show(name)
        self.assertTrue(self.registry.is_shown(name))

    def test_double_show_is_fine(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.registry.show(name)
        self.assertTrue(self.registry.is_shown(name))
        self.registry.show(name)
        self.assertTrue(self.registry.is_shown(name))

    def test_show_unbound_raises(self) -> None:
        name = 'increase'
        self.assertTrue(not self.registry.is_bound(name))
        with self.assertRaises(phile.trigger.Registry.NotBound):
            self.registry.show(name)

    def test_hide_after_show(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.registry.show(name)
        self.assertTrue(self.registry.is_shown(name))
        self.registry.hide(name)
        self.assertTrue(not self.registry.is_shown(name))

    def test_hide_hidden_is_fine(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.assertTrue(not self.registry.is_shown(name))
        self.registry.hide(name)
        self.assertTrue(not self.registry.is_shown(name))

    def test_hide_unbound_is_fine(self) -> None:
        name = 'increase'
        self.assertTrue(not self.registry.is_bound(name))
        self.registry.hide(name)
        self.assertTrue(not self.registry.is_shown(name))

    def test_unbind_hides(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.registry.show(name)
        self.assertTrue(self.registry.is_bound(name))
        self.assertTrue(self.registry.is_shown(name))
        self.registry.unbind(name)
        self.assertTrue(not self.registry.is_bound(name))
        self.assertTrue(not self.registry.is_shown(name))

    def test_activate_calls_bound_callback(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.registry.show(name)
        self.assertTrue(self.registry.is_bound(name))
        self.assertTrue(self.registry.is_shown(name))
        self.registry.activate(name)
        callback.assert_called_once_with()

    def test_activate_implicitly_hides(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.registry.show(name)
        self.assertTrue(self.registry.is_bound(name))
        self.assertTrue(self.registry.is_shown(name))
        self.registry.activate(name)
        self.assertTrue(not self.registry.is_shown(name))

    def test_activate_raises_if_unbound(self) -> None:
        name = 'increase'
        self.assertTrue(not self.registry.is_bound(name))
        with self.assertRaises(phile.trigger.Registry.NotBound):
            self.registry.activate(name)

    def test_activate_raises_if_hidden(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.assertTrue(self.registry.is_bound(name))
        self.assertTrue(not self.registry.is_shown(name))
        with self.assertRaises(phile.trigger.Registry.NotShown):
            self.registry.activate(name)

    def test_activate_if_shown_ignores_hidden(self) -> None:
        callback = unittest.mock.Mock()
        name = 'increase'
        self.registry.bind(name, callback)
        self.assertTrue(self.registry.is_bound(name))
        self.assertTrue(not self.registry.is_shown(name))
        self.registry.activate_if_shown(name)

    def test_activate_if_shown_raises_if_unbound(self) -> None:
        name = 'increase'
        self.assertTrue(not self.registry.is_bound(name))
        with self.assertRaises(phile.trigger.Registry.NotBound):
            self.registry.activate_if_shown(name)

    def test_event_callback_map_is_given_events(self) -> None:
        event_callback = unittest.mock.Mock()
        self.registry.event_callback_map.append(event_callback)
        callback = unittest.mock.Mock()
        name = 'increase'

        self.registry.bind(name, callback)
        event_callback.assert_called_once_with(
            phile.trigger.Registry.bind, self.registry, name
        )
        event_callback.reset_mock()

        self.registry.show(name)
        event_callback.assert_called_once_with(
            phile.trigger.Registry.show, self.registry, name
        )
        event_callback.reset_mock()

        self.registry.activate(name)
        event_callback.assert_called_once_with(
            phile.trigger.Registry.activate, self.registry, name
        )
        event_callback.reset_mock()

        self.registry.hide(name)
        event_callback.assert_called_once_with(
            phile.trigger.Registry.hide, self.registry, name
        )
        event_callback.reset_mock()

        self.registry.unbind(name)
        event_callback.assert_called_once_with(
            phile.trigger.Registry.unbind, self.registry, name
        )
        event_callback.reset_mock()


class TestProvider(unittest.TestCase):
    """Tests :func:`~phile.trigger.Provider`."""

    def setUp(self) -> None:
        self.callback_map: dict[str, phile.trigger.NullaryCallable] = {
            'open': unittest.mock.Mock(),
            'close': unittest.mock.Mock(),
        }
        self.registry = phile.trigger.Registry()
        self.provider = phile.trigger.Provider(
            callback_map=self.callback_map, registry=self.registry
        )

    def test_available_exceptions(self) -> None:
        with self.assertRaises(ValueError):
            raise phile.trigger.Provider.NotBound()

    def test_initialise_with_no_callbacks(self) -> None:
        self.callback_map = {}
        self.provider = phile.trigger.Provider(
            callback_map=self.callback_map, registry=self.registry
        )

    def test_bind_binds(self) -> None:
        self.assertTrue(not self.provider.is_bound())
        self.provider.bind()
        self.assertTrue(self.provider.is_bound())

    def test_double_bind_to_same_callback_is_okay(self) -> None:
        self.provider.bind()
        self.assertTrue(self.provider.is_bound())
        self.provider.bind()
        self.assertTrue(self.provider.is_bound())

    def test_bind_that_fails_unbinds_for_invariance(self) -> None:
        callback = unittest.mock.Mock()
        name = 'close'
        self.registry.bind(name, callback)
        with self.assertRaises(phile.trigger.Registry.AlreadyBound):
            self.provider.bind()
        self.assertTrue(not self.provider.is_bound())

    def test_unbind_after_bind(self) -> None:
        self.provider.bind()
        self.assertTrue(self.provider.is_bound())
        self.provider.unbind()
        self.assertTrue(not self.provider.is_bound())

    def test_unbind_unbound_is_okay(self) -> None:
        self.assertTrue(not self.provider.is_bound())
        self.provider.unbind()
        self.assertTrue(not self.provider.is_bound())

    def test_no_callback_means_always_bound(self) -> None:
        self.test_initialise_with_no_callbacks()
        self.assertTrue(self.provider.is_bound())

    def test_no_callback_bind_is_okay(self) -> None:
        self.test_initialise_with_no_callbacks()
        self.assertTrue(self.provider.is_bound())
        self.provider.bind()
        self.assertTrue(self.provider.is_bound())

    def test_context_manager_binds_and_unbinds(self) -> None:
        with self.provider:
            self.assertTrue(self.provider.is_bound())
        self.assertTrue(not self.provider.is_bound())

    def test_show_shows(self) -> None:
        name = 'open'
        self.provider.bind()
        self.assertTrue(not self.registry.is_shown(name))
        self.provider.show(name)
        self.assertTrue(self.registry.is_shown(name))

    def test_show_not_bound_by_provider_raises(self) -> None:
        callback = unittest.mock.Mock()
        name = 'clopen'
        self.registry.bind(name, callback)
        with self.assertRaises(phile.trigger.Provider.NotBound):
            self.provider.show(name)

    def test_hide_after_show(self) -> None:
        name = 'open'
        self.provider.bind()
        self.provider.show(name)
        self.assertTrue(self.registry.is_shown(name))
        self.provider.hide(name)
        self.assertTrue(not self.registry.is_shown(name))

    def test_hide_not_bound_by_provider_raises(self) -> None:
        callback = unittest.mock.Mock()
        name = 'clopen'
        self.registry.bind(name, callback)
        self.registry.show(name)
        with self.assertRaises(phile.trigger.Provider.NotBound):
            self.provider.hide(name)

    def test_show_all_shows(self) -> None:
        self.provider.bind()
        self.provider.show_all()
        for name in self.callback_map:
            self.assertTrue(self.registry.is_shown(name))


if __name__ == '__main__':
    unittest.main()
