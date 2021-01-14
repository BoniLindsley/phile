#!/usr/bin/env python3
"""
-----------------------
POSIX Signal in PySide2
-----------------------

When a :std:doc:`POSIX signal <library/signal>`
is sent to a Python process,
the current CPython `implementation (as of 2020-10-01)
<https://github.com/python/cpython/blob/256e54acdbdb26745d4bbb5cf366454151e42773/Modules/signalmodule.c#L248>`_
does roughly the following,
depending on the ``handler`` given to :func:`~signal.signal`:

    * If the ``handler`` is :data:`~signal.SIG_IGN`,
      the Python process does not receive the signal at all.
    * If the ``handler`` is :data:`~signal.SIG_DFL`,
      the operating system determines what to do
      by calling its own code.
      For example, for :data:`~signal.SIGINT`, it terminates.

Notice that in both cases so far,
everything occurs without needing to give control
to the Python interpreter.

If the ``handler`` is neither of those constants,
then it has to be a Python callable.
When the callable was installed via :func:`~signal.signal`,
CPython installs its own handler in the underlying operating system
to do the following:

    * Set some flag(s) to let the Python interpreter,
      when it becomes active, know that a signal was received.
    * If a valid socket was given to :func:`~signal.set_wakeup_fd`,
      then write the signal number in the socket.

And that is the end of the signal handler in CPython.
Notice that the Python interpreter does not receive control
and the ``handler`` is not referenced at any point.

When the next time the Python interpreter becomes active,
after finishing its last atomic bytecode,
before it resumes exection of the next bytecode,
it checks whether there is a set signal flag.
If there is,
it then runs the ``handler`` registered with the signal raised.
(For completeness sake, it continues as follows:
If the ``handler`` is invalid, an exception is raised at this point.
That exception, if any,
or any exception that the ``handler`` itself rasies,
will then be raised at the point where the interpreter had paused
after the bytecode that was finished processed.)

This implementation detail is important in Python code
relying on external libraries such as PySide2.
For example, while the PySide2 event
:meth:`loop <PySide2.QtCore.PySide2.QtCore.QCoreApplication.exec_>`
is waiting for an event in C++ code,
the Python interpreter is not active,
and no Python signal handler is ran until it is active again.
For example::

    # Handle a signal using default action.
    # In the case of SIGINT, it terminates the application
    # without going back into Python code.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Handle a signal using Python code.
    # But the code is not guaranteed to run.
    # It is merely flagged to be run in the future.
    signal.signal(
        signal.SIGALRM,
        lambda signal_number, _: QCoreApplication.instance.quit()
    )

A way to solve this problem was provided
by a `StackOverflow answer <https://stackoverflow.com/a/37229299>`_.
This module migrates the implementation over to PySide2.
The basic idea is to use :func:`~signal.set_wakeup_fd`
to write to a socket whenever a signal is received,
and use :class:`~PySide2.QtNetwork.PySide2.QtNetwork.QAbstractSocket`
to wait on the socket.
So whenever there is a signal,
Python interpreter has to become active to process the socket event
in the event loop,
thereby allowing the installed Python signal handlers to be ran,
and that happens before event loop processing resumes.
"""

# Standard libraries.
import signal
import socket
import sys
import typing
import warnings

# External dependencies.
import PySide2.QtCore
import PySide2.QtNetwork


class PosixSignal(PySide2.QtNetwork.QAbstractSocket):
    """
    Converter of :std:doc:`POSIX signals <library/signal>`
    to :std:doc:`PySide2 signals <PySide2/QtCore/Signal>`.

    :param ~PySide2.QtCore.PySide2.QtCore.QObject parent:
        Can be :data:`None`.
        If ``parent`` is not :data:`None`,
        then this instance will be destroyed when the ``parent`` is,
        unless it is given another parent through
        :meth:`~PySide2.QtCore.PySide2.QtCore.QObject.setParent`
        or otherwise.

    Emits a :data:`signal_received` PySide2 signal
    whenever the Python interpreter is set
    to receive and handle POSIX :func:`~signal.signal`-s.

    Example::

        import sys
        from PySide2.QtCore import QCoreApplication
        from phile.pyside2.posix_signal import (
            install_noop_signal_handler, PosixSignal
        )

        # Create a `QCoreApplication` before creating any `QObject`.
        app = QCoreApplication(sys.argv)
        # We will process signals with an _installed_ `signal()` handler.
        posix_signal = PosixSignal(app)
        # Handle signals from inside the PySide2 event loop.
        def quit_on_sigint(signal_number: int):
            if signal_number == signal.SIGINT:
                QCoreApplication.instance().quit()
        posix_signal.signal_received.connect(quit_on_sigint)
        # Let Python3 know we are interested in SIGINT.
        install_noop_signal_handler(signal.SIGINT)
        # Run PySide2 event loop and quit on SIGINT.
        return app.exec_()

    Note the precondition that
    the interpreter must be set to receive the particular POSIX signals.
    The Python interpreter does not receive signals
    for which the installed ``handler`` in :func:`~signal.signal`
    is either of the constants :data:`~signal.SIG_DFL`,
    which is the default for many POSIX signals,
    or :data:`~signal.SIG_IGN`,
    This means the user must inform Python3
    of the POSIX signals they are interested in in order for
    the :data:`signal_received` PySide2 signals to be emitted.

    Use the :func:`install_noop_signal_handler` function
    as a short-hand foring installing a handler.
    Install one of the two aforementioned constants
    to stop receiving a particular signal.
    See :func:`install_noop_signal_handler` for special behaviour
    in regards to :data:`~signal.SIG_IGN` handling by CPython.

    If :exc:`KeyboardInterrupt` is being raised
    from :data:`~signal.SIG_IGN` signals and that is undesirable,
    make sure that the :func:`~signal.signal` handler for the signal
    had been replaced using :func:`install_noop_signal_handler`
    or otherwise.

    While not officially supported
    (mostly because I do not know how to unit test such a situation),
    it is possible to use this :class:`PosixSignal` class
    without connecting to the :data:`signal_received` PySide2 signal.
    In order to emit the the :data:`signal_received` signal,
    the Python interpreter has to become active,
    and that means :func:`~signal.signal` handlers will be called.
    So an alternative way to make use of this class
    is to create it and use the :func:`~signal.signal` handlers directly.
    For example::

        import sys
        from PySide2.QtCore import QCoreApplication
        from phile.pyside2.posix_signal import (
            install_noop_signal_handler, PosixSignal
        )

        # Create a `QCoreApplication` before creating any `QObject`.
        app = QCoreApplication(sys.argv)
        # Let the Python interpreter take control
        # whenever signals with an _installed_ handler are raised.
        posix_signal = PosixSignal(app)
        # Let Python know how to handle the signals
        # when the interpreter does get control.
        signal.signal(
            signal.SIGINT, lambda _signal_number, _: app.quit()
        )
        # Run PySide2 event loop and quit on SIGINT.
        return app.exec_()

    .. note::
       Instances of this class must be created in the main thread
       because :func:`~signal.set_wakeup_fd` is used in implementation.
       Furthermore, if :func:`~signal.set_wakeup_fd` is already in use,
       such as another instance of :class:`PosixSignal` being alive,
       the resulting behaviour is undefiend,
       because instances will overwrite each other's fd (or socket).
       It is also undefined behaviour
       to :func:`~signal.set_wakeup_fd` again
       before this :class:`PosixSignal` object is destroyed.

       So, this class should only be instantiated once.
       Using the guarantees stated above,
       this class can and will make no attempt to restore the original fd
       because there is no way to
       determine the lifetime of the original fd.
       In the worst case scenario, the fd might be a reused ID.
    """

    signal_received = typing.cast(
        PySide2.QtCore.SignalInstance, PySide2.QtCore.Signal(int)
    )
    """
    PySide2 signal emitted when a POSIX signal is received.

    :param int: The POSIX signal number.

    Using a PySide2 signal instead of :func:`~signal.signal` handlers
    reduces the chance of having to fight over the signals.
    It also makes sure the interpreter stays in "signal handling mode"
    as little as possible.
    """

    def __init__(
        self,
        parent: typing.Optional[PySide2.QtCore.QObject] = None,
    ):

        # Create sockets for writing when signals are raised.
        write_socket, read_socket = socket.socketpair()
        # Give the receive side to PySide2.
        # Make sure PySide2 reads it as the correct type.
        #
        # I don't really know how to handle the different types.
        # Or how it matter.
        # The if tree here is just to make sure the type matches.
        # So branching coverage is not checked here.
        socket_type = write_socket.type
        if socket_type == socket.SOCK_DGRAM:  # pragma: no cover
            q_socket_type = PySide2.QtNetwork.QAbstractSocket.UdpSocket
        elif socket_type == socket.SOCK_STREAM:  # pragma: no cover
            q_socket_type = PySide2.QtNetwork.QAbstractSocket.TcpSocket
        else:  # pragma: no cover
            warnings.warn('Unsupported socket type. Attempting TCP.')
            q_socket_type = PySide2.QtNetwork.QAbstractSocket.TcpSocket
        super().__init__(q_socket_type, parent)  # type: ignore
        # Give PySide2 ownership of the socket.
        self.setSocketDescriptor(read_socket.fileno())
        read_socket.detach()
        # Respond to anything read from it.
        self.readyRead.connect(self._emit_signal_from_socket)

        # Write signal numbers to sending side of the sockets.
        # If fd wakeup by signals was already in use,
        # this might be a library usage conflict.
        write_socket.setblocking(False)
        old_wakeup_fd = signal.set_wakeup_fd(write_socket.fileno())
        if old_wakeup_fd != -1:
            # Restore it.
            signal.set_wakeup_fd(old_wakeup_fd)
            write_socket.close()
            raise RuntimeError('Signal fd wakeup already enabled.')
        # Give ownership to the signal module.
        # We retrieve ownership to close the socket
        # when this object is destroyed.
        write_socket.detach()

        # Do not try to restore the old wakeup fd.
        # We have no idea whether the fd will still be valid
        # when the lifetime of this instance ends.
        # Simply switch off the signal handling via fd.
        # close the `wakeup_fd` in use
        # which should be the same one we gave it.
        self.destroyed.connect(
            lambda _: socket.socket(fileno=signal.set_wakeup_fd(-1)).
            close()
        )

    def _emit_signal_from_socket(self):
        """
        Emit PySide2 event based on data from socket.

        Reads one byte from the underlying socket.
        The byte is parsed as a signal number,
        and a PySide2 signal is emitted based on the signal number.
        """
        # Data is received as a string.
        # Reading the raw data as an integer value
        # requires converting it into a byte array first.
        data = self.readData(1)
        signal_number = int.from_bytes(data.encode(), sys.byteorder)
        self.signal_received.emit(signal_number)
