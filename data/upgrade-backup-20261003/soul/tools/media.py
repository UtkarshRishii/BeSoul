from __future__ import annotations
from soul.tools.browser import URLArguments


class MediaTools:
    def __init__(self, bridge, browser):
        self.bridge, self.browser = bridge, browser

    async def play_youtube(self, args):
        data = await self.bridge.call("find_youtube", query=args.query)
        result = await self.browser.open_url(URLArguments(url=data["url"]))
        result.data.update(data)
        result.message = "Opened the matched YouTube video. Audible playback depends on browser autoplay/login; not yet verified."
        return result
