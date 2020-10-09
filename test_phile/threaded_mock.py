#!/usr/bin/env python3
"""
-------------
Threaded Mock
-------------
"""

import datetime
import threading
import typing
import unittest.mock


class ThreadedMock(unittest.mock.Mock):
    """
    A mock object to be called in a different thread.

    Example::

        import threading

        # This will be called in a thread.
        callee = ThreadedMock()
        # Threads that will call the mock object.
        bad_thread = threading.Thread(target=callee, args=(42, ))
        call_thread = threading.Thread(target=callee)
        # Call, eventually.
        bad_thread.start()
        call_thread.start()
        # Wait for the calls.
        callee.assert_called_with_soon()
        # Clean-up the threads.
        bad_thread.join()
        call_thread.join()

    Takes over :attr:`~unittest.mock.Mock.side_effect`.
    Modifying it is undefined behaviour.
    """

    def __init__(
        self,
        *args,
        target: typing.Callable = lambda *args, **kwargs: unittest.mock.
        DEFAULT,
        timeout: datetime.timedelta = datetime.timedelta(seconds=2),
        **kwargs
    ):
        """
        :param ~datetime.timedelta timeout:
            Initialses :attr:`timeout`,
            to two seconds by default for now.
        :param target:
            When ``self`` is called,
            arguments are forwarded to ``target``.
            The :attr:`~unittest.mock.Mock.return_value` is ignored,
            unless ``target`` returns :data:`~unittest.mock.DEFAULT`.
        :type target: :data:`~typing.Callable`
        """
        super().__init__(*args, **kwargs)
        self._call_found = threading.Event()
        """Set when an :data:`_expected_call` had been found."""
        self._expected_call: typing.Optional[unittest.mock._Call] = None
        """Call object to compare with in :meth:`_side_effect`"""
        self._mock_lock = threading.Lock()
        """Guards against changes to :data:`_expected_call`."""
        self._target = target
        """A callable to forward to when ``self`` is called."""
        self.timeout = timeout
        """Timeout duration when `self` is waiting to be called."""
        self.side_effect = self._side_effect

    def _side_effect(self, *args, **kwargs) -> typing.Any:
        """
        Checks if the given arguments are as expected when called.

        Sets :data:`_call_found` event
        to notify :meth:`assert_called_with_soon` it succeeded.
        """
        return_value = self._target(*args, **kwargs)
        new_call = unittest.mock.call(*args, **kwargs)
        with self._mock_lock:
            expected_call = self._expected_call
            if (expected_call is None) or (new_call == expected_call):
                self._call_found.set()
        return return_value

    def assert_called_with_soon(self, *args, **kwargs) -> None:
        """
        Waits for this mock object to be called with specified arguments.

        Asserts that the specified arguments are used eventually.
        That is, this does not fail if called with the wrong arguments.
        Due to the threaded nature of this assertion,
        it is not always possible to line up calls.
        So this waits for the expected call,
        allowing for other arguments before then.
        """
        with self._mock_lock:
            # Enable comparison in `_side_effect`.
            self._expected_call = unittest.mock.call(*args, **kwargs)
            self._call_found.clear()
            # Check the last call to see if assert is already satisfied.
            if self.call_args == self._expected_call:
                self._call_found.set()
        # Temporarily release
        # to allow `_side_effect` acquire the lock.
        # Wait for the expected call arguments to be found.
        was_called_found = self._call_found.wait(
            self.timeout.total_seconds()
        )
        with self._mock_lock:
            # Do a normal assert here to take advantage
            # of the normal assert log printout.
            if not was_called_found:
                self.assert_called_with(*args, **kwargs)
            # Reset everything, to prepare for the next call.
            self._expected_call = None
            self._call_found.clear()

    def assert_called_soon(self, *args, **kwargs) -> None:
        """Waits for this mock object to be called."""
        # Temporarily release
        # to allow `_side_effect` acquire the lock.
        # Wait for the expected call arguments to be found.
        was_called_found = self._call_found.wait(
            self.timeout.total_seconds()
        )
        with self._mock_lock:
            # Do a normal assert here to take advantage
            # of the normal assert log printout.
            if not was_called_found:
                self.assert_called()
            # Reset, to prepare for the next call.
            self._call_found.clear()


if __name__ == '__main__':

    class TestThreadedMock(unittest.TestCase):

        def setUp(self) -> None:
            self.callee = ThreadedMock()
            self.call_thread = threading.Thread(target=self.callee)

        def tearDown(self) -> None:
            try:
                self.call_thread.join(
                    timeout=datetime.timedelta(seconds=2).total_seconds()
                )
            except RuntimeError:
                pass

        def test_assert_called_with_soon_example(self) -> None:
            """Successful assert from example."""
            bad_thread = threading.Thread(
                target=self.callee, args=(42, )
            )
            bad_thread.start()
            self.call_thread.start()
            self.callee.assert_called_with_soon()
            bad_thread.join()

        def test_assert_called_with_soon_fail(self) -> None:
            """This blocks until a timeout, with no expected call."""
            self.call_thread.start()
            with self.assertRaises(AssertionError):
                self.callee.assert_called_with_soon(42)

        def test_assert_called_soon_example(self) -> None:
            """Successful assert from example."""
            self.call_thread.start()
            self.callee.assert_called_soon()

        def test_assert_called_soon_fail(self) -> None:
            """This blocks until a timeout, with no expected call."""
            with self.assertRaises(AssertionError):
                self.callee.assert_called_soon()

    unittest.main()
