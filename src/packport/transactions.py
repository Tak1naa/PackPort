from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class TransactionLog:
    def __init__(self, state_home: Path | None = None) -> None:
        base = state_home or Path.home() / ".local" / "state"
        directory = base / "packport" / "transactions"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}.jsonl"
        self._lock = threading.Lock()

    def write(self, event: str, **fields: Any) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **fields,
        }
        # Paths and command output are useful; file contents and environment are
        # intentionally never accepted by this API.
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.path.chmod(0o600)

