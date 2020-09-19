#!/usr/bin/env python3

# Standard libraries.
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

notification_directory = _app_dir_paths.user_state / "notification"
"""Directory containing files representing notification requests."""
