#!/usr/bin/env python3
"""
----------------
phile.tray.event
----------------
"""

# Standard library.
import bisect
import json
import logging
import pathlib
import typing

# External dependencies.
import watchdog.events  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.tray
import phile.watchdog_extras

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""

Handler = typing.Callable[[phile.tray.File], None]
"""Signature of callables processing tray files."""


class Filter:
    """
    Ignore events that are not tray file events.

    An event is a tray file event if it involves a file with the
    :attr:`~phile.configuration.Configuration.notification_suffix`
    and is in the
    :attr:`~phile.configuration.Configuration.notification_directory`.
    """

    def __init__(
        self,
        *args,
        configuration: phile.configuration.Configuration,
        event_handler: phile.watchdog_extras.EventHandler,
        **kwargs,
    ) -> None:
        """
        :param ~phile.configuration.Configuration configuration:
            Information on what constitute a tray file.
        :param event_handler:
            Handler to call if an event passes this filter.
        :type event_handler: :data:`~phile.watchdog_extras.EventHandler`
        """
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._event_handler = event_handler
        """Callback repsonsible of processing trays."""
        self._tray_suffix = configuration.tray_suffix
        """Suffix that trays must have."""
        self._tray_directory = configuration.tray_directory
        """The directory containing tray files."""

    def __call__(
        self, watchdog_event: watchdog.events.FileSystemEvent
    ) -> None:
        """
        Internal.

        Calls ``event_handler``
        if ``watchdog_event`` is a tray file event.
        """
        if watchdog_event.is_directory:
            return
        event_type = watchdog_event.event_type
        if event_type == watchdog.events.EVENT_TYPE_MOVED:
            for new_event in [
                watchdog.events.FileDeletedEvent(
                    watchdog_event.src_path
                ),
                watchdog.events.FileCreatedEvent(
                    watchdog_event.dest_path
                )
            ]:
                self.__call__(new_event)
            return
        tray_path = pathlib.Path(watchdog_event.src_path)
        if tray_path.suffix != self._tray_suffix:
            return
        if tray_path.parent != self._tray_directory:
            return
        self._event_handler(watchdog_event)


class Converter:
    """Convert a tray file event to a tray file."""

    def __init__(
        self,
        *args,
        configuration: phile.configuration.Configuration,
        tray_handler: Handler,
        **kwargs,
    ) -> None:
        """
        :param ~phile.configuration.Configuration configuration:
            Information on what constitute a tray file.
        :param tray_handler:
            Handler to call with the tray name.
        :type tray_handler: :data:`Handler`
        """
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._tray_handler = tray_handler
        """Callback repsonsible of processing tray by name"""
        self._tray_suffix = configuration.tray_suffix
        """Suffix that trays must have."""

    def __call__(
        self, watchdog_event: watchdog.events.FileSystemEvent
    ) -> None:
        """
        Internal.

        Calls ``tray_handler`` with the tray file
        given in the `watchdog_event`.
        The given ``watchdog_event`` must be a tray file event
        that is not a moved event.
        It is undefined behaviour otherwise.
        """
        assert (
            watchdog_event.event_type != watchdog.events.EVENT_TYPE_MOVED
        )
        tray_path = pathlib.Path(watchdog_event.src_path)
        tray_file = phile.tray.File(path=tray_path)
        self._tray_handler(tray_file)


class Sorter:
    """Collect tray files into a list."""

    Handler = typing.Callable[[int, phile.tray.File], None]
    """Signature for processing a tray file with its position."""

    def __init__(
        self,
        *args,
        configuration: phile.configuration.Configuration,
        insert: Handler,
        pop: Handler,
        set_item: Handler,
        **kwargs,
    ) -> None:
        """
        :param ~phile.configuration.Configuration configuration:
            Information on what constitute a tray file.
        :param Handler insert:
            Called when an untracked tray file is found.
            It is given the index at which the tray file is inserted at.
        :param Handler pop:
            Called when a tracked tray file is deleted.
            It is given the index the tray file was at before removal.
        :param Handler set_item:
            Called when a tracked tray file is modified.
            It is given the index the tray file is at.
        """
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._configuration = configuration
        """Determines where and which files are tray files."""
        self.tray_files: typing.List[phile.tray.File] = []
        """Keeps track of known tray files."""
        self._insert = insert
        self._pop = pop
        self._set_item = set_item

    def __call__(self, tray_file: phile.tray.File) -> None:
        """
        Forwards to handlers
        depending on how :data:`tray_files` is changed.
        Call different handlers depending on the given ``tray_file``.

        :param ~phile.tray.File tray_file:
            The tray file to insert or update in `:data:`tray_files`
            if it exists,
            or to pop from it otherwise.

        Tracking of the given ``tray_file`` in  :data:`tray_files`
        is updated before the handlers are called.
        """

        index = bisect.bisect_left(self.tray_files, tray_file)
        is_tracked: bool
        try:
            is_tracked = self.tray_files[index] == tray_file
        except IndexError:
            is_tracked = False

        tray_file_exists: bool
        try:
            tray_file.load()
        except FileNotFoundError:
            tray_file_exists = False
        except json.decoder.JSONDecodeError:
            tray_file_exists = False
            _logger.warning(
                'Tray file decoding failed: {}'.format(tray_file.path)
            )
        else:
            tray_file_exists = True

        if not tray_file_exists:
            if is_tracked:
                self.tray_files.pop(index)
                self._pop(index, tray_file)
        elif is_tracked:
            self.tray_files[index] = tray_file
            self._set_item(index, tray_file)
        else:
            self.tray_files.insert(index, tray_file)
            self._insert(index, tray_file)

    def load_all(self):
        assert len(self.tray_files) == 0
        # Update all existing tray files.
        configuration = self._configuration
        for tray_file_path in configuration.tray_directory.glob(
            '*' + self._configuration.tray_suffix
        ):
            if not tray_file_path.is_file():
                continue
            tray_file = phile.tray.File(
                configuration=configuration, path=tray_file_path
            )
            self.__call__(tray_file)
