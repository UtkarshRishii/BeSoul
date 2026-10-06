from __future__ import annotations
import re
from urllib.parse import urlsplit, urlunsplit, quote_plus
from pydantic import Field
from soul.tools.models import Arguments, ToolResult, ToolError


class URLArguments(Arguments):
    url: str = Field(min_length=1, max_length=4096)


class QueryArguments(Arguments):
    query: str = Field(min_length=1, max_length=500)


def normalize_url(value: str) -> str:
    value = value.strip()
    if any(ord(c) < 33 for c in value) or "\\" in value:
        raise ToolError("INVALID_URL", "URL contains whitespace, control characters or backslashes.")
    if "://" not in value:
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
            raise ToolError("INVALID_URL", "Only HTTP and HTTPS URLs are allowed.")
        value = "https://" + value
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise ValueError()
        _ = parts.port
        if not re.fullmatch(r"[A-Za-z0-9.:-]+", parts.hostname.encode("idna").decode()):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise ToolError("INVALID_URL", "Provide a valid HTTP(S) URL without embedded credentials.") from None
    return urlunsplit(parts)


class BrowserTools:
    def __init__(self, bridge):
        self.bridge = bridge
        self.last_url: str | None = None

    async def open_url(self, args: URLArguments) -> ToolResult:
        url = normalize_url(args.url)
        await self.bridge.call("open_url", url=url)
        self.last_url = url
        return ToolResult(success=True, message="URL handed to the default browser; page load is not yet verified.", data={"url": url})

    async def search_web(self, args: QueryArguments) -> ToolResult:
        return await self.open_url(URLArguments(url="https://www.google.com/search?q=" + quote_plus(args.query)))

    async def search_youtube(self, args: QueryArguments) -> ToolResult:
        return await self.open_url(URLArguments(url="https://www.youtube.com/results?search_query=" + quote_plus(args.query)))
