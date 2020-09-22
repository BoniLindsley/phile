#!/usr/bin/env python3

from setuptools import setup  # type: ignore

setup(
    name='phile',
    version='0.0.0.1',
    description='A file-based notification management',
    author='Boni Lindsley',
    author_email='boni.lindsley@gmail.com',
    packages=['phile'],
    license='MIT',
    install_requires=['PySide2', 'watchdog'],
    entry_points={'console_scripts': ['phile = phile.__main__:main', ]},
    extras_require={
        'dev': ['coverage', 'mypy', 'tox', 'yapf'],
    },
    # Requires Python 3.6 because Python is dropping support
    # for version 3.5 after September 2020 (as for 2020-09-05).
    # Reference: https://www.python.org/dev/peps/pep-0478/
    python_requires='>= 3.6',
)
