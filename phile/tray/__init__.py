#!/usr/bin/env python3
"""
.. automodule:: phile.tray.event
.. automodule:: phile.tray.gui
.. automodule:: phile.tray.publishers
.. automodule:: phile.tray.tmux
"""

# Standard library.
import contextlib
import dataclasses
import io
import json
import pathlib
import shutil
import typing
import warnings

# Internal packages.
import phile.configuration
import phile.data


@dataclasses.dataclass(eq=False)
class File(phile.data.File):
    icon_name: typing.Optional[str] = None
    icon_path: typing.Optional[pathlib.Path] = None
    text_icon: typing.Optional[str] = None

    @classmethod
    def from_path_stem(
        cls,
        path_stem: str,
        *args,
        configuration: phile.configuration.Configuration,
        **kwargs,
    ) -> 'File':
        """Dataclasses do not allow keyword-only arguments."""
        assert 'path' not in kwargs
        kwargs['path'] = cls.make_path(
            configuration=configuration, path_stem=path_stem
        )
        return cls(*args, **kwargs)

    @staticmethod
    def make_path(
        *,
        configuration: phile.configuration.Configuration,
        path_stem: str,
    ) -> pathlib.Path:
        return configuration.tray_directory / (
            path_stem + configuration.tray_suffix
        )

    @staticmethod
    def check_path(
        path: pathlib.Path,
        *,
        configuration: phile.configuration.Configuration,
    ) -> bool:
        return (
            path.parent == configuration.tray_directory
            and path.suffix == configuration.tray_suffix
        )

    def load(self):
        """
        Parse tray file for a tray icon to be displayed.

        :raises ~FileNotFoundError:
            If the file to load cannot be found.
        :raises ~json.decoder.JSONDecodeError:
            If the JSON string part of the tray file to load
            cannot be decode properly.

        The input file should start with a single line
        that can be displayed in a text tray environment such as `tmux`.

        The remaining lines should describe the request in json format.
        It should contain the following keys:

        * `icon_path` or `icon_name`: The latter is searched for
          from the underlying theme setup.

        It should not contan any other keys,
        and may be ignored, subject to implementation details.
        """
        # Buffer the file content to reduce the chance of file changes
        # introducing a race condition.
        content_stream = io.StringIO(self.path.read_text())
        # First line is the text icon.
        # Do not write content yet in case JSON decoding fails.
        text_icon = content_stream.readline().rstrip('\r\n')
        # Make sure there are content to read by reading one byte
        # and then resetting the offset before decoding.
        current_offset = content_stream.tell()
        if content_stream.read(1):
            content_stream.seek(current_offset)
            json_content = json.load(content_stream)
        else:
            json_content = {}
        # Get properties from the decoded structure.
        self.text_icon = text_icon
        self.icon_name = json_content.get('icon_name')
        icon_path = json_content.get('icon_path')
        if icon_path is not None:
            self.icon_path = pathlib.Path(icon_path)
        else:
            self.icon_path = None

    def save(self) -> None:
        # Buffer for data to be written.
        content_stream = io.StringIO()
        # First line is the text icon.
        if self.text_icon is not None:
            content_stream.write(self.text_icon)
        # Only copy over values that are filled in.
        json_content: typing.Dict[str, str] = {}
        for key in ['icon_name', 'icon_path']:
            value = getattr(self, key, None)
            if value is not None:
                json_content[key] = str(value)
        # If there is content to write, end the text icon line
        # before writing the JSON string.
        if json_content:
            content_stream.write('\n')
            json.dump(json_content, content_stream)
        # Copy over the buffer.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('w+') as file_stream:
            content_stream.seek(0)
            shutil.copyfileobj(content_stream, file_stream)
