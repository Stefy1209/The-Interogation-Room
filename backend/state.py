"""
In-memory session store (owned by A). No database — everything lives here
for the lifetime of the process and is wiped by /api/reset or a server restart.
"""
from typing import Dict, List


class SessionState:
    def __init__(self, difficulty: str = "medium") -> None:
        self.chat_histories: Dict[str, List[dict]] = {}  # suspect_id -> [{role, content}, ...]
        self.claims: List[dict] = []
        self.contradictions: List[dict] = []
        self.questions_asked: int = 0
        self.next_claim_id: int = 1
        self.next_contradiction_id: int = 1
        self.difficulty: str = difficulty


_sessions: Dict[str, SessionState] = {}


def get_session(session_id: str) -> SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = SessionState()
    return _sessions[session_id]


def reset_session(session_id: str, difficulty: str = "medium") -> None:
    _sessions[session_id] = SessionState(difficulty=difficulty)


def reset_all() -> None:
    _sessions.clear()
