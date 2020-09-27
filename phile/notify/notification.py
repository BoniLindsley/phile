#!/usr/bin/env python3

# Standard library.
import datetime
import pathlib

# External dependencies.
import appdirs  # type: ignore


class _AppDirPaths(appdirs.AppDirs):
    """
    Wraps `appdirs.AppDirs` properties in :py:class:`pathlib.Path`.

    Available properties:

    * site_config
    * site_data
    * user_cache
    * user_config
    * user_data
    * user_log
    * user_state
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_config = pathlib.Path(self.site_config_dir)
        self.site_data = pathlib.Path(self.site_data_dir)
        self.user_cache = pathlib.Path(self.user_cache_dir)
        self.user_config = pathlib.Path(self.user_config_dir)
        self.user_data = pathlib.Path(self.user_data_dir)
        self.user_log = pathlib.Path(self.user_log_dir)
        self.user_state = pathlib.Path(self.user_state_dir)


_app_dir_paths = _AppDirPaths(appname="phile", appauthor="BoniLindsley")
"""
Builder of resource directories used by this package.

It is an object that contains information necessary
to determine, for example, configuration, runtime and log directories.
"""


class Configuration:

    def __init__(
        self,
        *,
        notification_directory: pathlib.Path = _app_dir_paths.user_state
        / "notification",
        notification_suffix: str = '.notify'
    ) -> None:
        self.notification_directory = notification_directory
        """
        Directory containing files representing notification requests.
        """
        self.notification_suffix = notification_suffix


class Notification:

    class ParentError(ValueError):
        pass

    class SuffixError(ValueError):
        pass

    def __init__(
        self,
        *,
        configuration: Configuration = None,
        name: str = None,
        path: pathlib.Path = None
    ) -> None:
        if path is None:
            if configuration is None or name is None:
                raise ValueError(
                    'Notification is constructed from path'
                    ' or from both configuration and name'
                )
            path = configuration.notification_directory / (
                name + configuration.notification_suffix
            )
        else:
            if configuration is not None:
                path_parent = path.parent
                directory = configuration.notification_directory
                if path_parent != directory:
                    raise Notification.ParentError(
                        'Path parent ({}) is not {}'.format(
                            path_parent, directory
                        )
                    )
                path_suffix = path.suffix
                notification_suffix = configuration.notification_suffix
                if path_suffix != notification_suffix:
                    raise Notification.SuffixError(
                        'Path suffix ({}) is not {}'.format(
                            path_suffix, notification_suffix
                        )
                    )
        self.path = path

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return self.path == other.path

    def append(self, additional_content: str):
        with self.path.open('a') as notification_file:
            # End with a new line
            # so that appending again would not jumble up the text.
            notification_file.write(additional_content + '\n')

    @property
    def creation_datetime(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.path.stat().st_mtime)

    @property
    def name(self) -> str:
        return self.path.stem

    def read(self) -> str:
        return self.path.read_text()

    def remove(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def write(self, new_content: str):
        # End with a new line
        # so that appending would not jumble up the text.
        self.path.write_text(new_content + '\n')
