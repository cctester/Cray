"""
Built-in plugins for Cray.
"""

from cray.plugins.builtin.shell import ShellPlugin
from cray.plugins.builtin.http import HttpPlugin
from cray.plugins.builtin.file import FilePlugin
from cray.plugins.builtin.email import EmailPlugin
from cray.plugins.builtin.json_ import JsonPlugin
from cray.plugins.builtin.notify import NotifyPlugin
from cray.plugins.builtin.math_ import MathPlugin
from cray.plugins.builtin.text import TextPlugin
from cray.plugins.builtin.database import DatabasePlugin
from cray.plugins.builtin.git import GitPlugin
from cray.plugins.builtin.redis_ import RedisPlugin

__all__ = [
    "ShellPlugin",
    "HttpPlugin",
    "FilePlugin",
    "EmailPlugin",
    "JsonPlugin",
    "NotifyPlugin",
    "MathPlugin",
    "TextPlugin",
    "DatabasePlugin",
    "GitPlugin",
    "RedisPlugin",
]
