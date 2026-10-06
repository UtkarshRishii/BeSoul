import asyncio
import logging
import sys


def main() -> int:
    # Windows redirected streams otherwise use a legacy code page that cannot render the UI.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        from soul.cli.console import make_console
        from soul.core.lifecycle import run
    except ImportError:
        print("Install dependencies first: python -m pip install -r requirements.txt")
        return 1
    except Exception:
        print("Soul could not load its modules. Check your installation.")
        return 1
    console = make_console()
    try:
        return asyncio.run(run(console))
    except (KeyboardInterrupt, EOFError):
        console.print("[muted]Soul stopped.[/]")
        return 0
    except Exception:
        logging.getLogger("soul").exception("startup_failed") if logging.getLogger("soul").handlers else None
        console.print("[error]Soul could not start. Check .env values, paths and permissions. See data/soul.log if available.[/]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
