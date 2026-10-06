from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from soul.ui_bridge.input import DesktopInputProvider
from soul.ui_bridge.renderer import DesktopRenderer
from soul.ui_bridge.server import DesktopServer


class DesktopRuntime:
    """Run the Python core in its own asyncio thread while WinForms owns main."""

    def __init__(self, *, preview: bool = False) -> None:
        self.preview = preview
        self.started = threading.Event()
        self.thread = threading.Thread(target=self._run, name="soul-runtime", daemon=True)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.shutdown: asyncio.Event | None = None
        self.url = ""
        self.error: BaseException | None = None
        self.server: DesktopServer | None = None
        self.native_handle = 0

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as exc:
            self.error = exc
            self.started.set()

    async def _serve(self) -> None:
        from soul.config.settings import Settings
        from soul.events import EventBus

        self.loop = asyncio.get_running_loop()
        self.shutdown = asyncio.Event()
        settings = Settings.load()
        events = EventBus()
        input_provider = DesktopInputProvider()
        renderer = DesktopRenderer(events)
        server = DesktopServer(events, settings, input_provider, preview=self.preview)
        self.server = server
        self.url = await server.start()
        self.started.set()
        core_task: asyncio.Task[Any] | None = None
        try:
            if not self.preview:
                from soul.core.lifecycle import run

                async def core() -> None:
                    try:
                        result = await run(renderer.console, renderer=renderer, input_provider=input_provider,
                                           confirm_callback=server.confirm, events=events,
                                           on_ready=self._attach_assistant, settings=settings)
                        if result:
                            events.publish("StartupFailed", {"message": "SOUL needs configuration before it can connect."})
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logging.getLogger("soul").exception("desktop_core_startup_failed")
                        renderer.error("SOUL could not initialize. Check your model configuration and data permissions.")
                        events.publish("StartupFailed", {})

                core_task = asyncio.create_task(core(), name="desktop-core")
            await self.shutdown.wait()
        finally:
            input_provider.close()
            if core_task and not core_task.done():
                core_task.cancel()
                await asyncio.gather(core_task, return_exceptions=True)
            await server.close()

    def start(self) -> str:
        self.thread.start()
        if not self.started.wait(15):
            raise RuntimeError("Desktop startup timed out.")
        if self.error:
            raise self.error
        return self.url

    def close(self) -> None:
        if self.loop and self.shutdown and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.shutdown.set)
        self.thread.join(timeout=10)

    def _attach_assistant(self, assistant: Any) -> None:
        assert self.server is not None
        self.server.attach_assistant(assistant)
        if self.native_handle and assistant.desktop_context:
            assistant.desktop_context.register_self_window(self.native_handle)

    def register_window(self, window: Any) -> None:
        self.native_handle = int(window.native.Handle.ToInt64())
        if self.loop and self.server and self.server.assistant:
            self.loop.call_soon_threadsafe(self._attach_assistant, self.server.assistant)


def install_navigation_guard(window: Any, origin: str) -> None:
    """Pin the native WebView to the local app; user text cannot open web pages."""
    expected = urlsplit(origin)

    def guard(sender: Any, args: Any) -> None:
        destination = urlsplit(str(args.Uri))
        if (destination.scheme, destination.netloc) != (expected.scheme, expected.netloc):
            args.Cancel = True

    browser = window.native.browser
    browser.webview.NavigationStarting += guard
    window._soul_navigation_guard = guard


def main(*, preview: bool = False, serve_preview: bool = False) -> int:
    runtime = DesktopRuntime(preview=preview or serve_preview)
    try:
        url = runtime.start()
        if serve_preview:
            print(url, flush=True)
            while runtime.thread.is_alive():
                runtime.thread.join(timeout=1)
            return 0
        import webview

        webview.settings["ALLOW_FILE_URLS"] = False
        webview.settings["ALLOW_DOWNLOADS"] = False
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        if sys.platform == "win32":
            # Give Soul its own taskbar group instead of the Python host's icon.
            try:
                import ctypes

                set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
                set_app_id.argtypes = [ctypes.c_wchar_p]
                set_app_id.restype = ctypes.c_long
                set_app_id("Soul.Desktop.Intelligence")
            except (AttributeError, OSError):
                logging.getLogger("soul").debug("native_app_id_unavailable", exc_info=True)
        window = webview.create_window("SOUL", url, width=1320, height=900,
                                       min_size=(860, 640), background_color="#0d1528")
        def set_window_icon() -> None:
            if sys.platform != "win32":
                return
            try:
                icon_path = Path(__file__).resolve().parent / "icon.ico"
                native = getattr(window, "native", None)
                if not icon_path.is_file() or native is None:
                    return
                from System.Drawing import Icon  # type: ignore

                # WinForms sets both the titlebar and taskbar icons. Retain the
                # managed object for the window lifetime; avoid leaking raw HICONs.
                if not getattr(window, "_soul_window_icon", None):
                    window._soul_window_icon = Icon(str(icon_path))
                native.Icon = window._soul_window_icon
            except Exception:
                logging.getLogger("soul").debug("native_window_icon_unavailable", exc_info=True)

        def release_window_icon() -> None:
            icon = getattr(window, "_soul_window_icon", None)
            if icon is not None:
                try:
                    icon.Dispose()
                except Exception:
                    logging.getLogger("soul").debug("native_window_icon_cleanup_failed", exc_info=True)
                window._soul_window_icon = None

        def before_show() -> None:
            install_navigation_guard(window, runtime.server.origin)
            runtime.register_window(window)
            set_window_icon()

        def on_shown() -> None:
            set_window_icon()

        window.events.before_show += before_show
        window.events.shown += on_shown
        window.events.closed += runtime.close
        window.events.closed += release_window_icon
        webview.start(gui="edgechromium", debug=False, private_mode=True)
        return 0
    except (KeyboardInterrupt, EOFError):
        return 0
    except ImportError:
        print("Desktop dependencies are missing. Install requirements.txt, or run python main.py --cli.", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        logging.getLogger("soul").exception("desktop_shell_failed")
        print("SOUL's desktop window could not start. Check Microsoft Edge WebView2 or run python main.py --cli.",
              file=sys.stderr)
        return 1
    finally:
        runtime.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SOUL native Windows presentation shell")
    parser.add_argument("--preview", action="store_true", help="Open the UI without AI, microphone or desktop access")
    parser.add_argument("--serve-preview", action="store_true", help="Serve the unconnected UI for local browser inspection")
    arguments = parser.parse_args()
    raise SystemExit(main(preview=arguments.preview, serve_preview=arguments.serve_preview))
