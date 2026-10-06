from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from soul.memory.models import Memory, MemoryFact

class SQLiteMemoryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=5)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, content TEXT NOT NULL,
            category TEXT NOT NULL, importance REAL NOT NULL, confidence REAL NOT NULL,
            tags TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_accessed_at TEXT, source TEXT NOT NULL DEFAULT 'user_explicit')""")
        self.connection.commit()

    def list(self) -> list[Memory]:
        rows = self.connection.execute("SELECT * FROM memories ORDER BY id").fetchall()
        return [Memory(**{**dict(row), "tags": json.loads(row["tags"])}) for row in rows]

    def save(self, fact: MemoryFact) -> None:
        with self.connection:
            self.connection.execute("""INSERT INTO memories
                (key,content,category,importance,confidence,tags) VALUES (?,?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET content=excluded.content,
                category=excluded.category,importance=excluded.importance,
                confidence=excluded.confidence,tags=excluded.tags,updated_at=CURRENT_TIMESTAMP""",
                (fact.key, fact.content, fact.category, fact.importance,
                 fact.confidence, json.dumps(fact.tags)))

    def touch(self, ids: list[int]) -> None:
        with self.connection:
            self.connection.executemany("UPDATE memories SET last_accessed_at=CURRENT_TIMESTAMP WHERE id=?", [(i,) for i in ids])

    def delete(self, memory_id: int) -> bool:
        with self.connection:
            return self.connection.execute("DELETE FROM memories WHERE id=?", (memory_id,)).rowcount > 0

    def clear(self) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM memories")

    def close(self) -> None:
        self.connection.close()
