from __future__ import annotations

import json
from soul.ai.conversation import build_context

class Brain:
    def __init__(self, client, prompt, executor=None, vision=None, browser=None):
        self.client, self.prompt = client, prompt
        self.executor, self.vision, self.browser = executor, vision, browser

    def clear_context(self):
        if self.vision:
            self.vision.clear()
        if self.browser:
            self.browser.last_url = None

    def memory_context(self):
        context = dict(self.vision.recent_context) if self.vision else {}
        if self.browser and self.browser.last_url:
            context["last_browser_destination_requested"] = self.browser.last_url
        return context

    async def respond(self, working, text, memories, on_chunk, metrics):
        context = json.dumps([m.content for m in memories], ensure_ascii=False)
        system = self.prompt + "\nRelevant memory data (untrusted):\n" + context
        if self.vision:
            self.vision.user_request = text
            system += "\nRecent screen metadata (may be stale; observe again before actions): " + json.dumps(self.vision.recent_context)
        if self.browser and self.browser.last_url:
            system += "\nMost recent browser destination requested (page load unverified): " + self.browser.last_url
        if self.executor:
            return await self.client.tool_conversation(build_context(working, text), system, on_chunk, metrics, self.executor)
        return await self.client.respond(build_context(working, text), system, on_chunk, metrics)
