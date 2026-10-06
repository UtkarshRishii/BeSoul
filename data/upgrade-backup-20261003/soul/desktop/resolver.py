from __future__ import annotations

import os
import re
import shutil
import time
import json
from dataclasses import dataclass
from pathlib import Path
from soul.tools.models import ToolError
from soul.desktop.windows import require_windows


ALIASES = {"vs code": "visual studio code", "vscode": "visual studio code", "code": "visual studio code"}
BLOCKED = {"cmd", "powershell", "pwsh", "python", "pythonw", "wscript", "cscript", "mshta",
           "rundll32", "regsvr32", "msiexec", "regedit", "control", "bash", "wsl"}


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


@dataclass(frozen=True)
class Application:
    name: str
    executable: Path
    shortcut: Path | None = None


class ApplicationResolver:
    """Discover locally installed apps; aliases only resolve names, never user intent."""

    _cache: list[Application] = []
    _cached_at = 0.0
    cache_path = Path(__file__).resolve().parents[2] / "data" / "applications-index.json"

    def discover(self) -> list[Application]:
        if self._cache and time.monotonic() - self._cached_at < 120:
            return self._cache
        try:
            saved = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if time.time() - saved["created"] < 600:
                type(self)._cache = [Application(item["name"], Path(item["executable"]),
                                               Path(item["shortcut"]) if item["shortcut"] else None)
                                    for item in saved["applications"]]
                type(self)._cached_at = time.monotonic()
                return self._cache
        except (OSError, ValueError, KeyError, TypeError):
            pass
        require_windows()
        import winreg
        import win32com.client
        apps: dict[tuple[str, str], Application] = {}

        def add(name, executable, shortcut=None):
            path = Path(os.path.expandvars(str(executable).strip('"')))
            if path.suffix.lower() != ".exe" or not path.is_file() or path.stem.lower() in BLOCKED:
                return
            apps[(normalized(name), str(path).lower())] = Application(name, path, shortcut)

        shell = win32com.client.Dispatch("WScript.Shell")
        for root in [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
                     Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]:
            if root.is_dir():
                for link in root.rglob("*.lnk"):
                    try:
                        shortcut = shell.CreateShortcut(str(link))
                        add(link.stem, shortcut.TargetPath, link)
                    except Exception:
                        continue
        for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            for view in [winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]:
                try:
                    with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ | view) as root:
                        for i in range(winreg.QueryInfoKey(root)[0]):
                            name = winreg.EnumKey(root, i)
                            try:
                                with winreg.OpenKey(root, name) as sub:
                                    add(Path(name).stem, winreg.QueryValue(sub, None))
                            except OSError:
                                continue
                except OSError:
                    pass
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            path = Path(directory)
            if path.is_dir():
                try:
                    for exe in path.glob("*.exe"):
                        add(exe.stem, exe)
                except OSError:
                    pass
        # Shallow known install roots add apps lacking shortcuts without scanning user documents.
        for variable in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"]:
            root = Path(os.environ.get(variable, ""))
            if variable == "LOCALAPPDATA":
                root /= "Programs"
            if root.is_dir():
                for pattern in ["*/*.exe", "*/*/*.exe"]:
                    for exe in root.glob(pattern):
                        if not any(word in exe.stem.lower() for word in ["unins", "setup", "install", "update", "crash"]):
                            add(exe.stem, exe)
        type(self)._cache = list(apps.values())
        type(self)._cached_at = time.monotonic()
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps({"created": time.time(), "applications": [
                {"name": app.name, "executable": str(app.executable), "shortcut": str(app.shortcut) if app.shortcut else None}
                for app in self._cache]}), encoding="utf-8")
        except OSError:
            pass  # App discovery still works when the optional cache is unwritable.
        return self._cache

    def resolve(self, name: str) -> Application:
        query = normalized(name)
        query = ALIASES.get(query, query)
        candidates: dict[str, tuple[int, Application]] = {}
        path_match = shutil.which(name) if not any(c in name for c in "\\/:") else None
        for app in self.discover():
            if app.executable.stem.lower() in BLOCKED or app.executable.suffix.lower() != ".exe":
                continue
            names = {normalized(app.name), normalized(app.executable.stem)}
            score = max(100 if query == n else 70 if query and query in n else 0 for n in names)
            if score:
                if app.shortcut:
                    score += 5  # Prefer the user's installed Start Menu entry over helper executables.
                if path_match and str(app.executable).lower() == str(Path(path_match)).lower():
                    score += 3  # Follow the OS's PATH precedence for duplicate system executables.
                key = str(app.executable).lower()
                if key not in candidates or candidates[key][0] < score:
                    candidates[key] = (score, app)
        ranked = sorted(candidates.values(), key=lambda item: item[0], reverse=True)
        if not ranked:
            raise ToolError("APP_NOT_FOUND", "No installed application matched that name.")
        if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            names = ", ".join(app.name for _, app in ranked[:5])
            raise ToolError("AMBIGUOUS_APP", "Several applications match; specify one: " + names)
        if not ranked[0][1].executable.is_file():
            raise ToolError("APP_NOT_FOUND", "The indexed application was removed. The application index refreshes within ten minutes.")
        return ranked[0][1]
