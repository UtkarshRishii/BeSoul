from __future__ import annotations
import asyncio
import json
import os
import subprocess
import sys
import logging
from pathlib import Path
from soul.tools.models import ToolError


class DesktopBridge:
    """Persistent fixed-operation worker, launched from the package root on every platform."""

    def __init__(self):
        self.process = None
        self.lock = asyncio.Lock()
        self.stderr_task = None
        self.last_error = ""

    async def start(self):
        if self.process and self.process.returncode is None:
            return
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        env = dict(os.environ)
        env.pop("GEMINI_API_KEY", None)
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "soul.desktop.worker", "--serve",
            cwd=str(Path(__file__).resolve().parents[2]),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            creationflags=flags, env=env, limit=16 * 1024 * 1024)
        process = self.process
        async def drain():
            async for line in process.stderr:
                self.last_error = line.decode(errors="replace").strip()[-1000:]
                logging.getLogger("soul").debug("desktop_worker_stderr %s", self.last_error)
        self.stderr_task = asyncio.create_task(drain())

    async def close(self):
        process, self.process = self.process, None
        if process:
            if process.returncode is None:
                process.kill()
            await process.wait()
        if self.stderr_task:
            await self.stderr_task
            self.stderr_task = None

    async def call(self, operation: str, **arguments) -> dict:
        async with self.lock:
            await self.start()
            try:
                self.process.stdin.write((json.dumps({"operation": operation, "arguments": arguments}) + "\n").encode())
                await self.process.stdin.drain()
                stdout = await self.process.stdout.readline()
                response = json.loads(stdout)
            except BaseException as exc:
                await self.close()
                if isinstance(exc, asyncio.CancelledError):
                    raise
                logging.getLogger("soul").error("worker_protocol_failed error=%s detail=%s", type(exc).__name__, self.last_error)
                raise ToolError("WORKER_FAILED", "Desktop worker stopped. Launch Soul with its .venv Python; see the log for details.") from None
        if not response.get("success"):
            raise ToolError(response.get("error_code", "OS_ERROR"), response.get("message", "Operation failed."))
        return response.get("data", {})
