#!/usr/bin/env python3

# Standard libraries.
import signal
import types
import typing


def get_wakeup_fd() -> int:
    """
    Returns the file descriptor stored by :func:`~signal.set_wakeup_fd`.

    Currently, the only way to determine the fd is
    is to use :func:`~signal.set_wakeup_fd` using a dummy value,
    because it returns the previous fd,
    and then once more to restore it.
    This wraps the two calls for convenience.
    """
    wakeup_fd = signal.set_wakeup_fd(-1)
    signal.set_wakeup_fd(wakeup_fd)
    return wakeup_fd


Handler = typing.Callable[[signal.Signals, types.FrameType], typing.Any]
"""Type of callback that receive signals."""

SignalHandlerParameter = typing.Union[int, signal.Handlers, Handler]
"""Type of parameter ``handler`` of :func:`~signal.signal`."""


def install_noop_signal_handler(
    signal_number: signal.Signals,
    *,
    _noop_handler: SignalHandlerParameter = (
        lambda _signal_number, _: None
    )
) -> typing.Union[SignalHandlerParameter, None]:
    """
    Install a no-op handler for the given ``signal_number``.

    :param ~signal.Signals signal_number:
        The signal to install a noop handler for.
    :param SignalHandler _noop_handler:
        Internal. Implementation detail.
        Default is a noop lambda of the correct signature.
        A default argument is only created once
        regardless of the number of times the function is called.
    :returns: The previous signal handler for ``signal_number``.

    This overwrites any installed handler for the signal.
    In particular, in the case of :data:`~signal.SIGINT`,
    this removes the :func:`~signal.default_int_handler`
    which raises :exc:`KeyboardInterrupt` when called.
    This default handler is installed
    during the initialisation of the :mod:`signal` module.

    Note that this is different
    from installing the :data:`~signal.SIG_IGN` handler
    which instructs operating system to ignore the signal entirely,
    whereas a noop handler forces the Python interpreter
    to process the signal received
    when it becomes active and is available to do so.
    """

    # Do not replace with `signal.signal(signal_number, signal.SIG_IGN)`.
    # See documentation for details.
    # As for the use of a default argument,
    # it forces the interpreter to only create one copy of the handler.
    return signal.signal(signal_number, _noop_handler)
