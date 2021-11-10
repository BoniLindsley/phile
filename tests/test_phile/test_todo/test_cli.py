#!/usr/bin/env python3

# Standard libraries.
import io
import logging
import pathlib

# External dependencies.
import click
import click.testing
import pytest

# Internal modules
import phile.todo.cli


def get_target_module_name() -> str:
    return phile.todo.cli.__name__


def get_target_logger() -> logging.Logger:
    return logging.getLogger(get_target_module_name())


def reset_stream(target_stream: io.StringIO) -> None:
    target_stream.seek(0)
    target_stream.truncate()


class TestSetDefault:
    def test_creates_missing_keys(self) -> None:
        dest: dict[str, int] = {}
        source: dict[str, int] = {"a": 1}
        phile.todo.cli.setdefault_recursively(dest, source)
        assert dest == {"a": 1}

    def test_ignores_existing_keys(self) -> None:
        dest: dict[str, int] = {"b": 2}
        source: dict[str, dict[str, int]] = {"b": {"a": 1}}
        phile.todo.cli.setdefault_recursively(dest, source)
        assert dest == {"b": 2}

    def test_descends_into_nested_values(self) -> None:
        dest: dict[str, dict[str, int]] = {"c": {"d": 4}}
        source: dict[str, dict[str, int]] = {"c": {"d": 3, "e": 5}}
        phile.todo.cli.setdefault_recursively(dest, source)
        assert dest == {"c": {"d": 4, "e": 5}}


class TestGetConfigSubmap:
    def test_searches_for_config_with_package_name_as_keys(self) -> None:
        config_submap = phile.todo.cli.get_config_submap(
            config_map={"package": {"name": {"b": 2}}},
            submap_keys=["package", "name"],
        )
        assert config_submap == {"b": 2}

    def test_raises_key_error_if_missing(self) -> None:
        with pytest.raises(KeyError):
            phile.todo.cli.get_config_submap(
                config_map={},
                submap_keys=["package", "name"],
            )

    def test_raises_value_error_if_submap_is_not_a_dict(self) -> None:
        with pytest.raises(ValueError):
            phile.todo.cli.get_config_submap(
                config_map={"package": 1},
                submap_keys=["package"],
            )


class TestFillDefaultMapFromConfigMap:
    def test_ignores_inappropriate_config_map(self) -> None:
        context = click.Context(click.Command("someone"))
        phile.todo.cli.fill_default_map_from_config_map(
            config_map={}, context=context, submap_keys=["a"]
        )
        assert context.default_map is None
        phile.todo.cli.fill_default_map_from_config_map(
            config_map={"a": 1}, context=context, submap_keys=["a"]
        )
        assert context.default_map is None

    def test_uses_config_map_if_default_missing(self) -> None:
        context = click.Context(click.Command("someone"))
        phile.todo.cli.fill_default_map_from_config_map(
            config_map={"a": {"b": 2}},
            context=context,
            submap_keys=["a"],
        )
        assert context.default_map == {"b": 2}

    def test_does_not_override_default_map(self) -> None:
        context = click.Context(
            click.Command("someone"), default_map={"c": 3}
        )
        phile.todo.cli.fill_default_map_from_config_map(
            config_map={"a": {"b": 2, "c": 2}},
            context=context,
            submap_keys=["a"],
        )
        assert context.default_map == {"b": 2, "c": 3}


class TestReadConfigMap:
    def test_loads_json_content_into_config_map(
        self, tmp_path: pathlib.Path
    ) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text('{"a":1}')
        config_map = phile.todo.cli.read_config_map(config_path)
        assert config_map == {"a": 1}

    def test_raises_if_given_config_file_is_missing(
        self, tmp_path: pathlib.Path
    ) -> None:
        config_path = tmp_path / "config.json"
        with pytest.raises(FileNotFoundError):
            phile.todo.cli.read_config_map(config_path)

    def test_raises_if_given_config_file_is_not_json(
        self, tmp_path: pathlib.Path
    ) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text("a")
        with pytest.raises(phile.todo.cli.UnexpectedConfigContent):
            phile.todo.cli.read_config_map(config_path)

    def test_raises_if_given_config_file_is_not_map(
        self, tmp_path: pathlib.Path
    ) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text("1")
        with pytest.raises(phile.todo.cli.UnexpectedConfigContent):
            phile.todo.cli.read_config_map(config_path)


class TestFillDefaultMapFromConfigPath:
    def test_loads_json_into_default_map(
        self, tmp_path: pathlib.Path
    ) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text('{"phile":{"todo":{"a":1}}}')
        context = click.Context(click.Command("someone"))
        phile.todo.cli.fill_default_map_from_config_path(
            config_path=config_path,
            context=context,
            submap_keys=["phile", "todo"],
        )
        assert context.default_map == {"a": 1}

    def test_raises_if_given_config_file_is_missing(
        self, tmp_path: pathlib.Path
    ) -> None:
        config_path = tmp_path / "config.json"
        context = click.Context(click.Command("someone"))
        with pytest.raises(FileNotFoundError):
            phile.todo.cli.fill_default_map_from_config_path(
                config_path=config_path,
                context=context,
                submap_keys=["does", "not", "matter"],
            )

    def test_raises_if_given_config_file_is_not_map(
        self, tmp_path: pathlib.Path
    ) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text("1")
        context = click.Context(click.Command("someone"))
        with pytest.raises(phile.todo.cli.UnexpectedConfigContent):
            phile.todo.cli.fill_default_map_from_config_path(
                config_path=config_path,
                context=context,
                submap_keys=["does", "not", "matter"],
            )


class TestCreateConfigOptionCallback:
    def test_loads_json_into_default_map(
        self, tmp_path: pathlib.Path
    ) -> None:
        callback = phile.todo.cli.create_config_option_callback(
            submap_keys=["package", "name"]
        )
        config_path = tmp_path / "config.json"
        config_path.write_text('{"package":{"name":{"a":1}}}')
        context = click.Context(click.Command("load-it"))
        return_value = callback(
            context, click.Option(("--config",)), config_path
        )
        assert return_value == config_path
        assert context.default_map == {"a": 1}

    def test_ignores_missing_file_if_config_was_not_given_explicitly(
        self, tmp_path: pathlib.Path
    ) -> None:
        callback = phile.todo.cli.create_config_option_callback(
            submap_keys=["package", "name"]
        )
        config_path = tmp_path / "config.json"
        context = click.Context(click.Command("default-missing-okay"))
        context.set_parameter_source(
            "config", click.core.ParameterSource.DEFAULT
        )
        return_value = callback(
            context, click.Option(("--config",)), config_path
        )
        assert return_value == config_path
        assert context.default_map is None

    def test_raises_if_given_config_file_is_missing(
        self, tmp_path: pathlib.Path
    ) -> None:
        callback = phile.todo.cli.create_config_option_callback(
            submap_keys=[]
        )
        config_path = tmp_path / "config.json"
        context = click.Context(click.Command("missing-config"))
        with pytest.raises(click.UsageError):
            callback(context, click.Option(("--config",)), config_path)

    def test_raises_if_given_config_file_is_not_map(
        self, tmp_path: pathlib.Path
    ) -> None:
        callback = phile.todo.cli.create_config_option_callback(
            submap_keys=[]
        )
        config_path = tmp_path / "config.json"
        config_path.write_text("1")
        context = click.Context(click.Command("wrong-config"))
        with pytest.raises(click.UsageError):
            callback(context, click.Option(("--config",)), config_path)


class TestConfigOption:
    def test_uses_config_flag_by_default(
        self, tmp_path: pathlib.Path
    ) -> None:
        @click.command()
        @phile.todo.cli.config_option()
        @click.pass_context
        def do_it(context: click.Context) -> None:
            assert context.default_map == {"a": 1}

        config_path = tmp_path / "config.json"
        config_path.write_text('{"a": 1}')
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli=do_it,
            args=("--config", str(config_path)),
        )
        assert result.exit_code == 0

    def test_accepts_alternative_flags(
        self, tmp_path: pathlib.Path
    ) -> None:
        @click.command()
        @phile.todo.cli.config_option("-c", "--config")
        def do_it() -> None:
            pass

        config_path = tmp_path / "config.json"
        config_path.write_text("{}")
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli=do_it,
            args=("-c", str(config_path)),
        )
        assert result.exit_code == 0

    def test_descends_through_submap_keys_if_given(
        self, tmp_path: pathlib.Path
    ) -> None:
        @click.command()
        @phile.todo.cli.config_option(submap_keys=["grand", "parent"])
        @click.pass_context
        def do_it(context: click.Context) -> None:
            assert context.default_map == {"b": 2}

        config_path = tmp_path / "config.json"
        config_path.write_text('{"grand":{"parent":{"b": 2}}}')
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli=do_it,
            args=("--config", str(config_path)),
        )
        assert result.exit_code == 0

    def test_errors_if_given_path_is_missing(
        self, tmp_path: pathlib.Path
    ) -> None:
        @click.command()
        @phile.todo.cli.config_option()
        def do_it() -> None:
            pass

        config_path = tmp_path / "config.json"
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli=do_it,
            args=("--config", str(config_path)),
        )
        assert result.exit_code == 2
        assert (
            result.stderr.splitlines()[-1]
            == f"Error: Config file not found: {config_path}"
        )

    def test_errors_if_config_is_not_json(
        self, tmp_path: pathlib.Path
    ) -> None:
        @click.command()
        @phile.todo.cli.config_option()
        def do_it() -> None:
            pass

        config_path = tmp_path / "config.json"
        config_path.write_text("{")
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli=do_it,
            args=("--config", str(config_path)),
        )
        assert result.exit_code == 2
        assert (
            result.stderr.splitlines()[-1]
            == f"Error: Config file is not JSON: {config_path}"
        )


class TestCreateVerboseLogger:
    def test_logs_warnings_at_verbosity_0(self) -> None:
        output_stream = io.StringIO()
        phile.todo.cli.create_verbose_logger(
            0, output_stream=output_stream
        )

        get_target_logger().warning("Warning")
        assert (
            output_stream.getvalue()
            == f"[030] {get_target_module_name()}: Warning\n"
        )
        reset_stream(output_stream)

        get_target_logger().info("Info")
        assert output_stream.getvalue() == ""

    def test_logs_info_at_verbosity_1(self) -> None:
        output_stream = io.StringIO()
        phile.todo.cli.create_verbose_logger(
            1, output_stream=output_stream
        )

        get_target_logger().info("Info")
        assert (
            output_stream.getvalue()
            == f"[020] {phile.todo.cli.__name__}: Info\n"
        )
        reset_stream(output_stream)

        get_target_logger().debug("Debug")
        assert output_stream.getvalue() == ""

    def test_logs_debug_at_verbosity_2(self) -> None:
        output_stream = io.StringIO()
        phile.todo.cli.create_verbose_logger(
            2, output_stream=output_stream
        )

        get_target_logger().debug("Debug")
        assert (
            output_stream.getvalue()
            == f"[010] {phile.todo.cli.__name__}: Debug\n"
        )
        reset_stream(output_stream)

        get_target_logger().log(1, "Lowest level")
        assert output_stream.getvalue() == ""

    def test_logs_everything_at_verbosity_3(self) -> None:
        output_stream = io.StringIO()
        phile.todo.cli.create_verbose_logger(
            3, output_stream=output_stream
        )

        get_target_logger().debug("Debug")
        assert (
            f"[010] {phile.todo.cli.__name__}: Debug\n"
            in output_stream.getvalue()
        )
        reset_stream(output_stream)

        get_target_logger().log(1, "Lowest level")
        assert (
            output_stream.getvalue()
            == f"[001] {phile.todo.cli.__name__}: Lowest level\n"
        )


class TestVerboseOption:
    def test_uses_verbose_flag_by_default(self) -> None:
        logger = logging.getLogger(phile.todo.cli.__name__)

        @click.command()
        @phile.todo.cli.verbose_option()
        def do_it() -> None:
            logger.info("Hi!")

        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(do_it, ("--verbose",))
        assert result.stdout == ""
        assert result.stderr == "[020] phile.todo.cli: Hi!\n"

    def test_accepts_alternative_flags(self) -> None:
        logger = logging.getLogger(phile.todo.cli.__name__)

        @click.command()
        @phile.todo.cli.verbose_option("-v", "--verbosity")
        def do_it() -> None:
            logger.debug("Hi!")

        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(do_it, ("-vv",))
        assert result.stdout == ""
        assert result.stderr == "[010] phile.todo.cli: Hi!\n"


def test_group_sends_data_path_to_commands(
    tmp_path: pathlib.Path,
) -> None:
    @click.command()
    @click.option("--todo-path", type=pathlib.Path)
    def receives_todo_path(todo_path: pathlib.Path) -> None:
        click.echo(str(todo_path))

    group = phile.todo.cli.group
    group.add_command(receives_todo_path)
    try:
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            group,
            ("--data-dir", str(tmp_path), "receives-todo-path"),
        )
        assert result.stderr == ""
        assert result.stdout == str(tmp_path / "todo.txt") + "\n"
        assert result.exception is None
        assert result.exit_code == 0
    finally:
        group.commands.pop("receives-todo-path")


class TestTodoPathOption:
    def test_adds_new_option(self, tmp_path: pathlib.Path) -> None:
        @click.command()
        @phile.todo.cli.todo_path_option()
        def command_with_todo_path_option(
            todo_path: pathlib.Path,
        ) -> None:
            click.echo(str(todo_path))

        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            command_with_todo_path_option,
            ("--todo-path", str(tmp_path / "todo.txt")),
        )
        assert result.stderr == ""
        assert result.stdout == str(tmp_path / "todo.txt") + "\n"
        assert result.exception is None
        assert result.exit_code == 0

    def test_option_is_optional(self) -> None:
        @click.command()
        @phile.todo.cli.todo_path_option()
        def command_with_todo_path_option(
            todo_path: pathlib.Path,
        ) -> None:
            click.echo(str(todo_path))

        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(command_with_todo_path_option)
        assert result.stderr == ""
        assert result.stdout[-9:] == "todo.txt\n"
        assert result.exception is None
        assert result.exit_code == 0

    def test_accepts_custom_flag(self, tmp_path: pathlib.Path) -> None:
        @click.command()
        @phile.todo.cli.todo_path_option("--tpath")
        def command_with_todo_path_option(
            tpath: pathlib.Path,
        ) -> None:
            click.echo(str(tpath))

        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            command_with_todo_path_option,
            ("--tpath", str(tmp_path / "todo.txt")),
        )
        assert result.stderr == ""
        assert result.stdout == str(tmp_path / "todo.txt") + "\n"
        assert result.exception is None
        assert result.exit_code == 0

    def test_errors_if_path_is_directory(
        self, tmp_path: pathlib.Path
    ) -> None:
        @click.command()
        @phile.todo.cli.todo_path_option()
        def command_with_todo_path_option(
            todo_path: pathlib.Path,
        ) -> None:
            click.echo(str(todo_path))

        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            command_with_todo_path_option,
            ("--todo-path", str(tmp_path)),
        )
        assert result.stderr != ""
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 2


class TestList:
    def test_prints_file_line_by_line(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("a\nb\n")
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.list_,
            ("--todo-path", str(todo_path)),
        )
        assert result.stderr == ""
        assert result.stdout == "0. a\n1. b\n"
        assert result.exception is None
        assert result.exit_code == 0

    def test_prints_nothing_if_file_empty(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.touch()
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.list_,
            ("--todo-path", str(todo_path)),
        )
        assert result.stderr == ""
        assert result.stdout == ""
        assert result.exception is None
        assert result.exit_code == 0

    def test_prints_nothing_if_file_missing(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.list_,
            ("--todo-path", str(todo_path)),
        )
        assert result.stderr == ""
        assert result.stdout == ""
        assert result.exception is None
        assert result.exit_code == 0


def test_add_appends_to_file(tmp_path: pathlib.Path) -> None:
    todo_path = tmp_path / "todo.txt"
    todo_path.write_text("a\nb\n")
    runner = click.testing.CliRunner(mix_stderr=False)
    result = runner.invoke(
        phile.todo.cli.add,
        ("--todo-path", str(todo_path), "Thing"),
    )
    assert result.stdout == ""
    assert result.exception is None
    assert result.exit_code == 0
    assert todo_path.read_text() == "a\nb\n[ ] Thing\n"


class TestRemove:
    def test_deletes_given_line(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("a\nb\nc\n")
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.remove,
            ("--todo-path", str(todo_path), "1"),
        )
        assert result.stdout == ""
        assert result.exception is None
        assert result.exit_code == 0
        assert todo_path.read_text() == "a\nc\n"

    def test_fails_if_index_too_large(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.touch()
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.remove,
            ("--todo-path", str(todo_path), "1"),
        )
        assert (
            result.stderr.splitlines()[-1]
            == "Error: Cannot remove entry 1. Zero-based. Total: 0."
        )
        assert result.stdout == ""
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 2

    def test_fails_if_file_missing(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.remove,
            ("--todo-path", str(todo_path), "1"),
        )
        assert (
            result.stderr.splitlines()[-1]
            == f"Error: Cannot find todo path: {todo_path}"
        )
        assert result.stdout == ""
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 2


class TestStart:
    def test_modifies_given_line(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("a\nb\nc\n")
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.start,
            ("--todo-path", str(todo_path), "1"),
        )
        assert result.stdout == ""
        assert result.exception is None
        assert result.exit_code == 0
        assert (
            todo_path.read_text().splitlines()[1][:19]
            == "b #timetrack.start="
        )

    def test_fails_if_index_too_large(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.touch()
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.start,
            ("--todo-path", str(todo_path), "1"),
        )
        assert (
            result.stderr.splitlines()[-1]
            == "Error: Cannot get entry 1. Zero-based. Total: 0."
        )
        assert result.stdout == ""
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 2

    def test_fails_if_file_missing(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.start,
            ("--todo-path", str(todo_path), "1"),
        )
        assert (
            result.stderr.splitlines()[-1]
            == f"Error: Cannot find todo path: {todo_path}"
        )
        assert result.stdout == ""
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 2


class TestStop:
    def test_modifies_given_line(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.write_text("a\nb\nc\n")
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.stop,
            ("--todo-path", str(todo_path), "1"),
        )
        assert result.stdout == ""
        assert result.exception is None
        assert result.exit_code == 0
        assert (
            todo_path.read_text().splitlines()[1][:18]
            == "b #timetrack.stop="
        )

    def test_fails_if_index_too_large(
        self, tmp_path: pathlib.Path
    ) -> None:
        todo_path = tmp_path / "todo.txt"
        todo_path.touch()
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.stop,
            ("--todo-path", str(todo_path), "1"),
        )
        assert (
            result.stderr.splitlines()[-1]
            == "Error: Cannot get entry 1. Zero-based. Total: 0."
        )
        assert result.stdout == ""
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 2

    def test_fails_if_file_missing(self, tmp_path: pathlib.Path) -> None:
        todo_path = tmp_path / "todo.txt"
        runner = click.testing.CliRunner(mix_stderr=False)
        result = runner.invoke(
            phile.todo.cli.stop,
            ("--todo-path", str(todo_path), "1"),
        )
        assert (
            result.stderr.splitlines()[-1]
            == f"Error: Cannot find todo path: {todo_path}"
        )
        assert result.stdout == ""
        assert isinstance(result.exception, SystemExit)
        assert result.exit_code == 2
