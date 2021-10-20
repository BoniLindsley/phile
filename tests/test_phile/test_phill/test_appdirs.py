#!/usr/bin/env python3

# Standard libraries.
import pathlib

# External dependencies.
import appdirs

# Internal packages.
import phile.phill.appdirs


def test_from_module_spec_uses_distribution_name() -> None:
    module_spec = phile.phill.appdirs.__spec__
    assert module_spec is not None
    app_dirs = phile.phill.appdirs.from_module_spec(module_spec)
    assert app_dirs.appname == appdirs.AppDirs("phile").appname


class TestAppPaths:
    def test_from_app_dirs(self) -> None:
        app_dirs = appdirs.AppDirs("phile")
        app_paths = phile.phill.appdirs.AppPaths.from_app_dirs(app_dirs)
        assert app_paths.appname == appdirs.AppDirs("phile").appname

    def test_from_module_spec(self) -> None:
        app_dirs = appdirs.AppDirs("phile")
        module_spec = phile.phill.appdirs.__spec__
        assert module_spec is not None
        app_paths = phile.phill.appdirs.AppPaths.from_module_spec(
            module_spec
        )
        assert app_paths.appname == app_dirs.appname

    def test_has_expected_attributes(self) -> None:
        app_paths = phile.phill.appdirs.AppPaths()
        assert isinstance(app_paths.user_cache, pathlib.Path)
        assert isinstance(app_paths.user_config, pathlib.Path)
        assert isinstance(app_paths.user_data, pathlib.Path)
        assert isinstance(app_paths.user_log, pathlib.Path)
        assert isinstance(app_paths.user_state, pathlib.Path)
        assert isinstance(app_paths.site_log, pathlib.Path)
        assert isinstance(app_paths.site_state, pathlib.Path)
