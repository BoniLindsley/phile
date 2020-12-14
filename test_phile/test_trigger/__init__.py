#!/usr/bin/env python3
"""
-------------
Test triggers
-------------
"""

# Standard library.
import os
import pathlib
import tempfile
import unittest
import unittest.mock

# External dependencies.
import portalocker  # type: ignore[import]
import watchdog.events  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.trigger
import phile.watchdog_extras
import test_phile.threaded_mock


class TestHandler(unittest.TestCase):
    """Tests :data:`~phile.trigger.Handler`."""

    def test_lambda(self) -> None:
        """A lambda can be a :data:`~phile.trigger.Handler`."""
        _: phile.trigger.Handler = lambda _: None

    def test_function(self) -> None:
        """A function can be a :data:`~phile.trigger.Handler`."""

        def trigger_handle_function(trigger_name: str) -> None:
            pass

        _: phile.trigger.Handler = trigger_handle_function


class TestNoopHandler(unittest.TestCase):
    """Tests :data:`~phile.trigger.noop_handler`."""

    def test_is_handler(self) -> None:
        """The noop handler must be a trigger handler."""
        _: phile.trigger.Handler = phile.trigger.noop_handler

    def test_is_callable(self) -> None:
        """The noop handler must be callable. (Called for coverage.)"""
        phile.trigger.noop_handler('yellow')


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
        self.configuration = phile.configuration.Configuration(
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

    def test_check_path_with_invalid_characters(self) -> None:
        """A path with invalid character is never a trigger path."""
        valid_path = self.trigger_directory / (
            'a' + self.configuration.trigger_suffix
        )
        invalid_path = self.trigger_directory / (
            'a\0' + self.configuration.trigger_suffix
        )
        self.assertTrue(self.entry_point.check_path(valid_path))
        self.assertTrue(not self.entry_point.check_path(invalid_path))

    def test_get_trigger_path_with_invalid_characters(self) -> None:
        """Using invalid trigger name raises :exc:`ValueError`."""
        trigger_name = '/\\open'
        with self.assertRaises(ValueError):
            trigger_path = self.entry_point.get_trigger_path(
                trigger_name
            )

    def test_add_trigger_checks_for_callback(self) -> None:
        """Adding trigger makes sure the trigger has a callback."""
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        with self.assertRaises(AssertionError):
            self.entry_point.add_trigger(self.trigger_name)

    def test_add_and_remove_trigger(self) -> None:
        """Adding and removing trigger creates and deletes files."""
        self.entry_point.callback_map = {
            self.trigger_name: phile.trigger.noop_handler
        }
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
                'red': phile.trigger.noop_handler,
                'yellow': phile.trigger.noop_handler
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
        trigger_callback.assert_called_once_with(self.trigger_name)

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
        self.entry_point.callback_map = {
            self.trigger_name: phile.trigger.noop_handler
        }
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.add_trigger(self.trigger_name)
        self.trigger_path.unlink()
        self.entry_point.callback_map = {}
        self.entry_point.activate_trigger(self.trigger_path)

    def test_unbind_removes_triggers(self) -> None:
        """Unbinding cleans up any remaining triggers."""
        self.entry_point.callback_map = {
            self.trigger_name: phile.trigger.noop_handler
        }
        self.addCleanup(self.entry_point.unbind)
        self.entry_point.bind()
        self.entry_point.add_trigger(self.trigger_name)
        self.assertTrue(self.trigger_path.is_file())
        self.entry_point.unbind()
        self.assertTrue(not self.trigger_path.exists())


if __name__ == '__main__':
    unittest.main()
