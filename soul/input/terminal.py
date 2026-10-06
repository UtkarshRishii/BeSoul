from __future__ import annotations

class TerminalInputProvider:
    def __init__(self, console):
        self.console = console
        self.session = None

    async def get_input(self) -> str:
        import sys
        if not sys.stdin.isatty():
            return self.console.input("[accent]you › [/]")
        from prompt_toolkit import PromptSession
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.patch_stdout import patch_stdout
        if self.session is None:
            self.session = PromptSession()
        with patch_stdout(raw=True):
            return await self.session.prompt_async(HTML('<style fg="#7dd3c7"><b>you › </b></style>'))
