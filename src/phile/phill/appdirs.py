#!/usr/bin/env python3

# Standard library.
import importlib.metadata
import pathlib
import typing

# External dependencies.
import appdirs


def from_module_spec(
    module_spec: importlib.machinery.ModuleSpec,
) -> appdirs.AppDirs:
    module_name = module_spec.name
    distribution_name = module_name.partition(".")[0]
    distribution = importlib.metadata.distribution(distribution_name)
    return appdirs.AppDirs(appname=distribution.metadata["Name"])


class AppPaths(appdirs.AppDirs):

    __Self = typing.TypeVar("__Self", bound="AppPaths")

    @classmethod
    def from_app_dirs(
        cls: typing.Type[__Self],
        app_dirs: appdirs.AppDirs,
    ) -> __Self:
        return cls(
            appname=app_dirs.appname,
            appauthor=app_dirs.appauthor,
            version=app_dirs.version,
            roaming=app_dirs.roaming,
            multipath=app_dirs.multipath,
        )

    @classmethod
    def from_module_spec(
        cls: typing.Type[__Self],
        module_spec: importlib.machinery.ModuleSpec,
    ) -> __Self:
        app_dirs = from_module_spec(module_spec)
        return cls.from_app_dirs(app_dirs)

    @property
    def user_cache(self) -> pathlib.Path:
        return pathlib.Path(self.user_cache_dir)

    @property
    def user_config(self) -> pathlib.Path:
        return pathlib.Path(self.user_config_dir)

    @property
    def user_data(self) -> pathlib.Path:
        return pathlib.Path(self.user_data_dir)

    @property
    def user_log(self) -> pathlib.Path:
        return pathlib.Path(self.user_log_dir)

    @property
    def user_state(self) -> pathlib.Path:
        return pathlib.Path(self.user_state_dir)

    @property
    def site_log(self) -> pathlib.Path:
        return pathlib.Path(self.user_log_dir)

    @property
    def site_state(self) -> pathlib.Path:
        return pathlib.Path(self.user_state_dir)
