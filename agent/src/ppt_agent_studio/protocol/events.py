from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentEvent:
    seq: int
    session_id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    deck_id: str | None = None
    deck_revision: int | None = None

    def __post_init__(self) -> None:
        if self.seq < 0:
            raise ValueError("seq must be non-negative")
        if not self.session_id.strip():
            raise ValueError("session_id is required")
        if not self.type.strip():
            raise ValueError("type is required")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "seq": self.seq,
            "session_id": self.session_id,
            "type": self.type,
            "payload": dict(self.payload),
        }
        if self.deck_id is not None:
            out["deck_id"] = self.deck_id
        if self.deck_revision is not None:
            out["deck_revision"] = self.deck_revision
        return out
