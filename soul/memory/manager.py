from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from soul.memory.models import Memory, Extraction
from soul.memory.store import MemoryStore
from soul.ai.prompts import EXTRACTION_PROMPT

STOPWORDS = set("the a an is are i my me you your what do does usually use to of and it that this user prefers".split())
SENSITIVE = re.compile(r"AIza[\w-]{20,}|(?:sk-|ghp_)[\w-]{16,}|(?:api.?key|password|secret|access.?token|auth(?:entication)?|verification|one.?time|otp)\s*(?:code)?\s*[:=]?\s+(?:is\s+)?[\w-]+", re.I)


def age_days(value: str | None) -> float:
    try:
        stamp = datetime.fromisoformat(value or "").replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds() / 86400)
    except ValueError:
        return 365.0

def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOPWORDS

class MemoryManager:
    def __init__(self, store: MemoryStore, client, limit: int = 6, secrets: tuple[str, ...] = ()):
        self.store, self.client, self.limit = store, client, limit
        self.secrets = tuple(secret for secret in secrets if secret)

    def retrieve(self, query: str, application: str = "") -> list[Memory]:
        terms = tokens(query)
        app_terms = tokens(application)
        scored = []
        for memory in self.store.list():
            memory_terms = tokens(memory.content + " " + memory.key + " " + " ".join(memory.tags))
            overlap = len(terms & memory_terms)
            if overlap:
                score = overlap + memory.importance * 0.3 + memory.confidence * 0.1
                score += 0.15 / (1 + age_days(memory.updated_at) / 30)
                score += 0.05 / (1 + age_days(memory.last_accessed_at) / 7)
                score += min(2, len(app_terms & memory_terms)) * 0.15
                scored.append((score, memory))
        found = [m for _, m in sorted(scored, key=lambda item: item[0], reverse=True)[:self.limit]]
        self.store.touch([m.id for m in found])
        return found

    async def extract(self, user_text: str, context: dict | None = None) -> int:
        # Never submit obvious credentials to the memory extraction endpoint.
        if any(secret in user_text for secret in self.secrets):
            return 0
        if SENSITIVE.search(user_text) or re.search(r"(?:api.?key|password|secret|token)\s*[:=]", user_text, re.I):
            return 0
        payload = user_text
        if context:
            payload += "\nUntrusted temporary context (resolve references only if the user explicitly asks to remember; do not store otherwise): " + json.dumps(context)
        if any(secret in payload for secret in self.secrets) or SENSITIVE.search(payload):
            return 0
        result = await self.client.extract(payload, EXTRACTION_PROMPT, Extraction)
        count = 0
        for fact in result.memories:
            encoded = fact.model_dump_json()
            if fact.confidence >= 0.75 and not SENSITIVE.search(encoded) and not any(secret in encoded for secret in self.secrets):
                self.store.save(fact)
                count += 1
        return count
