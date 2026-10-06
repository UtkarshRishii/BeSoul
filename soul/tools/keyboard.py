"""Narrow keyboard schemas shared by the agent and its isolated OS worker."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from soul.tools.models import Arguments, ToolError


Key = Literal["tab", "enter", "escape", "space", "backspace", "delete", "up", "down", "left", "right",
              "home", "end", "pageup", "pagedown"]
Shortcut = Literal["ctrl+a", "ctrl+c", "ctrl+f", "ctrl+s", "ctrl+z", "ctrl+y", "ctrl+home", "ctrl+end",
                   "ctrl+shift+left", "ctrl+shift+right", "shift+tab", "shift+left", "shift+right",
                   "shift+home", "shift+end"]

KEY_CODES = {"tab": 0x09, "enter": 0x0D, "escape": 0x1B, "space": 0x20, "backspace": 0x08,
             "delete": 0x2E, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
             "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
             "ctrl": 0x11, "shift": 0x10, **{letter: ord(letter.upper()) for letter in "acfszy"}}
ALLOWED_SHORTCUTS = frozenset(Shortcut.__args__)
ALLOWED_KEYS = frozenset(Key.__args__)
CONFIRM_KEYS = frozenset({"enter", "delete", "backspace", "space"})
CONFIRM_SHORTCUTS = frozenset({"ctrl+s", "ctrl+z", "ctrl+y"})
SHELL_APPS = frozenset({"windowsterminal.exe", "powershell.exe", "pwsh.exe", "cmd.exe", "conhost.exe",
                        "openconsole.exe", "wsl.exe", "bash.exe", "mintty.exe", "wt.exe", "python.exe",
                        "pythonw.exe", "wscript.exe", "cscript.exe", "mshta.exe"})
SHELL_CONTROL = re.compile(r"\b(?:terminal|powershell|command prompt|debug console|python console|shell|xterm)\b", re.I)
UNSAFE_PROTOCOL = re.compile(r"^\s*(?:javascript|vbscript|data|file|shell|powershell|cmd|ms-msdt):", re.I)
SECRET_TEXT = re.compile(r"AIza[\w-]{20,}|(?:api.?key|password|secret|access.?token)\s*[:=]|-----BEGIN .*PRIVATE KEY", re.I)


class KeyboardTargetArguments(Arguments):
    target_id: str = Field(min_length=1, max_length=64)


class TypeTextArguments(KeyboardTargetArguments):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    text: str = Field(min_length=1, max_length=2000, strict=True, repr=False)

    @field_validator("text")
    @classmethod
    def plain_text_only(cls, value: str) -> str:
        validate_text(value)
        return value


class PressKeyArguments(KeyboardTargetArguments):
    key: Key


class ShortcutArguments(KeyboardTargetArguments):
    shortcut: Shortcut


def validate_text(text: str) -> None:
    if not isinstance(text, str) or not 1 <= len(text) <= 2000:
        raise ValueError("Typing requires 1 to 2000 characters.")
    if any(ord(character) < 32 or ord(character) == 127 or 0xD800 <= ord(character) <= 0xDFFF
           for character in text):
        raise ValueError("Control characters, line breaks and invalid Unicode are not allowed in typed text.")
    if SECRET_TEXT.search(text):
        raise ValueError("Enter credentials manually; automated credential entry is disabled.")
    if UNSAFE_PROTOCOL.search(text):
        raise ValueError("Executable and local-file protocols are not allowed in automated typing.")


def restricted_input_window(window: dict) -> bool:
    return (window.get("application", "").lower() in SHELL_APPS or
            window.get("window_class", "").lower() in {"consolewindowclass", "cascadia_hosting_window_class"} or
            (window.get("window_class") == "#32770" and window.get("title", "").strip().lower() == "run"))


def validate_keyboard_request(action: str, arguments: dict) -> None:
    """Repeat validation in the worker; callers cannot gain shell key combinations."""
    if action == "type_text":
        try:
            validate_text(arguments.get("text"))
        except (ValueError, TypeError):
            raise ToolError("INVALID_ARGUMENTS", "Typed input must be bounded plain text without credentials or controls.") from None
    elif action == "press_key" and arguments.get("key") in ALLOWED_KEYS:
        return
    elif action == "keyboard_shortcut" and arguments.get("shortcut") in ALLOWED_SHORTCUTS:
        return
    else:
        raise ToolError("RESTRICTED_KEY", "This keyboard operation is outside the allowed navigation and editing keys.")
