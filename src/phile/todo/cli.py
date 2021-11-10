#!/usr/bin/env python3

# Standard library.
# TODO[python 3.10]: Annotations are built-in in 3.10.
from __future__ import annotations
import collections.abc
import datetime
import gettext
import importlib.machinery
import importlib.metadata
import json
import logging
import pathlib
import typing

# External dependencies.
import click
import click.core

# Internal modules.
import phile.phill.appdirs
from . import txt


_T = typing.TypeVar("_T")
UnaryOperator = typing.Callable[[_T], _T]
AnyCallable = collections.abc.Callable[..., typing.Any]
ParameterCallback = collections.abc.Callable[
    [click.Context, click.Option, _T], _T
]


_module_spec: importlib.machinery.ModuleSpec = (
    # TODO[mypy issue 4145: Module variable `__spec__` not in type hint.
    #
    # If fixed
    #
    # -   Replace all use of `_module_spec` with `__spec__`.
    # -   Remove import of `importlib.machinery`.
    #
    __spec__  # type: ignore[name-defined]
)
_package_name = (
    getattr(_module_spec, "parent", None) or _module_spec.name
)
_logger = logging.getLogger(__name__)
_app_paths = phile.phill.appdirs.AppPaths.from_module_spec(_module_spec)


def setdefault_recursively(
    dest: dict[str, typing.Any], source: dict[str, typing.Any]
) -> None:
    """Does not guard against reference loops."""
    for key, value in source.items():
        dest_value = dest.setdefault(key, value)
        if dest_value is value:
            continue
        if isinstance(dest_value, dict) and isinstance(value, dict):
            setdefault_recursively(dest_value, value)


def get_config_submap(
    *,
    config_map: dict[str, typing.Any],
    submap_keys: list[str],
) -> dict[str, typing.Any]:
    # Postcondition: raises KeyError if keys not found.
    # Postcondition: raises ValueError if config key maps to non dict.
    for key in submap_keys:
        config_map = config_map[key]
    if not isinstance(config_map, dict):
        raise ValueError()
    return config_map


def fill_default_map_from_config_map(
    *,
    config_map: dict[str, typing.Any],
    context: click.Context,
    submap_keys: list[str],
) -> None:
    try:
        submap = get_config_submap(
            config_map=config_map, submap_keys=submap_keys
        )
    except (KeyError, ValueError):
        return
    default_map = context.default_map
    if default_map is None:
        context.default_map = submap
        return
    setdefault_recursively(default_map, submap)


class UnexpectedConfigContent(Exception):
    pass


def read_config_map(config_path: pathlib.Path) -> dict[str, typing.Any]:
    # Raises: `FileNotFoundError` if `config_path` missing.
    # Raises: `UnexpectedConfigContent` if file is not a JSON dict.
    config_text = config_path.read_text()
    try:
        config_map = json.loads(config_text)
    except json.JSONDecodeError as error:
        raise UnexpectedConfigContent(
            f"Config file is not JSON: {config_path}"
        ) from error
    if not isinstance(config_map, dict):
        raise UnexpectedConfigContent(
            f"Config file is not a dict: {config_path}"
        )
    return config_map


def fill_default_map_from_config_path(
    *,
    context: click.Context,
    config_path: pathlib.Path,
    submap_keys: list[str],
) -> None:
    # Raises: `FileNotFoundError` if `config_path` missing.
    # Raises: `UnexpectedConfigContent` if file is not a JSON dict.
    config_map = read_config_map(config_path)
    fill_default_map_from_config_map(
        config_map=config_map,
        context=context,
        submap_keys=submap_keys,
    )


def create_config_option_callback(
    *,
    submap_keys: list[str],
) -> ParameterCallback[pathlib.Path]:
    def parse_config_option(
        context: click.Context,
        option: click.Option,
        value: pathlib.Path,
    ) -> pathlib.Path:
        try:
            fill_default_map_from_config_path(
                context=context,
                config_path=value,
                submap_keys=submap_keys,
            )
        except FileNotFoundError:
            is_value_default = (
                context.get_parameter_source(option.name or "")
                == click.core.ParameterSource.DEFAULT
            )
            if not is_value_default:
                context.fail(f"Config file not found: {value}")
            return value
        except UnexpectedConfigContent as error:
            context.fail(str(error))
        return value

    return parse_config_option


def config_option(
    *args: str, **kwargs: typing.Any
) -> UnaryOperator[AnyCallable]:
    if not args:
        args = ("--config",)

    submap_keys = kwargs.pop("submap_keys", [])
    parse_config_option = create_config_option_callback(
        submap_keys=submap_keys
    )

    kwargs.setdefault("callback", parse_config_option)
    kwargs.setdefault("default", _app_paths.user_config / "config.json")
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("help", gettext.gettext("path to config file"))
    kwargs.setdefault("is_eager", True)
    kwargs.setdefault("show_default", True)
    kwargs.setdefault(
        "type", click.Path(dir_okay=False, path_type=pathlib.Path)
    )

    return click.option(*args, **kwargs)


# TODO[typing issue 829]: Cannot annotation with abstract io classes.
def create_verbose_logger(
    verbosity: int, *, output_stream: typing.TextIO
) -> None:
    # | Verbosity | Logging level |
    # | --------- | ------------- |
    # |         0 | 30 WARNING    |
    # |         1 | 20 INFO       |
    # |         2 | 10 DEBUG      |
    # |         3 | 1 everything  |
    #
    # The logging level of 0 bubbles filtering to the root logger.
    # And the logging level of the root logger is DEBUG 10 by default.
    logging_level = max((3 - verbosity) * 10, 1)

    formatter = logging.Formatter(
        "[%(levelno)03d] %(name)s: %(message)s",
    )

    handler = logging.StreamHandler(output_stream)
    handler.setFormatter(formatter)
    handler.setLevel(logging_level)
    _logger.addHandler(handler)

    # If logger level is NOTSET or zero,
    # it uses a parent logger level that is not NOTSET.
    # If root logger has level NOTSET, it logs all messages.
    logger_logging_level = _logger.getEffectiveLevel() or 1
    # Logger does not pass messages to handler if logger level too low.
    logger_logging_level = min(logger_logging_level, logging_level)
    _logger.setLevel(logging_level)


def verbose_option(
    *args: str, **kwargs: typing.Any
) -> UnaryOperator[AnyCallable]:
    if not args:
        args = ("--verbose",)

    def parse_verbose_option(
        context: click.Context,
        option: click.Option,
        value: int,
    ) -> int:
        del context
        del option
        create_verbose_logger(
            value, output_stream=click.get_text_stream("stderr")
        )
        return value

    kwargs.setdefault("callback", parse_verbose_option)
    kwargs.setdefault("count", True)
    kwargs.setdefault("default", 0)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault(
        "help", gettext.gettext("explain what is being done")
    )
    kwargs.setdefault("is_eager", True)

    return click.option(*args, **kwargs)


@click.group(name=_package_name.rpartition(".")[2])
@click.help_option("--help", "-h")
@config_option(submap_keys=_package_name.split("."))
@verbose_option("--verbose", "-v")
@click.option(
    "--data-dir",
    default=_app_paths.user_data / _package_name.partition(".")[2],
    help=gettext.gettext("directory containing todo files"),
    show_default=True,
    type=click.Path(file_okay=False, path_type=pathlib.Path),
)
@click.pass_context
def group(context: click.Context, data_dir: pathlib.Path) -> None:
    """Track tasks and time."""
    this_command = typing.cast(click.Group, context.command)
    assert isinstance(this_command, click.Group)

    todo_path = data_dir / "todo.txt"
    default_map_for_subcommands = {
        subcommand: {"todo_path": todo_path}
        for subcommand in this_command.list_commands(context)
    }

    fill_default_map_from_config_map(
        config_map=default_map_for_subcommands,
        context=context,
        submap_keys=[],
    )


def todo_path_option(
    *args: str, **kwargs: typing.Any
) -> UnaryOperator[AnyCallable]:
    if not args:
        args = ("--todo-path",)
    kwargs.setdefault(
        "default",
        _app_paths.user_data
        / _package_name.partition(".")[2]
        / "todo.txt",
    )
    kwargs.setdefault(
        "help", gettext.gettext("file containing todo tasks")
    )
    kwargs.setdefault("show_default", True)
    kwargs.setdefault(
        "type", click.Path(dir_okay=False, path_type=pathlib.Path)
    )
    return click.option(*args, **kwargs)


@group.command(name="list")
@todo_path_option()
def list_(todo_path: pathlib.Path) -> None:
    """List all tasks with their indices."""
    try:
        todo_list = txt.load(todo_path)
    except FileNotFoundError:
        todo_list = []
    for (todo_id, line) in enumerate(todo_list):
        click.echo(f"{todo_id}. {line}")


@group.command()
@click.argument("summary")
@todo_path_option()
def add(todo_path: pathlib.Path, summary: str) -> None:
    """Create a task with given summary."""
    _logger.debug("Adding todo: %s", summary)
    with todo_path.open("a") as todo_file:
        todo_file.write(f"[ ] {summary}\n")


@group.command()
@click.argument("todo_id", type=int)
@todo_path_option()
@click.pass_context
def remove(
    context: click.Context, todo_path: pathlib.Path, todo_id: int
) -> None:
    """Remove task at given index."""
    try:
        txt.remove(todo_path, index=todo_id)
    except (FileNotFoundError, IndexError) as error:
        context.fail(str(error))


@group.command()
@click.argument("todo_id", type=int)
@todo_path_option()
@click.pass_context
def start(
    context: click.Context, todo_path: pathlib.Path, todo_id: int
) -> None:
    """Start task at given index."""
    try:
        txt.start(
            todo_path, index=todo_id, now=datetime.datetime.utcnow()
        )
    except (FileNotFoundError, IndexError) as error:
        context.fail(str(error))


@group.command()
@click.argument("todo_id", type=int)
@todo_path_option()
@click.pass_context
def stop(
    context: click.Context, todo_path: pathlib.Path, todo_id: int
) -> None:
    """Stop task at given index."""
    try:
        txt.stop(
            todo_path, index=todo_id, now=datetime.datetime.utcnow()
        )
    except (FileNotFoundError, IndexError) as error:
        context.fail(str(error))
